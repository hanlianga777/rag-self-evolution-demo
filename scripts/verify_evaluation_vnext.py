"""Read-only 200-case replay through explicit OFFLINE Judge test responses.

This validates identity, source location, parser, diagnosis and comparison mechanics.
It never evaluates LLM semantic accuracy and is never imported by production scoring.
"""
import argparse,hashlib,json,pathlib,sqlite3,sys,collections
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
def digest(value):
    return hashlib.sha256((value if isinstance(value,str) else json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))).encode()).hexdigest()
def verify(database):
    from app.evaluation_contract import compare_cases
    from app.evaluation import EvaluationRunner
    from app.providers import DeepSeekProvider
    from app.config import Settings
    from app.diagnostics import diagnostic_view
    fixture=json.loads((ROOT/'backend/tests/fixtures/rag_200_vnext_review.json').read_text())
    db=sqlite3.connect(pathlib.Path(database).resolve().as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row;db.execute('pragma query_only=on');db.execute('begin')
    raw={};snapshots={}
    for run_id in {r['run_id'] for r in fixture['records']}:
        run=db.execute('select dataset_snapshot_json from evaluation_runs where id=?',(run_id,)).fetchone()
        assert run,'missing frozen historical run'
        snapshots[run_id]={q['id']:q for q in json.loads(run[0])['questions']}
        raw[run_id]={r['question_id']:json.loads(r['result_json']) for r in db.execute('select question_id,result_json from evaluation_case_results where run_id=?',(run_id,))}
        assert len(raw[run_id])==50
    class Runtime:
        def __init__(self):self.response=None;self.provider=DeepSeekProvider(Settings('offline-fixture','https://invalid','offline-fixture'))
        def judge(self,q,expected,answer,category,context=None):
            with patch.object(self.provider,'complete',return_value=json.dumps(self.response,ensure_ascii=False)):
                return self.provider.judge(q,expected,answer,context=context)
    runtime=Runtime();runner=EvaluationRunner(None,runtime);groups={g:{} for g in ['BL','A','B','C']};roots={};seen=set()
    with patch('urllib.request.urlopen',side_effect=AssertionError('offline acceptance forbids external calls')):
        for row in fixture['records']:
            key=(row['run_id'],row['question_id']);assert key not in seen;seen.add(key)
            original=raw[row['run_id']][row['question_id']];trace=original['programmatic_metrics']['retrieval_trace']
            assert digest(original['model_answer'])==row['answer_sha256']
            assert digest(trace['final'])==row['final_sha256']
            assert ('PASS' if original['passed'] else 'FAIL')==row['historical']
            frozen=snapshots[row['run_id']][row['question_id']]
            item={**frozen,'raw':frozen,'evidence':frozen.get('evidence',[])}
            if row['group']!='BL':item['baseline_findings']=groups['BL'][row['question_id']]['judge_result']['issues']
            runtime.response=row['judge_test_response']
            scored=runner.score_execution(item,{**original['programmatic_metrics'],'answer':original['model_answer'],'retrieval':original.get('retrieved_chunks',[]),'retrieval_trace':trace})
            assert scored['evaluation_outcome']['verdict']==row['expected']
            groups[row['group']][row['question_id']]=scored
            if row['group']=='BL':
                view=diagnostic_view(scored);roots[f"Q{row['question_number']:02}"]={'root':view['primary_root_cause'],'stage':view['retrieval_failure_stage'],'target_eligible':view['target_eligible']}
    counts={g:[sum(c['passed'] for c in cases.values()),sum(not c['passed'] for c in cases.values())] for g,cases in groups.items()}
    assert counts==fixture['expected_counts'];assert len(seen)==200
    comparison={g:compare_cases(groups['BL'],groups[g],[]) for g in ['A','B','C']}
    assert all(c['comparison_complete'] for c in comparison.values())
    assert [(len(c['all_fixed_question_ids']),c['new_regressions']) for c in comparison.values()]==[(4,0),(6,3),(3,1)]
    assert set(comparison['A']['continued_failure_new_issues'])=={r['question_id'] for r in fixture['records'] if r['group']=='A' and r['question_number'] in {15,17}}
    assert not roots['Q13']['target_eligible'] and not roots['Q22']['target_eligible']
    assert roots['Q04']['root']=='Ranking'
    q7={r['group']:r['question_id'] for r in fixture['records'] if r['question_number']==7}
    assert [groups[g][q7[g]]['primary_root_cause'] for g in ['BL','A','B','C']]==['Retrieval','Ranking','Retrieval','Retrieval']
    expected_targets={f'Q{n:02}' for n in [4,6,7,8,15,17,24,27,28,29,39,42]}
    assert {q for q,v in roots.items() if v['target_eligible']}==expected_targets,roots
    return {'verification_kind':'offline_structured_test_responses_NOT_LLM_Judge','records':200,'counts':counts,'PASS':157,'FAIL':43,'owner_unresolved':0,'baseline_diagnostics':roots,'comparisons':{g:{k:v for k,v in c.items() if k in ['comparison_complete','all_fixed_question_ids','new_regression_question_ids','continued_failure_new_critical_question_ids','continued_failure_new_issues']} for g,c in comparison.items()},'provider_calls':0}
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--database',default=str(ROOT/'backend/data/demo.db'));args=parser.parse_args()
    print(json.dumps(verify(args.database),ensure_ascii=False,indent=2))
