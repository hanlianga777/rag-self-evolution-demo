"""Deterministic, zero-Provider coverage planning over saved evidence only."""
import json
import sqlite3
from itertools import combinations
from pathlib import Path

from .agent_recovery import digest
from .diagnostics import diagnostic_view
from .full_text import CORPUS_LOCK
from .governance import _json, _now
from .optimization import prepare_response, validate_intervention
from .policy import DEFAULT_PIPELINE_CONFIG, ALLOWED_SEARCH_SPACE, validate_candidate_config

VERSION='coverage-planner-1'
REQUIREMENTS='相同冻结50题回答与Judge；检查目标要求及来源适用性、原有事实保留、11 Gate、Regression；人工发布。离线准入不证明修复。'


def plan_coverage(rows,base,candidates,*,round_number=1,labels=None):
    """Proposals never count as saved coverage. Group by actual legal interventions."""
    labels=list('ABC') if labels is None else labels
    current=[c for c in candidates if c['reasoning'].get('round',1)==round_number and c['reasoning'].get('candidate_label') in {'A','B','C'}]
    available=[label for label in labels if label not in {c['reasoning'].get('candidate_label') for c in current}]
    targets={ref:r['result'] for r in rows for ref in (r['id'],r['question_id'])}
    views={r['question_id']:r.get('diagnostic_view') or diagnostic_view(r['result']) for r in rows}
    matrix={r['question_id']:{'question_id':r['question_id'],'root_cause':views[r['question_id']]['primary_root_cause'],
        'observations':views[r['question_id']].get('experiment_plan',{}).get('observations',[]),
        'candidates':[],'proposed_candidates':[],'gap':None,'validation_requirements':REQUIREMENTS} for r in rows}
    rejected=[]
    for c in current:
        r=c['reasoning'];diff={k:v for k,v in c['config'].items() if v!=base.get(k)}
        try:
            if not validate_candidate_config(c['config'])['valid']:raise ValueError('配置超出Search Space')
            if diff!=r.get('changed_parameters'):raise ValueError('完整Diff与审计不符')
            p={**r,'target_bad_cases':r.get('observed_evidence',[]),'why':r.get('proposal'),'config_diff':diff}
            validate_intervention(p,targets,base)
            if not p['target_bad_cases']:raise ValueError('候选没有目标')
            for row in rows:
                if set((row['id'],row['question_id'])) & set(p['target_bad_cases']):
                    matrix[row['question_id']]['candidates'].append({'id':c['id'],'label':r['candidate_label'],
                        'config_diff':diff,'hypothesis':r['hypothesis'],'origin':(r.get('provenance') or {}).get('origin','saved_model_candidate')})
        except (ValueError,KeyError,TypeError) as error:rejected.append({'id':c['id'],'reason':str(error)})
    uncovered={q for q,m in matrix.items() if not m['candidates']}
    # Bounded single-stage templates. No retrieval calls, new evidence or guessed causal roots.
    options=[]
    for key,direction in [('candidate_k','candidate_recall'),('top_k','context_selection'),('rerank','context_selection'),('prompt_strategy','grounded_generation')]:
        values=list(ALLOWED_SEARCH_SPACE[key])
        if key=='rerank':values.sort(key=lambda value:0 if value=='query_only' else 1)
        for value in values:
            if type(value)==type(base.get(key)) and value==base.get(key):continue
            if key in {'candidate_k','top_k'} and value<=base.get(key,0):continue
            diff={key:value};config={**base,**diff}
            if not validate_candidate_config(config,prior_configs=[base,*[c['config'] for c in candidates]])['valid']:continue
            valid=[]
            for row in rows:
                q=row['question_id'];view=views[q];plan=view.get('experiment_plan',{})
                if q not in uncovered or plan.get('status')!='exploratory' or direction not in plan.get('directions',[]):continue
                p=_proposal('?',direction,diff,[row],views)
                try:validate_intervention(p,targets,base)
                except (ValueError,KeyError,TypeError):continue
                valid.append(row)
            if valid:options.append(_proposal('?',direction,diff,valid,views))
    best=()
    for size in range(1,min(len(available),len(options))+1):
        for group in combinations(options,size):
            covered=set().union(*(set(p['target_bad_cases']) for p in group))
            previous=set().union(*(set(p['target_bad_cases']) for p in best)) if best else set()
            if len(covered)>len(previous):best=group
    proposals=[]
    for label,option in zip(available,best):
        p={**option,'id':label};proposals.append(p)
        for q in p['target_bad_cases']:matrix[q]['proposed_candidates'].append(label)
    reachable=set().union(*(set(p['target_bad_cases']) for p in options)) if options else set()
    for q in uncovered:
        if matrix[q]['proposed_candidates']:continue
        plan=views[q].get('experiment_plan',{})
        matrix[q]['gap']='本轮剩余A/B/C容量不足，需明确调整规划，不能宣称完成' if q in reachable else '当前规则模板未找到通过严格验证的干预；'+str(plan.get('next_action') or plan.get('blockers') or '需人工扩展已验证规划能力')
    covered=sum(bool(m['candidates']) for m in matrix.values())
    pending=any(m['proposed_candidates'] or q in reachable for q,m in matrix.items() if not m['candidates'])
    return {'version':VERSION,'round':round_number,'status':'incomplete' if pending or rejected else 'complete' if covered==len(rows) else 'complete_with_gaps',
        'total':len(rows),'covered_count':covered,'planned_count':sum(bool(m['candidates'] or m['proposed_candidates']) for m in matrix.values()),
        'matrix':list(matrix.values()),'proposals':proposals,'rejected_saved_candidates':rejected,'provider_calls':0,
        'planner_scope':'单阶段最小参数探索模板；未覆盖能力明确列为缺口，不证明修复或语义充分。'}


def _proposal(label,direction,diff,rows,views):
    roots={r['question_id']:views[r['question_id']]['primary_root_cause'] for r in rows}
    observation={'candidate_recall':'candidate_pool_gap','context_selection':'context_pool_gap','grounded_generation':'answer_requirement_gap'}[direction]
    explanation={'candidate_recall':'扩大候选池，检验冻结规范缺失是否可被补回',
        'context_selection':'调整上下文选择，检验候选已含但Final遗漏的规范能否恢复',
        'grounded_generation':'调整有据回答策略，检验已保存要求的遗漏能否改善'}[direction]
    return {'id':label,'target_bad_cases':list(roots),'root_cause_evidence':list(roots),'target_root_causes':roots,
        'root_cause':next(iter(set(roots.values()))) if len(set(roots.values()))==1 else 'Unknown',
        'experiment_kind':'exploratory','intervention_direction':direction,'config_diff':diff,
        'evidence_assertions':[{'target_id':q,'observation':observation} for q in roots],
        'parameter_dependencies':[],'supporting_directions':[],
        'hypothesis':explanation+'；'+_json(diff)+'，仅为规则生成的可证伪实验假设，未确认因果',
        'why':'逐题保存Trace的'+observation+'支持此方向；保持各题原始诊断，不推断缺失证据',
        'expected_improvement':'目标要求覆盖改善；以正式完整Sandbox结果为准',
        'risk':'可能引入噪声、事实丢失、延迟和安全退化',
        'falsification':'若目标仍FAIL、来源不适用、原事实丢失或新增失败，则假设不成立；Gate与Regression不变',
        'provenance':{'origin':'deterministic_coverage_planner','version':VERSION,'hypothesis_origin':'explicit_structural_template_not_llm',
                      'source_question_ids':list(roots),'evidence_observation':observation}}


def coverage_inputs(store,experiment_id):
    experiment=store.experiment(experiment_id)
    if not experiment:raise ValueError('Experiment不存在')
    baseline=store.evaluation_run(experiment['baseline_run_id'])
    rows=[{**r,'diagnostic_view':diagnostic_view(r['result'])} for r in store.bad_case_rows(baseline['id']) if r['run_id']==baseline['id']]
    from .evaluation_contract import business_verdict
    rows=[r for r in rows if business_verdict(r['result'])=='FAIL' or (r['result'].get('evaluation_outcome') or {}).get('contract_version')!='business-vnext-1' and r['result'].get('passed') is False]
    base={**DEFAULT_PIPELINE_CONFIG,**baseline['config']}
    for key in ('run_target','knowledge_identity'):base.pop(key,None)
    number=max([c['reasoning'].get('round',1) for c in experiment['candidates'] if c['reasoning'].get('candidate_label') in {'A','B','C'}] or [1])
    report=plan_coverage(rows,base,experiment['candidates'],round_number=number)
    report['binding']=digest({'experiment':experiment,'baseline':baseline,'rows':rows,'plan':report})
    return experiment,baseline,rows,base,report


def complete_coverage(store,experiment_id,*,expected_binding,backup_path):
    """Append B/C in the same round; saved A, responses and usage remain immutable."""
    with CORPUS_LOCK,store.connection() as connection:
        connection.execute('BEGIN IMMEDIATE')
        experiment,baseline,rows,base,report=coverage_inputs(store,experiment_id)
        store.require_current_baseline(baseline['id'],connection)
        if store.current_baseline_identity(connection)['current_experiment_id']!=experiment_id:raise ValueError('不是当前Experiment')
        if report['binding']!=expected_binding:raise ValueError('规划身份或证据已变化，请重新预览')
        if experiment['status']!='completed' or experiment['result'].get('report_confirmation') or any(c['status'] in {'running','queued'} for c in experiment['candidates']):raise ValueError('实验正在运行或已确认，不能补齐规划')
        audit={}
        _,batch=prepare_response(_json({'candidates':report['proposals']}),base,rows,experiment['candidates'],
            experiment['evaluation_budget']['used'],report['round'],list('ABC'),None,[],audit)
        if audit['rejected_candidates']:raise ValueError('规划候选未通过统一验证：'+_json(audit['rejected_candidates']))
        projected=[*experiment['candidates'],*[{'id':experiment_id+'-'+label,'status':'generated','config':config,'reasoning':reason} for label,config,reason in batch]]
        final=plan_coverage(rows,base,projected,round_number=report['round'])
        final.update(source_binding=expected_binding,applied_at=_now(),added_candidate_ids=[experiment_id+'-'+b[0] for b in batch])
        path=Path(backup_path)
        if path.exists():raise ValueError('备份路径已存在')
        path.parent.mkdir(parents=True,exist_ok=True)
        # A separate reader backs up committed state; never back up the active writer.
        with sqlite3.connect(store.database_path) as source,sqlite3.connect(path) as destination:source.backup(destination)
        for label,config,reason in batch:
            connection.execute("INSERT INTO candidate_configs(id,experiment_id,status,config_json,reasoning_json,result_json,created_at) VALUES (?,?,'generated',?,?,'{}',?)",(experiment_id+'-'+label,experiment_id,_json(config),_json(reason),_now()))
        connection.execute("INSERT INTO agent_traces(experiment_id,status,result_json,created_at) VALUES (?,'coverage_planned',?,?)",(experiment_id,_json({'coverage_plan':final,'provider_calls':0,'validation_audit':audit}),_now()))
        connection.execute('UPDATE experiments SET result_json=? WHERE id=?',(_json({**experiment['result'],'coverage_plan':final}),experiment_id))
    return final
