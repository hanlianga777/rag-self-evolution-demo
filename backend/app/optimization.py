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
from .agent_inputs import prepare_baseline_rows, retrieval_facts, is_optimization_target, is_unstable_case, baseline_bad_case_rows, new_failure_ids
from .paid_run import provider_task
from .paid_schedule import wait_for_off_peak, clear_run_now
from .telemetry import collect_usage, measure, cost_fields
from .policy import ALLOWED_SEARCH_SPACE, DEFAULT_PIPELINE_CONFIG, MAX_EVALS, canonicalize_config, search_space_contract, validate_candidate_config, is_downgrade_with_retrieval


INTERVENTIONS = {
    'query_expansion': ({'query_rewrite','multi_query','hyde'}, {'recall_missing'}),
    'candidate_recall': ({'candidate_k','hybrid_search','hybrid_alpha'}, {'recall_missing'}),
    'context_selection': ({'top_k','rerank','min_score','retrieval_max_tokens'}, {'ranking_omission','retrieval_noise'}),
    'grounded_generation': ({'generation_thinking'}, {'final_sufficient','confirmed_claim','safety_failure'}),
    'stage_performance': (set(search_space_contract()), {'measured_latency'}),
}


DIRECTION_PARAMETERS = {
    'Query Rewrite':['query_rewrite'], 'HyDE':['hyde'], 'Multi-Query':['multi_query'],
    '候选数':['candidate_k'], 'Hybrid Search':['hybrid_search','hybrid_alpha'],
    'Rerank':['rerank'], '保留条数':['top_k'], '最低分数线':['min_score'],
    '上下文窗口':['retrieval_max_tokens'], 'Thinking 档位':['generation_thinking'], '降低 Thinking 档位':['generation_thinking'],
    '关闭耗时环节':['hyde','multi_query','query_rewrite','rerank'], '调整检索参数':['candidate_k','top_k'],
}
PRIORITY_PARAMETERS = {row['label']:list(dict.fromkeys(key for direction in row['directions'] for key in DIRECTION_PARAMETERS.get(direction, []))) for row in DIAGNOSTIC_CATEGORIES}

PARAMETER_ACTIONS = {
    'candidate_k':'调整候选池','top_k':'调整 Top-K','min_score':'调整最低分数线',
    'hybrid_search':'调整 Hybrid Search','hybrid_alpha':'调整混合比例','rerank':'调整 Rerank',
    'query_rewrite':'调整 Query Rewrite','multi_query':'调整 Multi-Query','hyde':'调整 HyDE',
    'generation_thinking':'调整 Thinking 档位',
    'retrieval_max_tokens':'调整检索长度上限',
}


THINKING_LEVELS = ('off', 'low', 'high', 'max')
EFFICIENCY_PARAMETERS = {'hyde','multi_query','candidate_k','top_k','min_score','rerank','hybrid_alpha'}


class ProposalValidationExhausted(ValueError):
    """Drafts exhausted validation retries without running a Sandbox."""


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
            diff=candidate.get('reasoning',{}).get('changed_parameters_vs_baseline',candidate.get('reasoning',{}).get('changed_parameters',{}))
            changes.append({'candidate_id':candidate.get('id'),'config_diff':diff,'harmed_gates':harmed,
                            'new_failure_question_ids':new_failure_ids(candidate.get('result',{})),
                            'attribution':'多个改动混在一起，无法判断是哪个参数造成的' if len(diff)>1 else '本方案只改动一个参数' if diff else '未知'})
    return changes


def efficiency_optimization(prior_candidates, completed):
    """Legacy name kept for callers; see downgrade_required (规则总表五.4)."""
    return False


def downgrade_required(prior_candidates, baseline, round_number):
    """规则总表五.4：截至第3轮C生成时，之前所有方案都没出现"降档+检索补强"，本轮须补上（C兜底）。"""
    if round_number != 3 or baseline.get('generation_thinking', 'max') == 'off':
        return False
    return not any(is_downgrade_with_retrieval({**baseline, **(c.get('config') or {})}, baseline)
                   for c in prior_candidates if c.get('reasoning', {}).get('candidate_label') in {'A', 'B', 'C'})


def inherited_base(candidate, baseline, prior_candidates, round_number, round_policy):
    """Validate inheritance against one saved, qualified earlier ABC in this experiment."""
    inherited = candidate.get('inherited_parameters', {})
    source_id = candidate.get('inherited_from')
    if not isinstance(inherited, dict):
        raise ValueError('inherited_parameters必须为对象')
    if not inherited and source_id is None:
        return baseline
    if (round_policy or {}).get('mode') != 'full_rounds' or round_number < 2:
        raise ValueError('继承参数只允许full_rounds实验第2轮起使用')
    source = next((c for c in prior_candidates if c['id'] == source_id), None)
    if (not source or source['status'] != 'evaluated'
            or source.get('result', {}).get('qualification', {}).get('qualified') is not True
            or source.get('reasoning', {}).get('candidate_label') not in {'A','B','C'}
            or source['reasoning'].get('round', round_number) >= round_number):
        raise ValueError('继承来源必须是本实验前几轮已评测合格的ABC方案')
    changes = source['reasoning'].get('changed_parameters_vs_baseline', source['reasoning'].get('changed_parameters', {}))
    if not inherited or any(
            key not in changes or type(value) is not type(changes[key]) or value != changes[key]
            or type(value) is not type(source['config'].get(key)) or value != source['config'].get(key)
            for key, value in inherited.items()):
        raise ValueError('继承参数必须是来源完整改动的子集且值完全一致')
    return {**baseline, **inherited}


def parse_agent_json(content, audit):
    """Only append unmatched closing brackets outside JSON strings; never edit content."""
    audit.pop('syntax_repair', None)
    options = dict(object_pairs_hook=unique_keys, parse_constant=reject_constant, parse_float=finite_float)
    try:
        return json.loads(content, **options)
    except json.JSONDecodeError:
        stack = []
        quoted = escaped = False
        for char in content:
            if quoted:
                if escaped: escaped = False
                elif char == '\\': escaped = True
                elif char == '"': quoted = False
            elif char == '"': quoted = True
            elif char in '{[': stack.append('}' if char == '{' else ']')
            elif char in '}]':
                if not stack or stack.pop() != char:
                    raise ValueError('Agent JSON括号不匹配')
        if quoted or not stack:
            raise
        appended = ''.join(reversed(stack))
        result = json.loads(content + appended, **options)
        audit['syntax_repair'] = {'appended':appended, 'original_length':len(content)}
        return result


def validate_round_contract(candidates, baseline, prior_candidates, baseline_gates=None, *, completed=0, labels=None, round_number=None):
    labels = labels if labels is not None else list('ABC')
    if len(candidates)!=len(labels) or any(not isinstance(c,dict) for c in candidates) or {c.get('id') for c in candidates}!=set(labels):
        raise ValueError('每轮必须恰好提供A/B/C三套方案' if labels == list('ABC') else '每轮必须恰好提供'+ '/'.join(labels) +'方案')
    used=set()
    downgrades = {}
    for candidate in candidates:
        diff=candidate.get('config_diff')
        if not isinstance(diff,dict) or not diff:raise ValueError('Config Diff必须包含实际参数改动')
        if len(diff) > 2:raise ValueError('每个方案相对底座最多改两个参数（规则总表五.1）')
        if used & set(diff):raise ValueError('同轮方案不得共用参数：'+','.join(sorted(used & set(diff))))
        used.update(diff)
        current=baseline.get('generation_thinking','max')
        proposed=diff.get('generation_thinking',current)
        if current not in THINKING_LEVELS or proposed not in THINKING_LEVELS:raise ValueError('未知Thinking档位')
        effective = {**baseline, **(candidate.get('inherited_parameters') or {}), **diff}
        downgrades[candidate.get('id')] = is_downgrade_with_retrieval(effective, baseline)
        for previous in gate_harming_changes(prior_candidates,baseline_gates):
            harmed=previous['config_diff']
            if harmed and diff == harmed:
                raise ValueError('不得照搬已证明伤害 Hard Gate 的相同改动')
    if round_number is not None and downgrade_required(prior_candidates, baseline, round_number) and not any(downgrades.values()):
        raise ValueError('降档补位（规则总表五.4）：之前所有方案都没有出现"Thinking从Max降档+至少一个检索参数改动"，第3轮C必须是这种方案')


def validate_prior_round_review(result, prior_candidates):
    review = result.get('prior_round_review')
    if not isinstance(review, dict) or not isinstance(review.get('plans'), list) or not isinstance(review.get('baseline_remaining_assessment'), str) or not review['baseline_remaining_assessment'].strip():
        raise ValueError('缺少前几轮复盘 prior_round_review：plans、baseline_remaining_assessment 必填')
    expected = {c['id'] for c in prior_candidates if c['status'] == 'evaluated'}
    plans = review['plans']
    if len(plans) != len(expected) or {p.get('candidate_id') for p in plans if isinstance(p, dict)} != expected:
        raise ValueError('前几轮复盘必须逐一覆盖本实验所有已完成历史方案')
    for plan in plans:
        changes = plan.get('changes')
        if (not (isinstance(changes, str) and changes.strip() or isinstance(changes, dict) and changes)
                or any(not isinstance(plan.get(k), str) or not plan[k].strip() for k in ('evidence_reason', 'conclusion'))
                or any(not isinstance(plan.get(k), list) for k in ('fixed_question_ids', 'new_failure_question_ids'))):
            raise ValueError('前几轮复盘每套须写改动、修好/弄坏题号、证据原因、结论')
        previous = next(c for c in prior_candidates if c['id'] == plan['candidate_id'])
        if set(plan['fixed_question_ids']) != set(previous['result'].get('all_fixed_question_ids', [])) or set(plan['new_failure_question_ids']) != set(new_failure_ids(previous['result'])):
            raise ValueError('前几轮复盘修好/弄坏题号须与保存结果一致，使用正式 question_id')
    conclusions = review.get('conclusions')
    if not isinstance(conclusions, list) or not conclusions or any(not isinstance(c, dict) or not isinstance(c.get('id'), str) or not c['id'].strip() or not isinstance(c.get('conclusion'), str) or not c['conclusion'].strip() for c in conclusions):
        raise ValueError('前几轮复盘须提供可引用的 conclusions（id、conclusion）')
    ids = {c['id'] for c in conclusions}
    if len(ids) != len(conclusions):
        raise ValueError('复盘结论编号不得重复')
    for candidate in result['candidates']:
        refs = candidate.get('review_conclusion_ids') if isinstance(candidate, dict) else None
        if not isinstance(refs, list) or not refs or any(not isinstance(r, str) or r not in ids for r in refs):
            raise ValueError('每套方案必须通过 review_conclusion_ids 引用前几轮复盘结论')
    return review


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
        raise ValueError('方案必须有目标 Bad Case')
    for reference in references:
        if reference not in targets:raise ValueError('目标不是本次运行保存的 Bad Case')
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
        labels={'positive_correctness':'正向题（Positive）正确性','positive_faithfulness':'正向题（Positive）忠实性','positive_completeness':'正向题（Positive）完整性','ablation_correctness':'消融题（Ablation）正确性','ablation_faithfulness':'消融题（Ablation）忠实性','ablation_completeness':'消融题（Ablation）完整性','safe_rejection_rate':'安全拒答率','safety_critical_accuracy':'安全关键准确率','prompt_injection_resistance':'提示注入抵抗','latency_p50_seconds':'回答耗时中位数','latency_p99_seconds':'回答耗时第99百分位'}
        failed = gate.get('passed') is False or gate.get('status') == 'FAIL'
        unstable_only = failed and bool(unstable) and not targets and not pending
        unstable_note = 'Baseline 该 Hard Gate 未过由不稳定题造成（复核多数判对），方案仍须通过该 Hard Gate' if unstable_only else ''
        pending_note = '复核技术异常或未完成，Hard Gate 归因未知；方案仍须通过该 Hard Gate' if failed and pending else ''
        summary.append({'dimension': metric, 'dimension_label':labels.get(metric,'维度记录缺失'), 'baseline_value': actual, 'target_value': target,
                        'operator': gate.get('operator'), 'gap': max(0, -margin),
                        'status': '未通过' if failed else '接近 Hard Gate',
                        'root_causes': [{'diagnosis_category': key, 'question_ids': ids,
                                         'priority': 1 if failed and any(q in targets for q in ids) else next((c['priority'] for c in DIAGNOSTIC_CATEGORIES if c['label']==key), None),
                                         'priority_note': '导致 Hard Gate 未过：'+labels.get(metric,'维度记录缺失') if failed and any(q in targets for q in ids) else unstable_note} for key, ids in groups.items()],
                        'target_question_ids': targets,
                        'root_cause_note': pending_note or unstable_note or ('整轮耗时问题，需结合已保存耗时拆解' if str(metric).startswith('latency_') else None if groups else '记录缺失：没有该维度对应的 Bad Case 诊断')})
    for item in summary:
        if item.get('root_cause_note') and any(word in item['root_cause_note'] for word in ('复核','不稳定')):item['root_cause_note']='记录不足，Hard Gate 归因未知'
        for cause in item['root_causes']:
            if '不稳定' in (cause.get('priority_note') or ''):cause['priority_note']=''
    return summary


def optimization_priorities(bad_cases, gates):
    summary = baseline_diagnosis_summary(bad_cases, gates)
    counts = Counter((row.get('diagnostic_view') or diagnostic_view(row['result']))['diagnosis_category'] for row in bad_cases if is_optimization_target(row))
    priorities = []
    for definition in DIAGNOSTIC_CATEGORIES:
        label = definition['label']
        if label == '性能问题':
            failed = [g for g in gates or [] if str(g.get('metric', '')).startswith('latency_')
                      and (g.get('passed') is False or g.get('status') == 'FAIL')]
            if failed:
                priorities.append({**definition, 'count': counts[label], 'priority': 1,
                                   'priority_note': '回答耗时 Hard Gate 未过；整轮性能问题不增加业务 Bad Case 数'})
                continue
        if not counts[label]:continue
        causes = [cause for item in summary if item['status']=='未通过' for cause in item['root_causes'] if cause['diagnosis_category']==label and cause['priority']==1]
        priorities.append({**definition, 'count':counts[label], 'priority':1 if causes else definition['priority'] or 3,
                           'priority_note':'；'.join(dict.fromkeys(cause['priority_note'] for cause in causes))})
    return sorted(priorities, key=lambda item:item['priority'])


def performance_facts(result, cases):
    """Use saved generation latency/usage only; absent measurements stay unknown."""
    metrics=result.get('metrics',{})
    slowest=[]
    stage_totals=Counter()
    measured_total=0
    for case in cases:
        measured=case.get('programmatic_metrics') or {}
        latency=measured.get('latency_ms')
        if type(latency) not in (int,float):continue
        measured_total += latency
        for stage in measured.get('stages') or []:
            if isinstance(stage,dict) and not stage.get('parent') and type(stage.get('duration_ms')) in (int,float):
                stage_totals[stage.get('stage_name','未知')] += stage['duration_ms']
        usage=measured.get('token_usage') or {}
        generation=(usage.get('generation') or {}) if isinstance(usage,dict) else {}
        reasoning=generation.get('reasoning_tokens',(generation.get('completion_tokens_details') or {}).get('reasoning_tokens'))
        slowest.append({'question_id':case.get('question_id'),'display_question_id':case.get('display_question_id') or case.get('question_id'),
                        'latency_seconds':latency/1000,'reasoning_tokens':reasoning})
    return {key:metrics.get(key,result.get(key)) for key in ('latency_p50_seconds','latency_p99_seconds')} | {
        'stage_shares':[{'stage':name,'duration_ms':duration,'share_of_answer_latency':duration/measured_total if measured_total else None} for name,duration in stage_totals.items()],
        'timing_note':'父子阶段嵌套，列出无parent的阶段；耗时为保存观测，不推断因果',
        'slowest_questions':sorted(slowest,key=lambda row:row['latency_seconds'],reverse=True)[:5]}


def enhancement_latency_deltas(baseline_config, baseline_result, candidates):
    """Observed bundle deltas; never claim causal attribution for mixed changes."""
    baseline = performance_facts(baseline_result, [])
    rows = []
    for parameter in ('hyde', 'query_rewrite', 'multi_query', 'top_k', 'candidate_k', 'generation_thinking'):
        samples = []
        for candidate in candidates:
            diff = candidate.get('reasoning', {}).get('changed_parameters_vs_baseline',candidate.get('reasoning', {}).get('changed_parameters', {}))
            if candidate.get('status') != 'evaluated' or parameter not in diff:
                continue
            performance = performance_facts(candidate.get('result', {}), [])
            deltas = {key:performance[key]-baseline[key] if type(performance[key]) in (int,float) and type(baseline[key]) in (int,float) else None
                      for key in ('latency_p50_seconds','latency_p99_seconds')}
            samples.append({'candidate_id':candidate['id'], 'value':diff[parameter], **deltas,
                'attribution':'无法单独归因' if len(diff)>1 else '单参数观测差值'})
        rows.append({'parameter':parameter, 'baseline_value':baseline_config.get(parameter), 'samples':samples,
            'mean_deltas':{key:sum(values)/len(values) if (values := [s[key] for s in samples if s[key] is not None]) else None
                           for key in ('latency_p50_seconds','latency_p99_seconds')},
            'interpretation':'相对Baseline的观测平均差值；多参数无法单独归因' if samples else '无本实验Sandbox观测'})
    return rows


def build_agent_prompt(bad_cases, base_config, prior_candidates, failed_gates, labels, *, baseline_gates=None, evaluation_budget=None, failed_parameter_signatures=None,
                       baseline_result=None, baseline_cases=None, candidate_cases=None, golden_questions=None, round_conclusions=None, round_policy=None, causal_evidence=False, round_number=None):
    """Build the exact Agent request without a Provider or persistence side effect."""
    system = ('你是RAG优化Agent。根据保存的错题诊断提出优化方案。'
              '一个方案=一个思路+必要的几个参数，可以跨环节联动。对照表表示优先尝试，不限制其他参数。'
              '先读程序生成的基线诊断摘要、速度事实、逐题变化及已被证明有害的改动清单gate_harming_changes。每轮恰好ABC三套，direction由你根据事实自行确定，不预设方向。同轮修改参数互斥。不得照搬gate_harming_changes。'
              '回答策略固定为Strict（分级回答），不是可调参数。generation_thinking可选off/low/high/max，Baseline是max；把Thinking从max降档并配合至少一个检索参数补强，用来验证较低档位能否同样修好Bad Case，是重要方向。每个方案相对其底座最多改两个参数。'
              'prior_sandbox_results里带no_effect的方案：50题回答与已跑结果完全相同，说明它改的参数在当前条件下没有改变交给模型的资料，不要再提出同类无效改动。'
              '每道错题的bad_cases[].issue_tags列出它同时存在的全部问题（检索层/生成层/安全边界/性能，可多个），diagnosis_category只是排优先级用的主原因；设计方案时要兼顾同一题的全部标签，不要只看主原因。'
              'enhancement_telemetry是增强生效遥测：每个增强手段（query_rewrite/multi_query/hyde/query_decompose）在几道题上开启、在几道题上带来了原问题查不到的新资料（effective_questions、new_final_hits）；生效为0说明这个手段在当前题上没起作用。'
              '有害改动仅禁止完整配置差异原样重复；叠加其他参数的组合只提示风险，不能推断单参数有害。'
              '先写前几轮复盘prior_round_review：summary首轮写无；plans逐一覆盖所有已完成历史方案，每条含candidate_id、changes、fixed_question_ids、new_failure_question_ids（均用保存的正式question_id）、evidence_reason（证据位置、速度、单/多参数归因）、conclusion（有效/有害/待验证及依据）；多参数必须说明无法单独确定并给most_likely_parameter和attribution_reason；baseline_remaining_assessment总结Baseline剩余错题；conclusions为[{id,conclusion}]。首轮plans为空，conclusions从Baseline事实归纳。每套方案必须用review_conclusion_ids引用其中结论。'
              '第二部分bad_case_summary：groups逐字采用bad_case_groups的layer/subtype/question_ids/count，focus指出最集中问题，conclusions为[{id,conclusion}]。第三部分每个Candidate必须有bad_case_conclusion_ids引用第二部分，predicted_fixed_question_ids写预计修好的正式题号数组；并写参数值、针对的问题、风险、依据。第四部分本轮结论将在试跑完成后另行请你根据保存结果撰写，previous_round_conclusions是下一轮必须吸收的经验。'
              '导致门槛未过的错题分类优先级升为1，按optimization_priorities及其原因安排优化。每个参数的用途与各可选值说明见allowed_parameter_values。'
              '每个参数的预期影响须点名预计修好的目标题号；风险须说明可能弄坏的题号或指标及原因；不得重复失败组合签名。'
              'target_bad_cases可用展示题号（例如Q04）、正式题目ID或Bad Case ID，必须引用当前bad_cases。'
              '合格标准：11项门槛全过；错题总数比Baseline至少少1道；新增错题最多1道且只能是普通题，严重题（安全关键、提示注入）不得新增错误。'
              '每轮三套跑完后统计：累计合格达到2个就停止出新方案、转入D；第3轮跑完仍只有1个合格也转入D；前三轮全不合格再出第4轮；全部试跑（含D）合计最多12次。'
              '设计方案时要留余量，让预期能修好的题数明显多于可能弄坏的题数，不要只追求刚好多修1道。'
              '只返回JSON，格式：{"prior_round_review":{"summary":"无","plans":[],"baseline_remaining_assessment":"整体判断","conclusions":[{"id":"L1","conclusion":"事实结论"}]},"bad_case_summary":{"groups":[],"focus":"最集中问题","conclusions":[{"id":"B1","conclusion":"统计事实"}]},"candidates":[{"id":"A","review_conclusion_ids":["L1"],"bad_case_conclusion_ids":["B1"],"predicted_fixed_question_ids":["正式题目ID"],"action_name":"中文动作短语",'
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
                     # 一题多问题：issue_tags 列出检索/生成/安全/性能全部标签；judge_failure 给未达标维度的分数与 Judge 理由（054 发现此前只在审计里、没进提示词）。
                     'issue_tags':[f"{tag['layer']}·{tag['label']}" for tag in view.get('issue_tags') or []],
                     'judge_failure':(row['result'].get('evaluation_outcome') or {}).get('reason'),
                     'retrieval_facts':row.get('retrieval_facts') or retrieval_facts(row['result'])})
    budget = {**{'used': 0, 'max': MAX_EVALS, 'reserved_for_d': 0}, **(evaluation_budget or {})}
    budget.update(remaining=max(0, budget['max'] - budget['used']), remaining_for_abc=max(0, budget['max'] - budget['used'] - budget['reserved_for_d']))
    baseline_by_id={case['question_id']:case for case in baseline_cases or []}
    questions = {q['id']:q for q in golden_questions or []}
    prior_results=[]
    for candidate in prior_candidates:
        result=candidate.get('result',{})
        saved={case['question_id']:case for case in (candidate_cases or {}).get(candidate['id'],[])}
        changes={}
        for label,key in (('fixed','all_fixed_question_ids'),('new_failures','new_failure_question_ids')):
            changes[label]=[]
            for question_id in (new_failure_ids(result) if label == 'new_failures' else result.get(key,[])):
                case=(baseline_by_id.get(question_id) or saved.get(question_id,{})) if label=='fixed' else (saved.get(question_id) or baseline_by_id.get(question_id,{}))
                changes[label].append({'question_id':question_id,'display_question_id':case.get('display_question_id') or question_id,
                    'diagnosis_category':case.get('diagnosis_category') or {'Retrieval':'检索层问题','Ranking':'检索层问题',
                        'Generation':'生成层问题','Safety':'安全边界问题','Performance':'性能问题'}.get(case.get('primary_root_cause'),'未知'),
                    'test_category':case.get('test_category'),'negative_subtype':case.get('negative_subtype'),
                    'retrieval_facts':retrieval_facts(case, questions.get(question_id), candidate.get('config'))})
        diff=candidate.get('reasoning',{}).get('changed_parameters_vs_baseline',candidate.get('reasoning',{}).get('changed_parameters',{}))
        prior_results.append({'id':candidate['id'],'action_name':candidate.get('reasoning',{}).get('action_name'),
            'hypothesis':candidate.get('reasoning',{}).get('hypothesis'),'configuration':candidate['config'],'status':candidate['status'],
            'result':{key:result.get(key) for key in ('qualification','bad_case_count','all_fixed_question_ids','regression','gates','no_effect','enhancement_telemetry')} | {'new_failure_question_ids':new_failure_ids(result)},
            'failed_questions':[{'question_id':q, 'display_question_id':case.get('display_question_id') or q,
                'judge_reason':case.get('judge_result',{}).get('reason'), 'retrieval_facts':retrieval_facts(case, questions.get(q), candidate.get('config'))}
                for q,case in saved.items() if case.get('passed') is False],
            'performance':performance_facts(result,list(saved.values())), 'question_changes':changes,
            'changed_parameters':candidate.get('reasoning',{}).get('changed_parameters',{}),
            **{key:candidate['reasoning'][key] for key in ('changed_parameters_vs_baseline','inherited_from','inherited_parameters') if key in candidate.get('reasoning',{})},
            'attribution':'多个改动混在一起，无法判断是哪个参数造成的' if len(diff)>1 else '本方案只改动一个参数' if diff else '未知'})
    prompt={
        'baseline_diagnosis_summary':baseline_diagnosis_summary(bad_cases, gates),
        'optimization_priorities':priorities,
        'evaluation_budget':budget, 'next_action':'analyze_and_propose' if budget['remaining_for_abc'] else 'review_for_d',
        'failed_parameter_signatures':failed_parameter_signatures or [],
        'goal':{'objective':'11项门槛全过；错题总数比Baseline至少少1道；新增错题最多1道且只能是普通题；安全关键题和提示注入题不得新增错误。',
                'failed_gates':failed_gates,'candidate_labels':labels,'baseline_configuration':base_config},
        'bad_cases':rows,
        'baseline_performance':performance_facts(baseline_result or {},baseline_cases or []),
        'priority_parameters':PRIORITY_PARAMETERS,
        'allowed_parameter_values':search_space_contract(),
        'round_contract':{'count':3,'downgrade_required':downgrade_required(prior_candidates, base_config, round_number),'parameters_disjoint':True,'max_changed_parameters':2},
        'previous_round_conclusions':round_conclusions or {},
        'gate_harming_changes':gate_harming_changes(prior_candidates,gates),
        'prior_sandbox_results':prior_results,
        'enhancement_latency_deltas':enhancement_latency_deltas(base_config, baseline_result or {}, prior_candidates),
    }
    from .agent_strategy import bad_case_groups
    latest = next((c for c in reversed(prior_candidates) if c['status']=='evaluated' and (candidate_cases or {}).get(c['id'])), None)
    prompt['bad_case_groups'] = bad_case_groups((candidate_cases or {})[latest['id']] if latest else [row['result'] | {'question_id':row['question_id']} for row in bad_cases])
    prompt['bad_case_scope'] = latest['id'] if latest else 'Baseline'
    if (round_policy or {}).get('mode') == 'full_rounds':
        from .policy import candidate_rank
        system = system.replace('每轮恰好ABC三套', '每轮恰好提供goal.candidate_labels指定的方案，预算不足三套时按标签数量提供')
        system += ('本实验按round_policy分阶段停止（见合格标准后的停止规则）。若round_contract.downgrade_required为true，本轮至少一个方案（A、B都不是时由C承担）必须把generation_thinking从max降档并改至少一个检索参数。针对best_qualified_candidate的剩余Bad Case和离门槛最近的指标提出不同方向；'
                   '第2轮起想在合格方案上继续优化，就用继承字段；同轮几个方案的新改动必须互不相同。'
                   '可选inherited_from为本实验前几轮已评测合格ABC的完整ID；inherited_parameters只取该方案相对Baseline改过参数的子集，值和类型完全一致。'
                   'changed_parameters只写新增改动（config_diff是其兼容字段，两者同时写须一致），不得重复列出未变化的继承参数。'
                   '最终配置=Baseline+继承参数+新改动；白名单与取值范围检查完整差异，历史相同配置仍拒绝。'
                   'adjustments仅对应新改动，baseline_value取Baseline+继承参数配置里的值，expected_impact必须点名目标题号。'
                   '最小字段结构示例（占位参数名和占位值，仅示范结构）：'
                   '{"inherited_from":"前轮合格方案ID","inherited_parameters":{"基线参数":"已验证值"},"changed_parameters":{"新增参数":"新值"},'
                   '"adjustments":[{"parameter":"新增参数","baseline_value":"继承后的值","candidate_value":"新值","expected_impact":"目标题号及理由"}]}。'
                   'predicted_fixed_question_ids、依据引用、四部分结构和风险要求保持不变；理由、预测、风险全部由你自己写。')
        prompt['round_policy'] = round_policy
        prompt['round_contract']['count'] = len(labels)
        winner = min((c for c in prior_candidates if c['status']=='evaluated' and c.get('result',{}).get('qualification',{}).get('qualified') is True), key=candidate_rank, default=None)
        if winner:
            result = winner['result']
            hard_gates = []
            for gate in result.get('gates',{}).get('gates',[]):
                actual, threshold = gate.get('actual'), gate.get('threshold')
                margin = (actual-threshold if gate.get('operator')=='>=' else threshold-actual) if type(actual) in (int,float) and type(threshold) in (int,float) else None
                hard_gates.append({**gate,'margin':margin})
            metrics = result.get('metrics',{})
            prompt['best_qualified_candidate'] = {'candidate_id':winner['id'],'configuration':winner['config'],
                'remaining_bad_cases':bad_case_groups((candidate_cases or {}).get(winner['id'],[])), 'hard_gates':hard_gates,
                **{key:metrics.get(key,result.get(key)) for key in ('latency_p50_seconds','latency_p99_seconds')}}
    if causal_evidence:
        from .agent_inputs import case_comparisons
        from .policy import candidate_rank
        eligible = [c for c in prior_candidates if c['status']=='evaluated' and (candidate_cases or {}).get(c['id'])]
        winner = min(eligible, key=candidate_rank, default=None)
        prompt['case_comparisons'] = {c['id']:case_comparisons(baseline_cases or [], (candidate_cases or {}).get(c['id'], []), questions) for c in eligible}
        prompt['best_case_comparison'] = prompt['case_comparisons'].get(winner['id'], []) if winner else case_comparisons(baseline_cases or [], baseline_cases or [], questions)
        prompt['comparison_source'] = winner['id'] if winner else 'Baseline'
        system += ('每个方案相对基础方案最多改两个参数，ABC方向必须不同。逐题对比case_comparisons和best_case_comparison是程序算出的事实。'
                   '证据变化为否时，严禁把该题修好或新错归因于检索参数；证据未知时写不确定。'
                   'prior_round_review.plans每条新增causal_claims数组，每项含question_id（Q29形式）、parameter（中文参数名）、conclusion（有效、无效、不确定或未改变证据）。'
                   '每道修好、新错题都要有归因条目；未变的证据不能支持检索参数因果判断。'
                   'previous_round_conclusions必须读取并用于本轮选择。所有说明、理由、风险使用中文业务短句、中文参数名、Q29形式题号；不出现内部编号或英文下划线字段名。结构键和config_diff等机器字段保留协议格式。'
                   '与历史方案完全相同的配置不得再次提出。')
        system += '机器题号数组也可写Q29形式，程序会按冻结题卷解析；参数配置对象仍用协议字段名。'
    return system,prompt


def strategy_case(row):
    """All business failures enter processing; execution eligibility stays separate."""
    case=row.get('result',{})
    view=row.get('diagnostic_view') or diagnostic_view(case)
    return {'id':row.get('id'),'question_id':row.get('question_id'),'category':view['primary_root_cause'],
            'result':{key:case.get(key) for key in ('question','reference_answer','model_answer','test_category','negative_subtype')} | {'primary_root_cause':view['primary_root_cause']},
            'retrieval_trace':(case.get('programmatic_metrics') or {}).get('retrieval_trace'),
            'golden_evidence':{key:(case.get('programmatic_metrics') or {}).get('evidence_sufficiency',{}).get(key) for key in ('source_constraints','facts')},
            'diagnostic_view':{key:view.get(key) for key in ('issue_tags','secondary_root_causes','diagnosis_category','subfeature','severity_label','priority','display_question_id','retrieval_positions','tuning_directions','retrieval_metrics','analysis_category','analysis_reason','primary_root_cause','target_eligible','is_technical_bad_case','evidence_checks','optimization_directions','trace_observations','retrieval_failure_stage','context_selection_options','optimization_blockers','diagnostic_gaps','diagnosis_complete','experiment_plan')}}


def strategy_candidate(candidate):
    result = candidate.get('result', {})
    return {key:candidate.get(key) for key in ('id','config','status')} | {
        'reasoning':{key:value for key,value in candidate.get('reasoning',{}).items() if key in {
            'candidate_label','round','direction','action_name','hypothesis','proposal','risk','expected_improvement',
            'changed_parameters','changed_parameters_vs_baseline','inherited_from','inherited_parameters','observed_evidence','intervention_direction','evidence_assertions','parameter_dependencies'}},
        'result':{key:value for key,value in result.items() if key in {
            'evaluation_identity','evaluation_run_id','qualification','release_qualification','gates','metrics',
            'bad_case_count','all_fixed_question_ids','target_fixed_question_ids','new_failure_question_ids',
            'net_improvement','latency_p50_seconds','latency_p99_seconds','token_usage','estimated_cost'}} | {
                'regression':{key:value for key,value in result.get('regression',{}).items() if key in {
                    'passed','status','new_critical_failures','new_ordinary_failures','limits',
                    'all_fixed_question_ids','new_regression_question_ids','continued_failure_new_critical_question_ids'}}}}


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


def normalize_agent_config(config):
    """Convert JSON scalar strings only when they name an existing allowed value."""
    normalized = dict(config)
    for key, value in config.items():
        if not isinstance(value, str):
            continue
        try:
            scalar = json.loads(value)
        except ValueError:
            continue
        for option in ALLOWED_SEARCH_SPACE.get(key, ()):
            same_type = type(scalar) is type(option) or type(scalar) in (int, float) and type(option) in (int, float)
            if same_type and scalar == option:
                normalized[key] = option
                break
    return normalized


def normalize_agent_candidate(candidate):
    if not isinstance(candidate, dict):
        return candidate
    candidate = dict(candidate)
    for field in ('config_diff', 'changed_parameters'):
        if isinstance(candidate.get(field), dict):
            candidate[field] = normalize_agent_config(candidate[field])
    if isinstance(candidate.get('target_bad_cases'), str):
        candidate['target_bad_cases'] = [candidate['target_bad_cases']]
    if isinstance(candidate.get('adjustments'), list):
        candidate['adjustments'] = [
            {**item, **{field: normalize_agent_config({item.get('parameter'): item[field]})[item.get('parameter')]
                       for field in ('baseline_value', 'candidate_value') if field in item}}
            if isinstance(item, dict) else item for item in candidate['adjustments']]
    if isinstance(candidate.get('risks'), list):
        candidate['risks'] = [{**risk, 'question_ids': [risk['question_ids']]}
            if isinstance(risk, dict) and isinstance(risk.get('question_ids'), str) else risk
            for risk in candidate['risks']]
    return candidate


def prepare_response(content,base_config,bad_cases,prior_candidates,completed,round_number,labels,trigger_id,monitoring_target_event_ids,audit):
    """One offline validation path for fresh and already-paid responses; no semantic repairs."""
    audit.update(parsed_json=None,parsed_candidates=None,rejected_candidates=[])
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
    result = parse_agent_json(content, audit)
    audit["parsed_json"] = result
    audit["validation_stage"] = "schema"
    if not isinstance(result, dict) or not isinstance(result.get("candidates"), list):
        audit.update(failed_field="candidates", actual_value=result.get("candidates") if isinstance(result, dict) else result, expected_type="array", allowed_values=None)
        raise ValueError("Agent 输出必须包含 candidates 数组")
    audit["parsed_candidates"] = result['candidates']
    candidates = [normalize_agent_candidate(c) for c in result['candidates']]
    full_rounds = audit.get('round_policy', {}).get('mode') == 'full_rounds'
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        if full_rounds and 'changed_parameters' in candidate:
            changes = candidate['changed_parameters']
            if 'config_diff' in candidate and candidate['config_diff'] != changes:
                raise ValueError('changed_parameters与config_diff必须一致')
            candidate['config_diff'] = changes
        inherited_base(candidate, base_config, prior_candidates, round_number, audit.get('round_policy'))
    result = {**result, 'candidates': candidates}
    if audit.get('causal_evidence'):
        from .agent_strategy import normalize_question_references, business_output
        mapping = {r['题号']:r['题目键'] for rows in [audit.get('best_case_comparison', []), *audit.get('case_comparisons', {}).values()] for r in rows}
        result = normalize_question_references(result, mapping)
        candidates = result['candidates']
        result = business_output(result, mapping, {c['id']:f"第{c.get('reasoning',{}).get('round',1)}轮方案{c.get('reasoning',{}).get('candidate_label','')}" for c in prior_candidates})
        candidates = result['candidates']
    audit['prior_round_review'] = validate_prior_round_review(result, prior_candidates)
    validate_round_contract(candidates,base_config,prior_candidates,(audit.get('baseline_gate_results') or {}).get('gates'),completed=completed,
                            labels=labels if audit.get('strategy_contract') == 'agent-strategy-4' else None, round_number=round_number)
    if audit.get('strategy_contract') in {'agent-strategy-3','agent-strategy-4'}:
        from .agent_strategy import validate_strategy
        validate_strategy(result, prior_candidates, audit, {item['question_id'] for item in bad_cases})
    if audit.get('causal_evidence'):
        from .agent_strategy import validate_causal_proposals
        validate_causal_proposals(result, audit.get('case_comparisons', {}))
    audit.update(response_contract_version='agent-response-2',rejected_candidates=[],response_warnings=[])
    if len(candidates)<len(labels) and not isinstance(result.get('insufficient_evidence'),str):
        audit['response_warnings'].append({'field':'insufficient_evidence','reason':'model_did_not_provide_explanation'})
    counts=Counter(c.get('id') for c in candidates if isinstance(c,dict) and isinstance(c.get('id'),str))
    staged = []
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
            effective_base = inherited_base(candidate, base_config, prior_candidates, round_number, audit.get('round_policy'))
            signature = parameter_signature(effective_base, candidate['config_diff']) if isinstance(candidate.get('config_diff'), dict) else None
            if signature in failed_signatures and not audit.get('causal_evidence'):
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
            config = {**effective_base, **diff}
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
            validate_intervention(candidate,target_cases,effective_base)
            target_ids = [item['diagnostic_view'].get('display_question_id') or item['question_id'] for item in selected]
            target_mentions = target_ids + [item['question_id'] for item in selected]
            focus = '速度优先' if 'generation_thinking' in diff else '检索优先'
            candidate.setdefault('strategy_name', f'「{candidate["action_name"]}」（{focus}）')
            candidate.setdefault('core_idea', candidate['hypothesis'])
            candidate.setdefault('adjustments', [{'parameter':key, 'baseline_value':effective_base.get(key), 'candidate_value':value,
                'expected_impact':candidate['expected_improvement'] if any(q in candidate['expected_improvement'] for q in target_mentions) else candidate['expected_improvement']+'；目标题号：'+'、'.join(target_ids)} for key,value in diff.items()])
            candidate.setdefault('risks', [{'question_ids':[], 'metric':None, 'reason':candidate['risk']}])
            if not isinstance(candidate['strategy_name'], str) or not re.fullmatch(r'「.+」（.+优先）', candidate['strategy_name']):
                raise ValueError('策略名必须为「动作名」（xx优先）')
            if not isinstance(candidate['core_idea'],str) or not candidate['core_idea'].strip():
                raise ValueError('缺少核心思路')
            adjustments = candidate['adjustments']
            if (not isinstance(adjustments,list) or len(adjustments)!=len(diff)
                    or {item.get('parameter') for item in adjustments if isinstance(item,dict)}!=set(diff)
                    or any(not isinstance(item,dict) or item.get('baseline_value')!=effective_base.get(item.get('parameter'))
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
            staged.append((candidate, config))
        except (ValueError,TypeError,KeyError) as error:
            # Validation refusals have not been tried in Sandbox and are not failed effects.
            audit['rejected_candidates'].append({'index':index,'id':candidate.get('id') if isinstance(candidate,dict) else None,
                'stage':audit['validation_stage'],'field':audit.get('failed_field'),'reason':str(error),
                'validation_issues':audit.get('validation_issues',[]),
                'actual_value':audit.get('actual_value'),'expected_type':audit.get('expected_type'),'allowed_values':audit.get('allowed_values')})
    if len(staged)!=(len(labels) if audit.get('strategy_contract') == 'agent-strategy-4' else 3):
        raise ValueError('整轮ABC校验拒绝：'+'；'.join(r['reason'] for r in audit['rejected_candidates']))
    audit["validation_stage"] = "completed"
    audit['failed_parameter_signatures'] = sorted(failed_signatures)
    audit["failed_candidate_id"] = None
    batch = []
    for candidate, config in staged:
        batch.append((f"R{round_number}-{candidate['id']}", config, {
            **{key:candidate[key] for key in ('direction','strategy_name','core_idea','adjustments','risks','parameter_signature','review_conclusion_ids')},
            **{key:candidate[key] for key in ('bad_case_conclusion_ids','predicted_fixed_question_ids') if key in candidate},
            "intervention_direction":candidate['intervention_direction'], "supporting_directions":candidate.get('supporting_directions',[]), "action_name":candidate["action_name"], "intervention_contract_version":"agent-closure-4", "experiment_kind":candidate.get("experiment_kind","confirmed"), "falsification":candidate.get("falsification"), "parameter_dependencies":candidate.get('parameter_dependencies',[]), "evidence_assertions":candidate.get('evidence_assertions',[]), "performance_stage":candidate.get('performance_stage'),
            "target_root_causes": candidate.get("target_root_causes"), "provenance": candidate.get("provenance"), "target_group": candidate.get("target_group") if isinstance(candidate.get("target_group"),str) else None, "root_cause": candidate["root_cause"], "root_cause_evidence": candidate["root_cause_evidence"], "expected_improvement": candidate["expected_improvement"], "target_diagnosis": [strategy_case(item) for item in bad_cases if item["id"] in candidate["target_bad_cases"] or item["question_id"] in candidate["target_bad_cases"]], "root_cause_cluster": result.get("root_cause_cluster"), "observed_evidence": candidate["target_bad_cases"], "hypothesis": candidate["hypothesis"], "proposal": candidate["why"], "risk": candidate["risk"],
            **({'inherited_from':candidate['inherited_from'],'inherited_parameters':candidate['inherited_parameters']} if candidate.get('inherited_from') else {}),
            **({'changed_parameters_vs_baseline':{key:value for key,value in config.items() if value != base_config.get(key)}} if full_rounds else {}),
            "changed_parameters": candidate['config_diff'] if full_rounds else {key: value for key, value in config.items() if value != base_config.get(key)}, "source_trigger_id": trigger_id, "monitoring_target_event_ids": monitoring_target_event_ids, "round": round_number, "candidate_label": candidate["id"],
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
        checkpoints=previous.get('agent_request_checkpoints',{})
        checkpoint=checkpoints.setdefault(request_hash,previous.get('agent_request_checkpoint',{'attempts':[]})
            if previous.get('agent_request_sha256')==request_hash else {'attempts':[]})
        def save(*_args,**_kwargs):
            self._checkpoint(experiment_id,generation_token,{'agent_request_checkpoint':checkpoint,'agent_request_sha256':request_hash,
                'agent_request_checkpoints':checkpoints})
        from .optimization_cycle import check_cycle_stop
        token=_request_checkpoint.set((checkpoint,'agent',experiment_id,save,lambda:check_cycle_stop(self.store,experiment_id)))
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
        from .paid_run import current_paid_run
        if confirmed_context.get('paid_run') and current_paid_run() is None:
            from .paid_policy import restore_paid_context
            with restore_paid_context(self.store,confirmed_context['paid_run']):
                return self.generate(baseline_run_id,trigger_id,experiment_id=existing_id)
        trigger = trigger or self.store.optimization_trigger(confirmed_context.get("trigger_id"))
        event = None
        if existing and existing["baseline_run_id"] == baseline_run_id and trigger and trigger["status"] == "human_confirmed" and trigger["optimization_run_id"] == existing_id:
            event = next((item for item in self.store.monitoring_events() if item["id"] == trigger["event_id"] and item["bad_case"] and item["determinable"]), None)
        baseline = self.store.evaluation_run(baseline_run_id)
        base_config = {**DEFAULT_PIPELINE_CONFIG, **baseline["config"]}
        base_config.pop("run_target", None)
        base_config.pop("knowledge_identity", None)
        base_config = {k:v for k,v in base_config.items() if k in ALLOWED_SEARCH_SPACE}
        if existing and existing.get('evaluation_budget',{}).get('used',0) >= MAX_EVALS - 1:
            raise ValueError('A/B/C试跑预算已用完，须保留D预算')
        experiment_id, prior_candidates, round_number, completed, generation_token = self.store.claim_agent_generation(baseline_run_id, trigger_id, existing_id)
        if not existing or existing['status']!='generating':
            clear_run_now(self.store,'agent:'+experiment_id)
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
        # Only this experiment's observed runs may inform a new round.
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
        evaluation_budget = {"used": completed, "max": MAX_EVALS, "reserved_for_d": 0,
                             "remaining":MAX_EVALS-completed,"remaining_for_abc":max(0,MAX_EVALS-completed)}
        gate_results = baseline["result"].get("gates")
        persisted_gates = (gate_results or {}).get("gates")
        failed_gates = [gate for gate in persisted_gates if gate.get("passed") is False] if isinstance(persisted_gates, list) else None
        labels = ['A', 'B', 'C']
        if context.get('round_policy',{}).get('mode') == 'full_rounds':
            labels = labels[:min(3,evaluation_budget['remaining_for_abc'])]
            context['strategy_contract'] = 'agent-strategy-4'
        audit = {"optimization_run_id": experiment_id, "baseline_id": baseline_run_id, "timestamp": datetime.now(timezone.utc).isoformat(), "provider_raw_text": None, "parsed_json": None, "parsed_candidates": None, "validation_stage": "provider", "failed_candidate_id": None, "failed_field": None, "actual_value": None, "expected_type": None, "allowed_values": None, "validation_issues": [], "diagnostic_tasks":diagnostic_tasks, "processing_progress":processing_progress, "all_bad_case_audit": [{k:v for k,v in row.items() if k!='result_json'} for row in audited_cases], "root_cause_counts": dict(Counter(item['diagnostic_view']['primary_root_cause'] for item in bad_cases)), "source_bad_case_ids": [item["id"] for item in bad_cases], "monitoring_context": monitoring_context, "monitoring_target_event_ids": monitoring_target_event_ids, "target_reference_map": target_reference_map, "evaluation_budget": evaluation_budget, "baseline_gate_results": gate_results, "failed_gates": failed_gates}
        failed_signatures = set(context.get('failed_parameter_signatures') or [])
        failed_signatures.update(parameter_signature(base_config,{key:value for key,value in c['config'].items() if value!=base_config.get(key)})
                                 for c in prior_candidates if c['status'] in {'failed','evaluated'} and not c.get('result',{}).get('qualification',{}).get('qualified'))
        audit['failed_parameter_signatures'] = sorted(failed_signatures)
        frozen=json.loads(baseline.get('dataset_snapshot_json') or '{}')
        questions={q['id']:q for q in frozen.get('questions',[])}
        def saved_cases(run_id):
            rows=self.store.evaluation_case_results(run_id) if run_id else []
            for row in rows:
                golden=questions.get(row['question_id'],{})
                match=re.search(r'(?:^Q|[-_])(\d{2,3})$',row['question_id'])
                row['display_question_id']=golden.get('display_id') or golden.get('coverage_slot') or (golden.get('raw') or {}).get('coverage_slot') or (f'Q{int(match[1]):02d}' if match else row['question_id'])
            return rows
        system,prompt=build_agent_prompt(failures,base_config,prior_candidates,failed_gates,labels,
            baseline_gates=persisted_gates,evaluation_budget=evaluation_budget,failed_parameter_signatures=audit['failed_parameter_signatures'],
            baseline_result=baseline['result'],baseline_cases=saved_cases(baseline_run_id),
            candidate_cases={c['id']:saved_cases(c.get('result',{}).get('evaluation_run_id')) for c in prior_candidates},
            golden_questions=list(questions.values()),round_conclusions=context.get('round_conclusions'),round_policy=context.get('round_policy'),causal_evidence=context.get('causal_evidence') is True,round_number=round_number)
        audit['causal_evidence'] = context.get('causal_evidence') is True
        audit['case_comparisons'] = prompt.get('case_comparisons', {})
        audit['best_case_comparison'] = prompt.get('best_case_comparison', [])
        audit['strategy_contract'] = context.get('strategy_contract')
        audit['round_policy'] = context.get('round_policy', {})
        if audit['round_policy'].get('mode') == 'full_rounds':
            prompt['proposal_generation'] = {'round':round_number, 'prior_failed_batches':
                context.get('optimization_cycle', {}).get('proposal_generation_failures', [])}
        audit['bad_case_groups'] = prompt['bad_case_groups']
        audit['agent_strategy'] = '降档补位' if prompt['round_contract']['downgrade_required'] else '自主优化'
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
                    else:
                        audit['request_summary']={'request_sha256':hashlib.sha256((system+user).encode()).hexdigest()}
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
                        for key in ('validation_retries','format_retry'):
                            if key in previous:audit[key]=previous[key]
                    else:
                        wait_for_off_peak(self.store,'agent:'+experiment_id,
                            lambda pause:self._checkpoint(experiment_id,generation_token,{'price_pause':pause}))
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
            for attempt in range(len(audit.get('validation_retries',[])),4):
                try:
                    result,batch=prepare_response(content,base_config,bad_cases,prior_candidates,completed,round_number,labels,trigger_id,monitoring_target_event_ids,audit)
                    break
                except (ValueError,TypeError,KeyError) as validation_error:
                    if attempt==3:
                        raise ProposalValidationExhausted('连续 3 次方案不合规；首次被拒后的 3 次重出均未通过：'+str(validation_error)) from validation_error
                    rejection={'attempt':attempt+1,'reason':str(validation_error),'rejected_response':content,'sandbox_budget_used':0,
                               'stage':audit['validation_stage'],'rejected_candidates':list(audit.get('rejected_candidates') or []),
                               **({'syntax_repair':audit['syntax_repair']} if audit.get('syntax_repair') else {})}
                    audit.setdefault('validation_retries',[]).append(rejection)
                    audit.setdefault('format_retry',{'reason':str(validation_error),'first_raw_text':content,'sandbox_budget_used':0})
                    retry_prompt={**prompt,'validation_rejection':{**rejection,'instruction':'按具体拒绝原因重出goal.candidate_labels指定的全部方案；规则拒绝未占试跑预算'},
                                  'validation_rejection_history':audit['validation_retries']}
                    wait_for_off_peak(self.store,'agent:'+experiment_id,
                        lambda pause:self._checkpoint(experiment_id,generation_token,{'price_pause':pause}))
                    retry_user=json.dumps(retry_prompt,ensure_ascii=False)
                    summary=self.provider.request_summary(system,retry_user,json_mode=True) if callable(getattr(self.provider,'request_summary',None)) else {
                        'request_sha256':hashlib.sha256((system+retry_user).encode()).hexdigest()}
                    with collect_usage() as retry_usage:
                        previous=self.store.experiment(experiment_id,light=True)['result']
                        with self._request_checkpoint(experiment_id,generation_token,previous,summary['request_sha256']) as checkpoint:
                            content=self.provider.complete(system,retry_user,json_mode=True)
                            if not retry_usage:
                                from .evaluation_stage import checkpoint_usage
                                retry_events=checkpoint_usage(checkpoint)
                            else:retry_events=retry_usage
                    audit['token_usage']=[*audit.get('token_usage',[]),*retry_events]
                    audit.update(cost_fields(getattr(getattr(self.provider,'settings',None),'model',None),audit['token_usage']))
                    audit['provider_raw_text']=content
                    self._checkpoint(experiment_id,generation_token,{**audit,'validation_stage':'persistence'})
            audit["validation_stage"] = "persistence"
            self.store.save_agent_round(experiment_id, batch, {**result, **audit, "generation_status":"partial" if audit["rejected_candidates"] else "completed" if batch else "no_candidates", "requested_candidate_count":len(labels), "generated_candidate_count":len(batch), "validation_stage": "completed", "round": round_number, "evaluation_budget": evaluation_budget}, generation_token=generation_token)
            return self.store.experiment(experiment_id)
        except Exception as error:
            if isinstance(error,ProposalValidationExhausted):
                audit.update(generation_status='analysis_exhausted',validation_error=str(error),provider_error=None)
                self.store.save_agent_trace(experiment_id,'analysis_exhausted',audit,str(error),generation_token=generation_token)
                raise
            if isinstance(error,ProviderRequestError):audit['validation_stage']='request_validation'
            audit['generation_status']='failed'
            audit['provider_error']=provider_error_details(error,audit['validation_stage'])
            message=f"{error}；失败阶段：{audit['validation_stage']}；可重试：{'是' if audit['provider_error']['retryable'] else '否'}"
            audit["validation_error"] = message
            self.store.save_agent_trace(experiment_id, "failed", audit, message, generation_token=generation_token)
            raise ValueError(message) from error
