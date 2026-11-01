"""Import-time FastAPI initialization must never open the user's real database."""
import atexit
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

_database = tempfile.TemporaryDirectory(prefix='rag-api-test-')
atexit.register(_database.cleanup)
with patch.dict(os.environ, {'RAG_DEMO_DB_PATH': str(Path(_database.name) / 'collection.db'), 'RAG_FORCE_MOCK': '1', 'RAG_SAFE_START': '0'}):
    # Tests replace the store; the real index switch journal must not inspect this empty fixture DB.
    with patch('app.corpus_management.require_consistent_switch'):
        from app import main
