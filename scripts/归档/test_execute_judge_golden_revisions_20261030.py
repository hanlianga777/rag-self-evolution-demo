import importlib.util
from contextlib import closing
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path


SCRIPT = Path(__file__).with_name('execute_judge_golden_revisions_20261030.py')


class GoldenExecutionSafetyTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('golden_revision_execution', SCRIPT)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def test_table_fingerprint_detects_same_count_content_change(self):
        with closing(sqlite3.connect(':memory:')) as db, db:
            db.execute('create table history(id integer primary key, payload text)')
            db.execute("insert into history values(1,'original')")
            before = self.module.table_fingerprints(db)
            db.execute("update history set payload='changed'")
            after = self.module.table_fingerprints(db)
        self.assertEqual(before['history']['rows'], 1)
        self.assertEqual(after['history']['rows'], 1)
        self.assertNotEqual(before['history']['sha256'], after['history']['sha256'])

    def test_rpc_limit_blocks_second_qc_before_request(self):
        quota = self.module.RequestCaps({'deepseek-flash': 1})
        quota.reserve('deepseek-flash')
        with self.assertRaisesRegex(RuntimeError, 'RPC limit'):
            quota.reserve('deepseek-flash')
        self.assertEqual(quota.used, {'deepseek-flash': 1})

    def test_active_revision_refuses_execution_before_first_request_without_writes(self):
        with closing(sqlite3.connect(':memory:')) as db, db:
            for table in ('evaluation_runs','golden_generation_runs','agent_traces'):
                db.execute(f'CREATE TABLE {table}(status TEXT)')
            db.execute('CREATE TABLE candidate_revision_runs(status TEXT,audit_json TEXT)')
            for status in ('queued','generating','validating','probing','qc'):
                with self.subTest(status=status):
                    db.execute('DELETE FROM candidate_revision_runs')
                    db.execute('INSERT INTO candidate_revision_runs VALUES (?,?)', (status, '{}'))
                    before = self.module.table_fingerprints(db)
                    requests = []
                    with self.assertRaisesRegex(RuntimeError, 'candidate_revision_runs'):
                        self.module.ensure_no_active_tasks(db)
                        requests.append('first request would start here')
                    self.assertEqual(requests, [])
                    self.assertEqual(self.module.table_fingerprints(db), before)
            db.execute('DELETE FROM candidate_revision_runs')
            db.execute('INSERT INTO candidate_revision_runs VALUES (?,?)', ('completed', '{"status":"qc"}'))
            with self.assertRaisesRegex(RuntimeError, 'candidate_revision_runs'):
                self.module.ensure_no_active_tasks(db)
            db.execute('UPDATE candidate_revision_runs SET audit_json=?', ('{}',))
            self.module.ensure_no_active_tasks(db)

    def test_missing_or_invalid_price_prevents_first_paid_request(self):
        with self.assertRaisesRegex(ValueError, 'price'):
            self.module.validate_prices({}, 'deepseek-flash')
        rates = {model: {'provider': provider, 'input': 1, 'output': 1, 'max_output': bound}
                 for model, provider, bound in [('deepseek-flash', 'DeepSeek', 65536), ('text-embedding-v4', 'Alibaba', 0), ('qwen3-rerank', 'Alibaba', 0)]}
        self.module.validate_prices(rates, 'deepseek-flash')
        rates['text-embedding-v4']['input'] = float('nan')
        with self.assertRaisesRegex(ValueError, 'price'):
            self.module.validate_prices(rates, 'deepseek-flash')

    def test_known_usage_and_usd_estimate_can_continue_without_actual_account_debit(self):
        call = {'provider': 'DeepSeek', 'model': 'deepseek-flash', 'status': 'ok', 'upper_estimate_yuan': None,
                'actual_debit': None, 'estimated_cost': {'amount': 0.01, 'currency': 'USD'},
                'usage': {'provider': 'DeepSeek', 'requested_model': 'deepseek-flash', 'status': 'ok', 'prompt_tokens': 10, 'completion_tokens': 20}}
        self.module.require_known_usage([call])
        call['usage']['completion_tokens'] = None
        with self.assertRaisesRegex(RuntimeError, 'request/Usage'):
            self.module.require_known_usage([call])
        call['status'] = 'reserved'
        with self.assertRaisesRegex(RuntimeError, 'request/Usage'):
            self.module.require_known_usage([call])

    def test_local_qc_entry_propagates_first_schema_failure_without_correction_retry(self):
        class Service:
            model = 'deepseek-flash'
            calls = 0
            def _quality_check(self, item):
                self.calls += 1
                raise ValueError('first schema failure')
        service = Service()
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
                'RAG_DEMO_DB_PATH': directory + '/unused.db', 'RAG_DEMO_INDEX_DIR': directory + '/index',
                'RAG_DEMO_DOCUMENTS_DIR': directory + '/documents', 'RAG_DEMO_ENV_PATH': directory + '/empty.env'}):
            sys.path.insert(0, str(SCRIPT.parents[2] / 'backend'))
            with self.assertRaisesRegex(ValueError, 'first schema failure'):
                self.module.single_quality_check(service, {})
        self.assertEqual(service.calls, 1)

    def test_authorization_binds_reviewable_plan_stage_and_actual_source_file(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'user-instruction.txt'
            source.write_text('Explicit owner instruction supplied outside this script')
            auth = {'source': 'direct_user_instruction', 'actor': 'Codex',
                    'plan_sha256': 'reviewed-plan', 'allowed_stages': ['revise-quality'],
                    'source_file': str(source), 'source_sha256': self.module.file_sha(source)}
            self.module.require_authorization(auth, 'reviewed-plan', 'revise-quality')
            with self.assertRaisesRegex(ValueError, 'authorization'):
                self.module.require_authorization(auth, 'changed-plan', 'revise-quality')
            with self.assertRaisesRegex(ValueError, 'authorization'):
                self.module.require_authorization(auth, 'reviewed-plan', 'review-freeze')
            source.write_text('changed instruction')
            with self.assertRaisesRegex(ValueError, 'authorization'):
                self.module.require_authorization(auth, 'reviewed-plan', 'revise-quality')

    def test_q13_proposal_comes_from_hash_verified_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            source = directory / 'source.json'; source.write_text('{}')
            proposals = directory / 'proposals.json'
            proposals.write_text(json.dumps({'original_snapshot': 'saved', 'rows': [
                {'slot': 'Q15', 'question_id': 'q15', 'before': {}, 'proposed_after': {'required_checks': []}},
                {'slot': 'Q36', 'question_id': 'q36', 'before': {}, 'proposed_after': {'auxiliary_information': []}},
            ]}))
            manifest = directory / 'manifest.json'
            manifest.write_text(json.dumps({'source_files': [{'path': str(source), 'sha256': self.module.file_sha(source)}],
                'cases': [{'golden_item': {'id': 'q13', 'raw': {'business_requirements': {'required_checks': [{'id': 'R4', 'logic': 'AND', 'atoms': [{'id': 'R4.1'}, {'id': 'R4.2'}]}]}}}}]}))
            _, changes, _ = self.module.load_changes(proposals, manifest)
            self.assertEqual(set(changes), {'q13', 'q15', 'q36'})
            self.assertEqual(changes['q13']['business_requirements']['required_checks'][0]['logic'], 'AND')
            source.write_text('drift')
            with self.assertRaisesRegex(ValueError, 'Source hash'):
                self.module.load_changes(proposals, manifest)

    def test_execute_flag_without_authorization_stops_before_creating_database_or_ledger(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            database = directory / 'missing.db'
            result = subprocess.run([sys.executable, str(SCRIPT), '--execute', '--output', str(directory / 'output'), '--database', str(database)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn('requires separate authorization', result.stderr)
            self.assertFalse(database.exists())
            self.assertFalse((directory / 'output').exists())

    def test_preservation_rejects_rewritten_history_even_when_new_rows_are_appended(self):
        with tempfile.TemporaryDirectory() as directory:
            before = Path(directory) / 'before.db'
            after = Path(directory) / 'after.db'
            with closing(sqlite3.connect(before)) as db, db:
                db.execute('create table questions(id text primary key, content text)')
                db.execute('create table dataset_versions(id text primary key, snapshot_json text)')
                db.execute("insert into questions values('target','old')")
                db.execute("insert into dataset_versions values('old','original frozen record')")
            self.module.backup_database(before, after)
            with closing(sqlite3.connect(after)) as db, db:
                db.execute("update questions set content='allowed edit' where id='target'")
                db.execute("insert into dataset_versions values('new','new snapshot')")
            self.module.assert_preserved(before, after, ['target'], allow_snapshot=True)
            with closing(sqlite3.connect(after)) as db, db:
                db.execute("update dataset_versions set snapshot_json='rewritten' where id='old'")
            with self.assertRaisesRegex(RuntimeError, 'Historical data changed'):
                self.module.assert_preserved(before, after, ['target'], allow_snapshot=True)


if __name__ == '__main__':
    unittest.main()
