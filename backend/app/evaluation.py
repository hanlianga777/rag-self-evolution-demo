"""Real, snapshot-bound Evaluation runner. It owns no production configuration."""

from __future__ import annotations

import json
from statistics import mean


SCORING_POLICY = {
    "version": "draft-v1",
    "label": "Draft Scoring Policy",
    "weights": {"correctness": 0.35, "completeness": 0.25, "faithfulness": 0.30, "behavior": 0.10},
}


class EvaluationRunner:
    def __init__(self, store, runtime):
        self.store = store
        self.runtime = runtime

    @staticmethod
    def _score(judge):
        return round(100 * (
            judge["correctness"] / 4 * SCORING_POLICY["weights"]["correctness"]
            + judge["completeness"] * SCORING_POLICY["weights"]["completeness"]
            + judge["faithfulness"] * SCORING_POLICY["weights"]["faithfulness"]
            + float(judge["behavior_pass"]) * SCORING_POLICY["weights"]["behavior"]
        ), 2)

    def start_baseline(self):
        approved = self.store.questions("golden")
        if not approved:
            raise ValueError("正式评测需要至少一题 approved Golden Question")
        snapshot = self.store.create_dataset_snapshot()
        production = self.store.active_production() or {"config": {"top_k": 4, "min_score": None}}
        judge_meta = {"model": self.runtime.model, "prompt_version": "judge-v1", "scoring_policy": SCORING_POLICY}
        run_id = self.store.create_evaluation_run(snapshot, production["config"], judge_meta)
        return run_id, approved, production["config"]

    def execute_baseline(self, run_id, approved, config):
        scores, failed = [], 0
        try:
            for item in approved:
                expected = item["reference_answer"] or item["raw"].get("expected_behavior", "拒答或澄清")
                execution = self.runtime.answer(item["question"], config)
                judge = self.runtime.judge(item["question"], expected, execution["answer"], item["test_category"])
                score = self._score(judge)
                expected_chunks = {chunk_id for evidence in item["evidence"] for chunk_id in evidence.get("source_chunk_ids", [])}
                retrieved = [entry.get("chunk_id") for entry in execution["retrieval"]]
                hit = bool(expected_chunks & set(retrieved)) if expected_chunks else None
                redline = (not judge["behavior_pass"]) or bool(judge.get("unsupported_claims"))
                result = {"question": item["question"], "reference_answer": expected, "retrieved_chunks": execution["retrieval"], "model_answer": execution["answer"], "programmatic_metrics": {"retrieval_hit": hit, "latency_ms": execution["latency_ms"], "input_tokens": execution.get("input_tokens"), "output_tokens": execution.get("output_tokens")}, "judge_result": judge, "overall_score": score, "passed": score >= 70 and not redline, "redline_pass": not redline}
                self.store.record_evaluation_case(run_id, item["id"], result)
                scores.append(score)
                if not result["passed"]:
                    failed += 1
                    category = "Safety" if not judge["behavior_pass"] else "Generation"
                    severity = "critical" if redline else "medium"
                    self.store.record_bad_case(run_id, item["id"], category, severity, result)
            result = {"completed": len(scores), "failed": failed, "overall_score": round(mean(scores), 2), "redline_pass": failed == 0, "cost": "Unavailable", "sla": "Pending Calibration"}
            return self.store.finish_evaluation_run(run_id, "completed", result)
        except Exception as error:
            result = {"completed": len(scores), "failed": failed, "overall_score": round(mean(scores), 2) if scores else None, "redline_pass": False, "cost": "Unavailable"}
            return self.store.finish_evaluation_run(run_id, "partial" if scores else "failed", result, str(error))

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
        judge_meta = {"model": self.runtime.model, "prompt_version": "judge-v1", "scoring_policy": SCORING_POLICY}
        return self.store.create_evaluation_run(snapshot, config, judge_meta), approved, config, candidate, baseline

    def execute_candidate(self, run_id, approved, config, candidate, baseline):
        run = self.execute_baseline(run_id, approved, config)
        baseline_cases = {item["question_id"]: item for item in self.store.evaluation_case_results(baseline["id"])}
        candidate_cases = {item["question_id"]: item for item in self.store.evaluation_case_results(run_id)}
        initially_failed = [question_id for question_id, item in baseline_cases.items() if not item.get("passed")]
        fixed = sum(candidate_cases.get(question_id, {}).get("passed") for question_id in initially_failed)
        initially_passed = [question_id for question_id, item in baseline_cases.items() if item.get("passed")]
        regressions = sum(not candidate_cases.get(question_id, {}).get("passed") for question_id in initially_passed)
        latencies = [item.get("programmatic_metrics", {}).get("latency_ms") for item in candidate_cases.values()]
        latencies = sorted(value for value in latencies if isinstance(value, (int, float)))
        result = {"evaluation_run_id": run_id, "baseline_run_id": baseline["id"], "status": run["status"], "overall_score": run["result"].get("overall_score"), "fix_rate": round(100 * fixed / len(initially_failed), 2) if initially_failed else "Not Applicable", "regression_rate": round(100 * regressions / len(initially_passed), 2) if initially_passed else "Not Applicable", "redline_pass": run["result"].get("redline_pass"), "p95_latency_ms": latencies[min(len(latencies) - 1, int(len(latencies) * .95))] if latencies else None}
        return self.store.finish_candidate(candidate["id"], "evaluated" if run["status"] == "completed" else run["status"], result)

    def run_baseline(self):
        return self.execute_baseline(*self.start_baseline())

    def run_candidate(self, candidate_id: str):
        return self.execute_candidate(*self.start_candidate(candidate_id))
