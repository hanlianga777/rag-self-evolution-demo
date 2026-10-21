"""Offline entry eligibility; uses the same checks as transactional creation."""
import copy,json,unittest
from unittest.mock import patch
import test_baseline_resume as fixture
from app.evaluation import EvaluationRunner

class BaselineEntryTests(unittest.TestCase):
    setUp=fixture.ResumeTests.setUp
    tearDown=fixture.ResumeTests.tearDown
    def partial(self):
        key,items,config=self.runner.start_baseline()
        return self.runner.execute_baseline(key,items,config)
    def test_identical_partial_is_explicitly_resumable_without_writes_or_provider(self):
        old=self.partial();before=copy.deepcopy(self.store.evaluation_runs());calls=(list(self.runtime.answers),list(self.runtime.judges))
        result=self.runner.baseline_preflight(old['id'])
        self.assertTrue(result['can_start']);self.assertTrue(result['can_resume']);self.assertEqual(result['resume_source_id'],old['id'])
        self.assertEqual(self.store.evaluation_runs(),before);self.assertEqual((self.runtime.answers,self.runtime.judges),calls)
        child,_,_=self.runner.start_baseline(result['resume_source_id'])
        self.assertEqual(self.store.evaluation_run(child)['result']['resume_source_id'],old['id'])
    def test_judge_parser_identity_and_full_request_parameters_cannot_resume(self):
        old=self.partial();original=old['judge']
        for field,value in [('prompt_version','old'),('output_parser_version','old'),('evaluation_identity','wrong'),('model','other'),('execution_snapshot',{'temperature':.7})]:
            judge={**original,field:value}
            with self.store.connection() as c:c.execute('update evaluation_runs set judge_json=? where id=?',(json.dumps(judge),old['id']))
            result=self.runner.baseline_preflight(old['id'])
            self.assertTrue(result['can_start']);self.assertFalse(result['can_resume']);self.assertIsNone(result['resume_source_id'])
            with self.assertRaises(ValueError):self.runner.start_baseline(old['id'])
    def test_pipeline_and_golden_snapshot_change_forces_fresh(self):
        old=self.partial()
        for column,value in [('config_json',{**old['config'],'top_k':99}),('dataset_snapshot_json',{**json.loads(old['dataset_snapshot_json']),'questions':[]})]:
            with self.store.connection() as c:c.execute(f'update evaluation_runs set {column}=? where id=?',(json.dumps(value),old['id']))
            result=self.runner.baseline_preflight(old['id']);self.assertFalse(result['can_resume']);self.assertTrue(result['can_start'])
            with self.assertRaises(ValueError):self.runner.start_baseline(old['id'])
            with self.store.connection() as c:c.execute(f'update evaluation_runs set {column}=? where id=?',(old[column] if column=='dataset_snapshot_json' else json.dumps(old['config']),old['id']))
    def test_active_task_and_duplicate_resume_are_blocked(self):
        old=self.partial();child,_,_=self.runner.start_baseline(old['id'])
        active=self.runner.baseline_preflight(old['id']);self.assertFalse(active['can_start']);self.assertIn('活动',active['reason'])
        self.store.finish_evaluation_run(child,'failed',{'resume_source_id':old['id']})
        self.assertFalse(self.runner.baseline_preflight(old['id'])['can_resume'])
    def test_corpus_or_missing_golden_prevents_fresh_and_resume(self):
        old=self.partial()
        with patch('app.governance.manifest_identity',return_value='different-corpus'):
            # Legacy fresh behavior stays as implemented; strict resume still rejects changed Corpus.
            result=self.runner.baseline_preflight(old['id']);self.assertFalse(result['can_resume'])
        with self.store.connection() as c:c.execute('delete from dataset_versions')
        result=self.runner.baseline_preflight(old['id']);self.assertFalse(result['can_start']);self.assertIn('Golden',result['reason'])
    def test_knowledge_corpus_mismatch_disables_fresh(self):
        self.runtime.corpus=type('Corpus',(),{'index_info':lambda _: {'knowledge_identity':'wrong-corpus'}})()
        result=self.runner.baseline_preflight();self.assertFalse(result['can_start']);self.assertIn('Knowledge',result['reason'])
    def test_api_does_not_implicitly_resume_or_call_provider(self):
        from api_fixture import main
        from fastapi.testclient import TestClient
        old=self.partial();before=copy.deepcopy(self.store.evaluation_runs())
        manager=type('Manager',(),{'state':lambda _:None})()
        with patch.object(main,'store',self.store),patch.object(main,'ai_service',self.runtime),patch.object(main,'corpus_manager',manager),patch.object(main.EvaluationRunner,'execute_baseline',side_effect=AssertionError('No worker allowed')) as worker:
            client=TestClient(main.app)
            p=client.get('/api/evaluation/preflight',params={'resume_source_id':old['id']});self.assertEqual(p.status_code,200);self.assertTrue(p.json()['can_resume'])
            for body in [None,{}, {'fresh':False}]:
                r=client.post('/api/evaluations/run',json=body,headers={'Origin':'http://127.0.0.1:5174'});self.assertEqual(r.status_code,409)
            worker.assert_not_called();self.assertEqual(self.store.evaluation_runs(),before)
    def test_fresh_never_inherits_old_failed_run_even_when_compatible(self):
        from api_fixture import main
        from fastapi.testclient import TestClient
        old=self.partial();manager=type('Manager',(),{'state':lambda _:None})()
        with patch.object(main,'store',self.store),patch.object(main,'ai_service',self.runtime),patch.object(main,'corpus_manager',manager),patch.object(main.threading,'Thread') as worker:
            r=TestClient(main.app).post('/api/evaluations/run',json={'fresh':True},headers={'Origin':'http://127.0.0.1:5174'})
        self.assertEqual(r.status_code,201,r.text)
        new=self.store.evaluation_run(r.json()['id']);self.assertNotIn('resume_source_id',new['result']);self.assertEqual(self.store.evaluation_case_results(new['id']),[])
        self.assertEqual(self.store.evaluation_run(old['id']),old)

    def test_preflight_and_post_share_current_golden_corpus_block(self):
        from api_fixture import main
        from fastapi.testclient import TestClient
        manager=type('Manager',(),{'state':lambda _:{'status':'active'}})()
        with patch.object(main,'store',self.store),patch.object(main,'ai_service',self.runtime),patch.object(main,'corpus_manager',manager),patch.object(main,'manifest_identity',return_value='changed'):
            client=TestClient(main.app);preflight=client.get('/api/evaluation/preflight').json()
            self.assertFalse(preflight['can_start']);self.assertIn('Corpus',preflight['reason'])
            post=client.post('/api/evaluations/run',json={'fresh':True},headers={'Origin':'http://127.0.0.1:5174'})
            self.assertEqual(post.status_code,409);self.assertEqual(post.json()['detail'],preflight['reason'])
            self.assertFalse(self.runtime.answers)
