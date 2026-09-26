"""V1.2 gates: machine evidence cannot be waived, model severity can be acknowledged."""
import tempfile
import unittest
from pathlib import Path

from app.governance import GovernanceStore
from test_revision_workflow import candidates


class V12GovernanceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.store = GovernanceStore(Path(self.directory.name) / 'isolated.db')
        self.items = self.store.save_mini_golden_candidates(candidates(), 'fixture')
        self.run_id = self.items[0]['raw']['generation_run_id']

    def quality(self, item, priority='P2', score=50, evidence_failure=False):
        self.store.record_probe_result(item['id'], {'question_quality': 20, 'golden_answer_quality': 20, 'evidence_support': 40, 'evidence_direct_failure': evidence_failure})
        if not evidence_failure:
            self.store.record_qc(item['id'], {'priority': priority, 'score': score, 'reason': 'human must inspect', 'issues': []}, 'failed')

    def test_positive_numeric_scores_do_not_override_valid_evidence_or_qc_priority(self):
        item = self.items[0]
        self.quality(item)
        approved = self.store.review_question(item['id'], 'approved', 'test_human')
        self.assertEqual(approved['review_status'], 'approved')

    def test_p0_requires_explicit_acknowledgement_and_reason(self):
        item = self.items[0]
        self.quality(item, 'P0')
        with self.assertRaisesRegex(ValueError, 'P0'):
            self.store.review_question(item['id'], 'approved', 'test_human')
        self.store.review_question(item['id'], 'approved', 'test_human', accept_qc_p0=True, reason='已核对完整原文，接受该机器风险判断')
        self.assertTrue(self.store.review_history(item['id'])[0]['accept_qc_p0'])

    def test_evidence_failure_cannot_be_waived(self):
        item = self.items[0]
        self.quality(item, evidence_failure=True)
        with self.assertRaises(ValueError):
            self.store.review_question(item['id'], 'approved', 'test_human', accept_qc_p0=True, reason='not sufficient')

    def test_ablation_does_not_require_positive_answer_or_evidence(self):
        item = self.items[8]
        self.store.review_question(item['id'], 'needs_revision', 'test_human', reason='独立鲁棒性题')
        chunks = [{'document_id': 'DOC-X', 'chunk_id': 'C1', 'chunk_text': '正确操作'}, {'document_id': 'DOC-X', 'chunk_id': 'C2', 'chunk_text': '启动前检查急停按钮，确认安全后开始清洁。'}]
        changes = {item['id']: {'question': '开工前怎么确认那个紧急停机的装置正常？', 'reference_answer': '启动前检查急停按钮', 'source_chunk_ids': ['C2']}}
        run = self.store.start_revision(item['id'], 'manual_edit', '独立知识点', False, changes, chunks)
        ready = self.store.prepare_revision(run['id'], chunks, similarity=lambda *_: 0)
        self.assertTrue(ready['validation']['passed'], ready.get('error'))

    def test_gate1_approves_and_freezes_once_atomically(self):
        for item in self.items:
            self.store.record_probe_result(item['id'], {'question_quality': 30, 'golden_answer_quality': 30, 'evidence_support': 40})
            self.store.record_qc(item['id'], {'score': 99, 'priority': 'P2'}, 'passed')
        result = self.store.review_generation_batch([i['id'] for i in self.items], 'test_human', confirmed_manual_review=True)
        self.assertEqual(len(result['snapshot']['question_ids']), 20)
        again = self.store.review_generation_batch([i['id'] for i in self.items], 'test_human', confirmed_manual_review=True)
        self.assertEqual(result['snapshot']['id'], again['snapshot']['id'])
        self.assertEqual(len(self.store.review_history(self.items[0]['id'])), 1)

    def test_gate1_failure_writes_neither_approval_nor_snapshot(self):
        with self.assertRaises(ValueError):
            self.store.review_generation_batch([i['id'] for i in self.items], 'test_human', confirmed_manual_review=True)
        self.assertEqual(self.store.review_history(self.items[0]['id']), [])
        self.assertEqual(self.store.dataset_snapshots(), [])

    def test_replace_switches_active_slot_only_on_apply_and_keeps_original(self):
        item = self.items[0]
        chunks = [{'document_id': 'DOC-X', 'chunk_id': 'C1', 'chunk_text': '正确操作'}, {'document_id': 'DOC-X', 'chunk_id': 'C2', 'chunk_text': '启动前检查急停按钮'}]
        changes = {item['id']: {'question': '开工前要检查哪个按钮？', 'reference_answer': '启动前检查急停按钮', 'source_chunk_ids': ['C2']}}
        run = self.store.start_revision(item['id'], 'manual_edit', '替换低价值题', False, changes, chunks, replacement=True, actor='test_human')
        self.store.prepare_revision(run['id'], chunks, similarity=lambda *_: 0)
        self.assertEqual(self.store.generation_run(self.run_id)['question_ids'][0], item['id'])
        applied = self.store.apply_revision(run['id'], chunks, similarity=lambda *_: 0)
        active_id = applied['question_ids'][0]
        self.assertNotEqual(active_id, item['id'])
        self.assertEqual(self.store.question(item['id'])['question'], item['question'])
        self.assertEqual(self.store.generation_run(self.run_id)['question_ids'][0], active_id)
        replacement = self.store.question(active_id)
        self.assertEqual(replacement['raw']['coverage_slot'], item['raw']['coverage_slot'])
        self.assertEqual(replacement['probe_status'], 'probe_pending')
        self.assertEqual(replacement['qc_status'], 'qc_pending')
        exported = self.store.generation_review(self.run_id, chunks)
        self.assertEqual(len(exported['questions']), 20)
        self.assertNotIn(item['id'], [row['id'] for row in exported['questions']])
        self.assertTrue(self.store.revision_history(item['id']))
