"""Saved D replacement uses disposable databases and no model transport."""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
import test_evaluation_context as fixtures
from app.governance import GovernanceStore

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))


class ImportTests(unittest.TestCase):
    result = fixtures.CompositeTests.result
    def setUp(self):
        fixtures.CompositeTests.setUp(self)
        from app.composite import pipeline_config
        self.source = GovernanceStore(Path(self.directory.name) / 'private.db')
        # A small hand-built fixture, never a copy of the demo database.
        with self.store.connection() as db, self.source.connection() as target:
            for table in ('evaluation_runs','evaluation_case_results','evaluation_checkpoints','candidate_configs'):
                rows=db.execute('select * from '+table).fetchall()
                for row in rows:
                    target.execute('insert into '+table+' values ('+','.join('?' for _ in row)+')',tuple(row))
        self.did=self.experiment+'-D'
        config={**pipeline_config(self.winner['config']),'top_k':6}
        reasoning={'candidate_label':'D','winner_id':self.winner['id'],'observed_evidence':['q2']}
        with self.store.connection() as db:
            db.execute('insert into candidate_configs values (?,?,?,?,?,?,?)',(self.did,self.experiment,'generated',json.dumps(config),json.dumps(reasoning),'{}','now'))
        self.old=self.store.create_evaluation_run(self.snapshot,{**config,'candidate_id':self.did,'run_target':'sandbox_candidate'},self.meta)
        self.store.finish_evaluation_run(self.old,'completed',{'evaluation_complete':True})
        with self.store.connection() as db:
            reasoning['sandbox_attempts']=[{'attempt':1,'evaluation_run_id':self.old,'started_at':'old-time'}]
            db.execute('update candidate_configs set reasoning_json=? where id=?',(json.dumps(reasoning),self.did))
        self.store.finish_candidate(self.did,'evaluated',{'evaluation_run_id':self.old})
        with self.store.connection() as db:
            state=json.loads(db.execute('select result_json from experiments where id=?',(self.experiment,)).fetchone()[0])
            state['composite']={'status':'generated','candidate_id':self.did}
            db.execute('update experiments set result_json=? where id=?',(json.dumps(state),self.experiment))
        self.run=self.source.create_evaluation_run(self.snapshot,{**config,'candidate_id':self.winner['id'],'run_target':'sandbox_candidate'},self.meta)
        for q in ('q','q2'):
            self.source.record_evaluation_case(self.run,q,{'question_id':q,'passed':True,'model_answer':'{ "saved": "q2" }' if q=='q2' else 'saved q','programmatic_metrics':{'token_usage':{'total_tokens':123}}})
        self.source.finish_evaluation_run(self.run,'completed',{'evaluation_complete':True,'total':2,'bad_case_count':0,'gates':{'passed':True},'internal_recheck':True,'purpose':'内部试跑','request_accounting':{'known_input_tokens':246}})
        with self.source.connection() as db:
            for q in ('q','q2'):db.execute('insert into evaluation_checkpoints values (?,?,?)',(self.run,q,json.dumps({'saved':True})))
        self.index={'identity':{'index':'fixture'},'files':{'manifest.json':'fixed-hash'}}

    def import_run(self):
        from import_d_result import import_saved_d
        return import_saved_d(self.store,self.source,self.run,self.did,self.index,self.index)

    def test_import_preserves_answers_times_usage_and_budget_recalculates_recommendation(self):
        before=self.store.experiment(self.experiment)['evaluation_budget']
        old=self.store.evaluation_run(self.old)
        self.import_run()
        saved=self.store.evaluation_run(self.run)
        original=self.source.evaluation_run(self.run)
        self.assertEqual(saved['created_at'],original['created_at'])
        self.assertEqual(saved['completed_at'],original['completed_at'])
        self.assertEqual(self.store.evaluation_case_results(self.run),self.source.evaluation_case_results(self.run))
        self.assertEqual(saved['result']['request_accounting'],{'known_input_tokens':246})
        self.assertEqual(saved['config']['candidate_id'],self.did)
        with self.store.connection() as db, self.source.connection() as source:
            self.assertEqual([tuple(r) for r in db.execute('select * from evaluation_checkpoints where run_id=? order by question_id',(self.run,))],[tuple(r) for r in source.execute('select * from evaluation_checkpoints where run_id=? order by question_id',(self.run,))])
        self.assertEqual(saved['result']['_evaluation_audit']['original_candidate_id'],self.winner['id'])
        candidate=self.store.candidate(self.did)
        self.assertEqual(candidate['reasoning']['sandbox_attempts'][0]['started_at'],original['created_at'])
        self.assertEqual(candidate['result']['winner_comparison']['fixed_cases'],['q2'])
        self.assertTrue(candidate['result']['release_qualification']['qualified'])
        self.assertEqual(self.store.recommendation(self.experiment)['result']['recommended_candidate'],self.did)
        self.assertEqual(self.store.experiment(self.experiment)['evaluation_budget'],before)
        self.assertEqual(self.store.evaluation_run(self.old),old)
        self.assertEqual(candidate['result']['_evaluation_audit']['superseded_evaluations'],[self.old])
        self.assertNotIn(self.old,[r['id'] for r in self.store.evaluation_history()])
        # Retrying an interrupted handoff must not duplicate cases or spend budget.
        self.import_run()
        self.assertEqual(len(self.store.evaluation_case_results(self.run)),2)
        self.assertEqual(self.store.experiment(self.experiment)['evaluation_budget'],before)

    def test_business_and_identity_mismatches_never_import(self):
        for field in ('top_k','knowledge_identity','unexpected_business_option'):
            with self.subTest(field=field):
                with self.source.connection() as db:
                    raw=db.execute('select config_json from evaluation_runs where id=?',(self.run,)).fetchone()[0]
                    config=json.loads(raw);config[field]='different'
                    db.execute('update evaluation_runs set config_json=? where id=?',(json.dumps(config),self.run))
                with self.assertRaisesRegex(ValueError,'配置'):
                    self.import_run()
                self.assertIsNone(self.store.evaluation_run(self.run))
                with self.source.connection() as db:db.execute('update evaluation_runs set config_json=? where id=?',(raw,self.run))
        from import_d_result import import_saved_d
        with self.assertRaisesRegex(ValueError,'索引'):
            import_saved_d(self.store,self.source,self.run,self.did,self.index,{'files':{'manifest.json':'changed'}})

    def test_golden_judge_and_incomplete_results_are_rejected_without_writes(self):
        for field,value in (('dataset_snapshot_json',json.dumps({'question_ids':['other']})),('judge_json','{}'),('status','running')):
            with self.subTest(field=field):
                with self.source.connection() as db:
                    original=db.execute('select '+field+' from evaluation_runs where id=?',(self.run,)).fetchone()[0]
                    db.execute('update evaluation_runs set '+field+'=? where id=?',(value,self.run))
                with self.assertRaises(ValueError):self.import_run()
                self.assertIsNone(self.store.evaluation_run(self.run))
                with self.source.connection() as db:db.execute('update evaluation_runs set '+field+'=? where id=?',(original,self.run))

    def test_display_api_hides_history_and_import_audit_even_in_raw_json(self):
        from api_fixture import main
        from fastapi.testclient import TestClient
        self.import_run()
        with patch.object(main,'store',self.store):
            client=TestClient(main.app)
            self.assertEqual(client.get('/api/evaluations/'+self.old).status_code,404)
            for path in ('/api/evaluations','/api/evaluations/'+self.run,'/api/experiments/'+self.experiment,'/api/experiments/'+self.experiment+'?light=true'):
                response=client.get(path)
                self.assertEqual(response.status_code,200,response.text[:200])
                self.assertNotIn(self.old,response.text)
                self.assertNotIn('_evaluation_audit',response.text)
                self.assertNotIn('internal_trial',response.text)
                self.assertNotIn('internal_recheck',response.text)
                if path=='/api/evaluations/'+self.run:
                    self.assertEqual(response.json()['cases'][1]['model_answer'],'{ "saved": "q2" }')

    def test_published_snapshots_are_filtered_on_every_display_endpoint(self):
        from api_fixture import main
        from fastapi.testclient import TestClient
        self.import_run()
        with self.store.connection() as db:
            raw=db.execute('select result_json from candidate_configs where id=?',(self.did,)).fetchone()[0]
            result=json.loads(raw)
            result['_evaluation_audit']['source_database']='/private/internal.db'
            db.execute('update candidate_configs set result_json=? where id=?',(json.dumps(result),self.did))
        with patch.object(main,'store',self.store):
            client=TestClient(main.app)
            published=client.post('/api/candidates/'+self.did+'/publish',json={'decision':'approved','actor':'fixture human'})
            self.assertEqual(published.status_code,201,published.text[:200])
            version_id=published.json()['id']
            responses=[published]
            for path in ('/api/versions','/api/pipeline','/api/overview','/api/overview?light=true','/api/optimization','/api/experiments/'+self.experiment):
                response=client.get(path)
                self.assertEqual(response.status_code,200,response.text[:200])
                responses.append(response)
                if path == '/api/pipeline':
                    self.assertEqual(response.json()['active_version']['snapshot']['candidate_id'],self.did)
            # Exercise the real rollback response on this disposable fixture only.
            with patch('app.config.load_settings',return_value=type('Settings',(),{'model':'fixture'})()):
                response=client.post('/api/versions/'+version_id+'/rollback',json={'decision':'approved','actor':'fixture human'})
            self.assertEqual(response.status_code,200,response.text[:200])
            responses.append(response)
            # No Provider transport: only verify that the scheme response is filtered too.
            with patch.object(main.ai_service,'answer',return_value={'retrieval':[],'_evaluation_audit':result['_evaluation_audit']}):
                response=client.post('/api/preview/scheme',json={'scheme_id':version_id,'question':'fixture'})
            self.assertEqual(response.status_code,200,response.text[:200])
            responses.append(response)
            for response in responses:
                for hidden in ('_evaluation_audit','internal_trial','internal.db',self.old):
                    self.assertNotIn(hidden,response.text,response.request.url)
        raw_version=next(v for v in self.store.production_versions() if v['id']==version_id)
        self.assertEqual(raw_version['snapshot']['evaluation_result']['_evaluation_audit'],result['_evaluation_audit'])
        with self.store.connection() as db:
            self.assertEqual(json.loads(db.execute('select result_json from candidate_configs where id=?',(self.did,)).fetchone()[0]),result)
