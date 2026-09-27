import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from app.ai_service import AiService
from app.governance import GovernanceStore
from app import main
from app.main import _run_mini_generation


class PartialGenerationTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.store = GovernanceStore(Path(self.folder.name) / "test.db")
        self.chunks = [{"chunk_id": f"C{i:02d}", "document_id": "D", "document_name": "fixture.pdf", "product": "P", "chunk_text": "设备可断电维护"} for i in range(1, 21)]
        self.corpus = Mock()
        self.corpus.chunks.return_value = self.chunks
        self.calls = []
        self.fail = set()
        self.provider = Mock()
        self.provider.settings.configured = True
        self.provider.settings.model = "mock-provider"
        self.provider.complete.side_effect = self.complete
        self.service = AiService(self.store, self.corpus, self.provider, False)
        self.service._indexed_embeddings = Mock(return_value=None)
        self.service._mini_coverage_plan = lambda chunks, _: [
            {"slot": f"Q{i:02d}", "test_category": "positive" if i <= 8 else "ablation" if i <= 12 else "negative", "document_id": "D", "product": "P", "evidence_chunk_ids": [chunks[i - 1]["chunk_id"]] if i <= 12 else [], "ablation_attribute": "weak_keywords" if 9 <= i <= 12 else None, "negative_subtype": "safe_rejection" if i > 12 else None, "expected_behavior": "safe_rejection" if i > 12 else None, "sources": [chunks[i - 1]]} for i in range(1, 21)
        ]
        self.service.quality_check = Mock(return_value={"priority": "P2", "reason": "fixture"})

    def complete(self, _system, payload, **_kwargs):
        data = json.loads(payload)
        slot = data["coverage_slot"]
        self.calls.append(slot)
        value = {"question": f"{slot} 如何维护设备？"}
        if data["category"] != "negative":
            value["reference_answer"] = "越界答案" if slot in self.fail else "设备可断电维护"
        return json.dumps(value, ensure_ascii=False)

    def test_partial_slots_persist_and_refill_only_failures(self):
        for missing in (1, 8):
            with self.subTest(missing=missing):
                self.fail = {f"Q{i:02d}" for i in range(1, missing + 1)}
                self.calls.clear()
                run_id = self.store.start_generation_run("mock-provider")
                _run_mini_generation(run_id, self.store, self.service, self.corpus)
                run = self.store.generation_run(run_id)
                self.assertEqual(run["status"], "needs_regeneration")
                self.assertEqual(len(run["question_ids"]), 20 - missing)
                self.assertEqual(run["operation_progress"]["phase_processed"], 20)
                self.assertEqual(run["operation_progress"]["phase_percent"], 100)
                self.assertEqual(run["operation_progress"]["processed_slots"], 20)
                self.assertEqual(run["operation_progress"]["hard_valid_completed"], 20 - missing)
                self.assertEqual(run["operation_progress"]["failed_count"], missing)
                self.assertEqual(run["artifacts"]["slot_audit"]["Q01"][0]["validation_error"], "unsupported answer anchor")
                self.assertEqual(run["artifacts"]["slot_audit"]["Q01"][0]["selected_evidence"][0]["chunk_text"], "设备可断电维护")
                self.assertEqual(len(self.store.generation_review(run_id, self.chunks, allow_partial=True)["questions"]), 20 - missing)
                with self.assertRaisesRegex(ValueError, "仅可查看"):
                    self.store.require_generation_ready(run["question_ids"][0])
                with self.assertRaisesRegex(ValueError, "完整入库"):
                    self.store.generation_review(run_id, self.chunks)
                self.store.claim_regeneration(run_id, run["artifacts"]["hard_validation"]["corpus_fingerprint"])
                self.assertEqual(self.store.generation_run(run_id)["operation_progress"]["phase_total"], missing)
                self.assertEqual(self.store.generation_run(run_id)["operation_progress"]["phase_processed"], 0)
                with self.assertRaisesRegex(ValueError, "仅待补题"):
                    self.store.claim_regeneration(run_id, run["artifacts"]["hard_validation"]["corpus_fingerprint"])
                self.fail.clear()
                self.calls.clear()
                with patch.object(self.store, "run_probe", return_value={"status": "passed"}), patch.object(self.store, "record_qc"):
                    _run_mini_generation(run_id, self.store, self.service, self.corpus, regenerate=True)
                complete = self.store.generation_run(run_id)
                self.assertEqual(complete["status"], "completed")
                self.assertEqual(len(complete["question_ids"]), 20)
                self.assertEqual(set(self.calls), {f"Q{i:02d}" for i in range(1, missing + 1)})
                self.assertEqual(len(set(complete["question_ids"])), 20)

    def test_processed_slots_advance_after_failed_attempts_without_valid_candidates(self):
        self.fail = {"Q01", "Q02", "Q03", "Q04"}
        run_id = self.store.start_generation_run("mock-provider")
        seen = []
        original = self.store.persist_generation_attempt

        def capture(*args, **kwargs):
            original(*args, **kwargs)
            if kwargs["slot"] == "Q03" and kwargs["attempt"] == 1:
                seen.append(self.store.generation_run(run_id)["operation_progress"])
            if kwargs["slot"] == "Q12":
                seen.append(self.store.generation_run(run_id)["operation_progress"])

        with patch.object(self.store, "persist_generation_attempt", side_effect=capture):
            _run_mini_generation(run_id, self.store, self.service, self.corpus)
        self.assertEqual((seen[0]["phase_processed"], seen[0]["phase_total"], seen[0]["phase_percent"], seen[0]["hard_valid_completed"]), (2, 20, 10, 0))
        self.assertEqual((seen[1]["phase_processed"], seen[1]["phase_percent"], seen[1]["hard_valid_completed"]), (12, 60, 8))

    def test_regeneration_phase_counts_only_missing_slots(self):
        self.fail = {f"Q{i:02d}" for i in range(1, 11)}
        run_id = self.store.start_generation_run("mock-provider")
        _run_mini_generation(run_id, self.store, self.service, self.corpus)
        run = self.store.generation_run(run_id)
        self.store.claim_regeneration(run_id, run["artifacts"]["hard_validation"]["corpus_fingerprint"])
        self.fail.clear()
        seen = []
        original = self.store.persist_generation_attempt

        def capture(*args, **kwargs):
            original(*args, **kwargs)
            if kwargs["slot"] == "Q04":
                seen.append(self.store.generation_run(run_id)["operation_progress"])

        with patch.object(self.store, "persist_generation_attempt", side_effect=capture), patch.object(self.store, "run_probe", return_value={"status": "passed"}), patch.object(self.store, "record_qc"):
            _run_mini_generation(run_id, self.store, self.service, self.corpus, regenerate=True)
        self.assertEqual((seen[0]["phase_processed"], seen[0]["phase_total"], seen[0]["phase_percent"], seen[0]["hard_valid_completed"]), (4, 10, 40, 14))
        self.assertEqual(seen[0]["processed_slots"], 20)

    def test_second_refill_switches_real_material_after_original_fails_again(self):
        self.fail = {"Q01"}
        run_id = self.store.start_generation_run("mock-provider")
        _run_mini_generation(run_id, self.store, self.service, self.corpus)
        fingerprint = self.store.generation_run(run_id)["artifacts"]["hard_validation"]["corpus_fingerprint"]
        self.store.claim_regeneration(run_id, fingerprint)
        _run_mini_generation(run_id, self.store, self.service, self.corpus, regenerate=True)
        self.assertEqual(self.store.generation_run(run_id)["status"], "needs_regeneration")
        self.assertEqual([item["attempt"] for item in self.store.generation_run(run_id)["artifacts"]["slot_audit"]["Q01"]], [1, 2, 3, 4])
        self.fail.clear()
        self.store.claim_regeneration(run_id, fingerprint)
        with patch.object(self.store, "run_probe", return_value={"status": "passed"}), patch.object(self.store, "record_qc"):
            _run_mini_generation(run_id, self.store, self.service, self.corpus, regenerate=True)
        self.assertEqual(self.store.generation_run(run_id)["status"], "completed")
        self.assertEqual(self.store.generation_run(run_id)["artifacts"]["slot_audit"]["Q01"][-1]["source_chunk_ids"], ["C02"])

    def test_progress_uses_persisted_slots_and_processed_quality_units(self):
        run_id = self.store.start_generation_run("mock-provider")
        for index in range(1, 21):
            slot = f"Q{index:02d}"
            candidate = {"coverage_slot": slot, "test_category": "positive" if index <= 8 else "ablation" if index <= 12 else "negative", "question": f"{slot} 问题", "reference_answer": "设备可断电维护" if index <= 12 else None, "evidence": [{"source_chunk_ids": [f"C{index:02d}"]}] if index <= 12 else [], "expected_behavior": "safe_rejection" if index > 12 else None}
            self.store.persist_generation_attempt(run_id, candidate, {slot: [{"attempt": 1, "validation_error": None}]}, slot=slot, attempt=1, model="mock-provider")
            if index in (1, 5, 12, 20):
                progress = self.store.generation_run(run_id)["operation_progress"]
                self.assertEqual(progress["hard_valid_completed"], index)
                self.assertEqual(progress["phase_percent"], index * 5)
                self.assertEqual(progress["overall_percent"], round(index / 60 * 100))
        self.store.update_generation_run(run_id, status="probing", progress={"stage": "probing", "probe_completed": 7})
        self.assertEqual(self.store.generation_run(run_id)["operation_progress"]["overall_percent"], 45)
        self.store.update_generation_run(run_id, status="qc", progress={"stage": "qc", "probe_completed": 20, "qc_completed": 5, "qc_skipped": 2})
        self.assertEqual(self.store.generation_run(run_id)["operation_progress"]["qc_processed"], 7)
        self.assertEqual(self.store.generation_run(run_id)["operation_progress"]["overall_percent"], 78)

    def test_invalid_json_attempt_keeps_bounded_response_preview(self):
        original = self.provider.complete.side_effect
        calls = 0

        def malformed(system, payload, **kwargs):
            nonlocal calls
            calls += 1
            return "{" + "x" * 900 if calls == 1 else original(system, payload, **kwargs)

        self.provider.complete.side_effect = malformed
        run_id = self.store.start_generation_run("mock-provider")
        with patch.object(self.store, "run_probe", return_value={"status": "passed"}), patch.object(self.store, "record_qc"):
            _run_mini_generation(run_id, self.store, self.service, self.corpus)
        first = self.store.generation_run(run_id)["artifacts"]["slot_audit"]["Q01"][0]
        self.assertEqual(first["error_type"], "JSONDecodeError")
        self.assertEqual(len(first["response_preview"]), 500)
        self.assertEqual(self.store.generation_run(run_id)["status"], "completed")

    def test_partial_api_is_read_only_and_refill_claim_is_exclusive(self):
        run_id = self.store.start_generation_run("mock-provider")
        candidate = {"coverage_slot": "Q01", "test_category": "positive", "question": "设备如何维护？", "reference_answer": "设备可断电维护", "evidence": [{"source_chunk_ids": ["C01"]}]}
        self.store.persist_generation_attempt(run_id, candidate, {"Q01": [{"attempt": 1, "validation_error": None}]}, slot="Q01", attempt=1, model="mock-provider")
        self.store.update_generation_run(run_id, status="needs_regeneration", progress={"stage": "needs_regeneration"})
        question_id = self.store.generation_run(run_id)["question_ids"][0]
        with patch.object(main, "store", self.store), patch.object(main, "corpus", self.corpus), patch.object(main, "_run_mini_generation"):
            client = TestClient(main.app)
            self.assertEqual(len(client.get(f"/api/governance/generation-runs/{run_id}/questions").json()["questions"]), 1)
            self.assertEqual(client.get(f"/api/governance/generation-runs/{run_id}/export").status_code, 409)
            headers = {"Origin": "http://127.0.0.1:5174"}
            self.assertEqual(client.post(f"/api/governance/questions/{question_id}/probe", headers=headers).status_code, 409)
            self.assertEqual(client.post(f"/api/governance/questions/{question_id}/review", json={"decision": "rejected"}, headers=headers).status_code, 409)
            self.assertEqual(client.put(f"/api/governance/questions/{question_id}", json={"question": "修改题目", "reference_answer": "设备可断电维护", "evidence": [{"source_chunk_ids": ["C01"]}]}, headers=headers).status_code, 409)
            with self.assertRaisesRegex(ValueError, "不完整"):
                self.store.start_revision(question_id, "ai_regenerate", "修改问题", False, {}, self.chunks)
            self.assertEqual(client.post(f"/api/governance/generation-runs/{run_id}/regenerate-failed", headers=headers).status_code, 202)
            self.assertEqual(client.post(f"/api/governance/generation-runs/{run_id}/regenerate-failed", headers=headers).status_code, 409)


if __name__ == "__main__":
    unittest.main()
