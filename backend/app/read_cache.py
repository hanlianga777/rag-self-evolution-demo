"""Bounded process cache for GET display responses; persisted writes invalidate it."""
import hashlib
import sqlite3
import time
from collections import OrderedDict
from contextlib import closing
from pathlib import Path

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


class ReadCacheMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, database_path, dependencies=()):
        super().__init__(app)
        self.database_path = Path(database_path).resolve()
        self.dependencies = [self.database_path, Path(str(self.database_path) + '-wal'), *map(Path, dependencies)]
        self.cache = OrderedDict()
        self.version = None

    def read_version(self):
        stamps = []
        for path in self.dependencies:
            try:
                stat = path.stat()
                # SQLite creates/removes an empty WAL on read-only traffic; that is not a write.
                stamps.append(None if path.name.endswith('-wal') and stat.st_size == 0 else (stat.st_ino, stat.st_mtime_ns, stat.st_size))
            except FileNotFoundError:
                stamps.append(None)
        return hashlib.sha256(repr(stamps).encode()).hexdigest()[:20]

    async def dispatch(self, request, call_next):
        path = request.url.path
        cacheable = request.method == 'GET' and (
            path in {'/api/workspace', '/api/overview', '/api/evaluation', '/api/optimization',
                     '/api/bad-cases', '/api/pipeline', '/api/governance/snapshots',
                     '/api/governance/generation-runs', '/api/governance/candidates'}
            or path.startswith(('/api/evaluations/', '/api/experiments/', '/api/governance/questions/', '/api/documents/'))
            and path.count('/') == 3)
        if not cacheable:
            return await call_next(request)
        version = self.read_version()
        if version != self.version:
            self.cache.clear()
            self.version = version
        # Only read status here; active progress and per-question results are never read by the cache.
        with closing(sqlite3.connect(self.database_path.as_uri() + '?mode=ro', uri=True)) as db:
            active = db.execute("SELECT 1 FROM evaluation_runs WHERE status IN ('queued','running') LIMIT 1").fetchone()
        key = (path, request.url.query, request.headers.get('origin', ''))
        saved = self.cache.get(key)
        if not active and saved and time.monotonic() - saved[0] < 30:
            self.cache.move_to_end(key)
            return Response(saved[1], status_code=200, headers=saved[2])
        response = await call_next(request)
        response.headers['X-Read-Version'] = version
        if active or response.status_code != 200:
            return response
        body = b''.join([chunk async for chunk in response.body_iterator])
        headers = dict(response.headers)
        if self.read_version() == version:
            self.cache[key] = (time.monotonic(), body, headers)
            # ponytail: one local demo process, bounded to 64 responses; no shared cache service.
            while len(self.cache) > 64 or sum(len(item[1]) for item in self.cache.values()) > 64 * 1024 * 1024:
                self.cache.popitem(last=False)
        return Response(body, status_code=response.status_code, headers=headers, background=response.background)
