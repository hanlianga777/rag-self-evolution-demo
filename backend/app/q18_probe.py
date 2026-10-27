"""Q18-only authorization; independent artifacts, never formal evaluation writes."""
import json
import hashlib
import sqlite3
import os
from datetime import datetime,timezone
from pathlib import Path
from .diagnostic_evidence import digest
from .config import load_settings

QUESTION_ID='V1G-110926448917-18'


def save_json(path,value):
    path=Path(path);temporary=path.with_suffix('.tmp')
    with temporary.open('w') as stream:
        json.dump(value,stream,ensure_ascii=False,indent=2);stream.flush();os.fsync(stream.fileno())
    os.replace(temporary,path)


def probe_directory(database):return Path(os.getenv('RAG_JUDGE_PROBE_DIR') or Path(database).parent/'judge_probes')


def probe_binding(plan):
    settings=load_settings()
    question=next((r for r in plan['eligibility'] if r['question_id']==QUESTION_ID),None)
    return digest({'source':plan['source_run_id'],'source_sha256':plan['source_sha256'],
        'identity':plan['new_evaluation_identity'],'judge':plan['new_judge'],'q18':question,
        'endpoint':settings.base_url,'timeout_seconds':settings.timeout_seconds})


def probe_preflight(runner,source_id):
    from .providers import DeepSeekProvider
    from .config import Settings
    from .evaluation_contract import BUSINESS_JUDGE_PROMPT,business_judge_input
    from .paid_run import execution_limits,provider_task
    plan=runner.judge_replay_preflight(source_id,include_executions=True)
    if not plan['can_replay'] or QUESTION_ID not in plan['executions']:raise ValueError('Q18 probe requires complete Replay eligibility')
    _,items,_,judge=runner.baseline_inputs(source_id)
    item=next(i for i in items if i['id']==QUESTION_ID);execution=plan['executions'][QUESTION_ID]
    context=runner.judge_context(item,execution);settings=load_settings()
    if settings.model!=judge['model'] or settings.base_url!='https://api.deepseek.com':raise ValueError('Q18 official model/endpoint mismatch')
    actual_provider=getattr(runner.runtime,'provider',None)
    if actual_provider is not None and (not isinstance(actual_provider,DeepSeekProvider) or actual_provider.settings!=settings):raise ValueError('Q18 loaded Provider configuration differs from current preflight')
    limits=judge['execution_snapshot']['request_limits']
    provider=DeepSeekProvider(Settings('offline-placeholder',settings.base_url,settings.model,settings.timeout_seconds))
    with execution_limits(limits),provider_task('judge'):
        summary=provider.request_summary(BUSINESS_JUDGE_PROMPT,business_judge_input(item['question'],item['reference_answer'] or item['raw'].get('expected_behavior','拒答或澄清'),execution['answer'],context),json_mode=True,temperature=0)
    return {'binding':probe_binding(plan),'source_run_id':source_id,'new_evaluation_identity':plan['new_evaluation_identity'],
        'reusable':plan['reusable'],'total':plan['total'],'generation_calls':0,'max_judge_calls':3,'max_contract_corrections':1,
        'stage_deadline_seconds':600,'request':summary,'limits':limits,'plan':plan,'item':item,'execution':execution,'context':context}


def validate_artifact(record,plan,database):
    from .evaluation_contract import validate_business_judgment
    if record.get('binding')!=probe_binding(plan) or record.get('mode')!='real' or record.get('status') not in {'judge_complete','reviewed'}:raise ValueError('Q18 probe identity/state is not eligible')
    expected=next(r['execution_sha256'] for r in plan['eligibility'] if r['question_id']==QUESTION_ID)
    if digest(record['execution'])!=expected:raise ValueError('Q18 execution hash changed')
    execution=record['execution'];item=record['item'];case=record['case'];judge=case['judge_result']
    with sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro',uri=True) as connection:
        row=connection.execute('SELECT dataset_snapshot_json FROM evaluation_runs WHERE id=?',(plan['source_run_id'],)).fetchone()
    frozen=next(q for q in json.loads(row[0])['questions'] if q['id']==QUESTION_ID)
    expected_item={'id':QUESTION_ID,'question':frozen['question'],'reference_answer':frozen.get('reference_answer'),
        'test_category':frozen['test_category'],'negative_subtype':frozen.get('negative_subtype'),'evidence':frozen.get('evidence',frozen.get('acceptable_evidence',[])),'raw':frozen}
    if any(item.get(k)!=v for k,v in expected_item.items()) or item.get('baseline_findings') is not None:raise ValueError('Q18 frozen question/reference changed')
    # Reconstruct the exact official context from current Canonical data, never trust saved scope metadata alone.
    from .evaluation import EvaluationRunner
    context=EvaluationRunner.judge_context(None,item,execution)
    if digest(context)!=record['context_sha256']:raise ValueError('Q18 Canonical input changed')
    raw=judge['raw_provider_response'].strip().removeprefix('\ufeff')
    if raw.startswith('```json\n') and raw.endswith('\n```'):raw=raw[8:-4]
    parsed=json.loads(raw)
    if any(parsed.get(k)!=judge.get(k) for k in ('verdict','checks','issues','reason','quality')):raise ValueError('Q18 raw judgment mismatch')
    validate_business_judgment(parsed,execution['answer'],context['final_context'],category=item['test_category'],
        constraints=context['source_constraints'],question=item['question'],reference=item['reference_answer'],
        candidates=context['retrieval_candidates'],canonical_chunks=context['_canonical_chunks'])
    ledger=json.loads(Path(record['ledger_path']).read_text())
    calls=ledger['calls']
    if ledger['identity']!=record['binding'] or ledger.get('stopped') or not 1<=len(calls)<=3:raise ValueError('Q18 payment identity/state invalid')
    if ledger.get('output_limits')!=plan['new_judge']['execution_snapshot']['request_limits']:raise ValueError('Q18 frozen request limits changed')
    if any(c.get('max_tokens')!=ledger['output_limits']['judge'] or c.get('status')!='ok' or c.get('task')!='judge' or c.get('provider')!='DeepSeek' or c.get('model')!=plan['new_judge']['model'] for c in calls):raise ValueError('Q18 unknown/non-Judge request')
    for call in calls:
        usage=call.get('usage',{})
        if usage.get('status')!='ok' or any(type(usage.get(k)) is not int or usage[k]<0 for k in ('prompt_tokens','completion_tokens')):raise ValueError('Q18 known Usage required')
    response=json.loads(Path(calls[-1]['raw_response_path']).read_text())
    if response['choices'][0]['message']['content']!=judge['raw_provider_response']:raise ValueError('Q18 original response mismatch')
    # Payment request digests also bind the original input and each finite correction.
    from .providers import DeepSeekProvider
    from .config import Settings
    from .evaluation_contract import BUSINESS_JUDGE_PROMPT,business_judge_input
    from .paid_run import execution_limits,provider_task
    from .evaluation_stage import correction_for
    settings=load_settings();provider=DeepSeekProvider(Settings('offline-placeholder',settings.base_url,settings.model,settings.timeout_seconds))
    attempts=record['checkpoint']['attempts']
    if len(attempts)!=len(calls):raise ValueError('Q18 attempt/payment records differ')
    for index,call in enumerate(calls):
        correction=correction_for({'attempts':attempts[:index]},attempts[index]['recorded_by_run_id'])
        request_context={**({'judge_correction':correction} if correction else {}),**context}
        with execution_limits(ledger['output_limits']),provider_task('judge'):
            request=provider._request(BUSINESS_JUDGE_PROMPT,business_judge_input(item['question'],item['reference_answer'],execution['answer'],request_context),True,False,0)
        request_sha=hashlib.sha256(json.dumps(json.loads(request.data),ensure_ascii=False).encode()).hexdigest()
        if call['request_sha256']!=request_sha:raise ValueError('Q18 actual Judge request input/configuration changed')
    return digest({'case':case,'attempts':attempts,'binding':record['binding'],'item':item,'context':record['context_sha256'],'ledger':ledger,'response':response})


def require_reviewed_probe(database,plan):
    binding=probe_binding(plan)
    for path in sorted(probe_directory(database).glob('*.probe.json')):
        try:
            record=json.loads(path.read_text());result_hash=validate_artifact(record,plan,database)
            review=record.get('review',{})
            if (record['status']=='reviewed' and review.get('decision')=='approved' and review.get('result_sha256')==result_hash
                and review.get('binding')==binding and review.get('actor') and all(isinstance(review.get(k),str) and review[k].strip() for k in ('facts','safety','scope_separation'))):return str(path)
        except (OSError,ValueError,KeyError,TypeError,IndexError,StopIteration,sqlite3.Error):continue
    raise ValueError('Q18 independent real probe and explicit business review required for this Evaluation Identity')


def run_probe(runner,source_id,*,expected_binding,authorize_provider,authorization_id,price_snapshot=None,budget_usd=None):
    from .paid_run import PaidRun,controlled_run,execution_limits
    from .evaluation_stage import perform_stage,correction_for
    from .full_text import CORPUS_LOCK
    with CORPUS_LOCK:
        preflight=probe_preflight(runner,source_id)
        if not authorize_provider or not authorization_id or preflight['binding']!=expected_binding:raise ValueError('Explicit Q18-only authorization with current binding required')
        if not getattr(runner.runtime,'live_enabled',False):raise ValueError('Q18 real probe requires configured real Provider')
        model=preflight['plan']['new_judge']['model']
        price=json.loads(Path(price_snapshot).read_text()) if price_snapshot else None
        if price:
            try:
                age=(datetime.now(timezone.utc)-datetime.fromisoformat(price['checked_at'])).total_seconds()
                if (not 0<=age<=86400 or price.get('currency')!='USD' or price.get('model')!=model
                    or price.get('source_url')!='https://api-docs.deepseek.com/quick_start/pricing/'):
                    price=None
            except (KeyError,TypeError,ValueError):
                price=None
        directory=probe_directory(runner.store.database_path);directory.mkdir(parents=True,exist_ok=True)
        path=directory/(digest(authorization_id)+'.probe.json')
        descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.close(descriptor)
        record={'binding':expected_binding,'mode':'real','status':'running','source_run_id':source_id,'question_id':QUESTION_ID,'authorization_id':authorization_id,
            'item':preflight['item'],'execution':preflight['execution'],'context_sha256':digest(preflight['context']),
            'checkpoint':{'attempts':[]},'budget_currency':'USD','price_snapshot':price,'ledger_path':str(path.with_suffix('.ledger.json'))}
        save_json(path,record)
        def current_binding():
            if len(record['checkpoint']['attempts'])>=3:raise ValueError('Q18 authorization exhausted')
            return probe_preflight(runner,source_id)['binding']
        prices={model:{'provider':'DeepSeek','input':price['input_per_million'],'output':price['output_per_million'],'max_output':preflight['limits']['judge'],'currency':'USD'}} if price else {}
        ledger=PaidRun(record['ledger_path'],budget_usd,prices,expected_binding,identity_check=current_binding,output_limits=preflight['limits'])
        def persist(state,**details):
            if state=='retrying' and ledger.stopped:
                last=record['checkpoint']['attempts'][-1]
                if (last['retryable'] and not last['request_execution_unknown'] and ledger.calls
                    and all(c['status']=='ok' for c in ledger.calls) and ledger.stopped==last['error_type']):
                    record.setdefault('known_response_retries',[]).append({'completed_calls':len(ledger.calls),'error_type':ledger.stopped})
                    ledger.stopped=None;ledger.save()
            record.update(stage_state=state,stage_details=details);save_json(path,record)
        def check_stop():
            if ledger.stopped or any(c['status']!='ok' for c in ledger.calls):raise RuntimeError('Q18 stopped or unknown request; no automatic retry')
            if current_binding()!=expected_binding:raise ValueError('Q18 preflight binding changed')
        try:
            with controlled_run(ledger),execution_limits(preflight['limits']):
                case=perform_stage(record['checkpoint'],'judge',lambda:runner.score_execution(preflight['item'],preflight['execution'],judge_correction=correction_for(record['checkpoint'],path.stem)),path.stem,automatic=True,check_stop=check_stop,on_state=persist)
            record.update(case=case,status='judge_complete')
            validate_artifact(record,preflight['plan'],runner.store.database_path)
        except Exception as error:
            if any(c['status']=='reserved' for c in ledger.calls):record['checkpoint'].setdefault('unknown_execution',{})['judge']=True
            record.update(status='technical_error',error_type=type(error).__name__,error=str(error));save_json(path,record);raise
        save_json(path,record)
        return {'path':str(path),'status':record['status'],'business_verdict':case['judge_result']['verdict'],'business_review_required':True}


def review_probe(runner,source_id,path,*,actor,decision,facts,safety,scope_separation):
    """Explicit human review, never auto-approve from Parser or business PASS."""
    preflight=probe_preflight(runner,source_id);path=Path(path).resolve()
    if path.parent!=probe_directory(runner.store.database_path).resolve():raise ValueError('Q18 review artifact outside probe directory')
    record=json.loads(path.read_text());result_hash=validate_artifact(record,preflight['plan'],runner.store.database_path)
    if decision not in {'approved','rejected'} or not all(isinstance(s,str) and s.strip() for s in (actor,facts,safety,scope_separation)):raise ValueError('Explicit facts/safety/scope business review required')
    record.update(status='reviewed',review={'binding':preflight['binding'],'result_sha256':result_hash,'actor':actor,'decision':decision,
        'facts':facts,'safety':safety,'scope_separation':scope_separation,'reviewed_at':datetime.now(timezone.utc).isoformat()})
    save_json(path,record);return {'path':str(path),'decision':decision}
