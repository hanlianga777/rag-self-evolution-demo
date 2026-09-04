import json
import unittest
from unittest.mock import patch

from app.config import Settings
from app.providers import DeepSeekProvider, ProviderUnavailable
from app.retrieval import LocalRetriever
from app.seed import DOCUMENTS


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
    def test_local_retriever_ranks_air_conditioner_repair_evidence_first(self):
        evidence = LocalRetriever(DOCUMENTS).search("我工位空调坏了咋整？")

        self.assertEqual(evidence[0]["document"], "空调设备报修流程.pdf")
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


if __name__ == "__main__":
    unittest.main()
