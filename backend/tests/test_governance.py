import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.evaluation import EvaluationRunner
from app.governance import GovernanceStore
from app.optimization import OptimizationAgent


class FakeRetriever:
    def search(self, question, limit=4, min_score=None):
        return [{
            "document_id": "DOC-001",
            "document": "卡赫_KIRA_B_50完整操作说明_中文版.pdf",
            "chunk_id": "KIRA-B50-CHUNK-0003",
            "section": "一般提示",
            "page_start": 2,
            "page_end": 2,
            "score": 0.73,
            "content": "第一次调试前应完整阅读操作说明书；可在设备显示屏查阅或下载到智能手机，并为后续使用妥善保管说明书。",
        }]


class GovernanceStoreTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.store = GovernanceStore(Path(self.directory.name) / "demo.db")

    def test_migration_imports_the_audited_candidate_draft_without_approving_it(self):
        summary = self.store.dataset_summary()

        self.assertEqual(summary["total"], 0)
        self.assertEqual(summary["legacy_total"], 40)
        self.assertEqual(summary["approved"], 0)
        self.assertEqual(self.store.question("GGC-033")["negative_subtype"], "ambiguous")
        self.assertEqual(self.store.question("GGC-001")["review_status"], "human_review_pending")
        self.assertEqual(self.store.question("GGC-001")["qc_status"], "qc_pending")

    def test_human_approval_creates_an_auditable_golden_snapshot(self):
        with self.assertRaisesRegex(ValueError, "Probe"):
            self.store.review_question("GGC-001", "approved", "local_user")

        self.store.run_probe("GGC-001", FakeRetriever(), [{
            "chunk_id": "KIRA-B50-CHUNK-0003",
            "text": "第一次调试前应完整阅读操作说明书；可在设备显示屏查阅或下载到智能手机，并为后续使用妥善保管说明书。",
        }])
        self.store.record_qc("GGC-001", {"score": 90, "priority": "P2", "issues": [], "reason": "证据自洽", "model": "test"}, "passed")
        self.store.review_question("GGC-001", "approved", "local_user")

        snapshot = self.store.create_dataset_snapshot()

        self.assertEqual(snapshot["question_ids"], ["GGC-001"])
        self.assertEqual(self.store.question("GGC-001")["stage"], "golden")
        self.assertEqual(self.store.review_history("GGC-001")[0]["decision"], "approved")

    def test_changing_approved_question_evidence_or_answer_invalidates_approval(self):
        self.store.run_probe("GGC-001", FakeRetriever(), [{"chunk_id": "KIRA-B50-CHUNK-0003", "text": "第一次调试前应完整阅读操作说明书；可在设备显示屏查阅或下载到智能手机，并为后续使用妥善保管说明书。"}])
        self.store.record_qc("GGC-001", {"score": 90, "priority": "P2", "issues": [], "reason": "证据自洽", "model": "test"}, "passed")
        approved = self.store.review_question("GGC-001", "approved", "local_user")
        changed = self.store.update_question(approved["id"], approved["question"], "已修改的答案", approved["evidence"], "local_user")

        self.assertEqual(changed["stage"], "candidate")
        self.assertEqual(changed["review_status"], "human_review_pending")
        self.assertEqual(changed["probe_status"], "probe_pending")
        self.assertEqual(changed["qc_status"], "qc_pending")

    def test_probe_persists_independent_programmatic_vector_and_full_text_signals(self):
        result = self.store.run_probe("GGC-001", FakeRetriever(), [{
            "chunk_id": "KIRA-B50-CHUNK-0003",
            "text": "第一次调试前应完整阅读操作说明书；可在设备显示屏查阅或下载到智能手机，并为后续使用妥善保管说明书。",
        }])

        self.assertTrue(result["programmatic"]["passed"])
        self.assertEqual(result["vector"]["signal"], "observed_only")
        self.assertTrue(result["full_text"]["passed"])
        self.assertEqual(self.store.question("GGC-001")["probe_status"], "probe_passed")

    def test_failed_probe_or_qc_requires_revision_and_qc_cannot_skip_probe(self):
        with self.assertRaisesRegex(ValueError, "Probe"):
            self.store.record_qc("GGC-001", {}, "failed")

        self.store.run_probe("GGC-001", FakeRetriever(), [])
        self.assertEqual(self.store.question("GGC-001")["review_status"], "needs_revision")

        self.store.run_probe("GGC-033", FakeRetriever(), [])
        self.store.record_qc("GGC-033", {"score": 0, "priority": "P0", "reason": "题目需改写", "model": "test"}, "failed")
        self.assertEqual(self.store.question("GGC-033")["qc_status"], "qc_failed")
        self.assertEqual(self.store.question("GGC-033")["review_status"], "needs_revision")

    def test_negative_probe_records_a_normalized_full_text_scan(self):
        result = self.store.run_probe("GGC-039", FakeRetriever(), [{"chunk_id": "KIRA-B50-CHUNK-0003", "text": "机器人操作说明"}])

        self.assertIn("normalized_query", result["full_text"])
        self.assertEqual(result["full_text"]["corpus_match_chunk_ids"], [])


class GovernanceApiTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.previous_store = main.store
        main.store = GovernanceStore(Path(self.directory.name) / "demo.db")
        self.addCleanup(setattr, main, "store", self.previous_store)
        self.client = TestClient(main.app)

    def test_governance_endpoints_block_review_until_probe_and_qc_pass(self):
        summary = self.client.get("/api/governance/summary").json()
        review = self.client.post("/api/governance/questions/GGC-001/review", json={"decision": "approved"})

        self.assertEqual(summary["total"], 0)
        self.assertEqual(summary["legacy_total"], 40)
        self.assertEqual(summary["approved"], 0)
        self.assertEqual(review.status_code, 409)
        self.assertIn("Probe", review.json()["detail"])
        self.assertEqual(self.client.get("/api/dataset").json()[0]["id"], "GGC-001")


class FakeEvaluationRuntime:
    model = "test-model"

    def answer(self, question, config):
        return {"answer": "第一次调试前完整阅读操作说明书。", "retrieval": [{"chunk_id": "KIRA-B50-CHUNK-0003", "score": 0.9}], "latency_ms": 7, "input_tokens": 3, "output_tokens": 4}

    def judge(self, question, expected, answer, category):
        return {"correctness": 4, "completeness": 1, "faithfulness": 1, "behavior_pass": True, "reason": "证据充分", "missing_points": [], "unsupported_claims": []}


class EvaluationRunnerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.store = GovernanceStore(Path(self.directory.name) / "demo.db")

    def approve_one(self):
        # A minimal complete three-group snapshot for EvaluationRunner behavior tests.
        with self.store.connection() as connection:
            connection.execute("UPDATE questions SET test_category = ? WHERE id = ?", ("ablation", "GGC-002"))
            connection.execute("UPDATE questions SET negative_subtype = ? WHERE id = ?", ("safety_critical", "GGC-033"))
            connection.execute("UPDATE questions SET negative_subtype = ? WHERE id = ?", ("prompt_injection", "GGC-034"))
        for question_id in ("GGC-001", "GGC-002", "GGC-033", "GGC-034"):
            self.store.record_probe_result(question_id, {"question_quality": 30, "golden_answer_quality": 30, "evidence_support": 40, "evidence_direct_failure": False, "reason": "test", "rule_version": "v1.0.1"})
            self.store.record_qc(question_id, {"score": 90, "priority": "P2", "issues": [], "reason": "test", "model": "test"}, "passed")
            self.store.review_question(question_id, "approved", "local_user")
        self.store.create_dataset_snapshot()

    def test_runner_uses_only_approved_snapshot_and_persists_real_case_results(self):
        self.approve_one()
        run = EvaluationRunner(self.store, FakeEvaluationRuntime()).run_baseline()

        self.assertEqual(run["status"], "completed")
        self.assertEqual(run["run_mode"], "real")
        self.assertEqual(run["result"]["completed"], 4)
        self.assertEqual(run["result"]["overall_score"], 100.0)
        self.assertEqual(run["result"]["overall_score_status"], "PASS")
        self.assertEqual(len(self.store.evaluation_case_results(run["id"])), 4)

    def test_runner_blocks_formal_evaluation_without_an_approved_question(self):
        with self.assertRaisesRegex(ValueError, "Snapshot"):
            EvaluationRunner(self.store, FakeEvaluationRuntime()).run_baseline()

    def test_candidate_run_reuses_the_completed_baseline_snapshot_and_keeps_production_unchanged(self):
        self.approve_one()
        baseline = EvaluationRunner(self.store, FakeEvaluationRuntime()).run_baseline()
        experiment_id = self.store.create_experiment(baseline["id"])
        self.store.save_candidate(experiment_id, "A", {"top_k": 6, "min_score": None}, {"hypothesis": "扩大召回"})

        candidate = EvaluationRunner(self.store, FakeEvaluationRuntime()).run_candidate(f"{experiment_id}-A")

        self.assertEqual(candidate["status"], "evaluated")
        self.assertEqual(candidate["result"]["baseline_run_id"], baseline["id"])
        self.assertEqual(self.store.active_production()["id"], "baseline-v1")

    def test_rank_two_evidence_inside_final_context_is_not_a_ranking_failure(self):
        class RankTwoRuntime(FakeEvaluationRuntime):
            def answer(self, question, config):
                result = super().answer(question, config)
                result["retrieval"] = [{"chunk_id": "NOISE", "score": .95}, {"chunk_id": "KIRA-B50-CHUNK-0003", "score": .9}]
                return result

        result = EvaluationRunner(self.store, RankTwoRuntime())._case_result(self.store.question("GGC-001"), {})

        self.assertNotIn("Ranking Failure", result["failure_tags"])
        self.assertEqual(result["root_cause"]["primary"], "None")

    def test_approved_candidate_can_publish_then_roll_back_without_overwriting_history(self):
        self.approve_one()
        baseline = EvaluationRunner(self.store, FakeEvaluationRuntime()).run_baseline()
        experiment_id = self.store.create_experiment(baseline["id"])
        candidate_id = f"{experiment_id}-A"
        self.store.save_candidate(experiment_id, "A", {"top_k": 6, "min_score": None}, {})
        EvaluationRunner(self.store, FakeEvaluationRuntime()).run_candidate(candidate_id)
        self.store.approve("candidate", candidate_id, "approved", "local_user")
        self.store.approve("release", candidate_id, "approved", "local_user")

        with self.assertRaisesRegex(ValueError, "11/11 Gate"):
            self.store.publish_candidate(candidate_id, "local_user")
        self.assertEqual(self.store.active_production()["id"], "baseline-v1")


class FakeAgentProvider:
    def complete(self, *_args, **_kwargs):
        return '{"root_cause_cluster":"检索范围不足","observed_evidence":["召回缺失"],"candidates":[{"id":"A","config":{"top_k":6},"hypothesis":"扩大召回","proposal":"增加上下文","risk":"延迟"},{"id":"B","config":{"min_score":0.2},"hypothesis":"过滤噪声","proposal":"提升过滤","risk":"拒答"},{"id":"C","config":{"min_score":0.1},"hypothesis":"平衡","proposal":"平衡召回","risk":"召回"}]}'


class OptimizationAgentTests(unittest.TestCase):
    def test_agent_only_persists_valid_a_b_c_configs_from_the_available_tools(self):
        with tempfile.TemporaryDirectory() as directory:
            store = GovernanceStore(Path(directory) / "demo.db")
            store.record_bad_case("EVAL-1", "GGC-001", "Generation", "medium", {"reason": "answer failed"})
            experiment = OptimizationAgent(store, FakeAgentProvider()).generate("EVAL-1")

        self.assertEqual(len(experiment["candidates"]), 3)
        self.assertEqual(experiment["candidates"][0]["config"]["top_k"], 6)


if __name__ == "__main__":
    unittest.main()
