"""Persist stages and RPC attempts; Judge format recovery is separate from transport."""
import time
import math
import hashlib
import json
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from .telemetry import collect_usage
from .paid_run import unsettled_usage

_request_checkpoint = ContextVar('evaluation_request_checkpoint', default=None)


@contextmanager
def request_checkpoint_scope(checkpoint, phase, run_id, on_state, check_stop):
    token = _request_checkpoint.set((checkpoint, phase, run_id, on_state, check_stop))
    try:
        yield
    finally:
        _request_checkpoint.reset(token)


def reopen_blocked_requests(checkpoint):
    """An explicit resume keeps completed RPCs and starts a fresh blocked-request window."""
    for request in checkpoint.get('provider_requests', {}).values():
        transport = request.get('transport')
        if transport and transport.get('state') == 'blocked':
            request.setdefault('transport_history', []).append(request.pop('transport'))
    for child in checkpoint.get('verdict_trials', {}).values():
        reopen_blocked_requests(child)
    for child in checkpoint.get('regression_review', {}).get('runs', []):
        reopen_blocked_requests(child)


def checkpoint_request(provider, model, endpoint, payload, action, *, reuse=True, transport_retry=False):
    """Persist a serial RPC inside its owning question/phase, never across Candidates."""
    from .providers import ProviderRequestError, request_with_retries
    context = _request_checkpoint.get()
    if context is None:
        return request_with_retries(action) if transport_retry else action()
    checkpoint, phase, run_id, on_state, check_stop = context
    check_stop()
    key = hashlib.sha256(json.dumps([phase, provider, model, endpoint, payload], sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    requests = checkpoint.setdefault('provider_requests', {})
    if not isinstance(requests, dict):
        raise ProviderRequestError('Provider 请求断点损坏')
    saved = requests.setdefault(key, {'phase':phase, 'provider':provider, 'model':model, 'attempts':[]})
    if (not isinstance(saved, dict) or not isinstance(saved.get('attempts'), list)
            or saved.get('status') == 'completed' and 'result' not in saved):
        raise ProviderRequestError('Provider 请求断点损坏')
    if saved.get('status') == 'completed' and (reuse or saved.get('persistence_pending')):
        if saved.get('persistence_pending'):
            on_state('running', phase=phase, durable=True)
            saved.pop('persistence_pending', None)
        return deepcopy(saved['result'])
    # A recovered worker may leave a request in flight. Keep its billing unknown
    # and start a separately accounted attempt under task006's revised policy.
    if saved.get('status') == 'inflight':
        for previous in saved['attempts']:
            if previous.get('status') == 'inflight':
                previous.update(status='unknown', recovery_reason='worker ended before request result was saved')
    def send():
        attempt = {'id':uuid.uuid4().hex, 'recorded_by_run_id':run_id, 'status':'inflight', 'usage':[]}
        saved['attempts'].append(attempt);saved['status'] = 'inflight'
        on_state('running', phase=phase, durable=True)
        try:
            with collect_usage() as usage:
                try:
                    value = action()
                finally:
                    for event in usage:event['checkpoint_request_id'] = attempt['id']
                    attempt['usage'] = usage
        except Exception as error:
            unknown = getattr(error, 'request_execution_unknown', None) is True or any(unsettled_usage(u) for u in attempt['usage'])
            attempt.update(status='unknown' if unknown else 'error', error_type=type(error).__name__)
            saved['status'] = attempt['status']
            on_state('running', phase=phase, durable=True)
            raise
        saved.update(status='completed', result=deepcopy(value))
        saved.pop('transport', None)
        attempt['status'] = 'completed'
        saved['persistence_pending'] = True
        on_state('running', phase=phase, durable=True)
        saved.pop('persistence_pending', None)
        return value

    if not transport_retry:
        return send()
    transport = saved.setdefault('transport', {})
    if not isinstance(transport, dict):
        raise ProviderRequestError('Provider 重试断点损坏')
    if transport.get('state') == 'ended':
        transport.clear()
    def persist_retry(state, **details):
        if state != 'sending':  # send() persists the count with its in-flight checkpoint.
            on_state(state, phase=phase, durable=True, **details)

    return request_with_retries(send, transport=transport, check_stop=check_stop,
                                on_state=persist_retry)


def checkpoint_usage(checkpoint):
    """RPC events also survive a worker dying before its outer stage attempt saves."""
    events = [u for a in checkpoint.get('attempts', []) for u in a.get('usage', [])]
    seen = {u.get('checkpoint_request_id') for u in events if u.get('checkpoint_request_id')}
    requests=[checkpoint.get('provider_requests',{}),*[h.get('provider_requests',{}) for h in checkpoint.get('manual_resume_history',[])]]
    for group in requests:
        for request in group.values():
            for attempt in request['attempts']:
                if attempt['id'] not in seen:events.extend(attempt.get('usage', []));seen.add(attempt['id'])
    return events


def judge_request_count(checkpoint, run_id):
    """Count semantic responses, independently of HTTP transport retry attempts."""
    return sum(max(1, sum(u.get('status') == 'ok' for u in attempt.get('usage', [])))
               for attempt in checkpoint.get('attempts', [])
               if attempt.get('phase') == 'judge' and attempt.get('recorded_by_run_id') == run_id
               and (attempt.get('status') == 'ok' or attempt.get('error_type') == 'ProviderInvalidResponse'))


def perform_stage(checkpoint,phase,action,run_id,*,automatic,check_stop,on_state):
    from .providers import ProviderInvalidResponse,ProviderTimeout,provider_error_details,stage_deadline,permanent_provider_error
    # Explicit Resume starts a new retry window; process recovery of this Run keeps its failures.
    prior=[a for a in checkpoint['attempts'] if a.get('phase')==phase and a.get('recorded_by_run_id')==run_id]
    failures=0;invalid_failures=0
    for a in reversed(prior):
        if a.get('status')=='ok':break
        failures+=1;invalid_failures+=a.get('error_type')=='ProviderInvalidResponse'
    windows=checkpoint.setdefault('phase_windows',{})
    window=windows.get(phase)
    requests = checkpoint.get('provider_requests', {})
    recovering = isinstance(requests, dict) and any(
        isinstance(request, dict) and request.get('phase') == phase and isinstance(request.get('transport'), dict)
        and request['transport'].get('state') in {'sending', 'request_retry', 'retry_wait', 'recovering', 'blocked'}
        for request in requests.values())
    if not window or window.get('run_id')!=run_id or recovering:
        window={'run_id':run_id,'started_at':time.time()};windows[phase]=window
    deadline=time.monotonic()+max(0,600-(time.time()-window['started_at']))
    if checkpoint.get('inflight')==phase:checkpoint.setdefault('unknown_execution',{})[phase]=True
    while True:
        check_stop()
        if (invalid_failures>=4 if phase=='judge' else failures>=3) or failures-invalid_failures>=3 or time.monotonic()>=deadline:
            last=checkpoint['attempts'][-1] if checkpoint['attempts'] else {}
            if (last.get('phase')==phase and last.get('recorded_by_run_id')==run_id
                    and last.get('status')=='error' and last.get('retryable') is True
                    and last.get('request_execution_unknown') is False):
                last['retryable']=False
                raise ProviderTimeout('Known Provider stage exhausted 3 attempts or 600 seconds')
            raise RuntimeError('Provider stage exhausted 3 attempts or 600 seconds')
        checkpoint['inflight']=phase
        on_state('running',phase=phase)
        started=time.perf_counter();usage=[]
        try:
            token = _request_checkpoint.set(_request_checkpoint.get() or (checkpoint,phase,run_id,on_state,check_stop))
            try:
                with collect_usage() as usage,stage_deadline(deadline,automatic=automatic,check_stop=check_stop):value=action()
            finally:
                _request_checkpoint.reset(token)
            # Missing Usage remains an accounting fact; a valid result is usable.
        except Exception as error:
            failures+=1
            attempt={'phase':phase,'status':'error','error_type':type(error).__name__,'error':str(error),
                     'cause_type':type(error.__cause__).__name__ if error.__cause__ else None,
                     'cause_message':str(error.__cause__) if error.__cause__ else None,'usage':usage,
                     'elapsed_ms':round((time.perf_counter()-started)*1000),
                     'raw_provider_response':getattr(error,'raw_provider_response',None),
                     'response_metadata':getattr(error,'response_metadata',None),'provider_status_code':getattr(error,'status_code',None),'recorded_by_run_id':run_id}
            attempt['provider_error']=provider_error_details(error,phase)
            explicit=getattr(error,'request_execution_unknown',None)
            unknown=explicit if explicit is not None else any(unsettled_usage(u) for u in usage if u.get('request_execution_unknown') is not False)
            billing_unknown=getattr(error,'billing_unknown',False) or any(unsettled_usage(u) for u in usage)
            if billing_unknown:checkpoint.setdefault('unsettled_usage',{})[phase]=True
            attempt['billing_unknown']=billing_unknown
            responses=max(1,sum(u.get('status')=='ok' for u in usage))
            retry = not isinstance(error, InterruptedError) and not permanent_provider_error(error) and time.monotonic()<deadline
            # A managed HTTP request keeps its own attempt limit and recovery state.
            transport_error=error
            while transport_error is not None:
                if getattr(transport_error,'provider_retry_exhausted',False):
                    retry=False
                    break
                transport_error=transport_error.__cause__
            if isinstance(error, ProviderInvalidResponse):
                retry = retry and phase=='judge' and invalid_failures<3 and judge_request_count(checkpoint,run_id)+responses<4
            else:
                retry = retry and failures-invalid_failures<3
            # Four invalid replies end this pass; validation stays strict.
            if isinstance(error,ProviderInvalidResponse):
                invalid_failures+=1
                if invalid_failures>=4:retry=False
            attempt['request_execution_unknown']=unknown
            if unknown:checkpoint.setdefault('unknown_execution',{})[phase]=True
            attempt['retryable']=retry;checkpoint['attempts'].append(attempt);checkpoint.pop('inflight',None)
            if permanent_provider_error(error):
                on_state('blocked', phase=phase, durable=True, error=str(error),
                         resume_hint='排除所列故障后，使用原实验和授权从断点手动续跑')
            if retry:
                delay=min(60,2**min(failures-1,6))
                delay=min(delay,max(0,deadline-time.monotonic()))
                attempt['retry_delay_seconds']=delay
                on_state('retrying',phase=phase,error=str(error),retry_count=failures)
                for _ in range(math.ceil(delay)):
                    check_stop();time.sleep(min(1,delay));delay-=min(1,delay)
                continue
            raise
        checkpoint['attempts'].append({'phase':phase,'status':'ok','recorded_by_run_id':run_id,'usage':usage,'elapsed_ms':round((time.perf_counter()-started)*1000)})
        checkpoint.pop('inflight',None);return value

def correction_for(checkpoint,run_id):
    previous=next((a for a in reversed(checkpoint['attempts']) if a.get('phase')=='judge' and a.get('error_type')=='ProviderInvalidResponse'),None)
    return {'error':previous['error'],'previous_response':previous.get('raw_provider_response')} if previous else None
