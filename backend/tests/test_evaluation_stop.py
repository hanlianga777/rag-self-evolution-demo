"""Cooperative cancellation with isolated SQLite and stub Providers."""
import unittest
from unittest.mock import patch
import test_baseline_resume as fixture
from app.evaluation import EvaluationRunner
from app.providers import ProviderTimeout

class StopTests(unittest.TestCase):
    setUp=fixture.ResumeTests.setUp
    tearDown=fixture.ResumeTests.tearDown

    def test_stop_during_generation_retains_answer_and_resumes_judge_only(self):
        runtime=fixture.Runtime(fail=None);runner=EvaluationRunner(self.store,runtime)
        key,items,config=runner.start_baseline(automatic=True)
        original=runtime.answer
        def answer(q,config):
            value=original(q,config)
            if q=='Q2':self.store.request_evaluation_stop(key)
            return value
        runtime.answer=answer
        result=runner.execute_baseline(key,items,config)
        self.assertEqual(result['status'],'partial');self.assertEqual(len(self.store.evaluation_case_results(key)),1)
        self.assertIn('execution',result['result']['checkpoints']['Q2']);self.assertEqual(runtime.judges,['Q1'])
        self.assertTrue(result['result']['stop_request']);self.assertFalse(self.store.claim_evaluation_worker(key))
        self.assertIsNone(runner.recover_run(key))
        runtime.answer=original
        child,items,config=runner.start_baseline(key,automatic=True)
        completed=runner.execute_baseline(child,items,config)
        self.assertEqual(completed['status'],'completed');self.assertEqual(runtime.answers.count('Q2'),1)
        self.assertEqual(runtime.answers.count('Q1'),1);self.assertEqual(completed['judge'],result['judge'])
        self.assertEqual(self.store.evaluation_run(key),result)

    def test_stop_during_backoff_prevents_retry(self):
        runtime=fixture.Runtime(fail=None);runner=EvaluationRunner(self.store,runtime)
        key,items,config=runner.start_baseline(automatic=True)
        def judge(*args,**kw):runtime.judges.append(args[0]);raise ProviderTimeout('fixture')
        runtime.judge=judge
        with patch('app.evaluation.time.sleep',side_effect=lambda _:self.store.request_evaluation_stop(key)):
            result=runner.execute_baseline(key,items,config)
        self.assertEqual(runtime.judges,['Q1']);self.assertEqual(result['status'],'partial')
        self.assertIn('execution',result['result']['checkpoints']['Q1'])

    def test_dead_worker_stops_idempotently_without_changing_completed_history(self):
        key,items,config=self.runner.start_baseline(automatic=True)
        result=self.store.evaluation_run(key)['result'];result['execution_owner_pid']=99999999
        self.store.update_evaluation_progress(key,result)
        with patch('app.governance.os.kill',side_effect=ProcessLookupError):stopped=self.store.request_evaluation_stop(key)
        self.assertEqual(stopped['status'],'partial');self.assertEqual(self.store.request_evaluation_stop(key),stopped)
        key,items,config=self.runner.start_baseline(automatic=True)
        self.runtime.fail=None
        complete=self.runner.execute_baseline(key,items,config)
        self.assertEqual(self.store.request_evaluation_stop(key),complete)

    def test_stop_api_missing_and_trusted_origin(self):
        from api_fixture import main
        from fastapi.testclient import TestClient
        client=TestClient(main.app)
        self.assertEqual(client.post('/api/evaluations/missing/stop',headers={'Origin':'https://untrusted.example'}).status_code,403)
        with patch.object(main,'store',self.store):
            self.assertEqual(client.post('/api/evaluations/missing/stop').status_code,404)
            key,_,_=self.runner.start_baseline(automatic=True)
            response=client.post(f'/api/evaluations/{key}/stop')
            self.assertEqual(response.status_code,200);self.assertEqual(response.json()['status'],'partial')

class SandboxStopTests(unittest.TestCase):
    import test_candidate_resume as candidate_fixture
    setUp=candidate_fixture.CandidateResumeTests.setUp
    tearDown=candidate_fixture.CandidateResumeTests.tearDown

    def test_sandbox_stop_retains_baseline_and_judge_checkpoint(self):
        original=self.runtime.judge
        key,items,config,candidate,baseline=self.runner.start_candidate(self.cid,automatic=True)
        def judge(*args,**kw):
            value=original(*args,**kw)
            self.store.request_evaluation_stop(key)
            return value
        self.runtime.judge=judge
        self.runner.execute_candidate(key,items,config,candidate,baseline)
        self.assertEqual(self.store.evaluation_run(key)['status'],'partial')
        self.assertEqual(len(self.store.evaluation_case_results(key)),1)
        self.assertEqual(self.store.candidate(self.cid)['status'],'failed')
        self.assertEqual(self.store.evaluation_run(self.baseline['id']),self.baseline)
        self.assertEqual(self.runtime.answers,['Q1'])
