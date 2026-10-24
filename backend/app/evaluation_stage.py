"""Shared finite Provider stage: Baseline and independent probes use one retry loop."""
import time
import math
import hashlib
import json
import uuid
from contextvars import ContextVar
from copy import deepcopy
from .telemetry import collect_usage
from .paid_run import unsettled_usage

_request_checkpoint = ContextVar('evaluation_request_checkpoint', default=None)


def checkpoint_request(provider, model, endpoint, payload, action, *, reuse=True):
    """Persist a serial RPC inside its owning question/phase, never across Candidates."""
    context = _request_checkpoint.get()
    if context is None:
        return action()
    checkpoint, phase, run_id, on_state, check_stop = context
    check_stop()
    key = hashlib.sha256(json.dumps([phase, provider, model, endpoint, payload], sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    saved = checkpoint.setdefault('provider_requests', {}).setdefault(key, {'phase':phase, 'provider':provider, 'model':model, 'attempts':[]})
    if saved.get('status') in {'inflight', 'unknown'} or any(unsettled_usage(u) for a in saved['attempts'] for u in a.get('usage', [])):
        failure = RuntimeError('RPC执行或Usage未知，须先对账，禁止重复发送')
        failure.request_execution_unknown = True
        raise failure
    if reuse and saved.get('status') == 'completed':
        return deepcopy(saved['result'])
    attempt = {'id':uuid.uuid4().hex, 'recorded_by_run_id':run_id, 'status':'inflight', 'usage':[]}
    saved['attempts'].append(attempt);saved['status'] = 'inflight'
    on_state('running', phase=phase)
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
        on_state('running', phase=phase)
        raise
    saved.update(status='completed', result=deepcopy(value))
    attempt['status'] = 'completed'
    on_state('running', phase=phase)
    return value


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


def perform_stage(checkpoint,phase,action,run_id,*,automatic,check_stop,on_state):
    from .providers import ProviderAPIError,ProviderInvalidResponse,ProviderTimeout,ProviderUnavailable,retryable_error,provider_error_details,stage_deadline
    # Explicit Resume starts a new retry window; process recovery of this Run keeps its failures.
    prior=[a for a in checkpoint['attempts'] if a.get('phase')==phase and a.get('recorded_by_run_id')==run_id]
    failures=0;invalid_failures=0
    for a in reversed(prior):
        if a.get('status')=='ok':break
        failures+=1;invalid_failures+=a.get('error_type')=='ProviderInvalidResponse'
    windows=checkpoint.setdefault('phase_windows',{})
    window=windows.get(phase)
    if not window or window.get('run_id')!=run_id:
        window={'run_id':run_id,'started_at':time.time()};windows[phase]=window
    deadline=time.monotonic()+max(0,600-(time.time()-window['started_at']))
    if checkpoint.get('inflight')==phase:checkpoint.setdefault('unknown_execution',{})[phase]=True
    if checkpoint.get('unknown_execution',{}).get(phase):
        raise RuntimeError('Unknown request execution after worker loss; explicit request/usage reconciliation required')
    while True:
        check_stop()
        if failures>=3 or invalid_failures>=2 or time.monotonic()>=deadline:
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
            if any(unsettled_usage(u) for u in usage):
                checkpoint['execution' if phase=='generation' else 'scored_result']=value
                failure=ProviderUnavailable('有效结果已保存，但Usage/费用未知，须先对账；不得重复生成')
                failure.request_execution_unknown=False;failure.billing_unknown=True
                raise failure
            if time.monotonic()>deadline:
                checkpoint['execution' if phase=='generation' else 'scored_result']=value
                raise ProviderTimeout('Known complete Provider response exceeded 600 seconds')
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
            retry=retryable_error(error) and not unknown and not billing_unknown and failures<3 and time.monotonic()<deadline
            # Repeated structurally invalid Judge replies are a terminal contract failure.
            if isinstance(error,ProviderInvalidResponse):
                invalid_failures+=1
                if invalid_failures>=2:retry=False
            attempt['request_execution_unknown']=unknown
            if unknown:checkpoint.setdefault('unknown_execution',{})[phase]=True
            attempt['retryable']=retry;checkpoint['attempts'].append(attempt);checkpoint.pop('inflight',None)
            if automatic and retry:
                delay=min(60,2**min(failures-1,6))
                retry_error=error
                while retry_error.__cause__ is not None and not isinstance(retry_error,ProviderAPIError):retry_error=retry_error.__cause__
                if isinstance(retry_error,ProviderAPIError):
                    try:delay=max(delay,float(retry_error.retry_after or 0))
                    except (TypeError,ValueError):
                        try:
                            from email.utils import parsedate_to_datetime
                            delay=max(delay,parsedate_to_datetime(retry_error.retry_after).timestamp()-time.time())
                        except (TypeError,ValueError,OverflowError):pass
                if not isinstance(delay,(int,float)) or not math.isfinite(delay):delay=60
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
    previous=next((a for a in reversed(checkpoint['attempts']) if a.get('phase')=='judge' and a.get('recorded_by_run_id')==run_id and a.get('error_type')=='ProviderInvalidResponse'),None)
    return {'error':previous['error'],'previous_response':previous.get('raw_provider_response')} if previous else None
