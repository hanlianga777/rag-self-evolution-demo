"""Opt-in, single serial paid run. No retry or implicit continuation."""
import hashlib
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
REQUEST_LIMITS = {'business_audit':16384,'qc':16384,'answerability':12288,'negative_subtype':8192,
                  'answer':8192,'judge':32768,'agent':16384,'query':4096,'revision':16384}


class PaidRun:
    def __init__(self, path, budget_yuan, prices, identity, *, identity_check=None, output_limits=None):
        if not math.isfinite(budget_yuan) or budget_yuan <= 0:
            raise ValueError('Invalid payment budget')
        self.path, self.budget, self.prices = Path(path), budget_yuan, prices
        self.identity, self.identity_check = identity, identity_check
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
        data = {'identity':self.identity, 'budget_yuan':self.budget, 'price_snapshot':self.prices,
                'spent_yuan':self.spent, 'available_yuan':max(0.,self.budget-self.spent-sum(c['reserved_yuan'] for c in self.calls if c['status']=='reserved')),
                'resume_authorization':getattr(self,'resume_authorization',None), 'stopped':self.stopped, 'calls':self.calls,'output_limits':self.output_limits,'stages':self.stages}
        with temporary.open('w') as stream:
            json.dump(data,stream,ensure_ascii=False,indent=2); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary,self.path)
        descriptor = os.open(self.path.parent,os.O_RDONLY)
        try: os.fsync(descriptor)
        finally: os.close(descriptor)

    def stop(self, reason):
        self.stopped = self.stopped or reason
        self.save()

    @classmethod
    def next_stage(cls,path,stage,identity_check,*,authorization=None,budget_yuan=None):
        """Explicit continuation between completed stages, never retry an unknown charge."""
        path=Path(path);data=json.loads(path.read_text())
        prior=data.get('resume_authorization')
        unresolved=[i for i,c in enumerate(data['calls']) if c['status']!='ok' and (not prior or i!=prior['unknown_call_index'])]
        if authorization is not None:
            if prior or len(unresolved)!=1 or authorization.get('source')!='direct_user_instruction' or authorization.get('max_judge_retries')!=1:
                raise RuntimeError('One explicit unknown Judge retry authorization required')
            index=unresolved[0];call=data['calls'][index]
            if call['status']!='reserved' or call.get('task')!='judge' or call['request_sha256']!=authorization.get('request_sha256'):
                raise RuntimeError('Unknown request does not match authorized Judge')
            prior={**authorization,'unknown_call_index':index,'authorized_at':datetime.now(timezone.utc).isoformat()}
        elif data['stopped'] or unresolved:
            raise RuntimeError('Paid stage has stopped or uncertain Usage; cannot continue')
        if identity_check()!=data['identity']: raise RuntimeError('Paid continuation identity changed')
        stages=data.get('stages',[])
        if stage in [s['stage'] for s in stages]: raise RuntimeError('Paid stage already claimed; no duplicate execution')
        run=cls.__new__(cls)
        run.path,run.budget,run.prices=path,data['budget_yuan'],data['price_snapshot']
        run.identity,run.identity_check=data['identity'],identity_check
        run.calls,run.spent,run.stopped=data['calls'],data['spent_yuan'],None
        run.resume_authorization=prior
        if budget_yuan is not None:
            if not math.isfinite(budget_yuan) or not 0<budget_yuan<=run.budget: raise ValueError('Resume budget must tighten existing limit')
            run.budget=budget_yuan
        run.output_limits=data['output_limits'];run.stages=[*stages,{'stage':stage,'claimed_at':datetime.now(timezone.utc).isoformat()}]
        run.save();return run

    def begin(self, provider, model, payload):
        if self.stopped: raise RuntimeError('Paid run stopped: '+self.stopped)
        auth=getattr(self,'resume_authorization',None)
        if any(call['status']=='reserved' and (not auth or i!=auth['unknown_call_index']) for i,call in enumerate(self.calls)):
            raise RuntimeError('Serial paid run already has an in-flight request')
        if self.identity_check is None or self.identity_check() != self.identity:
            raise RuntimeError('Paid run identity unavailable or changed')
        rate = self.prices.get(model)
        if not rate or rate.get('provider') != provider:
            raise RuntimeError('Payment price/model/provider unavailable')
        if any(type(rate.get(key)) not in (int,float) or not math.isfinite(rate[key]) or rate[key]<0 for key in ('input','output','max_output')):
            raise RuntimeError('Payment rate or output bound invalid')
        encoded = json.dumps(payload,ensure_ascii=False).encode()
        repeated_query = (max(0,len(payload.get('documents',[]))-1)*len(str(payload.get('query','')).encode())) if provider=='Alibaba' else 0
        # UTF-8 bytes plus framing allowance conservatively bound input tokens.
        bound = payload.get('max_tokens',rate['max_output'])
        if type(bound) is not int or not 0<=bound<=rate['max_output']: raise RuntimeError('Invalid output budget bound')
        reserved = ((len(encoded)+repeated_query+1024)*rate['input'] + bound*rate['output'])/1_000_000
        request_sha=hashlib.sha256(encoded).hexdigest()
        if auth:
            index=auth['unknown_call_index']
            if len(self.calls)==index+1 and (request_sha!=auth.get('retry_request_sha256',auth['request_sha256']) or _task.get()!='judge'):
                raise RuntimeError('Resume must first reuse saved answer and retry only missing Judge')
            if not self.stages[-1]['stage'].startswith(('agent-','candidate-')) and request_sha==auth.get('retry_request_sha256',auth['request_sha256']) and any(c['request_sha256']==request_sha for c in self.calls[index+1:]):
                raise RuntimeError('Authorized Judge retry already consumed')
        held=sum(c['reserved_yuan'] for c in self.calls if c['status']=='reserved')
        if self.spent + held + reserved > self.budget: raise RuntimeError('Payment budget insufficient')
        call = {'provider':provider,'model':model,'status':'reserved','reserved_yuan':reserved,
                'request_sha256':hashlib.sha256(encoded).hexdigest(),'started_at':datetime.now(timezone.utc).isoformat(),
                'task':_task.get(),'max_tokens':payload.get('max_tokens')}
        if auth and not self.stages[-1]['stage'].startswith(('agent-','candidate-')) and request_sha==auth.get('retry_request_sha256',auth['request_sha256']):call['retry_of_request_sha256']=auth['request_sha256']
        self.calls.append(call); self.save()
        return call

    def settle(self, call, usage):
        if call['status'] != 'reserved': raise RuntimeError('Duplicate payment Usage')
        call['usage'] = usage
        if usage.get('status')!='ok' or usage.get('provider')!=call['provider'] or usage.get('requested_model')!=call['model']:
            raise RuntimeError('Payment Usage identity/status invalid')
        prompt = usage.get('prompt_tokens',usage.get('total_tokens'))
        output = usage.get('completion_tokens',0 if call['provider']=='Alibaba' else None)
        if any(type(n) is not int or n<0 for n in (prompt,output)):
            raise RuntimeError('Payment Usage missing or invalid')
        rate = self.prices[call['model']]
        # Cache misses and peak prices bound the estimate; never claim account debit.
        amount = (prompt*rate['input']+output*rate['output'])/1_000_000
        self.spent += amount
        call.update(status='ok',usage=usage,upper_estimate_yuan=amount)
        self.save()
        if amount>call['reserved_yuan'] or self.spent>self.budget:
            raise RuntimeError('Payment budget/Usage bound exceeded')

    def limit(self):
        task = _task.get()
        if not self.output_limits or task not in self.output_limits:
            raise RuntimeError('Controlled request task limit unavailable')
        return self.output_limits[task]

    def response(self, body):
        call = _ticket.get()
        if call is None: return
        path = self.path.parent/f'{self.path.stem}-response-{len(self.calls):04d}.json'
        with path.open('x') as stream:
            json.dump(body,stream,ensure_ascii=False);stream.flush();os.fsync(stream.fileno())
        call['raw_response_path'] = str(path)
        self.save()


def current_paid_run(): return _run.get()


@contextmanager
def provider_task(task):
    token = _task.set(task)
    try: yield
    finally: _task.reset(token)


@contextmanager
def controlled_run(run):
    token = _run.set(run)
    try: yield
    except Exception as error:
        if run is not None: run.stop(type(error).__name__)
        raise
    finally: _run.reset(token)


@contextmanager
def paid_request(provider, model, payload):
    run = current_paid_run()
    if run is None:
        yield
        return
    token = None
    try:
        call = run.begin(provider,model,payload)
        token = _ticket.set(call)
        yield
        if call['status']!='ok': raise RuntimeError('Payment Usage missing')
    except Exception as error:
        run.stop(type(error).__name__)
        raise
    finally:
        if token is not None: _ticket.reset(token)


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
