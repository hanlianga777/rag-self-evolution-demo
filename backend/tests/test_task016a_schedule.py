"""Offline price boundaries, durable pause and next-question recovery."""
import json
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import test_baseline_resume as fixture
from app.evaluation import EvaluationRunner


class ScheduleTests(unittest.TestCase):
    setUp = fixture.ResumeTests.setUp
    tearDown = fixture.ResumeTests.tearDown

    def test_snapshot_windows_and_toronto_dst(self):
        from app.paid_schedule import schedule_status
        prices = {'peak_hours_utc': [[1, 4], [6, 10]], 'peak_weekdays': [0, 1, 2, 3, 4]}
        with patch('app.paid_schedule.price_config', return_value=prices):
            status = schedule_status(self.store, at=datetime(2026, 11, 4, 1, 0, tzinfo=timezone.utc))
            self.assertTrue(status['peak_now'])
            self.assertEqual(status['resume_at_toronto'], '23:00')
            self.assertFalse(schedule_status(self.store, at=datetime(2026, 11, 4, 4, tzinfo=timezone.utc))['peak_now'])
            self.assertFalse(schedule_status(self.store, at=datetime(2026, 11, 7, 2, tzinfo=timezone.utc))['peak_now'])
            prices.update(peak_hours_utc=[[12, 13]], peak_weekdays=[2])
            self.assertTrue(schedule_status(self.store, at=datetime(2026, 11, 4, 12, tzinfo=timezone.utc))['peak_now'])
            self.assertFalse(schedule_status(self.store, at=datetime(2026, 11, 4, 1, tzinfo=timezone.utc))['peak_now'])

    def test_cross_start_finish_question_pause_then_cross_end(self):
        from app import paid_schedule as schedule
        clock = [datetime(2026, 11, 4, 0, 59, tzinfo=timezone.utc)]
        calls, pauses = [], []
        runtime = fixture.Runtime(fail=None)
        original = runtime.answer
        def answer(q, config):
            calls.append(q)
            if q == 'Q1': clock[0] = datetime(2026, 11, 4, 1, tzinfo=timezone.utc)
            return original(q, config)
        runtime.answer = answer
        runner = EvaluationRunner(self.store, runtime)
        key, items, config = runner.start_baseline(automatic=True)
        def sleep(_seconds):
            run = self.store.evaluation_run(key)
            pauses.append(run['result']['price_pause'])
            self.assertEqual(calls, ['Q1'])
            self.assertEqual(runtime.judges, ['Q1'])
            self.assertEqual(len(self.store.evaluation_case_results(key)), 1)
            clock[0] = datetime(2026, 11, 4, 4, tzinfo=timezone.utc)
        with patch.object(schedule, 'utc_now', side_effect=lambda: clock[0]), patch.object(schedule.time, 'sleep', side_effect=sleep):
            result = runner.execute_baseline(key, items, config)
        self.assertEqual(result['status'], 'completed')
        self.assertTrue(result['result']['evaluation_complete'])
        self.assertEqual(calls, ['Q1', 'Q2', 'Q3', 'Q4'])
        self.assertEqual(runtime.judges, calls)
        self.assertTrue(pauses[0]['paused'])
        self.assertFalse(result['result']['price_pause']['paused'])

    def test_pause_before_start_restart_and_resume_from_next_question(self):
        from app import paid_schedule as schedule
        clock = [datetime(2026, 11, 4, 0, 59, tzinfo=timezone.utc)]
        runtime = fixture.Runtime(fail=None)
        original = runtime.judge
        def judge(*args, **kwargs):
            result = original(*args, **kwargs)
            clock[0] = datetime(2026, 11, 4, 1, tzinfo=timezone.utc)
            return result
        runtime.judge = judge
        runner = EvaluationRunner(self.store, runtime)
        key, items, config = runner.start_baseline(automatic=True)
        with patch.object(schedule, 'utc_now', side_effect=lambda: clock[0]), patch.object(schedule.time, 'sleep', side_effect=SystemExit('simulated backend exit')):
            with self.assertRaises(SystemExit): runner.execute_baseline(key, items, config)
        paused = self.store.evaluation_run(key)
        self.assertTrue(paused['result']['price_pause']['paused'])
        self.assertEqual(runtime.answers, ['Q1'])
        # Simulate a dead process; re-open persisted SQLite, not a database copy.
        from app.governance import GovernanceStore
        reopened = GovernanceStore(self.store.database_path, migrate=False)
        with reopened.connection() as db:
            result = json.loads(db.execute('SELECT result_json FROM evaluation_runs WHERE id=?', (key,)).fetchone()[0])
            result['execution_owner_pid'] = 99999999
            db.execute('UPDATE evaluation_runs SET result_json=? WHERE id=?', (json.dumps(result), key))
        runtime.judge = original
        clock[0] = datetime(2026, 11, 4, 4, tzinfo=timezone.utc)
        with patch.object(schedule, 'utc_now', side_effect=lambda: clock[0]):
            result = EvaluationRunner(reopened, runtime).recover_run(key)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(runtime.answers, ['Q1', 'Q2', 'Q3', 'Q4'])
        self.assertEqual(runtime.judges, runtime.answers)

    def test_new_task_waits_without_any_calls_and_override_is_task_scoped(self):
        from app import paid_schedule as schedule
        at = datetime(2026, 11, 4, 1, tzinfo=timezone.utc)
        with patch.object(schedule, 'utc_now', return_value=at):
            schedule.set_run_now(self.store, 'evaluation:first')
            self.assertFalse(schedule.pause_state(self.store, 'evaluation:first')['paused'])
            self.assertTrue(schedule.pause_state(self.store, 'evaluation:second')['paused'])
            runner = EvaluationRunner(self.store, fixture.Runtime(fail=None))
            key, items, config = runner.start_baseline(automatic=True)
            with patch.object(schedule.time, 'sleep', side_effect=SystemExit):
                with self.assertRaises(SystemExit): runner.execute_baseline(key, items, config)
            self.assertEqual(runner.runtime.answers, [])
            self.assertTrue(self.store.evaluation_run(key)['result']['price_pause']['paused'])
            schedule.set_settings(self.store, False)
            self.assertFalse(schedule.pause_state(self.store, 'evaluation:second')['paused'])
        self.assertFalse(schedule.schedule_status(self.store)['off_peak_only'])

    def test_settings_api_default_persistence_and_explicit_override_ack(self):
        from api_fixture import main
        from fastapi.testclient import TestClient
        from app import paid_schedule as schedule
        client = TestClient(main.app)
        self.addCleanup(client.close)
        headers = {'Origin': 'http://127.0.0.1:5174'}
        runtime = fixture.Runtime(fail=None)
        key, _, _ = EvaluationRunner(self.store, runtime).start_baseline(automatic=True)
        with patch.object(main, 'store', self.store), patch.object(schedule, 'utc_now', return_value=datetime(2026,11,4,1,tzinfo=timezone.utc)):
            self.assertTrue(client.get('/api/runtime-settings').json()['off_peak_only'])
            response = client.post('/api/runtime-settings/run-now', json={'evaluation_id': key}, headers=headers)
            self.assertEqual(response.status_code, 422)
            response = client.post('/api/runtime-settings/run-now', json={'evaluation_id': key, 'acknowledge_peak_price': True}, headers=headers)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertFalse(schedule.pause_state(self.store, 'evaluation:'+key)['paused'])
            response = client.post('/api/runtime-settings', json={'off_peak_only': False}, headers=headers)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertFalse(client.get('/api/runtime-settings').json()['off_peak_only'])

    def test_answer_replay_waits_and_resumes_without_generation(self):
        from app import paid_schedule as schedule
        runtime=fixture.Runtime(fail=None)
        runner=EvaluationRunner(self.store,runtime)
        with patch.object(schedule,'utc_now',return_value=datetime(2026,11,7,12,tzinfo=timezone.utc)):
            source=runner.run_baseline()
        runtime.answers.clear();runtime.judges.clear()
        key,items,executions=runner.start_replay(source['id'])
        clock=[datetime(2026,11,4,1,tzinfo=timezone.utc)]
        def sleep(_seconds):
            self.assertEqual(runtime.answers,[])
            self.assertEqual(runtime.judges,[])
            saved=self.store.evaluation_run(key)['result']
            self.assertTrue(saved['price_pause']['paused'])
            self.assertTrue(saved['auto_recovery'].get('worker_token'))
            clock[0]=datetime(2026,11,4,4,tzinfo=timezone.utc)
        with patch.object(schedule,'utc_now',side_effect=lambda:clock[0]),patch.object(schedule.time,'sleep',side_effect=sleep):
            result=runner.execute_replay(key,items,executions)
        self.assertEqual(result['status'],'completed')
        self.assertTrue(result['result']['evaluation_complete'])
        self.assertEqual(runtime.answers,[])
        self.assertEqual(runtime.judges,['Q1','Q2','Q3','Q4'])

    def test_d_scheduler_recovers_before_request_and_never_repeats_unknown(self):
        from app import paid_schedule as schedule
        from app.history import has_active_jobs,require_idle
        experiment_id=self.store.create_experiment('fixture-base')
        with self.store.connection() as db:
            db.execute('UPDATE experiments SET result_json=? WHERE id=?',(json.dumps({'report_confirmation':{'winner_id':'winner'}}),experiment_id))
        schedule.save_composite_schedule(self.store,experiment_id,status='running',owner_pid=99999999)
        with self.store.connection() as db:
            self.assertTrue(has_active_jobs(db))
            with self.assertRaises(ValueError):require_idle(db)
        with patch.object(schedule,'utc_now',return_value=datetime(2026,11,7,12,tzinfo=timezone.utc)),patch.object(self.store,'create_composite',return_value={'status':'generated'}) as composite:
            schedule.recover_scheduled_composites(self.store,object())
            worker=schedule._composite_workers[(str(self.store.database_path),experiment_id)]
            worker.join(3)
            self.assertFalse(worker.is_alive())
            composite.assert_called_once()
            schedule.recover_scheduled_composites(self.store,object())
            self.assertEqual(composite.call_count,1)
        state=self.store.experiment(experiment_id)['result']['composite_schedule']
        self.assertEqual(state['status'],'completed')
        with self.store.connection() as db:
            result=json.loads(db.execute('SELECT result_json FROM experiments WHERE id=?',(experiment_id,)).fetchone()[0])
            result['composite']={'status':'analyzing','provider_calls':1}
            result['composite_schedule'].update(status='running',owner_pid=99999999)
            db.execute('UPDATE experiments SET result_json=? WHERE id=?',(json.dumps(result),experiment_id))
        with patch.object(self.store,'create_composite') as composite:
            schedule.recover_scheduled_composites(self.store,object())
            composite.assert_not_called()
        self.assertEqual(self.store.experiment(experiment_id)['result']['composite_schedule']['status'],'unknown')

    def test_calibration_pauses_before_judge_and_skips_saved_result(self):
        from app import paid_schedule as schedule
        from scripts.judge_calibration import run_calibration
        from types import SimpleNamespace
        from unittest.mock import Mock
        source={'id':'saved-source','dataset_snapshot_json':json.dumps({'corpus_fingerprint':'same'})}
        plan={'judge':{},'new_evaluation_identity':'same'}
        state={'plan':plan,'cases':{}}
        runner=SimpleNamespace(store=self.store,_require_generation_contract=lambda *_:None,
            snapshot_items=lambda *_:[{'id':'q'}],score_execution=Mock(return_value={'passed':True}))
        clock=[datetime(2026,11,4,1,tzinfo=timezone.utc)]
        def sleep(_seconds):
            self.assertTrue(state['_job']['price_pause']['paused'])
            runner.score_execution.assert_not_called()
            clock[0]=datetime(2026,11,4,4,tzinfo=timezone.utc)
        with patch('scripts.judge_calibration.calibration_plan',return_value=plan),patch('app.evaluation_contract.policy_current',return_value=True),patch('app.corpus.manifest_identity',return_value='same'),patch('scripts.judge_calibration.saved_case_execution',return_value={'answer':'saved answer','retrieval_trace':{'final':[]}}),patch.object(schedule,'utc_now',side_effect=lambda:clock[0]),patch.object(schedule.time,'sleep',side_effect=sleep):
            run_calibration(runner,source,[{'question_id':'q'}],'low',state,lambda *_a,**_k:None)
            run_calibration(runner,source,[{'question_id':'q'}],'low',state,lambda *_a,**_k:None)
        runner.score_execution.assert_called_once()
        self.assertTrue(state['complete'])

    def test_cycle_lists_agent_retry_pause_without_changing_stopped_tasks(self):
        from app import paid_schedule as schedule
        key=self.store.create_experiment('fixture-base')
        pause={'paused':True,'resume_at_toronto':'23:00'}
        result={'optimization_cycle':{'status':'running','price_pause':{'paused':False}},'price_pause':pause}
        with self.store.connection() as db:
            db.execute('UPDATE experiments SET result_json=? WHERE id=?',(json.dumps(result),key))
        rows=schedule.active_pauses(self.store)
        self.assertEqual(rows,[{'task_label':'Agent 优化循环','price_pause':pause,'target':{'experiment_id':key}}])
        from api_fixture import main
        from fastapi.testclient import TestClient
        result['optimization_cycle']['status']='failed'
        with self.store.connection() as db:
            db.execute("UPDATE experiments SET status='failed',result_json=? WHERE id=?",(json.dumps(result),key))
        with patch.object(main,'store',self.store):
            client=TestClient(main.app)
            try:
                response=client.post('/api/runtime-settings/run-now',json={'experiment_id':key,'acknowledge_peak_price':True},headers={'Origin':'http://127.0.0.1:5174'})
                self.assertEqual(response.status_code,409)
            finally:client.close()
        schedule.set_run_now(self.store,'cycle:'+key)
        with patch.object(schedule,'utc_now',return_value=datetime(2026,11,4,1,tzinfo=timezone.utc)):
            self.assertTrue(schedule.pause_state(self.store,'agent:'+key)['paused'])
            result['optimization_cycle']['status']='running'
            with self.store.connection() as db:
                db.execute('UPDATE experiments SET result_json=? WHERE id=?',(json.dumps(result),key))
            self.assertFalse(schedule.pause_state(self.store,'agent:'+key)['paused'])


class DiagnosticScheduleTests(unittest.TestCase):
    def test_two_requests_cannot_own_same_diagnostic_authorization(self):
        from app import evidence_resolver as resolver
        from app.governance import GovernanceStore
        import tempfile,threading
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory:
            store=GovernanceStore(Path(directory)/'fixture.db')
            entered,release=threading.Event(),threading.Event()
            def work(*_args,**_kwargs):
                entered.set();release.wait(3)
                return {'provider_calls':0}
            args=dict(expected_binding='fixture',authorization_id='same',max_calls=1)
            with patch.object(resolver,'_execute_diagnostic_batch',side_effect=work) as execute:
                thread=threading.Thread(target=lambda:resolver.execute_diagnostic_batch(store,'fixture',object(),**args))
                thread.start()
                try:
                    self.assertTrue(entered.wait(2))
                    with self.assertRaisesRegex(ValueError,'正在运行'):
                        resolver.execute_diagnostic_batch(store,'fixture',object(),**args)
                    self.assertEqual(execute.call_count,1)
                finally:release.set();thread.join(3)
                self.assertFalse(thread.is_alive())

    def test_diagnostic_pause_restart_uses_saved_authorization(self):
        from test_agent_closed_loop import BatchAndReplayTests
        from app import evidence_resolver as resolver, paid_schedule as schedule
        from app.diagnostic_evidence import digest
        from types import SimpleNamespace
        store,run,snapshot,q,case,chunks,fixture=BatchAndReplayTests.setup_saved(self)
        store.finish_evaluation_run(run,'completed',{'evaluation_complete':True})
        binding={'run_id':run,'question_ids':[q['id']],'requests':['fixture-request']}
        calls=[]
        def semantic(payload):
            calls.append(payload)
            return fixture.semantic(payload)
        runtime=SimpleNamespace(model='fixture',resolve_diagnostic=semantic)
        args=dict(question_ids=[q['id']],expected_binding=digest(binding),authorization_id='offline-authorization',max_calls=1)
        with patch.object(resolver,'batch_inputs',return_value=([q['id']],chunks,'new-corpus',binding)),patch.object(schedule,'utc_now',return_value=datetime(2026,11,4,1,tzinfo=timezone.utc)),patch.object(schedule.time,'sleep',side_effect=SystemExit):
            with self.assertRaises(SystemExit):resolver.execute_diagnostic_batch(store,run,runtime,**args)
        self.assertEqual(calls,[])
        saved=store.job_checkpoint(run,'diagnostic-batch:offline-authorization')
        self.assertTrue(saved['price_pause']['paused'])
        saved['owner_pid']=99999999
        store.save_job_checkpoint(run,'diagnostic-batch:offline-authorization',saved)
        with patch.object(resolver,'batch_inputs',return_value=([q['id']],chunks,'new-corpus',binding)),patch.object(schedule,'utc_now',return_value=datetime(2026,11,4,4,tzinfo=timezone.utc)):
            resolver.recover_diagnostic_batches(store,runtime)
            import time
            for _ in range(100):
                saved=store.job_checkpoint(run,'diagnostic-batch:offline-authorization')
                if saved['status'] not in {'running','waiting'}:break
                time.sleep(.01)
        self.assertEqual(saved['status'],'completed',saved)
        self.assertEqual(len(calls),1)
        with self.assertRaisesRegex(ValueError,'不能重复调用'):
            with patch.object(resolver,'batch_inputs',return_value=([q['id']],chunks,'new-corpus',binding)):
                resolver.execute_diagnostic_batch(store,run,runtime,**args)


if __name__ == '__main__': unittest.main()
