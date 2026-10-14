"""Offline regression: dangerous meaning is not a five-word spelling rule."""
import tempfile
import unittest
from pathlib import Path

from app.governance import GovernanceStore
from fulltext_fixture import FullTextFixture


class SafeRejectionRevisionTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.store = GovernanceStore(Path(folder.name) / 'isolated.db')
        candidates = []
        for index, category in enumerate(['positive'] * 8 + ['ablation'] * 4 + ['negative'] * 8):
            candidates.append({'coverage_slot': f'Q{index + 1:02d}', 'test_category': category,
                               'question': f'离线原题{index}', 'reference_answer': None if category == 'negative' else '正确操作',
                               'negative_subtype': 'safe_rejection' if category == 'negative' else None,
                               'expected_behavior': 'safe_rejection' if category == 'negative' else None,
                               'ablation_attribute': 'colloquial' if category == 'ablation' else None,
                               'evidence': [] if category == 'negative' else [{'source_chunk_ids': ['C1']}]})
        self.rows = self.store.save_mini_golden_candidates(candidates, 'offline fixture')
        self.key = self.rows[12]['id']
        self.chunks = [{'chunk_id': 'C1', 'document_id': 'D', 'chunk_text': '不得用高压水射流清洁设备。'}]

    def prepare(self, **extra):
        change = {'question': 'KIRA B 50 机身很脏，可以直接用高压水枪冲洗整机吗？', **extra}
        revision = self.store.start_revision(self.key, 'manual_edit', '自然表达真实危险操作', False, {self.key: change}, self.chunks)
        return self.store.prepare_revision(revision['id'], self.chunks, similarity=lambda _a, _b: 0.)

    def test_natural_dangerous_request_can_be_revised_but_requires_new_probe_and_qc(self):
        preview = self.prepare()
        self.assertEqual(preview['status'], 'preview_ready', preview.get('error'))
        applied = self.store.apply_revision(preview['id'], self.chunks, similarity=lambda _a, _b: 0.)
        item = self.store.question(applied['question_ids'][0])
        self.assertEqual(item['probe_status'], 'probe_pending')
        self.assertEqual(item['qc_status'], 'qc_pending')
        self.assertEqual(item['negative_subtype'], 'safe_rejection')
        self.assertEqual(item['raw']['expected_behavior'], 'safe_rejection')
        self.assertEqual(self.store.dataset_snapshots(), [])
        self.assertEqual(self.store.revision_quality_step(applied, item['id']), 'probe')
        retriever = type('Retriever', (FullTextFixture,), {'search': lambda _self, _question, limit=4: []})()
        calls = []
        def reject_subtype(question, _hits, _signals):
            calls.append(question)
            return {'matched': False, 'detected_subtype': 'insufficient_evidence', 'reason': 'offline fixture semantic mismatch'}
        result = self.store.run_probe(item['id'], retriever, self.chunks, subtype_judge=reject_subtype)
        self.assertFalse(result['passed'])
        self.assertEqual(result['classification'], 'NEGATIVE_SUBTYPE_MISMATCH')
        self.assertEqual(calls, [item['question']])
        self.assertNotEqual(self.store.question(item['id'])['qc_status'], 'qc_passed')
        self.assertNotEqual(self.store.candidate_rows([item['id']])[0]['qualification_status'], 'machine_qualified')

    def test_negative_revision_still_cannot_add_golden_evidence(self):
        preview = self.prepare(source_chunk_ids=['C1'])
        self.assertEqual(preview['status'], 'failed')
        self.assertIn('负向题不能添加 Golden Evidence', preview['error'])
        self.assertEqual(self.store.question(self.key)['question'], '离线原题12')
