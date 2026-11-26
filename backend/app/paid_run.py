"""Serial request accounting, retaining unknown charges across bounded retries."""
import hashlib
import fcntl
import json
import math
import os
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path

_run = ContextVar('controlled_paid_run', default=None)
_ticket = ContextVar('controlled_paid_ticket', default=None)
_limits = ContextVar('frozen_execution_limits',default=None)
_task = ContextVar('controlled_provider_task',default=None)
_accounting = ContextVar('evaluation_accounting_only',default=False)
REQUEST_LIMITS = {'business_audit':16384,'qc':16384,'answerability':12288,'negative_subtype':8192,
                  'answer':65536,'judge':65536,'agent':32768,'query':16384,'revision':16384}


def _now():
    return datetime.now(timezone.utc).isoformat()


class PaidRun:
    def __init__(self, path, budget_yuan=None, prices=None, identity=None, *, identity_check=None, output_limits=None, request_policy=None):
        if type(budget_yuan) not in (int, float) or not math.isfinite(budget_yuan):
            budget_yuan = None
        self.path, self.budget, self.prices = Path(path), budget_yuan, prices or {}
        self.identity, self.identity_check = identity, identity_check
        self.request_policy = request_policy
        self.output_limits = output_limits
        self.calls, self.spent, self.stopped = [], 0., None
        self.stages = []
        try:
            descriptor = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            raise RuntimeError('Paid run ledger exists; no automatic resume') from None
        os.close(descriptor)
        self.save()

    def save(self):
        temporary = self.path.with_suffix(self.path.suffix+'.tmp')
        bounds = [call.get('upper_estimate_yuan') if call.get('upper_estimate_yuan') is not None
                  else call.get('reserved_yuan') for call in self.calls]
        data = {'identity':self.identity, 'budget_yuan':self.budget, 'price_snapshot':self.prices,
                'spent_yuan':self.spent, 'budget_used_upper_yuan':sum(bounds) if None not in bounds else None,
                'budget_enforcement':bool(getattr(self,'request_policy',None) and self.request_policy.get('budget_usd') is not None), 'available_yuan':None,
                'cost_unknown':any(c['status'] not in {'ok','rejected'} or c['status']=='ok'
                                   and c.get('upper_estimate_yuan') is None for c in self.calls),
                'stopped':self.stopped, 'calls':self.calls,'output_limits':self.output_limits,'stages':self.stages}
        if self.request_policy:
            from .paid_policy import E5_POLICY, e5_cost
            data['request_policy'] = self.request_policy
            if self.request_policy['kind'] == E5_POLICY:
                upper = e5_cost(self.calls)['budget_used_upper_usd']
                data.update(budget_used_upper_usd=upper, remaining_usd=max(0, self.request_policy['budget_usd']-upper))
        with temporary.open('w') as stream:
            json.dump(data,stream,ensure_ascii=False,indent=2); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary,self.path)
        descriptor = os.open(self.path.parent,os.O_RDONLY)
        try: os.fsync(descriptor)
        finally: os.close(descriptor)

    def stop(self, reason):
        with self.transaction(cancellable=False):
            self.stopped = self.stopped or reason
            self.save()

    @contextmanager
    def transaction(self, *, cancellable=True):
        """One process owns a paid policy ledger through settlement of each send."""
        if not self.request_policy:
            yield
            return
        from .providers import ProviderRequestError, check_provider_stop
        import time
        with self.path.with_suffix('.lock').open('a') as lock:
            while True:
                if cancellable:
                    check_provider_stop()
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    time.sleep(1)
            try:
                data = json.loads(self.path.read_text())
                if (data['identity'], data['price_snapshot'], data.get('request_policy'), data.get('output_limits')) != (
                        self.identity, self.prices, self.request_policy, self.output_limits):
                    raise ProviderRequestError('费用账本身份、价格、授权或请求上限已变化')
                if not isinstance(data['calls'], list) or any(not isinstance(call, dict) or 'status' not in call for call in data['calls']):
                    raise ValueError('invalid calls')
                self.calls, self.spent, self.stopped = data['calls'], data['spent_yuan'], data.get('stopped')
                self.stages = data.get('stages', [])
                self._retire_reserved()
            except (OSError, ValueError, KeyError, TypeError) as error:
                raise ProviderRequestError('费用账本缺失或损坏，请核对原账本') from error
            yield

    def reopen(self):
        """An explicit resume reopens the same authorization and balance."""
        with self.transaction():
            self._verify_identity()
            if self.stopped:
                self.stages.append({'resume_at': _now(), 'previous_stop': self.stopped})
                self.stopped = None
            self.save()

    def _verify_identity(self):
        from .providers import ProviderIdentityError

        try:
            matches = self.identity_check is not None and self.identity_check() == self.identity
        except (ValueError, OSError) as error:
            raise ProviderIdentityError(f'费用账本身份无法核对：{error}') from error
        if not matches:
            raise ProviderIdentityError('Paid run identity unavailable or changed')

    @classmethod
    def next_stage(cls,path,stage,identity_check,*,authorization=None,budget_yuan=None):
        """Continue a new stage while preserving prior unknown billing records."""
        path=Path(path);data=json.loads(path.read_text())
        if identity_check()!=data['identity']: raise RuntimeError('Paid continuation identity changed')
        stages=data.get('stages',[])
        if stage in [s.get('stage') for s in stages]: raise RuntimeError('Paid stage already claimed; no duplicate execution')
        run=cls.__new__(cls)
        run.path,run.budget,run.prices=path,data['budget_yuan'],data['price_snapshot']
        run.identity,run.identity_check=data['identity'],identity_check
        run.calls,run.spent,run.stopped=data['calls'],data['spent_yuan'],None
        run.output_limits=data['output_limits'];run.stages=[*stages,{'stage':stage,'claimed_at':datetime.now(timezone.utc).isoformat()}]
        run.request_policy=data.get('request_policy')
        run._retire_reserved()
        run.save();return run

    @classmethod
    def load_accounting(cls,path,identity_check):
        data=json.loads(Path(path).read_text());run=cls.__new__(cls)
        run.path,run.budget,run.prices=Path(path),data['budget_yuan'],data['price_snapshot']
        run.identity,run.identity_check=data['identity'],identity_check
        run.calls,run.spent,run.stopped=data['calls'],data['spent_yuan'],data.get('stopped')
        run.stages=data.get('stages',[]);run.output_limits=data.get('output_limits')
        run.request_policy=data.get('request_policy')
        run._retire_reserved()
        return run

    def _retire_reserved(self):
        from .paid_policy import E5_POLICY
        for index, call in enumerate(self.calls):
            if call.get('status') == 'reserved':
                # The old E5 runner wrote the unpriced reservation before saving
                # the USD bound, and only then allowed HTTP to start.
                old_unpriced = ((self.request_policy or {}).get('kind') == E5_POLICY
                                and index == len(self.calls)-1 and 'reservation_usd' not in call
                                and not call.get('raw_response_path'))
                if not call.get('sent_at') and (call.get('reserved_at') or old_unpriced):
                    call.update(status='rejected', upper_estimate_yuan=0., settlement='not_sent', settled_at=_now())
                else:
                    call.update(status='unknown', upper_estimate_yuan=None, recovery_reason='previous worker ended before settlement',
                                settled_at=_now())

    def begin(self, provider, model, payload):
        if getattr(self,'request_policy',None):
            from .paid_policy import guarded_begin
            return guarded_begin(self,provider,model,payload)
        return self._begin(provider,model,payload)

    def _begin(self, provider, model, payload, **reservation):
        from .providers import ProviderRequestError
        if self.stopped: raise ProviderRequestError('Paid run stopped: '+self.stopped)
        if any(call['status']=='reserved' for call in self.calls):
            raise ProviderRequestError('Serial paid run already has an in-flight request')
        self._verify_identity()
        rate = self.prices.get(model)
        if rate and (rate.get('provider') != provider or any(type(rate.get(key)) not in (int,float) or not math.isfinite(rate[key]) or rate[key]<0 for key in ('input','output','max_output'))):
            rate = None
        encoded = json.dumps(payload,ensure_ascii=False).encode()
        repeated_query = (max(0,len(payload.get('documents',[]))-1)*len(str(payload.get('query','')).encode())) if provider=='Alibaba' else 0
        # UTF-8 bytes plus framing allowance conservatively bound input tokens.
        bound = payload.get('max_tokens',rate['max_output'] if rate else None)
        if bound is not None and (type(bound) is not int or bound<0 or rate and bound>rate['max_output']):
            raise ProviderRequestError('Invalid output budget bound')
        if bound is not None and self.output_limits and _task.get() in self.output_limits and bound>self.output_limits[_task.get()]:
            raise ProviderRequestError('Frozen task output limit exceeded')
        reserved = ((len(encoded)+repeated_query+1024)*rate['input'] + bound*rate['output'])/1_000_000 if rate else None
        currency=rate.get('currency','CNY') if rate else None
        stamp = _now()
        call = {'provider':provider,'model':model,'status':'reserved','reserved_yuan':reserved if currency=='CNY' else None,
                'reservation_estimate':{'amount':reserved,'currency':currency} if reserved is not None else None,
                'request_sha256':hashlib.sha256(encoded).hexdigest(),'started_at':stamp,'reserved_at':stamp,
                'task':_task.get(),'max_tokens':payload.get('max_tokens'), **reservation}
        if _accounting.get():
            call.update(accounting_only=True)
            if not self.request_policy:
                call['request_payload'] = payload
        self.calls.append(call); self.save()
        return call

    def settle(self, call, usage):
        if call['status'] != 'reserved': raise RuntimeError('Duplicate payment Usage')
        call['settled_at'] = _now()
        if usage.get('status')=='rejected' and usage.get('request_execution_unknown') is False:
            call.update(status='rejected',usage=usage,upper_estimate_yuan=0.,settlement='provider_confirmed_rejection')
            self.save();return
        call['usage'] = usage
        prompt = usage.get('prompt_tokens',usage.get('total_tokens'))
        output = usage.get('completion_tokens',0 if call['provider']=='Alibaba' else None)
        if (usage.get('status')!='ok' or usage.get('provider')!=call['provider'] or usage.get('requested_model')!=call['model']
            or any(type(n) is not int or n<0 for n in (prompt,output))):
            call.update(status='unknown', upper_estimate_yuan=None, settlement='usage_unknown')
            self.save();return
        rate = self.prices.get(call['model'])
        if rate and (rate.get('provider') != call['provider'] or any(type(rate.get(key)) not in (int,float) or not math.isfinite(rate[key]) or rate[key]<0 for key in ('input','output'))):
            rate = None
        # Cache misses and peak prices bound the estimate; never claim account debit.
        amount = (prompt*rate['input']+output*rate['output'])/1_000_000 if rate else None
        currency=rate.get('currency','CNY') if rate else None
        if amount is not None and currency=='CNY':self.spent += amount
        call.update(status='ok',usage=usage,upper_estimate_yuan=amount if currency=='CNY' else None,
                    estimated_cost={'amount':amount,'currency':currency} if amount is not None else None)
        self.save()

    def limit(self):
        task = _task.get()
        if not self.output_limits or task not in self.output_limits:
            raise RuntimeError('Controlled request task limit unavailable')
        return self.output_limits[task]

    def response(self, body):
        call = _ticket.get()
        if call is None: return
        path = self.path.parent/f'{self.path.stem}-response-{len(self.calls):04d}.json'
        try:
            with path.open('x') as stream:
                json.dump(body,stream,ensure_ascii=False);stream.flush();os.fsync(stream.fileno())
        except OSError as error:
            error.provider_blocked = True
            call['response_save_error'] = str(error)
            raise
        call.update(raw_response_path=str(path), response_saved_at=_now())
        self.save()


def current_paid_run(): return _run.get()


@contextmanager
def provider_task(task):
    token = _task.set(task)
    try: yield
    finally: _task.reset(token)


@contextmanager
def controlled_run(run):
    from .task_leases import LeaseLost

    token = _run.set(run)
    try: yield
    except LeaseLost:
        # A replaced worker cannot stop the authorization used by its successor.
        raise
    except Exception as error:
        if run is not None: run.stop(type(error).__name__)
        raise
    finally: _run.reset(token)


@contextmanager
def paid_request(provider, model, payload, *, database_path=None):
    run = current_paid_run()
    if run is None and database_path is None:
        yield
        return
    from .providers import ProviderIdentityError, check_provider_stop, permanent_provider_error
    standalone = run is None
    if standalone:
        from .paid_policy import standalone_ledger
        try:
            run = standalone_ledger(database_path)
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
            raise ProviderIdentityError('费用账本缺失或损坏，请核对原账本') from error
    scope = _run.set(run)
    try:
        with run.transaction():
            check_provider_stop()
            call = run.begin(provider,model,payload)
            token = _ticket.set(call)
            try:
                check_provider_stop()
                call['sent_at'] = _now()
                run.save()
                yield
            except Exception as error:
                call['error_type'] = type(error).__name__
                if not standalone and permanent_provider_error(error):
                    run.stopped = run.stopped or type(error).__name__
                run.save()
                raise
            finally:
                _ticket.reset(token)
                if call['status'] == 'reserved':
                    run._retire_reserved()
                    run.save()
    finally:
        _run.reset(scope)


def payment_usage(usage):
    run,call = current_paid_run(),_ticket.get()
    if run is not None and call is not None: run.settle(call,usage)


@contextmanager
def execution_limits(limits):
    token=_limits.set(limits)
    try:yield
    finally:_limits.reset(token)


def current_request_limit():
    run=current_paid_run()
    limits=run.output_limits if run and run.output_limits is not None else _limits.get()
    if limits is None:return None
    if _task.get() not in limits:raise RuntimeError('Frozen task limit unavailable')
    return limits[_task.get()]

@contextmanager
def accounting_only():
    token=_accounting.set(True)
    try:yield
    finally:_accounting.reset(token)


def unsettled_usage(usage):
    if usage.get('status')=='rejected' and usage.get('request_execution_unknown') is False:return False
    return usage.get('provider') in {'Alibaba','DeepSeek'} and (usage.get('status')!='ok'
        or type(usage.get('prompt_tokens',usage.get('total_tokens'))) is not int
        or usage.get('provider')=='DeepSeek' and type(usage.get('completion_tokens')) is not int)


def require_reconciled_execution(result):
    """Keep ledger integrity checks; unknown billing no longer blocks recovery."""
    path=result.get('auto_recovery',{}).get('ledger_path')
    if path:
        try:data=json.loads(Path(path).read_text())
        except (OSError,ValueError):raise ValueError('费用账本缺失或无效，禁止续跑') from None
        if not isinstance(data,dict) or not isinstance(data.get('calls'),list) or any(not isinstance(c,dict) for c in data['calls']):raise ValueError('费用账本格式无效')
        if data.get('identity')!=result.get('auto_recovery',{}).get('ledger_identity'):
            raise ValueError('费用账本身份不匹配')
