"""Destructive operations run only against disposable, synthetic SQLite."""
import copy
from contextlib import closing
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from app.governance import GovernanceStore

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from replace_golden_content import apply, database_audit


class ReplacementTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.store = GovernanceStore(self.root / 'test.db')
        self.connection = sqlite3.connect(self.root / 'test.db'); self.addCleanup(self.connection.close)
        c = self.connection
        for (table,) in list(c.execute("SELECT name FROM sqlite_master WHERE type='table'")):
            c.execute('DELETE FROM "' + table + '"')
        questions = []
        for i in range(50):
            q = {'id': f'q{i}', 'question': f'原题{i}', 'reference_answer': '新版答案' if i < 30 else None,
                 'test_category': 'positive' if i < 20 else 'ablation' if i < 30 else 'negative',
                 'evidence': [], 'coverage_slot': f'Q{i+1:02}', 'content_revision': {'source_snapshot_id': 'old-snapshot'}}
            questions.append(q)
            c.execute('INSERT INTO questions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                      (q['id'],'golden','v1_mini',q['test_category'],None,'approved','probe_passed',q['question'],'旧版答案','[]','{}','before','before','qc_passed'))
        c.execute('INSERT INTO questions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)', ('intermediate','candidate','v1_mini','positive',None,'approved','probe_passed','无效中间题','旧答案','[]','{}','before','before','qc_passed'))
        c.execute('INSERT INTO dataset_versions VALUES (?,?,?,?,?)', ('old-snapshot','approved','fixture','{"immutable":true}','before'))
        c.execute('INSERT INTO golden_generation_runs VALUES (?,?,?,?,?,?)', ('old-run','{}','fixture','completed','[]','before'))
        c.execute('INSERT INTO golden_generation_artifacts VALUES (?,?,?,?)', ('old-run','[]','[]','{}'))
        c.execute('INSERT INTO evaluation_runs VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', ('old-eval','completed','fixture','fixture','old-snapshot','{}','{}','{}','{}',None,'before','before'))
        c.execute('INSERT INTO experiments VALUES (?,?,?,?,?)', ('old-experiment','old-eval','completed','{}','before'))
        c.execute('INSERT INTO candidate_configs VALUES (?,?,?,?,?,?,?)', ('old-candidate','old-experiment','evaluated','{}','{}','{}','before'))
        c.execute('INSERT INTO approvals VALUES (?,?,?,?,?,?)', (1,'release','old-candidate','rejected','human','before'))
        c.execute('INSERT INTO production_versions VALUES (?,?,?,?,?,?,?,?,?)', ('production','active','{"top_k":4}',None,None,None,None,'before','{}'))
        c.commit()
        self.plan = {'content_id':'new-content','run_id':'new-run','created_at':'after','questions':questions,
                     'old_questions':[q['id'] for q in questions]+['intermediate'], 'old_runs':['old-run'],
                     'old_snapshots':['old-snapshot'],'evaluation_ids':['old-eval'],'experiment_ids':['old-experiment'],
                     'snapshot':{'id':'new-snapshot','question_ids':[q['id'] for q in questions], 'questions':questions,
                                 'profile':{'name':'medium','positive_count':20,'ablation_count':10,'negative_count':20},
                                 'corpus_fingerprint':{},'coverage_plan':{'slots':[]}}}

    def output(self):
        path = self.root / 'output'; path.mkdir(); return path

    def test_backup_recovery_pending_states_and_independent_audit_survive(self):
        before = database_audit(self.connection)
        result = apply(self.connection, self.plan, self.output())
        self.assertEqual(result['questions'], 50)
        self.assertEqual(self.connection.execute('SELECT count(*) FROM evaluation_runs').fetchone()[0], 0)
        self.assertEqual(self.connection.execute('SELECT count(*) FROM candidate_configs').fetchone()[0], 0)
        self.assertEqual(self.connection.execute("SELECT count(*) FROM questions WHERE stage='candidate' AND probe_status='probe_pending' AND qc_status='qc_pending' AND review_status='human_review_pending'").fetchone()[0], 50)
        self.assertEqual(self.connection.execute("SELECT status,snapshot_json FROM dataset_versions WHERE id='old-snapshot'").fetchone(), ('archived','{"immutable":true}'))
        self.assertEqual(self.connection.execute("SELECT status FROM dataset_versions WHERE id='new-snapshot'").fetchone()[0], 'draft')
        after = database_audit(self.connection)
        for table in ('approvals','production_versions','rollback_history'):
            self.assertEqual(before[table], after[table])
        with closing(sqlite3.connect(result['backup_path'])) as backup:
            self.assertEqual(database_audit(backup), before)
            self.assertEqual(backup.execute('PRAGMA integrity_check').fetchone()[0], 'ok')

    def test_failure_rolls_back_entire_cleanup_and_preserves_verified_backup(self):
        before = database_audit(self.connection)
        plan = copy.deepcopy(self.plan); plan['snapshot']['id'] = 'old-snapshot'
        output = self.output()
        with self.assertRaises(sqlite3.IntegrityError):
            apply(self.connection, plan, output)
        self.assertEqual(database_audit(self.connection), before)
        with closing(sqlite3.connect(output / 'before.db')) as backup:
            self.assertEqual(database_audit(backup), before)
        self.assertFalse((output / 'execution.json').exists())

    def test_active_evaluation_is_rejected_before_backup_or_mutation(self):
        self.connection.execute("UPDATE evaluation_runs SET status='running'"); self.connection.commit()
        before = database_audit(self.connection); output = self.output()
        with self.assertRaisesRegex(ValueError, '活动任务'):
            apply(self.connection, self.plan, output)
        self.assertEqual(database_audit(self.connection), before)
        self.assertFalse((output / 'before.db').exists())
