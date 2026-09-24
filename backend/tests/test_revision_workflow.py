import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import main
from app.ai_service import AiService
from app.governance import GovernanceStore


def candidates():
    result = []
    for number in range(1, 21):
        category = "positive" if number <= 8 else "ablation" if number <= 12 else "negative"
        result.append({
            "coverage_slot": f"Q{number:02d}", "test_category": category,
            "question": f"原题 {number}",
            "reference_answer": None if category == "negative" else "正确操作",
            "expected_behavior": "safe_rejection" if number == 13 else "clarify" if number == 15 else "insufficient_evidence" if category == "negative" else None,
            "negative_subtype": "safe_rejection" if number == 13 else "clarify" if number == 15 else "insufficient_evidence" if category == "negative" else None,
            "ablation_attribute": "weak_keywords" if number == 9 else "colloquial" if category == "ablation" else None,
            "evidence": [] if category == "negative" else [{"source_chunk_ids": ["C1"], "evidence_key_points": ["正确操作"]}],
        })
    return result


class RevisionWorkflowTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.store = GovernanceStore(Path(directory.name) / "demo.db")
        self.rows = self.store.save_mini_golden_candidates(candidates(), "test-model")
        self.ids = [row["id"] for row in self.rows]
        self.chunks = [
            {"chunk_id": "C1", "document_id": "DOC-001", "chunk_text": "正确操作步骤", "section_path": "欧盟一致性声明"},
            {"chunk_id": "C2", "document_id": "DOC-001", "chunk_text": "启动前检查急停按钮，确认安全后开始清洁。", "section_path": "安全操作"},
        ]
        with self.store.connection() as connection:
            connection.execute("UPDATE golden_generation_runs SET status='completed' WHERE id=?", (self.rows[0]["raw"]["generation_run_id"],))
        for index, question_id in enumerate(self.ids):
            self.store.record_probe_result(question_id, {"question_quality": 30, "golden_answer_quality": 30, "evidence_support": 40})
            self.store.record_qc(question_id, {"score": 90, "priority": "P2", "reason": "通过"}, "passed")
            self.store.review_question(question_id, "needs_revision" if index in {0, 8, 12, 14} else "approved", "reviewer", reason="业务价值低" if index == 0 else "人工判定" if index in {8, 12, 14} else None)

    def test_review_reason_is_saved_without_inventing_older_event_reason(self):
        latest = self.store.review_history(self.ids[0])[0]
        self.assertEqual(latest["reason"], "业务价值低")
        self.assertTrue(latest["reviewed_at"])
        self.assertEqual(self.store.review_history("GGC-001"), [])

    def test_pair_draft_does_not_change_questions_until_atomic_apply(self):
        first, pair = self.ids[0], self.ids[8]
        original = [self.store.question(qid)["question"] for qid in (first, pair)]
        revision = self.store.start_revision(first, "manual_edit", "提升业务价值", True, {
            first: {"question": "清洁前如何检查急停按钮？", "reference_answer": "启动前检查急停按钮", "source_chunk_ids": ["C2"]},
            pair: {"question": "开机清洁前，急停按钮咋确认？", "reference_answer": "启动前检查急停按钮", "source_chunk_ids": ["C2"]},
        }, self.chunks)
        self.assertEqual([self.store.question(qid)["question"] for qid in (first, pair)], original)
        self.store.prepare_revision(revision["id"], self.chunks, similarity=lambda _a, _b: 0.1)
        self.assertEqual(self.store.revision_run(revision["id"])["status"], "preview_ready")
        self.store.apply_revision(revision["id"], self.chunks)
        self.assertEqual(self.store.question(first)["question"], "清洁前如何检查急停按钮？")
        self.assertEqual(self.store.question(pair)["raw"]["source_positive_id"], first)
        self.assertEqual(self.store.question(pair)["raw"]["ablation_attribute"], "weak_keywords")
        self.assertTrue(all(self.store.question(qid)["probe_status"] == "probe_pending" and self.store.question(qid)["qc_status"] == "qc_pending" for qid in (first, pair)))
        self.assertEqual(self.store.question(self.ids[1])["stage"], "golden")
        history = self.store.revision_history(first)
        self.assertEqual(history[0]["before"][first]["question"], original[0])
        self.assertEqual(history[0]["version_to"][first], 2)
        self.assertNotEqual(history[0]["previous_hash"][first], history[0]["new_hash"][first])

    def test_failed_draft_and_hash_conflict_preserve_original(self):
        first = self.ids[0]
        revision = self.store.start_revision(first, "manual_edit", "换证据", False, {first: {"question": "如何检查急停？", "reference_answer": "启动前检查急停按钮", "source_chunk_ids": ["MISSING"]}}, self.chunks)
        self.store.prepare_revision(revision["id"], self.chunks, similarity=lambda _a, _b: 0.1)
        self.assertEqual(self.store.revision_run(revision["id"])["status"], "failed")
        self.assertEqual(self.store.question(first)["question"], "原题 1")
        revision = self.store.start_revision(first, "manual_edit", "换证据", False, {first: {"question": "如何检查急停？", "reference_answer": "启动前检查急停按钮", "source_chunk_ids": ["C2"]}}, self.chunks)
        self.store.prepare_revision(revision["id"], self.chunks, similarity=lambda _a, _b: 0.1)
        with self.store.connection() as connection:
            connection.execute("UPDATE questions SET question='外部并发修改' WHERE id=?", (first,))
        with self.assertRaisesRegex(ValueError, "已变化"):
            self.store.apply_revision(revision["id"], self.chunks)

    def test_approved_question_cannot_enter_revision_or_snapshot_before_twenty_approvals(self):
        with self.assertRaisesRegex(ValueError, "已批准"):
            self.store.start_revision(self.ids[1], "manual_edit", "test", False, {}, self.chunks)
        with self.assertRaisesRegex(ValueError, "局部修订"):
            self.store.update_question(self.ids[1], "改动已批准题", "正确操作", self.store.question(self.ids[1])["evidence"], "reviewer")
        with self.assertRaisesRegex(ValueError, "局部修订"):
            self.store.update_question(self.ids[0], "绕过审计", "正确操作", self.store.question(self.ids[0])["evidence"], "reviewer")
        with self.assertRaisesRegex(ValueError, "20"):
            self.store.create_generation_snapshot(self.rows[0]["raw"]["generation_run_id"])
        with self.assertRaisesRegex(ValueError, "逐题"):
            self.store.review_generation_batch(self.ids, "reviewer", confirmed_manual_review=True)

    def test_semantic_duplicate_and_negative_targets_fail_closed(self):
        first = self.ids[0]
        run = self.store.start_revision(first, "manual_edit", "重复测试", False, {first: {"question": "与其他题重复", "reference_answer": "正确操作", "source_chunk_ids": ["C1"]}}, self.chunks)
        rejected = self.store.prepare_revision(run["id"], self.chunks, similarity=lambda _a, _b: .95)
        self.assertEqual(rejected["status"], "failed")
        self.assertIn("近重复", rejected["error"])
        for index, question, fragment in ((12, "请问设备报价？", "Q13"), (14, "免费换新版时要补充哪些条件？", "Q15")):
            question_id = self.ids[index]
            run = self.store.start_revision(question_id, "manual_edit", "修订边界", False, {question_id: {"question": question, "source_chunk_ids": []}}, self.chunks)
            rejected = self.store.prepare_revision(run["id"], self.chunks, similarity=lambda _a, _b: .1)
            self.assertEqual(rejected["status"], "failed")
            self.assertIn(fragment, rejected["error"])

    def test_model_unavailable_blocks_validation_without_mutating_candidate(self):
        first = self.ids[0]
        run = self.store.start_revision(first, "manual_edit", "修订", False, {first: {"question": "如何检查急停？", "reference_answer": "启动前检查急停按钮", "source_chunk_ids": ["C2"]}}, self.chunks)
        result = self.store.prepare_revision(run["id"], self.chunks, similarity=lambda _a, _b: (_ for _ in ()).throw(RuntimeError("BGE unavailable")))
        self.assertEqual(result["status"], "failed")
        self.assertIn("BGE", result["error"])
        self.assertIn(first, result["drafts"])
        self.assertEqual(self.store.question(first)["question"], "原题 1")

    def test_revision_api_requires_origin_and_persists_queued_run(self):
        old_store, old_corpus = main.store, main.corpus
        main.store = self.store
        main.corpus = type("Corpus", (), {"chunks": lambda _self: self.chunks})()
        self.addCleanup(setattr, main, "store", old_store)
        self.addCleanup(setattr, main, "corpus", old_corpus)
        client = TestClient(main.app)
        payload = {"mode": "manual_edit", "reason": "修订证据", "changes": {self.ids[0]: {"question": "如何检查急停？", "reference_answer": "启动前检查急停按钮", "source_chunk_ids": ["C2"]}}}
        route = f"/api/governance/questions/{self.ids[0]}/revision"
        self.assertEqual(client.post(route, json=payload, headers={"Origin": "https://untrusted.example"}).status_code, 403)
        with patch.object(main.threading, "Thread"):
            response = client.post(route, json=payload, headers={"Origin": "http://localhost:5174"})
        self.assertEqual(response.status_code, 202)
        revision_id = response.json()["id"]
        self.assertEqual(client.get(f"/api/governance/revisions/{revision_id}").json()["status"], "queued")
        self.assertEqual(self.store.question(self.ids[0])["question"], "原题 1")

    def test_controlled_provider_generates_pair_sequentially_without_applying(self):
        first, pair = self.ids[0], self.ids[8]
        run = self.store.start_revision(first, "ai_regenerate", "安全操作覆盖", True, {first: {"source_chunk_ids": ["C2"]}, pair: {"source_chunk_ids": ["C2"]}}, self.chunks)
        prompts = []
        class Provider:
            settings = SimpleNamespace(configured=True, model="controlled-model")
            def complete(self, instruction, payload, **kwargs):
                prompts.append((instruction, json.loads(payload)))
                question = "开机前咋查急停？" if len(prompts) == 2 else "清洁前如何检查急停按钮？"
                return json.dumps({"question": question, "reference_answer": "启动前检查急停按钮", "source_chunk_ids": ["C2"]}, ensure_ascii=False)
        service = AiService(self.store, SimpleNamespace(), Provider(), False)
        drafts = service.generate_revision_drafts(run, self.chunks)
        self.assertEqual(len(drafts), 2)
        self.assertEqual(prompts[1][1]["paired_positive"]["question"], drafts[first]["question"])
        self.assertEqual(self.store.question(first)["question"], "原题 1")
        resumed = service.generate_revision_drafts(run, self.chunks, existing={first: drafts[first]})
        self.assertEqual(len(resumed), 2)
        self.assertEqual(len(prompts), 3)
        self.assertEqual(prompts[-1][1]["paired_positive"]["question"], drafts[first]["question"])

    def test_restart_marks_unfinished_worker_interrupted_without_losing_audit(self):
        first = self.ids[0]
        run = self.store.start_revision(first, "manual_edit", "补证据", False, {first: {"question": "如何检查急停？", "reference_answer": "启动前检查急停按钮", "source_chunk_ids": ["C2"]}}, self.chunks)
        self.store.interrupt_revision_runs()
        restored = GovernanceStore(self.store.database_path).revision_run(run["id"])
        self.assertEqual(restored["status"], "interrupted")
        self.assertEqual(restored["reason"], "补证据")
        self.assertEqual(self.store.question(first)["question"], "原题 1")

    def test_old_scores_reset_and_only_successful_quality_allows_individual_rereview(self):
        first = self.ids[0]
        run = self.store.start_revision(first, "manual_edit", "修订操作", False, {first: {"question": "清洁前如何检查急停？", "reference_answer": "启动前检查急停按钮", "source_chunk_ids": ["C2"]}}, self.chunks)
        self.store.prepare_revision(run["id"], self.chunks, similarity=lambda _a, _b: .1)
        self.store.apply_revision(run["id"], self.chunks)
        self.assertEqual(self.store.question(first)["review_status"], "needs_revision")
        self.assertEqual(self.store.question(first)["probe_status"], "probe_pending")
        self.assertEqual(self.store.question(first)["qc_status"], "qc_pending")
        review = self.store.generation_review(self.rows[0]["raw"]["generation_run_id"], self.chunks)["questions"][0]
        self.assertIsNone(review["probe"])
        self.assertIsNone(review["qc"])
        self.assertEqual(len(review["probe_history"]), 1)
        self.assertEqual(len(review["qc_history"]), 1)
        self.store.record_probe_result(first, {"question_quality": 30, "golden_answer_quality": 30, "evidence_support": 40})
        self.store.record_qc(first, {"score": 90, "priority": "P2", "reason": "通过"}, "passed")
        finished = self.store.finish_revision_quality(run["id"], {first: {"probe": "passed", "qc": "qc_passed"}})
        self.assertEqual(finished["status"], "completed")
        self.assertEqual(self.store.question(first)["review_status"], "human_review_pending")
        with self.assertRaisesRegex(ValueError, "逐题"):
            self.store.review_generation_batch(self.ids, "reviewer", confirmed_manual_review=True)
        self.store.review_question(first, "approved", "reviewer")
        self.assertEqual(self.store.question(first)["stage"], "golden")


if __name__ == "__main__":
    unittest.main()
