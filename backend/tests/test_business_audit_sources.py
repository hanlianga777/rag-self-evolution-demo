"""Business audit input scope uses current Child assets without retrieval or Provider I/O."""
import copy
import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.ai_service import AiService
from app.business_golden import CHECKS


class BusinessAuditSourceTests(unittest.TestCase):
    def setUp(self):
        self.children = [
            {'chunk_id': 'ANCHOR', 'document_id': 'D1', 'product': 'KIRA B 50', 'parent_chunk_id': 'P1', 'chunk_text': '使用湿布擦拭外壳。'},
            {'chunk_id': 'BOUNDARY', 'document_id': 'D1', 'product': 'KIRA B 50', 'parent_chunk_id': 'P2', 'chunk_text': '不得使用高压水射流清洁设备。'},
            {'chunk_id': 'OTHER_TOPIC_DOCUMENT', 'document_id': 'D2', 'product': '其他设备', 'parent_chunk_id': 'P3', 'chunk_text': '其他型号的真实操作限制。'},
            {'chunk_id': 'CHAPTER', 'document_id': 'D1', 'product': 'KIRA B 50', 'parent_chunk_id': 'P1', 'chunk_text': '保养维护章节。'},
            {'chunk_id': 'VERSION', 'document_id': 'D1', 'product': 'KIRA B 50', 'parent_chunk_id': 'P0', 'chunk_text': '修订历史：正式资料。'},
        ]
        self.manifest = patch('app.ai_service.current_manifest', return_value={'sources': {'D1': 'fixture-sha', 'D2': 'other-fixture-sha'}})
        self.manifest.start()
        self.addCleanup(self.manifest.stop)
        self.service = object.__new__(AiService)
        self.service.corpus = SimpleNamespace(chunks=lambda: copy.deepcopy(self.children))
        self.service.business_parent_context = Mock(side_effect=AssertionError('Parent is not Child evidence'))
        self.service.provider = Mock()
        self.service.provider.complete.return_value = json.dumps({'checks': dict.fromkeys(CHECKS, True), 'reason': 'offline schema fixture', 'difficulty_observed': '中等'})
        self.item = {'question': '可以用高压水枪冲洗整机吗？', 'reference_answer': None, 'test_category': 'negative', 'evidence': [{'source_chunk_ids': ['OLD_DELETED_ASSET']}],
                     'raw': {'coverage_anchor_chunk_ids': ['ANCHOR'],
                             'validation': {'normalized_candidate': {'source_chunk_ids': ['ANCHOR']}},
                             'user_role': '运维人员', 'business_scenario': '清洁机身', 'user_intent': '确认清洁方式',
                             'expected_behavior': 'safe_rejection', 'expected_response': '拒绝高压水枪冲洗整机，并说明资料中的安全限制。',
                             'source_scope': {'chapter_anchor': 'CHAPTER', 'documents': ['D1']}}}

    def payload(self, **kwargs):
        self.result = self.service.business_quality_audit(self.item, [], **kwargs)
        self.assertEqual(self.service.provider.complete.call_count, 1)
        self.service.business_parent_context.assert_not_called()
        return json.loads(self.service.provider.complete.call_args.args[1])

    def test_negative_default_scope_stays_narrow_and_retains_expected_response(self):
        payload = self.payload()
        self.assertEqual({s['chunk_id'] for s in payload['sources']}, {'ANCHOR', 'CHAPTER', 'VERSION'})
        self.assertEqual(payload['metadata']['expected_response'], self.item['raw']['expected_response'])

    def test_explicit_negative_context_only_adds_requested_current_same_product_child(self):
        original = copy.deepcopy(self.item)
        payload = self.payload(context_chunk_ids=('BOUNDARY',))
        self.assertEqual({s['chunk_id'] for s in payload['sources']}, {'ANCHOR', 'BOUNDARY', 'CHAPTER', 'VERSION'})
        self.assertEqual(self.result['audit_source_chunk_ids'], [s['chunk_id'] for s in payload['sources']])
        self.assertEqual(self.result['corpus_fingerprint'], {'D1': 'fixture-sha', 'D2': 'other-fixture-sha'})
        self.assertEqual(self.item, original)
        self.assertNotIn('OLD_DELETED_ASSET', {s['chunk_id'] for s in payload['sources']})

    def test_unknown_other_product_parent_and_excessive_context_fail_before_provider(self):
        for keys in [('OLD_DELETED_ASSET',), ('OTHER_TOPIC_DOCUMENT',), ('P1',), ('ANCHOR', 'BOUNDARY', 'CHAPTER', 'VERSION')]:
            with self.subTest(keys=keys):
                with self.assertRaises(ValueError):
                    self.service.business_quality_audit(self.item, [], context_chunk_ids=keys)
                self.service.provider.complete.assert_not_called()

    def test_answerable_extra_context_is_rejected_before_provider(self):
        for category in ('positive', 'ablation'):
            with self.subTest(category=category):
                self.item['test_category'] = category
                with self.assertRaises(ValueError):
                    self.service.business_quality_audit(self.item, [], context_chunk_ids=('BOUNDARY',))
                self.service.provider.complete.assert_not_called()

    def test_answerable_audit_keeps_evidence_and_existing_scope_additions_only(self):
        for category in ('positive', 'ablation'):
            with self.subTest(category=category):
                self.service.provider.reset_mock()
                self.item.update(test_category=category, reference_answer='使用湿布擦拭外壳。', evidence=[{'source_chunk_ids': ['ANCHOR']}])
                payload = self.payload()
                self.assertEqual({s['chunk_id'] for s in payload['sources']}, {'ANCHOR', 'CHAPTER', 'VERSION'})
                self.assertNotIn('BOUNDARY', {s['chunk_id'] for s in payload['sources']})
                self.assertNotIn('OTHER_TOPIC_DOCUMENT', {s['chunk_id'] for s in payload['sources']})
