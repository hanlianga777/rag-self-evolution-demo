"""Agent format compatibility without changing saved-evidence or policy rules."""
import copy
import unittest

from app.optimization import validate_prior_round_review
import test_optimization_contract as contract


class AgentTypeTests(unittest.TestCase):
    setUp = contract.OptimizationContractTests.setUp
    run_drafts = contract.OptimizationContractTests.run_drafts

    def saved_review(self):
        experiment, trace, _, _, _ = self.run_drafts(contract.drafts())
        self.assertEqual(trace['status'], 'completed')
        for candidate in experiment['candidates']:
            self.store.finish_candidate(candidate['id'], 'evaluated', {
                'all_fixed_question_ids': ['Q1'], 'new_regression_question_ids': ['Q2']})
        prior = self.store.experiment(experiment['id'])['candidates']
        response = contract.drafts()
        response['prior_round_review']['plans'] = [{
            'candidate_id': c['id'], 'changes': '调整参数',
            'fixed_question_ids': ['Q1'], 'new_failure_question_ids': ['Q2'],
            'evidence_reason': '保存的逐题结果', 'conclusion': '无法单独归因',
        } for c in prior]
        return response, prior

    def test_changes_accepts_nonempty_string_or_object(self):
        response, prior = self.saved_review()
        for value in ('调整候选数', {'candidate_k': 24, 'multi_query': 2}):
            with self.subTest(changes=value):
                for plan in response['prior_round_review']['plans']:
                    plan['changes'] = value
                validate_prior_round_review(response, prior)

    def test_empty_or_missing_changes_still_rejected(self):
        response, prior = self.saved_review()
        for value in ('', '  ', {}, None, [], 24):
            with self.subTest(changes=value):
                invalid = copy.deepcopy(response)
                invalid['prior_round_review']['plans'][0]['changes'] = value
                with self.assertRaisesRegex(ValueError, '复盘'):
                    validate_prior_round_review(invalid, prior)
        del response['prior_round_review']['plans'][0]['changes']
        with self.assertRaisesRegex(ValueError, '复盘'):
            validate_prior_round_review(response, prior)

    def test_saved_ids_lists_and_conclusion_references_still_required(self):
        response, prior = self.saved_review()
        for field, value in (('fixed_question_ids', 'Q1'),
                             ('fixed_question_ids', ['invented']),
                             ('new_failure_question_ids', []),
                             ('evidence_reason', {}), ('conclusion', {})):
            with self.subTest(field=field, value=value):
                invalid = copy.deepcopy(response)
                invalid['prior_round_review']['plans'][0][field] = value
                with self.assertRaises(ValueError):
                    validate_prior_round_review(invalid, prior)
        response['candidates'][0]['review_conclusion_ids'] = ['invented']
        with self.assertRaisesRegex(ValueError, '引用'):
            validate_prior_round_review(response, prior)

    def test_proposal_numeric_strings_and_single_target_are_normalized(self):
        response = contract.drafts()
        response['candidates'][0].update(config_diff={'top_k': '6'}, target_bad_cases='Q1',
            adjustments=[{'parameter': 'top_k', 'baseline_value': '4',
                          'candidate_value': '6', 'expected_impact': '预计修好Q1'}],
            risks=[{'question_ids': 'Q2', 'reason': '可能减少其他题证据'}])
        experiment, trace, audit, _, raw = self.run_drafts(response)
        self.assertEqual(trace['status'], 'completed', audit.get('validation_error'))
        self.assertEqual(experiment['candidates'][0]['config']['top_k'], 6)
        self.assertEqual(experiment['candidates'][0]['reasoning']['observed_evidence'], ['Q1'])
        self.assertEqual(audit['provider_raw_text'], raw)
        self.assertEqual(audit['parsed_json']['candidates'][0]['config_diff']['top_k'], '6')

    def test_normalization_keeps_search_space_and_round_rules(self):
        for diff, reason in (({'top_k': '8'}, 'Search Space'),
                             ({'top_k': 'true'}, 'Search Space'),
                             ({'top_k': '6', 'min_score': '0.1'}, '共用参数'),
                             ({'top_k': '6', 'generation_thinking': 'low'}, '不得降低Thinking')):
            with self.subTest(diff=diff):
                response = contract.drafts()
                response['candidates'][0]['config_diff'] = diff
                experiment, trace, audit, _, _ = self.run_drafts(response)
                self.assertEqual(trace['status'], 'analysis_exhausted')
                self.assertEqual(experiment['candidates'], [])
                self.assertIn(reason, audit['validation_error'])


if __name__ == '__main__':
    unittest.main()
