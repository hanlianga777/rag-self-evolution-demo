import tempfile
import threading
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
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
                on_progress({"stage": "generating", "slot": "Q01", "attempt": 1, "completed_slots": 1, "slot_audit": {"Q01": [{"attempt": 1, "validation_error": None}]}})
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
        self.assertEqual(status.json()["artifacts"]["hard_validation"]["progress"]["completed_slots"], 1)
        self.assertEqual(self.client.post("/api/governance/generate-mini", headers={"Origin": "http://127.0.0.1:5174"}).status_code, 409)
        release.set()
        for _ in range(50):
            if self.client.get(f"/api/governance/generation-runs/{run_id}").json()["status"] == "failed":
                break
            threading.Event().wait(0.01)
        self.assertEqual(self.client.get(f"/api/governance/generation-runs/{run_id}").json()["status"], "failed")
        self.assertEqual(self.client.get("/api/dataset").json().__len__(), 40)

    def test_monitoring_trigger_is_pending_until_human_confirm(self):
        event = self.client.post("/api/monitoring/events", json={"question": "安全问题", "answer": "错误回答", "bad_case": True, "severity": "critical"}, headers={"Origin": "http://127.0.0.1:5174"})
        self.assertEqual(event.status_code, 201)
        trigger = event.json()["trigger"]
        self.assertEqual(trigger["status"], "pending_human_confirm")
        confirmed = self.client.post(f"/api/monitoring/triggers/{trigger['id']}/confirm", json={"decision": "approved"}, headers={"Origin": "http://127.0.0.1:5174"})
        self.assertEqual(confirmed.status_code, 200)
        self.assertEqual(confirmed.json()["status"], "human_confirmed")

    def test_optimization_returns_the_latest_persisted_experiment(self):
        experiment_id = main.store.create_experiment("EVAL-real")
        main.store.save_agent_trace(experiment_id, "completed", {"root_cause_cluster": "Retrieval Miss"})

        response = self.client.get("/api/optimization")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], experiment_id)
        self.assertEqual(response.json()["status"], "completed")
        self.assertIsNone(response.json()["recommendation"])

    def test_candidate_approval_blocks_an_incomplete_a_b_c_round(self):
        experiment = main.store.create_experiment("EVAL-real")
        candidate_id = f"{experiment}-R1-A"
        main.store.save_candidate(experiment, "R1-A", {}, {"round": 1, "candidate_label": "A"})
        main.store.finish_candidate(candidate_id, "evaluated", {"qualification": {"qualified": True}})

        response = self.client.post(f"/api/candidates/{candidate_id}/approval", json={"decision": "approved"}, headers={"Origin": "http://127.0.0.1:5174"})

        self.assertEqual(response.status_code, 409)
        self.assertIn("Round A/B/C", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
