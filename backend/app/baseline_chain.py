"""One explicitly armed Baseline -> Agent chain, driven by backend recovery monitor."""
import json
import threading
from datetime import datetime, timezone

from . import verdict
from .paid_schedule import _settings, _write, unattended_authorization
from .policy import DEFAULT_PIPELINE_CONFIG, MAX_EVALS

KEY = 'baseline_agent_chain'
_lock = threading.Lock()


def chain_status(store):
    return _settings(store).get(KEY, {})


def restore_initial_config(store, config=None, audit_note='用户 2026-11-16 授权新版本恢复初始配置'):
    """Archive the old release, retaining its configuration and rollback lineage."""
    from .corpus import current_manifest, manifest_identity
    from .full_text import CORPUS_LOCK
    target = dict(config or DEFAULT_PIPELINE_CONFIG)
    with CORPUS_LOCK, store.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        previous = store.active_production()
        db.execute('DELETE FROM pipeline_config_draft')
        if previous and previous['config'] == target:
            return previous
        now = datetime.now(timezone.utc)
        version_id = 'initial-' + now.strftime('%Y%m%d%H%M%S%f')
        snapshot = {'knowledge_identity':manifest_identity(current_manifest()), 'corpus_fingerprint':manifest_identity(current_manifest()),
                    'actor':'用户', 'audit_note':audit_note, 'previous_version_id':previous['id'] if previous else None}
        db.execute("UPDATE production_versions SET status='archived' WHERE status='active'")
        db.execute('INSERT INTO production_versions(id,status,config_json,previous_version_id,created_at,snapshot_json) VALUES (?,?,?,?,?,?)',
                   (version_id, 'active', json.dumps(target), previous['id'] if previous else None, now.isoformat(), json.dumps(snapshot, ensure_ascii=False)))
    return store.active_production()


def arm_chain(store, baseline_id, *, round_policy=None, paid_run=None, causal_evidence=False, audit_note='用户 2026-11-16 预先授权'):
    previous = chain_status(store)
    if previous and previous.get('baseline_id') != baseline_id and causal_evidence:
        experiment = store.experiment(previous.get('experiment_id'), light=True) if previous.get('experiment_id') else None
        failed_before_agent = previous.get('status') == 'failed' and not previous.get('experiment_id')
        if not failed_before_agent and (not experiment or experiment['result'].get('optimization_cycle', {}).get('status') != 'recommended'):
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
             'actor':'用户', 'audit_note':audit_note, 'authorized_at':datetime.now(timezone.utc).isoformat(), 'budget':MAX_EVALS}
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
        auto = result.get('auto_recovery') or {}
        if (result.get('evaluation_complete') is False and auto.get('enabled', auto.get('authorized'))
                and auto.get('state') not in {'blocked', 'stopped', 'exhausted'} and not result.get('stop_request')):
            return state
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
                from .agent_strategy import NEW_EXPERIMENT_STRATEGY
                context = {**NEW_EXPERIMENT_STRATEGY, 'chain_baseline_id':run['id'], 'audit_note':state['audit_note']}
                context.update({k:state[k] for k in ('round_policy','paid_run','causal_evidence') if k in state})
                if verdict.records(store, run['id'], connection=db):
                    launch = store.new_verdict_experiment(db, run['id'])
                    context = {**context, **launch,
                               'round_policy': {**launch['round_policy'], **context.get('round_policy', {})}}
                db.execute('INSERT INTO experiments VALUES (?,?,?,?,?)', (experiment_id,run['id'],'analyzing',json.dumps(context,ensure_ascii=False),datetime.now(timezone.utc).isoformat()))
                state['experiment_id'] = experiment_id
                db.execute('UPDATE paid_schedule_settings SET value_json=? WHERE key=?', (json.dumps(state,ensure_ascii=False),KEY))
        from .optimization_cycle import claim_cycle, cycle_occupied, run_until_qualified, take_cycle_claim
        experiment = store.experiment(state['experiment_id'], light=True)
        if not cycle_occupied(store, experiment) and not experiment['result'].get('optimization_cycle'):
            claim_cycle(store, state['experiment_id'])
            threading.Thread(target=run_until_qualified, args=(store,runtime,state['experiment_id']), kwargs={'claimed':True, 'lease_token':take_cycle_claim(store, state['experiment_id'])}, daemon=True).start()
        state.update(status='agent_running')
        _write(store, KEY, state)
        return state
