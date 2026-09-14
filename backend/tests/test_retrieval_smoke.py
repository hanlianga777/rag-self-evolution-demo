import json
import tempfile
import unittest
from pathlib import Path

from app.retrieval_smoke_test import run_smoke_test


class FakeRetriever:
    def __init__(self):
        self.questions = []

    def search(self, question):
        self.questions.append(question)
        if "分别应该怎么充电" in question:
            products = ("B2 遥控器", "B2 电池与充电器")
            documents = ("宇树_B2遥控器使用说明_中文版.pdf", "宇树_B2电池与充电器使用说明_中文版.pdf")
        elif "MacBook" in question:
            products = ("B2 遥控器",) * 4
            documents = ("宇树_B2遥控器使用说明_中文版.pdf",) * 4
        else:
            products = ("B2 遥控器",) * 4
            documents = ("宇树_B2遥控器使用说明_中文版.pdf",) * 4
        return [
            {
                "document": documents[index % len(documents)],
                "product": products[index % len(products)],
                "section": "充电",
                "section_path": "使用 / 充电",
                "page_start": index + 1,
                "page_end": index + 1,
                "chunk_id": f"CHUNK-{index + 1:04d}",
                "score": 0.9 - index / 10,
                "content_preview": "遥控器低电量时连接充电器",
                "content": "遥控器低电量时连接充电器",
            }
            for index in range(4)
        ]


class RetrievalSmokeTest(unittest.TestCase):
    def test_runner_writes_ranked_observations_without_changing_retrieval(self):
        retriever = FakeRetriever()
        with tempfile.TemporaryDirectory() as directory:
            report = run_smoke_test(retriever, Path(directory))
            payload = json.loads((Path(directory) / "retrieval_smoke_test.json").read_text(encoding="utf-8"))
            markdown = (Path(directory) / "retrieval_smoke_test.md").read_text(encoding="utf-8")

        self.assertEqual(len(retriever.questions), 12)
        self.assertEqual(report, payload)
        self.assertEqual(payload["summary"]["total_tests"], 12)
        remote = next(item for item in payload["results"] if item["test_id"] == "S-003")
        self.assertEqual(remote["evidence_hit_at_4"], "Yes")
        self.assertEqual(remote["top_k"][0]["rank"], 1)
        self.assertEqual(remote["top_k"][0]["product"], "B2 遥控器")
        multi = next(item for item in payload["results"] if item["test_id"] == "S-011")
        self.assertTrue(multi["document_hit_at_4"])
        self.assertFalse(multi["cross_product_contamination"])
        outside = next(item for item in payload["results"] if item["test_id"] == "S-012")
        self.assertEqual(outside["document_hit_at_1"], "Observation")
        self.assertIn("Total Tests：12", markdown)
        self.assertNotIn("Overall RAG Score", markdown)


if __name__ == "__main__":
    unittest.main()
