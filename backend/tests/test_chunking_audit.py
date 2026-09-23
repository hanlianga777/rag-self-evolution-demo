import unittest

from app.chunking_audit import adaptive_chunks, evidence_matches


class ChunkingAuditTests(unittest.TestCase):
    def test_merges_tiny_tail_only_with_same_section(self):
        doc = {"id": "DOC-1", "name": "x.pdf", "chunk_prefix": "X"}
        pages = [
            {"page": 1, "section_path": "操作", "text": "A" * 100 + "\n" + "B" * 100 + "\n" + "C" * 20},
            {"page": 2, "section_path": "安全", "text": "D" * 20},
        ]
        chunks = adaptive_chunks(doc, pages, len, target=200, soft_max=230, tiny=30, overlap=0)
        self.assertEqual(len(chunks), 2)
        self.assertIn("C" * 20, chunks[0]["chunk_text"])
        self.assertNotIn("D" * 20, chunks[0]["chunk_text"])
        self.assertEqual(chunks[1]["page_start"], 2)

    def test_evidence_requires_document_page_and_literal_source_text(self):
        evidence = {"document_id": "DOC-1", "page_start": 3, "page_end": 3, "key_points": ["必须先充满电。"]}
        hit = {"document_id": "DOC-1", "page_start": 3, "page_end": 3, "content": "首次使用，必须先充满电。"}
        self.assertTrue(evidence_matches(evidence, hit))
        self.assertFalse(evidence_matches(evidence, {**hit, "page_start": 4, "page_end": 4}))
        self.assertFalse(evidence_matches(evidence, {**hit, "content": "充电状态见指示灯。"}))


if __name__ == "__main__":
    unittest.main()
