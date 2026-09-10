import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from app.config import Settings
from app.ai_service import AiService
from app.providers import DeepSeekProvider, ProviderUnavailable
from app.retrieval import LocalRetriever
from app.seed import DOCUMENTS, SeedStore
from app.services import DemoService


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return json.dumps(self.payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class LiveServiceTests(unittest.TestCase):
    def setUp(self):
        self.provider = DeepSeekProvider(Settings("test-key", "https://example.invalid", "test-model"))

    def make_service(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        store = SeedStore(Path(directory.name) / "demo.db")
        return AiService(store, self.provider, False, DemoService(store).compare_preview)

    def test_local_retriever_ranks_b2_remote_control_evidence_first(self):
        evidence = LocalRetriever(DOCUMENTS).search("B2遥控器低电量怎么充电？")

        self.assertEqual(evidence[0]["document"], "宇树_B2遥控器使用说明_中文版.pdf")
        self.assertGreater(evidence[0]["score"], 0)

    def test_provider_without_key_never_sends_a_request(self):
        provider = DeepSeekProvider(Settings(api_key="", base_url="https://api.deepseek.com", model="deepseek-v4-flash"))

        with patch("app.providers.urllib.request.urlopen") as request:
            with self.assertRaises(ProviderUnavailable):
                provider.complete("system", "question")

        request.assert_not_called()

    def test_provider_parses_json_judge_response(self):
        provider = DeepSeekProvider(Settings(api_key="test-key", base_url="https://api.deepseek.com", model="deepseek-v4-flash"))
        response = FakeResponse({"choices": [{"message": {"content": '{"score": 88, "rationale": "回答有证据支撑"}'}}]})

        with patch("app.providers.urllib.request.urlopen", return_value=response):
            result = provider.judge("问题", "预期回答", "实际回答")

        self.assertEqual(result, {"score": 88.0, "rationale": "回答有证据支撑"})

    def test_provider_rejects_non_string_and_blank_answers(self):
        for content in (True, 7, ["answer"], {"answer": "text"}, None, "", " \n\t "):
            with self.subTest(content=content), patch("app.providers.urllib.request.urlopen", return_value=FakeResponse({"choices": [{"message": {"content": content}}]})):
                with self.assertRaises(ProviderUnavailable):
                    self.provider.complete("system", "question")

    def test_provider_rejects_non_numeric_non_finite_and_out_of_range_scores(self):
        for score in (True, False, "88", None, [], {}, -1, 101, float("nan"), float("inf"), float("-inf")):
            content = json.dumps({"score": score, "rationale": "reason"})
            with self.subTest(score=score), patch("app.providers.urllib.request.urlopen", return_value=FakeResponse({"choices": [{"message": {"content": content}}]})):
                with self.assertRaises(ProviderUnavailable):
                    self.provider.judge("question", "expected", "answer")
        for score in (0, 88.5, 100):
            content = json.dumps({"score": score, "rationale": "reason"})
            with patch("app.providers.urllib.request.urlopen", return_value=FakeResponse({"choices": [{"message": {"content": content}}]})):
                self.assertEqual(self.provider.judge("question", "expected", "answer")["score"], score)

    def test_evaluation_never_judges_fallback_or_counts_it_as_live_success(self):
        service = self.make_service()
        answer = FakeResponse({"choices": [{"message": {"content": "真实回答"}}]})
        judge = FakeResponse({"choices": [{"message": {"content": '{"score": 90, "rationale": "reason"}'}}]})
        answer_requests = 0

        def respond(request, **kwargs):
            nonlocal answer_requests
            if "response_format" in json.loads(request.data):
                return judge
            answer_requests += 1
            if answer_requests == 1:
                raise urllib.error.URLError("offline")
            return answer

        with patch("app.providers.urllib.request.urlopen", side_effect=respond) as request:
            result = service.evaluate(2)
        self.assertEqual(result["completed"], 1)
        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["average_score"], 90)
        self.assertEqual(request.call_count, 3)

    def test_failed_answers_have_no_live_score_and_no_judge_requests(self):
        service = self.make_service()
        with patch("app.providers.urllib.request.urlopen", side_effect=urllib.error.URLError("offline")) as request:
            result = service.evaluate(2)
        self.assertEqual(result["completed"], 0)
        self.assertEqual(result["failed"], 2)
        self.assertIsNone(result["average_score"])
        self.assertEqual(request.call_count, 2)

    def test_readiness_tracks_unverified_passed_and_failed_probe_states(self):
        service = self.make_service()
        self.assertEqual(service.readiness()["status"], "Configured (Unverified)")
        response = FakeResponse({"choices": [{"message": {"content": "连接成功"}}]})
        with patch("app.providers.urllib.request.urlopen", return_value=response):
            self.assertEqual(service.probe()["status"], "Ready")
        with patch("app.providers.urllib.request.urlopen", side_effect=urllib.error.URLError("offline")):
            self.assertEqual(service.probe()["status"], "Unavailable")
        self.assertEqual(service.readiness()["status"], "Unavailable")
        with patch("app.providers.urllib.request.urlopen", return_value=response):
            self.assertEqual(service.probe()["status"], "Ready")


if __name__ == "__main__":
    unittest.main()
