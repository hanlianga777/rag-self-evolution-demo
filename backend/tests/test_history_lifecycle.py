"""Isolated lifecycle tests; never operate on the real database or Providers."""
import json,tempfile,unittest
from pathlib import Path
from app.governance import GovernanceStore
from app.history import reset_experiments, prune_history

class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.store=GovernanceStore(Path(self.tmp.name)/'test.db')
        with self.store.connection() as c:c.execute('CREATE TABLE demo_state(key TEXT PRIMARY KEY,value TEXT)')

    def test_reset_retains_parameters_but_never_a_release_or_seed(self):
        config=self.store.active_production()['config']
        reset_experiments(self.store)
        for table in ['questions','dataset_versions','evaluation_runs','experiments','approvals','demo_state']:
            with self.store.connection() as c:self.assertEqual(c.execute('select count(*) from '+table).fetchone()[0],0,table)
        active=self.store.active_production()
        self.assertEqual(active['config'],config)
        self.assertEqual(active['provenance'],'bootstrap')
        self.assertIsNone(active['evaluation_run_id']);self.assertIsNone(active['approval_id'])
        again=GovernanceStore(self.store.database_path)
        self.assertEqual(again.questions(),[])
        self.assertEqual(len(again.production_versions()),1)

    def test_reset_refuses_active_work_without_partial_deletion(self):
        with self.store.connection() as c:c.execute("INSERT INTO experiments VALUES ('busy','B','generating','{}','2026')")
        n=len(self.store.questions())
        with self.assertRaisesRegex(ValueError,'活动'):reset_experiments(self.store)
        self.assertEqual(len(self.store.questions()),n)

    def test_retention_deletes_whole_run_and_protects_referenced_old_run(self):
        reset_experiments(self.store)
        with self.store.connection() as c:
            for n in range(53):
                rid=f'E{n:03}'
                c.execute("INSERT INTO evaluation_runs VALUES (?,'completed','real','real',NULL,'{}','{}','{}','{}',NULL,?,?)",(rid,f'{n:03}',f'{n:03}'))
                for q in range(100):c.execute('INSERT INTO evaluation_case_results(run_id,question_id,result_json) VALUES (?,?,?)',(rid,str(q),'{}'))
            c.execute("UPDATE production_versions SET evaluation_run_id='E000'")
        prune_history(self.store)
        with self.store.connection() as c:
            self.assertEqual(c.execute('select count(*) from evaluation_runs').fetchone()[0],51)
            self.assertEqual(c.execute("select count(*) from evaluation_case_results where run_id='E000'").fetchone()[0],100)
            self.assertEqual(c.execute("select count(*) from evaluation_case_results where run_id='E052'").fetchone()[0],100)
            self.assertEqual(c.execute("select count(*) from evaluation_case_results where run_id='E001'").fetchone()[0],0)

    def test_recent_monitoring_trigger_keeps_its_old_experiment_dependency(self):
        reset_experiments(self.store)
        with self.store.connection() as c:
            c.execute("INSERT INTO monitoring_events(id,question,answer,bad_case,severity,determinable,created_at) VALUES ('M','q','a',1,'ordinary',1,'now')")
            for n in range(52):
                c.execute("INSERT INTO experiments VALUES (?,'B','completed','{}',?)",(f'X{n:03}',f'{n:03}'))
            c.execute("INSERT INTO optimization_triggers VALUES ('T','manual','M','completed','human','now','now','X000')")
            c.execute("INSERT INTO approvals(gate,target_id,decision,actor,created_at) VALUES ('monitoring_trigger','T','approved','human','now')")
        prune_history(self.store)
        with self.store.connection() as c:
            self.assertEqual(c.execute("SELECT count(*) FROM approvals WHERE target_id='T'").fetchone()[0],1)
            self.assertEqual(c.execute("SELECT count(*) FROM experiments WHERE id='X000'").fetchone()[0],1)
            self.assertEqual(c.execute('SELECT count(*) FROM optimization_triggers t LEFT JOIN experiments e ON e.id=t.optimization_run_id WHERE t.optimization_run_id IS NOT NULL AND e.id IS NULL').fetchone()[0],0)

    def test_unassigned_business_pool_and_import_receipt_remain_an_atomic_object(self):
        reset_experiments(self.store)
        ids=self.store.save_business_candidates([{'question':'业务导入问题','test_category':'negative','import_row':2}],'input.xlsx','hash')
        prune_history(self.store)
        self.assertIsNotNone(self.store.question(ids[0]))
        self.assertEqual(self.store.business_import_receipt('hash')['question_ids'],ids)

    def test_live_revision_preview_keeps_old_whole_workset(self):
        reset_experiments(self.store)
        ids=self.store.save_business_candidates([{'question':'修订问题','test_category':'positive','import_row':2}],'input.xlsx','hash')
        with self.store.connection() as c:
            for n in range(52):
                c.execute("INSERT INTO golden_generation_runs VALUES (?,'{}','fixture','completed',?,?)",(f'G{n:03}',json.dumps(ids if n==0 else []),f'{n:03}'))
            c.execute('UPDATE questions SET raw_json=? WHERE id=?',(json.dumps({'generation_run_id':'G000'}),ids[0]))
            c.execute("INSERT INTO candidate_revision_runs VALUES ('REV','G000','preview_ready','{}','0','0')")
        prune_history(self.store)
        self.assertIsNotNone(self.store.question(ids[0]))
        with self.store.connection() as c:
            self.assertEqual(c.execute("SELECT count(*) FROM golden_generation_runs WHERE id='G000'").fetchone()[0],1)

    def test_pending_agent_contexts_are_not_completed_history(self):
        reset_experiments(self.store)
        with self.store.connection() as c:
            for n in range(52):c.execute("INSERT INTO experiments VALUES (?,'baseline','pending_agent','{}',?)",(str(n),str(n)))
        prune_history(self.store)
        with self.store.connection() as c:self.assertEqual(c.execute('SELECT count(*) FROM experiments').fetchone()[0],52)

    def test_answer_replay_keeps_source_evaluation_outside_history_limit(self):
        reset_experiments(self.store)
        with self.store.connection() as c:
            for n in range(53):
                config={'run_target':'answer_replay','source_evaluation_id':'E000'} if n==52 else {}
                c.execute("INSERT INTO evaluation_runs VALUES (?,'completed','real','real',NULL,'{}',?,'{}','{}',NULL,?,?)",(f'E{n:03}',json.dumps(config),f'{n:03}',f'{n:03}'))
        prune_history(self.store)
        with self.store.connection() as c:
            self.assertEqual(c.execute("SELECT count(*) FROM evaluation_runs WHERE id='E000'").fetchone()[0],1)
            self.assertEqual(c.execute("SELECT count(*) FROM evaluation_runs WHERE id='E001'").fetchone()[0],0)

    def test_backup_is_single_and_reset_rolls_back_on_unknown_nonempty_table(self):
        with self.store.connection() as c:
            c.execute('CREATE TABLE unknown_owner(id INTEGER)');c.execute('INSERT INTO unknown_owner VALUES (1)')
        with self.assertRaisesRegex(ValueError,'未知'):reset_experiments(self.store)
        self.assertGreater(len(self.store.questions()),0)
