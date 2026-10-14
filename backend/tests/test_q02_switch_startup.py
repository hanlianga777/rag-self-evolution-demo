"""Offline startup gate checks; no real Corpus or Provider acceptance."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.corpus_management import require_consistent_switch


class SwitchStartupTests(unittest.TestCase):
    def test_missing_journal_is_read_only(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            require_consistent_switch(root/'index')
            self.assertEqual(list(root.iterdir()),[])

    def test_completed_journal_with_mixed_binding_is_rejected(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);identity={'corpus_snapshot_id':'synthetic-new'}
            (root/'q02-switch.json').write_text(json.dumps({'phase':'completed','new_identity':identity}))
            with sqlite3.connect(root/'demo.db') as db:
                db.execute('CREATE TABLE golden_generation_artifacts (generation_run_id TEXT,hard_validation_json TEXT)')
                db.execute('INSERT INTO golden_generation_artifacts VALUES (?,?)',('GGEN-20261012120721324996',json.dumps({'corpus_fingerprint':{'corpus_snapshot_id':'synthetic-old'}})))
            with patch('app.corpus_management.validate_bundle',return_value={'manifest':{'knowledge_identity':identity}}):
                with self.assertRaisesRegex(ValueError,'inconsistent'):require_consistent_switch(root/'index')

    def test_authorized_reset_marker_only_bypasses_deleted_golden_not_corpus_state(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);identity={'corpus_snapshot_id':'synthetic-new'}
            (root/'q02-switch.json').write_text(json.dumps({'phase':'completed','new_identity':identity}))
            (root/'corpus_state.json').write_text(json.dumps({'knowledge_identity':identity}))
            with sqlite3.connect(root/'demo.db') as db:
                db.execute('CREATE TABLE schema_migrations (name TEXT,applied_at TEXT)')
                db.execute('INSERT INTO schema_migrations VALUES (?,?)',('experiment-reset-v1:synthetic-new','now'))
            with patch('app.corpus_management.validate_bundle',return_value={'manifest':{'knowledge_identity':identity}}):
                require_consistent_switch(root/'index')
                (root/'corpus_state.json').write_text(json.dumps({'knowledge_identity':{'corpus_snapshot_id':'wrong'}}))
                with self.assertRaisesRegex(ValueError,'inconsistent'):require_consistent_switch(root/'index')

    def test_direct_api_import_stops_before_database_writes(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/'q02-switch.json').write_text(json.dumps({'phase':'prepared'}))
            env={**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parents[1]),'RAG_DEMO_INDEX_DIR':str(root/'index'),'RAG_DEMO_DB_PATH':str(root/'demo.db'),
                 'RAG_DEMO_DOCUMENTS_DIR':str(root/'documents'),'RAG_DEMO_UPLOADS_DIR':str(root/'uploads'),
                 'RAG_DEMO_ENV_PATH':str(root/'absent.env'),'RAG_FORCE_MOCK':'1'}
            result=subprocess.run([sys.executable,'-c','import app.main'],env=env,capture_output=True,text=True,timeout=30)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('Incomplete Q02 switch',result.stderr)
            self.assertFalse((root/'demo.db').exists())


if __name__=='__main__':unittest.main()
