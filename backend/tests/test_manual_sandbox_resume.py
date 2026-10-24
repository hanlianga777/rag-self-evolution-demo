"""Manual consent may retry missing results; inherited unknown charges stay unknown."""
import json
import unittest
from copy import deepcopy
from unittest.mock import patch
import test_baseline_resume as fixture
from app.evaluation_stage import checkpoint_request
from app.providers import ProviderTimeout
from app.telemetry import record_usage


class ManualSandboxResumeTests(unittest.TestCase):
    setUp = fixture.ResumeTests.setUp
    tearDown = fixture.ResumeTests.tearDown

    def test_new_unknown_still_stops_and_saved_answer_only_needs_judge(self):
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
            second=self.runner.execute_candidate(*self.runner.start_candidate(cid,automatic=True,manual_resume=True))
            self.assertEqual(len(calls),2)
            self.assertEqual(second['result']['completed'],1)
            self.assertFalse(self.runner.candidate_resume_plan(cid)['can_resume'])
            self.assertTrue(self.runner.candidate_resume_plan(cid,manual_resume=True)['can_resume'])
            self.assertTrue(second['result']['checkpoints']['Q2']['unknown_execution']['judge'])
            fault[0]=False
            completed=self.runner.execute_candidate(*self.runner.start_candidate(cid,automatic=True,manual_resume=True))
        self.assertEqual(completed['result']['completed'],4)
        self.assertEqual(self.runtime.answers.count('Q2'),2)  # one Baseline, one Candidate answer
        self.assertGreater(completed['result']['request_accounting']['unknown_usage_events'],0)
        self.assertEqual(self.store.evaluation_run(first['result']['evaluation_run_id'])['status'],'partial')

    def test_a38_b48_manual_consent_completes_only_missing_work(self):
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
                    self.assertEqual(len(cases),missing-1)
                    self.assertFalse(self.runner.candidate_resume_plan(cid)['can_resume'])
                    with self.assertRaisesRegex(ValueError,'对账'):self.runner.start_candidate(cid)
                    fault[0]=False
                    threads=set(threading.enumerate())
                    with patch.object(main,'store',self.store),patch.object(main,'ai_service',self.runtime),TestClient(main.app) as client:
                        preview=client.get('/api/candidates/'+cid+'/preflight').json()
                        self.assertTrue(preview['can_start'])
                        self.assertEqual(preview['resume_plan']['next_question_id'],f'Q{missing}')
                        denied=client.post('/api/candidates/'+cid+'/run',headers={'Origin':'http://127.0.0.1:5174'})
                        self.assertEqual(denied.status_code,409)
                        response=client.post('/api/candidates/'+cid+'/run',headers={'Origin':'http://127.0.0.1:5174'},json={'authorize_provider':True})
                        self.assertEqual(response.status_code,201,response.text)
                        for worker in set(threading.enumerate())-threads:
                            if worker.name.endswith('(run)'):worker.join(10);self.assertFalse(worker.is_alive())
                    finished=self.store.evaluation_run(response.json()['id'])
                    self.assertEqual(finished['status'],'completed')
                    self.assertEqual(finished['result']['completed'],50)
                    candidate=self.store.candidate(cid)
                    self.assertEqual(candidate['status'],'evaluated')
                    self.assertIsInstance(candidate['result']['qualification']['qualified'],bool)
                    self.assertEqual(finished['result']['gates']['passed_count'],11)
                    self.assertEqual(finished['result']['manual_resume']['source_run_id'],source['id'])
                    self.assertGreater(finished['result']['request_accounting']['unknown_usage_events'],0)
                    self.assertEqual(self.store.evaluation_run(source['id']),old)
                    new=self.store.evaluation_case_results(finished['id'])
                    for case in cases:
                        saved=next(c for c in new if c['question_id']==case['question_id'])
                        self.assertEqual({k:v for k,v in saved.items() if k!='run_id'},{k:v for k,v in case.items() if k!='run_id'})
                        self.assertEqual(answers.count(case['question_id']),1)
                    if label=='B':self.assertEqual(rpc.count(('Q49','embedding')),1)
                    self.assertEqual(len(new),50)
        self.assertEqual(self.store.evaluation_run(baseline['id']),baseline)
