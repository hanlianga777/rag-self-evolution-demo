"""Baseline review uses disposable SQLite and stub generation/judgment."""
import unittest
from copy import deepcopy
from unittest.mock import patch

import test_baseline_resume as fixture
from app.providers import ProviderTimeout


class BaselineReviewTests(unittest.TestCase):
    setUp = fixture.ResumeTests.setUp
    tearDown = fixture.ResumeTests.tearDown

    def completed(self):
        key, items, config = self.runner.start_baseline()
        for item in items:
            self.store.record_evaluation_case(key, item['id'], {'passed': item['id'] not in {'Q1', 'Q2'}})
        self.store.finish_evaluation_run(key, 'completed', {'evaluation_complete': True, 'completed': 4,
            'technical_failed': 0, 'overall_score': 77, 'gates': {'passed': False}})
        return key, config

    def test_majority_is_saved_without_changing_formal_results_or_config(self):
        key, config = self.completed()
        before = deepcopy(self.store.evaluation_run(key))
        cases = self.store.evaluation_case_results(key)
        verdicts = iter([True, True, False, True])
        received = []
        def answer(q, actual):
            received.append(deepcopy(actual))
            return {'answer': 'fixture'}
        with patch.object(self.runtime, 'answer', side_effect=answer), \
             patch.object(self.runner, 'score_execution', side_effect=lambda *a, **k: {'passed': next(verdicts)}):
            review = self.runner.review_baseline_errors(key)
            self.assertEqual(self.runner.review_baseline_errors(key), review)
        self.assertEqual(received, [config] * 4)
        self.assertTrue(review['complete'])
        self.assertEqual(review['cases']['Q1']['regression_review']['status'], 'fluctuation')
        self.assertEqual(review['cases']['Q2']['regression_review']['status'], 'confirmed_regression')
        after = self.store.evaluation_run(key)
        self.assertEqual(after['result'].pop('baseline_review'), review)
        self.assertEqual(after['result'], before['result'])
        for field in ('status', 'completed_at', 'config_json', 'judge_json', 'dataset_snapshot_json'):
            self.assertEqual(after[field], before[field])
        self.assertEqual(self.store.evaluation_case_results(key), cases)

    def test_terminal_stage_failure_gets_one_final_retry_and_reuses_saved_answer(self):
        key, _ = self.completed()
        calls = []
        def score(item, execution, **kwargs):
            calls.append(item['id'])
            if len(calls) == 1:
                raise ProviderTimeout('fixture exhausted transport')
            return {'passed': True}
        with patch.object(self.runner, 'score_execution', side_effect=score):
            result = self.runner.review_baseline_errors(key)
        self.assertTrue(result['complete'])
        self.assertEqual(self.runtime.answers.count('Q1'), 2)
        self.assertEqual(self.runtime.answers.count('Q2'), 2)
        self.assertTrue(result['cases']['Q1']['final_retry_done'])

    def test_followup_stop_on_error_has_no_final_retry_and_saves_progress(self):
        key, _ = self.completed()
        updates = []
        with patch.object(self.runner, 'score_execution', side_effect=ProviderTimeout('fixture stop')) as score:
            with self.assertRaises(ProviderTimeout):
                self.runner.review_baseline_errors(key, on_progress=lambda review: updates.append(deepcopy(review)), stop_on_error=True)
        self.assertEqual(score.call_count, 1)
        self.assertEqual(self.runtime.answers, ['Q1'])
        saved = self.store.evaluation_run(key)['result']['baseline_review']
        self.assertIn('technical_error', saved['cases']['Q1'])
        self.assertNotIn('final_retry_done', saved['cases']['Q1'])
        self.assertEqual(updates[-1], saved)

    def test_incomplete_baseline_never_calls_provider(self):
        key, _ = self.completed()
        with self.store.connection() as db:
            db.execute("UPDATE evaluation_runs SET result_json='{}' WHERE id=?", (key,))
        with self.assertRaises(ValueError):
            self.runner.review_baseline_errors(key)
        self.assertEqual(self.runtime.answers, [])

    def test_changed_judge_identity_never_calls_provider(self):
        key, _ = self.completed()
        with patch('app.evaluation.policy_current', return_value=False), self.assertRaises(ValueError):
            self.runner.review_baseline_errors(key)
        self.assertEqual(self.runtime.answers, [])

    def test_resume_keeps_generation_saved_before_interruption(self):
        key, _ = self.completed()
        with patch.object(self.runner, 'score_execution', side_effect=KeyboardInterrupt), self.assertRaises(KeyboardInterrupt):
            self.runner.review_baseline_errors(key)
        with patch.object(self.runner, 'score_execution', return_value={'passed': True}):
            review = self.runner.review_baseline_errors(key)
        self.assertTrue(review['complete'])
        self.assertEqual(self.runtime.answers, ['Q1', 'Q1', 'Q2', 'Q2'])
