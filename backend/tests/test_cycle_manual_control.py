"""Manual stop/resume uses temporary SQLite and offline Providers only."""
import unittest
from copy import deepcopy
from unittest.mock import patch
from fastapi.testclient import TestClient
from api_fixture import main
from app.optimization_cycle import claim_cycle, run_until_qualified
import test_candidate_resume as candidate_fixture


class ManualCycleTests(unittest.TestCase):
    def setUp(self):
        candidate_fixture.CandidateResumeTests.setUp(self)
        self.runtime.provider=object()
    tearDown=candidate_fixture.CandidateResumeTests.tearDown

    def test_stop_then_explicit_cycle_resume_preserves_saved_cases_and_budget(self):
        key,items,config,candidate,baseline=self.runner.start_candidate(self.cid,automatic=True)
        original=self.runtime.judge
        def judge(*args,**kwargs):
            value=original(*args,**kwargs)
            self.store.request_evaluation_stop(key)
            return value
        self.runtime.judge=judge
        self.runner.execute_candidate(key,items,config,candidate,baseline)
        old=deepcopy(self.store.evaluation_run(key))
        self.assertEqual(self.store.experiment(self.exp)['evaluation_budget']['used'],1)
        self.runtime.judge=original
        claimed=claim_cycle(self.store,self.exp,current_round_only=True)
        self.assertIn(key,claimed['resume_stopped_runs'])
        result=run_until_qualified(self.store,self.runtime,self.exp,claimed=True)
        self.assertEqual(result['status'],'round_completed')
        self.assertEqual(self.store.candidate(self.cid)['status'],'evaluated')
        self.assertEqual(self.store.evaluation_run(key),old)
        self.assertEqual(self.runtime.answers,['Q1','Q2','Q3','Q4'])
        self.assertEqual(self.store.experiment(self.exp)['evaluation_budget']['used'],1)

    def test_cycle_stop_api_stops_active_sandbox_and_does_not_restart_it(self):
        claim_cycle(self.store,self.exp)
        key,items,config,candidate,baseline=self.runner.start_candidate(self.cid,automatic=True)
        old_baseline=deepcopy(self.store.evaluation_run(self.baseline['id']))
        client=TestClient(main.app)
        with patch.object(main,'store',self.store):
            denied=client.post(f'/api/experiments/{self.exp}/stop-cycle',headers={'Origin':'https://untrusted.example'})
            self.assertEqual(denied.status_code,403)
            response=client.post(f'/api/experiments/{self.exp}/stop-cycle')
            self.assertEqual(response.status_code,200,response.text)
            self.assertTrue(response.json()['stop_request'])
            self.assertEqual(client.post('/api/experiments/missing/stop-cycle').status_code,404)
        self.assertTrue(self.store.evaluation_run(key)['result']['stop_request'])
        self.runner.execute_candidate(key,items,config,candidate,baseline)
        result=run_until_qualified(self.store,self.runtime,self.exp,claimed=True)
        self.assertEqual(result['status'],'stopped')
        self.assertEqual(self.runtime.answers,[])
        self.assertEqual(self.store.evaluation_run(self.baseline['id']),old_baseline)

    def test_stop_during_last_price_check_does_not_wait_for_next_off_peak(self):
        from types import SimpleNamespace
        from app.paid_policy import guarded_begin
        from app.evaluation_stage import _request_checkpoint
        from app.optimization_cycle import check_cycle_stop,request_cycle_stop
        claim_cycle(self.store,self.exp)
        run=SimpleNamespace(request_policy={'kind':'off_peak_usd_cap_v1','database_path':str(self.store.database_path)})
        waits=[]
        def stop_once(_):
            if waits:raise AssertionError('停止请求未被处理')
            waits.append(True);request_cycle_stop(self.store,self.exp)
        token=_request_checkpoint.set(({},'agent',self.exp,lambda:None,lambda:check_cycle_stop(self.store,self.exp)))
        try:
            with patch('app.paid_schedule.schedule_status',return_value={'off_peak_only':True,'peak_now':True}), \
                 patch('app.paid_policy.time.sleep',side_effect=stop_once) as sleep:
                with self.assertRaises(InterruptedError):guarded_begin(run,'DeepSeek','fixture',{})
                self.assertEqual(sleep.call_count,1)
        finally:_request_checkpoint.reset(token)


if __name__=='__main__':unittest.main()
