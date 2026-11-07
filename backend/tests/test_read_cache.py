"""Display responses reuse work only while their persisted inputs are unchanged."""
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.gzip import GZipMiddleware
from app.read_cache import ReadCacheMiddleware


class ReadCacheTests(unittest.TestCase):
    def test_empty_wal_creation_is_not_a_data_change(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'test.db'
            path.touch()
            cache = ReadCacheMiddleware(FastAPI(), path)
            before = cache.read_version()
            Path(str(path) + '-wal').touch()
            self.assertEqual(cache.read_version(), before)

    def test_version_invalidates_response_and_gzip_preserves_json(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'test.db'
            with closing(sqlite3.connect(path)) as db, db:
                db.execute('CREATE TABLE evaluation_runs (status TEXT)')
                db.execute("INSERT INTO evaluation_runs VALUES ('completed')")
            app = FastAPI()
            calls = []

            @app.get('/api/evaluation')
            def read(light: bool = False):
                calls.append(light)
                return {'value': '保存内容' * 1000, 'light': light}

            app.add_middleware(ReadCacheMiddleware, database_path=path)
            app.add_middleware(GZipMiddleware, minimum_size=500)
            with TestClient(app) as client:
                first = client.get('/api/evaluation')
                second = client.get('/api/evaluation')
                self.assertEqual(first.json(), second.json())
                self.assertEqual(second.headers['content-encoding'], 'gzip')
                self.assertEqual(len(calls), 1)
                self.assertEqual(first.headers['x-read-version'], second.headers['x-read-version'])
                client.get('/api/evaluation?light=true')
                self.assertEqual(calls, [False, True])
                with closing(sqlite3.connect(path)) as db, db:
                    db.execute("UPDATE evaluation_runs SET status='running'")
                active = client.get('/api/evaluation')
                client.get('/api/evaluation')
                self.assertNotEqual(first.headers['x-read-version'], active.headers['x-read-version'])
                self.assertEqual(len(calls), 4)
                with closing(sqlite3.connect(path)) as db, db:
                    db.execute("UPDATE evaluation_runs SET status='completed'")
                client.get('/api/evaluation')
                client.get('/api/evaluation')
                self.assertEqual(len(calls), 5)
