"""Import-time FastAPI initialization must never open the user's real database."""
import atexit
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

_database = tempfile.TemporaryDirectory(prefix='rag-api-test-')
atexit.register(_database.cleanup)
with patch.dict(os.environ, {'RAG_DEMO_DB_PATH': str(Path(_database.name) / 'collection.db'), 'RAG_FORCE_MOCK': '1'}):
    from app import main
