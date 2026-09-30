import tempfile
import threading
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from api_fixture import main
from identity_fixture import completed_baseline
from app.governance import GovernanceStore


class GovernanceApiTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.previous_store = main.store
        main.store = GovernanceStore(Path(self.directory.name) / "demo.db")
        self.addCleanup(setattr, main, "store", self.previous_store)
        self.client = TestClient(main.app)

    def test_dataset_exposes_audited_candidates_not_seeded_scores(self):
        response = self.client.get("/api/dataset")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 40)
        self.assertEqual(response.json()[0]["review_status"], "human_review_pending")

    def test_evaluation_is_blocked_until_a_human_approves_a_question(self):
        response = self.client.post("/api/evaluations/run", headers={"Origin": "http://127.0.0.1:5174"})

        self.assertEqual(response.status_code, 409)
        self.assertIn("approved", response.json()["detail"])

    def test_untrusted_origin_cannot_trigger_manual_work(self):
        response = self.client.post("/api/governance/questions/GGC-001/probe", headers={"Origin": "https://evil.example"})

        self.assertEqual(response.status_code, 403)

    def test_documents_remain_the_four_formal_pdfs(self):
        response = self.client.get("/api/documents")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 4)

    def test_mini_generation_returns_run_before_worker_finishes_and_persists_progress(self):
        entered, release = threading.Event(), threading.Event()
        previous_service = main.ai_service

        class SlowService:
            model = "test-model"

            def generate_mini_golden(self, chunks, on_progress=None):
                on_progress({"stage": "coverage", "coverage_plan": [{"slot": "Q01"}]})
                on_progress({"stage": "generating", "slot": "Q01", "attempt": 1, "completed_slots": 0, "slot_audit": {"Q01": [{"attempt": 1, "validation_error": "invalid question/category"}]}, "candidate": None})
                entered.set()
                release.wait(5)
                return {"status": "failed", "profile": {"positive": 8, "ablation": 4, "negative": 8}, "coverage_plan": [{"slot": "Q01"}], "hard_validation": {"status": "failed"}, "slot_audit": {"Q01": [{"attempt": 1, "validation_error": None}]}, "failed_slots": ["Q02"]}

        main.ai_service = SlowService()
        self.addCleanup(setattr, main, "ai_service", previous_service)
        self.addCleanup(release.set)
        response = self.client.post("/api/governance/generate-mini", headers={"Origin": "http://127.0.0.1:5174"})
        self.assertEqual(response.status_code, 202)
        run_id = response.json()["run_id"]
        self.assertTrue(entered.wait(2))
        status = self.client.get(f"/api/governance/generation-runs/{run_id}")
        self.assertEqual(status.status_code, 200)
        self.assertEqual(status.json()["artifacts"]["hard_validation"]["progress"]["completed_slots"], 0)
        self.assertEqual(self.client.post("/api/governance/generate-mini", headers={"Origin": "http://127.0.0.1:5174"}).status_code, 409)
        release.set()
        for _ in range(50):
            if self.client.get(f"/api/governance/generation-runs/{run_id}").json()["status"] == "needs_regeneration":
                break
            threading.Event().wait(0.01)
        self.assertEqual(self.client.get(f"/api/governance/generation-runs/{run_id}").json()["status"], "needs_regeneration")
        self.assertEqual(self.client.get("/api/dataset").json().__len__(), 40)

    def test_partial_run_blocks_a_new_full_generation(self):
        run_id = main.store.start_generation_run("mock-provider")
        main.store.update_generation_run(run_id, status="needs_regeneration", progress={"stage": "needs_regeneration"})
        response = self.client.post("/api/governance/generate-mini", headers={"Origin": "http://127.0.0.1:5174"})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"], "当前 V1 Mini 尚有失败 Slot 待补齐，请先完成当前 Run。")
        self.assertEqual(len(main.store.generation_runs()), 1)

    def test_monitoring_trigger_is_pending_until_human_confirm(self):
        completed_baseline(main.store)
        event = self.client.post("/api/monitoring/events", json={"question": "安全问题", "answer": "错误回答", "bad_case": True, "severity": "critical"}, headers={"Origin": "http://127.0.0.1:5174"})
        self.assertEqual(event.status_code, 201)
        trigger = event.json()["trigger"]
        self.assertEqual(trigger["status"], "pending_human_confirm")
        confirmed = self.client.post(f"/api/monitoring/triggers/{trigger['id']}/confirm", json={"decision": "approved"}, headers={"Origin": "http://127.0.0.1:5174"})
        self.assertEqual(confirmed.status_code, 200)
        self.assertEqual(confirmed.json()["status"], "human_confirmed")

    def test_optimization_returns_the_latest_persisted_experiment(self):
        completed_baseline(main.store, run_id="EVAL-real")
        experiment_id = main.store.create_experiment("EVAL-real")
        main.store.save_agent_trace(experiment_id, "completed", {"root_cause_cluster": "Retrieval Miss"})

        response = self.client.get("/api/optimization")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], experiment_id)
        self.assertEqual(response.json()["status"], "completed")
        self.assertIsNone(response.json()["recommendation"])

    def test_pipeline_contract_uses_frozen_policy(self):
        from app.policy import search_space_contract

        response = self.client.get("/api/pipeline")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["search_space"], search_space_contract())
        self.assertEqual(response.json()["index"]["embedding_model"], main.corpus.index_info()["embedding_model"])

    def test_scheme_preview_only_uses_persisted_config(self):
        old_service = main.ai_service

        class PreviewService:
            def answer(self, question, config):
                return {"answer": question, "retrieval": [], "latency_ms": 1, "mode": "local", "model": None, "config_seen": config}

        main.ai_service = PreviewService()
        self.addCleanup(setattr, main, "ai_service", old_service)
        headers = {"Origin": "http://127.0.0.1:5174"}
        invalid = self.client.post("/api/preview/scheme", json={"question": "问题", "scheme_id": "missing"}, headers=headers)
        self.assertEqual(invalid.status_code, 404)
        self.assertEqual(self.client.post("/api/preview/scheme", json={"question": "问题", "scheme_id": "baseline"}, headers=headers).status_code, 404)
        experiment = main.store.create_experiment("EVAL-test")
        main.store.save_candidate(experiment, "R1-A", {"candidate_k": 24, "top_k": 4}, {"candidate_label": "A"})
        candidate_id = f"{experiment}-R1-A"
        candidate = self.client.post("/api/preview/scheme", json={"question": "问题", "scheme_id": candidate_id}, headers=headers)
        self.assertEqual(candidate.status_code, 200)
        self.assertEqual(candidate.json()["config_seen"]["candidate_k"], 24)
        self.assertEqual(candidate.json()["pipeline"], "candidate")
        self.assertEqual(self.client.post("/api/preview/scheme", json={"question": "问题", "scheme_id": candidate_id, "config": {"candidate_k": 999}}, headers=headers).json()["config_seen"]["candidate_k"], 24)
        production = self.client.post("/api/preview/scheme", json={"question": "问题", "scheme_id": "baseline-v1"}, headers=headers)
        self.assertEqual(production.status_code, 200)
        self.assertEqual(production.json()["pipeline"], "production")
        self.assertEqual(production.json()["config_seen"]["candidate_k"], 12)

    def test_publish_blocks_an_incomplete_a_b_c_round_without_old_approval_routes(self):
        experiment = main.store.create_experiment("EVAL-real")
        candidate_id = f"{experiment}-R1-A"
        main.store.save_candidate(experiment, "R1-A", {}, {"round": 1, "candidate_label": "A"})
        main.store.finish_candidate(candidate_id, "evaluated", {"qualification": {"qualified": True}})

        response = self.client.post(f"/api/candidates/{candidate_id}/publish", json={"decision": "approved"}, headers={"Origin": "http://127.0.0.1:5174"})

        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.client.post(f"/api/candidates/{candidate_id}/approval", json={"decision": "approved"}).status_code, 404)
        self.assertEqual(self.client.post(f"/api/candidates/{candidate_id}/release-approval", json={"decision": "approved"}).status_code, 404)


if __name__ == "__main__":
    unittest.main()
