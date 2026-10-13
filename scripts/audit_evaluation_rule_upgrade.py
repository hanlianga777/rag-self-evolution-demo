"""Read-only saved-Judge comparison, not a paid replay or formal Baseline."""
import csv
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.evaluation import EvaluationRunner, summarize_evaluation_cases
from app.evaluation_contract import VERSIONS, evaluation_identity


def audit():
    spec=importlib.util.spec_from_file_location('app._legacy_rules',ROOT/'docs/evaluation_rules/v1.2.1-claim-consistency.py')
    legacy=importlib.util.module_from_spec(spec);spec.loader.exec_module(legacy)
    ids=['EVAL-20261013055639244452','EVAL-20261013083057546375']
    records={}
    with sqlite3.connect((ROOT/'backend/data/demo.db').as_uri()+'?mode=ro',uri=True) as db:
        db.execute('PRAGMA query_only=ON');db.execute('BEGIN');db.row_factory=sqlite3.Row
        for key in ids:
            run=dict(db.execute('SELECT * FROM evaluation_runs WHERE id=?',(key,)).fetchone())
            records[key]=(run,{r['question_id']:json.loads(r['result_json']) for r in db.execute('SELECT * FROM evaluation_case_results WHERE run_id=?',(key,))})
    rows={};counts={}
    for key,(run,cases) in records.items():
        snapshot=json.loads(run['dataset_snapshot_json']);meta=json.loads(run['judge_json'])
        assert run['status']=='completed' and len(cases)==50
        assert evaluation_identity(snapshot,meta)==meta['evaluation_identity']
        items=[{**q,'raw':q,'evidence':q.get('evidence',q.get('acceptable_evidence',[]))} for q in snapshot['questions']]
        changed=[];previews=[]
        for item in items:
            case=cases[item['id']];metrics=case['programmatic_metrics'];judge=case['judge_result']
            assert legacy.assess_claims(case['model_answer'],judge,metrics['retrieval_trace']['final'])==metrics['claim_assessment']
            class SavedJudge:
                def judge(self,*args,**kwargs):return deepcopy(judge)
            execution={**metrics,'answer':case['model_answer'],'retrieval':case['retrieved_chunks']}
            preview=EvaluationRunner(None,SavedJudge()).score_execution(item,execution)
            previews.append(preview)
            comparison={'policy_behavior':{'old':judge['behavior_pass'],'preview':preview['programmatic_metrics']['behavior_contract']['effective_pass']},'passed':{'old':case['passed'],'preview':preview['passed']},
                'primary_root_cause':{'old':case['primary_root_cause'],'preview':preview['primary_root_cause']},
                'confidence':{'old':case['diagnosis']['status'],'preview':preview['diagnosis']['status']}}
            differences=[field for field,values in comparison.items() if values['old']!=values['preview']]
            reasons={'diagnosis':preview['diagnosis'],'behavior_contract':preview['programmatic_metrics']['behavior_contract']}
            rows.setdefault(item['id'],{'题号':'Q'+item['id'][-2:],'题目':item['question']})
            prefix='Baseline' if key==ids[0] else 'Candidate_A'
            rows[item['id']].update({prefix+'_新旧差异':json.dumps(comparison,ensure_ascii=False),prefix+'_原因':json.dumps(reasons,ensure_ascii=False),prefix+'_旧FailureTags':json.dumps(case['failure_tags'],ensure_ascii=False),prefix+'_预览FailureTags':json.dumps(preview['failure_tags'],ensure_ascii=False),prefix+'_缺失新版字段':[r['claim'] for r in judge.get('claim_reviews',[]) if r.get('kind')=='unresolved']})
            if differences:changed.append({'question_id':item['id'],'changed_fields':differences})
        counts[key]={'changed':changed,'old_identity':meta['evaluation_identity'],'preview_identity':evaluation_identity(snapshot,{**meta,**VERSIONS}),'formal_result':False,'new_provider_calls':0,'preview_gates':summarize_evaluation_cases(previews)['gates'],'preview_bad_cases':sum(not c['passed'] for c in previews)}
    output=ROOT/'docs/EVALUATION_RULE_UPGRADE_50_DIFF.csv'
    with output.open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(next(iter(rows.values()))),lineterminator="\n");writer.writeheader();writer.writerows(rows.values())
    assert len(rows)==50
    (ROOT/'output/playwright/evaluation-governance-20261013/offline-diff-summary.json').write_text(json.dumps(counts,ensure_ascii=False,indent=2))
    print(json.dumps(counts,ensure_ascii=False))


if __name__=='__main__':audit()
