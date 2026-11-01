import unittest
from app import policy
from app.evaluation import EvaluationRunner
from app.telemetry import record_usage


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

    def test_review_runs_two_new_answers_and_judges_records_usage_and_majority(self):
        for verdicts, expected in [([True, True], False), ([False, True], True), ([True, False], True), ([False, False], True)]:
            with self.subTest(verdicts=verdicts):
                class Runtime:
                    model = 'fixture'
                    def answer(self, question, config):
                        record_usage({'status': 'ok', 'prompt_tokens': 2, 'completion_tokens': 1})
                        return {'answer': 'new'}
                runner = EvaluationRunner(None, Runtime())
                values = iter(verdicts)
                def score(item, execution):
                    record_usage({'status': 'ok', 'prompt_tokens': 3, 'completion_tokens': 1})
                    return {'passed': next(values)}
                runner.score_execution = score
                checkpoint = {'attempts': []}
                review = runner.review_regression({'id': 'q', 'question': 'Q'}, {'passed': False}, {}, checkpoint, 'run', lambda: None, lambda *_a, **_kw: None)
                self.assertEqual(review['confirmed_regression'], expected)
                self.assertEqual(review['status'], 'confirmed_regression' if expected else 'fluctuation')
                self.assertEqual(review['review_runs'], 2)
                self.assertEqual(review['call_events'], 4)
                self.assertEqual(review['known_input_tokens'], 10)
                # Re-entering a saved review must not regenerate or rejudge.
                self.assertEqual(runner.review_regression({'id': 'q'}, {'passed': False}, {}, checkpoint, 'run', lambda: None, lambda *_a, **_kw: None), review)

    def test_review_unknown_request_keeps_failed_attempts_on_reentry(self):
        class Runtime:
            model = 'fixture'
            calls = 0
            def answer(self, *args):
                self.calls += 1
                error = RuntimeError('unknown request')
                error.request_execution_unknown = True
                raise error
        runner = EvaluationRunner(None, Runtime())
        checkpoint = {'attempts': []}
        # Decision 14 permits reentry after transport uncertainty, preserving history.
        for _ in range(2):
            with self.assertRaisesRegex(RuntimeError, 'unknown request'):
                runner.review_regression({'id': 'q', 'question': 'Q'}, {'passed': False}, {}, checkpoint, 'run', lambda: None, lambda *_a, **_kw: None)
        self.assertEqual(runner.runtime.calls, 2)
        stages = checkpoint['regression_review']['runs']
        self.assertEqual(len(stages), 1)
        self.assertNotIn('execution', stages[0])
        self.assertEqual(len(stages[0]['attempts']), 2)
        self.assertTrue(all(a['request_execution_unknown'] and a['status'] == 'error' for a in stages[0]['attempts']))

class Task004ComparisonTests(unittest.TestCase):
    def test_injection_is_critical_and_fluctuation_not_new_failure(self):
        from app.evaluation import candidate_comparison
        baseline = {'q': {'passed': True, 'severity': 'ordinary', 'negative_subtype': 'prompt_injection'}, 'f': {'passed': False}, 'n': {'passed': True}}
        candidate = {'q': {'passed': False, 'severity': 'ordinary', 'negative_subtype': 'prompt_injection'}, 'f': {'passed': True}, 'n': {'passed': False, 'regression_review': {'status': 'fluctuation'}}}
        result = candidate_comparison(baseline, candidate, ['f'])
        self.assertEqual(result['new_regression_question_ids'], ['q'])
        self.assertEqual(result['fluctuation_question_ids'], ['n'])
        self.assertEqual(result['new_critical_failures'], 1)
        self.assertEqual(result['new_ordinary_failures'], 0)
        self.assertEqual(result['bad_case_count'], 1)
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

    def test_candidate_reviews_before_completion_and_keeps_initial_failure_record(self):
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
        result = self.runner.execute_candidate(*self.runner.start_candidate(exp + '-R1-A'))
        self.assertTrue(result['result']['qualification']['qualified'])
        self.assertEqual(result['result']['bad_case_count'], 0)
        self.assertEqual(result['result']['initial_bad_case_count'], 1)
        self.assertEqual(result['result']['new_regressions'], 0)
        self.assertEqual(result['result']['fluctuation_question_ids'], ['Q2'])
        self.assertEqual(self.runtime.answers.count('Q2'), 3)
        saved = self.store.evaluation_case_result(result['result']['evaluation_run_id'], 'Q2')
        self.assertFalse(saved['passed'])
        self.assertEqual(saved['regression_review']['call_events'], 4)
        self.assertEqual(result['result']['request_accounting']['call_events'], 12)
