"""SQLite execution leases shared by the evaluation and optimization workers."""
import json
import logging
import os
import socket
import threading
import time
from contextlib import contextmanager
from contextvars import Context, ContextVar
from datetime import datetime, timezone
from uuid import uuid4

HEARTBEAT_SECONDS = 30
LEASE_SECONDS = 180
ACTIVE_STATES = ('queued', 'running', 'retry_wait', 'recovering')
STATES = (*ACTIVE_STATES, 'blocked', 'paused', 'completed', 'failed')
_workers = ContextVar('task_workers', default=())


class LeaseLost(InterruptedError):
    """The worker may no longer call the Provider or commit task results."""


def now():
    return time.time()


def initialize(db):
    db.execute("""CREATE TABLE IF NOT EXISTS task_leases (
        task_key TEXT PRIMARY KEY, business_status TEXT NOT NULL,
        lease_owner TEXT NOT NULL, heartbeat_at REAL NOT NULL,
        lease_expires_at REAL NOT NULL)""")


def row(db, key):
    if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='task_leases'").fetchone():
        return db.execute('SELECT * FROM task_leases WHERE task_key=?', (key,)).fetchone()
    return None


def active(db, key, *, legacy_pid=None, legacy_at=None):
    saved = row(db, key)
    if saved is not None:
        return saved['lease_expires_at'] > now()
    # Only old records lack a lease. Allow an upgrade grace period for an old,
    # live PID if the old worker left a recent timestamp.
    if type(legacy_pid) is not int or legacy_pid <= 0 or not legacy_at:
        return False
    try:
        date = datetime.fromisoformat(legacy_at)
        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)
        if date.timestamp() + LEASE_SECONDS <= now():
            return False
        os.kill(legacy_pid, 0)
    except PermissionError:
        return True
    except (ValueError, ProcessLookupError):
        return False
    return True


def claim(db, key, *, recovering=False, legacy_pid=None, legacy_at=None):
    """Caller holds BEGIN IMMEDIATE, covering eligibility and assignment together."""
    initialize(db)
    if active(db, key, legacy_pid=legacy_pid, legacy_at=legacy_at):
        return None
    token = uuid4().hex
    owner = json.dumps({'pid': os.getpid(), 'hostname': socket.gethostname(), 'token': token})
    at = now()
    db.execute("""INSERT INTO task_leases VALUES (?,?,?,?,?)
        ON CONFLICT(task_key) DO UPDATE SET business_status=excluded.business_status,
        lease_owner=excluded.lease_owner, heartbeat_at=excluded.heartbeat_at,
        lease_expires_at=excluded.lease_expires_at""",
        (key, 'recovering' if recovering else 'queued', owner, at, at + LEASE_SECONDS))
    return token


def current(store, key):
    return next((token for path, task, token in _workers.get()
                 if path == store.database_path and task == key), None)


def require(db, key, token, *, legacy=False):
    saved = row(db, key)
    if saved is None and legacy and token is None:
        return
    if (saved is None or not token or saved['lease_expires_at'] <= now()
            or json.loads(saved['lease_owner'])['token'] != token):
        raise LeaseLost(f'任务执行租约已失效：{key}')


def fence_writes(store, db):
    """Check all enclosing task tokens in the same transaction as result writes."""
    for path, key, token in _workers.get():
        if path == store.database_path:
            require(db, key, token)


def check(store):
    if _workers.get():
        with store.connection() as db:
            fence_writes(store, db)


def set_state(db, key, token, status):
    if status not in STATES:
        raise ValueError(f'不支持的任务状态：{status}')
    require(db, key, token)
    db.execute('UPDATE task_leases SET business_status=? WHERE task_key=?', (status, key))


def update_state(db, store, key, status):
    if token := current(store, key):
        set_state(db, key, token, status)


def renew(store, key, token, *, start=False):
    with store.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        at = now()
        return bool(db.execute("""UPDATE task_leases SET heartbeat_at=?, lease_expires_at=?,
            lease_owner=CASE WHEN ? THEN json_set(lease_owner,'$.worker_started',1) ELSE lease_owner END,
            business_status=CASE WHEN ? AND business_status='queued' THEN 'running' ELSE business_status END
            WHERE task_key=? AND json_extract(lease_owner,'$.token')=? AND lease_expires_at>?
            AND (NOT ? OR coalesce(json_extract(lease_owner,'$.worker_started'),0)=0)""",
            (at, at + LEASE_SECONDS, start, start, key, token, at, start)).rowcount)


@contextmanager
def work(store, key, token):
    if current(store, key) == token and token:
        yield
        return
    if not token or not renew(store, key, token, start=True):
        raise LeaseLost(f'任务执行租约已失效：{key}')
    stop = threading.Event()

    def heartbeat():
        while not stop.wait(HEARTBEAT_SECONDS):
            try:
                if not renew(store, key, token):
                    return
            except Exception:
                logging.exception('任务心跳写入失败：%s', key)

    thread = threading.Thread(target=Context().run, args=(heartbeat,), name='task-lease-heartbeat', daemon=True)
    thread.start()
    binding = _workers.set((*_workers.get(), (store.database_path, key, token)))
    try:
        check(store)
        yield
    finally:
        _workers.reset(binding)
        stop.set()
        with store.connection() as db:
            db.execute("""UPDATE task_leases SET lease_expires_at=0
                WHERE task_key=? AND json_extract(lease_owner,'$.token')=?""", (key, token))


def evaluation_active(db, run, result=None, *, include_unclaimed=False):
    result = result if result is not None else json.loads(run['result_json'])
    auto = result.get('auto_recovery', {})
    return active(db, 'evaluation:' + run['id'],
                  legacy_pid=result.get('execution_owner_pid') if auto.get('worker_token') or include_unclaimed else None,
                  legacy_at=auto.get('started_at') or dict(run).get('created_at'))


def cycle_active(db, experiment_id, state):
    return active(db, 'cycle:' + experiment_id,
                  legacy_pid=state.get('owner_pid') if state.get('status') == 'running' else None,
                  legacy_at=state.get('updated_at') or state.get('started_at'))


def complete_evaluation(status, result):
    return status == 'completed' and result.get('evaluation_complete') is not False


def progress_state(result):
    if (result.get('price_pause') or {}).get('paused'):
        return 'paused'
    retry = (result.get('provider_retry') or result.get('agent_provider_retry') or {}).get('state')
    return retry if retry in {'retry_wait', 'recovering', 'blocked'} else 'running'


def agent_active(db, experiment_id, result, *, legacy_generating=False):
    saved = result.get('agent_generation') or {}
    return active(db, 'agent:' + experiment_id, legacy_pid=saved.get('owner_pid') if legacy_generating else None,
                  legacy_at=saved.get('started_at'))


def mark_paused(db, key):
    if row(db, key):
        db.execute("UPDATE task_leases SET business_status='paused' WHERE task_key=?", (key,))
