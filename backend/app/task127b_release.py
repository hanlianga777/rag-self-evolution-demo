"""Prepare the E8-to-E9 handover for the task-bound 127b release."""
import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

from .agent126c import E8_BASELINE
from .agent127a_inheritance import E8_ID

TASK = '127b'
CHECKPOINT = '127b:release-preparation'
ROLLBACK = 'rollback-point-126d-baseline'
AUTHORIZED_AT = '2026-11-27 20:57～21:0x'


def e8_versions(db):
    return db.execute(
        "SELECT id,status,approval_id FROM production_versions WHERE json_extract(snapshot_json,'$.candidate_id') "
        'IN (SELECT id FROM candidate_configs WHERE experiment_id=?)', (E8_ID,)).fetchall()


def prepare_release(engine, candidate, backup):
    store, experiment_id = engine.store, engine.id
    evaluation_run = candidate['result']['evaluation_run_id']
    saved = store.job_checkpoint(experiment_id, CHECKPOINT)
    if saved:
        if (saved['candidate'] != candidate['id'] or saved['evaluation_run'] != evaluation_run or saved['backup'] != str(backup)
                or not backup.is_file() or store.active_production()['id'] != saved['active_version']):
            raise ValueError('127b 保存的发布准备记录与当前状态不一致')
        return saved

    baseline = next((row for row in store.production_versions() if row['id'] == ROLLBACK), None)
    if not baseline or baseline['snapshot'].get('baseline_run_id') != E8_BASELINE:
        raise ValueError('127b 找不到冻结 Baseline 的回滚点')
    rollback_index = engine.rollback_index(baseline)
    rehearsal = engine.rehearse_rollback(baseline, candidate)
    engine.check_stop()

    with store.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        active = [row['id'] for row in e8_versions(db) if row['status'] == 'active']
        if len(active) != 1 or not db.execute('SELECT 1 FROM experiments WHERE id=?', (E8_ID,)).fetchone():
            raise ValueError('127b 正式库中的 E8 已变化')
        _backup(Path(store.database_path).resolve(), backup, active[0], experiment_id, candidate['id'], evaluation_run)
        engine.check_stop()

        receipt = {'candidate': candidate['id'], 'backup': str(backup), 'rollback': ROLLBACK,
                   'active_version': active[0], 'evaluation_run': evaluation_run,
                   'rollback_rehearsal': rehearsal, 'rollback_index': rollback_index}
        db.execute('INSERT INTO job_checkpoints VALUES (?,?,?)',
                   (experiment_id, CHECKPOINT, json.dumps(receipt, ensure_ascii=False)))
    return receipt


def retire_e8(db, receipt):
    """Run inside the publication transaction, after the normal release checks."""
    versions = e8_versions(db)
    staged = [row['id'] for row in versions if row['status'] == 'active'] == [receipt['active_version']]
    rollback = db.execute("SELECT 1 FROM production_versions WHERE id=? AND status='archived' "
                          "AND json_extract(snapshot_json,'$.baseline_run_id')=?", (ROLLBACK, E8_BASELINE)).fetchone()
    if not staged or not rollback or not Path(receipt['backup']).is_file():
        raise ValueError('127b 已备份版本或 Baseline 回滚点发生变化')
    candidates = [row[0] for row in db.execute('SELECT id FROM candidate_configs WHERE experiment_id=?', (E8_ID,))]
    run_ids = [row[0] for row in db.execute(
        "SELECT id FROM evaluation_runs WHERE json_extract(config_json,'$.candidate_id') IN "
        '(SELECT id FROM candidate_configs WHERE experiment_id=?)', (E8_ID,))]
    for row in versions:
        version = row['id']
        db.execute('DELETE FROM rollback_history WHERE from_version_id=? OR to_version_id=?', (version, version))
        db.execute('DELETE FROM production_versions WHERE id=?', (version,))
        db.execute('DELETE FROM approvals WHERE id=?', (row['approval_id'],))
    for table in ('agent_traces', 'tool_calls', 'recommendations', 'candidate_configs'):
        db.execute(f'DELETE FROM {table} WHERE experiment_id=?', (E8_ID,))
    db.executemany('DELETE FROM approvals WHERE target_id=?', [(item,) for item in [E8_ID, *candidates]])
    for table in ('evaluation_case_results', 'evaluation_checkpoints', 'bad_cases'):
        db.executemany(f'DELETE FROM {table} WHERE run_id=?', [(item,) for item in run_ids])
    checkpoint_owners = [E8_ID, *run_ids, *(f'candidate:{cid}' for cid in candidates)]
    db.executemany('DELETE FROM job_checkpoints WHERE run_id=?', [(item,) for item in checkpoint_owners])
    lease_keys = [f'{kind}:{E8_ID}' for kind in ('cycle', 'agent', 'composite')]
    lease_keys.extend(f'evaluation:{rid}' for rid in run_ids)
    db.executemany('DELETE FROM task_leases WHERE task_key=?', [(key,) for key in lease_keys])
    if db.execute("SELECT 1 FROM sqlite_master WHERE name='paid_schedule_settings'").fetchone():
        db.executemany('DELETE FROM paid_schedule_settings WHERE key=?', [(f'override:{key}',) for key in lease_keys])
    if db.execute("SELECT 1 FROM sqlite_master WHERE name='model_request_reuse'").fetchone():
        db.executemany('DELETE FROM model_request_reuse WHERE origin=?', [(item,) for item in run_ids])
    db.executemany('DELETE FROM evaluation_runs WHERE id=?', [(item,) for item in run_ids])
    db.execute('DELETE FROM experiments WHERE id=?', (E8_ID,))
    if db.execute('PRAGMA foreign_key_check').fetchone():
        raise ValueError('127b 清理后出现外键不一致')
    return {'removed_versions': [row['id'] for row in versions], 'removed_runs': len(run_ids),
            'removed_candidates': len(candidates)}


def _backup(source, target, online, experiment, candidate, evaluation_run):
    if target.exists():
        # Reuse an intact backup left by an interrupted preparation.
        _check_backup(target, online, experiment, candidate, evaluation_run)
        return
    with TemporaryDirectory(prefix='.127b-', dir=target.parent) as temp:
        staged = Path(temp) / target.name
        staged.touch(mode=0o600)
        with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)) as db:
            with closing(sqlite3.connect(staged)) as dest:
                db.backup(dest)
                dest.execute('PRAGMA journal_mode=DELETE')
        _check_backup(staged, online, experiment, candidate, evaluation_run)
        with staged.open('rb') as handle:
            os.fsync(handle.fileno())
        os.replace(staged, target)
        descriptor = os.open(target.parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def _check_backup(path, online, experiment, candidate, evaluation_run):
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as db:
        winner = db.execute("""SELECT c.id FROM candidate_configs c JOIN evaluation_runs r
            ON r.id=json_extract(c.result_json,'$.evaluation_run_id')
            WHERE c.experiment_id=? AND c.id=? AND r.id=? AND r.status='completed'""",
                            (experiment, candidate, evaluation_run)).fetchone()
        if (db.execute('PRAGMA quick_check').fetchall() != [('ok',)]
                or db.execute("SELECT id FROM production_versions WHERE status='active'").fetchall() != [(online,)]
                or not winner or not db.execute('SELECT 1 FROM experiments WHERE id=?', (E8_ID,)).fetchone()):
            raise ValueError('127b 正式库备份验证失败')
