"""SQLite settings shared by runtime readers and writers."""
import logging
import sqlite3
import time
from pathlib import Path


def locked(error):
    return isinstance(error, sqlite3.OperationalError) and any(s in str(error).lower() for s in ('locked', 'busy'))


def retry_storage(action):
    """Retry storage only: callers must never wrap a Provider request here."""
    for attempt in range(8):
        try:
            return action()
        except Exception as error:
            if not locked(error) or attempt == 7:
                raise
            delay = min(8, .5 * 2 ** attempt)
            logging.warning('SQLite internal lock retry %s after %.1fs: %s', attempt + 1, delay, error)
            time.sleep(delay)


class Connection(sqlite3.Connection):
    def execute(self, *args, **kwargs):
        return retry_storage(lambda: super(Connection, self).execute(*args, **kwargs))

    def executemany(self, *args, **kwargs):
        return retry_storage(lambda: super(Connection, self).executemany(*args, **kwargs))

    def commit(self):
        return retry_storage(lambda: super(Connection, self).commit())


def open_database(path, *, read_only=False):
    target = Path(path).resolve().as_uri() + '?mode=ro' if read_only else str(path)
    connection = sqlite3.connect(target, uri=read_only, timeout=30, factory=Connection)
    connection.execute('PRAGMA busy_timeout=30000')
    if not read_only:
        if connection.execute('PRAGMA journal_mode').fetchone()[0] != 'wal':
            connection.execute('PRAGMA journal_mode=WAL')
        connection.execute('PRAGMA synchronous=NORMAL')
    return connection
