"""Run offline suites with disposable assets and a hard network boundary.

RAG_OFFLINE_ASSETS_ROOT optionally selects the local repository owning assets.
It is read only: every fixture writes to a temporary copy, never that repository.
"""
import os
import sys
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

root = Path(__file__).resolve().parents[1]
assets = Path(os.environ.get('RAG_OFFLINE_ASSETS_ROOT', str(root)))
with tempfile.TemporaryDirectory(prefix='rag-round0-offline-') as tmp:
    sandbox = Path(tmp)
    for name in ('documents', 'data/index'):
        source = assets / 'backend' / name
        if source.exists():
            shutil.copytree(source, sandbox / Path(name).name)
    (sandbox / '.env').write_text('')
    os.environ.update(RAG_DEMO_DB_PATH=str(sandbox/'test.db'), RAG_DEMO_INDEX_DIR=str(sandbox/'index'),
        RAG_DEMO_DOCUMENTS_DIR=str(sandbox/'documents'), RAG_DEMO_UPLOADS_DIR=str(sandbox/'uploads'),
        RAG_DEMO_ENV_PATH=str(sandbox/'.env'), RAG_FORCE_MOCK='1', HF_HUB_OFFLINE='1',
        TRANSFORMERS_OFFLINE='1', DEEPSEEK_API_KEY='', DASHSCOPE_API_KEY='', MINERU_API_KEY='')
    sys.path[:0] = [str(root/'backend'), str(root/'backend/tests')]
    with patch('urllib.request.urlopen', side_effect=AssertionError('Round0 offline: network forbidden')), \
         patch('socket.socket.connect', side_effect=AssertionError('Round0 offline: sockets forbidden')):
        import app.governance as governance
        governance.GOLDEN_DRAFT = sandbox / 'golden-draft.json'
        shutil.copy2(root/'backend/reports/golden_dataset_full_draft.json', governance.GOLDEN_DRAFT)
        suite = (unittest.defaultTestLoader.loadTestsFromNames(sys.argv[1:]) if len(sys.argv)>1
                 else unittest.defaultTestLoader.discover(str(root/'backend/tests')))
        result = unittest.TextTestRunner(verbosity=1).run(suite)
    print('OFFLINE TESTS:', result.testsRun, 'FAILURES:', len(result.failures), 'ERRORS:', len(result.errors),
          'SKIPPED:', len(result.skipped), 'REAL PROVIDER CALLS: 0')
    sys.exit(not result.wasSuccessful())
