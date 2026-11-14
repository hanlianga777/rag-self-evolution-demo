from contextlib import closing
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest


spec = importlib.util.spec_from_file_location('status_export', Path(__file__).with_name('export_run_status.py'))
status_export = importlib.util.module_from_spec(spec)
spec.loader.exec_module(status_export)


class StatusExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = self.root / 'demo.db'
        with closing(sqlite3.connect(self.db)) as c, c:
            c.executescript('''
                CREATE TABLE evaluation_runs(id TEXT,status TEXT,config_json TEXT,result_json TEXT,error_message TEXT,created_at TEXT);
                CREATE TABLE evaluation_case_results(run_id TEXT,result_json TEXT);
                CREATE TABLE experiments(id TEXT,status TEXT,result_json TEXT,created_at TEXT);
                CREATE TABLE candidate_configs(id TEXT,experiment_id TEXT,status TEXT,reasoning_json TEXT,result_json TEXT,created_at TEXT);
                CREATE TABLE golden_generation_runs(id TEXT,status TEXT,profile_json TEXT,question_ids_json TEXT,created_at TEXT);
                CREATE TABLE golden_generation_artifacts(generation_run_id TEXT,hard_validation_json TEXT);
                CREATE TABLE candidate_revision_runs(id TEXT,status TEXT,audit_json TEXT,created_at TEXT,updated_at TEXT);
                CREATE TABLE job_checkpoints(run_id TEXT,question_id TEXT,checkpoint_json TEXT);
            ''')

    def run_row(self, state='running', result=None, config=None, error=None):
        result = {'completed': 3, 'total': 10, 'technical_failed': 1, **(result or {})}
        with closing(sqlite3.connect(self.db)) as c, c:
            c.execute('INSERT INTO evaluation_runs VALUES(?,?,?,?,?,?)',
                      ('EVAL-TEST', state, json.dumps(config or {}), json.dumps(result), error, '2026-11-14T12:00:00Z'))

    def render(self):
        before = self.db.read_bytes()
        text = status_export.build_status(self.db, self.root)
        self.assertEqual(before, self.db.read_bytes())
        return text

    def test_idle_and_no_timestamp_only_change(self):
        text = self.render()
        self.assertIn('当前阶段：已完成（空闲）', text)
        self.assertIn('费用估算：未知', text)
        out = self.root / 'status.md'
        self.assertTrue(status_export.export_status(self.db, self.root, out))
        before = out.read_bytes()
        self.assertFalse(status_export.export_status(self.db, self.root, out))
        self.assertEqual(before, out.read_bytes())

    def test_running_baseline_and_candidate(self):
        self.run_row()
        self.assertIn('当前阶段：Baseline', self.render())
        self.assertIn('完成题数：3 / 10；技术失败数：1', self.render())
        with closing(sqlite3.connect(self.db)) as c, c:
            c.execute('UPDATE evaluation_runs SET config_json=?', (json.dumps({'candidate_id': 'C-1'}),))
            c.execute('INSERT INTO candidate_configs VALUES(?,?,?,?,?,?)',
                      ('C-1', 'EXP-1', 'running', '{"round":2,"candidate_label":"B","sandbox_attempts":[{}]}', '{}', '2026-11-14'))
            c.execute('INSERT INTO experiments VALUES(?,?,?,?)',
                      ('EXP-1', 'running', '{}', '2026-11-14'))
        text = self.render()
        self.assertIn('第2轮第2个 Candidate（B）', text)
        self.assertIn('预算已用 / 总数：1 / 12', text)

    def test_paused_uses_persisted_pause_only(self):
        self.run_row(result={'price_pause': {'paused': True, 'resume_at': '2026-11-15T10:00:00+00:00'}})
        text = self.render()
        self.assertIn('非平价时段暂停：是', text)
        self.assertIn('2026-11-15 05:00:00 EST', text)

    def test_error_is_safe_and_not_business_failure(self):
        self.run_row('failed', result={'question': '秘密题目', 'answer': '秘密回答'}, error='ProviderTimeout 秘密题目 秘密回答 sk-private')
        text = self.render()
        self.assertIn('当前阶段：出错', text)
        self.assertIn('ProviderTimeout', text)
        for secret in ['秘密题目', '秘密回答', 'sk-private']:
            self.assertNotIn(secret, text)

    def test_completed_metrics_and_unknown_cost(self):
        self.run_row('completed', result={'completed': 10, 'technical_failed': 0, 'bad_case_count': 2,
            'evaluation_complete': True, 'gates': {'passed_count': 9, 'total': 11},
            'metrics': {'latency_p50_seconds': 4.5, 'latency_p99_seconds': 20.0}})
        text = self.render()
        self.assertIn('| EVAL-TEST | 8 / 10 | 9 / 11 | 4.5 | 20.0 |', text)
        self.assertNotIn('当前阶段：出错', text)

    def test_rebuild_and_anchor_progress(self):
        ops = self.root / 'corpus_operations'
        ops.mkdir()
        (ops / 'operation.json').write_text(json.dumps({'status': 'running', 'created_at': '2026-11-14',
            'progress': {'completed': 1, 'total': 4}}))
        self.assertIn('知识库重建', self.render())
        (ops / 'operation.json').unlink()
        with closing(sqlite3.connect(self.db)) as c, c:
            c.execute('INSERT INTO candidate_revision_runs VALUES(?,?,?,?,?)',
                ('REV-1', 'probing', '{"progress":{"current":5,"total":50}}', '2026-11-14', '2026-11-14'))
        self.assertIn('题卷锚定', self.render())
        self.assertIn('完成题数：5 / 50', self.render())

    def test_golden_probe_and_qc_do_not_use_generation_counter(self):
        with closing(sqlite3.connect(self.db)) as c, c:
            c.execute('INSERT INTO golden_generation_runs VALUES(?,?,?,?,?)',
                ('GEN-1', 'probing', '{"expected_count":50}', '[]', '2026-11-14'))
            c.execute('INSERT INTO golden_generation_artifacts VALUES(?,?)',
                ('GEN-1', '{"progress":{"stage":"probing","phase_processed":50,"probe_completed":7,"qc_completed":3,"qc_skipped":1}}'))
        self.assertIn('完成题数：7 / 50', self.render())
        with closing(sqlite3.connect(self.db)) as c, c:
            c.execute('UPDATE golden_generation_runs SET status="qc"')
            c.execute('UPDATE golden_generation_artifacts SET hard_validation_json=?',
                ('{"progress":{"stage":"qc","phase_processed":50,"probe_completed":50,"qc_completed":3,"qc_skipped":1}}',))
        self.assertIn('完成题数：4 / 50', self.render())

    def test_permanent_failure_still_consumes_budget(self):
        with closing(sqlite3.connect(self.db)) as c, c:
            c.execute('INSERT INTO experiments VALUES(?,?,?,?)', ('EXP-1', 'completed', '{}', '2026-11-14'))
            c.execute('INSERT INTO candidate_configs VALUES(?,?,?,?,?,?)',
                ('C-1', 'EXP-1', 'failed', '{"sandbox_attempts":[{}]}',
                 '{"evaluation_complete":false,"technical_errors":[{"provider_error":{"http_status":401}}]}', '2026-11-14'))
        self.assertIn('预算已用 / 总数：1 / 12', self.render())
        with closing(sqlite3.connect(self.db)) as c, c:
            c.execute('UPDATE candidate_configs SET result_json=?',
                ('{"evaluation_complete":false,"technical_errors":[{"error":"ProviderTimeout"}]}',))
        self.assertIn('预算已用 / 总数：0 / 12', self.render())


if __name__ == '__main__':
    unittest.main()
