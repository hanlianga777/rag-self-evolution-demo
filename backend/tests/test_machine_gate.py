"""Offline dataset confirmation, risk classification and audit identity checks."""
import json
import tempfile
import unittest
from pathlib import Path
from app.governance import GovernanceStore, GENERATION_PROFILES

CHECKS = ['naturalness','business_value','intent','grounding','independence','copying','duplicates','type','coverage','diversity']

class MachineGateTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(); self.addCleanup(directory.cleanup)
        self.store = GovernanceStore(Path(directory.name)/'test.db')
        self.run = self.store.start_generation_run('fixture', 'full')
        for number in range(100):
            category = 'positive' if number<40 else 'ablation' if number<60 else 'negative'
            slot = f'Q{number+1:02d}'
            candidate = {'coverage_slot':slot,'test_category':category,'question':f'设备{number}如何使用？','reference_answer':None if category=='negative' else '先断电', 'evidence':[] if category=='negative' else [{'source_chunk_ids':['C1']}], 'expected_behavior':'insufficient_evidence' if category=='negative' else None}
            self.store.persist_generation_attempt(self.run, candidate, {}, slot=slot, attempt=1, model='fixture')
        self.store.update_generation_run(self.run,status='completed')
        self.ids=self.store.generation_run(self.run)['question_ids']
        for key in self.ids:
            self.store.record_probe_result(key,{'question_quality':30,'golden_answer_quality':30,'evidence_support':40,'probe_details':{'classification':'EVIDENCE_VALID'}})
            self.store.record_qc(key,{'score':95,'priority':'P2'},'passed')
            self.store.save_quality_audit(key,{'checks':dict.fromkeys(CHECKS,True),'reason':'fixture audit'})

    def gate(self): return self.store.generation_run(self.run)['human_gate']

    def test_a_safe_machines_require_one_explicit_dataset_confirmation(self):
        self.assertEqual(self.gate()['machine_qualified'],100)
        self.assertEqual(self.gate()['needs_human_review'],0)
        self.assertEqual(self.gate()['status'],'ready')
        self.assertEqual(self.store.dataset_snapshots(),[])
        with self.assertRaises(ValueError): self.store.review_generation_batch(self.ids,'fixture')
        result=self.store.review_generation_batch(self.ids,'fixture',confirmed_manual_review=True)
        self.assertEqual(set(result['snapshot']['qualification_sources'].values()),{'machine'})
        self.assertEqual(self.store.candidate_rows(self.ids)[0]['qualification_source'],'machine')

    def test_b_p1_exceptions_require_individual_human_decisions(self):
        for key in self.ids[:14]: self.store.record_qc(key,{'score':75,'priority':'P1'},'passed')
        self.assertEqual((self.gate()['machine_qualified'],self.gate()['needs_human_review']),(86,14))
        self.assertEqual(self.gate()['status'],'pending')
        with self.assertRaises(ValueError):self.store.review_generation_batch(self.ids,'fixture',confirmed_manual_review=True)
        for key in self.ids[:14]:self.store.review_question(key,'approved','fixture human',reason='reviewed P1 evidence')
        self.assertEqual(self.gate()['status'],'ready')
        result=self.store.review_generation_batch(self.ids,'fixture',confirmed_manual_review=True)
        self.assertEqual(sum(source=='human' for source in result['snapshot']['qualification_sources'].values()),14)

    def test_c_quality_blocker_and_changed_content_cannot_pass(self):
        self.store.save_quality_audit(self.ids[0],{'checks':{key:key!='naturalness' for key in CHECKS},'attention_reason':'提问口吻需优化'})
        self.assertEqual(self.gate()['needs_human_review'],1)
        self.assertEqual(self.gate()['status'],'pending')
        with self.assertRaises(ValueError):self.store.review_generation_batch(self.ids,'fixture',confirmed_manual_review=True)
        with self.store.connection() as c:c.execute('UPDATE questions SET question=? WHERE id=?',('changed',self.ids[0]))
        self.assertIn('质量记录已过期',self.store.candidate_rows([self.ids[0]])[0]['attention_reasons'])
        self.assertIn('题目质量审计待更新',self.store.candidate_rows([self.ids[0]])[0]['attention_reasons'])

    def test_d_incomplete_99_cannot_freeze(self):
        with self.store.connection() as c:c.execute('UPDATE golden_generation_runs SET question_ids_json=? WHERE id=?',(json.dumps(self.ids[:-1]),self.run))
        self.assertEqual(self.gate()['status'],'pending')
        with self.assertRaises(ValueError):self.store.review_generation_batch(self.ids[:-1],'fixture',confirmed_manual_review=True)

    def test_e_wrong_category_quota_cannot_freeze(self):
        with self.store.connection() as c:c.execute("UPDATE questions SET test_category='negative' WHERE id=?",(self.ids[0],))
        self.assertFalse(self.gate()['profile_complete'])
        with self.assertRaises(ValueError):self.store.review_generation_batch(self.ids,'fixture',confirmed_manual_review=True)

    def test_paginated_list_keeps_summary_and_lazy_detail_contract(self):
        from unittest.mock import patch
        from app import main
        with patch.object(main, 'store', self.store):
            first = main.candidate_list(self.run, 0, 30)
            second = main.candidate_list(self.run, 30, 30)
            self.assertEqual((len(first['rows']), first['total'], len(first['candidate_index'])), (30, 100, 100))
            self.assertFalse(set(row['id'] for row in first['rows']) & set(row['id'] for row in second['rows']))
            self.assertNotIn('evidence', first['rows'][0])
            self.assertNotIn('question', main.dataset(True)[0])
            self.assertIsInstance(first['rows'][0]['question'], str)
            self.assertEqual(sum(first['summary'][key] for key in ('machine_qualified', 'needs_processing', 'pending_checks')), 100)
            light = main.generation_runs(True)
            self.assertEqual(len(light), 1)
            self.assertNotIn('hard_validation_json', light[0]['artifacts'])

    def test_profiles_and_light_rows_have_no_details(self):
        self.assertEqual([p['expected_count'] for p in GENERATION_PROFILES.values()],[20,50,100])
        row=self.store.candidate_rows(self.ids)[0]
        self.assertNotIn('evidence',row);self.assertNotIn('probe_history',row)
        with self.assertRaises(ValueError):self.store.save_quality_audit(self.ids[0],{'checks':{'naturalness':True}})

class RevisionVectorReuseTests(unittest.TestCase):
    def test_batch_embeddings_are_reused_and_bound_to_space_identity(self):
        import numpy as np
        from unittest.mock import patch
        from app.ai_service import AiService
        from app.corpus import CorpusStore
        service=object.__new__(AiService)
        service.corpus=object.__new__(CorpusStore)
        identity={'knowledge_identity':{'version':'v1'},'dimension':2}
        with patch.object(CorpusStore,'index_info',return_value=identity), patch('app.knowledge_pipeline.AlibabaProvider.embed', side_effect=lambda texts,dimension:np.asarray([[1.,0.] for _ in texts])) as embed:
            service.prepare_revision_similarity(['first','second','third'])
            self.assertEqual(embed.call_count,1)
            self.assertEqual(service.revision_similarity('first','second'),1.)
            self.assertEqual(embed.call_count,1)
            identity['knowledge_identity']={'version':'v2'}
            service.revision_similarity('first','second')
            self.assertEqual(embed.call_count,2)
