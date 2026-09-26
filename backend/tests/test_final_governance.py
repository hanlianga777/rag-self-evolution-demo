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

    def test_qc_requires_valid_score_but_priority_drives_review(self):
        self.store.record_probe_result("GGC-001", {
            "question_quality": 30, "golden_answer_quality": 30, "evidence_support": 40,
            "evidence_direct_failure": False, "reason": "supported", "rule_version": "v1.0.1",
        })
        low = self.store.record_qc("GGC-001", {"score": 84, "priority": "P1", "reason": "needs revision", "model": "test"}, "passed")

        self.assertEqual(low["status"], "qc_passed")
        self.assertEqual(self.store.question("GGC-001")["review_status"], "human_review_pending")

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

    def test_failed_generation_run_keeps_slot_audit_without_candidate_workspace(self):
        run = self.store.save_failed_generation_run(
            {"positive": 8, "ablation": 4, "negative": 8}, "test-model", [{"slot": "Q01"}],
            {"status": "failed"}, {"Q01": [{"attempt": 3, "validation_error": "duplicate question"}]}, ["Q01"],
        )

        self.assertEqual(run["status"], "failed")
        self.assertEqual(run["question_ids"], [])
        self.assertEqual(run["artifacts"]["slot_audit"]["Q01"][-1]["validation_error"], "duplicate question")
        self.assertEqual(len([item for item in self.store.questions() if item["legacy_question_type"] == "v1_mini"]), 0)

    def test_async_run_keeps_slot_audit_then_atomically_adds_review_pending_candidates(self):
        run_id = self.store.start_generation_run("test-model")
        self.store.update_generation_run(run_id, status="generating", progress={"stage": "generating", "slot": "Q01", "completed_slots": 1}, validation={"slot_audit": {"Q01": [{"attempt": 1, "validation_error": None}]}, "valid_slots": [{"question": "first"}]})
        self.assertEqual(self.store.generation_run(run_id)["artifacts"]["hard_validation"]["progress"]["completed_slots"], 1)
        self.assertEqual(len([item for item in self.store.questions() if item["legacy_question_type"] == "v1_mini"]), 0)
        saved = self.store.save_mini_golden_candidates(self._mini_candidates(), "test-model", run_id=run_id)
        self.assertEqual(len(saved), 20)
        self.assertEqual(self.store.generation_run(run_id)["status"], "probing")
        self.assertEqual(self.store.generation_run(run_id)["artifacts"]["slot_audit"]["Q01"][0]["attempt"], 1)
        self.assertTrue(all(item["review_status"] == "human_review_pending" for item in saved))

    def test_ambiguous_negative_uses_answerability_judge_and_rejects_fake_negative(self):
        candidates = self._mini_candidates()
        negative = next(item for item in self.store.save_mini_golden_candidates(candidates, "test-model") if item["test_category"] == "negative")

        class AmbiguousRetriever:
            def search(self, *_args, **_kwargs):
                return [{"chunk_id": "C1", "score": .8}]

        result = self.store.run_probe(negative["id"], AmbiguousRetriever(), [{"chunk_id": "C1", "text": "无关正文"}], answerability_judge=lambda *_: {"answerable": True, "confidence": .9, "reason": "存在足够证据", "supporting_chunk_ids": ["C1"]})

        self.assertEqual(result["classification"], "FAKE_NEGATIVE_RISK")
        self.assertEqual(result["probe_details"]["negative_checks"]["answerability"]["answerable"], True)

    def test_recommendation_waits_for_all_three_candidates_in_the_round(self):
        experiment = self.store.create_experiment("EVAL-1")
        for label in "ABC":
            candidate_id = f"{experiment}-R1-{label}"
            self.store.save_candidate(experiment, f"R1-{label}", {"top_k": 4}, {"round": 1, "candidate_label": label})
            if label == "A":
                self.store.finish_candidate(candidate_id, "evaluated", self._qualified_result())

        recommendation = self.store.refresh_recommendation(experiment)

        self.assertEqual(recommendation["status"], "Needs Report Confirmation")
        self.assertEqual(len(recommendation['comparison']), 3)

    def test_round_budget_is_derived_from_evaluated_candidates(self):
        experiment = self.store.create_experiment("EVAL-1")
        for label in "ABC":
            candidate_id = f"{experiment}-R1-{label}"
            self.store.save_candidate(experiment, f"R1-{label}", {"top_k": 4}, {"round": 1, "candidate_label": label})
            self.store.finish_candidate(candidate_id, "evaluated", self._qualified_result(False))

        self.assertEqual(self.store.experiment(experiment)["evaluation_budget"], {"used": 3, "max": 12, 'reserved_for_d': 1})

    def test_multiple_pareto_candidates_require_human_recommendation(self):
        experiment = self.store.create_experiment("EVAL-1")
        for label in "ABC":
            candidate_id = f"{experiment}-R1-{label}"
            self.store.save_candidate(experiment, f"R1-{label}", {"top_k": 4}, {"round": 1, "candidate_label": label})
            self.store.finish_candidate(candidate_id, "evaluated", self._qualified_result(label != "C"))

        recommendation = self.store.refresh_recommendation(experiment)

        self.assertEqual(recommendation["status"], "Needs Report Confirmation")
        selected = self.store.select_recommendation(experiment, f"{experiment}-R1-A", "reviewer")
        self.assertEqual(selected['report_confirmation']['winner_id'], f"{experiment}-R1-A")
        self.assertEqual(selected['status'], 'Needs Composite')

    @staticmethod
    def _qualified_result(qualified=True):
        return {"qualification": {"qualified": qualified}, "metrics": {"positive_correctness": 80}, "comparison_metrics": {"recall_at_k": 90}, "gates": {"passed": qualified, "passed_count": 11, "total": 11}, "regression": {"passed": qualified, "status": "PASS" if qualified else "FAIL"}, "target_bad_cases_fixed": 1, "bad_case_count": 1}

    def _mini_candidates(self):
        candidates = []
        for category, count in (("positive", 8), ("ablation", 4), ("negative", 8)):
            for index in range(count):
                candidates.append({"test_category": category, "question": f"{category}-negative-check-{index}", "reference_answer": "证据答案" if category != "negative" else None, "expected_behavior": "insufficient_evidence" if category == "negative" else None, "evidence": [{"source_chunk_ids": ["C1"], "evidence_key_points": ["支持"]}] if category != "negative" else []})
        return candidates

    def test_batch_review_preflights_every_candidate_before_writing_any_approval(self):
        candidates = []
        for category, count in (("positive", 8), ("ablation", 4), ("negative", 8)):
            for index in range(count):
                candidates.append({"test_category": category, "question": f"{category}-{index}", "reference_answer": "证据答案" if category != "negative" else None, "expected_behavior": "insufficient_evidence" if category == "negative" else None, "evidence": [{"source_chunk_ids": ["C1"], "evidence_key_points": ["支持"]}] if category != "negative" else []})
        generated = self.store.save_mini_golden_candidates(candidates, "test-model")
        for item in generated[:-1]:
            self.store.record_probe_result(item["id"], {"question_quality": 30, "golden_answer_quality": 30, "evidence_support": 40, "evidence_direct_failure": False, "reason": "test"})
            self.store.record_qc(item["id"], {"score": 90, "priority": "P2", "reason": "test", "model": "test"}, "passed")
        with self.assertRaisesRegex(ValueError, "Probe"):
            self.store.review_generation_batch([item["id"] for item in generated], "reviewer", confirmed_manual_review=True)
        self.assertEqual(sum(item["stage"] == "golden" for item in self.store.questions()), 0)

    def test_batch_review_requires_explicit_confirmation_and_freezes_version(self):
        candidates = []
        for category, count in (("positive", 8), ("ablation", 4), ("negative", 8)):
            for index in range(count):
                candidates.append({"test_category": category, "question": f"{category}-{index}", "reference_answer": "证据答案" if category != "negative" else None, "expected_behavior": "insufficient_evidence" if category == "negative" else None, "evidence": [{"source_chunk_ids": ["C1"], "evidence_key_points": ["支持"]}] if category != "negative" else []})
        generated = self.store.save_mini_golden_candidates(candidates, "test-model")
        for item in generated:
            self.store.record_probe_result(item["id"], {"question_quality": 30, "golden_answer_quality": 30, "evidence_support": 40, "evidence_direct_failure": False, "reason": "test"})
            self.store.record_qc(item["id"], {"score": 90, "priority": "P2", "reason": "test", "model": "test"}, "passed")
        with self.assertRaisesRegex(ValueError, "confirmation"):
            self.store.review_generation_batch([item["id"] for item in generated], "reviewer", confirmed_manual_review=False)

        reviewed = self.store.review_generation_batch([item["id"] for item in generated], "reviewer", confirmed_manual_review=True)
        self.assertIn("snapshot", reviewed)
        snapshot = self.store.create_generation_snapshot(generated[0]["raw"]["generation_run_id"])
        self.assertEqual(len(snapshot["question_ids"]), 20)
        self.assertEqual(snapshot["generation_run_id"], generated[0]["raw"]["generation_run_id"])

    def test_probe_keeps_valid_evidence_as_retrieval_incoherent(self):
        candidates = []
        for category, count in (("positive", 8), ("ablation", 4), ("negative", 8)):
            for index in range(count):
                candidates.append({"test_category": category, "question": f"{category}-{index}", "reference_answer": "证据答案" if category != "negative" else None, "expected_behavior": "insufficient_evidence" if category == "negative" else None, "evidence": [{"source_chunk_ids": ["C1"], "evidence_key_points": ["支持"]}] if category != "negative" else []})
        item = self.store.save_mini_golden_candidates(candidates, "test-model")[0]

        class PipelineRetriever:
            def retrieve(self, *_args, **_kwargs):
                return [{"chunk_id": "OTHER", "score": .8, "final_score": .8}]

        result = self.store.run_probe(item["id"], PipelineRetriever(), [{"chunk_id": "C1", "text": "支持证据"}])
        self.assertTrue(result["passed"])
        self.assertEqual(result["classification"], "RETRIEVAL_INCOHERENT")
        self.store.record_qc(item["id"], {"score": 90, "priority": "P2", "reason": "原文支持"}, "passed")
        self.assertEqual(self.store.question(item["id"])["review_status"], "human_review_pending")

    def test_alias_mapping_uses_only_explicitly_approved_entries(self):
        self.assertEqual(self.store.approved_aliases(), {})
        self.store.approve_alias("B50", "KIRA B 50", "reviewer")
        self.assertEqual(self.store.approved_aliases(), {"B50": "KIRA B 50"})


if __name__ == "__main__":
    unittest.main()
