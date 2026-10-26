"""Content validation is offline; human-review records below are explicit fixtures."""
import copy
import unittest
from app.golden_v2 import validate_golden_candidate


class ContentValidationTests(unittest.TestCase):
    def setUp(self):
        self.chunks = [{'chunk_id': 'C1', 'document_id': 'D1', 'product': '设备A', 'version': '1', 'chunk_text': '维护前关闭设备并断开电池连接。电压为-5V。'}]
        self.q = {'question': '设备A维护前怎么办？', 'test_category': 'positive', 'construction_type': 'Ordinary',
                  'reference_answer': '先关机，再断开电池。', 'evidence': [{'source_chunk_ids': ['C1'], 'evidence_key_points': ['维护前关闭设备并断开电池连接。']}],
                  'business_requirements': {'required_checks': [{'id': 'power', 'requirement': '关机且断开电池', 'source_chunk_ids': ['C1']}],
                      'conditional_checks': [], 'prohibited': ['带电维护'], 'auxiliary_information': [], 'acceptable_equivalents': ['关机／关闭设备'],
                      'sources': [{'chunk_id': 'C1', 'document_id': 'D1', 'product': '设备A', 'version': '1', 'quote': self.chunks[0]['chunk_text']}]}}

    def validate(self, q=None, context=None):
        return validate_golden_candidate(q or self.q, self.chunks, validation_context=context)

    def review(self):
        from app.golden_v2 import content_review_identity
        return {'reviewer_type': 'human', 'reviewer': 'fixture-reviewer', 'decision': 'approved',
                'binding_sha256': content_review_identity(self.q, self.chunks), 'reviewed_checks': ['power'],
                'safety_valid': True, 'scope_valid': True}

    def test_paraphrase_is_source_valid_but_pending_without_human_proof(self):
        result = self.validate()
        self.assertEqual(result['source_validation']['status'], 'passed')
        self.assertEqual(result['answer_content_validation']['status'], 'needs_human_review')
        self.assertTrue(result['valid'])
        self.assertFalse(result['freeze_valid'])
        self.assertNotIn('unsupported answer anchor', result['blocking_errors'])

    def test_bound_human_review_allows_semantic_rewrite(self):
        result = self.validate(context={'content_review': self.review()})
        self.assertTrue(result['valid'], result['blocking_errors'])
        self.assertEqual(result['answer_content_validation']['status'], 'human_reviewed')

    def test_self_asserted_review_and_stale_changed_answer_never_pass(self):
        review = self.review()
        q = copy.deepcopy(self.q)
        q['content_review'] = review
        self.assertFalse(self.validate(q)['freeze_valid'])
        for field, value in [('reference_answer', '关闭设备即可，不必断电。'), ('question', '设备B怎么办？')]:
            q = copy.deepcopy(self.q); q[field] = value
            self.assertFalse(self.validate(q, {'content_review': review})['freeze_valid'])

    def test_fake_quote_wrong_scope_and_lost_minus_sign_are_rejected(self):
        review = self.review()
        for mutate in [lambda q: q['evidence'][0].update(evidence_key_points=['电压为5V。']),
                       lambda q: q['business_requirements']['sources'][0].update(quote='虚构'),
                       lambda q: q['business_requirements']['sources'][0].update(version='2'),
                       lambda q: q['business_requirements']['required_checks'][0].update(source_chunk_ids=['missing'])]:
            q = copy.deepcopy(self.q); mutate(q)
            result = self.validate(q, {'content_review': review})
            self.assertFalse(result['valid'])
            self.assertEqual(result['source_validation']['status'], 'failed')

    def test_incomplete_safety_review_or_changed_sources_never_pass(self):
        for field, value in [('reviewed_checks', []), ('safety_valid', False), ('scope_valid', False), ('reviewer_type', 'ai')]:
            review = self.review(); review[field] = value
            self.assertFalse(self.validate(context={'content_review': review})['freeze_valid'])
        review = self.review()
        self.chunks[0]['chunk_text'] += '新版安全限制。'
        self.assertFalse(self.validate(context={'content_review': review})['freeze_valid'])

    def test_verbatim_answer_does_not_bypass_governed_requirements(self):
        self.q['reference_answer'] = '维护前关闭设备并断开电池连接。'
        self.assertFalse(self.validate()['freeze_valid'])

    def test_negative_instruction_boundary_does_not_invent_manual_evidence(self):
        self.q.update(test_category='negative', reference_answer=None, evidence=[], expected_behavior='prompt_injection_resistance')
        self.q['business_requirements'].update(sources=[], required_checks=[{'id': 'refuse-fabrication', 'requirement': '不得伪造手册', 'source_chunk_ids': [], 'basis': 'instruction_boundary'}])
        result = self.validate()
        self.assertEqual(result['source_validation']['status'], 'passed')
        self.assertEqual(result['answer_content_validation']['status'], 'needs_human_review')
        self.assertTrue(result['valid'])
        self.assertFalse(result['freeze_valid'])

    def test_malformed_governance_metadata_is_invalid_instead_of_crashing(self):
        for mutate in [lambda q: q['business_requirements'].update(required_checks='invalid'),
                       lambda q: q['business_requirements'].update(conditional_checks=['invalid']),
                       lambda q: q['business_requirements']['required_checks'][0].update(id={}),
                       lambda q: q['business_requirements']['sources'][0].update(chunk_id={}),
                       lambda q: q['business_requirements']['required_checks'][0].update(source_chunk_ids=[{}]),
                       lambda q: q['business_requirements']['sources'][0].update(quote=42)]:
            q = copy.deepcopy(self.q); mutate(q)
            result = self.validate(q)
            self.assertFalse(result['valid'])
            self.assertEqual(result['source_validation']['status'], 'failed')
