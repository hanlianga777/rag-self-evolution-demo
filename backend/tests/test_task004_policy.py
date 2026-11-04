import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from app import policy
from app.followups import FollowupJobs


class Task004PolicyTests(unittest.TestCase):
    def test_abc_allows_many_ordinary_regressions_but_needs_net_target_improvement(self):
        regression = policy.evaluate_regression(new_critical_failures=0, new_ordinary_failures=3)
        self.assertTrue(regression['passed'])
        self.assertTrue(policy.qualify_candidate({'passed': True}, regression, 4, 6, 5)['qualified'])
        self.assertFalse(policy.qualify_candidate({'passed': True}, regression, 0, 6, 5)['qualified'])
        self.assertFalse(policy.qualify_candidate({'passed': True}, regression, 4, 6, 6)['qualified'])
        self.assertFalse(policy.evaluate_regression(new_critical_failures=1, new_ordinary_failures=0)['passed'])

    def test_final_requires_zero_regressions_and_keeps_least_wrong_abc(self):
        regression = policy.evaluate_regression(new_critical_failures=0, new_ordinary_failures=1)
        self.assertFalse(policy.qualify_release({'passed': True}, regression, 2)['qualified'])
        self.assertTrue(policy.qualify_release({'passed': True}, policy.evaluate_regression(new_critical_failures=0, new_ordinary_failures=0), 1)['qualified'])
        self.assertFalse(policy.qualify_release({'passed': False}, regression, 2)['qualified'])
        rows = [{'id': label, 'status': 'evaluated', 'reasoning': {'candidate_label': label}, 'result': {'bad_case_count': count, 'qualification': {'qualified': True}}} for label, count in [('A', 4), ('B', 2), ('C', 3)]]
        self.assertEqual(policy.select_final_candidate(rows)['candidate_id'], 'B')
        self.assertEqual(policy.select_final_candidate([*rows, {'id': 'missing', 'status': 'evaluated', 'reasoning': {'candidate_label': 'A'}, 'result': {'qualification': {'qualified': True}, 'bad_case_count': None}}])['candidate_id'], 'B')
        self.assertEqual(policy.select_final_candidate([])['decision'], '保持 Baseline')
        self.assertEqual(policy.select_final_candidate(rows, {'id': 'D', 'status': 'failed', 'result': {'release_qualification': {'qualified': True}}})['candidate_id'], 'B')
        self.assertEqual(policy.select_final_candidate(rows, {'id': 'D', 'status': 'evaluated', 'result': {'release_qualification': {'qualified': True}}})['decision'], '发布合格')

    def test_review_request_is_disabled_without_new_answers_or_judgments(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = Mock()
            jobs = FollowupJobs(SimpleNamespace(database_path=Path(directory) / 'isolated.db'), runtime)
            for _ in range(2):
                with self.assertRaisesRegex(ValueError, '以单遍结果为准，已关闭错题复核'):
                    jobs.start('run', 'review')
            self.assertFalse(jobs.root.exists())
            self.assertEqual(jobs.threads, {})
            runtime.answer.assert_not_called()
            runtime.judge.assert_not_called()

    def test_restart_preserves_unknown_review_history_without_resuming(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = Mock()
            jobs = FollowupJobs(SimpleNamespace(database_path=Path(directory) / 'isolated.db'), runtime)
            path = jobs.path('run', 'review')
            path.parent.mkdir(parents=True)
            history = {'_job': {'status': 'running'}, 'cases': {'q': {'regression_review': {'runs': [
                {'attempts': [{'phase': 'generation', 'status': 'error', 'request_execution_unknown': True}]}
            ]}}}}
            path.write_text(json.dumps(history))
            for _ in range(2):
                jobs.recover()
                with self.assertRaisesRegex(ValueError, '已关闭错题复核'):
                    jobs.start('run', 'review')
            self.assertEqual(json.loads(path.read_text()), history)
            self.assertEqual(jobs.threads, {})
            runtime.answer.assert_not_called()
            runtime.judge.assert_not_called()

class Task004ComparisonTests(unittest.TestCase):
    def test_injection_is_critical_and_historical_fluctuation_counts_as_single_pass_failure(self):
        from app.evaluation import candidate_comparison
        baseline = {'q': {'passed': True, 'severity': 'ordinary', 'negative_subtype': 'prompt_injection'}, 'f': {'passed': False}, 'n': {'passed': True}}
        candidate = {'q': {'passed': False, 'severity': 'ordinary', 'negative_subtype': 'prompt_injection'}, 'f': {'passed': True}, 'n': {'passed': False, 'regression_review': {'status': 'fluctuation'}}}
        result = candidate_comparison(baseline, candidate, ['f'])
        self.assertEqual(result['new_regression_question_ids'], ['n', 'q'])
        self.assertEqual(result['fluctuation_question_ids'], [])
        self.assertEqual(result['new_critical_failures'], 1)
        self.assertEqual(result['new_ordinary_failures'], 1)
        self.assertEqual(result['bad_case_count'], 2)
        self.assertEqual(result['target_bad_cases_fixed'], 1)
        ordinary = candidate_comparison({'q': {'passed': True, 'severity': 'ordinary'}}, {'q': {'passed': False, 'severity': 'critical', 'judge_result': {'issues': [{'critical': True}]}}}, [])
        self.assertEqual(ordinary['new_critical_failures'], 0)
        self.assertEqual(ordinary['new_ordinary_failures'], 1)

class Task004CandidateIntegrationTests(unittest.TestCase):
    def setUp(self):
        import test_baseline_resume as fixture
        fixture.ResumeTests.setUp(self)
        self.runtime.fail = None

    def tearDown(self):
        self.tmp.cleanup()

    def test_candidate_scores_once_and_keeps_initial_failure_record(self):
        original = self.runner.score_execution
        def baseline_score(item, execution, **kwargs):
            result = original(item, execution, **kwargs)
            result['passed'] = item['id'] != 'Q1'
            return result
        self.runner.score_execution = baseline_score
        baseline = self.runner.execute_baseline(*self.runner.start_baseline())
        self.assertEqual(baseline['status'], 'completed')
        exp = self.store.create_experiment(baseline['id'], 'completed')
        config = {**policy.DEFAULT_PIPELINE_CONFIG, 'top_k': 6}
        self.store.save_candidate(exp, 'R1-A', config, {'round': 1, 'candidate_label': 'A', 'observed_evidence': ['Q1']})
        counts = {}
        def candidate_score(item, execution, **kwargs):
            result = original(item, execution, **kwargs)
            counts[item['id']] = counts.get(item['id'], 0) + 1
            result['passed'] = item['id'] != 'Q2' or counts[item['id']] > 1
            return result
        self.runner.score_execution = candidate_score
        self.runtime.answers.clear()
        self.runtime.judges.clear()
        result = self.runner.execute_candidate(*self.runner.start_candidate(exp + '-R1-A'))
        self.assertEqual(result['status'], 'evaluated')
        self.assertFalse(result['result']['qualification']['qualified'])
        self.assertEqual(result['result']['bad_case_count'], 1)
        self.assertEqual(result['result']['initial_bad_case_count'], 1)
        self.assertEqual(result['result']['new_regressions'], 1)
        self.assertEqual(result['result']['new_regression_question_ids'], ['Q2'])
        self.assertEqual(result['result']['fluctuation_question_ids'], [])
        self.assertEqual(counts, {'Q1': 1, 'Q2': 1, 'Q3': 1, 'Q4': 1})
        self.assertEqual(self.runtime.answers, ['Q1', 'Q2', 'Q3', 'Q4'])
        self.assertEqual(self.runtime.judges, ['Q1', 'Q2', 'Q3', 'Q4'])
        saved = self.store.evaluation_case_result(result['result']['evaluation_run_id'], 'Q2')
        self.assertFalse(saved['passed'])
        self.assertNotIn('regression_review', saved)
        self.assertEqual(result['result']['request_accounting']['call_events'], 8)
