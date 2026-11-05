"""Synthetic QC role fixtures; no private files or Provider/approval evidence."""
import copy
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


class GoldenQCRoleScopeTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix='qc-role-scope-offline-')
        self.addCleanup(directory.cleanup)
        root = Path(directory.name); (root / '.env').write_text('')
        environment = patch.dict(os.environ, {'RAG_DEMO_DB_PATH': str(root / 'unused.db'),
            'RAG_DEMO_INDEX_DIR': str(root / 'index'), 'RAG_DEMO_DOCUMENTS_DIR': str(root / 'documents'),
            'RAG_DEMO_UPLOADS_DIR': str(root / 'uploads'), 'RAG_DEMO_ENV_PATH': str(root / '.env'),
            'DEEPSEEK_API_KEY': '', 'DASHSCOPE_API_KEY': '', 'MINERU_API_KEY': ''})
        environment.start(); self.addCleanup(environment.stop)
        from app.ai_service import AiService
        from app.providers import ProviderInvalidResponse
        self.AiService, self.InvalidResponse = AiService, ProviderInvalidResponse
        quote='维护前关闭设备并断开电池连接。'
        records=[]
        for index in range(1,51):
            qid=f'Q{index:02d}';required=qid+'-R1';auxiliary=qid+'-R2'
            requirements={'required_checks':[{'id':required,'requirement':'关机且断电','source_chunk_ids':['C1']}],
                'conditional_checks':[],'auxiliary_information':[{'id':auxiliary,'requirement':'辅助说明'}],
                'prohibited':[],'acceptable_equivalents':[],'sources':[{'chunk_id':'C1','quote':quote}]}
            records.append({'item':{'id':qid,'question':qid+'维护前怎么办？','test_category':'positive',
                'reference_answer':quote,'evidence':[{'source_chunk_ids':['C1'],'evidence_key_points':[quote]}],
                'raw':{'business_requirements':requirements,'expected_response':quote}},
                'expected_qc_check_ids':[required],'excluded_role_or_child_ids':[auxiliary]})
        response={'score':90,'priority':'P2','issues':[],'reason':'explicit synthetic QC fixture',
            'ablation_valid':True,'ablation_reason':'fixture','content_review':{'checks':[
                {'id':key,'applicable':True,'met':True,'reason':'fixture','support':[{'chunk_id':'C1','quote':quote}]}
                for key in ('Q36-R1','Q36-R2')],
                'scope_valid':True,'safety_valid':True,'prohibited_clear':True,'disputes':[]}}
        self.fixture={'records':records,'chunks':[{'chunk_id':'C1','document_id':'D','chunk_text':quote}],
            'recorded_failure':{'question_id':'Q36','raw_content':json.dumps(response)}}
        self.q36 = next(r for r in self.fixture['records'] if r['item']['id'] == self.fixture['recorded_failure']['question_id'])
        self.requests = []

    def qc(self, item, response):
        def complete(system, user, **kwargs):
            self.requests.append({'system': system, 'payload': json.loads(user)})
            return response if isinstance(response, str) else json.dumps(response)
        provider = SimpleNamespace(complete=complete, settings=SimpleNamespace(configured=True, model='OFFLINE-FIXTURE'))
        store = SimpleNamespace(probe_history=lambda _key: [], review_history=lambda _key: [])
        corpus = SimpleNamespace(chunks=lambda: self.fixture['chunks'])
        return self.AiService(store, corpus, provider, False)._quality_check(item)

    def test_synthetic_response_with_auxiliary_check_remains_strictly_rejected(self):
        raw = self.fixture['recorded_failure']['raw_content']
        self.assertEqual([c['id'] for c in json.loads(raw)['content_review']['checks']], ['Q36-R1','Q36-R2'])
        with self.assertRaisesRegex(self.InvalidResponse, 'required and conditional checks exactly once'):
            self.qc(self.q36['item'], raw)
        self.assertEqual(len(self.requests), 1)

    def test_correct_constructed_q36_sample_uses_only_required_parent_id_and_keeps_auxiliary_context(self):
        response = json.loads(self.fixture['recorded_failure']['raw_content'])
        response['content_review']['checks'] = [c for c in response['content_review']['checks'] if c['id'] == 'Q36-R1']
        response.update(offline_fixture=True, reason='OFFLINE FIXTURE corrected coverage sample, not a new Provider judgment')
        item = copy.deepcopy(self.q36['item']); before = copy.deepcopy(item)
        result = self.qc(item, response)
        self.assertEqual(result['content_validation']['status'], 'supported')
        payload = self.requests[0]['payload']
        self.assertEqual(payload.get('qc_check_ids'), ['Q36-R1'])
        self.assertEqual(payload['business_requirements'], item['raw']['business_requirements'])
        self.assertEqual(payload['expected_response'], item['raw']['expected_response'])
        self.assertIn('Q36-R2', [c['id'] for c in payload['business_requirements']['auxiliary_information'] if isinstance(c, dict)])
        self.assertEqual(item, before)

    def test_50_synthetic_contracts_expose_exact_qc_parent_whitelists(self):
        self.assertEqual(len(self.fixture['records']), 50)
        for record in self.fixture['records']:
            with self.subTest(question_id=record['item']['id']):
                item = record['item']; requirements = item['raw']['business_requirements']
                checks = [{'id': c['id'], 'applicable': field == 'required_checks', 'met': False,
                           'reason': 'OFFLINE FIXTURE schema-only sample, not a quality judgment', 'support': []}
                          for field in ('required_checks','conditional_checks') for c in requirements[field]]
                response = {'offline_fixture': True, 'score': 0, 'priority': 'P0', 'issues': ['OFFLINE FIXTURE'],
                    'reason': 'OFFLINE FIXTURE role/schema test only', 'ablation_valid': True, 'ablation_reason': 'OFFLINE FIXTURE',
                    'content_review': {'checks': checks, 'scope_valid': True, 'safety_valid': True, 'prohibited_clear': True, 'disputes': []}}
                self.qc(item, response)
                payload = self.requests[-1]['payload']
                self.assertEqual(payload.get('qc_check_ids'), record['expected_qc_check_ids'])
                self.assertFalse(set(payload['qc_check_ids']) & set(record['excluded_role_or_child_ids']))
                self.assertEqual(payload['business_requirements'], requirements)


if __name__ == '__main__':
    unittest.main()
