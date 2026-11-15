"""Read optimizations retain saved results and invalidate on every data category."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.governance import GovernanceStore
from app.read_cache import ReadCacheMiddleware
from app.read_view import read_view


class ReadOptimizationTests(unittest.TestCase):
    def test_unchanged_data_is_reused_after_thirty_seconds(self):
        with tempfile.TemporaryDirectory() as temp:
            store = GovernanceStore(Path(temp) / 'test.db')
            app = FastAPI()
            calls = []

            @app.get('/api/evaluation')
            def read():
                calls.append(1)
                return {'saved': len(calls)}

            app.add_middleware(ReadCacheMiddleware, database_path=store.database_path)
            with TestClient(app) as client:
                first = client.get('/api/evaluation')
                with patch('app.read_cache.time.monotonic', return_value=10**12):
                    self.assertEqual(client.get('/api/evaluation').json(), first.json())
            self.assertEqual(len(calls), 1)

    def test_all_write_categories_invalidate_cached_http_response(self):
        # Real tables, commits and HTTP reads; no production database or Provider.
        writes = {
            'evaluation': "INSERT INTO evaluation_runs VALUES ('e','completed','real','real','g','{}','{}','{}','{}',NULL,'now','now')",
            'experiment': "INSERT INTO experiments VALUES ('x','e','completed','{}','now')",
            'candidate': "INSERT INTO candidate_configs VALUES ('c','x','evaluated','{}','{}','{}','now')",
            'release': "INSERT INTO production_versions (id,status,config_json,created_at) VALUES ('p','active','{}','now')",
            'annotation': "INSERT INTO review_events (question_id,gate,decision,actor,created_at) VALUES ('q','human','approved','fixture','now')",
            'snapshot': "INSERT INTO dataset_versions VALUES ('g','approved','fixture','{}','now')",
        }
        tables = dict(zip(writes, ['evaluation_runs','experiments','candidate_configs','production_versions','review_events','dataset_versions']))
        for category, sql in writes.items():
            with self.subTest(category=category), tempfile.TemporaryDirectory() as temp:
                store = GovernanceStore(Path(temp) / 'test.db')
                app = FastAPI()

                @app.get('/api/overview')
                def read():
                    with store.connection() as db:
                        return {'count': db.execute('SELECT COUNT(*) FROM '+tables[category]).fetchone()[0]}

                app.add_middleware(ReadCacheMiddleware, database_path=store.database_path)
                with TestClient(app) as client:
                    first = client.get('/api/overview')
                    self.assertEqual(client.get('/api/overview').json(), first.json())
                    with store.connection() as db:
                        db.execute(sql)
                    second = client.get('/api/overview')
                    self.assertEqual(second.json()['count'], first.json()['count'] + 1)
                    self.assertNotEqual(second.headers['x-read-version'], first.headers['x-read-version'])

    def test_source_and_index_edits_invalidate_responses(self):
        for folder in ('documents', 'index'):
            with self.subTest(folder=folder), tempfile.TemporaryDirectory() as temp:
                store = GovernanceStore(Path(temp) / 'test.db')
                sources = Path(temp) / folder;sources.mkdir()
                source = sources / 'source';source.write_text('old')
                app = FastAPI()

                @app.get('/api/overview')
                def read():return {p.name:p.read_text() for p in sources.iterdir()}

                app.add_middleware(ReadCacheMiddleware, database_path=store.database_path, dependencies=[sources])
                with TestClient(app) as client:
                    self.assertEqual(client.get('/api/overview').json()['source'], 'old')
                    source.write_text('new')
                    self.assertEqual(client.get('/api/overview').json()['source'], 'new')
                    extra = sources / 'extra';extra.write_text('added')
                    self.assertEqual(client.get('/api/overview').json()['extra'], 'added')
                    extra.unlink()
                    self.assertNotIn('extra', client.get('/api/overview').json())

    def test_same_text_is_normalized_once_per_read_and_new_text_stays_fresh(self):
        from app.diagnostics import _text
        import unicodedata
        normalize = unicodedata.normalize
        with patch('unicodedata.normalize', wraps=normalize) as call:
            with read_view():
                self.assertEqual(_text('Ａ B。'), 'ab')
                self.assertEqual(_text('Ａ B。'), 'ab')
                self.assertEqual(_text('新内容'), '新内容')
            self.assertEqual(call.call_count, 2)
            self.assertEqual(_text('Ａ B。'), 'ab')
            self.assertEqual(call.call_count, 3)

    def test_shared_regression_baseline_is_loaded_once_without_changing_results(self):
        from identity_fixture import completed_baseline
        with tempfile.TemporaryDirectory() as temp:
            store = GovernanceStore(Path(temp) / 'test.db')
            baseline = completed_baseline(store)
            candidate_run = completed_baseline(store, target='sandbox_candidate')
            experiment = store.create_experiment(baseline)
            for label in 'ABC':
                store.save_candidate(experiment, label, {}, {'candidate_label': label, 'round': 1})
                store.finish_candidate(experiment+'-'+label, 'evaluated', {'baseline_run_id': baseline, 'evaluation_run_id': candidate_run, 'evaluation_complete': True})
            expected = store.experiment(experiment, light=True)
            queries = []
            original = store.connection
            from contextlib import contextmanager
            @contextmanager
            def traced():
                with original() as db:
                    db.set_trace_callback(queries.append)
                    yield db
            with patch.object(store, 'connection', traced), read_view():
                actual = store.experiment(experiment, light=True)
            self.assertEqual(actual, expected)
            reads = [q for q in queries if 'SELECT status,dataset_version_id,dataset_snapshot_json,judge_json FROM evaluation_runs' in q]
            self.assertEqual(len(reads), 1)
