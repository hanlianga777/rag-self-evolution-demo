import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.ai_service import AiService
from app.config import Settings
from app.providers import DeepSeekProvider
from app.seed import SeedStore
from app.services import DemoService

with tempfile.TemporaryDirectory() as startup_directory:
    with patch("app.config.load_settings", return_value=Settings("", "https://example.invalid", "test-model")), patch("app.seed.SeedStore", return_value=SeedStore(Path(startup_directory) / "demo.db")):
        from app import main

app = main.app


class DemoApiTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.store = SeedStore(Path(directory.name) / "demo.db")
        service = DemoService(self.store)
        ai_service = AiService(self.store, DeepSeekProvider(Settings("", "https://example.invalid", "test-model")), True, service.compare_preview)
        for name, value in (("store", self.store), ("service", service), ("ai_service", ai_service)):
            patcher = patch.object(main, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.client = TestClient(app, raise_server_exceptions=False)

    def test_seeded_overview_matches_baseline_story(self):
        response = self.client.get("/api/overview")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["kpis"]["overall_score"], 72.4)
        self.assertEqual(payload["kpis"]["bad_cases"], "4 / 8")
        self.assertEqual(payload["recommended_candidate"], "Candidate B")

    def test_evaluation_has_eight_bad_cases_and_recommends_b(self):
        evaluation = self.client.get("/api/evaluation").json()
        bad_cases = self.client.get("/api/bad-cases").json()
        optimization = self.client.get("/api/optimization").json()

        self.assertEqual(evaluation["questions"], 8)
        self.assertEqual(len(bad_cases), 4)
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
        response = self.client.post("/api/preview", json={"question": "B2遥控器低电量时如何充电？"})

        self.assertEqual(response.status_code, 200)
        preview = response.json()
        self.assertIn("未检索到", preview["baseline"]["answer"])
        self.assertIn("5V/2A", preview["candidate_b"]["answer"])
        self.assertEqual(preview["mode"], "mock")
        self.assertIn("fallback_reason", preview)

    def test_live_evaluation_rejects_more_than_forty_cases(self):
        response = self.client.post("/api/evaluations/live", json={"limit": 41})

        self.assertEqual(response.status_code, 422)

    def test_preview_requires_a_bounded_strict_string(self):
        for question in (None, 1, True, [], {}, "", "   ", "问" * 1001):
            with self.subTest(question_type=type(question).__name__, length=len(question) if isinstance(question, str) else None):
                response = self.client.post("/api/preview", json={"question": question})
                self.assertEqual(response.status_code, 422)
        for question in ("问", "问" * 1000):
            self.assertEqual(self.client.post("/api/preview", json={"question": question}).status_code, 200)

    def test_evaluation_requires_a_bounded_strict_integer(self):
        for limit in (None, True, False, "1", 1.0, [], {}, 0, -1, 41):
            with self.subTest(limit=limit):
                response = self.client.post("/api/evaluations/live", json={"limit": limit})
                self.assertEqual(response.status_code, 422)
        for limit in (1, 40):
            self.assertEqual(self.client.post("/api/evaluations/live", json={"limit": limit}).status_code, 200)
        self.assertEqual(self.client.post("/api/evaluations/live", json={}).status_code, 200)

    def test_untrusted_origins_cannot_trigger_paid_post_work(self):
        routes = (("/api/preview", {"question": "问"}, "preview"), ("/api/evaluations/live", {"limit": 1}, "evaluate"), ("/api/ai-readiness/probe", {}, "probe"))
        for route, payload, method in routes:
            for origin in ("https://evil.example", "null", "http://localhost:5174.evil.example", "http://localhost:3000"):
                with self.subTest(route=route, origin=origin), patch.object(main.ai_service, method, return_value={}) as operation:
                    response = self.client.post(route, json=payload, headers={"Origin": origin})
                    self.assertEqual(response.status_code, 403)
                    operation.assert_not_called()
            for origin in (None, "http://localhost:5174", "http://127.0.0.1:5174"):
                headers = {} if origin is None else {"Origin": origin}
                self.assertEqual(self.client.post(route, json=payload, headers=headers).status_code, 200)

    def test_demo_activation_is_consistent_and_survives_store_restart(self):
        self.client.post("/api/versions/v1.2/activate")
        for store in (self.store, SeedStore(self.store.database_path)):
            with patch.object(main, "store", store):
                versions = self.client.get("/api/versions").json()
                self.assertEqual([v["id"] for v in versions if v["status"] in ("Active", "Demo Active")], ["v1.2"])
                self.assertEqual(next(v["status"] for v in versions if v["id"] == "v1.2"), "Demo Active")
                workspace = self.client.get("/api/workspace").json()
                self.assertEqual(workspace["active_version"], "v1.2")
                self.assertEqual(workspace["environment"], "Robot PDF Demo · v1.2")
        restarted = DemoService(SeedStore(self.store.database_path))
        self.assertEqual(restarted.activate_version("v1.3")["status"], "Demo Active")
        self.assertEqual(self.store.get("workspace")["active_version"], "v1.3")
        self.assertIsNone(restarted.activate_version("nonexistent"))
        self.assertEqual(self.store.get("workspace")["active_version"], "v1.3")

    def test_workspace_document_count_matches_seed_documents(self):
        self.assertEqual(self.client.get("/api/workspace").json()["document_count"], len(self.client.get("/api/documents").json()))

    def test_documents_are_verified_robot_pdfs_with_local_targets(self):
        documents = self.client.get("/api/documents").json()

        self.assertEqual([document["name"] for document in documents], [
            "卡赫_KIRA_B_50完整操作说明_中文版.pdf",
            "宇树_B2四足机器人用户手册_中文版.pdf",
            "宇树_B2遥控器使用说明_中文版.pdf",
            "宇树_B2电池与充电器使用说明_中文版.pdf",
        ])
        for document in documents:
            response = self.client.get(document["pdf_url"])
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers["content-type"], "application/pdf")

    def test_existing_seed_database_refreshes_robot_seed_and_preserves_active_version(self):
        connection = sqlite3.connect(self.store.database_path)
        try:
            connection.execute("DELETE FROM demo_state WHERE key = 'demo_active_version'")
            connection.commit()
            migrated = SeedStore(self.store.database_path)
            self.assertEqual(migrated.get("workspace")["active_version"], "v1.0")
            self.assertEqual(migrated.get("workspace")["document_count"], 4)
            DemoService(migrated).activate_version("v1.2")
            self.assertEqual(connection.execute("SELECT value FROM demo_state WHERE key = 'demo_active_version'").fetchone()[0], "v1.2")
            seed = json.loads(connection.execute("SELECT value FROM demo_state WHERE key = 'seed'").fetchone()[0])
            self.assertEqual(seed["workspace"]["name"], "机器人智能问答评测与优化 Agent")
        finally:
            connection.close()

    def test_experiment_responses_always_identify_seeded_mock_replay(self):
        created = self.client.post("/api/experiments/run").json()
        for elapsed in (0, 2, 5, 7):
            main.service.runs[created["id"]]["started_at"] = 100
            with patch("app.services.time.monotonic", return_value=100 + elapsed):
                payload = self.client.get(f"/api/experiments/{created['id']}").json()
            for response in (created, payload):
                self.assertEqual(response.get("mode"), "mock")
                self.assertEqual(response.get("source"), "seeded_replay")


if __name__ == "__main__":
    unittest.main()
