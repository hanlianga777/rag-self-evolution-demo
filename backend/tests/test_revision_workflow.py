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
        with self.store.connection() as connection:
            pair = self.store.question(self.ids[8])
            connection.execute("UPDATE questions SET raw_json=? WHERE id=?", (json.dumps({**pair["raw"], "source_positive_id": self.ids[0]}), pair["id"]))
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
            pair: {"question": "开机前，那颗红色的紧急停机键要怎么确认？", "reference_answer": "启动前检查急停按钮", "source_chunk_ids": ["C2"]},
        }, self.chunks)
        self.assertEqual([self.store.question(qid)["question"] for qid in (first, pair)], original)
        self.store.prepare_revision(revision["id"], self.chunks, similarity=lambda _a, _b: 0.6)
        self.assertEqual(self.store.revision_run(revision["id"])["status"], "preview_ready")
        self.store.apply_revision(revision["id"], self.chunks, similarity=lambda _a, _b: .6)
        self.assertEqual(self.store.question(first)["question"], "清洁前如何检查急停按钮？")
        self.assertEqual(self.store.question(pair)["raw"]["source_positive_id"], first)
        self.assertEqual(self.store.question(pair)["raw"]["ablation_attribute"], "weak_keywords")
        self.assertTrue(all(self.store.question(qid)["probe_status"] == "probe_pending" and self.store.question(qid)["qc_status"] == "qc_pending" for qid in (first, pair)))
        self.assertEqual(self.store.question(self.ids[1])["stage"], "golden")
        history = self.store.revision_history(first)
        self.assertEqual(history[0]["before"][first]["question"], original[0])
        self.assertEqual(history[0]["version_to"][first], 2)
        self.assertNotEqual(history[0]["previous_hash"][first], history[0]["new_hash"][first])

    def test_q09_can_start_alone_without_changing_q01_and_keeps_relation(self):
        first, pair = self.ids[0], self.ids[8]
        with self.store.connection() as connection:
            connection.execute("UPDATE questions SET raw_json=? WHERE id=?", (json.dumps({**self.store.question(pair)["raw"], "paired_question_id": first}), pair))
        before = self.store.question(first)
        run = self.store.start_revision(pair, "manual_edit", "只修鲁棒性题", False, {
            pair: {"question": "开工前，那个红色急停还灵不灵，得怎么确认？", "reference_answer": "正确操作", "source_chunk_ids": ["C1"]},
        }, self.chunks)
        self.assertEqual(run["question_ids"], [pair])
        self.assertEqual(self.store.revision_positive(run)["id"], first)
        self.assertEqual(self.store.question(first), before)
        self.assertEqual(self.store.question(pair)["raw"].get("source_positive_id"), first)
        ready = self.store.prepare_revision(run["id"], self.chunks, similarity=lambda _a, _b: .6)
        self.assertFalse(ready.get("apply_blocked", False))
        self.store.apply_revision(run["id"], self.chunks, similarity=lambda _a, _b: .6)
        self.assertEqual(self.store.question(pair)["raw"]["source_positive_id"], first)
        self.assertEqual(self.store.question(pair)["raw"]["paired_question_id"], first)
        self.assertEqual(self.store.question(first), before)

    def test_explicit_pair_does_not_require_shared_original_chunk(self):
        first, pair = self.ids[0], self.ids[8]
        with self.store.connection() as connection:
            connection.execute("UPDATE questions SET evidence_json=? WHERE id=?", (json.dumps([{"source_chunk_ids": ["C2"]}]), pair))
        run = self.store.start_revision(pair, "manual_edit", "共同修订", True, {
            first: {"source_chunk_ids": ["C1"]}, pair: {"source_chunk_ids": ["C2"]},
        }, self.chunks)
        self.assertEqual(set(run["question_ids"]), {first, pair})

    def test_weak_keywords_rejects_lexical_overlap_and_inconsistent_answer(self):
        first, pair = self.ids[0], self.ids[8]
        with self.store.connection() as connection:
            connection.execute("UPDATE questions SET question='警告、小心、注意分别表示什么危险等级？', reference_answer='正确操作' WHERE id=?", (first,))
        for question, answer, error in (
            ("不同安全提示词分别代表什么危险程度？", "正确操作", "ABLATION_TOO_SIMILAR"),
            ("说明书里那几档安全提醒怎么看？哪个最严重，另外两档大概分别是在提醒什么风险？", "其他答案", "答案"),
        ):
            run = self.store.start_revision(pair, "manual_edit", "弱关键词修订", False, {
                pair: {"question": question, "reference_answer": answer, "source_chunk_ids": ["C1"]},
            }, self.chunks)
            result = self.store.prepare_revision(run["id"], self.chunks, similarity=lambda _a, _b: .1)
            self.assertIn(error, result["error"])
            self.assertTrue(result["apply_blocked"])
            self.store.discard_revision(run["id"])

    def test_weak_keywords_requires_semantic_alignment_and_accepts_indirect_question(self):
        first, pair = self.ids[0], self.ids[8]
        with self.store.connection() as connection:
            connection.execute("UPDATE questions SET question='警告、小心、注意分别表示什么危险等级？' WHERE id=?", (first,))
        good = "说明书里那几档安全提醒怎么看？哪个最严重，另外两档大概分别是在提醒什么风险？"
        run = self.store.start_revision(pair, "manual_edit", "弱关键词修订", False, {pair: {"question": good, "reference_answer": "正确操作", "source_chunk_ids": ["C1"]}}, self.chunks)
        blocked = self.store.prepare_revision(run["id"], self.chunks, similarity=lambda _a, _b: .27)
        self.assertIn("知识点不一致", blocked["error"])
        self.store.discard_revision(run["id"])
        run = self.store.start_revision(pair, "manual_edit", "弱关键词修订", False, {pair: {"question": good, "reference_answer": "正确操作", "source_chunk_ids": ["C1"]}}, self.chunks)
        accepted = self.store.prepare_revision(run["id"], self.chunks, similarity=lambda _a, _b: .65)
        self.assertEqual(accepted["status"], "preview_ready")
        self.assertFalse(accepted.get("apply_blocked", False))

    def test_manual_unchanged_seed_enters_blocked_preview_for_editing(self):
        pair = self.ids[8]
        run = self.store.start_revision(pair, "manual_edit", "准备人工改写", False, {
            pair: {"source_chunk_ids": ["C1"]},
        }, self.chunks)
        result = self.store.prepare_revision(run["id"], self.chunks, similarity=lambda _a, _b: .1)
        self.assertEqual(result["status"], "preview_ready")
        self.assertTrue(result["apply_blocked"])
        self.assertEqual(result["drafts"][pair]["question"], "原题 9")

    def test_manual_pair_seed_can_be_edited_after_blocked_preview(self):
        first, pair = self.ids[0], self.ids[8]
        with self.store.connection() as connection:
            connection.execute("UPDATE questions SET reference_answer='另一事实' WHERE id=?", (pair,))
        run = self.store.start_revision(pair, "manual_edit", "准备成对人工改写", True, {
            first: {"source_chunk_ids": ["C1"]}, pair: {"source_chunk_ids": ["C1"]},
        }, self.chunks)
        result = self.store.prepare_revision(run["id"], self.chunks, similarity=lambda _a, _b: .6)
        self.assertEqual(result["status"], "preview_ready")
        self.assertTrue(result["apply_blocked"])
        self.assertEqual(set(result["drafts"]), {first, pair})

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
            self.store.apply_revision(revision["id"], self.chunks, similarity=lambda _a, _b: .1)

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
        for index, question, fragment in ((12, "请问设备报价？", "安全拒答"),):
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

    def test_q09_only_ai_prompt_has_current_positive_and_weak_keyword_constraints(self):
        pair = self.ids[8]
        run = self.store.start_revision(pair, "ai_regenerate", "弱关键词修订", False, {pair: {"source_chunk_ids": ["C1"]}}, self.chunks)
        calls = []
        class Provider:
            settings = SimpleNamespace(configured=True, model="controlled-model")
            def complete(self, instruction, payload, **kwargs):
                calls.append((instruction, json.loads(payload)))
                return json.dumps({"question": "开工前，红色紧急停机开关是不是正常？", "reference_answer": "正确操作", "source_chunk_ids": ["C1"]}, ensure_ascii=False)
        AiService(self.store, SimpleNamespace(), Provider(), False).generate_revision_drafts(run, self.chunks)
        self.assertEqual(calls[0][1]["paired_positive"]["id"], self.ids[0])
        self.assertIn("不能只是同义词替换", calls[0][0])
        self.assertIn("原文关键词", calls[0][0])

    def test_q09_ai_lexical_repair_is_bounded_and_audited(self):
        pair = self.ids[8]
        run = self.store.start_revision(pair, "ai_regenerate", "降低词面重复", False, {pair: {"source_chunk_ids": ["C1"]}}, self.chunks)
        class Service:
            def __init__(self):
                self.calls = 0
            def generate_revision_drafts(self, prompt_run, chunks, on_progress=None, existing=None):
                self.calls += 1
                question = "原题 1" if self.calls < 3 else "开工前，红色紧急停机开关是不是正常？"
                return {pair: {"question": question, "reference_answer": "正确操作", "source_chunk_ids": ["C1"]}}
            def revision_similarity(self, _a, _b):
                return .6
        service = Service()
        main._prepare_revision(run["id"], self.store, service, SimpleNamespace(chunks=lambda: self.chunks))
        result = self.store.revision_run(run["id"])
        self.assertEqual(service.calls, 3)
        self.assertEqual(result["status"], "preview_ready")
        self.assertEqual([item["error"] for item in result["generation_attempts"][:2]], ["ABLATION_TOO_SIMILAR"] * 2)
        self.assertIsNone(result["generation_attempts"][2]["error"])
        self.assertEqual(self.store.question(pair)["question"], "原题 9")

    def test_q09_ai_stops_after_three_similar_drafts(self):
        pair = self.ids[8]
        run = self.store.start_revision(pair, "ai_regenerate", "降低词面重复", False, {pair: {"source_chunk_ids": ["C1"]}}, self.chunks)
        class Service:
            calls = 0
            def generate_revision_drafts(self, prompt_run, chunks, on_progress=None, existing=None):
                self.calls += 1
                return {pair: {"question": "原题 1", "reference_answer": "正确操作", "source_chunk_ids": ["C1"]}}
            def revision_similarity(self, _a, _b):
                return .6
        service = Service()
        main._prepare_revision(run["id"], self.store, service, SimpleNamespace(chunks=lambda: self.chunks))
        result = self.store.revision_run(run["id"])
        self.assertEqual(service.calls, 3)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(len(result["generation_attempts"]), 3)
        self.assertTrue(all(item["error"] == "ABLATION_TOO_SIMILAR" for item in result["generation_attempts"]))
        self.assertEqual(self.store.question(pair)["question"], "原题 9")

    def test_q09_ai_provider_error_is_audited_without_changing_candidate(self):
        pair = self.ids[8]
        run = self.store.start_revision(pair, "ai_regenerate", "模型失败审计", False, {pair: {"source_chunk_ids": ["C1"]}}, self.chunks)
        class Service:
            def generate_revision_drafts(self, prompt_run, chunks, on_progress=None, existing=None):
                raise RuntimeError("Provider unavailable")
            def revision_similarity(self, _a, _b):
                return .6
        main._prepare_revision(run["id"], self.store, Service(), SimpleNamespace(chunks=lambda: self.chunks))
        result = self.store.revision_run(run["id"])
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["generation_attempts"][0]["question_id"], pair)
        self.assertEqual(result["generation_attempts"][0]["error"], "Provider unavailable")
        self.assertEqual(self.store.question(pair)["question"], "原题 9")

    def test_preview_edit_regenerate_and_discard_preserve_original_until_apply(self):
        first, pair = self.ids[0], self.ids[8]
        run = self.store.start_revision(first, "manual_edit", "改善两题", True, {
            first: {"question": "清洁前如何检查急停按钮？", "reference_answer": "启动前检查急停按钮", "source_chunk_ids": ["C2"]},
            pair: {"question": "开机前，那颗红色的紧急停机键要怎么确认？", "reference_answer": "启动前检查急停按钮", "source_chunk_ids": ["C2"]},
        }, self.chunks)
        ready = self.store.prepare_revision(run["id"], self.chunks, similarity=lambda _a, _b: .6)
        first_hash = ready["new_hash"][first]
        pair_hash = ready["new_hash"][pair]
        edited = self.store.edit_revision_preview(run["id"], {pair: {
            "question": "准备干活时，那个红色紧停键怎么确认能用？", "reference_answer": "启动前检查急停按钮", "source_chunk_ids": ["C2"],
        }}, {pair: pair_hash}, self.chunks, similarity=lambda _a, _b: .6)
        self.assertEqual(edited["status"], "preview_ready")
        self.assertEqual(edited["new_hash"][first], first_hash)
        self.assertEqual(edited["drafts"][first], ready["drafts"][first])
        self.assertEqual(edited["draft_attempts"][-1]["question_ids"], [pair])
        self.assertEqual(self.store.question(pair)["question"], "原题 9")
        with self.assertRaisesRegex(ValueError, "过期"):
            self.store.edit_revision_preview(run["id"], {pair: {"question": "旧版"}}, {pair: pair_hash}, self.chunks, similarity=lambda _a, _b: .1)
        blocked = self.store.edit_revision_preview(run["id"], {pair: {"question": "无法使用的证据", "source_chunk_ids": ["MISSING"]}}, {pair: edited["new_hash"][pair]}, self.chunks, similarity=lambda _a, _b: .1)
        self.assertTrue(blocked["apply_blocked"])
        self.assertEqual(blocked["drafts"], edited["drafts"])
        with self.assertRaisesRegex(ValueError, "暂停"):
            self.store.apply_revision(run["id"], self.chunks, similarity=lambda _a, _b: .1)
        cancelled = self.store.discard_revision(run["id"])
        self.assertEqual((cancelled["status"], cancelled["stage"]), ("cancelled", "discarded"))
        self.assertEqual(self.store.question(first)["question"], "原题 1")
        self.assertEqual(self.store.question(pair)["question"], "原题 9")
        self.assertEqual(self.store.question(first)["probe_status"], "probe_passed")
        self.assertEqual(self.store.question(pair)["qc_status"], "qc_passed")
        self.assertEqual(len(self.store.probe_history(first)), 1)
        self.assertEqual(len(self.store.qc_history(pair)), 1)
        self.assertEqual(len(cancelled["draft_attempts"]), 2)
        self.store.start_revision(first, "manual_edit", "新一轮", False, {first: {"question": "清洁前如何检查急停？", "reference_answer": "启动前检查急停按钮", "source_chunk_ids": ["C2"]}}, self.chunks)

    def test_targeted_regeneration_uses_current_evidence_and_keeps_pair_draft(self):
        first, pair = self.ids[0], self.ids[8]
        run = self.store.start_revision(first, "manual_edit", "改善两题", True, {
            first: {"question": "清洁前如何检查急停按钮？", "reference_answer": "启动前检查急停按钮", "source_chunk_ids": ["C2"]},
            pair: {"question": "开机清洁前，急停按钮咋确认？", "reference_answer": "启动前检查急停按钮", "source_chunk_ids": ["C2"]},
        }, self.chunks)
        ready = self.store.prepare_revision(run["id"], self.chunks, similarity=lambda _a, _b: .6)
        started = self.store.begin_revision_regeneration(run["id"], pair, ready["new_hash"][pair])
        self.assertEqual(started["status"], "generating")
        with self.assertRaisesRegex(ValueError, "运行中"):
            self.store.begin_revision_regeneration(run["id"], pair, ready["new_hash"][pair])
        self.store.interrupt_revision_runs()
        interrupted = self.store.revision_run(run["id"])
        self.assertEqual(interrupted["active_draft"]["question_ids"], [pair])
        prompts = []
        class Provider:
            settings = SimpleNamespace(configured=True, model="controlled-model")
            def complete(self, instruction, payload, **kwargs):
                prompts.append(json.loads(payload))
                return json.dumps({"question": "开工前红色急停要咋查？", "reference_answer": "启动前检查急停按钮", "source_chunk_ids": ["C2"]}, ensure_ascii=False)
        service = AiService(self.store, SimpleNamespace(), Provider(), False)
        generated = service.generate_revision_drafts({**interrupted, "changes": {**interrupted["changes"], pair: {"source_chunk_ids": ["C2"]}}}, self.chunks, existing={first: {"question": ready["drafts"][first]["question"], "reference_answer": ready["drafts"][first]["reference_answer"], "source_chunk_ids": ["C2"]}})
        updated = self.store.finish_revision_regeneration(run["id"], {pair: generated[pair]}, self.chunks, similarity=lambda _a, _b: .6)
        self.assertEqual(len(prompts), 1)
        self.assertEqual(prompts[0]["selected_chunks"][0]["chunk_id"], "C2")
        self.assertEqual(updated["drafts"][first], ready["drafts"][first])
        self.assertEqual(updated["draft_attempts"][-1]["question_ids"], [pair])
        self.assertEqual(updated["draft_attempts"][-1]["status"], "passed")
        self.assertEqual(updated["draft_attempts"][-1]["before_drafts"][pair]["question"], ready["drafts"][pair]["question"])
        self.assertEqual(updated["draft_attempts"][-1]["validated_drafts"][pair]["question"], "开工前红色急停要咋查？")
        self.store.apply_revision(run["id"], self.chunks, similarity=lambda _a, _b: .6)
        history = self.store.revision_run(run["id"])
        self.assertEqual(len(history["draft_attempts"]), 1)
        self.assertEqual(self.store.question(pair)["probe_status"], "probe_pending")
        self.assertEqual(self.store.question(pair)["qc_status"], "qc_pending")
        self.store.finish_revision_quality(run["id"], {first: {"probe": "passed", "qc": "qc_passed"}, pair: {"probe": "passed", "qc": "qc_passed"}})
        self.assertEqual(len(self.store.revision_run(run["id"])["draft_attempts"]), 1)

    def test_preview_can_edit_both_paired_drafts_in_one_validation(self):
        first, pair = self.ids[0], self.ids[8]
        run = self.store.start_revision(first, "manual_edit", "改善两题", True, {
            first: {"question": "清洁前如何检查急停按钮？", "reference_answer": "启动前检查急停按钮", "source_chunk_ids": ["C2"]},
            pair: {"question": "开机清洁前，急停按钮咋确认？", "reference_answer": "启动前检查急停按钮", "source_chunk_ids": ["C2"]},
        }, self.chunks)
        ready = self.store.prepare_revision(run["id"], self.chunks, similarity=lambda _a, _b: .6)
        edited = self.store.edit_revision_preview(run["id"], {
            first: {"question": "启动清洁前怎样检查急停按钮？", "reference_answer": "启动前检查急停按钮", "source_chunk_ids": ["C2"]},
            pair: {"question": "开工前那个急停按键咋确认？", "reference_answer": "启动前检查急停按钮", "source_chunk_ids": ["C2"]},
        }, ready["new_hash"], self.chunks, similarity=lambda _a, _b: .6)
        self.assertFalse(edited["apply_blocked"])
        self.assertEqual(edited["drafts"][first]["question"], "启动清洁前怎样检查急停按钮？")
        self.assertEqual(edited["drafts"][pair]["question"], "开工前那个急停按键咋确认？")
        self.assertEqual(set(edited["draft_attempts"][-1]["question_ids"]), {first, pair})

    def test_preview_routes_require_origin_and_keep_candidate_unchanged(self):
        first, pair = self.ids[0], self.ids[8]
        run = self.store.start_revision(first, "manual_edit", "改善两题", True, {
            first: {"question": "清洁前如何检查急停按钮？", "reference_answer": "启动前检查急停按钮", "source_chunk_ids": ["C2"]},
            pair: {"question": "开机清洁前，急停按钮咋确认？", "reference_answer": "启动前检查急停按钮", "source_chunk_ids": ["C2"]},
        }, self.chunks)
        ready = self.store.prepare_revision(run["id"], self.chunks, similarity=lambda _a, _b: .1)
        old_store, old_corpus = main.store, main.corpus
        main.store = self.store
        main.corpus = type("Corpus", (), {"chunks": lambda _self: self.chunks})()
        self.addCleanup(setattr, main, "store", old_store)
        self.addCleanup(setattr, main, "corpus", old_corpus)
        client = TestClient(main.app)
        path = f"/api/governance/revisions/{run['id']}"
        payload = {"changes": {pair: {"question": "准备清洁时，急停按钮如何确认？", "reference_answer": "启动前检查急停按钮", "source_chunk_ids": ["C2"]}}, "expected_hashes": {pair: ready["new_hash"][pair]}}
        self.assertEqual(client.post(path + "/edit-draft", json=payload, headers={"Origin": "https://untrusted.example"}).status_code, 403)
        with patch.object(main.ai_service, "revision_similarity", side_effect=lambda _a, _b: .1):
            edited = client.post(path + "/edit-draft", json=payload, headers={"Origin": "http://localhost:5174"})
        self.assertEqual(edited.status_code, 200)
        self.assertEqual(edited.json()["status"], "preview_ready")
        self.assertEqual(self.store.question(pair)["question"], "原题 9")
        regeneration = {"question_id": pair, "expected_hash": edited.json()["new_hash"][pair]}
        self.assertEqual(client.post(path + "/regenerate-draft", json=regeneration, headers={"Origin": "https://untrusted.example"}).status_code, 403)
        with patch.object(main.threading, "Thread"):
            started = client.post(path + "/regenerate-draft", json=regeneration, headers={"Origin": "http://localhost:5174"})
        self.assertEqual(started.status_code, 202)
        self.assertEqual(self.store.revision_run(run["id"])["active_draft"]["question_ids"], [pair])
        self.store.fail_revision_regeneration(run["id"], "Provider unavailable")
        self.assertTrue(self.store.revision_run(run["id"])["apply_blocked"])
        self.assertEqual(client.post(path + "/discard", headers={"Origin": "https://untrusted.example"}).status_code, 403)
        discarded = client.post(path + "/discard", headers={"Origin": "http://localhost:5174"})
        self.assertEqual(discarded.status_code, 200)
        self.assertEqual(discarded.json()["status"], "cancelled")

    def test_interrupted_preview_edit_resumes_only_selected_question(self):
        first, pair = self.ids[0], self.ids[8]
        run = self.store.start_revision(first, "manual_edit", "改善两题", True, {
            first: {"question": "清洁前如何检查急停按钮？", "reference_answer": "启动前检查急停按钮", "source_chunk_ids": ["C2"]},
            pair: {"question": "开机清洁前，急停按钮咋确认？", "reference_answer": "启动前检查急停按钮", "source_chunk_ids": ["C2"]},
        }, self.chunks)
        ready = self.store.prepare_revision(run["id"], self.chunks, similarity=lambda _a, _b: .1)
        self.store._begin_preview_attempt(run["id"], [pair], {pair: ready["new_hash"][pair]}, "edit", {pair: {"question": "准备清洁时，急停按钮如何确认？", "reference_answer": "启动前检查急停按钮", "source_chunk_ids": ["C2"]}})
        self.store.interrupt_revision_runs()
        service = SimpleNamespace(revision_similarity=lambda _a, _b: .1)
        main._resume_revision_edit(run["id"], self.store, service, SimpleNamespace(chunks=lambda: self.chunks))
        restored = self.store.revision_run(run["id"])
        self.assertEqual(restored["status"], "preview_ready")
        self.assertEqual(restored["drafts"][first], ready["drafts"][first])
        self.assertEqual(restored["draft_attempts"][-1]["question_ids"], [pair])

    def test_regeneration_worker_calls_provider_for_only_selected_pair_member(self):
        first, pair = self.ids[0], self.ids[8]
        run = self.store.start_revision(first, "manual_edit", "改善两题", True, {
            first: {"question": "清洁前如何检查急停按钮？", "reference_answer": "启动前检查急停按钮", "source_chunk_ids": ["C2"]},
            pair: {"question": "开机清洁前，急停按钮咋确认？", "reference_answer": "启动前检查急停按钮", "source_chunk_ids": ["C2"]},
        }, self.chunks)
        ready = self.store.prepare_revision(run["id"], self.chunks, similarity=lambda _a, _b: .1)
        self.store.begin_revision_regeneration(run["id"], pair, ready["new_hash"][pair])
        calls = []
        class Service:
            revision_similarity = staticmethod(lambda _a, _b: .1)
            def generate_revision_drafts(self, prompt_run, chunks, *, existing):
                calls.append((prompt_run, existing))
                return {**existing, pair: {"question": "准备清洁时急停按钮咋确认？", "reference_answer": "启动前检查急停按钮", "source_chunk_ids": ["C2"]}}
        main._regenerate_revision_draft(run["id"], self.store, Service(), SimpleNamespace(chunks=lambda: self.chunks))
        updated = self.store.revision_run(run["id"])
        self.assertEqual(updated["status"], "preview_ready")
        self.assertEqual(calls[0][0]["changes"][pair]["source_chunk_ids"], ["C2"])
        self.assertEqual(list(calls[0][1]), [first])
        self.assertEqual(updated["drafts"][first], ready["drafts"][first])
        self.assertEqual(updated["draft_attempts"][-1]["question_ids"], [pair])

    def test_apply_revalidates_and_rejects_stale_current_index(self):
        first = self.ids[0]
        run = self.store.start_revision(first, "manual_edit", "换证据", False, {first: {"question": "清洁前如何检查急停？", "reference_answer": "启动前检查急停按钮", "source_chunk_ids": ["C2"]}}, self.chunks)
        self.store.prepare_revision(run["id"], self.chunks, similarity=lambda _a, _b: .1)
        with self.assertRaisesRegex(ValueError, "Hard Validation"):
            self.store.apply_revision(run["id"], self.chunks[:1], similarity=lambda _a, _b: .1)
        self.assertEqual(self.store.question(first)["question"], "原题 1")

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
        self.store.apply_revision(run["id"], self.chunks, similarity=lambda _a, _b: .1)
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
