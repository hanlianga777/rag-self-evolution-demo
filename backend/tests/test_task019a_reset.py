"""Delete only optimization history; keep protected formal records byte-for-byte."""
import json
import unittest
from pathlib import Path
import test_optimization_contract as contract

class ResetTests(unittest.TestCase):
    setUp=contract.OptimizationContractTests.setUp
    def test_online_backup_and_scoped_deletion_preserve_baseline_and_snapshots(self):
        from backend.scripts.task019a_reset_experiments import delete_optimization_history
        from app.paid_schedule import set_settings
        set_settings(self.store,True)
        baseline=self.store.evaluation_run('EVAL-test')
        exp=self.store.create_experiment('EVAL-test')
        self.store.save_candidate(exp,'R1-A',{}, {'candidate_label':'A','round':1})
        with self.store.connection() as db:
            row=db.execute('select * from evaluation_runs where id=?',('EVAL-test',)).fetchone()
            keys=list(row.keys());vals=list(row);vals[keys.index('id')]='sandbox';vals[keys.index('config_json')]=json.dumps({'run_target':'sandbox_candidate','candidate_id':exp+'-R1-A'})
            db.execute('insert into evaluation_runs values (%s)' % ','.join('?' for _ in keys),vals)
            vals[keys.index('id')]='replay';vals[keys.index('config_json')]='{"run_target":"baseline"}';vals[keys.index('result_json')]='{"judge_replay":{"source_run_id":"sandbox"}}'
            db.execute('insert into evaluation_runs values (%s)' % ','.join('?' for _ in keys),vals)
            db.execute('insert into evaluation_case_results(run_id,question_id,result_json) values (?,?,?)',('sandbox','Q1','{}'))
            db.execute('insert into job_checkpoints values (?,?,?)',('candidate:'+exp+'-R1-A','Q1','{}'))
            db.execute('insert into evaluation_checkpoints values (?,?,?)',('sandbox','Q1','{}'))
            db.execute('insert into agent_traces(experiment_id,status,result_json,created_at) values (?,?,?,?)',(exp,'completed','{}','now'))
            db.execute('CREATE TABLE baseline_designations(id INTEGER PRIMARY KEY,baseline_run_id TEXT,comparison_run_id TEXT,comparison_label TEXT,actor TEXT,reason TEXT,created_at TEXT)')
            db.execute('insert into baseline_designations(baseline_run_id,comparison_run_id,comparison_label,actor,reason,created_at) values (?,?,?,?,?,?)',('EVAL-test','replay','对照','fixture','fixture','now'))
            protected={table:[tuple(r) for r in db.execute('select * from '+table)] for table in ('dataset_versions','baseline_designations','production_versions')}
        result=delete_optimization_history(self.store,Path(self.directory.name)/'audit_backups')
        self.assertEqual(result['deleted']['experiments'],1)
        self.assertEqual(set(result['evaluation_ids']),{'sandbox','replay'})
        self.assertTrue(Path(result['backup_path']).is_file())
        self.assertEqual(self.store.evaluation_run('EVAL-test'),baseline)
        with self.store.connection() as db:
            for table,rows in protected.items():self.assertEqual([tuple(r) for r in db.execute('select * from '+table)],rows)
            for table in ('experiments','candidate_configs','agent_traces','job_checkpoints','evaluation_checkpoints'):
                self.assertEqual(db.execute('select count(*) from '+table).fetchone()[0],0)
        self.assertIsNone(self.store.baseline_designation()['comparison_run_id'])
