"""Frozen V1.3 release policy with no storage or provider side effects."""

from __future__ import annotations

import json
from numbers import Real


from . import rules


MAX_EVALS = rules.AGENT['budget']
FRIEND_BASELINE_CONFIG = rules.BASELINE.copy()
# The default Pipeline comparison remains unfiltered until an explicit score floor is selected.
DEFAULT_PIPELINE_CONFIG = {**FRIEND_BASELINE_CONFIG, 'min_score': rules.PIPELINE_VALUES['min_score'][0]}
DEFAULT_PIPELINE_CONFIG.pop('temperature')

GATE_DEFINITIONS = (
    *({'metric': f'{group}_{dimension}', 'operator': '>=', 'threshold': threshold}
      for group in ('positive', 'ablation')
      for dimension, threshold in zip(('correctness', 'faithfulness', 'completeness'), rules.GATES[f'{group}_avg'])),
    {'metric': 'safe_rejection_rate', 'operator': '>=', 'threshold': rules.GATES['safety_refusal']},
    {'metric': 'safety_critical_accuracy', 'operator': '>=', 'threshold': rules.GATES['safety_critical']},
    {'metric': 'prompt_injection_resistance', 'operator': '>=', 'threshold': rules.GATES['prompt_injection']},
    {'metric': 'latency_p50_seconds', 'operator': '<=', 'threshold': rules.GATES['p50_seconds']},
    {'metric': 'latency_p99_seconds', 'operator': '<=', 'threshold': rules.GATES['p99_seconds']},
)

QUALITY_METRICS = tuple(gate["metric"] for gate in GATE_DEFINITIONS if gate['operator'] == '>=')
ALLOWED_SEARCH_SPACE = rules.PIPELINE_VALUES
FIXED_PIPELINE_PARAMETERS = {'temperature': rules.BASELINE['temperature']}

EXCLUDED_AUTOMATIC_PARAMETERS = frozenset({
    "parser", "ocr", "chunk_method", "chunk_size", "chunk_overlap", "embedding_model",
    "generation_model", "rerank_model", "rerank_top_n",
})

# Descriptions follow ALLOWED_SEARCH_SPACE order; values remain validator-owned.
PARAMETER_EXPLANATIONS = {
    'query_decompose': ('把一句话里问了两三件事的问题拆成几个子问题，分别去查资料再合起来交给模型。适合答案分散在不同章节的题，但多一次模型调用、稍慢。', ['关闭', '开启（拆成子问题分别检索）']),
    'prompt_strategy': ('交给模型的回答提示词。各档以 Baseline 的分级回答为底，解决不同回答问题。', [
        'Baseline 分级回答',
        '有据直接答、答全要点，减少过度拒答',
        '安全结论在前、拒绝绕过和注入，型号或状态不明先追问',
    ]),
    'candidate_k': ('第一轮查找时先捞回多少段资料，留给后面排序挑选。捞得多不容易漏掉关键证据，但排序更费时。', ['常规范围', '扩大范围，适合证据分散在多处的题']),
    'top_k': ('排序后真正交给模型写回答的资料段数。给得多要点更全，但模型要读得更多、回答更慢，也更容易被无关内容干扰。', ['精简', '更全，稍慢']),
    'min_score': ('相关分低于这条线的资料直接丢掉，不交给模型。线越高资料越干净，但也可能把有用的证据一起筛掉。', ['不筛', '只去掉明显无关的', '适度筛选', '筛得较严', '最严']),
    'hybrid_search': ('同时用两种方式找资料：语义检索（意思相近就能找到）和关键词检索（字面一致才能找到），再把两边的分数合起来。', ['开（两种一起用）', '关（只用语义检索）']),
    'hybrid_alpha': ('混合检索时语义检索分数占多大比重，其余归关键词检索。只在混合检索开启时有效。', ['更看重关键词原文，适合型号、错误码这类精确词', '两者各半', '更看重意思相近，适合口语化问法']),
    'rerank': ('初步找回资料后，用专门的排序模型逐段判断和问题有多相关，再重新排队。', ['开（用排序模型精排）', '关（保持初步检索的顺序）', '仅原问题（只按用户原话做关键词排序，不调用排序模型）']),
    'query_rewrite': ('检索前先把用户的口语问题改写成更规范的说法再去查。', ['开', '关']),
    'multi_query': ('从不同角度多生成几种问法，分别检索后合并结果，减少一种问法漏掉证据的情况。', ['关（只用原问题）', '多生成几种问法；越多覆盖面越广，也越慢', '多生成几种问法；越多覆盖面越广，也越慢', '多生成几种问法；越多覆盖面越广，也越慢']),
    'hyde': ('先让模型写一段"可能的答案"，再拿这段话去检索。它和说明书原文的写法更接近，有时比直接用问题检索更容易找到证据。', ['开', '关']),
    'generation_thinking': (
        f"Baseline 思考档位为 {rules.BASELINE['generation_thinking']}，"
        + ('Agent 不调这一项' if rules.AGENT['thinking_locked'] else 'Agent 可调整'),
        ['不思考，最快', '略想', '多想', '想得最久，最慢'],
    ),
    'retrieval_max_tokens': ('交给模型的资料最多多长，超出部分截掉。', ['不限', '较宽松', '较紧，回答更快，但可能截掉证据']),
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
    critical_limit = rules.QUALIFICATION['max_new_critical']
    # Regression records both counts. Current qualification also requires the full comparison.
    checks = {"critical": valid and new_critical_failures <= critical_limit}
    passed = all(checks.values())
    return {"passed": passed, "status": "PASS" if passed else ("NOT_EVALUABLE" if not valid else "FAIL"), "new_critical_failures": new_critical_failures, "new_ordinary_failures": new_ordinary_failures, "limits": {"critical": critical_limit, "ordinary": None}, "checks": checks}


def protected_question(case, golden=None):
    """Use frozen question identity, never a candidate answer's dynamic issue severity."""
    golden = golden or {}
    subtype = golden.get('negative_subtype', case.get('negative_subtype'))
    # 规则总表一.6：严重题只看冻结题卷（负向子类型、criticality），不看某次判分给出的 severity。
    return subtype in {'safety_critical', 'prompt_injection'} or golden.get('criticality') == 'high'



CANDIDATE_QUALIFICATION_VERSION = rules.QUALIFICATION['version']
LEGACY_CANDIDATE_QUALIFICATION_VERSION = '2026-11-20b'


def qualification_description():
    rule = rules.QUALIFICATION
    return (f"{len(GATE_DEFINITIONS)} 项门槛全过、无严重违规，"
            f"相对 Baseline 新错不超过 {rule['max_new_failures']} 道，至少修好 {rule['min_fixed']} 道")


def qualify_candidate(gates: dict, regression: dict, target_bad_cases_fixed: int, baseline_bad_case_count: int, candidate_bad_case_count: int, *, rule_version: str | None = None) -> dict:
    counts_valid = all(isinstance(value, int) and not isinstance(value, bool) and value >= 0 for value in (target_bad_cases_fixed, baseline_bad_case_count, candidate_bad_case_count))
    checks = {
        "hard_gates": gates.get("passed") is True,
        "regression": regression.get("passed") is True,
    }
    version = {}
    if rule_version in {CANDIDATE_QUALIFICATION_VERSION, LEGACY_CANDIDATE_QUALIFICATION_VERSION}:
        fixed = regression.get('all_fixed_question_ids')
        new = regression.get('new_regression_question_ids')
        checks.update(comparison_complete=regression.get('comparison_complete') is True,
                      zero_new_failures=isinstance(new, list) and len(new) <= rules.QUALIFICATION['max_new_failures'],
                      at_least_one_fixed=isinstance(fixed, list) and len(fixed) >= rules.QUALIFICATION['min_fixed'])
        version['rule_version'] = rule_version
    if rule_version == CANDIDATE_QUALIFICATION_VERSION:
        checks['no_severe_risk'] = regression.get('severe_risk_question_ids') == []
    qualified = all(checks.values())
    return {**version, "qualified": qualified, "status": "QUALIFIED" if qualified else "NOT_QUALIFIED", "checks": checks,
            "target_bad_cases_fixed": target_bad_cases_fixed if counts_valid else None,
            "bad_case_reduction": baseline_bad_case_count - candidate_bad_case_count if counts_valid else None}


def qualify_release(gates: dict, regression: dict, fixed_count: int, baseline_bad_case_count=None, candidate_bad_case_count=None) -> dict:
    """Legacy qualification for records outside the current Agent round contract."""
    checks = {"hard_gates": gates.get("passed") is True,
              "regression": regression.get("passed") is True and regression.get("new_critical_failures") is not None
              and regression['new_critical_failures'] <= rules.QUALIFICATION['max_new_critical']}
    return {"qualified": all(checks.values()), "checks": checks}


def require_gate_request_actor(gate, actor, *, allow_self_check=False):
    actors = rules.GATE_USER_ACTORS
    if allow_self_check:
        actors = actors | {rules.AUTHORIZATION[gate]['self_check_executor'].casefold()}
    if actor.strip().casefold() not in actors:
        raise ValueError(f"Gate {gate[-1]} 需要通过用户确认入口核对授权")


def gate2_self_check_authorized(authorization):
    actor = (authorization or {}).get('actor')
    return bool(authorization and authorization.get('enabled') is True and authorization.get('authorized_at')
                and isinstance(actor, str) and actor.strip()
                and actor.strip().casefold() in rules.GATE_USER_ACTORS)


def gate_audit(gate, actor, *, authorization=None, reviews=None):
    rule = rules.AUTHORIZATION[gate]
    if not isinstance(actor, str) or not actor.strip():
        raise ValueError('确认人不能为空')
    actor = actor.strip()
    if reviews is not None:
        raise ValueError(f"Gate {gate[-1]} 已取消固定双审，须按当前用户授权确认")
    if actor.casefold() == (rule['self_check_executor'] or '').casefold():
        if not gate2_self_check_authorized(authorization):
            raise ValueError('Gate 2 Codex 自检须有已保存的用户授权')
        return rules.AGENT_GATE_AUDIT.copy()
    if actor.casefold() == rules.AGENT_GATE_AUDIT['executed_by'].casefold() or actor == '总指挥':
        raise ValueError('Gate 3 发布须由用户明确批准' if gate == 'gate3' else 'Gate 2 须由用户确认或经用户授权由 Codex 自检')
    return {'authorizer': rule['authorizer'], 'executed_by': actor, 'review_method': rule['manual_review_method']}


def composite_source_eligible(candidate: dict, identity: str) -> bool:
    result = candidate.get('result', {})
    return bool(candidate.get('status') == 'evaluated' and result.get('evaluation_identity') == identity
                and result.get('qualification', {}).get('qualified') is True
                and not result.get('continued_failure_new_critical_question_ids'))


def composite_source_grade(candidate, baseline):
    diff = {k:v for k,v in candidate['config'].items() if k in ALLOWED_SEARCH_SPACE and v != baseline.get(k)}
    critical = candidate.get('result', {}).get('regression', {}).get('new_critical_failures')
    excluded = critical != 0 or bool(candidate.get('result', {}).get('continued_failure_new_critical_question_ids'))
    return {'parameter_diff':diff, 'grade':'excluded' if excluded else 'whole_bundle' if len(diff)>1 else 'single_parameter',
            'rule':'新增关键 Bad Case 或关键 Regression 记录缺失，排除' if excluded else '无法单独归因，只能整组取用' if len(diff)>1 else '单参数可单独取用'}


def validate_composite_sources(sources, config, baseline, reasons):
    selected = []
    for source in sources:
        grade = composite_source_grade(source, baseline)
        if grade['grade']=='excluded':
            raise ValueError('D来源有新增关键 Bad Case 或记录缺失，排除')
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
            len(candidate.get('reasoning', {}).get('changed_parameters_vs_baseline', candidate.get('reasoning', {}).get('changed_parameters', {}))), candidate['id'])


def select_final_candidate(candidates: list[dict], final_candidate: dict | None = None) -> dict:
    """规则总表五.7：最终结果取所有合格方案（含合格的 D）中最好的；一个都没有就是本次 Agent 优化失败。"""
    pool = [c for c in candidates if c.get('status') == 'evaluated' and c.get('reasoning', {}).get('candidate_label') != 'D'
            and c.get('result', {}).get('qualification', {}).get('qualified') is True]
    d_qualified = bool(final_candidate and final_candidate.get('status') == 'evaluated'
                       and final_candidate.get('result', {}).get('qualification', {}).get('qualified') is True)
    if not pool and not d_qualified:
        return {'decision': '本次 Agent 优化失败', 'candidate_id': None, 'reason': '没有合格方案'}
    winner = min(pool, key=candidate_rank) if pool else None
    # 朋友的"逐题非回退门"：D 要晋升，相对 Winner 不能多错任何一道题，且错题总数更少；打平或有退步就保留 Winner。
    d_blocked = None
    if d_qualified and winner is not None:
        d_blocked = d_regression_vs_winner(final_candidate, winner)
    if d_qualified and (winner is None or not d_blocked):
        pool.append(final_candidate)
    best = min(pool, key=candidate_rank)
    if final_candidate and best is final_candidate:
        return {'decision': '推荐 Candidate D', 'candidate_id': best['id'], 'reason': 'D 合格，且按错题数、新增错题数、P99 排序最好'}
    if d_blocked:
        reason = f'D 未通过逐题非回退门（{d_blocked}），保留已验证的 Winner'
    elif final_candidate and final_candidate.get('status') == 'evaluated' and not d_qualified:
        reason = 'D 不合格，取合格方案中最好的'
    else:
        reason = '合格方案中按错题数、新增错题数、P99 排序最好'
    return {'decision': '保留 Winner 方案', 'candidate_id': best['id'], 'reason': reason}


def _failed_set(result):
    """相对同一个 Baseline：失败 = (Baseline 错题 − 修好) ∪ 新错。只用两者共有的 Baseline 错题，所以比较时抵消。"""
    return set(result.get('new_regression_question_ids') or []), set(result.get('all_fixed_question_ids') or [])


def d_regression_vs_winner(d, winner):
    """返回 D 未能晋升的原因；None 表示 D 相对 Winner 逐题不退步且错题更少。"""
    d_new, d_fixed = _failed_set(d.get('result', {}))
    w_new, w_fixed = _failed_set(winner.get('result', {}))
    worse = sorted((d_new - w_new) | (w_fixed - d_fixed))
    if worse:
        return 'Winner 答对而 D 答错：' + '、'.join(worse)
    d_bad, w_bad = d.get('result', {}).get('bad_case_count'), winner.get('result', {}).get('bad_case_count')
    if not (type(d_bad) is int and type(w_bad) is int and d_bad < w_bad):
        return '与 Winner 打平（失败题集合没有变少）'
    return None


def canonicalize_config(config: dict) -> str:
    """A stable representation used for candidate de-duplication and audit records."""
    if not isinstance(config, dict):
        raise ValueError("config must be an object")
    return json.dumps(config, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def search_space_contract(*, for_agent=False) -> dict:
    """Expose the validator's allowed values and JSON types to the Agent."""
    contract = {}
    for key, allowed in ALLOWED_SEARCH_SPACE.items():
        if for_agent and key not in rules.AGENT['tunable']:
            continue
        if for_agent and key == 'generation_thinking':
            allowed = rules.AGENT['thinking_values']
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
    for key, fixed in FIXED_PIPELINE_PARAMETERS.items():
        if key in config and config[key] != fixed:
            errors.append(f"{key} is fixed to {fixed}")
            issues.append({"field": key, "actual": config[key], "expected_type": "fixed", "allowed_values": [fixed], "error": f"{key} is fixed"})
    unknown = set(config) - set(ALLOWED_SEARCH_SPACE) - set(FIXED_PIPELINE_PARAMETERS)
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
        if key not in config and key in {"generation_thinking", "retrieval_max_tokens", "query_decompose", "prompt_strategy"}:
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
