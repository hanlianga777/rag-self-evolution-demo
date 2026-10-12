"""Opt-in, single serial paid run. No retry, automatic resume or request changes."""
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


class PaidRun:
    def __init__(self, path, budget_yuan, prices, identity, *, identity_check=None):
        if not math.isfinite(budget_yuan) or budget_yuan <= 0:
            raise ValueError('Invalid payment budget')
        self.path, self.budget, self.prices = Path(path), budget_yuan, prices
        self.identity, self.identity_check = identity, identity_check
        self.calls, self.spent, self.stopped = [], 0., None
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
                'stopped':self.stopped, 'calls':self.calls}
        with temporary.open('w') as stream:
            json.dump(data,stream,ensure_ascii=False,indent=2); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary,self.path)
        descriptor = os.open(self.path.parent,os.O_RDONLY)
        try: os.fsync(descriptor)
        finally: os.close(descriptor)

    def stop(self, reason):
        self.stopped = reason
        self.save()

    def begin(self, provider, model, payload):
        if self.stopped: raise RuntimeError('Paid run stopped: '+self.stopped)
        if any(call['status']=='reserved' for call in self.calls):
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
        reserved = ((len(encoded)+repeated_query+1024)*rate['input'] + rate['max_output']*rate['output'])/1_000_000
        if self.spent + reserved > self.budget: raise RuntimeError('Payment budget insufficient')
        call = {'provider':provider,'model':model,'status':'reserved','reserved_yuan':reserved,
                'request_sha256':hashlib.sha256(encoded).hexdigest(),'started_at':datetime.now(timezone.utc).isoformat()}
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


def current_paid_run(): return _run.get()


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
