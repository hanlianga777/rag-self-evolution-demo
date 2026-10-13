"""Explicit 2026-10-13 owner run: resume, first ABC, no Gate2 or publication."""
import hashlib
import json
import sys
import time
import urllib.request
from dataclasses import replace
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from run_golden_owner_night import identity
from app.paid_run import PaidRun, controlled_run, current_paid_run
from app.providers import DeepSeekProvider, ProviderTimeout, ProviderNetworkError

OUT=ROOT/'output/playwright/baseline-continuous-20261013'
LEDGER=ROOT/'output/playwright/golden-delegated-20261012/paid-calls.json'
SOURCE='EVAL-20261013005603096653'
FROZEN='8cdc2a32aea37a069dd75557c34688a0cae64fa0a52c0361c8020377a8c19106'


def retry_allowed(used, error):
    return used==0 and isinstance(error,(ProviderTimeout,ProviderNetworkError))


def execute():
    # A persisted start marker prevents accidental reruns of this one-off authorization.
    marker=OUT/('started-'+SOURCE+'.json')
    with marker.open('x') as stream:json.dump({'source':SOURCE,'identity':FROZEN},stream)
    from app import main
    from fastapi.testclient import TestClient
    assert main.ai_service.live_enabled
    source=main.store.evaluation_run(SOURCE)
    assert source['judge']['evaluation_identity']==FROZEN
    source_cases=main.store.evaluation_case_results(SOURCE)
    assert len(source_cases)>=26
    client=TestClient(main.app)
    active_id=None
    stage='baseline-continuous-'+SOURCE[-8:]
    retries={}
    # Q27 was already in flight when the old process stopped: this run is its one recovery.
    retries[(stage,'V1G-120721324996-27','judge')]=1
    replay_path=OUT/'q38-saved-format-recovery.json'
    replay=(json.loads(replay_path.read_text()) if replay_path.exists()
            and source['result']['checkpoints'].get('V1G-120721324996-38',{}).get('execution') else None)
    replay_used=False
    ledger_before=json.loads(LEDGER.read_text())
    for audit_path in OUT.glob('*-network-recovery-*.json'):
        audit=json.loads(audit_path.read_text())
        if 'request_sha256' not in audit:continue
        checkpoint=source['result']['checkpoints'].get(audit['question_id'],{})
        failures=[c for c in ledger_before['calls'] if c['request_sha256']==audit['request_sha256'] and c['status']=='reserved']
        if checkpoint.get('execution') and len(failures)>=2:
            raise RuntimeError('Same question failed twice; recovery authorization exhausted: '+audit['question_id'])

    def save(name,value):
        path=OUT/(name+'.json');temporary=path.with_suffix('.tmp')
        temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2));temporary.replace(path)

    def claim(name,reason=None):
        data=json.loads(LEDGER.read_text())
        settings=main.ai_service.provider.settings
        request=urllib.request.Request(settings.base_url+'/user/balance',headers={'Authorization':'Bearer '+settings.api_key})
        with urllib.request.urlopen(request,timeout=30) as response:balance=json.load(response)
        cash=sum(float(b['total_balance']) for b in balance['balance_infos'] if b['currency']=='CNY')
        assert balance['is_available'] and cash>3
        save(name+'-balance',balance)
        # External Q22 timeout and Q27 in-flight Usage are absent from the original ledger.
        # Hold 0.50 CNY each; never invent ledger requests or release unknown charges.
        budget=min(data['budget_yuan'],data['spent_yuan']+cash-3-1.)
        authorization={'source':'direct_user_instruction','scope':'finite_checkpoint_resume',
            'max_missing_request_retries':1,'source_evaluation_id':active_id or SOURCE,
            'evaluation_identity':FROZEN,'held_request_sha256':[c['request_sha256'] for c in data['calls'] if c['status']=='reserved'],
            'reason':reason or 'Explicit continuous recovery authorization','external_unknown_reserve_yuan':1.}
        return PaidRun.next_stage(LEDGER,name,identity,authorization=authorization,budget_yuan=budget)

    class FiniteProvider(DeepSeekProvider):
        def complete_with_metrics(self,*args,**kwargs):
            nonlocal replay_used
            if replay and not replay_used:
                mode=kwargs.get('json_mode',args[2] if len(args)>2 else False)
                payload=json.loads(self._request(args[0],args[1],mode,kwargs.get('stream',False),kwargs.get('temperature',.2)).data)
                user=json.loads(payload['messages'][1]['content']) if mode else None
                if isinstance(user,dict) and user.get('question')==replay['question']:
                    assert user['actual_answer']==replay['answer']
                    assert user['final_context']==replay['final_context']
                    replay_used=True
                    from app.telemetry import record_usage
                    record_usage(replay['usage'])
                    save('q38-replay-consumed',{'run_id':active_id,'original_request_sha256':replay['request_sha256'],
                        'current_request_sha256':hashlib.sha256(json.dumps(payload,ensure_ascii=False).encode()).hexdigest(),
                        'new_provider_calls':0,'original_response_path':replay['original_response_path']})
                    return {'content':replay['normalized_content'],'usage':replay['usage']}
            try:return super().complete_with_metrics(*args,**kwargs)
            except (ProviderTimeout,ProviderNetworkError) as error:
                run=current_paid_run()
                checkpoint=main.store.evaluation_run(active_id)['result']['checkpoints'] if active_id else {}
                question=next((q for q,c in checkpoint.items() if c.get('inflight')),None)
                task=run.calls[-1].get('task')
                key=(stage,question,task)
                if not retry_allowed(retries.get(key,0),error):raise
                retries[key]=1
                old=run.calls[-1]
                name=stage+'-network-recovery-'+str(len(run.calls))
                save(name,{'evaluation_run_id':active_id,'question_id':question,'task':task,
                    'request_sha256':old['request_sha256'],'error_type':type(error).__name__,
                    'cause_type':type(error.__cause__).__name__,'retry_limit':1,'original_usage':'Unknown'})
                resumed=claim(name,str(error))
                # Serial worker keeps the same context object, including already-successful retrieval.
                run.__dict__.update(resumed.__dict__)
                return super().complete_with_metrics(*args,**kwargs)

    main.ai_service.provider=FiniteProvider(replace(main.ai_service.provider.settings,timeout_seconds=600))

    def post(path,payload=None):
        response=client.post(path,json=payload,headers={'Origin':'http://127.0.0.1:5174'})
        save(stage+'-api',{'status':response.status_code,'body':response.json()})
        if response.status_code>=400:raise RuntimeError(response.text)
        return response.json()

    def wait(key):
        deadline=time.monotonic()+10800
        while time.monotonic()<deadline:
            value=main.store.evaluation_run(key)
            save(stage+'-progress',value)
            if value['status'] in {'completed','partial','failed'}:
                if value['status']!='completed':raise RuntimeError(value.get('error_message') or 'Evaluation incomplete')
                assert value['judge']['evaluation_identity']==FROZEN and value['result']['completed']==50
                return value
            time.sleep(5)
        raise RuntimeError('Bounded evaluation wait exceeded')

    with controlled_run(claim(stage)):
        value=post('/api/evaluations/run',{'resume_source_id':SOURCE});active_id=value['id']
        save('resume-start',value);print('BASELINE_STARTED',active_id,flush=True)
        baseline=wait(active_id)
        old={c['question_id']:c for c in main.store.evaluation_case_results(SOURCE)}
        cases={c['question_id']:c for c in main.store.evaluation_case_results(active_id)}
        assert all(cases[q]==c for q,c in old.items())
        assert sum(a['phase']=='generation' and a['status']=='ok' for a in baseline['result']['checkpoints']['V1G-120721324996-27']['attempts'])==1
        save('reuse-proof',{'completed_cases_reused':len(source_cases),'q27_answer_reused':True,'identity':FROZEN})
    print('BASELINE_COMPLETE',active_id,flush=True)
    stage='agent-continuous-1'
    with controlled_run(claim(stage)):
        experiment=post('/api/experiments/run');save('experiment',experiment)
    candidates=[c for c in experiment['candidates'] if c['reasoning'].get('round')==1]
    assert len(candidates)==3
    for label in ('A','B','C'):
        candidate=next(c for c in candidates if c['reasoning']['candidate_label']==label)
        stage='candidate-continuous-'+label+'1'
        with controlled_run(claim(stage)):
            value=post('/api/candidates/'+candidate['id']+'/run');active_id=value['id']
            print('CANDIDATE_STARTED',label,active_id,flush=True);wait(active_id)
            # Evaluation completion precedes Candidate/Recommendation persistence by a few ms.
            for _ in range(20):
                if main.store.candidate(candidate['id'])['status']!='running':break
                time.sleep(.25)
            save('candidate-'+label,main.store.candidate(candidate['id']))
    save('experiment-final',main.store.experiment(experiment['id']))
    save('recommendation-final',main.store.recommendation(experiment['id']))
    print('FIRST_ABC_FINISHED',flush=True)


if __name__=='__main__':
    if len(sys.argv)>1:SOURCE=sys.argv[1]
    try:execute()
    except Exception as error:
        (OUT/'stopped.json').write_text(json.dumps({'type':type(error).__name__,'error':str(error)},ensure_ascii=False))
        raise
