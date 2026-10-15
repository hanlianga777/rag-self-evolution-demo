"""Offline audit payloads preserve only verified, applied clone provenance."""
import copy
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.ai_service import AiService
from app.business_golden import CHECKS
from app.governance import GovernanceStore


class BusinessAuditCloneHistoryTests(unittest.TestCase):
    def setUp(self):
        self.source = {
            'id': 'SOURCE', 'question': '设备长期存放时电池怎么维护？',
            'reference_answer': '存放前充满，每月至少完全充电一次。',
            'evidence': [{'source_chunk_ids': ['C1']}], 'test_category': 'positive',
            'negative_subtype': None, 'legacy_question_type': 'v1_mini',
            'raw': {'generation_run_id': 'OLD', 'generation_path': 'business_question_first',
                    'coverage_slot': 'Q01', 'business_design': {'question': '原始存放问题'},
                    'user_role': '操作员', 'business_scenario': '长期停用', 'user_intent': '电池存放维护'},
        }
        self.clone = copy.deepcopy(self.source)
        self.clone['id'] = 'CLONE'
        self.clone['raw'].update(
            generation_run_id='NEW',
            source_reference={'question_id': 'SOURCE', 'generation_run_id': 'OLD'},
            clone_provenance={'source_content_hash': GovernanceStore._quality_content(self.source),
                              'semantic_content_unchanged': True},
        )
        self.questions = {'SOURCE': self.source, 'CLONE': self.clone}
        self.runs = {key: {'id': key, 'question_ids': [qid], 'artifacts': {'hard_validation': {}}}
                     for key, qid in [('OLD', 'SOURCE'), ('NEW', 'CLONE')]}
        self.revision = {
            'id': 'APPLIED-SOURCE', 'generation_run_id': 'OLD', 'actor': 'Codex',
            'reason': '删除无依据的水箱存放要求，保留电池存放意图', 'applied_at': '2026-10-15T01:00:00+00:00',
            'question_ids': ['SOURCE'], 'drafts': {'SOURCE': copy.deepcopy(self.source)},
            'changes': {'SOURCE': {'reference_answer': self.source['reference_answer']}},
            # _revision_hash is deliberately not _quality_content.
            'new_hash': {'SOURCE': 'different-revision-hash'},
        }
        self.histories = {'SOURCE': [self.revision], 'CLONE': []}
        self.payloads = []
        self.service = object.__new__(AiService)
        self.service.store = SimpleNamespace(
            question=lambda key: copy.deepcopy(self.questions[key]),
            generation_run=lambda key, **kwargs: copy.deepcopy(self.runs.get(key)),
            revision_history=lambda key: copy.deepcopy(self.histories.get(key, [])),
            _quality_content=GovernanceStore._quality_content,
        )
        self.service.corpus = SimpleNamespace(chunks=lambda: [{'chunk_id': 'C1', 'document_id': 'D1',
                                                             'product': '设备', 'chunk_text': '存放维护。'}])
        self.service.business_parent_context = lambda slot: []
        self.service.provider = SimpleNamespace(complete=self.complete)
        self.manifest = patch('app.ai_service.current_manifest', return_value={'sources': {'D1': 'offline'}})
        self.manifest.start()
        self.addCleanup(self.manifest.stop)

    def complete(self, system, payload, **kwargs):
        self.payloads.append(json.loads(payload))
        return json.dumps({'checks': dict.fromkeys(CHECKS, False), 'reason': 'independent offline refusal'})

    def audit(self, item=None):
        result = self.service.business_quality_audit(copy.deepcopy(item or self.clone), [])
        self.assertFalse(result['checks']['copying'])  # Adding history must not override the judge.
        return self.payloads[-1]['revisions']

    def test_identical_clone_receives_applied_source_reason_and_original_identity(self):
        revisions = self.audit()
        self.assertEqual([r['id'] for r in revisions], ['APPLIED-SOURCE'])
        self.assertEqual(revisions[0]['generation_run_id'], 'OLD')
        self.assertEqual(revisions[0]['source_question_id'], 'SOURCE')
        self.assertEqual(revisions[0]['reason'], '删除无依据的水箱存放要求，保留电池存放意图')
        self.assertEqual(revisions[0]['changes'], {'SOURCE': {'reference_answer': '存放前充满，每月至少完全充电一次。'}})

    def test_two_identical_clone_links_preserve_original_history(self):
        middle = copy.deepcopy(self.clone)
        middle['id'] = 'MIDDLE'
        middle['raw']['generation_run_id'] = 'MID'
        self.questions['MIDDLE'] = middle
        self.runs['MID'] = {'id': 'MID', 'question_ids': ['MIDDLE'], 'artifacts': {'hard_validation': {}}}
        self.clone['raw']['source_reference'] = {'question_id': 'MIDDLE', 'generation_run_id': 'MID'}
        self.clone['raw']['clone_provenance']['source_content_hash'] = GovernanceStore._quality_content(middle)
        self.assertEqual([r['id'] for r in self.audit()], ['APPLIED-SOURCE'])

    def test_unapplied_wrong_run_and_stale_drafts_are_not_source_history(self):
        for change in ('not_applied', 'wrong_run', 'old_draft', 'missing_draft'):
            with self.subTest(change=change):
                revision = copy.deepcopy(self.revision)
                if change == 'not_applied': revision.pop('applied_at')
                if change == 'wrong_run': revision['generation_run_id'] = 'UNRELATED'
                if change == 'old_draft': revision['drafts']['SOURCE']['question'] = '另一业务问题'
                if change == 'missing_draft': revision.pop('drafts')
                self.histories['SOURCE'] = [revision]
                self.assertEqual(self.audit(), [])

    def test_changed_clone_cannot_inherit_source_history(self):
        original = copy.deepcopy(self.clone)
        for field, value in [('question', '另一问题'), ('reference_answer', '另一答案'),
                             ('evidence', [{'source_chunk_ids': ['OTHER']}]),
                             ('test_category', 'negative'), ('negative_subtype', 'clarify')]:
            with self.subTest(field=field):
                self.clone.clear(); self.clone.update(copy.deepcopy(original))
                self.clone[field] = value
                self.assertEqual(self.audit(), [])
        self.clone.clear(); self.clone.update(copy.deepcopy(original))
        self.clone['raw']['business_design'] = {'question': '新的业务设计'}
        self.assertEqual(self.audit(), [])

    def test_untrusted_pointer_stale_hash_or_wrong_membership_cannot_inherit(self):
        original = copy.deepcopy(self.clone)
        for change in ('caller_pointer', 'source_run', 'source_member', 'clone_member', 'hash'):
            with self.subTest(change=change):
                self.clone.clear(); self.clone.update(copy.deepcopy(original))
                self.runs['OLD']['question_ids'] = ['SOURCE']
                self.runs['NEW']['question_ids'] = ['CLONE']
                item = copy.deepcopy(self.clone)
                if change == 'caller_pointer': item['raw']['source_reference']['question_id'] = 'FORGED'
                if change == 'source_run': self.clone['raw']['source_reference']['generation_run_id'] = 'UNRELATED'; item = copy.deepcopy(self.clone)
                if change == 'source_member': self.runs['OLD']['question_ids'] = []
                if change == 'clone_member': self.runs['NEW']['question_ids'] = []
                if change == 'hash': self.clone['raw']['clone_provenance']['source_content_hash'] = 'stale'; item = copy.deepcopy(self.clone)
                self.assertEqual(self.audit(item), [])

    def test_source_reference_cycle_stops_without_duplicate_history(self):
        self.clone['raw']['source_reference'] = {'question_id': 'CLONE', 'generation_run_id': 'NEW'}
        self.clone['raw']['clone_provenance']['source_content_hash'] = 'cannot-be-self-consistent'
        self.assertEqual(self.audit(), [])
