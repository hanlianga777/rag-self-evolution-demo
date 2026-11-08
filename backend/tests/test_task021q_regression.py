import json
import tempfile
import unittest
from pathlib import Path

from app.governance import GovernanceStore
from app.policy import evaluate_regression, qualify_candidate


class RegressionLimitTests(unittest.TestCase):
    def test_ordinary_over_limit_fails_even_when_more_cases_are_fixed(self):
        regression = evaluate_regression(new_critical_failures=0, new_ordinary_failures=3)
        self.assertFalse(regression['passed'])
        self.assertEqual(regression['limits'], {'critical': 0, 'ordinary': 1})
        self.assertEqual(regression['checks'], {'critical': True, 'ordinary': False})
        self.assertFalse(qualify_candidate({'passed': True}, regression, 4, 6, 5)['qualified'])
        self.assertTrue(evaluate_regression(new_critical_failures=0, new_ordinary_failures=1)['passed'])
        self.assertFalse(evaluate_regression(new_critical_failures=1, new_ordinary_failures=0)['passed'])
        self.assertEqual(evaluate_regression(new_critical_failures=0, new_ordinary_failures=None)['status'], 'NOT_EVALUABLE')

    def test_read_projection_recalculates_without_overwriting_saved_results(self):
        with tempfile.TemporaryDirectory() as directory:
            store = GovernanceStore(Path(directory) / 'isolated.db')
            questions = [{'id': q} for q in ['Q13', 'Q30', 'Q37', 'fixed']]
            snapshot = json.dumps({'questions': questions})
            saved = {'evaluation_run_id': 'candidate-run', 'baseline_run_id': 'baseline',
                     'evaluation_complete': True, 'regression': {'passed': True, 'status': 'PASS', 'limits': {'critical': 0, 'ordinary': None}},
                     'qualification': {'qualified': False}, 'release_qualification': {'qualified': False}}
            with store.connection() as c:
                for run in ['baseline', 'candidate-run']:
                    c.execute('INSERT INTO evaluation_runs VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                              (run, 'completed', 'real', 'real', 'golden', snapshot, '{}', '{"evaluation_identity":"same"}', '{}', None, 'now', 'now'))
                for q in ['Q13', 'Q30', 'Q37', 'fixed']:
                    for run in ['baseline', 'candidate-run']:
                        case = {'passed': (q == 'fixed') == (run == 'candidate-run'), 'severity': 'ordinary' if run == 'baseline' else 'critical'}
                        c.execute('INSERT INTO evaluation_case_results(run_id,question_id,result_json) VALUES (?,?,?)', (run, q, json.dumps(case)))
                c.execute('INSERT INTO experiments VALUES (?,?,?,?,?)', ('exp', 'baseline', 'completed', '{}', 'now'))
                c.execute('INSERT INTO candidate_configs VALUES (?,?,?,?,?,?,?)', ('exp-R3-A', 'exp', 'evaluated', '{}', '{"round":3,"candidate_label":"A"}', json.dumps(saved), 'now'))
                before = c.execute('SELECT result_json FROM candidate_configs').fetchone()[0]
            for result in [store.candidate('exp-R3-A')['result'], store.candidates('exp', light=True)[0]['result'], store.experiment('exp', light=True)['candidates'][0]['result']]:
                review = result['regression_review']
                self.assertEqual(review['status'], 'FAIL')
                self.assertEqual(review['new_ordinary_failures'], 3)
                self.assertEqual(review['new_critical_failures'], 0)
                self.assertEqual(review['case_severities'], {'Q13': 'ordinary', 'Q30': 'ordinary', 'Q37': 'ordinary'})
                self.assertEqual(review['fixed_count'], 1)
                self.assertEqual(result['regression'], saved['regression'])
                self.assertEqual(result['release_qualification'], saved['release_qualification'])
            with store.connection() as c:
                self.assertEqual(c.execute('SELECT result_json FROM candidate_configs').fetchone()[0], before)
                questions[0]['negative_subtype'] = 'prompt_injection'
                c.execute('UPDATE evaluation_runs SET dataset_snapshot_json=? WHERE id=?', (json.dumps({'questions': questions}), 'baseline'))
            review = store.candidate('exp-R3-A')['result']['regression_review']
            self.assertEqual(review['new_critical_failures'], 1)
            self.assertEqual(review['case_severities']['Q13'], 'critical')
            self.assertFalse(review['checks']['critical'])
            with store.connection() as c:
                c.execute("UPDATE evaluation_runs SET status='partial' WHERE id='candidate-run'")
            review = store.candidate('exp-R3-A')['result']['regression_review']
            self.assertEqual(review['status'], 'NOT_EVALUABLE')
            self.assertIsNone(review['new_ordinary_failures'])
