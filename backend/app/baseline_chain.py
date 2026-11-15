"""One explicitly armed Baseline -> Agent chain, driven by backend recovery monitor."""
import json
import threading
from datetime import datetime, timezone

from .paid_schedule import _settings, _write, unattended_authorization
from .policy import DEFAULT_PIPELINE_CONFIG

KEY = 'baseline_agent_chain'
_lock = threading.Lock()


def chain_status(store):
    return _settings(store).get(KEY, {})


def restore_initial_config(store):
    """Archive the old release, retaining its configuration and rollback lineage."""
    from .corpus import current_manifest, manifest_identity
    from .full_text import CORPUS_LOCK
    with CORPUS_LOCK, store.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        previous = store.active_production()
        db.execute('DELETE FROM pipeline_config_draft')
        if previous and previous['config'] == DEFAULT_PIPELINE_CONFIG:
            return previous
        now = datetime.now(timezone.utc)
        version_id = 'initial-' + now.strftime('%Y%m%d%H%M%S%f')
        snapshot = {'knowledge_identity':manifest_identity(current_manifest()), 'corpus_fingerprint':manifest_identity(current_manifest()),
                    'actor':'用户', 'audit_note':'用户 2026-11-14 授权新版本恢复初始配置', 'previous_version_id':previous['id'] if previous else None}
        db.execute("UPDATE production_versions SET status='archived' WHERE status='active'")
        db.execute('INSERT INTO production_versions(id,status,config_json,previous_version_id,created_at,snapshot_json) VALUES (?,?,?,?,?,?)',
                   (version_id, 'active', json.dumps(DEFAULT_PIPELINE_CONFIG), previous['id'] if previous else None, now.isoformat(), json.dumps(snapshot, ensure_ascii=False)))
    return store.active_production()


def arm_chain(store, baseline_id, *, round_policy=None, paid_run=None, causal_evidence=False):
    previous = chain_status(store)
    if previous and previous.get('baseline_id') != baseline_id and causal_evidence:
        experiment = store.experiment(previous.get('experiment_id'), light=True) if previous.get('experiment_id') else None
        if not experiment or experiment['result'].get('optimization_cycle', {}).get('status') != 'recommended':
            raise ValueError('前次串联尚未结束，不能启动新实验')
        history = _settings(store).get(KEY+'_history', [])
        _write(store, KEY+'_history', history + [previous])
        previous = {}
    if previous and previous.get('baseline_id') != baseline_id and previous.get('status') not in {'completed','failed'}:
        raise ValueError('已有Baseline串联记录，禁止重复启动')
    if previous.get('baseline_id') == baseline_id:
        return previous
    run = store.evaluation_run(baseline_id, light=True)
    if not run or run['config'].get('run_target') != 'baseline':
        raise ValueError('串联只能绑定显式Baseline')
    state = {'baseline_id':baseline_id, 'snapshot_id':run['dataset_version_id'], 'status':'waiting_baseline', 'designated':False,
             'actor':'用户', 'audit_note':'用户 2026-11-14 预先授权', 'authorized_at':datetime.now(timezone.utc).isoformat(), 'budget':12}
    if round_policy: state['round_policy'] = round_policy
    if paid_run: state['paid_run'] = paid_run
    if causal_evidence: state['causal_evidence'] = True
    _write(store, KEY, state)
    return state


def advance_chain(store, runtime):
    """Called by the existing 5-second monitor; never creates a second experiment."""
    with _lock:
        state = chain_status(store)
        if state.get('status') != 'waiting_baseline':
            return state
        run = store.evaluation_run(state['baseline_id'], light=True)
        if not run or run['status'] != 'completed':
            return state
        result = run['result']
        if result.get('evaluation_complete') is not True or result.get('technical_failed') != 0:
            state.update(status='failed', error='Baseline未完整结束或存在技术失败，保留断点')
            _write(store, KEY, state)
            return state
        if not unattended_authorization(store).get('enabled'):
            return state
        # Persist the selected role before current-baseline guards resolve the run.
        state['designated'] = True
        _write(store, KEY, state)
        store.require_current_baseline(run['id'])
        with store.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            state = chain_status(store)
            if not state.get('experiment_id'):
                experiment_id = 'EXP-' + datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')
                context = {'strategy_contract':'agent-strategy-4' if state.get('round_policy') else 'agent-strategy-3', 'chain_baseline_id':run['id'], 'audit_note':state['audit_note']}
                context.update({k:state[k] for k in ('round_policy','paid_run','causal_evidence') if k in state})
                db.execute('INSERT INTO experiments VALUES (?,?,?,?,?)', (experiment_id,run['id'],'analyzing',json.dumps(context,ensure_ascii=False),datetime.now(timezone.utc).isoformat()))
                state['experiment_id'] = experiment_id
                db.execute('UPDATE paid_schedule_settings SET value_json=? WHERE key=?', (json.dumps(state,ensure_ascii=False),KEY))
        from .optimization_cycle import claim_cycle, run_until_qualified
        experiment = store.experiment(state['experiment_id'], light=True)
        if experiment['result'].get('optimization_cycle', {}).get('status') != 'running':
            claim_cycle(store, state['experiment_id'])
            threading.Thread(target=run_until_qualified, args=(store,runtime,state['experiment_id']), kwargs={'claimed':True}, daemon=True).start()
        state.update(status='agent_running')
        _write(store, KEY, state)
        return state
