import unittest
from unittest.mock import Mock

import numpy as np

from app.corpus import EMBEDDING_MODEL, chunk_sections, tokenizer_token_count
from app.retrieval import VectorRetriever


class CorpusTests(unittest.TestCase):
    def test_chunk_sections_keeps_a_section_together_across_pages(self):
        chunks = chunk_sections(
            document={"id": "DOC-003", "name": "遥控器.pdf", "vendor": "宇树", "product": "B2 遥控器", "chunk_prefix": "B2-RC"},
            pages=[
                {"page": 1, "text": "甲乙丙丁丁丁", "section_path": "安全 / 充电"},
                {"page": 2, "text": "戊己庚辛壬癸", "section_path": "安全 / 充电"},
                {"page": 2, "text": "子丑寅卯", "section_path": "维护"},
            ],
            token_counter=len,
            target_tokens=13,
            overlap_tokens=2,
        )

        self.assertEqual(chunks[0]["page_start"], 1)
        self.assertEqual(chunks[0]["page_end"], 2)
        self.assertEqual(chunks[0]["section_path"], "安全 / 充电")
        self.assertEqual(chunks[-1]["section_path"], "维护")
        self.assertEqual(chunks[0]["vendor"], "宇树")
        self.assertEqual(chunks[0]["product"], "B2 遥控器")
        self.assertEqual(chunks[0]["section"], "充电")
        self.assertEqual(chunks[0]["chunk_text"], chunks[0]["text"])
        self.assertEqual(chunks[0]["embedding_status"], "Pending")

    def test_token_count_matches_the_bge_tokenizer(self):
        from transformers import AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained(EMBEDDING_MODEL, local_files_only=True)
        text = "B2 遥控器低电量时如何充电？"
        self.assertEqual(tokenizer_token_count(tokenizer, text), len(tokenizer.encode(text, add_special_tokens=False)))

    def test_chunk_sections_keeps_source_pages_and_stable_ids(self):
        chunks = chunk_sections(
            document={"id": "DOC-003", "name": "宇树_B2遥控器使用说明_中文版.pdf", "vendor": "宇树", "product": "B2 遥控器", "category": "工业巡检机器人", "chunk_prefix": "B2-RC"},
            pages=[{"page": 8, "text": "低电量时应将遥控器连接充电器。建议使用 5V/2A USB 充电器。" * 30, "section_path": "充电"}],
            token_counter=lambda text: len(text),
            target_tokens=120,
            overlap_tokens=20,
        )

        self.assertGreater(len(chunks), 1)
        self.assertEqual(chunks[0]["chunk_id"], "B2-RC-CHUNK-0001")
        self.assertEqual(chunks[0]["page_start"], 8)
        self.assertEqual(chunks[0]["page_end"], 8)
        self.assertEqual(chunks[0]["section_path"], "充电")
        self.assertNotIn("samples", chunks[0])
        self.assertTrue(all(chunk["token_count"] <= 120 for chunk in chunks))

    def test_vector_retriever_uses_normalized_bge_vector_and_fixed_top_k(self):
        chunks = [{"document_id": "DOC-003", "document_name": "遥控器.pdf", "product": "B2 遥控器", "chunk_id": f"B2-REMOTE-CHUNK-{index:04d}", "section": "充电", "section_path": "充电", "page_start": index, "page_end": index, "text": "真实 OCR 文本"} for index in range(1, 6)]
        corpus = Mock()
        corpus.chunks.return_value = chunks
        retriever = VectorRetriever(corpus)
        retriever._load = Mock(return_value=True)
        retriever._model = Mock()
        retriever._model.encode.return_value = np.ones((1, 512), dtype="float32")
        retriever._index = Mock()
        retriever._index.search.return_value = (np.array([[.95, .12, .02, -.80]], dtype="float32"), np.array([[0, 1, 2, 3]]))

        evidence = retriever.search("MacBook 怎么开机？")

        self.assertEqual(retriever._model.encode.call_args.kwargs["normalize_embeddings"], True)
        self.assertEqual(retriever._index.search.call_args.args[1], 4)
        self.assertEqual(retriever._model.encode.call_args.args[0], ["MacBook 怎么开机？"])
        self.assertEqual(len(evidence), 4)
        self.assertEqual(evidence[0]["chunk_id"], "B2-REMOTE-CHUNK-0001")
        self.assertEqual(evidence[0]["product"], "B2 遥控器")
        self.assertEqual(evidence[0]["section"], "充电")

    def test_pipeline_normalizes_vector_and_bm25_before_hybrid_then_filters_after_rerank(self):
        chunks = [
            {"document_id": "DOC-1", "document_name": "one.pdf", "product": "产品A", "vendor": "厂商", "chunk_id": "A", "section": "维护", "section_path": "维护", "page_start": 1, "page_end": 1, "text": "机器人 充电 操作"},
            {"document_id": "DOC-2", "document_name": "two.pdf", "product": "产品B", "vendor": "厂商", "chunk_id": "B", "section": "维护", "section_path": "维护", "page_start": 1, "page_end": 1, "text": "机器人 充电 安全"},
        ]
        corpus = Mock(); corpus.chunks.return_value = chunks
        retriever = VectorRetriever(corpus)
        retriever.vector_candidates = Mock(return_value=[
            {"chunk_id": "A", "score": 0.9, **chunks[0]}, {"chunk_id": "B", "score": 0.2, **chunks[1]},
        ])

        evidence = retriever.retrieve("机器人充电", {"candidate_k": 12, "top_k": 1, "min_score": 0.6, "hybrid_search": True, "hybrid_alpha": 0.5, "rerank": True, "metadata_filter": "OFF"})

        self.assertEqual(len(evidence), 1)
        self.assertIn("vector_normalized", evidence[0])
        self.assertIn("bm25_normalized", evidence[0])
        self.assertIn("rerank_score", evidence[0])


if __name__ == "__main__":
    unittest.main()
