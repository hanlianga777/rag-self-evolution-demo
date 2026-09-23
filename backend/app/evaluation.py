"""Snapshot-bound Evaluation runner and V1.0.1 metric aggregation."""

from __future__ import annotations

import json
from statistics import mean

from .policy import DEFAULT_PIPELINE_CONFIG, calculate_overall_score, evaluate_gates, evaluate_regression, qualify_candidate


def _percentile(values: list[float], percentile: float):
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int((len(ordered) - 1) * percentile))]


def _mean(values: list[float]):
    return round(mean(values), 2) if values else None


def summarize_evaluation_cases(cases: list[dict]) -> dict:
    """Aggregate persisted case records without inventing absent group metrics."""
    groups = {"positive": [], "ablation": [], "negative": []}
    for case in cases:
        if case.get("test_category") in groups:
            groups[case["test_category"]].append(case)

    def quality(group: str, key: str):
        values = []
        for item in groups[group]:
            value = item.get("judge_result", {}).get(key)
            if isinstance(value, (int, float)):
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
    safe = lambda item: 100.0 if item.get("judge_result", {}).get("behavior_pass") else 0.0
    metrics.update({
        "safe_rejection_rate": _mean([safe(item) for item in negatives]),
        "safety_critical_accuracy": _mean([safe(item) for item in negatives if item.get("severity") == "critical"]),
        "prompt_injection_resistance": _mean([safe(item) for item in negatives if item.get("negative_subtype") == "prompt_injection"]),
    })
    latency_seconds = [item["programmatic_metrics"]["latency_ms"] / 1000 for item in cases if isinstance(item.get("programmatic_metrics", {}).get("latency_ms"), (int, float))]
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
    return {
        "completed": len(cases), "failed": sum(not item.get("passed", False) for item in cases),
        "group_metrics": {group: {key: metrics[f"{group}_{key}"] for key in ("correctness", "faithfulness", "completeness")} for group in ("positive", "ablation")},
        "safety_metrics": {key: metrics[key] for key in ("safe_rejection_rate", "safety_critical_accuracy", "prompt_injection_resistance")},
        "metrics": metrics, "gates": evaluate_gates(metrics), "overall_score": overall["score"], "overall_score_status": overall["status"],
        "comparison_metrics": {"ttft_seconds": _mean(ttfts), "ttft_target_status": "WARNING" if ttfts and _mean(ttfts) > 5 else "OK" if ttfts else "NOT_MEASURED", "input_tokens": sum(input_tokens) if input_tokens else None, "output_tokens": sum(output_tokens) if output_tokens else None, "token_cost": round(sum(provider_costs), 6) if provider_costs else None, "token_cost_status": "MEASURED" if provider_costs else "Token Usage / Provider Cost unavailable", "recall_at_k": round(100 * sum(bool(hit) for hit in hits) / len(hits), 2) if hits else None, "precision_at_k": _mean(precisions), "mrr": _mean(reciprocal_ranks)},
        "bad_case_count": sum(not item.get("passed", False) for item in cases),
    }


class EvaluationRunner:
    def __init__(self, store, runtime):
        self.store, self.runtime = store, runtime

    def start_baseline(self):
        approved = self.store.questions("golden")
        categories = {item["test_category"] for item in approved}
        negative_subtypes = {item.get("negative_subtype") for item in approved if item["test_category"] == "negative"}
        if not {"positive", "ablation", "negative"}.issubset(categories) or not {"safety_critical", "prompt_injection"}.issubset(negative_subtypes):
            raise ValueError("正式评测需要完整 approved Golden：Positive、Ablation、Negative、Safety Critical 与 Prompt Injection")
        snapshot = self.store.create_dataset_snapshot()
        production = self.store.active_production() or {"config": {}}
        config = {**DEFAULT_PIPELINE_CONFIG, **production["config"]}
        judge_meta = {"model": self.runtime.model, "prompt_version": "judge-v1", "scoring_policy": "v1.0.1-gates"}
        return self.store.create_evaluation_run(snapshot, config, judge_meta), approved, config

    def _case_result(self, item: dict, config: dict):
        expected = item["reference_answer"] or item["raw"].get("expected_behavior", "拒答或澄清")
        execution = self.runtime.answer(item["question"], config)
        judge = self.runtime.judge(item["question"], expected, execution["answer"], item["test_category"])
        expected_chunks = {chunk_id for evidence in item["evidence"] for chunk_id in evidence.get("source_chunk_ids", [])}
        retrieved = [entry.get("chunk_id") for entry in execution["retrieval"]]
        matching = [index + 1 for index, chunk_id in enumerate(retrieved) if chunk_id in expected_chunks]
        hit = bool(matching) if expected_chunks else None
        precision = len(matching) / len(retrieved) * 100 if expected_chunks and retrieved else None
        redline = (not judge["behavior_pass"]) or bool(judge.get("unsupported_claims"))
        score = round((judge["correctness"] * 25 + judge["completeness"] * 100 + judge["faithfulness"] * 100) / 3, 2)
        failure_tags = []
        if not judge["behavior_pass"]:
            failure_tags.append("BehaviorFailure")
        if judge.get("unsupported_claims"):
            failure_tags.append("UnsupportedAnswer")
        if judge["correctness"] == 0:
            failure_tags.append("IncorrectAnswer")
        if item["test_category"] != "negative" and expected_chunks and not hit:
            failure_tags.append("RetrievalMiss")
        severity = "critical" if item["raw"].get("criticality") == "high" or item.get("negative_subtype") == "safety_critical" else "ordinary"
        root_cause = "Safety" if not judge["behavior_pass"] else "Retrieval" if "RetrievalMiss" in failure_tags else "Generation" if failure_tags else "None"
        return {"question": item["question"], "reference_answer": expected, "test_category": item["test_category"], "negative_subtype": item.get("negative_subtype"), "severity": severity, "retrieved_chunks": execution["retrieval"], "model_answer": execution["answer"], "programmatic_metrics": {"retrieval_hit": hit, "retrieval_precision": precision, "retrieval_rank": matching[0] if matching else None, "latency_ms": execution["latency_ms"], "ttft_ms": execution.get("ttft_ms"), "input_tokens": execution.get("input_tokens"), "output_tokens": execution.get("output_tokens"), "provider_cost": execution.get("provider_cost")}, "judge_result": judge, "overall_score": score, "failure_tags": failure_tags, "root_cause": {"primary": root_cause, "secondary": [], "evidence_match": hit}, "passed": not failure_tags, "redline_pass": not redline}

    def execute_baseline(self, run_id, approved, config):
        cases = []
        try:
            for item in approved:
                result = self._case_result(item, config)
                self.store.record_evaluation_case(run_id, item["id"], result)
                cases.append(result)
                if not result["passed"]:
                    self.store.record_bad_case(run_id, item["id"], "Safety" if not result["judge_result"]["behavior_pass"] else "Generation", result["severity"], result)
            return self.store.finish_evaluation_run(run_id, "completed", summarize_evaluation_cases(cases))
        except Exception as error:
            return self.store.finish_evaluation_run(run_id, "partial" if cases else "failed", summarize_evaluation_cases(cases), str(error))

    def start_candidate(self, candidate_id: str):
        candidate = self.store.candidate(candidate_id)
        if candidate is None:
            raise ValueError("Candidate 不存在")
        experiment = self.store.experiment(candidate["experiment_id"])
        baseline = self.store.evaluation_run(experiment["baseline_run_id"]) if experiment else None
        if baseline is None or baseline["status"] != "completed":
            raise ValueError("Candidate 必须基于已完成的 Baseline 运行")
        snapshot = json.loads(baseline["dataset_snapshot_json"])
        approved = [self.store.question(question_id) for question_id in snapshot["question_ids"]]
        config = {**candidate["config"], "run_target": "sandbox_candidate", "candidate_id": candidate_id}
        return self.store.create_evaluation_run(snapshot, config, {"model": self.runtime.model, "scoring_policy": "v1.0.1-gates"}), approved, config, candidate, baseline

    def execute_candidate(self, run_id, approved, config, candidate, baseline):
        run = self.execute_baseline(run_id, approved, config)
        baseline_cases = {item["question_id"]: item for item in self.store.evaluation_case_results(baseline["id"])}
        candidate_cases = {item["question_id"]: item for item in self.store.evaluation_case_results(run_id)}
        failed = [question_id for question_id, item in baseline_cases.items() if not item.get("passed")]
        fixed = sum(candidate_cases.get(question_id, {}).get("passed", False) for question_id in failed)
        passed = [(question_id, item) for question_id, item in baseline_cases.items() if item.get("passed")]
        regression = evaluate_regression(new_critical_failures=sum(not candidate_cases.get(question_id, {}).get("passed", False) and item.get("severity") == "critical" for question_id, item in passed), new_ordinary_failures=sum(not candidate_cases.get(question_id, {}).get("passed", False) and item.get("severity") != "critical" for question_id, item in passed))
        qualification = qualify_candidate(run["result"]["gates"], regression, fixed, len(failed), run["result"]["bad_case_count"])
        result = {"evaluation_run_id": run_id, "baseline_run_id": baseline["id"], **run["result"], "regression": regression, "target_bad_cases_fixed": fixed, "qualification": qualification, "recommendation": None}
        finished = self.store.finish_candidate(candidate["id"], "evaluated", result)
        recommendation = self.store.refresh_recommendation(candidate["experiment_id"])
        return {**finished, "recommendation": recommendation}

    def run_baseline(self):
        return self.execute_baseline(*self.start_baseline())

    def run_candidate(self, candidate_id: str):
        return self.execute_candidate(*self.start_candidate(candidate_id))
