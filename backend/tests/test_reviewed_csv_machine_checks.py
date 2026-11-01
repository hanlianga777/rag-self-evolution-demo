"""Machine rechecks use the normal gates and keep human-import history intact."""
import copy
import unittest
from unittest.mock import patch

import test_reviewed_csv_import as reviewed_fixture


class MachineChecksImportTests(unittest.TestCase):
    setUp = reviewed_fixture.ReviewedCsvImportTests.setUp

    def machine_import(self, candidates=None):
        candidates = copy.deepcopy(candidates or self.candidates)
        for candidate in candidates:
            if candidate['test_category'] == 'ablation':
                candidate['ablation_attribute'] = 'colloquial'
        self.chunks[0]['document_id'] = 'D1'
        return self.store.import_reviewed_candidates(candidates, self.digest,
            source='同一份定稿', review_note='重走机器检查', machine_checks=True)

    def test_same_file_creates_separate_machine_run_without_old_approval(self):
        old = self.store.import_reviewed_candidates(self.candidates, self.digest, source='定稿', review_note='已审定')
        self.store.review_generation_batch(old['question_ids'], '用户', confirmed_manual_review=True, reason='明确确认')
        frozen = self.store.create_generation_snapshot(old['generation_run_id'])
        old_rows = [self.store.question(key) for key in old['question_ids']]
        new = self.machine_import()
        self.assertNotEqual(old['generation_run_id'], new['generation_run_id'])
        with self.assertRaisesRegex(ValueError, '已导入'):
            self.machine_import()
        rows = [self.store.question(key) for key in new['question_ids']]
        self.assertTrue(all(row['raw']['source'] == 'reviewed_csv_machine_checks' and row['legacy_question_type'] == 'v1_mini' for row in rows))
        self.assertTrue(all(row['raw']['validation']['valid'] and not row['raw']['validation']['freeze_valid'] for row in rows))
        self.assertTrue(all(row['stage'] == 'candidate' and row['review_status'] == 'human_review_pending' for row in rows))
        self.assertTrue(all(not self.store.review_history(row['id']) for row in rows))
        self.assertEqual(old_rows, [self.store.question(key) for key in old['question_ids']])
        self.assertEqual(frozen['id'], self.store.current_baseline_identity()['current_golden_id'])

    def test_pending_probe_qc_cannot_confirm_or_freeze_but_review_page_opens(self):
        imported = self.machine_import()
        run_id, ids = imported['generation_run_id'], imported['question_ids']
        review = self.store.generation_review(run_id, self.chunks)
        self.assertEqual(len(review['questions']), 50)
        self.assertTrue(all(row['probe'] is None and row['qc'] is None for row in review['questions']))
        self.assertTrue(all(row['qualification_status'] != 'human_approved' for row in review['questions']))
        with self.assertRaisesRegex(ValueError, 'Probe / QC'):
            self.store.review_generation_batch(ids, '用户', confirmed_manual_review=True, reason='不能跳过机器检查')
        with self.assertRaises(ValueError):
            self.store.create_generation_snapshot(run_id)
        with self.store.connection() as connection:
            for table in ('probe_results', 'qc_results', 'review_events', 'approvals'):
                self.assertEqual(connection.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0], 0)

    def test_machine_negative_role_adapter_keeps_expected_text_and_norms(self):
        candidates = copy.deepcopy(self.candidates)
        candidates[-1]['reference_answer'] = '手册没有说明，不猜测。'
        candidates[-1]['expected_response'] = '手册没有说明，不猜测。'
        candidates[-1]['evidence'] = [{'source_chunk_ids':['C1'], 'evidence_key_points':['使用前先断电。']}]
        requirements = copy.deepcopy(candidates[-1]['business_requirements'])
        imported = self.machine_import(candidates)
        negative = self.store.question(imported['question_ids'][-1])
        self.assertIsNone(negative['reference_answer'])
        self.assertEqual(negative['evidence'], [])
        self.assertEqual(negative['raw']['expected_response'], '手册没有说明，不猜测。')
        self.assertEqual(negative['raw']['business_requirements'], requirements)
        self.assertEqual(candidates[-1]['reference_answer'], '手册没有说明，不猜测。')

    def test_machine_hard_validation_cannot_be_replaced_by_old_approval(self):
        candidates = copy.deepcopy(self.candidates)
        candidates[0]['question'] = '第几页？'
        candidates[0]['validation'] = {'valid': True, 'freeze_valid': True, 'content_review': {'decision':'approved'}}
        with self.assertRaisesRegex(ValueError, '机器检查导入'):
            self.machine_import(candidates)
        self.assertFalse(self.store.generation_runs(qualification=False))

    def test_http_machine_mode_is_explicit_and_uses_normal_gate(self):
        from api_fixture import main
        from fastapi.testclient import TestClient
        candidates = copy.deepcopy(self.candidates)
        for candidate in candidates:
            if candidate['test_category'] == 'ablation': candidate['ablation_attribute'] = 'colloquial'
        self.chunks[0]['document_id'] = 'D1'
        payload = {'candidates':candidates, 'source_sha256':self.digest,
                   'source':'定稿', 'review_note':'重走机器检查', 'machine_checks':True}
        with patch.object(main, 'store', self.store), patch.object(main.corpus, 'chunks', return_value=self.chunks):
            client = TestClient(main.app)
            headers = {'Origin':'http://localhost:5174'}
            response = client.post('/api/governance/reviewed-import', json=payload, headers=headers)
            self.assertEqual(response.status_code, 201, response.text)
            imported = response.json()
            response = client.post('/api/governance/review-batch', json={'question_ids':imported['question_ids'],
                'actor':'用户', 'confirmed_manual_review':True, 'reason':'待机器检查'}, headers=headers)
            self.assertEqual(response.status_code, 409, response.text)


if __name__ == '__main__':
    unittest.main()
