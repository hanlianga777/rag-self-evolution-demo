"""Persist the first successful result for an identical frozen evaluation input."""
import hashlib
import json
import threading
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy

_scope = ContextVar('evaluation_reuse_scope', default=None)
# Serial evaluation workers share one process. Keep check/call/save atomic there.
_lock = threading.RLock()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


@contextmanager
def reuse_scope(store, run):
    snapshot = json.loads(run['dataset_snapshot_json'])
    identity = digest([snapshot, run['config'].get('knowledge_identity'), run['judge']])
    with store.connection() as db:
        db.execute('CREATE TABLE IF NOT EXISTS model_request_reuse (identity TEXT, kind TEXT, request_hash TEXT, origin TEXT, result_json TEXT, PRIMARY KEY(identity,kind,request_hash))')
    token = _scope.set((store, identity, run['id']))
    try:
        yield
    finally:
        _scope.reset(token)


@contextmanager
def bypass_reuse():
    token = _scope.set(None)
    try:
        yield
    finally:
        _scope.reset(token)


def reuse_result(kind, payload, action):
    scope = _scope.get()
    if scope is None:
        return action()
    import os
    if kind == 'judge' and os.environ.get('JUDGE_REUSE_BYPASS') == '1':
        # 仅供内部"同一批回答判两遍"的一致率测试；结果不写入复用表，也不进入正式成绩。
        return action()
    store, identity, origin = scope
    request_hash = digest(payload)
    with _lock:
        with store.connection() as db:
            saved = db.execute('SELECT origin,result_json FROM model_request_reuse WHERE identity=? AND kind=? AND request_hash=?', (identity,kind,request_hash)).fetchone()
        if saved:
            result = json.loads(saved['result_json'])
            result['reused_from'] = {'run_id':saved['origin'], 'request_sha256':request_hash, 'kind':kind}
            return result
        result = action()  # Exceptions and invalid judgments never become reusable.
        with store.connection() as db:
            db.execute('INSERT OR IGNORE INTO model_request_reuse VALUES (?,?,?,?,?)', (identity,kind,request_hash,origin,json.dumps(result,ensure_ascii=False)))
        return deepcopy(result)


def carry_generation_reuse(store, source, target):
    """Carry exact request entries only after Judge-only replay validation."""
    if (source['dataset_snapshot_json'] != target['dataset_snapshot_json'] or source['config'] != target['config']
            or any(source['judge'].get(k) != target['judge'].get(k) for k in
                   ('model', 'generation_prompt_version', 'generation_boundary_sha256', 'execution_snapshot'))):
        return 0
    source_identity = digest([json.loads(source['dataset_snapshot_json']), source['config'].get('knowledge_identity'), source['judge']])
    with reuse_scope(store, target):
        _, target_identity, _ = _scope.get()
        with store.connection() as db:
            return db.execute("INSERT OR IGNORE INTO model_request_reuse SELECT ?,kind,request_hash,origin,result_json FROM model_request_reuse WHERE identity=? AND kind IN ('generation','retrieval')",
                              (target_identity, source_identity)).rowcount


def matching_configuration(store, run):
    """Reuse a whole completed result only under the identical frozen contract."""
    from .policy import ALLOWED_SEARCH_SPACE
    def configuration(config):
        return {k:v for k,v in config.items() if k in ALLOWED_SEARCH_SPACE or k == 'knowledge_identity'}
    with store.connection() as db:
        ids = [r[0] for r in db.execute("SELECT id FROM evaluation_runs WHERE status='completed' AND dataset_version_id=? AND id<>? ORDER BY created_at,id", (run['dataset_version_id'],run['id']))]
    for key in ids:
        source = store.evaluation_run(key)
        if (source['dataset_snapshot_json'] == run['dataset_snapshot_json'] and source['judge'] == run['judge']
                and configuration(source['config']) == configuration(run['config'])
                and source['result'].get('evaluation_complete') is True and source['result'].get('technical_failed') == 0):
            cases = {c['question_id']:c for c in store.evaluation_case_results(key)}
            if set(cases) == set(json.loads(run['dataset_snapshot_json'])['question_ids']):
                return cases
    return {}


def reused_case(source):
    case = deepcopy(source)
    case.pop('run_id',None);case.pop('question_id',None)
    provenance = {'run_id':source['run_id'], 'kind':'configuration'}
    case['reused_from'] = provenance
    metrics = case['programmatic_metrics']
    metrics.update(token_usage={}, judge_usage=[], input_tokens=0, output_tokens=0, estimated_cost=0, judge_cost=0,
                   request_reuse={'generation':provenance,'judge':provenance}, timing_provenance='复用来源实测耗时')
    case['judge_result'].update(token_usage=[], estimated_cost=0, reused_from=provenance)
    return case
