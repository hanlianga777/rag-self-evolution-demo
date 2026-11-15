"""D side-effect text/list contracts; Mock provider and disposable databases."""
import unittest
from copy import deepcopy

import test_task021h_composite as prerequisite


class SideEffectFormatTests(unittest.TestCase):
    setUp = prerequisite.PrerequisiteTests.setUp
    result = prerequisite.PrerequisiteTests.result
    replace_case = prerequisite.PrerequisiteTests.replace_case
    refresh_facts = prerequisite.PrerequisiteTests.refresh_facts
    suggestion = prerequisite.PrerequisiteTests.suggestion
    validate = prerequisite.PrerequisiteTests.validate
    provider = prerequisite.PrerequisiteTests.provider
    fields = ('same_premise_evidence', 'different_premise_evidence', 'risk_checklist')

    def test_nonempty_lists_pass_and_are_saved_unchanged(self):
        value = self.suggestion()
        side = value['changes'][0]['side_effect_check']
        for field in self.fields:
            side[field] = ['未观察到', ' 核对保护题与临界门槛 ']
        original = deepcopy(value)
        provider = self.provider(value)
        candidate = self.store.create_composite(self.experiment, provider)
        self.assertEqual(candidate['status'], 'generated', candidate)
        self.assertEqual(candidate['reasoning']['changes'][0]['side_effect_check'], side)
        decision = self.store.experiment(self.experiment)['result']['composite']
        self.assertEqual(decision['suggestion'], original)
        self.assertEqual(decision['attempts'][0]['parsed_json'], original)
        prompt = provider.complete.call_args.args[0]
        for field in self.fields:
            self.assertIn(field + ':字符串或字符串数组均可', prompt)
        self.assertIn("没有证据写'未观察到'", prompt)
        provider.complete.assert_called_once()

    def test_invalid_values_and_missing_fields_name_the_field(self):
        for field in self.fields:
            for invalid in ([], [''], ['有效', '  '], ['有效', 1], '', '  ', None, {}, 1):
                with self.subTest(field=field, invalid=invalid):
                    value = self.suggestion()
                    value['changes'][0]['side_effect_check'][field] = invalid
                    with self.assertRaisesRegex(ValueError, 'side_effect_check.' + field + ' 须为非空字符串或字符串数组'):
                        self.validate(value)
            value = self.suggestion()
            del value['changes'][0]['side_effect_check'][field]
            with self.subTest(missing=field), self.assertRaisesRegex(ValueError, 'side_effect_check.' + field):
                self.validate(value)

    def test_strings_still_pass_unchanged(self):
        value = self.suggestion()
        self.assertEqual(self.validate(value)[1], value['changes'])

    def test_old_facts_do_not_require_the_three_fields(self):
        self.facts['version'] = 'winner-refinement-1'
        value = self.suggestion()
        for field in self.fields:
            del value['changes'][0]['side_effect_check'][field]
        self.assertEqual(self.validate(value)[1], value['changes'])

    def test_existing_required_fields_still_reject_lists(self):
        for field in ('historical_effects', 'winner_fixed_risk', 'gate_risk', 'mitigation'):
            value = self.suggestion()
            value['changes'][0]['side_effect_check'][field] = ['有效']
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, '改动缺副作用检查'):
                self.validate(value)

    def test_failed_decision_is_archived_and_success_is_reused(self):
        invalid = self.suggestion()
        invalid['changes'][0]['side_effect_check']['risk_checklist'] = []
        failed = self.store.create_composite(self.experiment, self.provider(*[invalid] * 3))
        self.assertEqual(failed['provider_calls'], 3)
        self.assertTrue(all('side_effect_check.risk_checklist' in a['validation_error'] for a in failed['attempts']))
        confirmation = deepcopy(self.store.experiment(self.experiment)['result']['report_confirmation'])
        good = self.suggestion()
        good['changes'][0]['side_effect_check']['risk_checklist'] = ['核对保护题', '核对门槛']
        provider = self.provider(good)
        candidate = self.store.create_composite(self.experiment, provider)
        self.assertEqual(candidate['status'], 'generated', candidate)
        state = self.store.experiment(self.experiment)['result']
        self.assertEqual(state['composite']['previous_failures'], [failed])
        self.assertEqual(state['report_confirmation'], confirmation)
        self.assertEqual(self.store.create_composite(self.experiment, provider)['id'], candidate['id'])
        provider.complete.assert_called_once()
