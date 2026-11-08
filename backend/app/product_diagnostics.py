"""Product views calculated exclusively from saved answers, traces and usage."""
import json
from collections import defaultdict
from statistics import mean, median

from .diagnostics import automatic_analysis, diagnostic_view

STAGE_LABELS = {'query_processing':'查询处理','vector_search':'Embedding Retrieval','bm25':'BM25',
    'rerank':'Rerank','metadata_filter':'资料筛选','hybrid_fusion':'检索合并','parent_expand':'补齐上下文',
    'retrieval_other':'检索其他处理','generation':'Generation','context_budget':'上下文容量处理','context_build':'拼接上下文'}


def objective_metrics(cases, questions):
    retrieval=[];ttft=[];tokens=[];costs=[];stages=defaultdict(float)
    enhancements={key:0 for key in ('hyde','multi_query','query_rewrite')};usage_missing=0
    for case in cases:
        metrics=case.get('programmatic_metrics') or {}
        if case.get('test_category') in {'positive','ablation'}:
            result=automatic_analysis(case,golden_item=questions.get(case['question_id']))['retrieval_metrics']
            if all(result.get(k) is not None for k in ('recall_at_k','precision_at_k','mrr')):
                retrieval.append(result)
        if type(metrics.get('ttft_ms')) in (int,float):ttft.append(metrics['ttft_ms'])
        if all(type(metrics.get(k)) is int for k in ('input_tokens','output_tokens')):
            tokens.append(metrics['input_tokens']+metrics['output_tokens'])
        cost=metrics.get('cost_estimation') or {}
        if type(cost.get('amount')) in (int,float) and cost.get('currency')=='USD':costs.append(cost['amount'])
        saved_stages=metrics.get('stages') or []
        for stage in saved_stages:
            duration=stage.get('duration_ms');name=stage.get('stage_name')
            if type(duration) not in (int,float) or name=='judge':continue
            if name=='retrieval' and not stage.get('parent'):
                children=[s for s in saved_stages if s.get('parent')=='retrieval' and type(s.get('duration_ms')) in (int,float)]
                for child in children:stages[child['stage_name']]+=child['duration_ms']
                stages['retrieval_other']+=max(0,duration-sum(s['duration_ms'] for s in children))
            elif not stage.get('parent'):
                stages[name]+=duration
        usage=metrics.get('token_usage')
        auxiliary=usage.get('auxiliary_queries') if isinstance(usage,dict) else None
        if not isinstance(auxiliary,list):usage_missing+=1
        else:
            for event in auxiliary:
                if event.get('task') in enhancements and event.get('status') in {'ok','completed'}:
                    enhancements[event['task']]+=1
    total=sum(stages.values())
    count=len(cases)
    return {'recall_at_k':mean(r['recall_at_k'] for r in retrieval)*100 if retrieval else None,
        'precision_at_k':mean(r['precision_at_k'] for r in retrieval)*100 if retrieval else None,
        'mrr':mean(r['mrr'] for r in retrieval) if retrieval else None,
        'retrieval_evaluable_cases':len(retrieval),'retrieval_scope':'正向题（Positive）和消融题（Ablation），按逐题标准证据原文匹配最终内容后取平均；负向题（Negative）不纳入',
        'ttft_median_ms':median(ttft) if ttft else None,'ttft_recorded_cases':len(ttft),
        'average_tokens':mean(tokens) if len(tokens)==count and count else None,
        'token_scope':'每道保存回答的输入加输出 Token，包含 Thinking Token，不含判分和向量、Rerank',
        'average_estimated_cost':{'amount':mean(costs) if len(costs)==count and count else None,'currency':'USD',
            'recorded_cases':len(costs),'scope':'保存的回答请求费用估算；不含判分、向量、Rerank；不是整轮账单'},
        'stage_breakdown':[{'stage':name,'label':STAGE_LABELS.get(name,'其他回答处理'),'total_ms':ms,'share_percent':ms/total*100 if total else 0} for name,ms in stages.items()],
        'stage_scope':'累计已保存回答阶段；检索按直接子环节拆开，子环节不重复累计；不含判分',
        'enhancement_counts':{key:None if usage_missing else count for key,count in enhancements.items()},
        'enhancement_missing_cases':usage_missing,'enhancement_scope':'已保存辅助查询成功调用次数，不按开关推算'}


def thinking_comparison(runs,current_id):
    identities={run['judge'].get('evaluation_identity') for run,_ in runs}
    if None in identities or len(identities)>1:
        return {'columns':[],'different_cases':[],'note':'判分身份不同，不能比较 Hard Gate 或逐题修好、弄坏。'}
    columns=[];by_id={};all_ids=set()
    for run,cases in runs:
        questions={q['id']:q for q in json.loads(run['dataset_snapshot_json']).get('questions',[])}
        metrics=objective_metrics(cases,questions);gates=run['result'].get('gates') or {}
        gate_rows=gates.get('gates',[])
        latency={g['metric']:g.get('actual') for g in gate_rows if g['metric'].startswith('latency_')}
        effort=run['config'].get('generation_thinking')
        columns.append({'id':run['id'],'label':{'max':'Max','high':'High','low':'Low','off':'OFF'}.get(effort,'档位记录缺失'),
            'current':run['id']==current_id,'metrics':{**metrics,**latency,'gate_passed':gates.get('passed_count'),
            'gate_total':gates.get('total'),'correct_count':sum(c.get('passed') is True for c in cases),
            'bad_case_count':sum(c.get('passed') is False for c in cases)},'gates':gate_rows})
        by_id[run['id']]={c['question_id']:c for c in cases};all_ids.update(by_id[run['id']])
    different=[]
    for key in sorted(all_ids):
        results={run['id']:{'passed':by_id[run['id']].get(key,{}).get('passed')} for run,_ in runs}
        if len({r['passed'] for r in results.values()})<2:continue
        case=next((by_id[r['id']][key] for r,_ in runs if by_id[r['id']].get(key,{}).get('passed') is False),{})
        view=diagnostic_view(case)
        different.append({'question_id':key,'display_question_id':view['display_question_id'],'question':case.get('question'),
            'diagnosis_category':view['diagnosis_category'],'subfeature':view['subfeature'],'results':results})
    all_current_failures = all(by_id[current_id].get(row['question_id'],{}).get('passed') is False for row in different)
    note = f'两档结果不同的题目共 {len(different)} 道，均已列入本轮 Bad Case。' if all_current_failures else f'结果不同的题目共 {len(different)} 道，已按保存结果列出。'
    return {'columns':columns,'different_cases':different,'note':note,
            'judge_thinking':runs[0][0]['judge'].get('judge_thinking',{}).get('reasoning_effort')}


def product_diagnostics(store,run,cases=None):
    if 'dataset_snapshot_json' not in run:
        run=store.evaluation_run(run['id'])
    cases=store.evaluation_case_results(run['id']) if cases is None else cases
    questions={q['id']:q for q in json.loads(run['dataset_snapshot_json']).get('questions',[])}
    from .agent_inputs import baseline_bad_case_rows, baseline_review_summary
    from .optimization import baseline_diagnosis_summary, optimization_priorities
    rows=baseline_bad_case_rows(store,run)
    result={'objective_metrics':objective_metrics(cases,questions), 'review_summary': baseline_review_summary(run),
        'optimization_priorities':optimization_priorities(rows,run['result'].get('gates',{}).get('gates',[])),
        'baseline_diagnosis_summary':baseline_diagnosis_summary(rows,run['result'].get('gates',{}).get('gates',[]))}
    designation=store.baseline_designation()
    if designation and run['id']==designation['baseline_run_id']:
        comparison=store.evaluation_run(designation['comparison_run_id'])
        for saved in store.evaluation_history():
            if (saved['id']==run['id'] or saved['status']!='completed'
                    or saved.get('run_mode')!='real' or saved.get('data_source')!='real'
                    or saved.get('dataset_version_id')!=run.get('dataset_version_id')
                    or saved['result'].get('evaluation_complete') is not True or saved['result'].get('technical_failed')
                    or not saved['result'].get('judge_replay',{}).get('source_run_id')
                    or saved['judge'].get('evaluation_identity')!=run['judge'].get('evaluation_identity')
                    or saved['config'].get('generation_thinking')==run['config'].get('generation_thinking')):
                continue
            if {k:v for k,v in saved['config'].items() if k!='generation_thinking'} != {k:v for k,v in run['config'].items() if k!='generation_thinking'}:
                continue
            comparison=store.evaluation_run(saved['id'])
            break
        if comparison:
            result['thinking_comparison']=thinking_comparison([(comparison,store.evaluation_case_results(comparison['id'])),(run,cases)],run['id'])
    return result
