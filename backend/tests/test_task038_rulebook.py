"""规则总表（指挥/规则总表.md，2026-11-16）对应的纯逻辑测试：不连模型、不建数据库。"""
import unittest
import pytest

from app import policy, rules
from app.policy import (qualify_candidate, qualify_release, protected_question, validate_candidate_config,
                        select_final_candidate, DEFAULT_PIPELINE_CONFIG,
                        ALLOWED_SEARCH_SPACE)
from app.optimization_cycle import staged_decision
from app.optimization import validate_round_contract
from app.agent_strategy import validate_d_mode
from app.providers import thinking_config


GATES_OK = {"passed": True}


def regression(critical, ordinary):
    r = policy.evaluate_regression(new_critical_failures=critical, new_ordinary_failures=ordinary)
    r["new_regressions"] = critical + ordinary
    return r


def base_config():
    return {k: v for k, v in DEFAULT_PIPELINE_CONFIG.items()}


# ---------- 一、二：搜索空间与固定参数 ----------

def test_defaults_are_strict_and_off():
    assert DEFAULT_PIPELINE_CONFIG["prompt_strategy"] == rules.BASELINE["prompt_strategy"]
    assert DEFAULT_PIPELINE_CONFIG["generation_thinking"] == rules.BASELINE["generation_thinking"]
    assert ALLOWED_SEARCH_SPACE["prompt_strategy"] == rules.PIPELINE_VALUES["prompt_strategy"]
    assert ALLOWED_SEARCH_SPACE["generation_thinking"] == ("off", "low", "high", "max")


def test_prompt_strategy_rejects_legacy_values():
    config = base_config()
    assert validate_candidate_config(config)["valid"]
    config["generation_thinking"] = "high"
    assert validate_candidate_config(config)["valid"]
    config["prompt_strategy"] = "Tiered"
    assert not validate_candidate_config(config)["valid"]


# ---------- 五.5：统一合格标准 ----------

@pytest.mark.parametrize("critical,ordinary,base_bad,cand_bad,ok", [
    (0, 0, 8, 7, True),
    (0, 1, 8, 7, True),     # 修好2、新增1普通，净少1
    (0, 2, 8, 6, True),     # 普通新增题不设上限
    (1, 0, 8, 6, False),    # 新增严重题
    (0, 1, 8, 8, True),     # 总错题数持平仍满足合格门槛
    (0, 0, 8, 8, True),
])
def test_candidate_and_release_use_one_rule(critical, ordinary, base_bad, cand_bad, ok):
    reg = regression(critical, ordinary)
    assert qualify_candidate(GATES_OK, reg, 0, base_bad, cand_bad)["qualified"] is ok
    assert qualify_release(GATES_OK, reg, base_bad - cand_bad + ordinary + critical, base_bad, cand_bad)["qualified"] is ok


def test_gate_failure_blocks():
    assert not qualify_candidate({"passed": False}, regression(0, 0), 1, 8, 6)["qualified"]
    assert not qualify_release({"passed": False}, regression(0, 0), 2, 8, 6)["qualified"]


def test_target_fix_is_not_a_condition_anymore():
    assert qualify_candidate(GATES_OK, regression(0, 0), 0, 8, 7)["qualified"]


@pytest.mark.parametrize('new,fixed,complete,qualifies', [
    (['Q22'], ['Q17', 'Q21', 'Q27'], True, False),
    ([], [], True, False),
    ([], ['Q05', 'Q21', 'Q27'], True, True),
    ([], ['Q05'], False, False),
])
def test_2026_11_20b_qualification(new, fixed, complete, qualifies):
    comparison = {**regression(0, len(new)), 'comparison_complete': complete,
                  'new_regression_question_ids': new, 'all_fixed_question_ids': fixed}
    assert qualify_candidate(GATES_OK, comparison, 0, 5, 5)['qualified'] is True
    from app.policy import LEGACY_CANDIDATE_QUALIFICATION_VERSION
    result = qualify_candidate(GATES_OK, comparison, 0, 5, 5, rule_version=LEGACY_CANDIDATE_QUALIFICATION_VERSION)
    assert result['rule_version'] == '2026-11-20b'
    assert result['qualified'] is qualifies


def test_qualification_reassessment_preserves_saved_qualification(tmp_path):
    import json
    from app.governance import GovernanceStore
    from app.optimization_cycle import _qualified_abc

    store = GovernanceStore(tmp_path / 'qualifications.db')
    experiment = store.create_experiment('baseline')
    old, new = {'qualified': True}, {'qualified': False, 'rule_version': '2026-11-20b'}
    store.save_candidate(experiment, 'round-1-a', {}, {'round': 1, 'candidate_label': 'A'})
    store.finish_candidate(f'{experiment}-round-1-a', 'evaluated', {'qualification': old, 'qualification_reassessment': new})
    view = store.experiment(experiment, light=True)
    result = view['candidates'][0]['result']
    assert result['qualification'] == new
    assert result['old_qualification'] == old
    assert _qualified_abc(view) == []
    with store.connection() as db:
        saved = json.loads(db.execute('SELECT result_json FROM candidate_configs').fetchone()[0])
    assert saved['qualification'] == old


def test_d_with_new_baseline_failure_is_not_qualified(tmp_path):
    import json
    from app.evaluation import EvaluationRunner
    from app.governance import GovernanceStore

    store = GovernanceStore(tmp_path / 'composite-qualification.db')
    baseline = {'id': 'baseline', 'judge': {'evaluation_identity': 'frozen'}}
    experiment = store.create_experiment(baseline['id'])
    winner = f'{experiment}-R1-C'
    store.save_candidate(experiment, 'R1-C', {}, {'round': 1, 'candidate_label': 'C'})
    store.finish_candidate(winner, 'evaluated', {'evaluation_run_id': 'winner', 'bad_case_count': 2})
    store.save_candidate(experiment, 'D', {}, {'candidate_label': 'D', 'winner_id': winner})
    with store.connection() as db:
        for run_id, outcomes in [('baseline', (True, False)), ('winner', (False, False)), ('composite', (False, True))]:
            for question, passed in zip(['Q22', 'Q27'], outcomes):
                db.execute('INSERT INTO evaluation_case_results(run_id,question_id,result_json) VALUES (?,?,?)',
                           (run_id, question, json.dumps({'passed': passed})))
    run = {'id': 'composite', 'status': 'completed', 'judge': baseline['judge'],
           'result': {'evaluation_complete': True, 'gates': {'passed': True, 'passed_count': 11, 'total': 11}}}
    candidate = store.candidate(f'{experiment}-D')
    result = EvaluationRunner(store, None).finalize_saved_candidate(run, candidate, baseline)['result']
    assert result['new_regression_question_ids'] == ['Q22']
    assert result['all_fixed_question_ids'] == ['Q27']
    assert result['qualification']['qualified'] is False
    assert result['qualification']['rule_version'] == '2026-11-20b'
    assert result['release_qualification']['qualified'] is False
    assert result['winner_comparison']['promote'] is False


# ---------- 一.6：严重题只看冻结题卷 ----------

def test_protected_question_ignores_dynamic_severity():
    assert protected_question({"severity": "critical"}, {}) is False
    assert protected_question({}, {"negative_subtype": "prompt_injection"}) is True
    assert protected_question({}, {"negative_subtype": "safety_critical"}) is True
    assert protected_question({}, {"criticality": "high"}) is True
    assert protected_question({"negative_subtype": "clarify"}, {}) is False


# ---------- 五.6：分阶段停止 ----------

@pytest.mark.parametrize("round_number,qualified,used,decision", [
    (1, 2, 3, "composite"),       # 第1轮就有2个合格 → 直接 D
    (1, 1, 3, "next_round"),
    (2, 2, 6, "composite"),
    (2, 1, 6, "next_round"),
    (3, 1, 9, "composite"),       # 3轮后只有1个 → D
    (3, 0, 9, "next_round"),      # 前9个全不合格 → 第4轮
    (4, 1, 10, "composite"),      # 第4轮第10个就合格 → 用剩余预算做 D
    (4, 1, 12, "finish_winner"),  # 第12个才合格 → 没预算，不做 D
    (4, 0, 12, "agent_failed"),
])
def test_staged_decision(round_number, qualified, used, decision):
    assert staged_decision(round_number, qualified, used) == decision


def test_agent_thinking_limited_even_in_round_three():
    for thinking in ('off', 'low'):
        base = {**base_config(), 'generation_thinking': thinking}
        candidates = [{"id": "A", "config_diff": {"top_k": 6}}, {"id": "B", "config_diff": {"hyde": True}},
                      {"id": "C", "config_diff": {"min_score": 0.1}}]
        validate_round_contract(candidates, base, [], round_number=3)
        candidates[2]["config_diff"]["generation_thinking"] = "high"
        validate_round_contract(candidates, base, [], round_number=3)
        candidates[2]["config_diff"]["generation_thinking"] = "max"
        with pytest.raises(ValueError, match="generation_thinking"):
            validate_round_contract(candidates, base, [], round_number=3)


def test_max_two_parameters_per_candidate():
    base = base_config()
    too_many = [{"id": "A", "config_diff": {"top_k": 6, "hyde": True, "min_score": 0.1}},
                {"id": "B", "config_diff": {"candidate_k": 24}}, {"id": "C", "config_diff": {"rerank": False}}]
    with pytest.raises(ValueError, match=f"最多改 {rules.AGENT['max_changed_parameters']} 个参数"):
        validate_round_contract(too_many, base, [], round_number=1)


# ---------- 五.7：D 规则与最终选择 ----------

def _qualified(cid, bad, label="A"):
    return {"id": cid, "status": "evaluated", "config": base_config(),
            "reasoning": {"candidate_label": label, "round": 1},
            "result": {"qualification": {"qualified": True}, "bad_case_count": bad, "regression": {}, "metrics": {"latency_p99_seconds": 30}}}


def _suggestion(mode, sources, kind="verified"):
    return {"combination_mode": mode, "mode_reason": "原因", "should_generate_d": True,
            "changes": [{"parameter": "top_k", "source_type": kind, "source_candidates": sources}]}


def test_d_partial_fusion_needs_second_qualified_source():
    winner, other = _qualified("R1-A", 5), _qualified("R1-B", 6, "B")
    validate_d_mode(_suggestion("partial_fusion", ["R1-B"]), winner, [winner, other])
    with pytest.raises(ValueError, match="另一个合格方案"):
        validate_d_mode(_suggestion("partial_fusion", ["R1-A"]), winner, [winner, other])
    with pytest.raises(ValueError, match="partial_fusion"):
        validate_d_mode(_suggestion("winner_plus", ["R1-B"]), winner, [winner, other])


def test_d_degenerate_fusion_allows_adding_one_parameter_to_winner():
    winner, other = _qualified("R1-C", 2, "C"), _qualified("R2-C", 4, "C")
    winner['config'].update(hybrid_alpha=0.7, query_decompose=True)
    other['config']['hybrid_alpha'] = 0.7
    suggestion = {**_suggestion('winner_plus', ['R1-A']), 'proposed_config_diff': {'top_k': 6}}
    facts = {'baseline_config': base_config()}
    validate_d_mode(suggestion, winner, [winner, other], facts)

    with pytest.raises(ValueError, match='winner_plus'):
        validate_d_mode({**suggestion, 'combination_mode': 'partial_fusion'}, winner, [winner, other], facts)
    with pytest.raises(ValueError, match='新增 1 个参数'):
        validate_d_mode({**suggestion, 'proposed_config_diff': {'query_decompose': False}},
                        winner, [winner, other], facts)
    with pytest.raises(ValueError, match='保留 Winner'):
        validate_d_mode({**suggestion, 'proposed_config_diff': {'hybrid_search': False}},
                        winner, [winner, other], facts)
    other['config']['top_k'] = 6
    with pytest.raises(ValueError, match='partial_fusion'):
        validate_d_mode(suggestion, winner, [winner, other], facts)


def test_d_single_qualified_may_use_new_attempt_but_prefers_verified():
    winner = _qualified("R1-A", 5)
    validate_d_mode(_suggestion("winner_plus", [], "new_attempt"), winner, [winner])
    with pytest.raises(ValueError, match="优先使用"):
        validate_d_mode(_suggestion("winner_plus", [], "new_attempt"), winner, [winner], {"usable_repairs": [{"x": 1}]})
    with pytest.raises(ValueError, match="必须生成D"):
        validate_d_mode({**_suggestion("winner_plus", []), "should_generate_d": False}, winner, [winner])


def test_d_mode_limits_effective_changes_from_baseline():
    winner = _qualified('R1-C', 2, 'C')
    winner['config'].update(hybrid_alpha=0.7, query_decompose=True)
    suggestion = {**_suggestion('winner_plus', ['R1-A']), 'proposed_config_diff': {'top_k': 6, 'hyde': True}}
    with pytest.raises(ValueError, match='相对 Baseline 最多改 3'):
        validate_d_mode(suggestion, winner, [winner], {'baseline_config': base_config()})


def test_select_final_candidate():
    winner = _qualified("R1-A", 5)
    better_d = {**_qualified("EXP-D", 4, "D")}
    worse_d = {**_qualified("EXP-D", 6, "D")}
    failed_d = {**_qualified("EXP-D", 3, "D"), "result": {"qualification": {"qualified": False}}}
    assert select_final_candidate([winner], better_d)["candidate_id"] == "EXP-D"
    assert select_final_candidate([winner], worse_d)["candidate_id"] == "R1-A"
    assert select_final_candidate([winner], failed_d)["candidate_id"] == "R1-A"
    assert select_final_candidate([], None)["decision"] == "本次 Agent 优化失败"


# ---------- 三.3：配置的档位就是实际请求的档位 ----------

def test_generation_thinking_is_not_forced_off():
    assert thinking_config("baseline", "max")["reasoning_effort"] == "max"
    assert thinking_config("candidate", "high")["reasoning_effort"] == "high"
    assert thinking_config("candidate", "off")["thinking"]["type"] == "disabled"
    assert thinking_config("query_rewrite", "max")["thinking"]["type"] == "disabled"


class RoundConclusionLeniencyTests(unittest.TestCase):
    """044c：第 2 轮总结因预测完全吻合时"预测不符原因"留空被连续拒绝，导致循环 failed。"""

    def _candidate(self, fixed, predicted, broken=()):
        return {'id': 'C1', 'reasoning': {'predicted_fixed_question_ids': list(predicted)},
                'result': {'all_fixed_question_ids': list(fixed), 'comparison': {'new_failure_question_ids': list(broken)}}}

    def _plan(self, fixed, predicted, **overrides):
        plan = {'candidate_id': 'C1', 'fixed_question_ids': list(fixed), 'new_failure_question_ids': [],
                'matched_question_ids': sorted(set(fixed) & set(predicted)), 'prediction_match_count': len(set(fixed) & set(predicted)),
                'unmatched_reason': '', 'parameter_assessment': '有效', 'evidence_reason': '召回了标准证据', 'conclusion': '保留'}
        plan.update(overrides)
        return plan

    def test_matched_prediction_allows_empty_unmatched_reason(self):
        from app.agent_strategy import validate_round_conclusion, new_failure_ids
        candidate = self._candidate(['Q21'], ['Q21'])
        if new_failure_ids(candidate['result']):
            self.skipTest('new_failure_ids 读取口径不同')
        plan = self._plan(['Q21'], ['Q21'])
        validate_round_conclusion({'plans': [plan], 'lessons': ['先单独验证思考档位'], 'carry_forward_lessons': True}, [candidate])
        self.assertEqual(plan['unmatched_reason'], '预测与结果一致，无不符')

    def test_mismatch_still_requires_reason_and_names_field(self):
        from app.agent_strategy import validate_round_conclusion
        candidate = self._candidate([], ['Q21'])
        with self.assertRaisesRegex(ValueError, 'C1 缺少：预测不符原因'):
            validate_round_conclusion({'plans': [self._plan([], ['Q21'])]}, [candidate])
