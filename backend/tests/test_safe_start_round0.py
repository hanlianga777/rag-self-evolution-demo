import os, tempfile, unittest
from pathlib import Path
from unittest.mock import patch

class SafeStartTests(unittest.TestCase):
    def test_store_open_without_migration_does_not_create_database(self):
        from app.governance import GovernanceStore
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'missing.db'
            with self.assertRaises(FileNotFoundError): GovernanceStore(path, migrate=False)
            self.assertFalse(path.exists())

    def test_baseline_draft_rejects_candidate_thinking(self):
        from api_fixture import main
        from fastapi import HTTPException
        from app.policy import DEFAULT_PIPELINE_CONFIG
        identity=main.store.current_baseline_identity()
        with self.assertRaises(HTTPException) as error:
            main.save_pipeline_draft(main.PipelineDraftRequest(identity=identity,config={**DEFAULT_PIPELINE_CONFIG,'generation_thinking':'low'}))
        self.assertEqual(error.exception.status_code,422)

    def test_ordinary_import_does_not_create_missing_database(self):
        import subprocess, sys
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/'missing.db'
            env={**os.environ,'RAG_DEMO_DB_PATH':str(db),'RAG_DEMO_ENV_PATH':str(Path(tmp)/'empty.env')}
            env.pop('RAG_SAFE_START',None)
            env['PYTHONPATH']=str(Path(__file__).resolve().parents[1])
            result=subprocess.run([sys.executable,'-c','import app.main'],env=env,capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('安全启动要求已有数据库',result.stderr)
            self.assertFalse(db.exists())
    def test_service_entrypoints_do_not_build_index(self):
        root=Path(__file__).resolve().parents[2]
        for name in ('start.sh','scripts/run_api_service.sh'):
            self.assertNotIn('app.build_index', (root/name).read_text())
