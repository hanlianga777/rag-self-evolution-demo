import unittest
from unittest.mock import Mock

import numpy as np

from app.corpus import chunk_sections
from app.retrieval import VectorRetriever


class CorpusTests(unittest.TestCase):
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

    def test_vector_retriever_uses_normalized_bge_vector_and_fixed_top_k(self):
        chunks = [{"document_id": "DOC-003", "document_name": "遥控器.pdf", "chunk_id": f"B2-REMOTE-CHUNK-{index:04d}", "section_path": "充电", "page_start": index, "page_end": index, "text": "真实 OCR 文本"} for index in range(1, 6)]
        corpus = Mock()
        corpus.chunks.return_value = chunks
        retriever = VectorRetriever(corpus)
        retriever._load = Mock(return_value=True)
        retriever._model = Mock()
        retriever._model.encode.return_value = np.ones((1, 512), dtype="float32")
        retriever._index = Mock()
        retriever._index.search.return_value = (np.array([[.95, .90, .85, .80]], dtype="float32"), np.array([[0, 1, 2, 3]]))

        evidence = retriever.search("B2 遥控器充电")

        self.assertEqual(retriever._model.encode.call_args.kwargs["normalize_embeddings"], True)
        self.assertEqual(retriever._index.search.call_args.args[1], 4)
        self.assertEqual(retriever._model.encode.call_args.args[0], ["B2 遥控器充电"])
        self.assertEqual(len(evidence), 4)
        self.assertEqual(evidence[0]["chunk_id"], "B2-REMOTE-CHUNK-0001")


if __name__ == "__main__":
    unittest.main()
