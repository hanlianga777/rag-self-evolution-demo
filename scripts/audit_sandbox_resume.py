#!/usr/bin/env python3
"""Read-only Sandbox failure audit. Network and all Provider calls are blocked."""
import argparse,hashlib,json,os,socket,sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))


def blocked(*args,**kwargs):raise RuntimeError('Sandbox audit prohibits network / Provider calls')


def audit(database,index):
    from app.governance import GovernanceStore
    from app.evaluation import EvaluationRunner
    from app.full_text import validate_bundle
    from app.telemetry import cost_report
    store=object.__new__(GovernanceStore);store.database_path=database
    baseline=store.require_current_baseline();identity=store.current_baseline_identity()
    bundle=validate_bundle(index,require_full_text=True)
    experiment=store.experiment(identity['current_experiment_id'])
    runner=EvaluationRunner(store,SimpleNamespace(model=baseline['judge']['model']))
    report={'provider_calls':0,'baseline_id':baseline['id'],'baseline_unchanged':True,
            'evaluation_identity':baseline['judge']['evaluation_identity'],'index_valid':True,
            'knowledge_identity':bundle['manifest'].get('knowledge_identity'),'candidates':[]}
    deepseek=[]
    for c in experiment['candidates']:
        if c['reasoning'].get('candidate_label') not in {'A','B','C'}:continue
        plan=runner.candidate_resume_plan(c['id']);source=store.evaluation_run(plan['source_run_id']) if plan['source_run_id'] else None
        result=(source or {}).get('result',{});cases=store.evaluation_case_results(source['id']) if source else []
        if source:
            snapshot=json.loads(source['dataset_snapshot_json'])
            assert source['judge']==baseline['judge'] and snapshot==json.loads(baseline['dataset_snapshot_json'])
            expected=runner.candidate_inputs(c['id'])[1];assert source['config']==expected
            assert plan['reusable']==len(cases)==len({r['question_id'] for r in cases})
            if result.get('resume_source_id'):
                with store.connection() as connection:
                    old=dict(connection.execute('SELECT question_id,result_json FROM evaluation_case_results WHERE run_id=?',(result['resume_source_id'],)))
                    new=dict(connection.execute('SELECT question_id,result_json FROM evaluation_case_results WHERE run_id=?',(source['id'],)))
                assert all(new.get(q)==value for q,value in old.items())
                plan['ancestor_results_byte_identical']=len(old)
        attempts=[{'question_id':q,**a} for q,cp in result.get('checkpoints',{}).items() for a in cp.get('attempts',[])]
        events=[u for a in attempts for u in a.get('usage',[])]
        deepseek.extend(u for u in events if u.get('provider')=='DeepSeek' and u.get('status')=='ok')
        report['candidates'].append({'label':c['reasoning']['candidate_label'],'status':c['status'],'candidate_id':c['id'],
            'resume_plan':plan,'error':(source or {}).get('error_message'),'stop_request':result.get('stop_request'),
            'failed_attempts':[a for a in attempts if a.get('status')=='error'],
            'completed_results_sha256':hashlib.sha256(json.dumps(cases,sort_keys=True).encode()).hexdigest()})
    total=sum(c['resume_plan']['estimated_calls_without_retries'] for c in report['candidates'])
    historical=cost_report(baseline['judge']['model'],deepseek)
    report['budget']={'estimated_calls_without_retries':total,'historical_deepseek':historical,
        'projected_deepseek_calls':sum(c['resume_plan']['pending_answers']+c['resume_plan']['pending_judges'] for c in report['candidates']),
        'projection_is_not_hard_budget':True,'alibaba_price_and_unknown_charge':'需按账号真实账单对账；不将未知费用当0'}
    if historical.get('status')=='estimated' and deepseek:
        report['budget']['deepseek_historical_average_projection']={
            'amount':historical['amount']/len(deepseek)*report['budget']['projected_deepseek_calls'],
            'currency':historical['currency'],'basis':'已保存历史Usage/费率的均值外推，非实扣或总预算'}
    prices=historical.get('price_snapshot') or {}
    rates=list(prices.get('periods',{}).values()) or [prices]
    if deepseek and all(all(type(r.get(k)) in (int,float) for k in ('input_per_million','cached_input_per_million','output_per_million')) for r in rates):
        totals=[sum(((u['prompt_tokens']-u['prompt_cache_hit_tokens'])*rate['input_per_million']+u['prompt_cache_hit_tokens']*rate['cached_input_per_million']+u['completion_tokens']*rate['output_per_million'])/prices['unit'] for u in deepseek) for rate in rates]
        factor=report['budget']['projected_deepseek_calls']/len(deepseek)
        report['budget']['historical_sample_projection_range']={'lower':min(totals)*factor,'upper':max(totals)*factor,
            'currency':prices['currency'],'basis':'保存的峰谷费率与实际Token样本外推；非承诺、非硬预算，不含Alibaba和未知请求'}
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('database','index','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    os.environ.update(RAG_DEMO_DB_PATH=str(args.database.resolve()),RAG_DEMO_INDEX_DIR=str(args.index.resolve()),RAG_DEMO_ENV_PATH='/tmp/rag-sandbox-audit-no-env')
    with patch.object(socket.socket,'connect',blocked),patch.object(socket.socket,'connect_ex',blocked):result=audit(args.database.resolve(),args.index.resolve())
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'index_valid':result['index_valid'],'candidates':[{k:c['resume_plan'][k] for k in ('completed','reusable','can_resume','estimated_calls_without_retries')}|{'label':c['label']} for c in result['candidates']],
        'budget':{k:v for k,v in result['budget'].items() if k!='historical_deepseek'},'provider_calls':0},ensure_ascii=False))
