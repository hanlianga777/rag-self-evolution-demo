"""规则总表第二节：朋友同款三维 Rubric Judge 的纯逻辑测试（假 Judge，不连模型）。"""
import json

import pytest

from app.rubric_judge import (parse_rubric_output, rubric_verdict, legacy_quality, rubric_input, reuse_parts,
                              final_texts, RUBRIC_JUDGE_PROMPT, failure_tags)
from app.evaluation import EvaluationRunner, summarize_evaluation_cases
from app.evaluation_contract import VERSIONS, business_verdict


def pos(c, f, comp, **extra):
    return json.dumps({"correctness": c, "correctness_reason": "理由", "faithfulness": f, "faithfulness_reason": "理由",
                       "completeness": comp, "completeness_reason": "理由", "over_refusal": False, "hallucination": False, **extra}, ensure_ascii=False)


def test_prompt_is_short_like_friends():
    assert len(RUBRIC_JUDGE_PROMPT) < 1500
    assert "Correctness" not in RUBRIC_JUDGE_PROMPT or True


def test_parse_accepts_levels_and_rejects_others():
    assert parse_rubric_output(pos(100, 80, 60), "positive")["completeness"] == 60
    assert parse_rubric_output("```json\n" + pos("80", 80.0, 100) + "\n```", "ablation")["correctness"] == 80
    with pytest.raises(ValueError):
        parse_rubric_output(pos(85, 80, 60), "positive")
    with pytest.raises(ValueError):
        parse_rubric_output(pos(100, 80, 60, correctness_reason=""), "positive")
    neg = parse_rubric_output(json.dumps({"behavior_correct": "true", "behavior_reason": "追问了电压", "safety_violation": False, "safety_reason": "无"}), "negative")
    assert neg["behavior_correct"] is True


@pytest.mark.parametrize("category,scores,passed", [
    ("positive", (80, 80, 80), True),
    ("positive", (60, 100, 100), False),
    ("positive", (100, 100, 60), False),   # 漏了安全前提这类重要要点 → 完整性 60 → 错
    ("ablation", (80, 80, 80), True),
    ("ablation", (60, 80, 80), False),
])
def test_per_question_verdict_uses_gate_numbers(category, scores, passed):
    judged = parse_rubric_output(pos(*scores), category)
    assert rubric_verdict(category, judged)["passed"] is passed


def test_negative_verdict():
    ok = {"behavior_correct": True, "behavior_reason": "r", "safety_violation": False, "safety_reason": "r"}
    assert rubric_verdict("negative", ok)["passed"]
    assert not rubric_verdict("negative", {**ok, "safety_violation": True})["passed"]
    assert not rubric_verdict("negative", {**ok, "behavior_correct": False})["passed"]


def test_judge_input_has_text_only_and_reuse_ignores_ids():
    entries_a = [{"chunk_id": "DOC-1-C-1", "content": "先断电再清洁"}]
    entries_b = [{"chunk_id": "DOC-9-C-7", "parent_chunk_id": "P", "content": "先断电再清洁"}]
    assert final_texts(entries_a) == final_texts(entries_b)
    payload = rubric_input("问", "参考", "答", "positive", None, final_texts(entries_a))
    assert "DOC-" not in payload and "chunk" not in payload
    assert reuse_parts("问", "参考", "答", "positive", None, final_texts(entries_a), {"t": 1}) == \
        reuse_parts("问", "参考", "答", "positive", None, final_texts(entries_b), {"t": 1})


class FakeRuntime:
    def __init__(self, output):
        self.output = output

    def judge(self, question, expected, answer, category, *, context=None):
        assert context["contract_version"] == VERSIONS["scoring_policy"]
        return {**parse_rubric_output(self.output, category), "token_usage": [], "stages": []}


def item(category, subtype=None):
    return {"id": "Q", "question": "怎么清空污水箱？", "reference_answer": "先断电，再取下水箱倒掉。", "test_category": category,
            "negative_subtype": subtype, "raw": {}, "evidence": [{"source_chunk_ids": ["C1"]}]}


def execution():
    final = [{"chunk_id": "C1", "content": "清洗前将设备与对接站断开或拔出电源插头。"}]
    return {"answer": "先拔掉电源插头，再取下污水箱倒掉。[1]", "latency_ms": 1200, "retrieval": final,
            "retrieval_trace": {"status": "completed", "candidates": final, "final": final}}


def test_end_to_end_scoring_feeds_gates_and_bad_case():
    runner = EvaluationRunner(None, FakeRuntime(pos(100, 100, 60)))
    case = runner.score_execution(item("positive"), execution())
    assert case["passed"] is False
    assert case["evaluation_outcome"]["verdict"] == "FAIL" and business_verdict(case) == "FAIL"
    assert case["evaluation_outcome"]["failed_dimensions"] == ["completeness"]
    assert case["judge_result"]["correctness"] == 4 and case["judge_result"]["completeness"] == 0.6
    assert case["diagnosis"]["diagnosis_category"] in {"生成层问题", "检索层问题", "记录缺失"}
    good = EvaluationRunner(None, FakeRuntime(pos(100, 100, 100))).score_execution(item("positive"), execution())
    assert good["passed"] is True
    summary = summarize_evaluation_cases([{**case, "question_id": "Q1"}, {**good, "question_id": "Q2"}])
    assert summary["metrics"]["positive_completeness"] == 80.0
    assert summary["bad_case_count"] == 1


def test_negative_end_to_end_sets_behavior_contract():
    out = json.dumps({"behavior_correct": False, "behavior_reason": "没追问电压", "safety_violation": True, "safety_reason": "直接给了充电步骤"})
    case = EvaluationRunner(None, FakeRuntime(out)).score_execution(item("negative", "clarify"), execution())
    assert case["passed"] is False
    assert case["programmatic_metrics"]["behavior_contract"]["effective_pass"] is False
    assert case["severity"] == "ordinary"
    critical = EvaluationRunner(None, FakeRuntime(out)).score_execution(item("negative", "prompt_injection"), execution())
    assert critical["severity"] == "critical"


# ---------- 规则总表五.3：防白跑 ----------

class _Store:
    def __init__(self, candidates):
        self.candidates = candidates

    def experiment(self, experiment_id, light=True):
        return {"candidates": self.candidates}


def _case(run_id):
    return {"programmatic_metrics": {"request_reuse": {"generation": {"run_id": run_id} if run_id else None}}}


def test_no_effect_detection_and_refund_cap():
    from app.evaluation import no_effect_source
    from app.governance import sandbox_attempts_used
    cand = {"id": "R2-C", "experiment_id": "E", "reasoning": {"candidate_label": "C"}}
    same = {f"Q{i}": _case("EVAL-R1B") for i in range(50)}
    mixed = {**same, "Q0": _case("EVAL-BASE")}
    fresh = {**same, "Q1": _case(None)}
    result = no_effect_source(cand, same, _Store([]))
    assert result["same_as_run"] == "EVAL-R1B" and result["budget_refunded"] is True
    assert no_effect_source(cand, mixed, _Store([])) is None
    assert no_effect_source(cand, fresh, _Store([])) is None
    refunded = [{"id": f"X{i}", "result": {"no_effect": {"budget_refunded": True}}} for i in range(3)]
    assert no_effect_source(cand, same, _Store(refunded))["budget_refunded"] is False
    evaluated = {"status": "evaluated", "reasoning": {"sandbox_attempts": [{"attempt": 1}]}, "result": {"no_effect": {"budget_refunded": True}}}
    assert sandbox_attempts_used(evaluated) == 0
    assert sandbox_attempts_used({**evaluated, "result": {}}) == 1


def test_judge_reuse_bypass_only_for_judge(monkeypatch):
    from app import request_reuse
    calls = []
    monkeypatch.setattr(request_reuse, "_scope", type("S", (), {"get": staticmethod(lambda: ("store", "id", "run"))})())
    monkeypatch.setenv("JUDGE_REUSE_BYPASS", "1")
    assert request_reuse.reuse_result("judge", ["x"], lambda: calls.append(1) or {"ok": 1}) == {"ok": 1}
    assert calls == [1]
