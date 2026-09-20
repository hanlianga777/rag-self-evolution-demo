import json
import unittest
from unittest.mock import patch

from app.config import Settings
from app.providers import DeepSeekProvider, ProviderUnavailable


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return json.dumps(self.payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.provider = DeepSeekProvider(Settings("test-key", "https://example.invalid", "test-model"))

    def test_judge_requires_structured_scores_for_real_evaluation(self):
        content = '{"correctness":4,"completeness":1,"faithfulness":1,"behavior_pass":true,"reason":"证据充分","missing_points":[],"unsupported_claims":[]}'
        with patch("app.providers.urllib.request.urlopen", return_value=FakeResponse({"choices": [{"message": {"content": content}}]})):
            result = self.provider.judge("问题", "预期", "回答")

        self.assertEqual(result["correctness"], 4)
        self.assertTrue(result["behavior_pass"])

    def test_judge_rejects_legacy_score_only_json(self):
        with patch("app.providers.urllib.request.urlopen", return_value=FakeResponse({"choices": [{"message": {"content": '{"score": 88}'}}]})):
            with self.assertRaises(ProviderUnavailable):
                self.provider.judge("问题", "预期", "回答")

    def test_unconfigured_provider_never_sends_a_request(self):
        provider = DeepSeekProvider(Settings("", "https://example.invalid", "test-model"))
        with patch("app.providers.urllib.request.urlopen") as request:
            with self.assertRaises(ProviderUnavailable):
                provider.complete("system", "question")
        request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
