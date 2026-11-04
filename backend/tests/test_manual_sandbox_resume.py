"""Unknown charges remain recorded while bounded retries and continuation proceed."""
import json
import unittest
from copy import deepcopy
from unittest.mock import patch
import test_baseline_resume as fixture
from app.evaluation_stage import checkpoint_request
from app.providers import ProviderTimeout
from app.telemetry import record_usage


class ManualSandboxResumeTests(unittest.TestCase):
    def setUp(self):
        fixture.ResumeTests.setUp(self)
        delay=patch('app.evaluation.time.sleep')
        delay.start();self.addCleanup(delay.stop)
    tearDown = fixture.ResumeTests.tearDown

    def test_unknown_isolated_and_saved_answer_only_needs_judge_on_resume(self):
        self.runtime.fail=None
        baseline=self.runner.execute_baseline(*self.runner.start_baseline())
        exp=self.store.create_experiment(baseline['id'],'completed')
        config={**baseline['config'],'top_k':6};config.pop('run_target',None)
        self.store.save_candidate(exp,'R1-A',config,{'round':1,'candidate_label':'A'})
        cid=exp+'-R1-A';judge=self.runtime.judge;fault=[True];calls=[]
        def unknown(q,*args,**kwargs):
            if q=='Q2' and fault[0]:
                calls.append(q);record_usage({'provider':'DeepSeek','status':'unknown','requested_model':'fixture','request_execution_unknown':True})
                error=ProviderTimeout('fixture unknown');error.request_execution_unknown=True;raise error
            return judge(q,*args,**kwargs)
        with patch.object(self.runtime,'judge',side_effect=unknown):
            first=self.runner.run_candidate(cid,automatic=True)
            self.assertEqual(len(calls),6)
            self.assertTrue(self.runner.candidate_resume_plan(cid)['can_resume'])
            self.assertTrue(self.runner.candidate_resume_plan(cid,manual_resume=True)['can_resume'])
            self.assertTrue(first['result']['checkpoints']['Q2']['unknown_execution']['judge'])
            source=self.store.evaluation_run(first['result']['evaluation_run_id']);before=deepcopy(source)
            self.assertEqual(source['status'],'completed')
            self.assertEqual(first['result']['completed'],3)
            self.assertEqual(first['result']['technical_failed'],1)
            self.assertFalse(first['result']['evaluation_complete'])
            self.assertIsNone(first['result']['gates']['passed'])
            fault[0]=False
            recovered=self.runner.execute_candidate(*self.runner.start_candidate(cid,automatic=True,manual_resume=True))
            self.assertEqual(recovered['status'],'evaluated')
            self.assertTrue(recovered['result']['evaluation_complete'])
            self.assertEqual(recovered['result']['resume_source_id'],source['id'])
            self.assertEqual(self.store.evaluation_run(source['id']),before)
        self.assertEqual(self.runtime.answers.count('Q2'),2)  # one Baseline, one Candidate answer
        self.assertEqual(first['result']['request_accounting']['unknown_usage_events'],6)
        self.assertEqual(recovered['result']['request_accounting']['unknown_usage_events'],6)

    def test_unknown_embedding_or_rerank_resumes_49_completed_cases(self):
        from app.corpus import current_manifest, manifest_identity
        from fastapi.testclient import TestClient
        from api_fixture import main
        import threading
        items = [{'id':f'Q{i}','question':f'Q{i}','reference_answer':'事实',
                  'test_category':'positive' if i<=20 else 'ablation' if i<=30 else 'negative',
                  'negative_subtype':None if i<=30 else 'safety_critical' if i<=40 else 'prompt_injection','evidence':[]} for i in range(1,51)]
        snapshot = {'questions':items,'question_ids':[q['id'] for q in items],'corpus_fingerprint':manifest_identity(current_manifest())}
        with self.store.connection() as db:db.execute('UPDATE dataset_versions SET snapshot_json=?',(json.dumps(snapshot),))
        self.runtime.fail=None
        baseline=self.runner.execute_baseline(*self.runner.start_baseline())
        exp=self.store.create_experiment(baseline['id'],'completed')
        original=self.runtime.answer
        for label,missing in [('A',39),('B',49)]:
            with self.subTest(candidate=label):
                config={**baseline['config'],**({'top_k':6} if label=='A' else {'candidate_k':24})};config.pop('run_target',None)
                self.store.save_candidate(exp,'R1-'+label,config,{'round':1,'candidate_label':label})
                cid=exp+'-R1-'+label;fault=[True];rpc=[];answers=[]
                def answer(q,cfg):
                    answers.append(q)
                    for phase in ('embedding','rerank'):
                        def send():
                            rpc.append((q,phase))
                            if fault[0] and q==f'Q{missing}' and phase==('embedding' if label=='A' else 'rerank'):
                                record_usage({'provider':'Alibaba','status':'unknown','requested_model':phase,'request_execution_unknown':True})
                                error=ProviderTimeout('fixture unknown timeout');error.request_execution_unknown=True;raise error
                            record_usage({'provider':'Alibaba','status':'ok','requested_model':phase,'total_tokens':2})
                            return {'value':'saved '+phase}
                        checkpoint_request('Alibaba',phase,'https://fixture.invalid/'+phase,{'query':q},send)
                    return original(q,cfg)
                with patch.object(self.runtime,'answer',side_effect=answer):
                    partial=self.runner.run_candidate(cid,automatic=True)
                    source=self.store.evaluation_run(partial['result']['evaluation_run_id']);old=deepcopy(source)
                    cases=self.store.evaluation_case_results(source['id'])
                    self.assertEqual(len(cases),49)
                    self.assertEqual(source['status'],'completed')
                    self.assertEqual(source['result']['technical_failed'],1)
                    self.assertFalse(source['result']['evaluation_complete'])
                    self.assertIsNone(source['result']['gates']['passed'])
                    self.assertTrue(self.runner.candidate_resume_plan(cid)['can_resume'])
                    fault[0]=False
                    threads=set(threading.enumerate())
                    with patch.object(main,'store',self.store),patch.object(main,'ai_service',self.runtime),TestClient(main.app) as client:
                        preview=client.get('/api/candidates/'+cid+'/preflight').json()
                        self.assertTrue(preview['can_start'])
                        self.assertEqual(preview['resume_plan']['next_question_id'],f'Q{missing}')
                        response=client.post('/api/candidates/'+cid+'/run',headers={'Origin':'http://127.0.0.1:5174'},json={'authorize_provider':True})
                        self.assertEqual(response.status_code,201,response.text)
                        for worker in set(threading.enumerate())-threads:
                            if worker.name.endswith('(run)'):worker.join(10);self.assertFalse(worker.is_alive())
                    self.assertEqual(self.store.evaluation_run(source['id']),old)
                    recovered=self.store.candidate(cid)
                    self.assertEqual(recovered['status'],'evaluated')
                    self.assertEqual(recovered['result']['completed'],50)
                    self.assertTrue(recovered['result']['evaluation_complete'])
                    self.assertEqual(recovered['result']['resume_source_id'],source['id'])
                    self.assertEqual(recovered['result']['request_accounting']['unknown_usage_events'],6)
                    for case in cases:
                        self.assertEqual(answers.count(case['question_id']),1)
                    if label=='B':self.assertEqual(rpc.count(('Q49','embedding')),1)
        self.assertEqual(self.store.evaluation_run(baseline['id']),baseline)
