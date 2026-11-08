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

# Each API case swaps main.store for its own disposable DB. Follow that DB for
# cache stamps too, so responses cannot leak from another test's store.
from app.read_cache import ReadCacheMiddleware

class _FixtureReadCache(ReadCacheMiddleware):
    async def dispatch(self, request, call_next):
        path = main.store.database_path.resolve()
        if path != self.database_path:
            self.database_path = path
            self.dependencies = [path, Path(str(path) + '-wal')]
            self.version = None
            self.cache.clear()
        return await super().dispatch(request, call_next)

for middleware in main.app.user_middleware:
    if middleware.cls is ReadCacheMiddleware:
        middleware.cls = _FixtureReadCache
