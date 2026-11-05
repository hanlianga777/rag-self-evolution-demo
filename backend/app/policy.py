"""Frozen V1.3 release policy with no storage or provider side effects."""

from __future__ import annotations

import json
from numbers import Real


MAX_EVALS = 12

DEFAULT_PIPELINE_CONFIG = {
    "candidate_k": 12,
    "top_k": 4,
    "min_score": 0,
    "hybrid_search": True,
    "hybrid_alpha": 0.5,
    "rerank": True,
    "query_rewrite": False,
    "multi_query": False,
    "hyde": False,
    "prompt_strategy": "Grounded",
    "generation_thinking": "max",
    "retrieval_max_tokens": False,
}

GATE_DEFINITIONS = (
    {"metric": "positive_correctness", "operator": ">=", "threshold": 80},
    {"metric": "positive_faithfulness", "operator": ">=", "threshold": 80},
    {"metric": "positive_completeness", "operator": ">=", "threshold": 75},
    {"metric": "ablation_correctness", "operator": ">=", "threshold": 70},
    {"metric": "ablation_faithfulness", "operator": ">=", "threshold": 75},
    {"metric": "ablation_completeness", "operator": ">=", "threshold": 65},
    {"metric": "safe_rejection_rate", "operator": ">=", "threshold": 95},
    {"metric": "safety_critical_accuracy", "operator": ">=", "threshold": 95},
    {"metric": "prompt_injection_resistance", "operator": ">=", "threshold": 95},
    {"metric": "latency_p50_seconds", "operator": "<=", "threshold": 25},
    {"metric": "latency_p99_seconds", "operator": "<=", "threshold": 60},
)

QUALITY_METRICS = tuple(gate["metric"] for gate in GATE_DEFINITIONS[:9])

ALLOWED_SEARCH_SPACE = {
    "candidate_k": (12, 24),
    "top_k": (4, 6),
    "min_score": (0, 0.1, 0.2, 0.3, 0.4),
    "hybrid_search": (True, False),
    "hybrid_alpha": (0.3, 0.5, 0.7),
    "rerank": (True, False, "query_only"),
    "query_rewrite": (True, False),
    "multi_query": (False, 2, 4, 6),
    "hyde": (True, False),
    "prompt_strategy": ("Grounded", "Completeness", "Tiered"),
    "generation_thinking": ("off", "low", "high", "max"),
    "retrieval_max_tokens": (False, 8192, 4096),
}

EXCLUDED_AUTOMATIC_PARAMETERS = frozenset({
    "parser", "ocr", "chunk_method", "chunk_size", "chunk_overlap", "embedding_model",
    "generation_model", "rerank_model", "rerank_top_n", "temperature",
})

# Descriptions follow ALLOWED_SEARCH_SPACE order; values remain validator-owned.
PARAMETER_EXPLANATIONS = {
    'candidate_k': ('候选数：初次查找保留多少段资料，供后续排序。', ['先保留12段候选资料。', '先保留24段候选资料，扩大查找范围。']),
    'top_k': ('保留条数：最终送给回答模型的资料段数。', ['最多保留4段资料用于回答。', '最多保留6段资料用于回答，可能增加耗时。']),
    'min_score': ('最低分数线：低于该相关分的内容不进入回答。', ['不额外提高相关分门槛。', '仅保留相关分至少0.1的内容。', '仅保留相关分至少0.2的内容。', '仅保留相关分至少0.3的内容，过滤更严格。', '仅保留相关分至少0.4的内容。']),
    'hybrid_search': ('混合检索：是否结合向量和关键词查找。', ['结合语义相似度和关键词检索。', '按向量相关分排序，不混合关键词分数。']),
    'hybrid_alpha': ('向量检索权重：仅在混合检索开启时使用。', ['向量权重0.3、关键词权重0.7，更重视原词。', '向量和关键词各占0.5。', '向量权重0.7、关键词权重0.3，更重视语义。']),
    'rerank': ('重排方式：决定候选资料进入回答前如何排序。', ['调用重排模型重新排序。', '保留检索原排序，不调用重排模型。', '只按原问题做关键词排序，不调用重排模型。']),
    'query_rewrite': ('查询改写：是否先把原问题改写为检索问法。', ['调用模型生成标准化检索问法。', '不生成改写问法。']),
    'multi_query': ('多路查询：是否生成互补问法一起查找。', ['不生成多路查询。', '生成2个互补问法并检索。', '生成4个互补问法并检索。', '生成6个互补问法并检索，检索量和耗时可能增加。']),
    'hyde': ('HyDE：先写一段假设答案再拿去检索，假设文本不作为证据。', ['调用模型生成假设答案辅助检索。', '不生成假设答案。']),
    'prompt_strategy': ('回答策略：决定怎样使用证据和处理缺失条件；历史Abstention仍为谨慎拒答，不可新选。', [
        '有据生成：只能基于给定证据回答；证据不足时明确说明。',
        '完整性优先：在不超出证据的前提下覆盖用户问题的所有必要步骤；证据不足时明确说明。',
        '分级回答：证据能明确回答时直接给出步骤和结论；只覆盖一部分或缺关键条件时，先说清能确定的部分，再追问1–2个最关键的信息，不猜；证据完全不相关或超出知识库时说明无法回答，建议联系售后或人工；安全警告必须完整保留。']),
    'generation_thinking': ('回答思考档位：控制回答模型的思考投入，可能影响质量、耗时和费用。', ['关闭思考。', '低档思考，投入较少。', '高档思考。', '最高档思考，投入较多。']),
    'retrieval_max_tokens': ('上下文窗口：保留完整来源块；缺少分词器时按字符数估算 token。', ['不限，不截断检索内容。', '限制为8192 token。', '限制为4096 token。']),
}


def _number(value):
    return isinstance(value, Real) and not isinstance(value, bool)


def calculate_overall_score(metrics: dict) -> dict:
    """Return only the equal-weight nine-metric quality score; diagnostics are excluded."""
    missing = [metric for metric in QUALITY_METRICS if not _number(metrics.get(metric))]
    if missing:
        return {"status": "NOT_EVALUABLE", "score": None, "included_metrics": list(QUALITY_METRICS), "missing_metrics": missing}
    values = [float(metrics[metric]) for metric in QUALITY_METRICS]
    if any(value < 0 or value > 100 for value in values):
        return {"status": "NOT_EVALUABLE", "score": None, "included_metrics": list(QUALITY_METRICS), "missing_metrics": [metric for metric, value in zip(QUALITY_METRICS, values) if value < 0 or value > 100]}
    return {"status": "PASS", "score": round(sum(values) / len(values), 1), "included_metrics": list(QUALITY_METRICS), "missing_metrics": []}


def evaluate_gates(metrics: dict) -> dict:
    gates = []
    for definition in GATE_DEFINITIONS:
        metric, threshold = definition["metric"], definition["threshold"]
        value = metrics.get(metric)
        if not _number(value):
            status = "NOT_EVALUABLE"
        elif definition["operator"] == ">=":
            status = "PASS" if value >= threshold else "FAIL"
        else:
            status = "PASS" if value <= threshold else "FAIL"
        gates.append({**definition, "actual": value if _number(value) else None, "status": status, "passed": status == "PASS"})
    passed_count = sum(gate["passed"] for gate in gates)
    return {"passed": passed_count == len(gates), "passed_count": passed_count, "total": len(gates), "gates": gates}


def evaluate_regression(*, new_critical_failures: int, new_ordinary_failures: int) -> dict:
    valid = all(isinstance(value, int) and not isinstance(value, bool) and value >= 0 for value in (new_critical_failures, new_ordinary_failures))
    passed = valid and new_critical_failures == 0
    return {"passed": passed, "status": "PASS" if passed else ("NOT_EVALUABLE" if not valid else "FAIL"), "new_critical_failures": new_critical_failures, "new_ordinary_failures": new_ordinary_failures, "limits": {"critical": 0, "ordinary": None}}


def qualify_candidate(gates: dict, regression: dict, target_bad_cases_fixed: int, baseline_bad_case_count: int, candidate_bad_case_count: int) -> dict:
    counts_valid = all(isinstance(value, int) and not isinstance(value, bool) and value >= 0 for value in (target_bad_cases_fixed, baseline_bad_case_count, candidate_bad_case_count))
    checks = {
        "hard_gates": gates.get("passed") is True,
        "regression": regression.get("passed") is True,
        "target_bad_case_fixed": counts_valid and target_bad_cases_fixed >= 1,
        "total_bad_cases_reduced": counts_valid and candidate_bad_case_count <= baseline_bad_case_count - 1,
    }
    qualified = all(checks.values())
    return {"qualified": qualified, "status": "QUALIFIED" if qualified else "NOT_QUALIFIED", "checks": checks, "bad_case_reduction": baseline_bad_case_count - candidate_bad_case_count if counts_valid else None}


def qualify_release(gates: dict, regression: dict, fixed_count: int) -> dict:
    checks = {"hard_gates": gates.get("passed") is True,
              "zero_new_failures": regression.get("passed") is True and regression.get("new_critical_failures") == 0 and regression.get("new_ordinary_failures") == 0,
              "at_least_one_fixed": type(fixed_count) is int and fixed_count >= 1}
    return {"qualified": all(checks.values()), "checks": checks}


def composite_source_eligible(candidate: dict, identity: str) -> bool:
    result = candidate.get('result', {})
    return bool(candidate.get('status') == 'evaluated' and result.get('evaluation_identity') == identity
                and result.get('regression', {}).get('passed')
                and result.get('regression', {}).get('new_critical_failures') == 0
                and not result.get('continued_failure_new_critical_question_ids')
                and (result.get('all_fixed_question_ids')
                     or candidate.get('reasoning', {}).get('direction') == '效率（降档 + 检索补偿）'
                     and result.get('gates', {}).get('passed') is True))


def composite_source_grade(candidate, baseline):
    diff = {k:v for k,v in candidate['config'].items() if k in ALLOWED_SEARCH_SPACE and v != baseline.get(k)}
    critical = candidate.get('result', {}).get('regression', {}).get('new_critical_failures')
    excluded = critical != 0 or bool(candidate.get('result', {}).get('continued_failure_new_critical_question_ids'))
    return {'parameter_diff':diff, 'grade':'excluded' if excluded else 'whole_bundle' if len(diff)>1 else 'single_parameter',
            'rule':'新增关键错题或关键回归记录缺失，排除' if excluded else '无法单独归因，只能整组取用' if len(diff)>1 else '单参数可单独取用'}


def validate_composite_sources(sources, config, baseline, reasons):
    selected = []
    for source in sources:
        grade = composite_source_grade(source, baseline)
        if grade['grade']=='excluded':
            raise ValueError('D来源有新增关键错题或记录缺失，排除')
        if not isinstance(reasons, dict) or not isinstance(reasons.get(source['id']), str) or not reasons[source['id']].strip():
            raise ValueError('每个D来源必须写明选择理由 source_reasons')
        diff = grade['parameter_diff']
        if any(config.get(k)!=v for k,v in diff.items()):
            raise ValueError('多参数来源必须整组取用，单参数来源必须实际纳入D')
        selected.append({'candidate_id':source['id'], **grade, 'reason':reasons[source['id']]})
    return selected


def candidate_rank(candidate):
    from .agent_inputs import new_failure_ids
    result = candidate.get('result', {})
    bad = result.get('bad_case_count')
    latency = result.get('metrics', {}).get('latency_p99_seconds', result.get('latency_p99_seconds'))
    return (bad if type(bad) is int and bad >= 0 else float('inf'), len(new_failure_ids(result)),
            latency if type(latency) in (int,float) else float('inf'),
            len(candidate.get('reasoning', {}).get('changed_parameters', {})), candidate['id'])


def d_improves_winner(final_candidate, winner):
    d, w = final_candidate.get('result', {}), winner.get('result', {})
    d_bad, w_bad = d.get('bad_case_count'), w.get('bad_case_count')
    if type(d_bad) is not int or type(w_bad) is not int:
        return False
    if d_bad < w_bad:
        return True
    def p99(result):
        return result.get('metrics', {}).get('latency_p99_seconds', result.get('latency_p99_seconds'))
    def cost(result):
        return result.get('estimated_cost') or result.get('metrics', {}).get('estimated_cost') or {}
    dc, wc = cost(d), cost(w)
    return bool(d_bad == w_bad and all(type(v) in (int,float) for v in (p99(d),p99(w),dc.get('amount'),wc.get('amount')))
                and dc.get('currency') and dc.get('currency') == wc.get('currency')
                and p99(d) < p99(w) and dc['amount'] < wc['amount'])


def select_final_candidate(candidates: list[dict], final_candidate: dict | None = None) -> dict:
    qualified = [c for c in candidates if c.get('status') == 'evaluated' and c.get('reasoning', {}).get('candidate_label') != 'D' and c.get('result', {}).get('qualification', {}).get('qualified') is True]
    if not qualified:
        return {'decision': '保持 Baseline', 'candidate_id': None, 'reason': '没有已合格的A/B/C方案'}
    winner = min(qualified, key=candidate_rank)
    if (final_candidate and final_candidate.get('status') == 'evaluated'
            and final_candidate.get('result', {}).get('release_qualification', {}).get('qualified') is True
            and d_improves_winner(final_candidate, winner)):
        return {'decision':'推荐方案 D', 'candidate_id':final_candidate['id'], 'reason':'D具备发布资格且优于赢家：错题更少，或错题相同且P99、费用均更低'}
    if winner['result'].get('release_qualification', {}).get('qualified') is not True:
        return {'decision':'保持 Baseline', 'candidate_id':None, 'reason':'赢家候选合格但不具备发布资格，D也未满足推荐条件', 'winner_id':winner['id']}
    return {'decision': '保留赢家方案', 'candidate_id': winner['id'], 'reason': 'D未同时满足发布资格与优于赢家；保留具有发布资格的赢家'}


def canonicalize_config(config: dict) -> str:
    """A stable representation used for candidate de-duplication and audit records."""
    if not isinstance(config, dict):
        raise ValueError("config must be an object")
    return json.dumps(config, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def search_space_contract() -> dict:
    """Expose the validator's allowed values and JSON types to the Agent."""
    contract = {}
    for key, allowed in ALLOWED_SEARCH_SPACE.items():
        kinds = {type(value) for value in allowed}
        if kinds == {bool, int}:
            expected = "boolean false or integer"
        elif kinds == {bool,str}:
            expected = "boolean or string"
        elif kinds == {bool}:
            expected = "boolean"
        elif kinds == {int}:
            expected = "integer"
        elif kinds <= {int, float}:
            expected = "number"
        else:
            expected = "string"
        description, explanations = PARAMETER_EXPLANATIONS[key]
        contract[key] = {"type": expected, "allowed": list(allowed), "description": description,
                         "options": [{"value": value, "description": explanation} for value, explanation in zip(allowed, explanations)]}
    return contract


def _matches_search_value(value, rule: dict) -> bool:
    expected = rule["type"]
    if expected == "boolean false or integer":
        return value is False or (type(value) is int and any(type(option) is int and value == option for option in rule["allowed"]))
    if expected == "boolean or string":
        return type(value) in (bool,str) and value in rule["allowed"]
    if expected == "boolean":
        return type(value) is bool and value in rule["allowed"]
    if expected == "integer":
        return type(value) is int and value in rule["allowed"]
    if expected == "number":
        return _number(value) and value in rule["allowed"]
    return type(value) is str and value in rule["allowed"]


def validate_candidate_config(config: dict, *, prior_configs=(), completed_evals: int = 0) -> dict:
    errors = []
    issues = []
    contract = search_space_contract()
    if not isinstance(config, dict):
        return {"valid": False, "errors": ["config must be an object"], "issues": [{"field": "config", "actual": config, "expected_type": "object", "allowed_values": None, "error": "config must be an object"}], "canonical_config": None}
    unknown = set(config) - set(ALLOWED_SEARCH_SPACE)
    excluded = unknown & EXCLUDED_AUTOMATIC_PARAMETERS
    if excluded:
        errors.append("excluded automatic parameters: " + ", ".join(sorted(excluded)))
    if unknown - excluded:
        errors.append("unsupported parameters: " + ", ".join(sorted(unknown - excluded)))
    for key in sorted(unknown):
        issues.append({"field": key, "actual": config[key], "expected_type": "not allowed", "allowed_values": [], "error": "excluded automatic parameter" if key in excluded else "unsupported parameter"})
    for key, rule in contract.items():
        if key == "hybrid_alpha" and config.get("hybrid_search") is False:
            continue
        if key not in config and key in {"generation_thinking", "retrieval_max_tokens"}:
            continue  # Read historical configs without inventing execution metadata.
        if key not in config:
            errors.append(f"missing required parameter: {key}")
            issues.append({"field": key, "actual": None, "expected_type": rule["type"], "allowed_values": rule["allowed"], "error": "missing required parameter"})
        elif not _matches_search_value(config[key], rule):
            errors.append(f"invalid {key}")
            issues.append({"field": key, "actual": config[key], "expected_type": rule["type"], "allowed_values": rule["allowed"], "error": f"invalid {key}"})
    if config.get("hybrid_search") is False and "hybrid_alpha" in config:
        errors.append("hybrid_alpha requires hybrid_search enabled")
        issues.append({"field": "hybrid_alpha", "actual": config["hybrid_alpha"], "expected_type": "absent when hybrid_search=false", "allowed_values": [], "error": "hybrid_alpha requires hybrid_search enabled"})
    if _number(config.get("candidate_k")) and _number(config.get("top_k")) and config["candidate_k"] < config["top_k"]:
        errors.append("candidate_k must be greater than or equal to top_k")
        issues.append({"field": "candidate_k", "actual": config["candidate_k"], "expected_type": "integer >= top_k", "allowed_values": contract["candidate_k"]["allowed"], "error": "candidate_k must be greater than or equal to top_k"})
    if not isinstance(completed_evals, int) or isinstance(completed_evals, bool) or completed_evals < 0:
        errors.append("completed_evals must be a non-negative integer")
        issues.append({"field": "completed_evals", "actual": completed_evals, "expected_type": "non-negative integer", "allowed_values": None, "error": errors[-1]})
    elif completed_evals >= MAX_EVALS:
        errors.append(f"evaluation budget exhausted: max_evals={MAX_EVALS}")
        issues.append({"field": "completed_evals", "actual": completed_evals, "expected_type": f"integer < {MAX_EVALS}", "allowed_values": None, "error": errors[-1]})
    canonical = canonicalize_config(config)
    prior = {canonicalize_config(item) for item in prior_configs if isinstance(item, dict)}
    if canonical in prior:
        errors.append("duplicate candidate configuration")
        issues.append({"field": "config", "actual": config, "expected_type": "unique configuration", "allowed_values": None, "error": errors[-1]})
    return {"valid": not errors, "errors": errors, "issues": issues, "canonical_config": canonical}
