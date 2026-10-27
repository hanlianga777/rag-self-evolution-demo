"""Offline disposition routing; no review or Provider action is performed."""
import unittest
from app.governance import GovernanceStore


class DispositionTests(unittest.TestCase):
    def test_routes_quality_safety_and_retrieval_without_waiving_them(self):
        route = GovernanceStore.golden_disposition
        self.assertEqual(route([]), 'review')
        self.assertEqual(route(['检索不连贯']), 'review_retrieval_risk')
        self.assertEqual(route(['QC 未通过', '检索不连贯']), 'investigate_and_revalidate')
        self.assertEqual(route(['题目质量需修订']), 'investigate_and_revalidate')
        self.assertEqual(route(['语义/安全争议待复核']), 'resolve_source_or_safety')
        self.assertEqual(route(['质量记录已过期']), 'revalidate')
        self.assertEqual(route(['任意业务审计原因'], {'checks': {'grounding': False}}), 'investigate_and_revalidate')

    def test_business_audit_requires_all_ten_explicit_true_checks(self):
        from app.business_golden import CHECKS, audit_passed
        self.assertTrue(audit_passed({'checks': dict.fromkeys(CHECKS, True)}))
        for checks in ({}, {'grounding': True}, {**dict.fromkeys(CHECKS, True), 'extra': True},
                       {**dict.fromkeys(CHECKS, True), 'grounding': 1},
                       {**dict.fromkeys(CHECKS, True), 'grounding': False}):
            with self.subTest(checks=checks):
                self.assertFalse(audit_passed({'checks': checks}))
                self.assertEqual(GovernanceStore.golden_disposition([], {'checks': checks}), 'investigate_and_revalidate')
