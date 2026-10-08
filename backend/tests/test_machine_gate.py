"""Offline dataset confirmation, risk classification and audit identity checks."""
import json
import sqlite3
from unittest.mock import patch
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
            candidate = {'coverage_slot':slot,'test_category':category,'question':f'设备{number}如何使用？','reference_answer':None if category=='negative' else '先断电', 'evidence':[] if category=='negative' else [{'source_chunk_ids':['C1']}], 'negative_subtype':'safety_critical' if number==60 else 'prompt_injection' if number==61 else None, 'expected_behavior':'insufficient_evidence' if category=='negative' else None}
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

    def test_full_freeze_with_sqlite_cache_spill_is_atomic_and_idempotent(self):
        # Small page cache deterministically reproduces the real 100-question lock.
        connect = sqlite3.connect
        def limited_cache(*args, **kwargs):
            connection = connect(*args, **kwargs)
            connection.execute('PRAGMA cache_size=10')
            connection.execute('PRAGMA busy_timeout=100')
            return connection
        with patch('app.governance.sqlite3.connect', side_effect=limited_cache):
            first = self.store.review_generation_batch(self.ids, 'fixture', confirmed_manual_review=True)
            second = self.store.review_generation_batch(self.ids, 'fixture', confirmed_manual_review=True)
        self.assertEqual(first['snapshot'], second['snapshot'])
        self.assertEqual(len(first['snapshot']['questions']), 100)
        self.assertEqual(len(self.store.dataset_snapshots()), 1)
        with self.store.connection() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM approvals WHERE gate='dataset'").fetchone()[0], 100)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM review_events WHERE decision='dataset_confirmed'").fetchone()[0], 100)
        self.assertFalse(self.store.current_baseline_identity()['requires_new_golden'])
        self.assertIsNone(self.store.current_baseline_identity()['current_baseline_id'])

    def test_freeze_api_ready_pending_and_database_error_are_readable(self):
        from api_fixture import main
        from fastapi.testclient import TestClient
        with patch.object(main, 'store', self.store):
            client = TestClient(main.app, raise_server_exceptions=False)
            payload = {'question_ids': self.ids, 'confirmed_manual_review': True}
            headers = {'Origin': 'http://localhost:5174'}
            self.store.record_qc(self.ids[0], {'score':75, 'priority':'P1'}, 'passed')
            pending = client.post('/api/governance/review-batch', json=payload, headers=headers)
            self.assertEqual(pending.status_code, 409)
            self.assertIn(self.ids[0], pending.json()['detail'])
            self.assertEqual(self.store.dataset_snapshots(), [])
            self.store.review_question(self.ids[0], 'approved', 'fixture human', reason='reviewed evidence')
            with patch.object(self.store, 'review_generation_batch', side_effect=sqlite3.OperationalError('fixture database failure')):
                failed = client.post('/api/governance/review-batch', json=payload, headers=headers)
            self.assertEqual(failed.status_code, 503)
            self.assertEqual(failed.headers['access-control-allow-origin'], headers['Origin'])
            self.assertIn('Snapshot', failed.json()['detail'])
            ready = client.post('/api/governance/review-batch', json=payload, headers=headers)
            self.assertEqual(ready.status_code, 200)
            repeated = client.post('/api/governance/review-batch', json=payload, headers=headers)
            self.assertEqual(ready.json()['snapshot'], repeated.json()['snapshot'])
            self.assertEqual(len(client.get('/api/governance/snapshots').json()), 1)

    def test_baseline_requires_frozen_snapshot_with_current_corpus_identity(self):
        from app.evaluation import EvaluationRunner
        from app.corpus import current_manifest, manifest_identity
        from types import SimpleNamespace
        identity = manifest_identity(current_manifest())
        runtime = SimpleNamespace(model='fixture', corpus=SimpleNamespace(index_info=lambda: {'knowledge_identity':identity, 'knowledge_config':{'candidate_k':12, 'top_k':4}}))
        runner = EvaluationRunner(self.store, runtime)
        with self.assertRaisesRegex(ValueError, 'Snapshot'):
            runner.start_baseline()
        frozen = self.store.review_generation_batch(self.ids, 'fixture', confirmed_manual_review=True)['snapshot']
        evaluation_id, approved, config = runner.start_baseline()
        self.assertEqual(len(approved), 100)
        self.assertEqual(self.store.evaluation_run(evaluation_id)['dataset_version_id'], frozen['id'])
        self.assertEqual(config['knowledge_identity'], identity)
        runtime.corpus.index_info = lambda: {'knowledge_identity':{'version':'other'}, 'knowledge_config':{'candidate_k':12, 'top_k':4}}
        with self.assertRaisesRegex(ValueError, 'does not belong'):
            runner.start_baseline()
        self.assertEqual(len(self.store.evaluation_runs()), 1)

    def test_snapshot_insert_failure_rolls_back_question_and_approval_updates(self):
        before = self.store.candidate_rows(self.ids)
        with self.store.connection() as connection:
            connection.execute("CREATE TRIGGER fail_snapshot BEFORE INSERT ON dataset_versions BEGIN SELECT RAISE(ABORT, 'fixture snapshot failure'); END")
            approvals = connection.execute('SELECT COUNT(*) FROM approvals').fetchone()[0]
            reviews = connection.execute('SELECT COUNT(*) FROM review_events').fetchone()[0]
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.review_generation_batch(self.ids, 'fixture', confirmed_manual_review=True)
        self.assertEqual(self.store.dataset_snapshots(), [])
        self.assertEqual(self.store.candidate_rows(self.ids), before)
        with self.store.connection() as connection:
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM approvals').fetchone()[0], approvals)
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM review_events').fetchone()[0], reviews)
        self.assertTrue(self.store.current_baseline_identity()['requires_new_golden'])

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
