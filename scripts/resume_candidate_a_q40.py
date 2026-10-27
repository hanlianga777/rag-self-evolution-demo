"""Explicit Q40-only punctuation replay, then the existing Candidate Resume."""
import argparse,hashlib,json,sqlite3,sys,urllib.request
from dataclasses import replace
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
SOURCE='EVAL-20261013074657234750'
CID='EXP-20261013065746494438-R1-A'
QID='V1G-120721324996-40'


def close_outer_object(raw):
    stack=[];quoted=escaped=False
    for char in raw:
        if quoted:
            if escaped:escaped=False
            elif char=='\\':escaped=True
            elif char=='"':quoted=False
        elif char=='"':quoted=True
        elif char in '{[':stack.append(char)
        elif char in '}]':
            if not stack or stack.pop()!=('{' if char=='}' else '['):raise ValueError('Not one missing outer brace')
    if quoted or stack!=['{']:raise ValueError('Not one missing outer brace')
    try:json.loads(raw)
    except json.JSONDecodeError as error:
        if error.pos!=len(raw):raise ValueError('JSON error is not at EOF') from error
    else:raise ValueError('Original JSON already complete')
    fixed=raw+'}';value=json.loads(fixed)
    if not isinstance(value,dict):raise ValueError('Outer value is not an object')
    return fixed


def execute(ledger,audit,run=False):
    audit.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect((ROOT/'backend/data/demo.db').as_uri()+'?mode=ro',uri=True) as db:
        for table in ('evaluation_runs','candidate_configs','golden_generation_runs','candidate_revision_runs','experiments'):
            if db.execute('SELECT id FROM '+table+" WHERE status IN ('running','queued','generating')").fetchone():
                raise RuntimeError('Active worker; do not initialize another executor')
        if run:
            with sqlite3.connect(audit/'before-resume.db') as backup:db.backup(backup)
    from app import main
    from app.evaluation import EvaluationRunner
    from app.evaluation_contract import quote_present,observe_evidence
    from app.paid_run import PaidRun,controlled_run
    from app.providers import DeepSeekProvider
    from app.telemetry import record_usage
    from app.corpus import current_manifest,manifest_identity
    source=main.store.evaluation_run(SOURCE);runner=EvaluationRunner(main.store,main.ai_service)
    approved,config,candidate,baseline=runner.candidate_inputs(CID)
    assert source['status']=='partial' and source['result']['completed']==39
    assert candidate['result']['evaluation_run_id']==SOURCE and config['prompt_strategy']=='Grounded'
    assert source['judge']==baseline['judge'] and len(approved)==50 and main.ai_service.live_enabled
    checkpoint=source['result']['checkpoints'][QID];attempt=checkpoint['attempts'][-1]
    data=json.loads(ledger.read_text());call=data['calls'][-1]
    response_file=Path(call['raw_response_path']);response_bytes=response_file.read_bytes();body=json.loads(response_bytes)
    raw=attempt['raw_provider_response'];assert raw==body['choices'][0]['message']['content']
    assert body['choices'][0]['finish_reason']=='stop' and call['status']=='ok' and call['task']=='judge'
    assert call['usage']==attempt['usage'][0]
    fixed=close_outer_object(raw);parsed=json.loads(fixed)
    assert {'correctness','faithfulness','completeness','behavior_pass','reason','missing_points','unsupported_claims','claim_reviews','evidence_sufficiency'}<=set(parsed)
    fixed_path=audit/'q40-normalized.json'
    if fixed_path.exists():assert fixed_path.read_text()==fixed
    else:fixed_path.write_text(fixed)
    proof={'source_run_id':SOURCE,'question_id':QID,'source_response_file':str(response_file),
           'source_response_file_sha256':hashlib.sha256(response_bytes).hexdigest(),
           'original_content_sha256':hashlib.sha256(raw.encode()).hexdigest(),
           'normalized_content_sha256':hashlib.sha256(fixed.encode()).hexdigest(),
           'original_length':len(raw),'normalized_length':len(fixed),'only_change':'append one final outer }',
           'request_sha256':call['request_sha256'],'usage':call['usage'],'finish_reason':'stop',
           'new_q40_provider_calls':0,'authorization':'direct_user_instruction: Q40-only local replay and Candidate A Resume'}
    item=next(i for i in approved if i['id']==QID)
    final=checkpoint['execution']['retrieval_trace']['final'];observation=observe_evidence(item,final)
    expected_input={'question':item['question'],'reference_answer':item['reference_answer'] or item['raw'].get('expected_behavior','拒答或澄清'),
        'actual_answer':checkpoint['execution']['answer'],'golden_evidence':item['evidence'],'final_context':final,
        'category':item['test_category'],'negative_subtype':item.get('negative_subtype'),'expected_behavior':item['raw'].get('expected_behavior'),
        'source_constraints':observation['source_constraints'],'programmatic_evidence_observation':observation}
    settings=replace(main.ai_service.provider.settings,timeout_seconds=600)
    class ReplayProvider(DeepSeekProvider):
        used=False
        validation=False
        def complete_with_metrics(self,system,user,json_mode=False,**kwargs):
            payload=json.loads(self._request(system,user,json_mode,kwargs.get('stream',False),kwargs.get('temperature',.2)).data)
            sha=hashlib.sha256(json.dumps(payload,ensure_ascii=False).encode()).hexdigest()
            user_input=json.loads(user) if json_mode else None
            if isinstance(user_input,dict) and user_input.get('question')==item['question']:
                assert user_input==expected_input and payload['max_tokens']==source['judge']['execution_snapshot']['request_limits']['judge']
                assert payload['temperature']==0 and payload['model']==source['judge']['model']
                proof['rebuilt_request_sha256']=sha
                proof['replay_input_verification']='all Judge input fields equal frozen Snapshot and saved checkpoint; JSON key order may differ'
                if self.used:raise RuntimeError('Q40 replay already consumed')
                self.used=True;record_usage(call['usage'])
                return {'content':fixed,'usage':call['usage']}
            if self.validation:raise RuntimeError('Provider calls forbidden during local validation')
            return super().complete_with_metrics(system,user,json_mode,**kwargs)
    provider=ReplayProvider(settings);provider.validation=True
    main.ai_service.provider=provider
    from app.paid_run import execution_limits
    with execution_limits(baseline['judge']['execution_snapshot']['request_limits']):
        checked=runner.score_execution(next(i for i in approved if i['id']==QID),checkpoint['execution'])
    assert provider.used
    final=checkpoint['execution']['retrieval_trace']['final']
    assert all(quote_present(s,final) for review in parsed['claim_reviews'] for s in review['support'])
    assert all(quote_present(s,final) for s in parsed['evidence_sufficiency']['fact_support'])
    proof['q40_case_passed']=checked['passed']
    proof['q40_failure_tags']=checked['failure_tags']
    proof['pending_claims_preserved']=checked['programmatic_metrics']['claim_assessment']['pending']
    assert all(checked['judge_result'][k]==parsed[k] for k in ('correctness','faithfulness','completeness','behavior_pass','reason','missing_points','unsupported_claims'))
    assert response_file.read_bytes()==response_bytes and json.loads(ledger.read_text())==data
    proof['strict_parser_and_source_validation']='passed';proof['validated_case']=checked
    (audit/'q40-replay-validation.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2))
    print('Q40_STRICT_VALIDATION_PASSED; NEW_PROVIDER_CALLS=0',flush=True)
    if not run:return
    identity=lambda:{'candidate_id':CID,'baseline_id':main.store.experiment(main.store.candidate(CID)['experiment_id'])['baseline_run_id'],
        'judge':main.store.require_current_baseline(baseline['id'])['judge'],'config':main.store.candidate(CID)['config'],
        'snapshot':main.store.evaluation_run(baseline['id'])['dataset_snapshot_json'],'corpus':manifest_identity(current_manifest())}
    paid=PaidRun.next_stage(ledger,'candidate-A-Q40-local-format-resume',identity)
    provider.used=False;provider.validation=False
    old_cases=main.store.evaluation_case_results(SOURCE)
    with controlled_run(paid):
        started=runner.start_candidate(CID)
        assert main.store.evaluation_case_results(started[0])==old_cases
        (audit/'resume-start.json').write_text(json.dumps({'run_id':started[0],'source_run_id':SOURCE,'reused_cases':len(old_cases),'q40_answer_reused':True}))
        print('REAL_A_RESUME_STARTED',started[0],flush=True)
        result=runner.execute_candidate(*started)
    saved=main.store.evaluation_run(started[0])
    (audit/'candidate-final.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    (audit/'evaluation-final.json').write_text(json.dumps(saved,ensure_ascii=False,indent=2))
    assert main.store.evaluation_run(SOURCE)==source and main.store.evaluation_case_results(SOURCE)==old_cases
    assert response_file.read_bytes()==response_bytes
    assert json.loads(ledger.read_text())['calls'][:len(data['calls'])]==data['calls']
    assert provider.used
    q40=next(c for c in main.store.evaluation_case_results(started[0]) if c['question_id']==QID)
    assert all(q40['judge_result'][k]==checked['judge_result'][k] for k in ('correctness','faithfulness','completeness','behavior_pass','reason','claim_reviews','evidence_sufficiency'))
    proof.update(resume_run_id=started[0],original_cases_reused=39,q40_replay_consumed=True,
        new_q40_provider_calls=0,final_status=saved['status'],completed=saved['result']['completed'])
    (audit/'q40-replay-validation.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2))
    print('REAL_A_FINISHED',saved['status'],saved['result']['completed'],flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--ledger',type=Path,required=True);parser.add_argument('--audit-dir',type=Path,required=True);parser.add_argument('--execute',action='store_true')
    args=parser.parse_args();execute(args.ledger,args.audit_dir,args.execute)
