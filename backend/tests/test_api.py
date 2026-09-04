import os
import unittest

from fastapi.testclient import TestClient

os.environ["RAG_FORCE_MOCK"] = "1"

from app.main import app


class DemoApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_seeded_overview_matches_baseline_story(self):
        response = self.client.get("/api/overview")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["kpis"]["overall_score"], 72.4)
        self.assertEqual(payload["kpis"]["bad_cases"], "8 / 40")
        self.assertEqual(payload["recommended_candidate"], "Candidate B")

    def test_evaluation_has_eight_bad_cases_and_recommends_b(self):
        evaluation = self.client.get("/api/evaluation").json()
        bad_cases = self.client.get("/api/bad-cases").json()
        optimization = self.client.get("/api/optimization").json()

        self.assertEqual(evaluation["questions"], 40)
        self.assertEqual(len(bad_cases), 8)
        self.assertEqual(optimization["recommendation"]["candidate"], "B")
        self.assertTrue(optimization["recommendation"]["full_regression_passed"])

    def test_readiness_is_mock_in_the_test_environment_and_never_leaks_a_key(self):
        response = self.client.get("/api/readiness")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["mode"], "mock")
        self.assertNotIn("api_key", response.json())

    def test_experiment_starts_as_a_replay_run(self):
        response = self.client.post("/api/experiments/run")

        self.assertEqual(response.status_code, 201)
        run = response.json()
        self.assertEqual(run["status"], "queued")
        self.assertEqual(run["candidates"][0]["completed_cases"], 0)
        self.assertEqual(self.client.get(f"/api/experiments/{run['id']}").status_code, 200)

    def test_candidate_b_can_be_activated_for_demo(self):
        response = self.client.post("/api/versions/v1.2/activate")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "Demo Active")

    def test_preview_compares_the_known_bad_case(self):
        response = self.client.post("/api/preview", json={"question": "我工位空调坏了咋整？"})

        self.assertEqual(response.status_code, 200)
        preview = response.json()
        self.assertIn("暂时无法确认", preview["baseline"]["answer"])
        self.assertIn("30 分钟", preview["candidate_b"]["answer"])
        self.assertEqual(preview["mode"], "mock")
        self.assertIn("fallback_reason", preview)

    def test_live_evaluation_rejects_more_than_forty_cases(self):
        response = self.client.post("/api/evaluations/live", json={"limit": 41})

        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
