#!/usr/bin/env python3
"""Zero-call accounting audit over the current frozen experiment and checkpoints."""
import os,sys,json,sqlite3,hashlib,socket
from pathlib import Path
from collections import defaultdict
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'backend'),str(ROOT/'scripts')]
OUT=ROOT/'outputs/sandbox_cost_preflight_20261023'
os.environ.update(RAG_DEMO_DB_PATH=str(ROOT/'backend/data/demo.db'),RAG_DEMO_ENV_PATH='/tmp/sandbox-audit-absent.env')
from app.governance import GovernanceStore
from app.evaluation import EvaluationRunner
from app.sandbox_budget import prices
from types import SimpleNamespace

def blocked(*a,**kw):raise AssertionError('Audit prohibits all Provider/network calls')

def main():
    store=object.__new__(GovernanceStore);store.database_path=ROOT/'backend/data/demo.db'
    baseline=store.require_current_baseline();experiment=store.experiment(store.current_baseline_identity()['current_experiment_id'])
    runner=EvaluationRunner(store,SimpleNamespace(model=baseline['judge']['model']));quote=prices();rows=[];history=defaultdict(list);classes=defaultdict(lambda:{"events":0,"known_fee_cny":0.})
    with patch.object(socket.socket,'connect',blocked),patch.object(socket.socket,'connect_ex',blocked):
        for candidate in experiment['candidates']:
            label=candidate['reasoning'].get('candidate_label')
            if label not in 'ABC' or len(label)!=1:continue
            items,config,_,_=runner.candidate_inputs(candidate['id']);plan=runner.candidate_resume_plan(candidate['id'])
            source=store.evaluation_run(plan['source_run_id']) if plan['source_run_id'] else None
            cases=store.evaluation_case_results(source['id']) if source else [];done={c['question_id'] for c in cases}
            cps=(source or {}).get('result',{}).get('checkpoints',{})
            for cp in cps.values():
                seen=defaultdict(int)
                for attempt in cp.get('attempts',[]):
                    for usage in attempt.get('usage',[]):
                        key=(usage.get('provider'),usage.get('requested_model'),attempt.get('phase'));kind='retry' if seen[key] else 'normal';seen[key]+=1
                        if usage.get('status')!='ok':kind='unknown'
                        classes[kind]['events']+=1
                        if usage.get('status')=='ok':
                            rate=quote['models'][usage['requested_model']]
                            classes[kind]['known_fee_cny']+=(usage.get('prompt_tokens',usage.get('total_tokens',0))*rate['input']+usage.get('completion_tokens',0)*rate['output'])/1e6
                        if usage.get('status')=='ok':history[(usage['provider'],usage['requested_model'],attempt['phase'])].append(usage)
            assert not source or source['config']==config and source['judge']==baseline['judge']
            rows.append({'label':label,'candidate_id':candidate['id'],'config':candidate['config'],'config_sha256':hashlib.sha256(json.dumps(candidate['config'],sort_keys=True).encode()).hexdigest(),'reasoning_sha256':hashlib.sha256(json.dumps(candidate['reasoning'],sort_keys=True).encode()).hexdigest(),'run_id':plan['source_run_id'],'plan':plan,'evaluation_identity':baseline['judge']['evaluation_identity'],'completed_question_ids':[i['id'] for i in items if i['id'] in done],'pending_question_ids':[i['id'] for i in items if i['id'] not in done],'case_sha256':hashlib.sha256(json.dumps(cases,sort_keys=True).encode()).hexdigest(),'checkpoint_sha256':hashlib.sha256(json.dumps(cps,sort_keys=True).encode()).hexdigest(),'checkpoint_states':{q:{'answer_saved':'execution' in cp,'judge_saved':'scored_result' in cp,'unknown':cp.get('unknown_execution'),'inflight':cp.get('inflight')} for q,cp in cps.items()}})
    counts={'answer':sum(r['plan']['pending_answers'] for r in rows),'judge':sum(r['plan']['pending_judges'] for r in rows),'embedding':sum(r['plan']['pending_answers'] for r in rows),'rerank':sum(r['plan']['pending_answers'] for r in rows if r['config']['rerank'] is True)}
    assert counts=={'answer':111,'judge':111,'embedding':111,'rerank':61}
    rates=quote['models'];projection={};history_totals=[]
    for (provider,model,phase),usages in history.items():
        rate=rates[model];task='judge' if phase=='judge' else 'answer' if provider=='DeepSeek' else 'embedding' if model=='text-embedding-v4' else 'rerank'
        miss_output=sum((u.get('prompt_tokens',u.get('total_tokens',0))*rate['input']+u.get('completion_tokens',0)*rate['output'])/1e6 for u in usages)
        history_totals.append({'provider':provider,'model':model,'phase':phase,'successful_usage_events':len(usages),'conservative_usage_cost_cny':miss_output})
        projection[task]=miss_output/len(usages)*counts[task]
    limits=baseline['judge']['execution_snapshot']['request_limits'];caps=quote['request_byte_limits']
    upper={'answer':counts['answer']*(caps['answer']*2+limits['answer']*8)/1e6,'judge':counts['judge']*(caps['judge']*2+limits['judge']*8)/1e6,'embedding':counts['embedding']*rates['text-embedding-v4']['max_input_bytes']*.5/1e6,'rerank':counts['rerank']*rates['qwen3-rerank']['max_input_bytes']*.5/1e6}
    report={'provider_calls_this_audit':0,'fee_this_audit_cny':0,'base_commit':'4d061bc','baseline_id':baseline['id'],'baseline_completed':baseline['result'].get('completed'),'baseline_bad_cases':baseline['result'].get('bad_case_count'),'candidates':rows,'normal_request_counts':counts,'normal_total':sum(counts.values()),'historical_known_usage_by_stage':history_totals,'historical_cost_is_not_account_debit':True,'history_contains_paid_judge_recoveries':True,'historical_call_classes':dict(classes),'unknown_A_reconciled':False,'unknown_A_amount_cny':None,'mean_token_projection_peak_cny':projection,'mean_token_projection_total_peak_cny':sum(projection.values()),'mean_projection_offpeak_deepseek_cny':sum(v*(.5 if k in {'answer','judge'} else 1) for k,v in projection.items()),'normal_bound_by_stage_cny':upper,'normal_bound_total_cny':sum(upper.values()),'max_three_attempt_bound_cny':sum(upper.values())*3,'recommended_new_authorization_ceiling_cny':300,'ceiling_scope':'future shared Experiment Sandbox; historical charges including unknown A are separate and not zero','assumptions':['official Beijing Alibaba endpoints and DeepSeek peak cache miss','no config or frozen output-limit changes','request UTF8+repeated rerank query+1024 <= enforced byte ceilings','three-attempt conservative envelope; unknown stops rather than retries','current rates expire after 24h; recheck required']}
    OUT.joinpath('cost_and_checkpoint_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    protected=json.loads(OUT.joinpath('protected_before.json').read_text());changed=[p for p,s in protected.items() if hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=s];assert not changed,changed
    OUT.joinpath('protection_after.json').write_text(json.dumps({'all_unchanged':True,'files':len(protected),'provider_calls':0,'formal_database_sha256':protected['backend/data/demo.db']},indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k.endswith('_cny') or k in ['normal_total','normal_request_counts']},ensure_ascii=False))

if __name__=='__main__':main()
