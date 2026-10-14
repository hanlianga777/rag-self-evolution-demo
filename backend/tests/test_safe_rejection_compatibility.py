"""Saved answer/Judge replay only; never calls Provider or opens the active DB."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from copy import deepcopy

_isolation = tempfile.TemporaryDirectory()
for _key, _leaf in [('RAG_DEMO_DB_PATH', 'demo.db'), ('RAG_DEMO_ENV_PATH', 'missing.env'), ('RAG_DEMO_INDEX_DIR', 'index'), ('RAG_DEMO_DOCUMENTS_DIR', 'documents'), ('RAG_DEMO_UPLOADS_DIR', 'uploads')]:
    os.environ.setdefault(_key, str(Path(_isolation.name) / _leaf))

from app.evaluation_contract import assess_claims, abstention_valid, evaluation_identity, VERSIONS


class SafeRejectionCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.saved = json.loads((Path(__file__).parent / 'fixtures/safe_rejection_saved_case.json').read_text())

    def assess(self):
        s = self.saved
        return assess_claims(s['answer'], s['judge'], s['entries'], item=s['item'])

    def test_saved_real_refusal_accepts_only_after_full_grounded_audit(self):
        before = deepcopy(self.saved)
        result = self.assess()
        self.assertEqual(len(result['accepted']), 5)
        self.assertFalse(result['confirmed'] or result['pending'])
        self.assertEqual(self.saved, before)
        self.assertEqual([self.saved['judge'][k] for k in ['correctness', 'faithfulness', 'completeness', 'behavior_pass']], [4, 1, 1, True])

    def test_safe_rejection_enum_alone_cannot_waive_an_abstention(self):
        self.saved['judge']['unsupported_claims'] = self.saved['judge']['unsupported_claims'][3:4]
        review = self.saved['judge']['claim_reviews'][3]
        review['unsupported_claim_index'] = 0
        self.saved['judge']['claim_reviews'] = [review]
        self.assertTrue(self.assess()['pending'])

    def test_ignored_safety_or_extra_operation_never_gets_accepted(self):
        original = deepcopy(self.saved)
        for field in ['evidence_ignored', 'capability_absence_asserted', 'new_technical_operation']:
            with self.subTest(field=field):
                self.saved = deepcopy(original)
                self.saved['judge']['claim_reviews'][3]['abstention_basis'][field] = True
                self.assertTrue(self.assess()['pending'])

    def test_behavior_mismatch_positive_or_different_negative_type_stays_pending(self):
        original = deepcopy(self.saved)
        for mode in ['failed_behavior', 'positive', 'subtype_conflict']:
            with self.subTest(mode=mode):
                self.saved = deepcopy(original)
                if mode == 'failed_behavior': self.saved['judge']['behavior_pass'] = False
                elif mode == 'positive': self.saved['item']['test_category'] = 'positive'
                else: self.saved['item']['negative_subtype'] = 'insufficient_evidence'
                self.assertTrue(self.assess()['pending'])

    def test_missing_or_unlocated_safety_basis_is_not_grounded_refusal(self):
        original = deepcopy(self.saved)
        for mode in ['wrong_quote', 'missing_support', 'wrong_answer', 'wrong_scope', 'missing_chunk', 'inapplicable']:
            with self.subTest(mode=mode):
                self.saved = deepcopy(original)
                j = self.saved['judge']; review = j['claim_reviews'][1]
                if mode == 'wrong_quote': review['support'][0]['quote'] = '允许用高压水枪'
                elif mode == 'missing_support': review['support'] = []
                elif mode == 'wrong_answer': review['claim'] = '未出现的拒答'
                elif mode == 'wrong_scope': j['claim_reviews'][3]['abstention_basis']['scope'] = 'whole_corpus'
                elif mode == 'missing_chunk': j['claim_reviews'][3]['abstention_basis']['checked_chunk_ids'].pop()
                else: review['operation_basis']['source_applicable'] = False
                self.assertTrue(self.assess()['pending'])

    def test_refusal_does_not_hide_unsourced_repair_or_unsafe_exception(self):
        original = deepcopy(self.saved)
        for kind, basis in [('unsupported_instruction', {'effect': 'technical_change', 'source_applicable': False}), ('contradiction', {'effect': 'none', 'source_applicable': True})]:
            with self.subTest(kind=kind):
                self.saved = deepcopy(original)
                r = self.saved['judge']['claim_reviews'][2]
                r.update(kind=kind, operation_basis=basis, changes_operation=basis['effect'] == 'technical_change')
                result = self.assess()
                self.assertTrue(result['confirmed'])
                self.assertTrue(any(r['kind'] == 'supported_abstention' for r in result['pending']))

    def test_duplicate_or_unreviewed_claim_cannot_supply_compatibility(self):
        original = deepcopy(self.saved)
        for mode in ['unreviewed', 'duplicate']:
            self.saved = deepcopy(original)
            if mode == 'unreviewed': self.saved['judge']['unsupported_claims'].append('未审核操作')
            else: self.saved['judge']['claim_reviews'].append(deepcopy(self.saved['judge']['claim_reviews'][0]))
            self.assertTrue(self.assess()['pending'])

    def test_changed_semantics_change_identity_and_require_actual_answer(self):
        old = {**VERSIONS, 'evidence_matcher_version': 'evidence-v5-claim-scope', 'scoring_policy': 'v1.4-governance-outcomes'}
        self.assertNotEqual(evaluation_identity({'id': 'frozen'}, old), evaluation_identity({'id': 'frozen'}, VERSIONS))
        s = self.saved
        self.assertFalse(abstention_valid(s['judge']['claim_reviews'][3], s['judge'], s['entries'], s['item']))
