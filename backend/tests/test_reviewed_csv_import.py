"""Human-reviewed CSV imports retain their real, unexecuted machine status."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app.governance import GovernanceStore


class ReviewedCsvImportTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.store = GovernanceStore(Path(directory.name) / 'test.db')
        self.chunks = [{'chunk_id': 'C1', 'chunk_text': '使用前先断电。'}]
        self.patch = patch('app.corpus.CorpusStore.chunks', return_value=self.chunks)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.candidates = []
        for i in range(50):
            group = 'positive' if i < 20 else 'ablation' if i < 30 else 'negative'
            self.candidates.append({
                'coverage_slot': f'Q{i + 1:02d}', 'question': f'设备{i}操作前怎么办？',
                'test_category': group, 'reference_answer': '先断电' if group != 'negative' else None,
                'negative_subtype': 'insufficient_evidence' if group == 'negative' else None,
                'expected_behavior': 'insufficient_evidence' if group == 'negative' else None,
                'evidence': [] if group == 'negative' else [{'source_chunk_ids': ['C1'], 'evidence_key_points': ['使用前先断电。']}],
                'business_requirements': {'sources': [] if group == 'negative' else [{'chunk_id': 'C1', 'quote': '使用前先断电。'}],
                    'required_checks': [{'id': 'R1', 'requirement': '手册未说明', 'source_chunk_ids': [], 'basis': 'missing_information'}] if group == 'negative' else [{'id': 'R1', 'requirement': '先断电', 'source_chunk_ids': ['C1']}],
                    'conditional_checks': [], 'auxiliary_information': [], 'prohibited': [], 'acceptable_equivalents': []}})
        self.digest = hashlib.sha256(b'reviewed CSV').hexdigest()

    def imported(self):
        return self.store.import_reviewed_candidates(self.candidates, self.digest, source='任务005修订稿/定稿', review_note='总指挥已审定')

    def test_existing_confirmation_and_snapshot_without_fabricated_machine_results(self):
        imported = self.imported()
        ids = imported['question_ids']
        self.assertEqual(len(ids), 50)
        self.assertEqual(self.store.generation_run(imported['generation_run_id'])['human_gate']['status'], 'pending')
        with self.assertRaises(ValueError):
            self.store.create_generation_snapshot(imported['generation_run_id'])
        for confirm, reason in ((False, '已确认'), (True, None)):
            with self.assertRaises(ValueError):
                self.store.review_generation_batch(ids, '用户', confirmed_manual_review=confirm, reason=reason)
        reviewed = self.store.review_generation_batch(ids, '用户', confirmed_manual_review=True, reason='任务005红线清单已确认')
        self.assertTrue(all(q['stage'] == 'golden' for q in reviewed['reviewed']))
        snapshot = self.store.create_generation_snapshot(imported['generation_run_id'])
        self.assertEqual(snapshot['question_ids'], ids)
        self.assertEqual(snapshot, self.store.create_generation_snapshot(imported['generation_run_id']))
        self.assertEqual(snapshot['qualification_sources'], dict.fromkeys(ids, 'human_reviewed_csv'))
        self.assertEqual(self.store.current_baseline_identity()['current_golden_id'], snapshot['id'])
        with self.store.connection() as c:
            self.assertEqual(c.execute('SELECT COUNT(*) FROM probe_results').fetchone()[0], 0)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM qc_results').fetchone()[0], 0)
        rows = self.store.candidate_rows(ids)
        self.assertTrue(all(row['qualification_status'] == 'human_approved' for row in rows))
        self.assertTrue(all(row['probe_status'] == 'probe_pending' and row['qc_status'] == 'qc_pending' for row in rows))
        self.assertEqual(self.store.review_history(ids[0])[0]['reason'], '任务005红线清单已确认')

    def test_changed_content_corpus_and_membership_cannot_be_confirmed_or_frozen(self):
        imported = self.imported()
        ids = imported['question_ids']
        self.store.review_generation_batch(ids, '用户', confirmed_manual_review=True, reason='已确认')
        with self.store.connection() as c:
            c.execute('UPDATE questions SET question=? WHERE id=?', ('被改的问题', ids[0]))
        with self.assertRaises(ValueError):
            self.store.create_generation_snapshot(imported['generation_run_id'])
        with self.assertRaises(ValueError):
            self.store.review_generation_batch(ids, '用户', confirmed_manual_review=True, reason='已确认')

    def test_bad_sources_and_incomplete_import_write_nothing(self):
        invalid = copy.deepcopy(self.candidates)
        invalid[0]['business_requirements']['sources'][0]['quote'] = '并不存在的证据'
        for candidates in (self.candidates[:-1], invalid):
            with self.assertRaises(ValueError):
                self.store.import_reviewed_candidates(candidates, self.digest, source='任务005', review_note='已审定')
        self.assertFalse(any(q['raw'].get('source') == 'reviewed_csv' for q in self.store.questions()))

    def test_wrong_negative_behavior_answer_and_condition_cannot_enter_reviewed_path(self):
        for change in ('behavior', 'answer', 'evidence', 'condition', 'order'):
            invalid = copy.deepcopy(self.candidates)
            if change == 'behavior': invalid[-1]['expected_behavior'] = 'safe_rejection'
            if change == 'answer': invalid[0]['reference_answer'] = None
            if change == 'evidence': invalid[0]['evidence'] = []
            if change == 'condition': invalid[0]['business_requirements']['conditional_checks'] = [{'id': 'K1', 'requirement': '先断电', 'source_chunk_ids': ['C1'], 'trigger': '开机时'}]
            if change == 'order': invalid.reverse()
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.store.import_reviewed_candidates(invalid, hashlib.sha256(change.encode()).hexdigest(), source='任务005', review_note='已审定')

    def test_provenance_corpus_and_membership_tampering_remain_blocked(self):
        imported = self.imported()
        ids = imported['question_ids']
        with patch('app.reviewed_import.manifest_identity', return_value={'corpus': 'changed'}):
            with self.assertRaises(ValueError):
                self.store.review_generation_batch(ids, '用户', confirmed_manual_review=True, reason='已确认')
        with self.store.connection() as c:
            raw = json.loads(c.execute('SELECT raw_json FROM questions WHERE id=?', (ids[0],)).fetchone()[0])
            raw['import_audit']['review_note'] = '篡改说明'
            c.execute('UPDATE questions SET raw_json=? WHERE id=?', (json.dumps(raw), ids[0]))
        with self.assertRaises(ValueError):
            self.store.review_generation_batch(ids, '用户', confirmed_manual_review=True, reason='已确认')
        with self.store.connection() as c:
            c.execute('UPDATE golden_generation_runs SET question_ids_json=? WHERE id=?', (json.dumps(ids[:-1]), imported['generation_run_id']))
        with self.assertRaises(ValueError):
            self.store.review_generation_batch(ids[:-1], '用户', confirmed_manual_review=True, reason='已确认')

    def test_raw_source_marker_cannot_replace_import_receipt(self):
        imported = self.imported()
        with self.store.connection() as c:
            c.execute('DELETE FROM business_import_batches')
        with self.assertRaises(ValueError):
            self.store.review_generation_batch(imported['question_ids'], '用户', confirmed_manual_review=True, reason='已确认')

    def test_active_revision_and_superseded_rows_cannot_be_reapproved(self):
        imported = self.imported()
        ids = imported['question_ids']
        with self.store.connection() as c:
            c.execute('INSERT INTO candidate_revision_runs VALUES (?,?,?,?,?,?)',
                      ('revision', imported['generation_run_id'], 'queued', json.dumps({'question_ids':[ids[0]]}), 'fixture', 'fixture'))
        with self.assertRaisesRegex(ValueError, '局部修订'):
            self.store.review_generation_batch(ids, '用户', confirmed_manual_review=True, reason='已确认')
        with self.store.connection() as c:
            c.execute('DELETE FROM candidate_revision_runs WHERE id=?', ('revision',))
            c.execute('UPDATE questions SET stage=? WHERE id=?', ('superseded', ids[0]))
        with self.assertRaises(ValueError):
            self.store.review_generation_batch(ids, '用户', confirmed_manual_review=True, reason='已确认')

    def test_http_import_uses_existing_explicit_confirmation_and_snapshot_routes(self):
        from api_fixture import main
        from fastapi.testclient import TestClient
        with patch.object(main, 'store', self.store):
            client = TestClient(main.app)
            headers = {'Origin': 'http://localhost:5174'}
            payload = {'candidates':self.candidates, 'source_sha256':self.digest, 'source':'任务005', 'review_note':'总指挥已审定'}
            imported = client.post('/api/governance/reviewed-import', json=payload, headers=headers)
            self.assertEqual(imported.status_code, 201, imported.text)
            run = imported.json()
            confirmation = {'question_ids':run['question_ids'], 'actor':'用户', 'confirmed_manual_review':True}
            self.assertEqual(client.post('/api/governance/review-batch', json=confirmation, headers=headers).status_code, 409)
            confirmation['reason'] = '任务005红线清单已确认'
            self.assertEqual(client.post('/api/governance/review-batch', json=confirmation, headers=headers).status_code, 200)
            frozen = client.post(f"/api/governance/generation-runs/{run['generation_run_id']}/snapshot", headers=headers)
            self.assertEqual(frozen.status_code, 201, frozen.text)
            summary = client.get('/api/governance/candidates', params={'run_id':run['generation_run_id']}).json()['summary']
            self.assertEqual((summary['ai'], summary['machine_qualified'], summary['reviewed_csv']), (0, 0, 50))


if __name__ == '__main__':
    unittest.main()
