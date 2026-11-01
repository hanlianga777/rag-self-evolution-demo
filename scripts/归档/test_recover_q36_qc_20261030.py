"""Offline guards only; app imports occur after isolated env and TCP block."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).with_name('recover_q36_qc_20261030.py')
spec = importlib.util.spec_from_file_location('q36_recovery', SCRIPT)
recovery = importlib.util.module_from_spec(spec); spec.loader.exec_module(recovery)


class Q36RecoverySafetyTests(unittest.TestCase):
    def test_no_execute_by_default_and_execute_requires_separate_authorization(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, str(SCRIPT), '--output', directory, '--execute'], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn('Explicit plan-bound authorization required', result.stderr)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_exact_wire_request_blocks_second_call_or_any_changed_parameter(self):
        payload = {'model': 'deepseek-flash', 'max_tokens': 16384, 'stream': False,
                   'messages': [{'role': 'user', 'content': 'Q36 only'}]}
        plan = {'model': 'deepseek-flash', 'wire_payload': payload}
        recovery.validate_outgoing(plan, [], 'DeepSeek', 'deepseek-flash', payload)
        for changes in ({'max_tokens': 16385}, {'stream': True}, {'messages': []}, {'model': 'other'}):
            with self.subTest(changes=changes), self.assertRaisesRegex(RuntimeError, 'Only one exact'):
                recovery.validate_outgoing(plan, [], 'DeepSeek', 'deepseek-flash', {**payload, **changes})
        for calls, provider, model in [([{}], 'DeepSeek', 'deepseek-flash'), ([], 'Alibaba', 'deepseek-flash'), ([], 'DeepSeek', 'other')]:
            with self.assertRaisesRegex(RuntimeError, 'Only one exact'):
                recovery.validate_outgoing(plan, calls, provider, model, payload)

    def test_projection_preserves_actual_final_and_conclusions_without_changing_saved_probe(self):
        # A test fixture, never a Provider response or formal quality history.
        details = {'classification': 'NEGATIVE_VALID', 'evidence_coverage': {'final_context': ['C1']},
            'probe_execution_status': 'completed', 'question_validity': 'valid', 'retrieval_coherent': None, 'risk': None,
            'retrieval_trace': {'status': 'ok', 'corpus_fingerprint': {'id': 'fixture'},
                'final': [{'chunk_id': 'C1', 'content': 'actual chosen text'}], 'candidates': [{'content': 'UNRELATED CORPUS'}]},
            'full_text': {'passed': True, 'mode': 'actual', 'normalized_query': 'unused'},
            'negative_checks': {'fake_negative_check': {'passed': True}, 'subtype_semantic': None,
                'answerability': {'answerable': False, 'reason': 'actual missing fact', 'token_usage': [{'secret_noise': 'omit'}]},
                'full_text_probe': {'status': 'complete', 'signal_only': True, 'corpus_fingerprint': {'id': 'fixture'},
                    'coverage': {'parsed_pages': 2}, 'anchors': [], 'matches': [
                        {'document_id': 'D1', 'page': 2, 'content': 'actual source quote'},
                        {'document_id': 'D9', 'page': 9, 'content': 'UNRELATED CORPUS'}]},
                'legacy_chunk_signals': {'signal_only': True, 'matches': [{'chunk_id': 'C1', 'content_preview': 'omit'}]},
                'vector_probe': {'signal_only': True, 'observed_hits': [{'chunk_id': 'C1', 'content': 'omit'}]}}}
        saved = copy.deepcopy(details)
        projected = recovery.project_probe(details, {'sources': [{'document_id': 'D1', 'pages': [2, 2], 'quote': 'source quote'}]})
        self.assertEqual(details, saved)
        self.assertEqual(projected['retrieval_trace']['final'], saved['retrieval_trace']['final'])
        self.assertEqual(projected['negative_checks']['answerability'], {'answerable': False, 'reason': 'actual missing fact'})
        self.assertEqual(projected['negative_checks']['full_text_probe']['matches'][0]['source_quotes_present_verbatim'], ['source quote'])
        self.assertEqual(projected['projection']['original_probe_details_sha256'], recovery.common.digest(saved))
        self.assertFalse(projected['projection']['is_full_probe_trace'])
        self.assertNotIn('UNRELATED CORPUS', json.dumps(projected))
        self.assertNotIn('token_usage', projected['negative_checks']['answerability'])

    def test_store_proxy_rejects_other_question_and_never_changes_saved_history(self):
        class Store:
            def probe_history(self, key): raise AssertionError('No other history access allowed')
        with self.assertRaisesRegex(ValueError, 'Only approved Q36'):
            recovery.ProjectedStore(Store()).probe_history('Q13')

    def test_history_guard_detects_overwrite_unrelated_rows_and_second_qc(self):
        with tempfile.TemporaryDirectory() as directory:
            old, new = Path(directory) / 'old.db', Path(directory) / 'new.db'
            with sqlite3.connect(old) as db:
                db.execute('create table qc_results(id integer primary key,question_id text,result_json text)')
                db.execute('create table evaluation_runs(id text,result text)')
                db.execute("insert into qc_results values(1,?, 'original failure')", (recovery.QUESTION,))
                db.execute("insert into evaluation_runs values('old','protected')")
            recovery.common.backup_database(old, new)
            with sqlite3.connect(new) as db: db.execute('insert into qc_results values(2,?,?)', (recovery.QUESTION, 'real new result'))
            recovery.preserve(old, new)
            with sqlite3.connect(new) as db: db.execute('insert into qc_results values(3,?,?)', (recovery.QUESTION, 'forbidden second result'))
            with self.assertRaisesRegex(RuntimeError, 'excess results'): recovery.preserve(old, new)
            with sqlite3.connect(new) as db:
                db.execute('delete from qc_results where id=3')
                db.execute("update evaluation_runs set result='changed'")
            with self.assertRaisesRegex(RuntimeError, 'evaluation_runs'): recovery.preserve(old, new)

    def test_first_schema_error_propagates_without_retry_under_isolation(self):
        class Service:
            model = 'deepseek-flash'
            calls = 0
            def _quality_check(self, item):
                self.calls += 1
                raise ValueError('first invalid QC response')
        service = Service()
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
            'RAG_DEMO_DB_PATH': directory + '/test.db', 'RAG_DEMO_INDEX_DIR': directory + '/index',
            'RAG_DEMO_DOCUMENTS_DIR': directory + '/documents', 'RAG_DEMO_ENV_PATH': directory + '/empty.env',
            'RAG_DEMO_UPLOADS_DIR': directory + '/uploads', 'DEEPSEEK_API_KEY': '', 'DASHSCOPE_API_KEY': '', 'RAG_SAFE_START': '1'}), recovery.offline():
            sys.path.insert(0, str(SCRIPT.parents[2] / 'backend'))
            with self.assertRaisesRegex(ValueError, 'first invalid QC'):
                recovery.common.single_quality_check(service, {})
        self.assertEqual(service.calls, 1)

if __name__ == '__main__': unittest.main(verbosity=2)
