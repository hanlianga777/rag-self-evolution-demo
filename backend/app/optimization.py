"""Manually started, bounded A/B/C Optimization Agent for V1.3."""

from __future__ import annotations

import json
import math
import hashlib
import re
from contextlib import contextmanager
from datetime import datetime, timezone
from collections import Counter

from .providers import ProviderRequestError, provider_error_details
from .diagnostics import diagnostic_view
from .diagnostic_categories import DIAGNOSTIC_CATEGORIES
from .agent_inputs import prepare_baseline_rows, retrieval_facts, is_optimization_target, is_unstable_case, baseline_bad_case_rows
from .paid_run import provider_task
from .telemetry import collect_usage, measure, cost_fields
from .policy import ALLOWED_SEARCH_SPACE, DEFAULT_PIPELINE_CONFIG, MAX_EVALS, canonicalize_config, search_space_contract, validate_candidate_config


INTERVENTIONS = {
    'query_expansion': ({'query_rewrite','multi_query','hyde'}, {'recall_missing'}),
    'candidate_recall': ({'candidate_k','hybrid_search','hybrid_alpha'}, {'recall_missing'}),
    'context_selection': ({'top_k','rerank','min_score','retrieval_max_tokens'}, {'ranking_omission','retrieval_noise'}),
    'grounded_generation': ({'prompt_strategy','generation_thinking'}, {'final_sufficient','confirmed_claim','safety_failure'}),
    'stage_performance': (set(search_space_contract()), {'measured_latency'}),
}


DIRECTION_PARAMETERS = {
    '改写查询':['query_rewrite'], 'HyDE':['hyde'], '多路查询':['multi_query'],
    '候选数':['candidate_k'], '混合检索':['hybrid_search','hybrid_alpha'],
    '重排':['rerank'], '保留条数':['top_k'], '最低分数线':['min_score'],
    '回答策略':['prompt_strategy'], '上下文窗口':['retrieval_max_tokens'], '思考档位':['generation_thinking'], '降低思考档位':['generation_thinking'],
    '关闭耗时环节':['hyde','multi_query','query_rewrite','rerank'], '调整检索参数':['candidate_k','top_k'],
}
PRIORITY_PARAMETERS = {row['label']:list(dict.fromkeys(key for direction in row['directions'] for key in DIRECTION_PARAMETERS.get(direction, []))) for row in DIAGNOSTIC_CATEGORIES}

PARAMETER_ACTIONS = {
    'candidate_k':'调整候选池','top_k':'调整TopK','min_score':'调整最低分数线',
    'hybrid_search':'调整混合检索','hybrid_alpha':'调整混合比例','rerank':'调整重排',
    'query_rewrite':'调整查询改写','multi_query':'调整多路查询','hyde':'调整HyDE',
    'prompt_strategy':'调整回答策略','generation_thinking':'调整思考档位',
    'retrieval_max_tokens':'调整检索长度上限',
}


ROUND_DIRECTIONS = ('检索召回增强', '排序与过滤', '回答策略', '效率（降档 + 检索补偿）')
THINKING_LEVELS = ('off', 'low', 'high', 'max')
EFFICIENCY_PARAMETERS = {'hyde','multi_query','candidate_k','top_k','min_score','rerank','hybrid_alpha'}


def gate_harming_changes(prior_candidates, baseline_gates=None):
    baseline = {g.get('id') or g.get('metric'):g for g in baseline_gates or []}
    changes=[]
    for candidate in prior_candidates:
        gates=candidate.get('result',{}).get('gates',{})
        gates=gates.get('gates',[]) if isinstance(gates,dict) else gates or []
        harmed=[]
        for gate in gates:
            original=baseline.get(gate.get('id') or gate.get('metric'))
            if gate.get('passed') is False and (not original or original.get('passed') is True):
                harmed.append(gate)
            elif original and type(gate.get('actual')) in (int,float) and type(original.get('actual')) in (int,float):
                worse=gate['actual'] < original['actual'] if original.get('operator')=='>=' else gate['actual'] > original['actual']
                if gate.get('passed') is False and worse: harmed.append(gate)
        if harmed:
            diff=candidate.get('reasoning',{}).get('changed_parameters',{})
            changes.append({'candidate_id':candidate['id'] if 'id' in candidate else None,'config_diff':diff,'harmed_gates':harmed})
    return changes


def validate_round_contract(candidates, baseline, prior_candidates, baseline_gates=None):
    if len(candidates)!=3 or {c.get('id') for c in candidates}!={'A','B','C'}:
        raise ValueError('每轮必须恰好提供A/B/C三套方案')
    directions=[c.get('direction') for c in candidates]
    if any(d not in ROUND_DIRECTIONS for d in directions) or len(set(directions))!=3 or directions.count(ROUND_DIRECTIONS[-1])!=1:
        raise ValueError('三套方向须不同，且必须恰好一套效率（降档 + 检索补偿）')
    used=set()
    for candidate in candidates:
        diff=candidate.get('config_diff')
        if not isinstance(diff,dict) or not diff:raise ValueError('Config Diff必须包含实际参数改动')
        if used & set(diff):raise ValueError('同轮方案不得共用参数：'+','.join(sorted(used & set(diff))))
        used.update(diff)
        current=baseline.get('generation_thinking','max')
        proposed=diff.get('generation_thinking',current)
        if current not in THINKING_LEVELS or proposed not in THINKING_LEVELS:raise ValueError('未知Thinking档位')
        lower=THINKING_LEVELS.index(proposed)<THINKING_LEVELS.index(current)
        if candidate['direction']==ROUND_DIRECTIONS[-1]:
            if not lower or not EFFICIENCY_PARAMETERS & {k for k,v in diff.items() if v!=baseline.get(k)}:
                raise ValueError('效率方案必须降低Thinking且实际修改至少一个检索补偿参数')
        elif lower:raise ValueError('质量方向不得降低Thinking')
        for previous in gate_harming_changes(prior_candidates,baseline_gates):
            harmed=previous['config_diff']
            if harmed and all(k in diff and diff[k]==v for k,v in harmed.items()):
                raise ValueError('不得照搬已证明伤害门槛的相同改动')


def validate_intervention(candidate, targets, baseline):
    """Priority directions are advice; validate actual changes and saved targets only."""
    diff=candidate.get('config_diff')
    if not isinstance(diff,dict) or not diff or any(value==baseline.get(key) for key,value in diff.items()):
        raise ValueError('Config Diff必须包含实际参数改动')
    config={**baseline,**diff}
    if config.get('hybrid_search') is False and 'hybrid_alpha' not in diff:
        config.pop('hybrid_alpha',None)
    check=validate_candidate_config(config)
    if not check['valid']:raise ValueError('非法参数：'+'；'.join(check['errors']))
    references=candidate.get('target_bad_cases')
    if not isinstance(references,list) or not references:
        raise ValueError('方案必须有目标错题')
    for reference in references:
        if reference not in targets:raise ValueError('目标不是本次运行保存的错题')
        if not diagnostic_view(targets[reference])['target_eligible']:
            raise ValueError('目标记录缺失，先补齐记录')
    for field in ('hypothesis','why','expected_improvement','risk'):
        if not isinstance(candidate.get(field),str) or not candidate[field].strip():
            raise ValueError('缺少方案思路、理由、预期改善或风险')


def parameter_signature(base_config, diff):
    """Order-independent signature of the complete proposed parameter combination."""
    config = {**base_config, **diff}
    if config.get('hybrid_search') is False and 'hybrid_alpha' not in diff:
        config.pop('hybrid_alpha', None)
    return hashlib.sha256(canonicalize_config(config).encode()).hexdigest()


def baseline_diagnosis_summary(bad_cases, gates):
    """Saved Gate values only; within 5% of the threshold is shown as near it."""
    summary = []
    for gate in gates or []:
        actual, target = gate.get('actual'), gate.get('threshold')
        if type(actual) not in (int, float) or type(target) not in (int, float):
            continue
        margin = actual - target if gate.get('operator') == '>=' else target - actual
        if gate.get('passed') is not False and margin > abs(target) * 0.05:
            continue
        metric = gate.get('metric') or gate.get('id')
        groups = {}
        unstable = []
        targets = []
        pending = []
        for row in bad_cases:
            case = row['result']
            category = case.get('test_category')
            relevant = (str(metric).startswith('positive_') and category == 'positive'
                        or str(metric).startswith('ablation_') and category == 'ablation'
                        or metric == 'safe_rejection_rate' and category == 'negative'
                        or metric == 'safety_critical_accuracy' and category == 'negative' and case.get('negative_subtype') == 'safety_critical'
                        or metric == 'prompt_injection_resistance' and category == 'negative' and case.get('negative_subtype') == 'prompt_injection')
            if relevant:
                view = row.get('diagnostic_view') or diagnostic_view(case)
                groups.setdefault(view.get('diagnosis_category', '记录缺失：缺分类记录'), []).append(view.get('display_question_id') or row['question_id'])
                (targets if is_optimization_target(row) else unstable if is_unstable_case(row) else pending).append(view.get('display_question_id') or row['question_id'])
        labels={'positive_correctness':'正向题正确性','positive_faithfulness':'正向题忠实性','positive_completeness':'正向题完整性','ablation_correctness':'消融题正确性','ablation_faithfulness':'消融题忠实性','ablation_completeness':'消融题完整性','safe_rejection_rate':'安全拒答率','safety_critical_accuracy':'安全关键准确率','prompt_injection_resistance':'提示注入抵抗','latency_p50_seconds':'回答耗时中位数','latency_p99_seconds':'回答耗时第99百分位'}
        failed = gate.get('passed') is False or gate.get('status') == 'FAIL'
        unstable_only = failed and bool(unstable) and not targets and not pending
        unstable_note = 'Baseline 该门槛未过由不稳定题造成（复核多数判对），方案仍须通过该门槛' if unstable_only else ''
        pending_note = '复核技术异常或未完成，门槛归因未知；方案仍须通过该门槛' if failed and pending else ''
        summary.append({'dimension': metric, 'dimension_label':labels.get(metric,'维度记录缺失'), 'baseline_value': actual, 'target_value': target,
                        'operator': gate.get('operator'), 'gap': max(0, -margin),
                        'status': '未通过' if failed else '接近门槛',
                        'root_causes': [{'diagnosis_category': key, 'question_ids': ids,
                                         'priority': 1 if failed and any(q in targets for q in ids) else next((c['priority'] for c in DIAGNOSTIC_CATEGORIES if c['label']==key), None),
                                         'priority_note': '导致门槛未过：'+labels.get(metric,'维度记录缺失') if failed and any(q in targets for q in ids) else unstable_note} for key, ids in groups.items()],
                        'target_question_ids': targets,
                        'root_cause_note': pending_note or unstable_note or ('整轮耗时问题，需结合已保存耗时拆解' if str(metric).startswith('latency_') else None if groups else '记录缺失：没有该维度对应的错题诊断')})
    for item in summary:
        if item.get('root_cause_note') and any(word in item['root_cause_note'] for word in ('复核','不稳定')):item['root_cause_note']='记录不足，门槛归因未知'
        for cause in item['root_causes']:
            if '不稳定' in (cause.get('priority_note') or ''):cause['priority_note']=''
    return summary


def optimization_priorities(bad_cases, gates):
    summary = baseline_diagnosis_summary(bad_cases, gates)
    counts = Counter((row.get('diagnostic_view') or diagnostic_view(row['result']))['diagnosis_category'] for row in bad_cases if is_optimization_target(row))
    priorities = []
    for definition in DIAGNOSTIC_CATEGORIES:
        label = definition['label']
        if not counts[label]:continue
        causes = [cause for item in summary if item['status']=='未通过' for cause in item['root_causes'] if cause['diagnosis_category']==label and cause['priority']==1]
        priorities.append({**definition, 'count':counts[label], 'priority':1 if causes else definition['priority'] or 3,
                           'priority_note':'；'.join(dict.fromkeys(cause['priority_note'] for cause in causes))})
    return sorted(priorities, key=lambda item:item['priority'])


def build_agent_prompt(bad_cases, base_config, prior_candidates, failed_gates, labels, *, baseline_gates=None, evaluation_budget=None, failed_parameter_signatures=None):
    """Build the exact Agent request without a Provider or persistence side effect."""
    system = ('你是RAG优化Agent。根据保存的错题诊断提出优化方案。'
              '一个方案=一个思路+必要的几个参数，可以跨环节联动。对照表表示优先尝试，不限制其他参数。'
              '先读程序生成的基线诊断摘要。每轮恰好ABC三套，每套direction为检索召回增强/排序与过滤/回答策略/效率（降档 + 检索补偿）之一。三套方向不同，恰好一套效率：Thinking低于Baseline且至少改HyDE、Multi-Query、CandidateK、TopK、MinScore、Rerank、Hybrid权重之一；另两套不得降档。同轮修改参数互斥。不得照搬gate_harming_changes。'
              '导致门槛未过的错题分类优先级升为1，按optimization_priorities及其原因安排优化。每个参数的用途与各可选值说明见allowed_parameter_values。'
              '每个参数的预期影响须点名预计修好的目标题号；风险须说明可能弄坏的题号或指标及原因；不得重复失败组合签名。'
              'target_bad_cases可用展示题号（例如Q04）、正式题目ID或Bad Case ID，必须引用当前bad_cases。'
              '没有合格方案就回到分析并再出一轮，最多12次试跑，其中1次留给D。D仅合并已验证有效改动；'
              'D无新增错题且至少修好1道才发布，否则保留赢家；发布规则与门槛不变。'
              '只返回JSON，格式：{"candidates":[{"id":"A","action_name":"中文动作短语",'
              '"direction":"检索召回增强","strategy_name":"「动作名」（检索优先）","core_idea":"一两句话",'
              '"adjustments":[{"parameter":"参数名","baseline_value":0,"candidate_value":0,"expected_impact":"预计修好Q04"}],'
              '"risks":[{"question_ids":[],"metric":"可能退化的指标","reason":"原因"}],'
              '"hypothesis":"一个优化思路","why":"对应错题及理由","target_bad_cases":["Q04"],'
              '"config_diff":{},"expected_improvement":"预期改善","risk":"可能退化"}]}。')
    gates = baseline_gates if baseline_gates is not None else failed_gates
    priorities = optimization_priorities(bad_cases, gates)
    priority_by_category = {item['label']:item for item in priorities}
    rows=[]
    for row in bad_cases:
        view=row.get('diagnostic_view') or diagnostic_view(row['result'])
        rows.append({'id':row['id'],'question_id':row['question_id'], 'display_question_id':view.get('display_question_id', row['question_id']),
                     'question':row['result'].get('question'),
                     'diagnosis_category':view.get('diagnosis_category',view['primary_root_cause']),
                     'reason':view['analysis_reason'], 'subfeature':view.get('subfeature'), 'severity_label':view.get('severity_label'),
                     'priority':priority_by_category.get(view.get('diagnosis_category'),{}).get('priority',view.get('priority')),
                     'priority_note':priority_by_category.get(view.get('diagnosis_category'),{}).get('priority_note',''),
                     'retrieval_facts':row.get('retrieval_facts') or retrieval_facts(row['result'])})
    budget = {**{'used': 0, 'max': MAX_EVALS, 'reserved_for_d': 1}, **(evaluation_budget or {})}
    budget.update(remaining=max(0, budget['max'] - budget['used']), remaining_for_abc=max(0, budget['max'] - budget['used'] - budget['reserved_for_d']))
    prompt={
        'baseline_diagnosis_summary':baseline_diagnosis_summary(bad_cases, gates),
        'optimization_priorities':priorities,
        'evaluation_budget':budget, 'next_action':'analyze_and_propose' if budget['remaining_for_abc'] else 'review_for_d',
        'failed_parameter_signatures':failed_parameter_signatures or [],
        'goal':{'objective':'通过11项门槛、错题总数少于Baseline、至少修好1道目标错题，安全关键题和提示注入题无新错。普通新错留给方案D处理。',
                'failed_gates':failed_gates,'candidate_labels':labels,'baseline_configuration':base_config},
        'bad_cases':rows,
        'priority_parameters':PRIORITY_PARAMETERS,
        'allowed_parameter_values':search_space_contract(),
        'round_contract':{'directions':ROUND_DIRECTIONS,'count':3,'exactly_one_efficiency':True,'parameters_disjoint':True},
        'gate_harming_changes':gate_harming_changes(prior_candidates,gates),
        'prior_sandbox_results':[{'id':c['id'],'action_name':c.get('reasoning',{}).get('action_name'),
            'hypothesis':c.get('reasoning',{}).get('hypothesis'),'configuration':c['config'],'status':c['status'],
            'result':{key:c.get('result',{}).get(key) for key in ('qualification','bad_case_count','all_fixed_question_ids','new_failure_question_ids','regression','gates')}} for c in prior_candidates],
    }
    return system,prompt


def strategy_case(row):
    """All business failures enter processing; execution eligibility stays separate."""
    case=row.get('result',{})
    view=row.get('diagnostic_view') or diagnostic_view(case)
    return {'id':row.get('id'),'question_id':row.get('question_id'),'category':view['primary_root_cause'],
            'result':{key:case.get(key) for key in ('question','reference_answer','model_answer','test_category','negative_subtype')} | {'primary_root_cause':view['primary_root_cause']},
            'retrieval_trace':(case.get('programmatic_metrics') or {}).get('retrieval_trace'),
            'golden_evidence':{key:(case.get('programmatic_metrics') or {}).get('evidence_sufficiency',{}).get(key) for key in ('source_constraints','facts')},
            'diagnostic_view':{key:view.get(key) for key in ('diagnosis_category','subfeature','severity_label','priority','display_question_id','retrieval_positions','tuning_directions','retrieval_metrics','analysis_category','analysis_reason','primary_root_cause','target_eligible','is_technical_bad_case','evidence_checks','optimization_directions','trace_observations','retrieval_failure_stage','context_selection_options','optimization_blockers','diagnostic_gaps','diagnosis_complete','experiment_plan')}}


def strategy_candidate(candidate):
    return {key:candidate.get(key) for key in ('id','config','status')} | {
        'reasoning':{key:value for key,value in candidate.get('reasoning',{}).items() if key!='target_diagnosis'},
        'result':{key:value for key,value in candidate.get('result',{}).items() if key not in {'checkpoints','all_bad_case_audit'}}}


def unique_keys(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError('Agent JSON存在重复键：'+key)
        result[key]=value
    return result


def reject_constant(value):
    raise ValueError('Agent JSON包含非有限数值：'+value)


def finite_float(value):
    result=float(value)
    if not math.isfinite(result):raise ValueError('Agent JSON包含非有限数值')
    return result


def prepare_response(content,base_config,bad_cases,prior_candidates,completed,round_number,labels,trigger_id,monitoring_target_event_ids,audit):
    """One offline validation path for fresh and already-paid responses; no semantic repairs."""
    prior=[base_config]+[item['config'] for item in prior_candidates]
    target_reference_map={key:{'bad_case_id':item['id']} for item in bad_cases for key in (item['id'],item['question_id'])}
    display_ids = {}
    for item in bad_cases:
        display = item['diagnostic_view'].get('display_question_id')
        if isinstance(display,str) and re.fullmatch(r'Q\d+',display):
            display_ids.setdefault(display, set()).add(item['question_id'])
    # Only unambiguous aliases from this Baseline's frozen question mapping are valid.
    display_ids = {key:next(iter(ids)) for key,ids in display_ids.items() if len(ids)==1}
    target_reference_map.update({key:target_reference_map[value] for key,value in display_ids.items()})
    audit["validation_stage"] = "json_parse"
    result = json.loads(content, object_pairs_hook=unique_keys, parse_constant=reject_constant, parse_float=finite_float)
    audit["parsed_json"] = result
    audit["validation_stage"] = "schema"
    if not isinstance(result, dict) or not isinstance(result.get("candidates"), list):
        audit.update(failed_field="candidates", actual_value=result.get("candidates") if isinstance(result, dict) else result, expected_type="array", allowed_values=None)
        raise ValueError("Agent 输出必须包含 candidates 数组")
    candidates = result.get("candidates", [])
    audit["parsed_candidates"] = candidates
    validate_round_contract(candidates,base_config,prior_candidates,(audit.get('baseline_gate_results') or {}).get('gates'))
    audit.update(response_contract_version='agent-response-2',rejected_candidates=[],response_warnings=[])
    if len(candidates)<len(labels) and not isinstance(result.get('insufficient_evidence'),str):
        audit['response_warnings'].append({'field':'insufficient_evidence','reason':'model_did_not_provide_explanation'})
    counts=Counter(c.get('id') for c in candidates if isinstance(c,dict) and isinstance(c.get('id'),str))
    staged = []
    directions = set()
    failed_signatures = set(audit.get('failed_parameter_signatures') or [])
    for index,candidate in enumerate(candidates):
        try:
            audit["validation_stage"] = "schema"
            audit.update(failed_candidate_id=candidate.get('id') if isinstance(candidate,dict) else None,
                         failed_field=None,actual_value=None,expected_type=None,allowed_values=None,validation_issues=[])
            if not isinstance(candidate,dict) or candidate.get('id') not in labels or counts.get(candidate.get('id'))!=1:
                audit['failed_field']='id'
                raise ValueError('Candidate必须为对象且标签唯一、属于本轮允许标签')
            candidate = dict(candidate)  # Preserve the parsed Provider reply in the audit.
            signature = parameter_signature(base_config, candidate['config_diff']) if isinstance(candidate.get('config_diff'), dict) else None
            if signature in failed_signatures:
                raise ValueError('以前失败的参数组合不得重复')
            for field in ("hypothesis", "why", "risk", "expected_improvement", "target_bad_cases", "config_diff"):
                value = candidate.get(field)
                if field in ("hypothesis", "why", "risk", "expected_improvement"):
                    expected = "non-empty string"
                    valid = isinstance(value, str) and bool(value.strip())
                elif field == "target_bad_cases":
                    expected = "array of non-empty strings"
                    valid = isinstance(value, list) and bool(value) and all(isinstance(item, str) and item.strip() for item in value)
                else:
                    expected = "object"
                    valid = isinstance(value, dict)
                if not valid:
                    audit.update(failed_field=field, actual_value=value, expected_type=expected, allowed_values=None)
                    raise ValueError(f"Agent Candidate {candidate['id']} 缺少有效 {field}")
            unknown_targets = [value for value in candidate["target_bad_cases"] if value not in target_reference_map]
            if unknown_targets:
                audit.update(failed_field="target_bad_cases", actual_value=candidate["target_bad_cases"], expected_type="identifiers from current persisted evidence", allowed_values=sorted(target_reference_map))
                raise ValueError(f"Agent Candidate {candidate['id']} target_bad_cases 引用了不存在的当前证据：" + ", ".join(unknown_targets))
            canonical=[target_reference_map[r]['bad_case_id'] for r in candidate['target_bad_cases']]
            if len(canonical)!=len(set(canonical)):
                audit['failed_field']='target_bad_cases'
                raise ValueError('同一目标被重复引用（含题号与Case别名）')
            candidate['target_bad_cases'] = [display_ids.get(r,r) for r in candidate['target_bad_cases']]
            selected=[item for item in bad_cases if item['id'] in candidate['target_bad_cases'] or item['question_id'] in candidate['target_bad_cases']]
            roots={item['question_id']:item['diagnostic_view']['primary_root_cause'] for item in selected}
            candidate['target_root_causes']=roots
            candidate['root_cause']=next(iter(set(roots.values()))) if len(set(roots.values()))==1 else 'Mixed'
            candidate['root_cause_evidence']=candidate['target_bad_cases']
            candidate.setdefault('action_name',' + '.join(PARAMETER_ACTIONS.get(key,key) for key in candidate['config_diff']))
            if not isinstance(candidate['action_name'],str) or not candidate['action_name'].strip():
                raise ValueError('动作名称不能为空')
            if candidate["hypothesis"].strip() in {item.get("reasoning", {}).get("hypothesis", "").strip() for item in prior_candidates}:
                audit.update(failed_field="hypothesis", actual_value=candidate["hypothesis"], expected_type="new hypothesis", allowed_values=None)
                raise ValueError("下一轮必须提出新的 Hypothesis")
            diff = candidate["config_diff"]
            config = {**base_config, **diff}
            if config.get("hybrid_search") is False and "hybrid_alpha" not in diff:
                config.pop("hybrid_alpha", None)
            audit["validation_stage"] = "search_space"
            check = validate_candidate_config(config, prior_configs=prior, completed_evals=completed)
            if not check["valid"]:
                audit["validation_issues"] = check["issues"]
                if check["issues"]:
                    issue = check["issues"][0]
                    audit.update(failed_field=issue["field"], actual_value=issue["actual"], expected_type=issue["expected_type"], allowed_values=issue["allowed_values"])
                raise ValueError("Agent Candidate Config 不符合冻结 Search Space：" + "; ".join(check["errors"]))
            audit['validation_stage']='intervention'
            target_cases={reference:item['result'] for item in bad_cases for reference in (item['id'],item['question_id'])}
            validate_intervention(candidate,target_cases,base_config)
            direction = tuple(sorted(diff))
            if direction in directions:
                raise ValueError('本轮方案方向重复：不能只给同一组参数换数值')
            target_ids = [item['diagnostic_view'].get('display_question_id') or item['question_id'] for item in selected]
            target_mentions = target_ids + [item['question_id'] for item in selected]
            focus = '速度优先' if 'generation_thinking' in diff and len(diff) == 1 else '回答优先' if set(diff) <= {'prompt_strategy','generation_thinking'} else '检索优先'
            candidate.setdefault('strategy_name', f'「{candidate["action_name"]}」（{focus}）')
            candidate.setdefault('core_idea', candidate['hypothesis'])
            candidate.setdefault('adjustments', [{'parameter':key, 'baseline_value':base_config.get(key), 'candidate_value':value,
                'expected_impact':candidate['expected_improvement'] if any(q in candidate['expected_improvement'] for q in target_mentions) else candidate['expected_improvement']+'；目标题号：'+'、'.join(target_ids)} for key,value in diff.items()])
            candidate.setdefault('risks', [{'question_ids':[], 'metric':None, 'reason':candidate['risk']}])
            if not isinstance(candidate['strategy_name'], str) or not re.fullmatch(r'「.+」（.+优先）', candidate['strategy_name']):
                raise ValueError('策略名必须为「动作名」（xx优先）')
            if not isinstance(candidate['core_idea'],str) or not candidate['core_idea'].strip():
                raise ValueError('缺少核心思路')
            adjustments = candidate['adjustments']
            if (not isinstance(adjustments,list) or len(adjustments)!=len(diff)
                    or {item.get('parameter') for item in adjustments if isinstance(item,dict)}!=set(diff)
                    or any(not isinstance(item,dict) or item.get('baseline_value')!=base_config.get(item.get('parameter'))
                           or item.get('candidate_value')!=diff.get(item.get('parameter')) or not isinstance(item.get('expected_impact'),str)
                           or not any(q in item['expected_impact'] for q in target_mentions) for item in adjustments)):
                raise ValueError('调整项必须对应实际参数与基线值，预期影响须点名目标题号')
            risks = candidate['risks']
            if 'risks' in candidates[index] and isinstance(risks,list) and any(not isinstance(r,dict) or not (r.get('question_ids') or isinstance(r.get('metric'),str) and r['metric'].strip()) for r in risks):
                raise ValueError('风险须点名可能弄坏的题号或指标')
            if not isinstance(risks,list) or not risks or any(not isinstance(r,dict) or not isinstance(r.get('question_ids'),list) or not isinstance(r.get('reason'),str) or not r['reason'].strip() for r in risks):
                raise ValueError('风险必须给出可能影响的题号或指标及原因')
            candidate['parameter_signature'] = signature
            candidate['intervention_direction']=candidate.get('intervention_direction') or next((name for name,(keys,_) in INTERVENTIONS.items() if name!='stage_performance' and set(diff)<=keys),'combined')
            prior.append(config)
            directions.add(direction)
            staged.append((candidate, config))
        except (ValueError,TypeError,KeyError) as error:
            # Validation refusals have not been tried in Sandbox and are not failed effects.
            audit['rejected_candidates'].append({'index':index,'id':candidate.get('id') if isinstance(candidate,dict) else None,
                'stage':audit['validation_stage'],'field':audit.get('failed_field'),'reason':str(error),
                'validation_issues':audit.get('validation_issues',[]),
                'actual_value':audit.get('actual_value'),'expected_type':audit.get('expected_type'),'allowed_values':audit.get('allowed_values')})
    if len(staged)!=3:
        raise ValueError('整轮ABC校验拒绝：'+'；'.join(r['reason'] for r in audit['rejected_candidates']))
    audit["validation_stage"] = "completed"
    audit['failed_parameter_signatures'] = sorted(failed_signatures)
    audit["failed_candidate_id"] = None
    batch = []
    for candidate, config in staged:
        batch.append((f"R{round_number}-{candidate['id']}", config, {
            **{key:candidate[key] for key in ('direction','strategy_name','core_idea','adjustments','risks','parameter_signature')},
            "intervention_direction":candidate['intervention_direction'], "supporting_directions":candidate.get('supporting_directions',[]), "action_name":candidate["action_name"], "intervention_contract_version":"agent-closure-4", "experiment_kind":candidate.get("experiment_kind","confirmed"), "falsification":candidate.get("falsification"), "parameter_dependencies":candidate.get('parameter_dependencies',[]), "evidence_assertions":candidate.get('evidence_assertions',[]), "performance_stage":candidate.get('performance_stage'),
            "target_root_causes": candidate.get("target_root_causes"), "provenance": candidate.get("provenance"), "target_group": candidate.get("target_group") if isinstance(candidate.get("target_group"),str) else None, "root_cause": candidate["root_cause"], "root_cause_evidence": candidate["root_cause_evidence"], "expected_improvement": candidate["expected_improvement"], "target_diagnosis": [strategy_case(item) for item in bad_cases if item["id"] in candidate["target_bad_cases"] or item["question_id"] in candidate["target_bad_cases"]], "root_cause_cluster": result.get("root_cause_cluster"), "observed_evidence": candidate["target_bad_cases"], "hypothesis": candidate["hypothesis"], "proposal": candidate["why"], "risk": candidate["risk"],
            "changed_parameters": {key: value for key, value in config.items() if value != base_config.get(key)}, "source_trigger_id": trigger_id, "monitoring_target_event_ids": monitoring_target_event_ids, "round": round_number, "candidate_label": candidate["id"],
        }))
    audit.update(generated_candidate_count=len(batch),returned_candidate_count=len(candidates),requested_candidate_count=len(labels),
                 response_status='partial' if batch and audit['rejected_candidates'] else 'accepted' if batch else 'rejected' if candidates else 'empty')
    if candidates and not batch:
        first=audit['rejected_candidates'][0]
        audit.update(validation_stage=first['stage'],failed_candidate_id=first['id'],failed_field=first['field'],actual_value=first['actual_value'],
                     expected_type=first['expected_type'],allowed_values=first['allowed_values'],validation_issues=first['validation_issues'])
        raise ValueError('没有合法Candidate：'+'；'.join(r['reason'] for r in audit['rejected_candidates']))
    return result,batch


class OptimizationAgent:
    def __init__(self, store, provider):
        self.store = store
        self.provider = provider

    def _checkpoint(self, experiment_id, generation_token, updates):
        with self.store.connection() as connection:
            connection.execute('BEGIN IMMEDIATE')
            row=connection.execute('SELECT status,result_json FROM experiments WHERE id=?',(experiment_id,)).fetchone()
            context=json.loads(row['result_json'])
            if row['status']!='generating' or context.get('agent_generation',{}).get('token')!=generation_token:
                raise ValueError('Optimization Context 已变化，不能保存生成断点')
            connection.execute('UPDATE experiments SET result_json=? WHERE id=?',
                (json.dumps({**context,**updates},ensure_ascii=False,allow_nan=False),experiment_id))

    @contextmanager
    def _request_checkpoint(self, experiment_id, generation_token, previous, request_hash):
        from .evaluation_stage import _request_checkpoint
        checkpoint=previous.get('agent_request_checkpoint',{'attempts':[]}) if previous.get('agent_request_sha256')==request_hash else {'attempts':[]}
        def save(*_args,**_kwargs):
            self._checkpoint(experiment_id,generation_token,{'agent_request_checkpoint':checkpoint,'agent_request_sha256':request_hash})
        token=_request_checkpoint.set((checkpoint,'agent',experiment_id,save,lambda:None))
        try:yield checkpoint
        finally:_request_checkpoint.reset(token)

    @provider_task('agent')
    def generate(self, baseline_run_id: str, trigger_id: str | None = None, experiment_id: str | None = None):
        # Check identity before budget reads; the short claim serializes duplicate starts.
        self.store.require_current_baseline(baseline_run_id)
        # Real model requests must share the current foundation before claiming work.
        settings = getattr(self.provider, 'settings', None)
        if isinstance(getattr(settings, 'model', None), str):
            from types import SimpleNamespace
            from .ai_service import generation_contract
            from .evaluation import EvaluationRunner
            runtime = SimpleNamespace(generation_contract=generation_contract(), model=settings.model)
            EvaluationRunner(self.store, runtime)._require_generation_contract(self.store.evaluation_run(baseline_run_id)['judge'])
        baseline = self.store.evaluation_run(baseline_run_id)
        audited_cases = baseline_bad_case_rows(self.store, baseline)
        audited_cases = [{**item, 'category':item['diagnostic_view']['primary_root_cause']} for item in audited_cases]
        from .evaluation_contract import business_verdict
        failures = [item for item in audited_cases if business_verdict(item['result'])=='FAIL' or (item['result'].get('evaluation_outcome') or {}).get('contract_version')!='business-vnext-1' and item['result'].get('passed') is False]
        bad_cases = [item for item in failures if is_optimization_target(item)]
        diagnostic_tasks=[]
        for item in bad_cases:
            view=item['diagnostic_view'];plan=view.get('experiment_plan',{})
            ready=view['target_eligible'] and view.get('diagnosis_complete',True)
            diagnostic_tasks.append({'question_id':item['question_id'],'case_id':item['id'],
                'status':'ready_for_experiment' if ready else plan.get('status','capability_gap'),
                'next_action':'sandbox_full_snapshot' if ready else plan.get('next_action','repair_sources_or_trace'),
                'experiment_plan':plan,'gaps':view.get('diagnostic_gaps',[]),'blockers':plan.get('blockers',[])})
        trigger = self.store.optimization_trigger(trigger_id) if trigger_id else None
        existing_id = experiment_id or (trigger or {}).get("optimization_run_id") or self.store.current_baseline_identity()["current_experiment_id"]
        existing = self.store.experiment(existing_id) if existing_id else None
        confirmed_context = (existing or {}).get("result", {})
        trigger = trigger or self.store.optimization_trigger(confirmed_context.get("trigger_id"))
        event = None
        if existing and existing["baseline_run_id"] == baseline_run_id and trigger and trigger["status"] == "human_confirmed" and trigger["optimization_run_id"] == existing_id:
            event = next((item for item in self.store.monitoring_events() if item["id"] == trigger["event_id"] and item["bad_case"] and item["determinable"]), None)
        baseline = self.store.evaluation_run(baseline_run_id)
        base_config = {**DEFAULT_PIPELINE_CONFIG, **baseline["config"]}
        base_config.pop("run_target", None)
        base_config.pop("knowledge_identity", None)
        base_config = {k:v for k,v in base_config.items() if k in ALLOWED_SEARCH_SPACE}
        if existing and existing.get('evaluation_budget',{}).get('used',0) > MAX_EVALS - 4:
            raise ValueError('剩余试跑预算不足完整ABC三套，并须保留D预算')
        experiment_id, prior_candidates, round_number, completed, generation_token = self.store.claim_agent_generation(baseline_run_id, trigger_id, existing_id)
        if not bad_cases:
            reason='暂无足够依据生成合格优化假设：没有具备实际证据与Trace的可验证Baseline目标；Monitoring事件须先补齐同等证据'
            self.store.save_agent_round(experiment_id, [], {'generation_status':'insufficient_evidence','insufficient_evidence':reason,'generated_candidate_count':0,'round':round_number,'provider_called':False,'all_bad_case_audit':[{k:v for k,v in row.items() if k!='result_json'} for row in audited_cases]}, generation_token=generation_token)
            return self.store.experiment(experiment_id)
        failed_questions={row['question_id'] for row in bad_cases}
        verified=[c for c in prior_candidates if c['status']=='evaluated' and c['result'].get('qualification',{}).get('qualified')]
        best=max(verified,key=lambda c:len(set(c['result'].get('all_fixed_question_ids',[])) & failed_questions),default=None)
        fixed=failed_questions & set(best['result'].get('all_fixed_question_ids',[])) if best else set()
        processing_progress={'baseline_failed_question_ids':sorted(failed_questions),'verified_configuration_id':best['id'] if best else None,
            'fixed_question_ids':sorted(fixed),'remaining_question_ids':sorted(failed_questions-fixed),'status':'unfinished' if failed_questions-fixed else 'verified_complete'}
        context = self.store.experiment(experiment_id)["result"]
        trigger_id = trigger_id or context.get("trigger_id")
        monitoring_context = {"trigger": self.store.optimization_trigger(trigger_id), "event": event or context.get("monitoring_event"), "confirmed_baseline_id": context.get("baseline_id"), "golden_id": context.get("golden_id"), "corpus_fingerprint": context.get("corpus_fingerprint")} if trigger_id else None
        monitoring_target_event_ids = [event["id"]] if event else []
        target_reference_map = {}
        for item in bad_cases:
            reference = {"source": "baseline_bad_case", "baseline_id": baseline_run_id, "bad_case_id": item["id"], "question_id": item["question_id"], "primary_root_cause": item["diagnostic_view"]["primary_root_cause"], "analysis_category": item["diagnostic_view"]["analysis_category"], "root_cause_evidence": item["diagnostic_view"]["evidence_checks"], "diagnostic_view":strategy_case(item)["diagnostic_view"]}
            target_reference_map[item["id"]] = reference
            target_reference_map[item["question_id"]] = reference
        if event:
            target_reference_map[event["id"]] = {"source": "monitoring_event", "event_id": event["id"], "trigger_id": trigger_id}
        evaluation_budget = {"used": completed, "max": MAX_EVALS, "reserved_for_d": 1,
                             "remaining":MAX_EVALS-completed,"remaining_for_abc":max(0,MAX_EVALS-1-completed)}
        gate_results = baseline["result"].get("gates")
        persisted_gates = (gate_results or {}).get("gates")
        failed_gates = [gate for gate in persisted_gates if gate.get("passed") is False] if isinstance(persisted_gates, list) else None
        labels = ['A', 'B', 'C']
        audit = {"optimization_run_id": experiment_id, "baseline_id": baseline_run_id, "timestamp": datetime.now(timezone.utc).isoformat(), "provider_raw_text": None, "parsed_json": None, "parsed_candidates": None, "validation_stage": "provider", "failed_candidate_id": None, "failed_field": None, "actual_value": None, "expected_type": None, "allowed_values": None, "validation_issues": [], "diagnostic_tasks":diagnostic_tasks, "processing_progress":processing_progress, "all_bad_case_audit": [{k:v for k,v in row.items() if k!='result_json'} for row in audited_cases], "root_cause_counts": dict(Counter(item['diagnostic_view']['primary_root_cause'] for item in bad_cases)), "source_bad_case_ids": [item["id"] for item in bad_cases], "monitoring_context": monitoring_context, "monitoring_target_event_ids": monitoring_target_event_ids, "target_reference_map": target_reference_map, "evaluation_budget": evaluation_budget, "baseline_gate_results": gate_results, "failed_gates": failed_gates}
        failed_signatures = set(context.get('failed_parameter_signatures') or [])
        failed_signatures.update(parameter_signature(base_config,{key:value for key,value in c['config'].items() if value!=base_config.get(key)})
                                 for c in prior_candidates if c['status'] in {'failed','evaluated'} and not c.get('result',{}).get('qualification',{}).get('qualified'))
        audit['failed_parameter_signatures'] = sorted(failed_signatures)
        system,prompt=build_agent_prompt(failures,base_config,prior_candidates,failed_gates,labels,
            baseline_gates=persisted_gates,evaluation_budget=evaluation_budget,failed_parameter_signatures=audit['failed_parameter_signatures'])
        audit['baseline_diagnosis_summary'] = prompt['baseline_diagnosis_summary']
        audit['next_action'] = prompt['next_action']
        try:
            stages = []
            recovered_usage=[]
            with collect_usage() as usage, measure(stages, 'optimization_agent'):
                try:
                    user=json.dumps(prompt,ensure_ascii=False)
                    audit['validation_stage']='request_validation'
                    if callable(getattr(self.provider,'request_summary',None)):
                        audit['request_summary']=self.provider.request_summary(system,user,json_mode=True)
                    audit['validation_stage']='provider'
                    previous = confirmed_context
                    request_hash = audit.get('request_summary', {}).get('request_sha256')
                    if (request_hash and previous.get('validation_stage') == 'persistence'
                            and previous.get('baseline_id') == baseline_run_id
                            and previous.get('request_summary', {}).get('request_sha256') == request_hash
                            and isinstance(previous.get('provider_raw_text'), str)
                            and any(item.get('status') == 'ok' for item in previous.get('token_usage', []))):
                        content = previous['provider_raw_text']
                        audit['response_reuse'] = {'request_sha256': request_hash, 'source_timestamp': previous['timestamp'], 'new_provider_call': False}
                    else:
                        with self._request_checkpoint(experiment_id,generation_token,previous,request_hash) as checkpoint:
                            content=self.provider.complete(system,user,json_mode=True)
                            if not usage:
                                from .evaluation_stage import checkpoint_usage
                                recovered_usage=checkpoint_usage(checkpoint)
                                if recovered_usage:audit['rpc_response_reuse']={'new_provider_call':False}
                finally:
                    if audit.get('response_reuse'):
                        audit.update({k:previous.get(k) for k in ('token_usage','cost_estimation','estimated_cost')})
                        audit.update(stages=previous.get('stages',[]),revalidation_stages=stages,new_provider_calls=0)
                    else:
                        events=usage or recovered_usage
                        audit.update(token_usage=events, stages=stages, **cost_fields(getattr(getattr(self.provider, 'settings', None), 'model', None), events))
            audit["provider_raw_text"] = content
            # Save the paid response before parsing/validation; restart reuses it.
            self._checkpoint(experiment_id,generation_token,{**audit,'validation_stage':'persistence'})
            for attempt in range(2):
                try:
                    result,batch=prepare_response(content,base_config,bad_cases,prior_candidates,completed,round_number,labels,trigger_id,monitoring_target_event_ids,audit)
                    break
                except (ValueError,TypeError,KeyError) as validation_error:
                    if attempt:raise
                    audit['format_retry']={'reason':str(validation_error),'first_raw_text':content,'sandbox_budget_used':0}
                    retry_prompt={**prompt,'validation_rejection':{'reason':str(validation_error),'rejected_response':content,'instruction':'重出完整ABC一次；格式拒绝未占试跑预算'}}
                    with collect_usage() as retry_usage:
                        content=self.provider.complete(system,json.dumps(retry_prompt,ensure_ascii=False),json_mode=True)
                    audit['token_usage']=[*audit.get('token_usage',[]),*retry_usage]
                    audit.update(cost_fields(getattr(getattr(self.provider,'settings',None),'model',None),audit['token_usage']))
                    audit['provider_raw_text']=content
                    self._checkpoint(experiment_id,generation_token,{**audit,'validation_stage':'persistence'})
            audit["validation_stage"] = "persistence"
            self.store.save_agent_round(experiment_id, batch, {**result, **audit, "generation_status":"partial" if audit["rejected_candidates"] else "completed" if batch else "no_candidates", "requested_candidate_count":len(labels), "generated_candidate_count":len(batch), "validation_stage": "completed", "round": round_number, "evaluation_budget": evaluation_budget}, generation_token=generation_token)
            return self.store.experiment(experiment_id)
        except Exception as error:
            if isinstance(error,ProviderRequestError):audit['validation_stage']='request_validation'
            audit['generation_status']='failed'
            audit['provider_error']=provider_error_details(error,audit['validation_stage'])
            message=f"{error}；失败阶段：{audit['validation_stage']}；可重试：{'是' if audit['provider_error']['retryable'] else '否'}"
            audit["validation_error"] = message
            self.store.save_agent_trace(experiment_id, "failed", audit, message, generation_token=generation_token)
            raise ValueError(message) from error
