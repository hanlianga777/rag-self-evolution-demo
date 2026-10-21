"""Read-only replay of saved Medium50 diagnostics; never a new evaluation.

Only the acceptance expectations below use question numbers. Production diagnosis
reads immutable source reviews and derives roots without identifiers or roots in
those review records. Provider entry points are prohibited during verification.
"""
import argparse,hashlib,json,os,pathlib,sqlite3,sys,tempfile
from contextlib import ExitStack
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))


def verify(database):
    database=pathlib.Path(database).resolve()
    with tempfile.TemporaryDirectory() as isolated,ExitStack() as stack:
        for key,value in {'RAG_DEMO_DB_PATH':str(database),'RAG_DEMO_ENV_PATH':str(pathlib.Path(isolated)/'missing.env'),
            'RAG_DEMO_INDEX_DIR':str(ROOT/'backend/data/index'),'RAG_DEMO_DOCUMENTS_DIR':str(ROOT/'backend/documents'),
            'RAG_DEMO_UPLOADS_DIR':str(pathlib.Path(isolated)/'uploads')}.items():
            stack.enter_context(patch.dict(os.environ,{key:value}))
        from app.diagnostics import diagnostic_view
        from app.diagnostic_evidence import digest,case_digest
        from app.evaluation_contract import VERSIONS,BUSINESS_JUDGE_PROMPT,evaluation_identity,validate_business_judgment
        from app.ai_service import GENERATION_BOUNDARY
        from app.governance import GovernanceStore
        from app.optimization import validate_intervention
        from app.policy import GATE_DEFINITIONS,ALLOWED_SEARCH_SPACE
        for method in ['urllib.request.urlopen','app.providers.DeepSeekProvider.complete','app.knowledge_pipeline.AlibabaProvider._post']:
            stack.enter_context(patch(method,side_effect=AssertionError('offline diagnostics prohibit Provider/network')))
        c=sqlite3.connect(database.as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row
        stack.callback(c.close);c.execute('PRAGMA query_only=ON');c.execute('BEGIN')
        before=hashlib.sha256(database.read_bytes()).hexdigest()
        run=dict(c.execute('SELECT * FROM evaluation_runs WHERE id=?',('EVAL-20261021013401711966',)).fetchone())
        snapshot=json.loads(run['dataset_snapshot_json']);judge=json.loads(run['judge_json']);result=json.loads(run['result_json']);config=json.loads(run['config_json'])
        raw_cases=list(c.execute('SELECT question_id,result_json FROM evaluation_case_results WHERE run_id=?',(run['id'],)))
        saved_hash=digest([list(row) for row in raw_cases]);assert run['status']=='partial' and len(raw_cases)==49
        assert all(judge[k]==v for k,v in VERSIONS.items()) and evaluation_identity(snapshot,judge)==judge['evaluation_identity']
        assert hashlib.sha256(BUSINESS_JUDGE_PROMPT.encode()).hexdigest()==judge['judge_prompt_sha256']
        assert hashlib.sha256(GENERATION_BOUNDARY.encode()).hexdigest()==judge['generation_boundary_sha256']
        assert len(GATE_DEFINITIONS)==11 and ALLOWED_SEARCH_SPACE['top_k']==(4,6)
        expected={3:'Ranking',4:'Ranking',6:'Ranking',7:'Retrieval',8:'Ranking',17:'Retrieval',24:'Retrieval',27:'Ranking',28:'Retrieval',29:'Retrieval'}
        diagnoses={};passes=0
        for row in raw_cases:
            case=json.loads(row['result_json']);unchanged=case_digest(case)
            if case['passed']:passes+=1;continue
            number=int(row['question_id'].split('-')[2]);view=diagnostic_view(case)
            assert view['primary_root_cause']==expected[number],(number,view)
            assert case_digest(case)==unchanged and case['evaluation_outcome']['verdict']=='FAIL'
            assert any(f.get('provenance',{}).get('kind')=='independent_offline_review' for f in view['evidence_checks'])
            assert view['target_eligible']==(number!=27)
            diff=({'candidate_k':24} if expected[number]=='Retrieval' else (view.get('context_selection_options') or [{}])[0])
            proposal={'root_cause':expected[number],'intervention_direction':'candidate_recall' if expected[number]=='Retrieval' else 'context_selection',
                'config_diff':diff,'target_bad_cases':[row['question_id']],
                'evidence_assertions':[{'target_id':row['question_id'],'observation':'recall_missing' if expected[number]=='Retrieval' else 'ranking_omission'}],
                'parameter_dependencies':[{'parameters':list(diff),'reason':'同时保留入口与原有必要流程'}] if len(diff)>1 else [],
                'hypothesis':'依据保存规范与Trace验证必要事实覆盖','why':'候选及Final覆盖已核验','risk':'更多上下文可能带来噪声','expected_improvement':'必要规范进入上下文，仍待正式实验验证回答'}
            if number==27:
                assert view['context_selection_options']==[] and view['optimization_blockers']
                proposal['config_diff']={'top_k':6}
                try:validate_intervention(proposal,{row['question_id']:case},config)
                except ValueError:pass
                else:raise AssertionError('toolbox boundary bypassed')
            else:validate_intervention(proposal,{row['question_id']:case},config)
            diagnoses[f'Q{number:02}']={k:view.get(k) for k in ['primary_root_cause','target_eligible','optimization_directions','context_selection_options','optimization_blockers','diagnostic_gaps']}
        assert set(expected)=={int(q[1:]) for q in diagnoses} and passes==39
        q18=next(q for q in snapshot['questions'] if q['id'].split('-')[2]=='18');cp=result['checkpoints'][q18['id']]
        assert result['technical_error_count']==1 and q18['id'] not in {r['question_id'] for r in raw_cases}
        assert 'scored_result' not in cp and cp['execution']['answer']
        for attempt in cp['attempts']:
            if attempt['phase']!='judge':continue
            try:validate_business_judgment(json.loads(attempt['raw_provider_response']),cp['execution']['answer'],cp['execution']['retrieval_trace']['final'],category=q18['test_category'],question=q18['question'],reference=q18['reference_answer'],candidates=cp['execution']['retrieval_trace']['candidates'])
            except ValueError as error:assert str(error)=='support is not located in actual full Final'
            else:raise AssertionError('Q18 invalid raw PASS silently accepted')
        store=object.__new__(GovernanceStore)
        store.validate_evaluation_start(c,snapshot,judge);_,rows=store.validate_evaluation_resume(c,snapshot,config,judge,run['id']);assert len(rows)==49
        assert digest([list(row) for row in c.execute('SELECT question_id,result_json FROM evaluation_case_results WHERE run_id=?',(run['id'],))])==saved_hash
        assert c.total_changes==0 and hashlib.sha256(database.read_bytes()).hexdigest()==before
        return {'kind':'readonly_saved_diagnosis_NOT_Baseline_or_Agent_run','provider_calls':0,'run_id':run['id'],
            'identity':judge['evaluation_identity'],'database_sha256':before,'completed_unchanged':49,'business_pass_unchanged':passes,'business_fail_unchanged':10,
            'q18':'technical_error; same-identity explicit resume guards pass, not executed; repeated title-support failure remains possible',
            'gate_definitions_sha256':digest(GATE_DEFINITIONS),'search_space_sha256':digest(ALLOWED_SEARCH_SPACE),'diagnoses':diagnoses}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--database',default=str(ROOT/'backend/data/demo.db'));parser.add_argument('--output');args=parser.parse_args()
    result=verify(args.database);text=json.dumps(result,ensure_ascii=False,indent=2)
    if args.output:pathlib.Path(args.output).write_text(text+'\n')
    print(text)
