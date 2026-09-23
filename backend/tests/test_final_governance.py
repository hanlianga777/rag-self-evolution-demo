import tempfile
import unittest
from pathlib import Path

from app.governance import GovernanceStore
from app.evaluation import summarize_evaluation_cases


class FinalGovernanceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.store = GovernanceStore(Path(self.directory.name) / "demo.db")

    def test_monitoring_trigger_requires_human_confirmation(self):
        event = self.store.record_monitoring_event(
            question="安全测试", answer="错误答案", bad_case=True, severity="critical", determinable=True,
        )
        trigger = self.store.optimization_trigger_for_event(event["id"])

        self.assertEqual(trigger["status"], "pending_human_confirm")
        self.assertFalse(self.store.trigger_is_confirmed(trigger["id"]))
        self.store.confirm_optimization_trigger(trigger["id"], "local_user")
        self.assertTrue(self.store.trigger_is_confirmed(trigger["id"]))

    def test_four_recent_ordinary_bad_cases_create_one_pending_trigger(self):
        for number in range(4):
            self.store.record_monitoring_event(
                question=f"问题 {number}", answer="可判定回答", bad_case=True, severity="ordinary", determinable=True,
            )
        triggers = self.store.optimization_triggers()

        self.assertEqual(len(triggers), 1)
        self.assertEqual(triggers[0]["reason"], "recent_20_bad_cases>=4")

    def test_evaluation_summary_keeps_missing_groups_not_evaluable(self):
        result = summarize_evaluation_cases([
            {"test_category": "positive", "judge_result": {"correctness": 4, "faithfulness": 1, "completeness": 1, "behavior_pass": True}, "programmatic_metrics": {"latency_ms": 100, "retrieval_hit": True, "retrieval_precision": 1, "retrieval_rank": 1}},
        ])

        self.assertEqual(result["gates"]["total"], 11)
        self.assertFalse(result["gates"]["passed"])
        self.assertEqual(result["overall_score_status"], "NOT_EVALUABLE")
        self.assertIn("ttft_seconds", result["comparison_metrics"])

    def test_probe_uses_frozen_30_30_40_score_and_evidence_failure_cannot_be_compensated(self):
        item = self.store.question("GGC-001")
        result = self.store.record_probe_result(item["id"], {
            "question_quality": 30,
            "golden_answer_quality": 30,
            "evidence_support": 20,
            "evidence_direct_failure": True,
            "reason": "Evidence cannot support the Golden Answer",
            "rule_version": "v1.0.1",
        })

        self.assertEqual(result["score"], 80)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(self.store.question(item["id"])["probe_status"], "needs_revision")

    def test_qc_requires_zero_to_hundred_score_at_least_85_and_priority(self):
        self.store.record_probe_result("GGC-001", {
            "question_quality": 30, "golden_answer_quality": 30, "evidence_support": 40,
            "evidence_direct_failure": False, "reason": "supported", "rule_version": "v1.0.1",
        })
        low = self.store.record_qc("GGC-001", {"score": 84, "priority": "P1", "reason": "needs revision", "model": "test"}, "passed")

        self.assertEqual(low["status"], "qc_failed")
        self.assertEqual(self.store.question("GGC-001")["review_status"], "needs_revision")

    def test_human_confirm_creates_a_linked_optimization_run_without_generating_candidates(self):
        event = self.store.record_monitoring_event(question="安全题", answer="错误", bad_case=True, severity="critical", determinable=True)
        trigger = self.store.optimization_trigger_for_event(event["id"])

        confirmed = self.store.confirm_optimization_trigger(trigger["id"], "reviewer")

        self.assertEqual(confirmed["status"], "human_confirmed")
        self.assertTrue(confirmed["optimization_run_id"])
        self.assertEqual(self.store.experiment(confirmed["optimization_run_id"])["status"], "pending_agent")

    def test_mini_generation_requires_exact_profile_and_never_auto_approves(self):
        candidates = []
        for category, count in (("positive", 8), ("ablation", 4), ("negative", 8)):
            for index in range(count):
                candidates.append({"test_category": category, "question": f"{category}-{index}", "reference_answer": "证据答案" if category != "negative" else None, "expected_behavior": "insufficient_evidence" if category == "negative" else None, "evidence": [{"source_chunk_ids": ["C1"], "evidence_key_points": ["支持"]}] if category != "negative" else []})

        generated = self.store.save_mini_golden_candidates(candidates, "test-model")

        self.assertEqual(len(generated), 20)
        self.assertTrue(all(item["stage"] == "candidate" and item["review_status"] == "human_review_pending" for item in generated))
        artifacts = self.store.generation_artifacts(generated[0]["raw"]["generation_run_id"])
        self.assertEqual(artifacts["hard_validation"]["counts"], {"positive": 8, "ablation": 4, "negative": 8})
        self.assertEqual(len(artifacts["coverage_plan"]), 20)

    def test_batch_review_preflights_every_candidate_before_writing_any_approval(self):
        candidates = []
        for category, count in (("positive", 8), ("ablation", 4), ("negative", 8)):
            for index in range(count):
                candidates.append({"test_category": category, "question": f"{category}-{index}", "reference_answer": "证据答案" if category != "negative" else None, "expected_behavior": "insufficient_evidence" if category == "negative" else None, "evidence": [{"source_chunk_ids": ["C1"], "evidence_key_points": ["支持"]}] if category != "negative" else []})
        generated = self.store.save_mini_golden_candidates(candidates, "test-model")
        for item in generated[:-1]:
            self.store.record_probe_result(item["id"], {"question_quality": 30, "golden_answer_quality": 30, "evidence_support": 40, "evidence_direct_failure": False, "reason": "test"})
            self.store.record_qc(item["id"], {"score": 90, "priority": "P2", "reason": "test", "model": "test"}, "passed")
        with self.assertRaisesRegex(ValueError, "All Mini"):
            self.store.review_generation_batch([item["id"] for item in generated], "reviewer")
        self.assertEqual(sum(item["stage"] == "golden" for item in self.store.questions()), 0)

    def test_alias_mapping_uses_only_explicitly_approved_entries(self):
        self.assertEqual(self.store.approved_aliases(), {})
        self.store.approve_alias("B50", "KIRA B 50", "reviewer")
        self.assertEqual(self.store.approved_aliases(), {"B50": "KIRA B 50"})


if __name__ == "__main__":
    unittest.main()
