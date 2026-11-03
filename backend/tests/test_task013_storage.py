"""Temporary SQLite only; no real Provider or user data."""
import json
import sqlite3
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import test_baseline_resume as fixture
from app.evaluation import EvaluationRunner
from app.providers import ProviderInvalidResponse


class StorageTests(unittest.TestCase):
    setUp = fixture.ResumeTests.setUp
    tearDown = fixture.ResumeTests.tearDown

    def test_connections_use_wal_and_long_busy_timeout(self):
        with self.store.connection() as c:
            self.assertEqual(c.execute('PRAGMA journal_mode').fetchone()[0], 'wal')
            self.assertGreaterEqual(c.execute('PRAGMA busy_timeout').fetchone()[0], 30000)

    def test_checkpoint_rows_preserve_history_and_write_only_changed_question(self):
        run, items, config = self.runner.start_baseline()
        result = self.store.evaluation_run(run)['result']
        result['checkpoints'] = {}
        sizes = []
        for i in range(50):
            result['checkpoints'][str(i)] = {'answer': '证据' * 40000, 'attempts': []}
            self.store.update_evaluation_progress(run, result)
            with self.store.connection() as c:
                sizes.append(c.execute('SELECT length(result_json) FROM evaluation_runs WHERE id=?', (run,)).fetchone()[0])
        self.assertLess(max(sizes), 2000)
        self.assertEqual(self.store.evaluation_run(run)['result']['checkpoints'], result['checkpoints'])
        with self.store.connection() as c:
            self.assertEqual(c.execute('SELECT count(*) FROM evaluation_checkpoints WHERE run_id=?', (run,)).fetchone()[0], 50)

    def test_three_invalid_judge_replies_are_corrected_without_regeneration(self):
        runtime = fixture.Runtime(fail=None)
        original = runtime.judge
        seen = []
        def judge(q, *args, **kwargs):
            if q == 'Q1' and len(seen) < 3:
                seen.append(q)
                raise ProviderInvalidResponse('answer quote is missing or not located', raw_provider_response='{}')
            return original(q, *args, **kwargs)
        runtime.judge = judge
        runner = EvaluationRunner(self.store, runtime)
        run, items, config = runner.start_baseline(automatic=True)
        with patch('app.evaluation_stage.time.sleep'):
            result = runner.execute_baseline(run, items, config)
        self.assertTrue(result['result']['evaluation_complete'])
        self.assertFalse(any(a.get('recorded_by_run_id','').endswith(':final-retry') for a in result['result']['checkpoints']['Q1']['attempts']))
        self.assertEqual(runtime.answers.count('Q1'), 1)
        self.assertEqual(len([a for a in result['result']['checkpoints']['Q1']['attempts'] if a['phase'] == 'judge']), 4)

    def test_saved_score_survives_transient_case_write_failure(self):
        runtime = fixture.Runtime(fail=None)
        runner = EvaluationRunner(self.store, runtime)
        run, items, config = runner.start_baseline(automatic=True)
        original = self.store.record_evaluation_case
        failures = []
        def save(*args, **kwargs):
            if not failures:
                failures.append(True)
                raise sqlite3.OperationalError('database is locked')
            return original(*args, **kwargs)
        with patch.object(self.store, 'record_evaluation_case', side_effect=save), patch('app.evaluation_stage.time.sleep'):
            result = runner.execute_baseline(run, items, config)
        self.assertTrue(result['result']['evaluation_complete'])
        self.assertEqual(runtime.answers.count('Q1'), 1)
        self.assertEqual(runtime.judges.count('Q1'), 1)

    def test_answer_replay_recovers_saved_executions_without_answer_calls(self):
        runtime=fixture.Runtime(fail=None)
        runner=EvaluationRunner(self.store,runtime)
        source=runner.execute_baseline(*runner.start_baseline(automatic=True))
        replay,items,executions=runner.start_replay(source['id'])
        runtime.answers.clear()
        result=self.store.evaluation_run(replay)['result']
        self.assertTrue(result.get('auto_recovery',{}).get('enabled'))
        result['execution_owner_pid']=99999999
        self.store.update_evaluation_progress(replay,result)
        with patch('app.governance.os.kill',side_effect=ProcessLookupError):
            finished=runner.recover_run(replay)
        self.assertTrue(finished['result']['evaluation_complete'])
        self.assertFalse(runtime.answers)

    def test_candidate_checkpoint_is_detached_but_detail_stays_readable(self):
        with self.store.connection() as c:
            c.execute("INSERT INTO experiments VALUES ('exp','baseline','completed','{}','now')")
            c.execute("INSERT INTO candidate_configs VALUES ('candidate','exp','generated','{}','{}','{}','now')")
        checkpoints={'Q1':{'answer':'证据'*100000}}
        self.store.finish_candidate('candidate','failed',{'checkpoints':checkpoints,'evaluation_complete':False,'error':'database is locked'})
        with self.store.connection() as c:
            raw=c.execute("SELECT result_json FROM candidate_configs WHERE id='candidate'").fetchone()[0]
        self.assertLess(len(raw),1000)
        self.assertEqual(self.store.candidate('candidate')['result']['checkpoints'],checkpoints)
        self.assertNotIn('checkpoints',self.store.experiment('exp',light=True)['candidates'][0]['result'])
        self.assertTrue(self.store.experiment('exp',light=True)['candidates'][0]['product_interruption'])

    def test_storage_migration_preserves_review_and_checkpoint_values(self):
        run,items,config=self.runner.start_baseline()
        original=self.store.evaluation_run(run)['result']
        original.update(checkpoints={'Q1':{'execution':{'answer':'原回答'},'attempts':[]}},
                        baseline_review={'complete':True,'cases':{'Q1':{'votes':[False,True,False]}}})
        with self.store.connection() as c:
            c.execute('UPDATE evaluation_runs SET result_json=? WHERE id=?',(json.dumps(original),run))
        self.store.migrate_evaluation_checkpoints()
        self.assertEqual(self.store.evaluation_run(run)['result'],original)
        self.assertNotIn('checkpoints',self.store.evaluation_run(run,light=True)['result'])
        self.assertNotIn('votes',self.store.evaluation_run(run,light=True)['result']['baseline_review']['cases']['Q1'])

    def test_completed_nonreusable_rpc_retries_storage_without_calling_provider(self):
        from app.evaluation_stage import perform_stage,checkpoint_request
        checkpoint={'attempts':[]}
        calls=[];failed=[]
        def state(*args,**kwargs):
            if any(r.get('status')=='completed' for r in checkpoint.get('provider_requests',{}).values()) and not failed:
                failed.append(True)
                raise sqlite3.OperationalError('database is locked')
        def action():
            def provider():calls.append(True);return {'answer':'saved'}
            return checkpoint_request('fixture','fixture','judge',{},provider,reuse=False)
        with patch('app.evaluation_stage.time.sleep'):
            value=perform_stage(checkpoint,'judge',action,'run',automatic=True,check_stop=lambda:None,on_state=state)
        self.assertEqual(value,{'answer':'saved'})
        self.assertEqual(len(calls),1)

    def test_transient_monitor_read_error_keeps_automatic_run_recoverable(self):
        runtime=fixture.Runtime(fail=None);runner=EvaluationRunner(self.store,runtime)
        run,items,config=runner.start_baseline(automatic=True)
        original=self.store.evaluation_run;failed=[]
        def read(key,**kwargs):
            if kwargs.get('light') and not failed:
                failed.append(True);raise OSError('temporary read failure')
            return original(key,**kwargs)
        with patch.object(self.store,'evaluation_run',side_effect=read):
            interrupted=runner.execute_baseline(run,items,config)
        self.assertEqual(interrupted['status'],'running')
        result=original(run)['result'];result['auto_recovery']['worker_thread']=-1
        self.store.update_evaluation_progress(run,result)
        completed=runner.recover_run(run)
        self.assertTrue(completed['result']['evaluation_complete'])

    def test_light_review_preserves_the_same_optimization_counts(self):
        from app.agent_inputs import baseline_review_summary
        run,items,config=self.runner.start_baseline()
        result=self.store.evaluation_run(run)['result']
        result.update(bad_case_count=2,calibration_import={'source':'fixture'},baseline_review={'complete':True})
        self.store.update_evaluation_progress(run,result)
        for q,status in [('Q1','confirmed_regression'),('Q2','fluctuation')]:
            self.store.save_job_checkpoint(run,'review:'+q,{'regression_review':{'status':status,'failed_votes':2 if q=='Q1' else 1,'total_votes':3,'runs':[{'execution':{'raw':'x'*100000}}]}})
        full=self.store.evaluation_run(run)
        light=self.store.evaluation_run(run,light=True)
        self.assertEqual(baseline_review_summary(light),baseline_review_summary(full))
        self.assertEqual(baseline_review_summary(light)['target_count'],1)
        self.assertNotIn('runs',light['result']['baseline_review']['cases']['Q1']['regression_review'])


if __name__ == '__main__':
    unittest.main()
