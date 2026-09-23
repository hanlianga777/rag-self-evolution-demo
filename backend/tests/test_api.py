import tempfile
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

    def test_monitoring_trigger_is_pending_until_human_confirm(self):
        event = self.client.post("/api/monitoring/events", json={"question": "安全问题", "answer": "错误回答", "bad_case": True, "severity": "critical"}, headers={"Origin": "http://127.0.0.1:5174"})
        self.assertEqual(event.status_code, 201)
        trigger = event.json()["trigger"]
        self.assertEqual(trigger["status"], "pending_human_confirm")
        confirmed = self.client.post(f"/api/monitoring/triggers/{trigger['id']}/confirm", json={"decision": "approved"}, headers={"Origin": "http://127.0.0.1:5174"})
        self.assertEqual(confirmed.status_code, 200)
        self.assertEqual(confirmed.json()["status"], "human_confirmed")


if __name__ == "__main__":
    unittest.main()
