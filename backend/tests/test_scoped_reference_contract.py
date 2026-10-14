"""Synthetic contract checks only: one mocked Judge, no Provider or active DB."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from copy import deepcopy
from unittest.mock import patch

_isolation = tempfile.TemporaryDirectory()
for _key, _leaf in [('RAG_DEMO_DB_PATH', 'demo.db'), ('RAG_DEMO_ENV_PATH', 'missing.env'), ('RAG_DEMO_INDEX_DIR', 'index'), ('RAG_DEMO_DOCUMENTS_DIR', 'documents'), ('RAG_DEMO_UPLOADS_DIR', 'uploads')]:
    os.environ.setdefault(_key, str(Path(_isolation.name) / _leaf))

from app.config import Settings
from app.evaluation_contract import assess_claims, evaluation_identity, VERSIONS
from app.providers import DeepSeekProvider, ProviderInvalidResponse


class ScopedReferenceContractTests(unittest.TestCase):
    def setUp(self):
        self.answer = '当前任务按规定完成。后续结束路线时：关闭清洁功能。'
        self.entries = [{'chunk_id': 'route', 'content': '结束路线时：关闭清洁功能。', 'document_id': 'manual', 'metadata': {'product': 'device', 'version': '1.0'}}]
        self.item = {'test_category': 'positive', 'raw': {'source_document_id': 'manual', 'product': 'device', 'version': '1.0'}}
        self.review = {'unsupported_claim_index': 0, 'claim': '后续结束路线时：关闭清洁功能。',
            'kind': 'scoped_reference', 'changes_operation': False, 'critical': False, 'reason': '保留来源流程条件的参考资料',
            'operation_basis': {'effect': 'none', 'source_applicable': False},
            'scope_basis': {'answer_scope_quote': '后续结束路线时：', 'source_scope': {'chunk_id': 'route', 'quote': '结束路线时：'},
                'requested_workflow_applicable': False, 'authorizes_operation': False, 'evidence_ignored': False, 'source_identity_matches': True},
            'support': [{'chunk_id': 'route', 'quote': '关闭清洁功能。'}]}
        self.judge = {'correctness': 4, 'completeness': 1, 'faithfulness': 1, 'behavior_pass': True, 'behavior_evidence': '',
            'reason': '离线构造', 'missing_points': [], 'unsupported_claims': [self.review['claim']], 'claim_reviews': [self.review],
            'evidence_sufficiency': {'status': 'unknown', 'fact_support': [], 'conflicts': []}}

    def assess(self):
        return assess_claims(self.answer, self.judge, self.entries, item=self.item)

    def test_explicit_scoped_reference_is_accepted_without_mutating_raw_judgment(self):
        before = deepcopy(self.judge)
        for category in ['positive', 'ablation']:
            self.item['test_category'] = category
            self.assertEqual(len(self.assess()['accepted']), 1)
        self.assertEqual(self.judge, before)

    def test_missing_or_unsafe_scope_flags_remain_pending(self):
        original = deepcopy(self.review)
        for field in original['scope_basis']:
            for missing in [True, False]:
                with self.subTest(field=field, missing=missing):
                    self.review.clear(); self.review.update(deepcopy(original))
                    if missing: self.review['scope_basis'].pop(field)
                    else: self.review['scope_basis'][field] = True if field in {'requested_workflow_applicable', 'authorizes_operation', 'evidence_ignored'} else False
                    self.assertTrue(self.assess()['pending'])

    def test_wrong_answer_source_negative_or_changed_operation_cannot_escape(self):
        original = deepcopy(self.review)
        for mode in ['negative', 'behavior_failed', 'operation', 'wrong_answer', 'wrong_source', 'missing_support', 'missing_source', 'wrong_kind']:
            with self.subTest(mode=mode):
                self.review.clear(); self.review.update(deepcopy(original))
                self.item['test_category'] = 'positive'; self.judge['behavior_pass'] = True
                if mode == 'negative': self.item['test_category'] = 'negative'
                elif mode == 'behavior_failed': self.judge['behavior_pass'] = False
                elif mode == 'operation': self.review.update(changes_operation=True, operation_basis={'effect': 'technical_change', 'source_applicable': False})
                elif mode == 'wrong_answer': self.review['claim'] = '立即退出当前任务'
                elif mode == 'wrong_source': self.review['scope_basis']['source_scope']['quote'] = '当前任务必须执行'
                elif mode == 'missing_support': self.review['support'] = []
                elif mode == 'missing_source': self.review['support'][0]['chunk_id'] = 'not-final'
                else: self.review['kind'] = 'unresolved'
                self.assertTrue(self.assess()['pending'])

    def test_scope_cannot_borrow_unrelated_answer_prefix_or_foreign_final_entry(self):
        self.review['claim'] = '关闭清洁功能。'
        self.assertTrue(self.assess()['pending'])
        self.review['answer_quotes'] = ['关闭清洁功能。']
        self.assertTrue(self.assess()['pending'])
        self.review['answer_quotes'] = ['后续结束路线时：关闭清洁功能。']
        self.entries.append({**deepcopy(self.entries[0]), 'chunk_id': 'foreign'})
        self.review['scope_basis']['source_scope']['chunk_id'] = 'foreign'
        self.assertTrue(self.assess()['pending'])

    def test_identity_flags_cannot_override_missing_or_conflicting_source_metadata(self):
        original = deepcopy(self.entries)
        for mode in ['empty_metadata', 'product', 'version', 'document_id', 'mixed_metadata', 'mixed_support']:
            with self.subTest(mode=mode):
                self.entries[:] = deepcopy(original)
                self.review['support'] = [{'chunk_id': 'route', 'quote': '关闭清洁功能。'}]
                if mode == 'empty_metadata': self.entries[0]['metadata'] = {}
                elif mode in {'product', 'version'}: self.entries[0]['metadata'][mode] = 'foreign'
                elif mode == 'document_id': self.entries[0]['document_id'] = 'foreign'
                elif mode == 'mixed_metadata': self.entries[0]['product'] = 'foreign'
                else:
                    self.entries.append({**deepcopy(self.entries[0]), 'chunk_id': 'foreign', 'document_id': 'foreign'})
                    self.review['support'].append({'chunk_id': 'foreign', 'quote': '关闭清洁功能。'})
                self.assertTrue(self.review['scope_basis']['source_identity_matches'])
                self.assertTrue(self.assess()['pending'])

    def test_undeclared_version_is_unknown_only_for_one_actual_entry_without_version_constraint(self):
        self.entries[0]['metadata'].pop('version')
        self.item['raw'].pop('version')
        original = deepcopy(self.entries)
        self.assertTrue(self.assess()['accepted'])
        self.assertEqual(self.entries, original)  # No invented version is persisted.
        self.item['raw']['version'] = '1.0'
        self.assertTrue(self.assess()['pending'])
        self.item['raw'].pop('version')
        self.entries[0]['version'] = ''
        self.assertTrue(self.assess()['pending'])
        self.entries[0]['version'] = '2.0'
        self.entries[0]['metadata']['version'] = '1.0'
        self.assertTrue(self.assess()['pending'])

    def test_extra_unsourced_instruction_still_fails(self):
        self.answer += '更换传感器。'
        self.judge['unsupported_claims'].append('更换传感器。')
        self.judge['claim_reviews'].append({'unsupported_claim_index': 1, 'claim': '更换传感器。', 'kind': 'unsupported_instruction',
            'changes_operation': True, 'critical': True, 'reason': '没有适用依据', 'support': [],
            'operation_basis': {'effect': 'technical_change', 'source_applicable': False}})
        result = self.assess()
        self.assertEqual(len(result['accepted']), 1)
        self.assertEqual(len(result['confirmed']), 1)

    def test_one_judge_parser_preserves_fields_and_rejects_missing_basis(self):
        provider = DeepSeekProvider(Settings('fixture', 'https://example.invalid', 'fixture'))
        context = {'category': 'positive', 'final_context': self.entries, 'source_constraints': self.item['raw']}
        with patch.object(provider, 'complete', return_value=json.dumps(self.judge)) as call:
            result = provider.judge('当前任务', '规定步骤', self.answer, context=context)
            self.assertEqual(result['claim_reviews'][0]['consistency_status'], 'consistent')
            self.assertEqual(call.call_count, 1)
            self.assertIn('scope_basis', call.call_args.args[0])
        self.review['scope_basis'].pop('authorizes_operation')
        with patch.object(provider, 'complete', return_value=json.dumps(self.judge)):
            with self.assertRaises(ProviderInvalidResponse): provider.judge('当前任务', '规定步骤', self.answer, context=context)

    def test_identity_changes_and_old_unresolved_review_is_not_upgraded(self):
        old = {'prompt_version': 'judge-v3.3-operation-scope', 'evidence_matcher_version': 'evidence-v6-safe-abstention', 'scoring_policy': 'v1.5-diagnostic-targets'}
        self.assertNotEqual(evaluation_identity({'id': 'frozen'}, old), evaluation_identity({'id': 'frozen'}, VERSIONS))
        self.review['kind'] = 'unresolved'; self.review.pop('scope_basis')
        self.assertTrue(self.assess()['pending'])
