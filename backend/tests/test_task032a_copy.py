"""Presentation copy must not change the search-space contract; no DB/provider."""
import unittest
from app.policy import ALLOWED_SEARCH_SPACE, PARAMETER_EXPLANATIONS, search_space_contract

class ParameterCopyTest(unittest.TestCase):
    def test_parameter_copy_covers_each_unchanged_option(self):
        contract = search_space_contract()
        self.assertEqual(len(PARAMETER_EXPLANATIONS), 12)
        for key, allowed in ALLOWED_SEARCH_SPACE.items():
            description, options = PARAMETER_EXPLANATIONS[key]
            self.assertEqual(len(options), len(allowed))
            self.assertEqual(contract[key]['allowed'], list(allowed))
            self.assertEqual([option['value'] for option in contract[key]['options']], list(allowed))
            self.assertTrue(all('。；' not in text and '；。' not in text for text in [description, *options]))
        self.assertIn('相关分低于这条线的资料直接丢掉', contract['min_score']['description'])
        self.assertEqual(contract['prompt_strategy']['allowed'], ['Grounded', 'Completeness', 'Tiered'])
