"""Offline acceptance: isolate assets before importing app; never call a real Provider.

Copies current assets only as disposable test inputs; does not prove their Provider lifecycle.
Pass unittest module names to run a targeted subset.
"""
import os,sys,tempfile,shutil,unittest
from pathlib import Path
root=Path(__file__).resolve().parents[1];sandbox=Path(tempfile.mkdtemp(prefix='rag-closure-offline-'))
shutil.copytree(root/'backend/documents',sandbox/'documents')
shutil.copytree(root/'backend/data/index',sandbox/'index')
(sandbox/'.env').write_text('')
os.environ.update(RAG_DEMO_DB_PATH=str(sandbox/'test.db'),RAG_DEMO_INDEX_DIR=str(sandbox/'index'),RAG_DEMO_DOCUMENTS_DIR=str(sandbox/'documents'),RAG_DEMO_UPLOADS_DIR=str(sandbox/'uploads'),RAG_DEMO_ENV_PATH=str(sandbox/'.env'),RAG_FORCE_MOCK='1',DEEPSEEK_API_KEY='',DASHSCOPE_API_KEY='',MINERU_API_KEY='')
sys.path.insert(0,str(root/'backend'))
from unittest.mock import patch
import app.governance as governance
governance.GOLDEN_DRAFT=sandbox/'golden-draft.json';shutil.copy2(root/'backend/reports/golden_dataset_full_draft.json',governance.GOLDEN_DRAFT)
sys.path.insert(0,str(root/'backend/tests'))
suite=unittest.defaultTestLoader.loadTestsFromNames(sys.argv[1:]) if len(sys.argv)>1 else unittest.defaultTestLoader.discover(str(root/'backend/tests'))
with patch('urllib.request.urlopen',side_effect=RuntimeError('Offline acceptance: external calls forbidden')):
 result=unittest.TextTestRunner(verbosity=1).run(suite)
print('ISOLATION:',sandbox,'TESTS:',result.testsRun,'FAILURES:',len(result.failures),'ERRORS:',len(result.errors));sys.exit(not result.wasSuccessful())
