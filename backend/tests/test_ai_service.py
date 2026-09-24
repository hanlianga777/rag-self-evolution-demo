import json
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


class GoldenProvider(LiveProvider):
    def __init__(self):
        self.calls = 0

    def complete(self, prompt, *_args, **_kwargs):
        self.calls += 1
        if "负向问题" in prompt:
            return f'{{"question":"知识库外的安全边界问题 {self.calls}","expected_behavior":"safe_rejection"}}'
        if "alias_entity" in prompt:
            return f'{{"question":"请说明别名操作要求 {self.calls}","reference_answer":"请按照原厂说明书执行操作。","original_entity":"产品","alias_expression":"这台设备"}}'
        return f'{{"question":"请说明操作要求 {self.calls}","reference_answer":"请按照原厂说明书执行操作。"}}'


class RepairingGoldenProvider(GoldenProvider):
    def __init__(self, failures=1):
        super().__init__()
        self.failures = failures

    def complete(self, prompt, payload, **kwargs):
        slot = json.loads(payload)["coverage_slot"]
        if slot == "Q01" and self.failures:
            self.failures -= 1
            return "{}"
        return super().complete(prompt, payload, **kwargs)


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

    def test_mini_generation_plans_coverage_before_creating_all_three_groups(self):
        chunks = []
        for document in range(1, 5):
            for chunk in range(1, 4):
                chunks.append({"document_id": f"DOC-{document}", "document_name": f"文档 {document}", "product": f"产品 {document}", "section": f"章节 {chunk}", "section_path": f"文档 {document} / 章节 {chunk}", "page_start": chunk, "chunk_id": f"D{document}-C{chunk}", "chunk_text": "请按照原厂说明书执行操作。"})
        service = AiService(Mock(), Mock(), GoldenProvider(), False)

        generated = service.generate_mini_golden(chunks)

        self.assertEqual(len(generated["candidates"]), 20)
        self.assertEqual({category: sum(candidate["test_category"] == category for candidate in generated["candidates"]) for category in ("positive", "ablation", "negative")}, {"positive": 8, "ablation": 4, "negative": 8})
        self.assertEqual(generated["profile"]["expected_count"], 20)
        self.assertEqual({item["document_id"] for item in generated["coverage_plan"] if item["test_category"] != "negative"}, {"DOC-1", "DOC-2", "DOC-3", "DOC-4"})
        self.assertTrue(any(item.get("ablation_attribute") == "cross_chunk" and len(item["evidence"][0]["source_chunk_ids"]) == 2 for item in generated["candidates"]))

    def test_mini_generation_repairs_only_the_failed_slot_and_keeps_audit(self):
        generated = AiService(Mock(), Mock(), RepairingGoldenProvider(), False).generate_mini_golden(self._chunks())

        self.assertEqual(generated["status"], "candidate_generated")
        self.assertEqual(len(generated["candidates"]), 20)
        self.assertEqual(len(generated["slot_audit"]["Q01"]), 2)
        self.assertEqual(generated["slot_audit"]["Q01"][0]["validation_error"], "invalid question/category")

    def test_mini_generation_records_failed_run_after_two_repairs(self):
        generated = AiService(Mock(), Mock(), RepairingGoldenProvider(failures=3), False).generate_mini_golden(self._chunks())

        self.assertEqual(generated["status"], "failed")
        self.assertEqual(generated["failed_slots"], ["Q01"])
        self.assertEqual(len(generated["slot_audit"]["Q01"]), 3)

    def test_coverage_prefers_representative_body_chunks_when_available(self):
        chunks = self._chunks()
        chunks[0].update({"section_path": "封面", "chunk_text": "短"})
        chunks[1].update({"section_path": "正文 / 操作", "chunk_text": "有效正文" * 60})

        plan = AiService._mini_coverage_plan(chunks)

        self.assertNotIn("D1-C1", [item["evidence_chunk_ids"][0] for item in plan if item["document_id"] == "DOC-1" and item["evidence_chunk_ids"]])
        self.assertTrue(all(item.get("selected_reason") for item in plan))

    def test_hard_validation_rejects_alias_ablation_without_recorded_alias(self):
        candidate = {"coverage_slot": "Q09", "test_category": "ablation", "question": "别名问题", "reference_answer": "答案", "evidence": [{"source_chunk_ids": ["D1-C1"]}], "ablation_attribute": "alias_entity"}

        validation = AiService._hard_validate([candidate], self._chunks())

        self.assertTrue(any("missing alias metadata" in error for error in validation["rejected"]))

    @staticmethod
    def _chunks():
        chunks = []
        for document in range(1, 5):
            for chunk in range(1, 4):
                chunks.append({"document_id": f"DOC-{document}", "document_name": f"文档 {document}", "product": f"产品 {document}", "section": f"章节 {chunk}", "section_path": f"文档 {document} / 章节 {chunk}", "page_start": chunk, "chunk_id": f"D{document}-C{chunk}", "chunk_text": "请按照原厂说明书执行操作。"})
        return chunks


if __name__ == "__main__":
    unittest.main()
