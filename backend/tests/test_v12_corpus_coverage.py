import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np

from app import corpus
from app.ai_service import AiService


class DynamicCorpusTests(unittest.TestCase):
    def test_discovers_new_pdf_and_keeps_persisted_metadata_optional(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "new source.pdf").write_bytes(b"fixture")
            with patch.object(corpus, "DOCUMENTS_DIR", root):
                documents = corpus.discover_documents()
                self.assertEqual(len(documents), 1)
                self.assertEqual(documents[0]["name"], "new source.pdf")
                self.assertTrue(documents[0]["id"])
                self.assertTrue(documents[0]["chunk_prefix"])
                self.assertEqual(corpus.current_manifest()["sources"], {documents[0]["id"]: corpus.source_fingerprint(documents[0])})

    def test_store_lists_persisted_arbitrary_documents(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "documents.json").write_text('[{"id":"manual-Z","name":"manual.pdf","chunks":1,"status":"Indexed"}]', encoding="utf-8")
            (root / "chunks.json").write_text('[{"document_id":"manual-Z","chunk_id":"c-9","chunk_text":"fact"}]', encoding="utf-8")
            with patch.object(corpus, "DOCUMENTS_DIR", root):
                store = corpus.CorpusStore(root)
                self.assertEqual(store.documents()[0]["id"], "manual-Z")
                self.assertEqual(store.detail("manual-Z")["chunks"][0]["chunk_text"], "fact")


class EmbeddingCoverageTests(unittest.TestCase):
    @staticmethod
    def _chunks(count):
        return [{"document_id": f"manual-{i}", "chunk_id": f"segment-{i}", "chunk_text": f"事实 {i}"} for i in range(count)]

    def test_quota_and_arbitrary_ids_across_corpus_sizes(self):
        for count in (1, 2, 4, 6, 10):
            with self.subTest(count=count):
                chunks = self._chunks(count)
                vectors = np.asarray([[1., 0.] if i % 2 else [0., 1.] for i in range(count)], dtype="float32")
                plan = AiService._mini_coverage_plan(chunks, vectors)
                self.assertEqual([sum(slot["test_category"] == group for slot in plan) for group in ("positive", "ablation", "negative")], [8, 4, 8])
                self.assertTrue({slot["document_id"] for slot in plan}.issubset({chunk["document_id"] for chunk in chunks}))
                self.assertEqual(len({slot["evidence_chunk_ids"][0] for slot in plan[:8]}), min(count, 8))
                self.assertTrue(all("topic_cluster" in slot for slot in plan))

    def test_cluster_selection_uses_vectors_instead_of_document_order(self):
        chunks = self._chunks(10)
        vectors = np.asarray([[1., 0.]] * 5 + [[0., 1.]] * 5, dtype="float32")
        plan = AiService._mini_coverage_plan(chunks, vectors)
        selected = [slot["evidence_chunk_ids"][0] for slot in plan[:8]]
        self.assertTrue(any(value in selected for value in ("segment-0", "segment-1", "segment-2", "segment-3", "segment-4")))
        self.assertTrue(any(value in selected for value in ("segment-5", "segment-6", "segment-7", "segment-8", "segment-9")))

    def test_single_chunk_does_not_force_cross_chunk_slot(self):
        plan = AiService._mini_coverage_plan(self._chunks(1), np.asarray([[1., 0.]], dtype="float32"))
        self.assertFalse(any(slot.get("ablation_attribute") == "cross_chunk" for slot in plan))
        self.assertTrue(all(slot.get("source_positive_slot") is None for slot in plan))

    def test_structured_slots_require_explicit_source_facts(self):
        chunks = self._chunks(2)
        chunks[0]["chunk_text"] = "设备A：电压 24V\n设备A：容量 10Ah"
        chunks[1]["chunk_text"] = "普通说明文本，没有列出明确事实。"
        plan = AiService._mini_coverage_plan(chunks, np.asarray([[1., 0.], [0., 1.]], dtype="float32"))
        self.assertTrue(any(slot.get("structured_type") == "Aggregation" for slot in plan if slot["sources"][0]["chunk_id"] == "segment-0"))
        self.assertTrue(all(slot.get("structured_type") is None for slot in plan if slot["sources"][0]["chunk_id"] == "segment-1"))

    def test_rejects_misaligned_or_missing_embeddings(self):
        with self.assertRaisesRegex(Exception, "Embedding"):
            AiService._mini_coverage_plan(self._chunks(2), np.asarray([[1., 0.]], dtype="float32"))

    def test_bridge_uses_two_chunks_only_with_shared_explicit_entity(self):
        chunks = self._chunks(2)
        chunks[0]["chunk_text"] = "设备A 电压：24V"
        chunks[1]["chunk_text"] = "设备A 容量：10Ah"
        plan = AiService._mini_coverage_plan(chunks, np.asarray([[1., 0.], [0., 1.]], dtype="float32"))
        bridges = [slot for slot in plan if slot.get("structured_type") == "Bridge"]
        self.assertTrue(bridges)
        self.assertTrue(all(len(slot["evidence_chunk_ids"]) == 2 for slot in bridges))

    def test_revision_material_accepts_missing_optional_product_within_document(self):
        chunk = {"document_id": "manual-Z", "chunk_id": "segment-9", "chunk_text": "确定的操作事实"}
        store = Mock()
        store.generation_run.return_value = {"artifacts": {"coverage_plan": [{"slot": "Q09", "document_id": "manual-Z"}]}}
        store.questions.return_value = []
        service = AiService(store, Mock(), Mock(), False)
        run = {"generation_run_id": "run-1", "question_ids": ["item-9"], "before": {"item-9": {"test_category": "ablation", "raw": {"coverage_slot": "Q09"}, "evidence": [{"source_chunk_ids": ["segment-9"]}]}}, "changes": {}, "reason": "改善问法"}
        selected = service.select_revision_material(run, [chunk])
        self.assertEqual(selected["item-9"]["chunk_ids"], ["segment-9"])

    def test_revision_material_accepts_same_document_chunk_without_product(self):
        chunks = [{"document_id": "manual-Z", "chunk_id": "segment-1", "product": "robot-A", "chunk_text": "原始事实"}, {"document_id": "manual-Z", "chunk_id": "segment-2", "chunk_text": "后续事实"}]
        store = Mock()
        store.generation_run.return_value = {"artifacts": {"coverage_plan": []}}
        store.questions.return_value = []
        service = AiService(store, Mock(), Mock(), False)
        run = {"generation_run_id": "run-1", "question_ids": ["item-1"], "before": {"item-1": {"test_category": "positive", "raw": {"coverage_slot": "Q01"}, "evidence": [{"source_chunk_ids": ["segment-1"]}]}}, "changes": {"item-1": {"source_chunk_ids": ["segment-2"]}}, "reason": "人工换材"}
        self.assertEqual(service.select_revision_material(run, chunks)["item-1"]["chunk_ids"], ["segment-2"])


if __name__ == "__main__":
    unittest.main()
