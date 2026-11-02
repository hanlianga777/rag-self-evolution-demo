"""Snapshot-bound Evaluation runner and V1.0.1 metric aggregation."""

from __future__ import annotations

import os
import json
import time
import math
from .safety_guard import check_safety, adjudicate
from statistics import mean
from .evaluation_contract import VERSIONS, policy_current, evaluation_identity, observe_evidence, resolve_evidence, compare_cases, assess_claims, validate_business_judgment, business_check_roles, quote_present

from .policy import DEFAULT_PIPELINE_CONFIG, calculate_overall_score, evaluate_gates, evaluate_regression, qualify_candidate, qualify_release


ROOT_CAUSE_BY_TAG = {
    "Query Failure": "Query", "Retrieval Failure": "Retrieval", "Ranking Failure": "Ranking",
    "Metadata / Entity Failure": "Metadata / Entity", "Generation Failure": "Generation",
    "Evidence / Citation Failure": "Generation", "Hallucination": "Generation",
    "Unsafe Answer": "Safety", "Safety Failure": "Safety", "Performance Failure": "Performance",
}


def root_cause_layers(failure_tags: list[str], coverage: dict | None = None, test_category: str | None = None) -> tuple[str, list[str]]:
    """Preliminary diagnosis from observed pipeline evidence; legacy callers retain tag order."""
    layers = list(dict.fromkeys(ROOT_CAUSE_BY_TAG[tag] for tag in failure_tags if tag in ROOT_CAUSE_BY_TAG))
    if test_category is None:
        return (layers[0], layers[1:]) if layers else ("None", [])
    if not failure_tags:
        return "None", []
    if "Safety" in layers:
        primary = "Safety"
    elif test_category in {"positive", "ablation"} and any(layer in layers for layer in {"Generation", "Retrieval", "Ranking"}):
        candidate = (coverage or {}).get('candidate_recall', {}).get('all_hit')
        final = (coverage or {}).get('final_context', {}).get('all_hit')
        if not (coverage or {}).get('required_chunk_ids'):
            primary = "Unknown"
        elif candidate is False:
            primary = "Retrieval"
        elif candidate is True and final is False:
            primary = "Ranking"
        elif final is True:
            primary = "Generation"
        else:
            primary = "Unknown"
    else:
        primary = layers[0] if layers else "Unknown"
    return primary, [layer for layer in layers if layer != primary]


def _percentile(values: list[float], percentile: float):
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int((len(ordered) - 1) * percentile))]


def _mean(values: list[float]):
    return round(mean(values), 2) if values else None


def policy_behavior(case):
    value=case.get('programmatic_metrics',{}).get('behavior_contract',{}).get('effective_pass',case.get('judge_result',{}).get('behavior_pass'))
    return value if type(value) is bool else None


def protected_question(case, golden=None):
    """Use frozen question identity, never a candidate answer's dynamic issue severity."""
    golden = golden or {}
    return (golden.get('negative_subtype', case.get('negative_subtype')) in {'safety_critical', 'prompt_injection'}
            or golden.get('criticality') == 'high'
            or golden.get('severity', case.get('severity')) == 'critical')


def candidate_comparison(baseline, candidate, targets, golden_questions=None):
    """Task 004 compares saved binary outcomes; only reviewed fluctuations are excluded."""
    comparison = compare_cases(baseline, candidate, targets)
    fluctuations = sorted(q for q, c in candidate.items() if baseline.get(q, {}).get('passed') is True and c.get('regression_review', {}).get('status') == 'fluctuation')
    new = sorted(q for q, c in baseline.items() if c.get('passed') is True and candidate.get(q, {}).get('passed') is False and q not in fluctuations)
    fixed = sorted(q for q, c in baseline.items() if c.get('passed') is False and candidate.get(q, {}).get('passed') is True)
    critical = [q for q in new if protected_question(baseline[q], (golden_questions or {}).get(q))]
    target = sorted(set(fixed) & set(targets))
    complete = bool(baseline) and set(baseline) == set(candidate) and all(type(c.get('passed')) is bool for c in [*baseline.values(), *candidate.values()])
    return {**comparison, 'comparison_complete': complete,
            'new_regression_question_ids': new, 'new_regressions': len(new), 'fluctuation_question_ids': fluctuations,
            'new_critical_failures': len(critical), 'new_ordinary_failures': len(new) - len(critical),
            'all_fixed_question_ids': fixed, 'target_fixed_question_ids': target, 'target_bad_cases_fixed': len(target),
            'incidental_fixed_question_ids': sorted(set(fixed) - set(target)), 'incidental_fixes': len(set(fixed) - set(target)),
            'net_improvement': len(fixed) - len(new), 'formal_blocking_question_ids': critical,
            'bad_case_count': sum(c.get('passed') is False for q, c in candidate.items() if q not in fluctuations),
            'initial_bad_case_count': sum(c.get('passed') is False for c in candidate.values()),
            'regression_interpretation': '初次新增错题复核两次，三次多数判错才计新增；普通新增只记录，关键安全及注入新增阻断ABC'}


def summarize_evaluation_cases(cases: list[dict], *, complete=True) -> dict:
    """Aggregate persisted case records without inventing absent group metrics."""
    groups = {"positive": [], "ablation": [], "negative": []}
    for case in cases:
        if case.get("test_category") in groups:
            groups[case["test_category"]].append(case)

    def quality(group: str, key: str):
        values = []
        for item in groups[group]:
            value = item.get("judge_result", {}).get(key)
            if type(value) not in (int, float) or not math.isfinite(value):
                return None
            values.append(float(value) * (25 if key == "correctness" else 100))
        return _mean(values)

    metrics = {
        "positive_correctness": quality("positive", "correctness"),
        "positive_faithfulness": quality("positive", "faithfulness"),
        "positive_completeness": quality("positive", "completeness"),
        "ablation_correctness": quality("ablation", "correctness"),
        "ablation_faithfulness": quality("ablation", "faithfulness"),
        "ablation_completeness": quality("ablation", "completeness"),
    }

    negatives = groups["negative"]
    safe = lambda item: None if policy_behavior(item) is None else 100.0 if policy_behavior(item) else 0.0
    metrics.update({
        "safe_rejection_rate": _mean([safe(item) for item in negatives]) if all(policy_behavior(item) is not None for item in negatives) else None,
        "safety_critical_accuracy": _mean([safe(item) for item in negatives if item.get("negative_subtype") == "safety_critical"]) if all(policy_behavior(item) is not None for item in negatives if item.get("negative_subtype") == "safety_critical") else None,
        "prompt_injection_resistance": _mean([safe(item) for item in negatives if item.get("negative_subtype") == "prompt_injection"]) if all(policy_behavior(item) is not None for item in negatives if item.get("negative_subtype") == "prompt_injection") else None,
    })
    latency_seconds = [item["programmatic_metrics"]["latency_ms"] / 1000 for item in cases if isinstance(item.get("programmatic_metrics", {}).get("latency_ms"), (int, float))]
    if len(latency_seconds) != len(cases):
        latency_seconds=[]
    metrics["latency_p50_seconds"] = _percentile(latency_seconds, .5)
    metrics["latency_p99_seconds"] = _percentile(latency_seconds, .99)
    hits = [item["programmatic_metrics"]["retrieval_hit"] for item in cases if item.get("programmatic_metrics", {}).get("retrieval_hit") is not None]
    precisions = [item["programmatic_metrics"]["retrieval_precision"] for item in cases if isinstance(item.get("programmatic_metrics", {}).get("retrieval_precision"), (int, float))]
    reciprocal_ranks = [1 / item["programmatic_metrics"]["retrieval_rank"] for item in cases if isinstance(item.get("programmatic_metrics", {}).get("retrieval_rank"), int) and item["programmatic_metrics"]["retrieval_rank"] > 0]
    ttfts = [item["programmatic_metrics"]["ttft_ms"] / 1000 for item in cases if isinstance(item.get("programmatic_metrics", {}).get("ttft_ms"), (int, float))]
    input_tokens = [item["programmatic_metrics"]["input_tokens"] for item in cases if isinstance(item.get("programmatic_metrics", {}).get("input_tokens"), (int, float))]
    output_tokens = [item["programmatic_metrics"]["output_tokens"] for item in cases if isinstance(item.get("programmatic_metrics", {}).get("output_tokens"), (int, float))]
    provider_costs = [item["programmatic_metrics"]["provider_cost"] for item in cases if isinstance(item.get("programmatic_metrics", {}).get("provider_cost"), (int, float))]
    overall = calculate_overall_score(metrics)
    result = {
        'safety_verification_complete':not any(c.get('evaluation_outcome',{}).get('safety_review_required') for c in cases),
        'safety_review_question_ids':[c.get('question_id') for c in cases if c.get('evaluation_outcome',{}).get('safety_review_required')],
        "completed": len(cases), "failed": sum(not item.get("passed", False) for item in cases),
        "group_metrics": {group: {key: metrics[f"{group}_{key}"] for key in ("correctness", "faithfulness", "completeness")} for group in ("positive", "ablation")},
        "safety_metrics": {key: metrics[key] for key in ("safe_rejection_rate", "safety_critical_accuracy", "prompt_injection_resistance")},
        "metrics": metrics, "gates": evaluate_gates(metrics), "overall_score": overall["score"], "overall_score_status": overall["status"],
        "comparison_metrics": {"ttft_seconds": _mean(ttfts), "ttft_target_status": "WARNING" if ttfts and _mean(ttfts) > 5 else "OK" if ttfts else "NOT_MEASURED", "input_tokens": sum(input_tokens) if input_tokens else None, "output_tokens": sum(output_tokens) if output_tokens else None, "token_cost": round(sum(provider_costs), 6) if provider_costs else None, "token_cost_status": "MEASURED" if provider_costs else "Token Usage / Provider Cost unavailable", "recall_at_k": round(100 * sum(bool(hit) for hit in hits) / len(hits), 2) if hits else None, "precision_at_k": _mean(precisions), "mrr": _mean(reciprocal_ranks)},
        "bad_case_count": sum(not item.get("passed", False) for item in cases),
    }
    if not complete:
        result.update(overall_score=None, overall_score_status='NOT_EVALUABLE',partial_bad_case_count=result['bad_case_count'],bad_case_count=None, gates={**evaluate_gates({}), 'passed':None,'passed_count':None})
    return result


def gate_details(cases: list[dict], gates: list[dict], *, statistics_version='frozen-negative-subtype-2') -> list[dict]:
    """Explain stored gates from the same persisted case inputs used by aggregation."""
    details = []
    for gate in gates:
        metric = gate["metric"]
        selected = cases
        if metric.startswith("positive_") or metric.startswith("ablation_"):
            group, field = metric.split("_", 1)
            selected = [item for item in cases if item.get("test_category") == group]
            values = [(item, item.get("judge_result", {}).get(field)) for item in selected]
            contributions = [{"question_id": item.get("question_id"), "value": round(float(value) * (25 if field == "correctness" else 100), 2), "passed": item.get("passed")} for item, value in values if isinstance(value, (int, float))]
            formula = "算术平均；Correctness 原始 0–4 分乘以 25" if field == "correctness" else "逐题 0–1 分乘以 100 后算术平均"
        elif metric in {"safe_rejection_rate", "safety_critical_accuracy", "prompt_injection_resistance"}:
            selected = [item for item in cases if item.get("test_category") == "negative" and (metric != "safety_critical_accuracy" or (item.get("negative_subtype") == "safety_critical" if statistics_version == "frozen-negative-subtype-2" else item.get("severity") == "critical")) and (metric != "prompt_injection_resistance" or item.get("negative_subtype") == "prompt_injection")]
            contributions = [{"question_id": item.get("question_id"), "value": None if policy_behavior(item) is None else 100.0 if policy_behavior(item) else 0.0, "passed": item.get("passed")} for item in selected]
            formula = "适用负向题政策行为通过比例；旧记录使用保存的 behavior_pass"
        else:
            contributions = [{"question_id": item.get("question_id"), "value": round(item["programmatic_metrics"]["latency_ms"] / 1000, 2), "passed": item.get("passed")} for item in cases if isinstance(item.get("programmatic_metrics", {}).get("latency_ms"), (int, float))]
            formula = "排序后取 floor((n-1)×p) 位；p=0.50" if metric == "latency_p50_seconds" else "排序后取 floor((n-1)×p) 位；p=0.99"
        failed = [item for item in contributions if item["value"] is not None and (item["value"] < gate["threshold"] if gate["operator"] == ">=" else item["value"] > gate["threshold"])]
        details.append({**gate, "formula": formula, "included_cases": len(contributions), "contributing_cases": contributions, "failed_cases": failed})
    return details


def frozen_run_judge(function):
    """A resumed run uses its saved Judge setting, independent of current env."""
    from functools import wraps
    @wraps(function)
    def execute(self, run_id, *args, **kwargs):
        from .providers import judge_thinking
        run = self.store.evaluation_run(run_id)
        effort = (run or {}).get('judge', {}).get('judge_thinking', {}).get('reasoning_effort')
        with judge_thinking(effort):
            return function(self, run_id, *args, **kwargs)
    return execute


class EvaluationRunner:
    def __init__(self, store, runtime):
        self.store, self.runtime = store, runtime

    def _require_generation_contract(self, judge):
        contract = getattr(self.runtime, 'generation_contract', None)
        if isinstance(contract, dict) and any(judge.get(k) != v for k, v in contract.items()):
            raise ValueError('Generation contract不匹配，禁止跨版本生成或续跑')
        if isinstance(contract, dict) and judge.get('common_identity_version') != 'round0-common-1':
            raise ValueError('Generation/Thinking共同合同缺失（历史未知），禁止新生成或比较')
        if judge.get('common_identity_version') == 'round0-common-1':
            from .providers import thinking_config
            if judge.get('judge_thinking') != thinking_config('judge'):
                raise ValueError('Judge Thinking合同不匹配，禁止跨身份比较或续跑')
            if judge.get('generation_model_constraint') != self.runtime.model or judge.get('model') != self.runtime.model:
                raise ValueError('共同模型合同不匹配，禁止跨身份比较或续跑')

    def snapshot_items(self, snapshot):
        frozen = {item['id']: item for item in snapshot.get('questions', [])}
        items = []
        for key in snapshot.get('question_ids', []):
            try:
                current = self.store.question(key)
            except KeyError:
                if key not in frozen or 'test_category' not in frozen[key]:
                    raise ValueError('历史Snapshot缺少完整题目/类别，不能按当前题目补造')
                current = {'id':key, **frozen[key], 'raw':frozen[key]}
            raw = frozen.get(key, current['raw'])
            items.append({**current, 'question': raw['question'], 'reference_answer': raw.get('reference_answer'), 'expected_behavior': raw.get('expected_behavior'), 'evidence': raw.get('evidence', raw.get('acceptable_evidence', [])), 'raw': raw, 'test_category': raw.get('test_category', current['test_category']), 'negative_subtype': raw.get('negative_subtype', current.get('negative_subtype'))})
        return items

    def baseline_inputs(self, resume_source_id=None):
        from .providers import judge_thinking
        from contextlib import nullcontext
        source=self.store.evaluation_run(resume_source_id) if resume_source_id else None
        context=judge_thinking(source['judge'].get('judge_thinking',{}).get('reasoning_effort')) if source else nullcontext()
        with context:
            return self._baseline_inputs(resume_source_id)

    def _baseline_inputs(self, resume_source_id=None):
        snapshots = self.store.dataset_snapshots()
        if not snapshots:
            raise ValueError("正式评测需要已批准（approved）且显式创建的 Golden Snapshot")
        snapshot = snapshots[0]["snapshot"]
        from .scoring_contract import validate_snapshot_manifest
        if isinstance(getattr(self.runtime, "generation_contract", None), dict):
            validate_snapshot_manifest(snapshot)
        approved = self.snapshot_items(snapshot)
        categories = {item["test_category"] for item in approved}
        negative_subtypes = {item.get("negative_subtype") for item in approved if item["test_category"] == "negative"}
        if not {"positive", "ablation", "negative"}.issubset(categories) or not {"safety_critical", "prompt_injection"}.issubset(negative_subtypes):
            raise ValueError("正式评测需要完整 approved Golden：Positive、Ablation、Negative、Safety Critical 与 Prompt Injection")
        production = self.store.active_production() or {"config": {}}
        source = self.store.evaluation_run(resume_source_id) if resume_source_id else None
        config = {**DEFAULT_PIPELINE_CONFIG, "run_target": "baseline"}
        if source:
            self._require_generation_contract(source['judge'])
            from .evaluation_contract import experiment_config_identity
            if source['judge'].get('common_identity_version') == 'round0-common-1' and source.get('result',{}).get('experiment_config_identity') != experiment_config_identity(source['config']):
                raise ValueError('实验配置身份不匹配，禁止复用已保存答案或续跑')
            config = dict(source['config'])
        else:
            draft_reader = getattr(self.store, 'pipeline_draft', None)
            draft = draft_reader() if callable(draft_reader) else None
            if isinstance(draft, dict) and isinstance(draft.get('config'), dict):
                if draft.get('identity') != self.store.current_baseline_identity():
                    raise ValueError('Config Draft基准已变化，请刷新核对后重新保存')
                from .policy import validate_candidate_config
                validation = validate_candidate_config(draft['config'])
                if not validation['valid']:
                    raise ValueError('Config Draft参数非法：' + '; '.join(validation['errors']))
                config.update(draft['config'])
                if config.get('hybrid_search') is False: config.pop('hybrid_alpha', None)
            config['generation_thinking'] = getattr(getattr(getattr(self.runtime, 'provider', None), 'settings', None), 'baseline_thinking', 'max')
            if config['generation_thinking'] not in {'off', 'low', 'high', 'max'}:
                raise ValueError('BASELINE_THINKING必须为off/low/high/max')
        index_info = self.runtime.corpus.index_info() if hasattr(self.runtime, "corpus") and hasattr(self.runtime.corpus, "index_info") else {}
        if not isinstance(index_info, dict):
            index_info = {}
        if index_info.get('knowledge_identity'):
            if snapshot.get('corpus_fingerprint') != index_info['knowledge_identity']:
                raise ValueError('Golden Snapshot does not belong to active Knowledge Pipeline')
            from .canonical_evidence import optimization_preflight
            if not resume_source_id:
                chunks=self.runtime.corpus.chunks()
                for item in approved:
                    readiness=optimization_preflight(item,chunks)
                    if not readiness['ready']:raise ValueError(item['id']+': '+'; '.join(readiness['blocking_errors']))
            config['knowledge_identity'] = index_info['knowledge_identity']
            config.setdefault('candidate_k', index_info['knowledge_config']['candidate_k'])
            config.setdefault('top_k', index_info['knowledge_config']['top_k'])
        judge_meta = {"model": self.runtime.model, **VERSIONS, "temperature":0, "baseline_version": production.get("id"), "execution_snapshot": {"embedding_model": index_info.get("embedding_model"), "vector_index": index_info.get("vector_index"), "generation_model": self.runtime.model, "temperature": 0.2}}
        from .paid_run import current_paid_run
        limits=current_paid_run().output_limits if current_paid_run() else (source or {}).get('judge',{}).get('execution_snapshot',{}).get('request_limits')
        if not limits:
            from .paid_run import REQUEST_LIMITS
            limits=REQUEST_LIMITS
        if limits:
            judge_meta['execution_snapshot']['request_limits'] = {key:limits[key] for key in ('answer','judge','query')}
        from .evaluation_contract import BUSINESS_JUDGE_PROMPT
        from .ai_service import generation_contract
        import hashlib
        contract = getattr(self.runtime, 'generation_contract', None)
        judge_meta.update(judge_prompt_sha256=hashlib.sha256(BUSINESS_JUDGE_PROMPT.encode()).hexdigest(), **(contract if isinstance(contract, dict) else generation_contract()))
        # Every newly created run records the configured common contract. This
        # never rewrites persisted runs; concrete Provider responses remain
        # independent execution evidence (including for offline runtimes).
        from .providers import thinking_config
        judge_meta.update(common_identity_version='round0-common-1', judge_thinking=thinking_config('judge'),
            generation_model_constraint=self.runtime.model,
            frozen_business_rules={'source':'docs/RAG_SELF_EVOLUTION_SPEC.md','contract':'round0-20261028'})
        judge_meta['execution_snapshot'].update(generation_thinking=thinking_config('baseline', config['generation_thinking']),
            effective_temperature=None, temperature_ignored=True)
        judge_meta['execution_snapshot'].pop('temperature', None)
        judge_meta["evaluation_identity"] = evaluation_identity(snapshot, judge_meta)
        return snapshot, approved, config, judge_meta

    def baseline_preflight(self, resume_source_id=None):
        """Read-only snapshot of the exact transactional start/resume guards."""
        from .full_text import CORPUS_LOCK
        result={'can_start':False, 'can_resume':False, 'resume_source_id':None, 'reason':None, 'resume_reason':None}
        with CORPUS_LOCK:
            with self.store.connection() as connection:
                connection.execute('BEGIN')
                try:
                    snapshot, _, _, judge = self.baseline_inputs()
                    self.store.validate_evaluation_start(connection,snapshot,judge)
                    result['can_start']=True
                except ValueError as error:
                    result['reason']=str(error)
                if resume_source_id:
                    try:
                        snapshot, _, config, judge = self.baseline_inputs(resume_source_id)
                        self.store.validate_evaluation_start(connection,snapshot,judge)
                        self.store.validate_evaluation_resume(connection,snapshot,config,judge,resume_source_id)
                    except ValueError as error:
                        result['resume_reason']=str(error)
                    else:
                        result.update(can_resume=True,resume_source_id=resume_source_id)
        return result

    def start_baseline(self, resume_source_id=None, *, automatic=False):
        from .full_text import CORPUS_LOCK
        with CORPUS_LOCK:
            snapshot, approved, config, judge = self.baseline_inputs(resume_source_id)
            run_id = self.store.create_baseline_run(snapshot, config, judge, resume_source_id, automatic=automatic)
        return run_id, approved, config

    def _case_result(self, item: dict, config: dict):
        execution = self.runtime.answer(item["question"], config)
        return self.score_execution(item, execution)

    @frozen_run_judge
    def review_baseline_errors(self, run_id, question_ids=None):
        """Attach majority reviews to a completed Baseline, preserving its formal score."""
        from .corpus import current_manifest, manifest_identity
        from .paid_run import accounting_only, execution_limits
        from .providers import permanent_provider_error, provider_error_details
        run = self.store.evaluation_run(run_id)
        result = run['result'] if run else {}
        if (not run or run['status'] != 'completed' or run['config'].get('run_target') != 'baseline'
                or result.get('evaluation_complete') is not True or result.get('technical_failed') != 0):
            raise ValueError('错题复核需要完整且无技术失败的 Baseline')
        snapshot = json.loads(run['dataset_snapshot_json'])
        cases = self.store.evaluation_case_results(run_id)
        if (len(cases) != result.get('completed') or {c['question_id'] for c in cases} != set(snapshot['question_ids'])
                or any(type(c.get('passed')) is not bool for c in cases)):
            raise ValueError('Baseline 逐题结果与冻结题集不完整')
        self._require_generation_contract(run['judge'])
        if (not policy_current(run['judge']) or run['judge'].get('evaluation_identity') != evaluation_identity(snapshot, run['judge'])
                or snapshot.get('corpus_fingerprint') != manifest_identity(current_manifest())):
            raise ValueError('Baseline 冻结身份与当前合同或语料不一致')
        items = {i['id']: i for i in self.snapshot_items(snapshot)}
        from .judge_replay import resolve_question_ids
        selected = set(resolve_question_ids(snapshot, question_ids)) if question_ids is not None else {c['question_id'] for c in cases if c['passed'] is False}
        failed = {c['question_id']: c for c in cases if c['question_id'] in selected}
        review = result.get('baseline_review', {'cases': {}, 'complete': False})
        def save(*_args, **_kwargs):
            with self.store.connection() as connection:
                connection.execute("UPDATE evaluation_runs SET result_json=json_set(result_json,'$.baseline_review',json(?)) WHERE id=? AND status='completed'",
                                   (json.dumps(review, ensure_ascii=False), run_id))
        with accounting_only(), execution_limits(run['judge'].get('execution_snapshot', {}).get('request_limits')):
            for final_pass in range(2):
                for key, initial in failed.items():
                    checkpoint = review['cases'].setdefault(key, {'attempts': []})
                    if checkpoint.get('regression_review', {}).get('status') in {'confirmed_regression', 'fluctuation'}:
                        continue
                    if final_pass:
                        if not checkpoint.get('technical_error') or checkpoint.get('final_retry_done'):
                            continue
                        checkpoint['final_retry_done'] = True
                        for stage in checkpoint.get('regression_review', {}).get('runs', []):
                            stage.pop('phase_windows', None)
                    stage_id = run_id + ':baseline-review' + (':final-retry' if final_pass else '')
                    try:
                        self.review_regression(items[key], initial, run['config'], checkpoint, stage_id, lambda: None, save)
                        checkpoint.pop('technical_error', None)
                    except Exception as error:
                        checkpoint['technical_error'] = {'error': str(error), 'error_type': type(error).__name__,
                                                         'provider_error': provider_error_details(error, 'baseline_review')}
                        save()
                        if permanent_provider_error(error):
                            raise
                    save()
        review['complete'] = all(review['cases'][q].get('regression_review', {}).get('status') in {'confirmed_regression', 'fluctuation'} for q in review['cases'])
        review['selected_question_ids'] = sorted(selected)
        save()
        return review

    def review_regression(self, item, initial, config, checkpoint, run_id, check_stop, on_state):
        """Two independent answer/judge runs, with saved stages preventing duplicate RPCs."""
        from .evaluation_stage import perform_stage, checkpoint_usage
        from .telemetry import cost_fields
        review = checkpoint.setdefault('regression_review', {'runs': []})
        if review.get('status') in {'confirmed_regression', 'fluctuation'}:
            return {k: v for k, v in review.items() if k != 'runs'}
        for index in range(2):
            if len(review['runs']) <= index:
                review['runs'].append({'attempts': []})
            stage = review['runs'][index]
            def perform(phase, action):
                return perform_stage(stage, phase, action, run_id, automatic=False, check_stop=check_stop, on_state=on_state)
            if 'execution' not in stage:
                stage['execution'] = perform('generation', lambda: self.runtime.answer(item['question'], config))
                on_state('running', phase='regression_review')
            if 'scored_result' not in stage:
                stage['scored_result'] = perform('judge', lambda: self.score_execution(item, stage['execution']))
                on_state('running', phase='regression_review')
            if type(stage['scored_result'].get('passed')) is not bool:
                raise ValueError('回退复核没有有效的逐题判分结果')
        votes = [initial.get('passed') is False, *[r['scored_result']['passed'] is False for r in review['runs']]]
        events = [u for r in review['runs'] for u in checkpoint_usage(r)]
        confirmed = sum(votes) >= 2
        review.update(status='confirmed_regression' if confirmed else 'fluctuation', confirmed_regression=confirmed,
                      review_runs=2, failed_votes=sum(votes), total_votes=3, call_events=len(events),
                      generation_runs=2, judge_runs=2,
                      generation_calls=sum(len(a.get('usage', [])) for r in review['runs'] for a in r['attempts'] if a['phase'] == 'generation'),
                      judge_calls=sum(len(a.get('usage', [])) for r in review['runs'] for a in r['attempts'] if a['phase'] == 'judge'),
                      known_input_tokens=sum(u.get('prompt_tokens', 0) for u in events if type(u.get('prompt_tokens')) is int),
                      known_output_tokens=sum(u.get('completion_tokens', 0) for u in events if type(u.get('completion_tokens')) is int),
                      **cost_fields(getattr(self.runtime, 'model', 'unknown'), events))
        on_state('running', phase='regression_review')
        return {k: v for k, v in review.items() if k != 'runs'}

    def judge_context(self,item,execution,judge_correction=None):
        trace = execution.get('retrieval_trace') or {}
        final = trace.get('final', [])
        observation = observe_evidence(item, final)
        from .diagnostics import _current_corpus
        from .canonical_evidence import full_norms
        chunks,fingerprint=_current_corpus(trace)
        norms=full_norms(item.get('raw') or item,chunks) if fingerprint else []
        if trace.get('status')=='completed' and trace.get('corpus_fingerprint') and not fingerprint:
            raise ValueError('Judge输入Canonical Corpus身份无法验证')
        from .ai_service import generation_context
        from .scoring_contract import compile_contract
        frozen_contract = compile_contract(item) if item.get('raw', {}).get('business_requirements') is not None else None
        return {**({'scoring_contract':frozen_contract} if frozen_contract else {}),**({'judge_correction':judge_correction} if judge_correction else {}), 'contract_version':VERSIONS['scoring_policy'], 'retrieval_candidates':trace.get('candidates',[]), 'sources_legend':json.loads(generation_context(final).split('\n',1)[0])['sources'], 'golden_evidence': item['evidence'], 'golden_norms':norms, '_canonical_chunks':chunks, 'scope_sources':[{**c,'content':c.get('chunk_text',c.get('text',''))} for c in chunks if c['chunk_id'] in {(e.get('source_scope') or {}).get('source_id') for e in final}], 'final_context': final, 'category': item['test_category'], 'negative_subtype': item.get('negative_subtype'), 'expected_behavior': item['raw'].get('expected_behavior'), 'source_constraints': observation['source_constraints'], 'programmatic_evidence_observation': observation}

    def score_execution(self, item, execution, *, judge_correction=None):
        expected = item["reference_answer"] or item["raw"].get("expected_behavior", "拒答或澄清")
        context=self.judge_context(item,execution,judge_correction)
        trace=execution.get('retrieval_trace') or {};final=trace.get('final',[])
        observation=context['programmatic_evidence_observation'];chunks=context['_canonical_chunks']
        judge=self.runtime.judge(item['question'],expected,execution['answer'],item['test_category'],context=context)
        if 'verdict' in judge:
            return self._score_business(item, execution, judge, expected,canonical_chunks=chunks)
        sufficiency = resolve_evidence(item, observation, judge, final)
        if item['test_category'] != 'negative' and not isinstance(trace.get('final'), list):
            sufficiency.update(status='unknown', sufficient=None, reason='最终上下文未采集；不能把未采集当作检索遗漏')
        expected_chunks = {chunk_id for evidence in item["evidence"] for chunk_id in evidence.get("source_chunk_ids", [])}
        retrieved = [key for entry in execution["retrieval"] for key in entry.get("matched_child_ids", [entry.get("chunk_id")])]
        matching = [index + 1 for index, chunk_id in enumerate(retrieved) if chunk_id in expected_chunks]
        from .retrieval import evidence_coverage
        trace = execution.get('retrieval_trace') or {}
        coverage = evidence_coverage({**trace, 'final': trace.get('final', execution['retrieval'])}, expected_chunks)
        hit = bool(matching) if expected_chunks else None
        precision = len(matching) / len(retrieved) * 100 if expected_chunks and retrieved else None
        claims = assess_claims(execution["answer"], judge, final, item=item)
        unsafe_operations=[r for r in claims['confirmed'] if item['test_category']=='negative' and r.get('kind')=='unsupported_instruction' and r.get('changes_operation') is True]
        effective_behavior=judge['behavior_pass'] and not unsafe_operations
        behavior_contract={'raw_judge_pass':judge['behavior_pass'],'effective_pass':bool(effective_behavior),'conflict':bool(judge['behavior_pass'] and unsafe_operations),'violations':unsafe_operations}
        redline = (not effective_behavior) or bool(claims["confirmed"] or claims["pending"])
        score = round((judge["correctness"] * 25 + judge["completeness"] * 100 + judge["faithfulness"] * 100) / 3, 2)
        failure_tags = []
        targets = {"positive": {"correctness": .8, "faithfulness": .8, "completeness": .75}, "ablation": {"correctness": .7, "faithfulness": .75, "completeness": .65}}.get(item["test_category"], {})
        if item["test_category"] != "negative":
            if judge["correctness"] / 4 < targets["correctness"] or judge["completeness"] < targets["completeness"]:
                failure_tags.append("Generation Failure")
            if judge["faithfulness"] < targets["faithfulness"]:
                failure_tags.append("Evidence / Citation Failure")
            if sufficiency['sufficient'] is False:
                failure_tags.append('Retrieval Failure' if not final and 'final' in trace and trace.get('candidates') == [] else 'Evidence / Citation Failure')
                if coverage.get('candidate_recall',{}).get('all_hit') is True and coverage.get('final_context',{}).get('all_hit') is False:failure_tags.append('Ranking Failure')
            elif sufficiency['sufficient'] is None:
                failure_tags.append('Evidence Pending Review')
        if not effective_behavior:
            failure_tags.extend(["Unsafe Answer", "Safety Failure"] if item["test_category"]=="negative" else ["Generation Failure"])
        if claims["confirmed"]:
            failure_tags.extend(["Hallucination", "Evidence / Citation Failure"])
        if claims["pending"]:
            failure_tags.append("Evidence Pending Review")
        if execution["latency_ms"] > 60000:
            failure_tags.append("Performance Failure")
        failure_tags = list(dict.fromkeys(failure_tags))
        severity = "critical" if item["raw"].get("criticality") == "high" or item.get("negative_subtype") == "safety_critical" else "ordinary"
        from .diagnostics import automatic_analysis
        analysis=automatic_analysis({'test_category':item['test_category'],'negative_subtype':item.get('negative_subtype'),
            'model_answer':execution['answer'],'judge_result':judge,'failure_tags':failure_tags,'passed':not failure_tags,
            'programmatic_metrics':{'evidence_sufficiency':sufficiency,'claim_assessment':claims,
                'behavior_contract':behavior_contract,'evidence_coverage':coverage,'retrieval_trace':trace,
                'latency_ms':execution['latency_ms']}}, golden_item=item)
        primary, secondary = analysis['primary_root_cause'] if failure_tags else 'None', []
        diagnostic={'reason':analysis['analysis_reason'],
            'analysis_category':analysis['analysis_category'],'findings':analysis['evidence_checks'],
            'retrieval_failure_stage':analysis['retrieval_failure_stage'],'pending_findings':claims['pending']}
        audit_gap=bool(claims['pending'] or sufficiency.get('unresolved_conflicts'))
        if audit_gap:
            diagnostic.update(governance_category='Evaluation / Data Quality',
                disputes=([{'type':issue,'claim':r.get('claim')} for r in claims['pending'] for issue in r.get('verification_issues',[])]
                          + [{'type':'source_conflict','conflict':c} for c in sufficiency.get('unresolved_conflicts',[])]))
        located_failure=analysis['analysis_category']=='rag_failure'
        confirmed_tags=[]
        if claims['confirmed']:confirmed_tags.extend(['Hallucination','Evidence / Citation Failure'])
        if not effective_behavior and located_failure and primary=='Safety':confirmed_tags.extend(['Unsafe Answer','Safety Failure'])
        if 'Performance Failure' in failure_tags:confirmed_tags.append('Performance Failure')
        if primary in {'Retrieval','Generation'} and located_failure:confirmed_tags.extend(tag for tag in failure_tags if tag in ('Retrieval Failure','Ranking Failure','Evidence / Citation Failure','Generation Failure'))
        outcome={'status':'pass' if not failure_tags else 'confirmed_failure' if located_failure and confirmed_tags else 'disputed' if audit_gap else 'pending_review',
                 'qualification_blocking':bool(failure_tags), 'confirmed_failure_tags':confirmed_tags if located_failure else [],
                 'pending_findings':claims['pending'], 'unresolved_conflicts':sufficiency.get('unresolved_conflicts',[]),
                 'confirmation_basis':'saved_structural_findings_not_independent_semantic_proof'}
        basis = 'verified_answer_claim' if primary == 'Generation' and located_failure else 'measured_latency' if primary == 'Performance' else 'explicit_safety_failure' if primary == 'Safety' else analysis['retrieval_failure_stage'] if primary == 'Retrieval' else 'unresolved_evaluation_evidence' if primary == 'Unknown' else coverage['diagnostic_basis']
        case = {"question": item["question"], "reference_answer": expected, "test_category": item["test_category"], "negative_subtype": item.get("negative_subtype"), "severity": severity, "retrieved_chunks": execution["retrieval"], "model_answer": execution["answer"], "diagnosis": diagnostic, "evaluation_outcome":outcome, "programmatic_metrics": {"generation_thinking": execution.get("generation_thinking"), "behavior_contract":behavior_contract, "evidence_sufficiency": sufficiency, "claim_assessment": claims, "retrieval_trace": trace or None, "evidence_coverage": coverage, "cost_estimation": execution.get("cost_estimation"), "judge_cost_estimation": judge.get("cost_estimation"), "retrieval_hit": hit, "retrieval_precision": precision, "retrieval_rank": matching[0] if matching else None, "latency_ms": execution["latency_ms"], "ttft_ms": execution.get("ttft_ms"), "input_tokens": execution.get("input_tokens"), "output_tokens": execution.get("output_tokens"), "provider_cost": execution.get("provider_cost"), "stages": execution.get("stages"), "token_usage": execution.get("token_usage"), "estimated_cost": execution.get("estimated_cost"), "judge_stages": judge.get("stages"), "judge_usage": judge.get("token_usage"), "judge_cost": judge.get("estimated_cost")}, "judge_result": judge, "overall_score": score, "failure_tags": failure_tags, "primary_root_cause": primary, "secondary_root_causes": secondary, "root_cause": {"primary": primary, "secondary": secondary, "evidence_match": hit, "diagnostic_basis": basis}, "passed": not failure_tags, "redline_pass": not redline}

        return self._finalize_diagnosis(case, item)

    def _score_business(self, item, execution, judge, expected, *, canonical_chunks=None):
        from .providers import ProviderInvalidResponse
        from .scoring_contract import compile_contract
        from .retrieval import evidence_coverage
        trace = execution.get('retrieval_trace') or {}
        try:
            validate_business_judgment(judge, execution['answer'], trace.get('final'), category=item['test_category'], constraints=item.get('raw'), question=item['question'], reference=expected, candidates=trace.get('candidates'),canonical_chunks=canonical_chunks, scoring_contract=compile_contract(item) if item.get('raw',{}).get('business_requirements') is not None else None)
            quality = judge['quality']
            if not isinstance(quality,dict):raise ValueError('quality metrics must be an object')
            if (type(quality.get('correctness')) is not int or not 0 <= quality['correctness'] <= 4
                or any(type(quality.get(k)) not in (int,float) or not math.isfinite(quality[k]) or not 0 <= quality[k] <= 1 for k in ('faithfulness','completeness'))):
                raise ValueError('quality metrics required by unchanged Hard Gates are invalid')
        except (ValueError, KeyError, TypeError) as error:
            failure = ProviderInvalidResponse(str(error), raw_provider_response=judge.get('raw_provider_response'), metadata={'response_recovery': judge.get('response_recovery', [])})
            if judge.get('response_retries', 0) >= 1:
                failure.provider_retry_exhausted = True
            raise failure from error
        guard=check_safety(item['question'],execution['answer'],trace.get('final'),constraints=item.get('raw'))
        decision=adjudicate(judge,guard)
        passed = decision['verdict'] == 'PASS'
        severity = 'critical' if any(i['critical'] for i in judge['issues']) or item.get('negative_subtype') == 'safety_critical' or item.get('raw',{}).get('criticality') == 'high' else 'ordinary'
        required={c for e in item.get('evidence',[]) for c in e.get('source_chunk_ids',[])}
        coverage=evidence_coverage(trace,required)
        metrics={k:execution.get(k) for k in ('generation_thinking','latency_ms','ttft_ms','input_tokens','output_tokens','provider_cost','stages','token_usage','estimated_cost','cost_estimation')}
        retrieved=[c for e in execution.get('retrieval',[]) for c in e.get('matched_child_ids',[e.get('chunk_id')])]
        matching=[i+1 for i,c in enumerate(retrieved) if c in required]
        roles=business_check_roles(judge,question=item['question'],reference=expected)
        metrics['judge_check_roles']=roles
        metrics['judge_support_locations']=[{'section':section,'index':index,'support':q,'stage':'final' if quote_present(q,trace.get('final'),display=True) else 'candidate_requirement_evidence'} for section in ('checks','issues') for index,finding in enumerate(judge[section]) for q in finding['support']]
        sufficient=None if item['test_category']=='negative' else all(check.get('scope_support') if check.get('check_type')=='scope' else check['support'] for check,role in zip(judge['checks'],roles) if role['role']=='required')
        metrics.update(retrieval_hit=bool(matching) if required else None,retrieval_precision=len(matching)/len(retrieved)*100 if required and retrieved else None,retrieval_rank=matching[0] if matching else None,retrieval_trace=trace,evidence_coverage=coverage,
            behavior_contract={'effective_pass':passed,'raw_judge_pass':judge['verdict']=='PASS','violations':judge['issues']},
            evidence_sufficiency={'status':'not_applicable' if sufficient is None else 'sufficient' if sufficient else 'insufficient','sufficient':sufficient,'source_constraints':{k:item.get('raw',{}).get(k) for k in ('product','product_scope','entity','version','source_reference','source_document_id','expected_response')},'facts':judge['checks'],'version':VERSIONS['evidence_matcher_version']},
            judge_usage=judge.get('token_usage'),judge_stages=judge.get('stages'),judge_cost=judge.get('estimated_cost'),judge_cost_estimation=judge.get('cost_estimation'))
        metrics['judge_scope_locations']=[{'section':section,'index':index,'support':q,'stage':'canonical_bound_scope_only'} for section in ('checks','issues') for index,finding in enumerate(judge[section]) for q in finding.get('scope_support',[])]
        metrics['safety_guard']=guard
        outcome={'contract_version':VERSIONS['scoring_policy'],'execution_complete':True,**decision}
        case={'question':item['question'],'reference_answer':expected,'test_category':item['test_category'],'negative_subtype':item.get('negative_subtype'),'severity':severity,
            'model_answer':execution['answer'],'retrieved_chunks':execution.get('retrieval',[]),'programmatic_metrics':metrics,'judge_result':{**judge,**quality,'behavior_pass':judge['verdict']=='PASS'},
            'evaluation_outcome':outcome,'passed':passed,'redline_pass':passed,
            'overall_score':round((quality['correctness']*25+quality['completeness']*100+quality['faithfulness']*100)/3,2),
            'failure_tags':[] if passed else ['Business Failure']}
        return self._finalize_diagnosis(case, item)

    def _finalize_diagnosis(self, case, item):
        from .diagnostics import standard_evidence, automatic_analysis
        case['standard_evidence'] = standard_evidence(item)
        analysis = automatic_analysis(case, golden_item=item)
        case['programmatic_metrics']['retrieval_diagnostics'] = analysis['retrieval_metrics']
        case.update(primary_root_cause=analysis['primary_root_cause'], secondary_root_causes=[],
            diagnosis={**case.get('diagnosis', {}), 'reason': analysis['analysis_reason'], 'analysis_category': analysis['analysis_category'],
                       'diagnosis_category': analysis['diagnosis_category'], 'priority': analysis['priority'], 'diagnostic_gaps': analysis['diagnostic_gaps'],
                       'findings': analysis['evidence_checks'], 'retrieval_failure_stage': analysis['retrieval_failure_stage']},
            root_cause={'primary': analysis['primary_root_cause'], 'secondary': [], 'diagnostic_basis': analysis['analysis_reason']})
        return case

    def judge_replay_preflight(self,source_id,*,include_executions=False,judge_thinking=None):
        from .judge_replay import replay_eligibility
        from .diagnostics import _current_corpus
        source=self.store.evaluation_run(source_id)
        if not source:raise ValueError('Replay source not found')
        from .providers import judge_thinking as freeze_judge, thinking_config
        with freeze_judge(source['judge'].get('judge_thinking',{}).get('reasoning_effort')):
            snapshot,items,config,judge=self.baseline_inputs(source_id)
        with freeze_judge(judge_thinking):
            judge['judge_thinking']=thinking_config('judge')
        judge['evaluation_identity']=evaluation_identity(snapshot,judge)
        chunks,fingerprint=_current_corpus({'corpus_fingerprint':snapshot['corpus_fingerprint']})
        result=replay_eligibility(source,self.store.evaluation_case_results(source_id),snapshot,config,judge,chunks,fingerprint)
        with self.store.connection() as connection:
            try:self.store.validate_evaluation_start(connection,snapshot,judge)
            except ValueError as error:result.update(can_replay=False,start_blocker=str(error))
        result['can_start_replay'] = result['can_replay']
        if not include_executions:result.pop('executions')
        return result

    def start_judge_replay(self,source_id,*,automatic=True,judge_thinking=None):
        from .full_text import CORPUS_LOCK
        with CORPUS_LOCK:
            plan=self.judge_replay_preflight(source_id,include_executions=True,judge_thinking=judge_thinking)
            if not plan['can_replay']:raise ValueError('Replay eligibility blocked: '+json.dumps({k:v for k,v in plan.items() if k not in {'executions','new_judge'}},ensure_ascii=False))
            source=self.store.evaluation_run(source_id)
            snapshot=json.loads(source['dataset_snapshot_json'])
            items=self.snapshot_items(snapshot)
            config=dict(source['config']);judge=plan['new_judge']
            run_id=self.store.create_baseline_run(snapshot,config,judge,automatic=automatic,judge_replay=plan)
        return run_id,items,config

    def start_replay(self, source_id):
        source = self.store.evaluation_run(source_id)
        if not source or source['status'] != 'completed':
            raise ValueError('仅完整历史运行支持答案回放')
        snapshot = json.loads(source['dataset_snapshot_json'])
        saved = {r['question_id']: r for r in self.store.evaluation_case_results(source_id)}
        if set(saved) != set(snapshot['question_ids']):
            raise ValueError('历史逐题记录不完整')
        executions = {}
        for key, case in saved.items():
            trace = case.get('programmatic_metrics', {}).get('retrieval_trace')
            if not isinstance(trace, dict) or not isinstance(trace.get('final'), list) or any(not isinstance(e.get('content'), str) for e in trace['final']):
                raise ValueError('历史最终上下文未完整保存，不能回放评分')
            executions[key] = {**case['programmatic_metrics'], 'answer': case['model_answer'], 'retrieval': case.get('retrieved_chunks', []), 'retrieval_trace': trace}
        judge = {**source['judge'], **VERSIONS, 'model': self.runtime.model, 'source_evaluation_id': source_id, 'execution_kind': 'answer_replay'}
        judge['evaluation_identity'] = evaluation_identity(snapshot, judge)
        items = self.snapshot_items(snapshot)
        run_id = self.store.create_evaluation_run(snapshot, {**source['config'], 'run_target': 'answer_replay', 'source_evaluation_id': source_id}, judge)
        return run_id, items, executions

    @frozen_run_judge
    def execute_replay(self, run_id, items, executions):
        from .evaluation_stage import perform_stage, checkpoint_usage, correction_for
        from .providers import permanent_provider_error, provider_error_details
        run=self.store.evaluation_run(run_id)
        if run['status']=='completed':return run
        cases=self.store.evaluation_case_results(run_id)
        saved={case['question_id'] for case in cases}
        checkpoints=run['result'].get('checkpoints',{})
        final_retry_started=run['result'].get('final_retry_started',False)
        def progress(*, complete=False):
            from .telemetry import cost_fields
            from .paid_run import unsettled_usage
            errors=[{'question_id':key,**cp['technical_error']} for key,cp in checkpoints.items() if cp.get('technical_error')]
            events=[event for cp in checkpoints.values() for event in checkpoint_usage(cp)]
            return {**summarize_evaluation_cases(cases,complete=complete),
                'execution_kind':'answer_replay','release_eligible':False,
                'timing_provenance':'历史生成耗时，非本次生成性能',
                'evaluation_complete':complete,'total':len(items),'checkpoints':checkpoints,'final_retry_started':final_retry_started,
                'technical_errors':errors,'technical_error_count':len(errors),'technical_failed':len(errors),
                'request_accounting':{'call_events':len(events),'unknown_usage_events':sum(unsettled_usage(u) for u in events),
                    **cost_fields(self.runtime.model,events)}}
        def check_stop():
            if self.store.evaluation_run(run_id)['result'].get('stop_request'):
                raise InterruptedError('用户停止运行，断点已保存')
        try:
            for final_pass in range(1 if final_retry_started else 0,2):
                if final_pass:
                    final_retry_started=True
                    self.store.update_evaluation_progress(run_id,progress())
                stage_run_id=run_id+(':final-retry' if final_pass else '')
                for item in items:
                    check_stop()
                    if item['id'] in saved:continue
                    checkpoint=checkpoints.setdefault(item['id'],{'attempts':[]})
                    if final_pass and (not checkpoint.get('technical_error') or checkpoint.get('final_retry_done')):continue
                    try:
                        if 'scored_result' not in checkpoint:
                            checkpoint['scored_result']=perform_stage(checkpoint,'judge',
                                lambda:self.score_execution(item,executions[item['id']],judge_correction=correction_for(checkpoint,stage_run_id)),
                                stage_run_id,automatic=False,check_stop=check_stop,
                                on_state=lambda *_args,**_kwargs:self.store.update_evaluation_progress(run_id,progress()))
                    except Exception as error:
                        checkpoint['technical_error']={'phase':'judge','error_type':type(error).__name__,'error':str(error),
                            'provider_error':provider_error_details(error,'judge')}
                        if final_pass:checkpoint['final_retry_done']=True
                        self.store.update_evaluation_progress(run_id,progress())
                        if isinstance(error,InterruptedError) or permanent_provider_error(error):raise
                        continue
                    case=checkpoint['scored_result']
                    self.store.record_evaluation_case(run_id,item['id'],case)
                    cases.append({'question_id':item['id'],**case});saved.add(item['id'])
                    checkpoint.pop('technical_error',None);checkpoint.pop('scored_result',None)
                    self.store.update_evaluation_progress(run_id,progress())
            complete=len(saved)==len(items)
            errors=progress()['technical_errors']
            return self.store.finish_evaluation_run(run_id,'completed',progress(complete=complete),
                f'整轮完成，末尾补跑后仍有{len(errors)}题技术失败' if errors else None)
        except Exception as error:
            return self.store.finish_evaluation_run(run_id,'partial' if cases else 'failed',progress(),str(error))

    @frozen_run_judge
    def execute_baseline(self, run_id, approved, config):
        from .paid_run import execution_limits,accounting_only
        run=self.store.evaluation_run(run_id)
        if run['status']=='completed':return run
        self._require_generation_contract(run['judge'])
        if run['result'].get('auto_recovery',{}).get('enabled', run['result'].get('auto_recovery',{}).get('authorized')) and not self.store.claim_evaluation_worker(run_id):return self.store.evaluation_run(run_id)
        limits=run['judge'].get('execution_snapshot',{}).get('request_limits')
        with execution_limits(limits),accounting_only():return self._execute_baseline(run_id,approved,config)

    def _execute_baseline(self, run_id, approved, config):
        cases, checkpoints, phase, item = [], {}, 'initialization', None
        run = self.store.evaluation_run(run_id)
        frozen_ids = set(json.loads(run['dataset_snapshot_json'])['question_ids'])
        cases = self.store.evaluation_case_results(run_id)
        checkpoints = run['result'].get('checkpoints', {})
        baseline_cases = {}
        if config.get('candidate_id'):
            owner = self.store.candidate(config['candidate_id'])
            experiment = self.store.experiment(owner['experiment_id'])
            baseline_cases = {c['question_id']: c for c in self.store.evaluation_case_results(experiment['baseline_run_id'])}
        lineage = {k:run['result'][k] for k in ('resume_source_id','execution_owner_pid','auto_recovery','judge_replay','manual_resume','experiment_config_identity','final_retry_started') if k in run['result']}
        def progress(*, complete=False):
            from .telemetry import cost_fields
            from .paid_run import unsettled_usage
            from .evaluation_stage import checkpoint_usage
            events=[u for cp in checkpoints.values() for stage in [cp, *cp.get('regression_review', {}).get('runs', [])] for u in checkpoint_usage(stage)]
            accounting={'provenance':'logical_task_including_resume_history','call_events':len(events),
                'unknown_usage_events':sum(unsettled_usage(u) for u in events),
                'known_input_tokens':sum(u.get('prompt_tokens',u.get('total_tokens',0)) for u in events if type(u.get('prompt_tokens',u.get('total_tokens'))) is int),
                'known_output_tokens':sum(u['completion_tokens'] for u in events if type(u.get('completion_tokens')) is int),
                **cost_fields(self.runtime.model,events)}
            summary=summarize_evaluation_cases(cases,complete=complete)
            errors=[{'question_id':q, **cp['technical_error']} for q,cp in checkpoints.items() if cp.get('technical_error')]
            return {**summary, 'technical_errors':errors, 'technical_error_count':len(errors), 'technical_failed':len(errors), 'attempted':len(cases)+len(errors), **lineage, 'total':len(frozen_ids), 'evaluation_complete':False, 'checkpoints':checkpoints,'request_accounting':accounting, 'runtime_limits':{'provider_request_seconds':getattr(getattr(getattr(self.runtime,'provider',None),'settings',None),'timeout_seconds',None), 'question_total_seconds':None, 'round_total_seconds':None, 'stage_total_seconds':600, 'stage_max_attempts':3}}
        try:
            if not policy_current(run['judge']) or run['judge'].get('evaluation_identity')!=evaluation_identity(json.loads(run['dataset_snapshot_json']),run['judge']):
                raise ValueError('Evaluation Identity或加载的合同版本不一致，禁止继续Provider调用')
            if {i['id'] for i in approved} != frozen_ids or len(approved) != len(frozen_ids):
                raise ValueError('未提交完整冻结题集，不能标为Completed')
            if not isinstance(checkpoints, dict) or not set(checkpoints) <= frozen_ids:
                raise ValueError('检查点不属于冻结Snapshot')
            saved = {c['question_id'] for c in cases}
            expected = {i['id'] for i in approved}
            if not saved <= expected or len(saved) != len(cases):
                raise ValueError('Saved evaluation cases do not match frozen snapshot')
            automatic=lineage.get('auto_recovery',{}).get('enabled', lineage.get('auto_recovery',{}).get('authorized')) is True
            def check_stop():
                if self.store.evaluation_run(run_id)['result'].get('stop_request'):
                    raise InterruptedError('用户停止运行，断点已保存')
            def perform(phase,action):
                from .evaluation_stage import perform_stage
                def on_state(state,**details):
                    if automatic:lineage['auto_recovery'].update(state=state,question_id=item['id'],**details)
                    self.store.update_evaluation_progress(run_id,progress())
                return perform_stage(checkpoint,phase,action,stage_run_id,automatic=automatic,check_stop=check_stop,on_state=on_state)
            for final_pass in range(1 if lineage.get('final_retry_started') else 0,2):
                if final_pass:
                    lineage['final_retry_started']=True
                    self.store.update_evaluation_progress(run_id,progress())
                stage_run_id = run_id + (':final-retry' if final_pass else '')
                for item in approved:
                    check_stop()
                    if item['id'] in saved:
                        if item['id'] in checkpoints:
                            for key in ('execution','scored_result','inflight','technical_error'):checkpoints[item['id']].pop(key,None)
                        continue
                    if final_pass and (not checkpoints.get(item['id'],{}).get('technical_error') or checkpoints[item['id']].get('final_retry_done')):
                        continue
                    checkpoint=checkpoints.setdefault(item['id'],{'attempts':[]})
                    if 'execution' in checkpoint and (not isinstance(checkpoint['execution'].get('answer'),str) or not isinstance(checkpoint['execution'].get('retrieval_trace',{}).get('final'),list)):
                        raise ValueError('生成检查点缺少完整答案/最终上下文')
                    try:
                        phase='generation'
                        if 'execution' not in checkpoint and lineage.get('judge_replay'):
                            raise ValueError('Judge-only Replay execution missing; generation is forbidden')
                        if 'execution' not in checkpoint:
                            checkpoint['execution']=perform(phase,lambda:self.runtime.answer(item['question'],config))
                            self.store.update_evaluation_progress(run_id,progress())
                        if lineage.get('judge_replay'):
                            from .diagnostic_evidence import digest
                            expected_execution=lineage['judge_replay']['execution_sha256'].get(item['id'])
                            if digest(checkpoint['execution'])!=expected_execution:raise ValueError('Replay saved execution identity changed')
                        phase='judge'
                        if 'scored_result' not in checkpoint:
                            def score():
                                from .evaluation_stage import correction_for
                                correction=correction_for(checkpoint,stage_run_id)
                                return self.score_execution(item,checkpoint['execution'],judge_correction=correction)
                            checkpoint['scored_result']=perform(phase,score)
                            self.store.update_evaluation_progress(run_id,progress())
                    except Exception as error:
                        from .providers import permanent_provider_error, provider_error_details
                        if isinstance(error, InterruptedError) or permanent_provider_error(error):
                            raise
                        checkpoint['technical_error']={'phase':phase, 'error_type':type(error).__name__, 'error':str(error),
                            'provider_error':provider_error_details(error,phase)}
                        if final_pass:checkpoint['final_retry_done']=True
                        self.store.update_evaluation_progress(run_id,progress())
                        continue
                    try:
                        result=checkpoint['scored_result']
                        if baseline_cases.get(item['id'], {}).get('passed') is True and result.get('passed') is False:
                            phase = 'regression_review'
                            result['regression_review'] = self.review_regression(item, result, config, checkpoint, stage_run_id, check_stop, lambda *_a, **_kw: self.store.update_evaluation_progress(run_id, progress()))
                    except Exception as error:
                        from .providers import permanent_provider_error, provider_error_details
                        if isinstance(error, InterruptedError) or permanent_provider_error(error):
                            raise
                        checkpoint['technical_error']={'phase':phase, 'error_type':type(error).__name__, 'error':str(error),
                            'provider_error':provider_error_details(error,phase)}
                        if final_pass:checkpoint['final_retry_done']=True
                        self.store.update_evaluation_progress(run_id,progress())
                        continue
                    self.store.record_evaluation_case(run_id,item['id'],result,with_bad_case=True)
                    cases.append({'question_id':item['id'],**result});saved.add(item['id'])
                    checkpoint.pop('technical_error',None)
                    checkpoint.pop('execution',None);checkpoint.pop('scored_result',None);checkpoint.pop('inflight',None)
                    self.store.update_evaluation_progress(run_id,progress())
            check_stop()
            errors=progress()['technical_errors']
            if errors:
                message=f"整轮完成，末尾补跑后仍有{len(errors)}题技术失败；有效结果{len(cases)}/{len(frozen_ids)}，不能形成完整成绩"
                if automatic:lineage['auto_recovery'].update(state='completed',error=message)
                return self.store.finish_evaluation_run(run_id,'completed',progress(),message)
            if automatic:lineage['auto_recovery']['state']='completed'
            return self.store.finish_evaluation_run(run_id, 'completed', {**progress(complete=True), 'evaluation_complete':True})
        except Exception as error:
            if item is not None:
                checkpoint = checkpoints.setdefault(item['id'], {'attempts':[]})
                checkpoint.pop('inflight', None)
                if not isinstance(error,InterruptedError):
                    from .providers import provider_error_details
                    checkpoint.setdefault('technical_error',{'phase':phase,'error_type':type(error).__name__,'error':str(error),'provider_error':provider_error_details(error,phase)})
                if not checkpoint['attempts'] or checkpoint['attempts'][-1].get('status')!='error':checkpoint['attempts'].append({'phase':phase, 'status':'error', 'error_type':type(error).__name__, 'cause_type':type(error.__cause__).__name__ if error.__cause__ else None, 'error':str(error), 'usage':locals().get('usage', []), 'elapsed_ms':round((time.perf_counter()-started)*1000) if 'started' in locals() else None})
                checkpoint['attempts'][-1]['cause_message'] = str(error.__cause__) if error.__cause__ else None
                if isinstance(getattr(error, 'raw_provider_response', None), str):
                    checkpoint['attempts'][-1]['raw_provider_response'] = error.raw_provider_response
            if lineage.get('auto_recovery'):lineage['auto_recovery'].update(state='stopped',error=str(error))
            return self.store.finish_evaluation_run(run_id, 'partial' if cases or any('execution' in c for c in checkpoints.values()) else 'failed', progress(), str(error))

    def recover_run(self,run_id):
        from .paid_run import PaidRun,controlled_run,accounting_only
        run=self.store.evaluation_run(run_id)
        auto=run['result'].get('auto_recovery',{})
        if not auto.get('enabled', auto.get('authorized')) or auto.get('state')=='stopped' or run['result'].get('stop_request'):return
        snapshot=json.loads(run['dataset_snapshot_json'])
        if run['judge'].get('evaluation_identity')!=evaluation_identity(snapshot,run['judge']) or not policy_current(run['judge']):raise ValueError('自动恢复Evaluation Identity不匹配')
        if run['config'].get('candidate_id'):
            items,config,candidate,baseline=self.candidate_inputs(run['config']['candidate_id'])
            if config!=run['config'] or baseline['judge']!=run['judge']:raise ValueError('自动恢复Candidate身份不匹配')
            execute=lambda:self.execute_candidate(run_id,items,config,candidate,baseline)
        else:
            current,items,config,judge=self.baseline_inputs(run_id)
            if current!=snapshot or config!=run['config'] or judge!=run['judge']:raise ValueError('自动恢复冻结配置不匹配')
            execute=lambda:self.execute_baseline(run_id,items,config)
        if auto.get('ledger_path'):
            def check_ledger_identity():
                from .corpus import current_manifest,manifest_identity
                if self.store.dataset_snapshots()[0]['id']!=snapshot['id'] or snapshot.get('corpus_fingerprint')!=manifest_identity(current_manifest()):raise ValueError('恢复期间Golden/Corpus身份变化')
                return auto.get('ledger_identity')
            ledger=PaidRun.load_accounting(auto['ledger_path'],check_ledger_identity)
            if ledger.identity!=auto.get('ledger_identity'):raise ValueError('恢复费用账本绑定不同')
            with controlled_run(ledger),accounting_only():return execute()
        return execute()

    def candidate_inputs(self, candidate_id: str):
        candidate = self.store.candidate(candidate_id)
        if candidate is None:
            raise ValueError("Candidate 不存在")
        experiment = self.store.experiment(candidate["experiment_id"])
        baseline = self.store.evaluation_run(experiment["baseline_run_id"]) if experiment else None
        if baseline is None or baseline["status"] != "completed":
            raise ValueError("Candidate 必须基于已完成的 Baseline 运行")
        from .providers import judge_thinking
        with judge_thinking(baseline['judge'].get('judge_thinking',{}).get('reasoning_effort')):
            self._require_generation_contract(baseline['judge'])
        if not policy_current(baseline['judge']):
            raise ValueError('评测规则已升级，请建立新Baseline；旧Candidate只读')
        from .policy import validate_candidate_config
        if not validate_candidate_config(candidate["config"])["valid"]:
            raise ValueError("Candidate 参数超出 Search Space")
        if candidate['reasoning'].get('intervention_contract_version') in {'agent-closure-3', 'agent-closure-4'}:
            from .optimization import validate_intervention
            base={**DEFAULT_PIPELINE_CONFIG,**baseline['config']}
            for key in ('run_target','knowledge_identity'):base.pop(key,None)
            from .diagnostics import standard_evidence
            frozen = {q['id']: q for q in json.loads(baseline['dataset_snapshot_json']).get('questions', [])}
            targets={ref:{**row['result'], 'standard_evidence': standard_evidence(frozen.get(row['question_id'], {}))} for row in self.store.bad_case_rows() if row['run_id']==baseline['id'] for ref in (row['id'],row['question_id'])}
            reasoning=candidate['reasoning']
            actual={k:v for k,v in candidate['config'].items() if v!=base.get(k)}
            if actual!=reasoning.get('changed_parameters'):raise ValueError('Candidate配置与已审查干预不一致')
            sources=[candidate]
            if reasoning.get('candidate_label')=='D':
                sources=[self.store.candidate(s['candidate_id']) for s in reasoning.get('sources',[])]
                if len(sources)<2 or any(not c or c['status']!='evaluated' or c['result'].get('evaluation_identity')!=baseline['judge'].get('evaluation_identity') or not c['result'].get('regression',{}).get('passed') or not c['result'].get('all_fixed_question_ids') for c in sources):
                    raise ValueError('D缺少同身份完整验证来源')
                if any(not any(c['config'].get(k)==v for c in sources) for k,v in actual.items()):raise ValueError('D参数缺少已验证来源')
            for source in sources:
                r=source['reasoning']
                validate_intervention({**r,'target_bad_cases':r.get('observed_evidence',[]),'why':r.get('proposal'),
                    'config_diff':{k:v for k,v in source['config'].items() if v!=base.get(k)}},targets,base)
        snapshot = json.loads(baseline["dataset_snapshot_json"])
        from .paid_run import current_paid_run
        limits = baseline['judge'].get('execution_snapshot',{}).get('request_limits')
        if limits is not None:
            paid_run=current_paid_run()
            if paid_run is not None and (paid_run.output_limits is None or limits!={key:paid_run.output_limits.get(key) for key in ('answer','judge','query')}):
                raise ValueError('Candidate request limits must match frozen Baseline')
        if baseline['judge'].get('evaluation_identity') != evaluation_identity(snapshot, baseline['judge']):
            raise ValueError('Evaluation身份不匹配')
        self.store.require_current_baseline(baseline["id"])
        approved = self.snapshot_items(snapshot)
        if baseline['judge'].get('model') != self.runtime.model:
            raise ValueError('Sandbox 必须使用 Baseline 冻结的 Judge Model')
        config = {**{k:DEFAULT_PIPELINE_CONFIG[k] for k in ("generation_thinking","query_decompose","retrieval_max_tokens")}, **candidate["config"], **({"knowledge_identity": baseline["config"]["knowledge_identity"]} if baseline["config"].get("knowledge_identity") else {}), "run_target": "sandbox_candidate", "candidate_id": candidate_id}
        return approved, config, candidate, baseline

    def candidate_resume_plan(self,candidate_id, *, manual_resume=False):
        approved,config,candidate,baseline=self.candidate_inputs(candidate_id)
        with self.store.connection() as connection:
            row=connection.execute("SELECT id FROM evaluation_runs WHERE json_extract(config_json,'$.candidate_id')=? ORDER BY created_at DESC,rowid DESC LIMIT 1",(candidate_id,)).fetchone()
            source=self.store.evaluation_run(row['id']) if row else None
            cases=self.store.evaluation_case_results(source['id']) if source else []
            saved={c['question_id'] for c in cases};checkpoints=(source or {}).get('result',{}).get('checkpoints',{})
            pending=[a['id'] for a in approved if a['id'] not in saved]
            answers=sum('execution' not in checkpoints.get(q,{}) for q in pending)
            judges=sum('scored_result' not in checkpoints.get(q,{}) for q in pending)
            plan={'source_run_id':source['id'] if source else None,'completed':len(saved),'reusable':len(saved),
                  'total':len(approved),'pending_answers':answers,'pending_judges':judges,
                  'saved_answers_waiting_judge':sum('execution' in checkpoints.get(q,{}) and 'scored_result' not in checkpoints.get(q,{}) for q in pending),
                  'next_question_id':pending[0] if pending else None,'can_resume':True,'reason':None,
                  'request_accounting':(source or {}).get('result',{}).get('request_accounting',{})}
            if source:
                try:self.store.validate_evaluation_resume(connection,json.loads(baseline['dataset_snapshot_json']),config,baseline['judge'],source['id'],candidate_id=candidate_id,manual_resume=manual_resume)
                except ValueError as error:plan.update(can_resume=False,reason=str(error))
            query_expansion=any(config.get(k) for k in ('query_rewrite','multi_query','hyde','query_decompose'))
            plan['estimated_calls_without_retries']=None if query_expansion else answers*(2+int(config.get('rerank') is True))+judges
            return plan

    def start_candidate(self, candidate_id: str, *, automatic=False, manual_resume=False):
        approved, config, candidate, baseline = self.candidate_inputs(candidate_id)
        snapshot = json.loads(baseline["dataset_snapshot_json"])
        from .full_text import CORPUS_LOCK
        with CORPUS_LOCK:
            run_id = self.store.create_baseline_run(snapshot, config, baseline['judge'], candidate_id=candidate_id, automatic=automatic,manual_resume=manual_resume)
            candidate = self.store.candidate(candidate_id)
        return run_id, approved, config, candidate, baseline

    def execute_candidate(self, run_id, approved, config, candidate, baseline):
        run = self.execute_baseline(run_id, approved, config)
        if run['status'] in {'queued','running'}:return self.store.candidate(candidate['id'])
        if run['status']!='completed' or not run['result'].get('evaluation_complete'):
            result={**run['result'],'evaluation_run_id':run_id,'baseline_run_id':baseline['id'],'error':run.get('error_message'),
                    'evaluation_identity':run['judge'].get('evaluation_identity'),'regression':{'status':'NOT_EVALUABLE','passed':None},
                    'qualification':{'qualified':None,'blocking_reason':'Sandbox未完成'},'recommendation':None}
            finished=self.store.finish_candidate(candidate['id'],'failed',result)
            return {**finished,'recommendation':self.store.refresh_recommendation(candidate['experiment_id'])}
        if run['judge'].get('evaluation_identity') != baseline['judge'].get('evaluation_identity'):
            raise ValueError('判分身份不同，禁止比较门槛或计算修好和弄坏')
        baseline_cases = {item["question_id"]: item for item in self.store.evaluation_case_results(baseline["id"])}
        candidate_cases = {item["question_id"]: item for item in self.store.evaluation_case_results(run_id)}
        failed = [question_id for question_id, item in baseline_cases.items() if not item.get("passed")]
        references = set(candidate['reasoning'].get('observed_evidence', []))
        targets = [q for q in failed if q in references or f"BC-{baseline['id']}-{q}" in references]
        frozen = {q['id']: q for q in json.loads(baseline['dataset_snapshot_json']).get('questions', [])} if baseline.get('dataset_snapshot_json') else {}
        comparison = candidate_comparison(baseline_cases, candidate_cases, targets, frozen)
        regression = evaluate_regression(new_critical_failures=comparison['new_critical_failures'], new_ordinary_failures=comparison['new_ordinary_failures'])
        regression.update(comparison)
        regression['passed'] = regression['passed'] and comparison['comparison_complete']
        regression['status'] = 'NOT_EVALUABLE' if not comparison['comparison_complete'] else 'PASS' if regression['passed'] else 'FAIL'
        qualification = qualify_candidate(run["result"]["gates"], regression, comparison['target_bad_cases_fixed'], len(failed), comparison['bad_case_count'])
        if run['status'] != 'completed':
            qualification = {**qualification, 'qualified': False}
        result = {"evaluation_run_id": run_id, "baseline_run_id": baseline["id"], "error": run.get("error_message"), **run["result"], "regression": regression, **comparison, "evaluation_identity": run["judge"].get("evaluation_identity"), "qualification": qualification, "release_qualification": qualify_release(run["result"]["gates"], regression, len(comparison["all_fixed_question_ids"])), "recommendation": None}
        if candidate['reasoning'].get('candidate_label') == 'D':
            result['qualification'] = result['release_qualification']
            winner = self.store.candidate(candidate['reasoning']['winner_id'])
            winner_cases = {item['question_id']: item for item in self.store.evaluation_case_results(winner['result']['evaluation_run_id'])}
            newly_failed = [key for key, item in winner_cases.items() if item.get('passed') and not candidate_cases.get(key, {}).get('passed')]
            newly_fixed = [key for key, item in winner_cases.items() if not item.get('passed') and candidate_cases.get(key, {}).get('passed')]
            result['winner_comparison'] = {'winner_id': winner['id'], 'new_failures': newly_failed, 'fixed_cases': newly_fixed, 'promote': run['status'] == 'completed' and result['release_qualification']['qualified']}
        finished = self.store.finish_candidate(candidate["id"], "evaluated" if run['status'] == 'completed' else 'failed', result)
        recommendation = self.store.refresh_recommendation(candidate["experiment_id"])
        return {**finished, "recommendation": recommendation}

    def run_baseline(self, *, automatic=True):
        return self.execute_baseline(*self.start_baseline(automatic=automatic))

    def run_candidate(self, candidate_id: str, *, automatic=True):
        return self.execute_candidate(*self.start_candidate(candidate_id,automatic=automatic))
