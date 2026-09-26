"""V1.1 contracts: current-run provenance and one human release action."""

import tempfile
import unittest
from pathlib import Path

from app.governance import GovernanceStore
from app.policy import DEFAULT_PIPELINE_CONFIG


class V11ClosureTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.store = GovernanceStore(Path(directory.name) / "demo.db")

    def test_overview_summary_excludes_legacy_and_previous_runs(self):
        candidates = []
        for number in range(20):
            category = "positive" if number < 8 else "ablation" if number < 12 else "negative"
            candidates.append({
                "coverage_slot": f"Q{number + 1:02d}", "test_category": category,
                "question": f"问题 {number + 1}",
                "reference_answer": None if category == "negative" else "说明书原文",
                "expected_behavior": "insufficient_evidence" if category == "negative" else None,
                "evidence": [] if category == "negative" else [{"source_chunk_ids": ["C1"], "evidence_key_points": ["说明书原文"]}],
            })
        rows = self.store.save_mini_golden_candidates(candidates, "fixture")
        with self.store.connection() as connection:
            connection.execute("UPDATE golden_generation_runs SET status='completed' WHERE id=?", (rows[0]["raw"]["generation_run_id"],))
        summary = self.store.dataset_summary()
        self.assertEqual(summary["total"], 20)
        self.assertEqual(summary["pending_review"], 20)
        self.assertEqual(summary["legacy_total"], 40)

    def test_publish_is_the_only_human_release_action_and_is_atomic(self):
        run_id = self.store.create_evaluation_run({"id": "GD-fixture"}, DEFAULT_PIPELINE_CONFIG, {"model": "fixture"})
        self.store.finish_evaluation_run(run_id, "completed", {"gates": {"passed": True}})
        experiment_id = self.store.create_experiment(run_id)
        for label in "ABC":
            self.store.save_candidate(experiment_id, label, DEFAULT_PIPELINE_CONFIG, {"round": 1, "candidate_label": label})
            self.store.finish_candidate(f"{experiment_id}-{label}", "evaluated", {
                "qualification": {"qualified": label == "A"}, "evaluation_run_id": run_id,
                "gates": {"passed": label == "A", "passed_count": 11 if label == "A" else 0},
                "regression": {"passed": label == "A"},
            })
        candidate_id = f"{experiment_id}-A"
        self.store.confirm_experiment_report(experiment_id, candidate_id, "test_human")
        self.store.create_composite(experiment_id)
        before = len(self.store.production_versions())
        published = self.store.publish_candidate(candidate_id, "human_reviewer")
        self.assertEqual(len(self.store.production_versions()), before + 1)
        self.assertEqual(published["snapshot"]["human_release"]["actor"], "human_reviewer")
        self.assertEqual(self.store.latest_approval("human_release", candidate_id)["decision"], "approved")
        with self.assertRaises(ValueError):
            self.store.publish_candidate(candidate_id, "human_reviewer")
        self.assertEqual(len(self.store.production_versions()), before + 1)


if __name__ == "__main__":
    unittest.main()
