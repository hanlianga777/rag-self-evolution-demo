"""Offline regression for frozen negative behavior at Baseline preflight."""
import unittest
from app.evaluation import EvaluationRunner
from app.canonical_evidence import optimization_preflight


class FrozenBehaviorPreflightTests(unittest.TestCase):
    def test_preflight_uses_frozen_behavior_and_rejects_missing_or_invalid(self):
        class Store:
            def question(self, key):
                return {'id': key, 'test_category': 'negative', 'raw': {}}
        runner = EvaluationRunner(Store(), None)
        for behavior in ('safe_rejection', 'insufficient_evidence', 'clarify', 'prompt_injection_resistance', None, 'invalid'):
            with self.subTest(behavior=behavior):
                frozen = {'id': 'Q', 'question': 'Q', 'test_category': 'negative', 'evidence': []}
                if behavior is not None:
                    frozen['expected_behavior'] = behavior
                item = runner.snapshot_items({'question_ids': ['Q'], 'questions': [frozen]})[0]
                self.assertEqual(optimization_preflight(item, [])['ready'], behavior not in (None, 'invalid'))

        class StaleStore:
            def question(self, key):
                return {'id': key, 'test_category': 'negative', 'expected_behavior': 'safe_rejection', 'raw': {}}
        item = EvaluationRunner(StaleStore(), None).snapshot_items({'question_ids': ['Q'], 'questions': [{'id': 'Q', 'question': 'Q', 'test_category': 'negative'}]})[0]
        self.assertFalse(optimization_preflight(item, [])['ready'])
