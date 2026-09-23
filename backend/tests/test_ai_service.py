import unittest
from unittest.mock import Mock

from app.ai_service import AiService
from app.policy import DEFAULT_PIPELINE_CONFIG


class LiveProvider:
    class Settings:
        configured = True
        model = "test-model"

    settings = Settings()

    def complete_with_metrics(self, *_args, **_kwargs):
        return {"content": "基于证据的回答", "ttft_ms": 25, "input_tokens": 10, "output_tokens": 5}


class AiServiceTests(unittest.TestCase):
    def test_answer_runs_frozen_pipeline_and_returns_provider_metrics(self):
        retriever = Mock()
        retriever.retrieve.return_value = [{"chunk_id": "C1", "content": "真实证据", "document": "manual.pdf", "page_start": 1, "page_end": 1, "score": .9}]
        service = AiService(Mock(), Mock(), LiveProvider(), False)
        service.retriever = retriever

        result = service.answer("如何操作", DEFAULT_PIPELINE_CONFIG)

        self.assertEqual(result["answer"], "基于证据的回答")
        self.assertEqual(result["ttft_ms"], 25)
        self.assertEqual(result["input_tokens"], 10)
        self.assertEqual(result["output_tokens"], 5)
        self.assertEqual(retriever.retrieve.call_args.args[1]["candidate_k"], 12)


if __name__ == "__main__":
    unittest.main()
