"""Offline fault injection. No real Provider, Corpus or user database."""
import unittest,json,tempfile
from pathlib import Path
from unittest.mock import patch
import test_baseline_resume as fixture
Runtime=fixture.Runtime
from app.providers import ProviderTimeout,ProviderInvalidResponse,DeepSeekProvider
from app.config import Settings
from app.evaluation import EvaluationRunner
from app.paid_run import PaidRun,controlled_run,accounting_only,paid_request
from app.telemetry import record_usage

class AutomaticRecoveryTests(unittest.TestCase):
    setUp=fixture.ResumeTests.setUp
    tearDown=fixture.ResumeTests.tearDown
    def test_judge_retry_reuses_answer_and_identity(self):
        runtime=Runtime(fail=None);original=runtime.judge;failed=False
        def judge(q,*args,**kwargs):
            nonlocal failed
            if q=='Q2' and not failed:failed=True;raise ProviderInvalidResponse('schema',raw_provider_response='{}')
            return original(q,*args,**kwargs)
        runtime.judge=judge;runner=EvaluationRunner(self.store,runtime)
        key,items,config=runner.start_baseline(automatic=True)
        identity=self.store.evaluation_run(key)['judge']['evaluation_identity']
        with patch('app.evaluation.time.sleep'):result=runner.execute_baseline(key,items,config)
        self.assertEqual(result['status'],'completed');self.assertEqual(runtime.answers.count('Q2'),1)
        self.assertEqual(result['judge']['evaluation_identity'],identity)
        self.assertEqual(result['result']['checkpoints']['Q2']['attempts'][1]['status'],'error')

    def test_accounting_ignores_budget_but_stops_on_unknown_usage(self):
        run=PaidRun(Path(self.tmp.name)/'audit.json',.001,{}, {},identity_check=lambda:{})
        with controlled_run(run),accounting_only():
            with paid_request('DeepSeek','fixture',{'max_tokens':999999}):record_usage({'status':'ok','provider':'DeepSeek','requested_model':'fixture','prompt_tokens':1000000,'completion_tokens':1000000})
            with self.assertRaisesRegex(RuntimeError,'Usage missing'):
                with paid_request('DeepSeek','fixture',{}):pass
            with self.assertRaisesRegex(RuntimeError,'stopped'):
                with paid_request('DeepSeek','fixture',{}):self.fail('Unknown Usage must stop before another request')
        self.assertEqual(len(run.calls),2);self.assertIsNone(run.calls[0]['upper_estimate_yuan'])
        self.assertEqual(run.calls[1]['status'],'unknown');self.assertTrue(run.stopped)

    def test_format_recovery_preserves_strict_judge_validation(self):
        provider=DeepSeekProvider(Settings('fixture','https://invalid','fixture'))
        with patch.object(provider,'complete',return_value='```json\n'+json.dumps({'correctness':4,'completeness':1,'faithfulness':1,'behavior_pass':True,'reason':'fixture'})+'\n```'):
            result=provider.judge('q','a','a');self.assertEqual(result['correctness'],4);self.assertEqual(result['format_recovery'],'markdown_fence')
        with patch.object(provider,'complete',return_value='{"correctness":4'):
            with self.assertRaises(ProviderInvalidResponse):provider.judge('q','a','a')

    def test_dead_worker_stops_unknown_inflight_without_replaying_completed_question(self):
        runtime=Runtime(fail=None);runner=EvaluationRunner(self.store,runtime)
        key,items,config=runner.start_baseline(automatic=True)
        case=runner._case_result(items[0],config);self.store.record_evaluation_case(key,items[0]['id'],case)
        execution=runtime.answer(items[1]['question'],config)
        result=self.store.evaluation_run(key)['result']
        result.update(execution_owner_pid=99999999,checkpoints={items[1]['id']:{'execution':execution,'attempts':[],'inflight':'judge'}})
        result['auto_recovery'].update(worker_token='crashed',worker_thread=-1)
        self.store.update_evaluation_progress(key,result)
        with patch('app.governance.os.kill',side_effect=ProcessLookupError):
            self.store.interrupt_evaluation_runs();self.assertEqual(self.store.evaluation_run(key)['status'],'queued')
            completed=runner.recover_run(key)
        self.assertEqual(completed['status'],'partial');self.assertEqual(runtime.answers.count('Q1'),1);self.assertEqual(runtime.answers.count('Q2'),1)
        self.assertIn('Unknown request',completed['error_message'])
        self.assertEqual(len(self.store.evaluation_case_results(key)),1)
        self.assertIn('execution',completed['result']['checkpoints']['Q2'])

    def test_same_worker_cannot_claim_twice_or_rejudge_completed_run(self):
        runtime=Runtime(fail=None);runner=EvaluationRunner(self.store,runtime)
        key,items,config=runner.start_baseline(automatic=True)
        self.assertTrue(self.store.claim_evaluation_worker(key));self.assertFalse(self.store.claim_evaluation_worker(key))
        self.assertEqual(runner.execute_baseline(key,items,config)['status'],'running');self.assertFalse(runtime.answers)

    def test_network_recovers_but_provider_account_failure_is_terminal(self):
        from app.providers import ProviderAPIError
        for error in [ProviderTimeout('fixture timeout'),ProviderAPIError('fixture account',status_code=402)]:
            runtime=Runtime(fail=None);judge=runtime.judge;calls=[]
            def flaky(q,*args,**kw):
                calls.append(q)
                if q=='Q2' and calls.count(q)==1:raise error
                return judge(q,*args,**kw)
            runtime.judge=flaky;runner=EvaluationRunner(self.store,runtime);key,items,config=runner.start_baseline(automatic=True)
            with patch('app.evaluation.time.sleep'):result=runner.execute_baseline(key,items,config)
            self.assertEqual(result['status'],'completed' if isinstance(error,ProviderTimeout) else 'partial')
            self.assertEqual(runtime.answers.count('Q2'),1)

    def test_repeated_invalid_schema_stops_with_raw_audit_not_completed(self):
        runtime=Runtime(fail=None);runner=EvaluationRunner(self.store,runtime)
        runtime.judge=lambda *_a,**_kw:(_ for _ in ()).throw(ProviderInvalidResponse('fixture schema',raw_provider_response='{}'))
        key,items,config=runner.start_baseline(automatic=True)
        with patch('app.evaluation.time.sleep'):result=runner.execute_baseline(key,items,config)
        self.assertEqual(result['status'],'partial');checkpoint=result['result']['checkpoints']['Q1']
        errors=[a for a in checkpoint['attempts'] if a['status']=='error']
        self.assertEqual(len(errors),2);self.assertEqual(errors[-1]['raw_provider_response'],'{}');self.assertIn('execution',checkpoint)

    def test_long_task_is_not_stopped_by_elapsed_time(self):
        import itertools
        runner=EvaluationRunner(self.store,Runtime(fail=None));key,items,config=runner.start_baseline(automatic=True)
        with patch('app.evaluation.time.perf_counter',side_effect=itertools.count(0,1300)):
            result=runner.execute_baseline(key,items,config)
        self.assertEqual(result['status'],'completed');self.assertIsNone(result['result']['runtime_limits']['round_total_seconds'])

    def test_score_checkpoint_avoids_duplicate_judge_after_persistence_failure(self):
        runtime=Runtime(fail=None);runner=EvaluationRunner(self.store,runtime);key,items,config=runner.start_baseline(automatic=True)
        with patch.object(self.store,'record_evaluation_case',side_effect=OSError('fixture disk')):
            first=runner.execute_baseline(key,items,config)
        self.assertEqual(first['status'],'partial');self.assertIn('scored_result',first['result']['checkpoints']['Q1'])
        child,items,config=runner.start_baseline(key,automatic=True);result=runner.execute_baseline(child,items,config)
        self.assertEqual(result['status'],'completed');self.assertEqual(runtime.judges.count('Q1'),1);self.assertEqual(runtime.answers.count('Q1'),1)

    def test_partial_http_body_is_recovered_only_when_complete_json(self):
        import http.client
        from app.telemetry import collect_usage
        class Response:
            def __enter__(self):return self
            def __exit__(self,*_a):pass
            def read(self):raise http.client.IncompleteRead(json.dumps({'choices':[{'message':{'content':'回答'},'finish_reason':'stop'}],'usage':{'prompt_tokens':12,'completion_tokens':4}}).encode(),2)
        provider=DeepSeekProvider(Settings('fixture','https://invalid','fixture'))
        with patch('app.providers.urllib.request.urlopen',return_value=Response()),collect_usage() as usage:
            result=provider.complete_with_metrics('s','u')
        self.assertEqual(result['content'],'回答');self.assertEqual(usage[0]['completion_tokens'],4)

    def test_truncated_finish_reason_retains_real_usage_and_raw_response(self):
        from test_live_services import FakeResponse
        from app.telemetry import collect_usage
        provider=DeepSeekProvider(Settings('fixture','https://invalid','fixture'))
        with patch('app.providers.urllib.request.urlopen',return_value=FakeResponse({'choices':[{'message':{'content':'{"correctness":4'},'finish_reason':'length'}],'usage':{'prompt_tokens':10,'completion_tokens':20}})),collect_usage() as usage:
            with self.assertRaises(ProviderInvalidResponse) as raised:provider.complete_with_metrics('s','u')
        self.assertEqual(raised.exception.response_metadata['finish_reason'],'length');self.assertEqual(usage[0]['completion_tokens'],20)
        self.assertEqual(raised.exception.raw_provider_response,'{"correctness":4')

    def test_startup_does_not_auto_authorize_legacy_partial_or_duplicate_live_owner(self):
        from api_fixture import main
        key,items,config=EvaluationRunner(self.store,Runtime(fail=None)).start_baseline(automatic=True)
        self.assertTrue(self.store.claim_evaluation_worker(key));self.store.interrupt_evaluation_runs()
        with patch.object(main,'store',self.store),patch('app.main.threading.Thread') as worker:
            main.recover_authorized_evaluations();worker.assert_not_called()
        result=self.store.evaluation_run(key)['result'];self.store.finish_evaluation_run(key,'partial',result,'fixture terminal')
        with patch.object(main,'store',self.store),patch('app.main.threading.Thread') as worker:
            main.recover_authorized_evaluations();worker.assert_not_called()

    def test_api_progress_comes_from_rows_not_stale_cached_count(self):
        from api_fixture import main
        runner=EvaluationRunner(self.store,Runtime(fail=None));key,items,config=runner.start_baseline(automatic=True)
        self.store.record_evaluation_case(key,items[0]['id'],runner._case_result(items[0],config))
        run=self.store.evaluation_run(key);run['result']['completed']=999
        with patch.object(main,'store',self.store):visible=main.persisted_evaluation_progress(run)
        self.assertEqual(visible['result']['completed'],1);self.assertEqual(visible['result']['total'],4)

    def test_wrapped_retrieval_timeout_retries_but_quota_and_config_do_not(self):
        from app.providers import retryable_error,ProviderAPIError
        error=RuntimeError('retrieval failure');error.__cause__=TimeoutError('fixture')
        self.assertTrue(retryable_error(error));self.assertFalse(retryable_error(ValueError('identity changed')))
        self.assertFalse(retryable_error(ProviderAPIError('quota',status_code=429,raw_provider_response='{"error":{"code":"insufficient_quota"}}')))

    def test_known_cost_above_budget_is_recorded_without_execution_block(self):
        prices={'fixture':{'provider':'DeepSeek','input':100.,'output':100.,'max_output':1}}
        paid=PaidRun(Path(self.tmp.name)/'above-budget.json',.001,prices,{},identity_check=lambda:{})
        with controlled_run(paid),accounting_only(),paid_request('DeepSeek','fixture',{'max_tokens':99999}):
            record_usage({'provider':'DeepSeek','requested_model':'fixture','status':'ok','prompt_tokens':1000000,'completion_tokens':1000000})
        self.assertGreater(paid.spent,paid.budget);self.assertEqual(paid.calls[0]['status'],'ok')
        self.assertFalse(json.loads(paid.path.read_text())['budget_enforcement'])
