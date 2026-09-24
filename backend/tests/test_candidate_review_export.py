import csv
import io
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.governance import GovernanceStore


def candidates():
    return [
        {
            "test_category": category,
            "coverage_slot": f"Q{number:02d}",
            "question": f"测试问题 {number}",
            "reference_answer": None if category == "negative" else "有依据的答案",
            "expected_behavior": "insufficient_evidence" if category == "negative" else None,
            "evidence": [] if category == "negative" else [{"source_chunk_ids": ["C1"], "evidence_key_points": ["必须先确认状态"]}],
        }
        for number, category in enumerate(["positive"] * 8 + ["ablation"] * 4 + ["negative"] * 8, 1)
    ]


class CandidateReviewExportTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.store = GovernanceStore(Path(directory.name) / "demo.db")
        old_store, old_corpus = main.store, main.corpus
        main.store = self.store
        main.corpus = type("Corpus", (), {"chunks": lambda _self: [{"chunk_id": "C1", "document_id": "DOC-001", "section_path": "操作 / 首次使用", "page_start": 3, "page_end": 4, "chunk_text": "必须先确认状态"}]})()
        self.addCleanup(setattr, main, "store", old_store)
        self.addCleanup(setattr, main, "corpus", old_corpus)
        self.client = TestClient(main.app)
        self.rows = self.store.save_mini_golden_candidates(candidates(), "test-model")
        self.run_id = self.rows[0]["raw"]["generation_run_id"]

    def passed_probe(self, question_id):
        return self.store.record_probe_result(question_id, {"question_quality": 30, "golden_answer_quality": 30, "evidence_support": 40, "reason": "证据命中", "probe_details": {"classification": "EVIDENCE_VALID", "vector": {"top_k": [{"chunk_id": "C1", "score": .9}]}}})

    def test_json_export_contains_only_run_questions_and_full_histories(self):
        first = self.rows[0]["id"]
        self.passed_probe(first)
        self.passed_probe(first)
        self.store.record_qc(first, {"score": 72, "priority": "P1", "reason": "待改写"}, "failed")
        self.store.record_qc(first, {"score": 88, "priority": "P2", "reason": "已复核"}, "passed")
        self.store.review_question(first, "approved", "reviewer")

        response = self.client.get(f"/api/governance/generation-runs/{self.run_id}/export?format=json")

        self.assertEqual(response.status_code, 200)
        self.assertIn(f"golden_candidate_{self.run_id}.json", response.headers["content-disposition"])
        questions = response.json()["questions"]
        self.assertEqual(len(questions), 20)
        self.assertEqual([item["slot"] for item in questions], [f"Q{number:02d}" for number in range(1, 21)])
        self.assertTrue(all(item["legacy_question_type"] == "v1_mini" for item in questions))
        self.assertEqual(questions[0]["evidence_details"][0]["chunks"][0]["chunk_text"], "必须先确认状态")
        self.assertEqual(len(questions[0]["probe_history"]), 2)
        self.assertEqual(len(questions[0]["qc_history"]), 2)
        self.assertEqual(questions[0]["qc"]["score"], 88)
        self.assertEqual(len(questions[0]["review_history"]), 1)
        self.assertEqual(questions[-1]["evidence_details"], [])

    def test_markdown_and_csv_export_all_twenty_without_legacy(self):
        markdown = self.client.get(f"/api/governance/generation-runs/{self.run_id}/export?format=markdown")
        csv_response = self.client.get(f"/api/governance/generation-runs/{self.run_id}/export?format=csv")

        self.assertEqual(markdown.status_code, 200)
        self.assertEqual(csv_response.status_code, 200)
        self.assertIn(f"golden_candidate_{self.run_id}.md", markdown.headers["content-disposition"])
        self.assertIn(f"golden_candidate_{self.run_id}.csv", csv_response.headers["content-disposition"])
        self.assertEqual(sum(line.startswith("## Q") for line in markdown.text.splitlines()), 20)
        self.assertIn("必须先确认状态", markdown.text)
        self.assertNotIn("GGC-001", markdown.text)
        rows = list(csv.DictReader(io.StringIO(csv_response.content.decode("utf-8-sig"))))
        self.assertEqual(len(rows), 20)
        self.assertEqual(rows[0]["id"], self.rows[0]["id"])
        self.assertEqual(rows[-1]["id"], self.rows[-1]["id"])

    def test_export_rejects_unknown_and_incomplete_runs(self):
        self.assertEqual(self.client.get("/api/governance/generation-runs/unknown/export?format=json").status_code, 404)
        incomplete = self.store.start_generation_run("test-model")
        self.assertEqual(self.client.get(f"/api/governance/generation-runs/{incomplete}/export?format=json").status_code, 409)
        self.assertEqual(self.client.get(f"/api/governance/generation-runs/{self.run_id}/export?format=xml").status_code, 422)

    def test_missing_chunk_is_disclosed_and_csv_escapes_formula(self):
        self.store.update_question(self.rows[0]["id"], "=SUM(1,2)", "有依据的答案", self.rows[0]["evidence"], "reviewer")
        main.corpus = type("Corpus", (), {"chunks": lambda _self: []})()

        review = self.client.get(f"/api/governance/generation-runs/{self.run_id}/export?format=json").json()
        markdown = self.client.get(f"/api/governance/generation-runs/{self.run_id}/export?format=markdown").text
        csv_response = self.client.get(f"/api/governance/generation-runs/{self.run_id}/export?format=csv")

        self.assertEqual(review["questions"][0]["evidence_details"][0]["chunks"][0]["resolution"], "missing_current_index")
        self.assertIn("当前索引未匹配", markdown)
        rows = list(csv.DictReader(io.StringIO(csv_response.content.decode("utf-8-sig"))))
        self.assertEqual(rows[0]["question"], "'=SUM(1,2)")
        self.assertEqual(len(rows), 20)

    def test_batch_skips_approved_without_duplicate_events(self):
        ids = [row["id"] for row in self.rows]
        for question_id in ids:
            self.passed_probe(question_id)
            self.store.record_qc(question_id, {"score": 90, "priority": "P2", "reason": "通过"}, "passed")
        self.store.review_question(ids[0], "approved", "reviewer")

        result = self.store.review_generation_batch(ids, "reviewer", confirmed_manual_review=True)

        self.assertEqual(len(result["reviewed"]), 20)
        self.assertEqual(len(self.store.review_history(ids[0])), 1)
        self.assertTrue(all(self.store.question(question_id)["stage"] == "golden" for question_id in ids))

    def test_batch_never_overrides_last_manual_rejection_after_reprobe(self):
        ids = [row["id"] for row in self.rows]
        for question_id in ids:
            self.passed_probe(question_id)
            self.store.record_qc(question_id, {"score": 90, "priority": "P2", "reason": "通过"}, "passed")
        self.store.review_question(ids[0], "rejected", "reviewer")
        self.passed_probe(ids[0])  # Probe can reset the materialized status to pending.
        with self.assertRaisesRegex(ValueError, "人工"):
            self.store.review_generation_batch(ids, "reviewer", confirmed_manual_review=True)
        self.assertEqual(sum(self.store.question(question_id)["stage"] == "golden" for question_id in ids), 0)

    def test_batch_gate_failure_is_atomic(self):
        ids = [row["id"] for row in self.rows]
        for question_id in ids:
            self.passed_probe(question_id)
            self.store.record_qc(question_id, {"score": 90, "priority": "P2", "reason": "通过"}, "passed")
        self.store.record_qc(ids[1], {"score": 72, "priority": "P1", "reason": "未通过"}, "failed")

        with self.assertRaises(ValueError):
            self.store.review_generation_batch(ids, "reviewer", confirmed_manual_review=True)

        self.assertTrue(all(not self.store.review_history(question_id) for question_id in ids))
        self.assertTrue(all(self.store.question(question_id)["stage"] == "candidate" for question_id in ids))

    def test_batch_can_approve_recovered_qc_without_manual_rejection(self):
        ids = [row["id"] for row in self.rows]
        for question_id in ids:
            self.passed_probe(question_id)
            self.store.record_qc(question_id, {"score": 90, "priority": "P2", "reason": "通过"}, "passed")
        self.store.record_qc(ids[1], {"score": 72, "priority": "P1", "reason": "未通过"}, "failed")
        self.store.record_qc(ids[1], {"score": 90, "priority": "P2", "reason": "重新通过"}, "passed")
        self.assertEqual(self.store.question(ids[1])["review_status"], "needs_revision")

        self.store.review_generation_batch(ids, "reviewer", confirmed_manual_review=True)

        self.assertTrue(all(self.store.question(question_id)["stage"] == "golden" for question_id in ids))


if __name__ == "__main__":
    unittest.main()
