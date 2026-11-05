"""Task019a one-off cleanup. No model calls, no repository writes, online backup first."""
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from contextlib import closing


def delete_optimization_history(store, backup_directory, *, expected_experiment_ids=None):
    def read_plan(db):
        experiments = [r[0] for r in db.execute('SELECT id FROM experiments')]
        if expected_experiment_ids is not None and set(experiments) != set(expected_experiment_ids):
            raise ValueError('实验清单已变化，拒绝删除；不要删除019a新实验')
        if db.execute("SELECT 1 FROM evaluation_runs WHERE status IN ('queued','running') LIMIT 1").fetchone() or db.execute("SELECT 1 FROM experiments WHERE status='generating' OR json_extract(result_json,'$.optimization_cycle.status')='running' LIMIT 1").fetchone():
            raise ValueError('仍有任务在运行，拒绝删除')
        candidates = [r[0] for r in db.execute('SELECT id FROM candidate_configs')]
        runs = [dict(r) for r in db.execute('SELECT id,config_json,result_json FROM evaluation_runs')]
        targets = {r['id'] for r in runs if (json.loads(r['config_json']).get('run_target')=='sandbox_candidate'
            or json.loads(r['config_json']).get('candidate_id') in candidates)}
        while True:
            more = {r['id'] for r in runs if json.loads(r['result_json']).get('resume_source_id') in targets
                or (json.loads(r['result_json']).get('judge_replay') or {}).get('source_run_id') in targets}
            if more <= targets:
                break
            targets.update(more)
        pinned = {r[0] for r in db.execute('SELECT baseline_run_id FROM baseline_designations')}
        if targets & pinned:
            raise ValueError('删除集合触及正式Baseline指定记录，拒绝删除')
        if any(r[0] in targets for r in db.execute('SELECT evaluation_run_id FROM production_versions')):
            raise ValueError('删除集合触及线上配置引用，拒绝删除')
        return experiments, candidates, sorted(targets)

    def protected_digest(db, targets):
        digest = hashlib.sha256()
        tables = ('dataset_versions','questions','probe_results','qc_results','review_events','baseline_designations','production_versions','pipeline_config_draft')
        for table in tables:
            digest.update(table.encode())
            for row in db.execute('SELECT * FROM '+table+' ORDER BY rowid'):
                digest.update(json.dumps(tuple(row),ensure_ascii=False).encode())
        for table, column in (('evaluation_runs','id'),('evaluation_case_results','run_id'),('evaluation_checkpoints','run_id'),('bad_cases','run_id')):
            digest.update(table.encode())
            for row in db.execute('SELECT * FROM '+table+' ORDER BY rowid'):
                if row[column] not in targets:
                    digest.update(json.dumps(tuple(row),ensure_ascii=False).encode())
        return digest.hexdigest()

    with store.connection() as db:
        plan = read_plan(db)
        before = protected_digest(db, plan[2])
    directory = Path(backup_directory)
    directory.mkdir(parents=True,exist_ok=True)
    path = directory / ('task019a-before-delete-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.db')
    # SQLite's online backup includes committed WAL content without copying DB files.
    with closing(sqlite3.connect(f'file:{store.database_path}?mode=ro',uri=True)) as source, closing(sqlite3.connect(path)) as destination:
        source.backup(destination)
        if destination.execute('PRAGMA quick_check').fetchone()[0]!='ok':
            raise ValueError('在线备份完整性检查未通过')
    with store.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        if read_plan(db) != plan or protected_digest(db,plan[2]) != before:
            raise ValueError('备份后数据发生变化，拒绝删除')
        experiments, candidates, targets = plan
        deleted = {}
        def remove(table, column, ids):
            deleted[table] = sum(db.execute('DELETE FROM '+table+' WHERE '+column+'=?',(value,)).rowcount for value in ids)
        for table in ('evaluation_case_results','evaluation_checkpoints','bad_cases'):
            remove(table,'run_id',targets)
        remove('job_checkpoints','run_id', [*targets,*experiments,*['candidate:'+c for c in candidates]])
        remove('evaluation_runs','id',targets)
        for table in ('agent_traces','tool_calls','recommendations'):
            remove(table,'experiment_id',experiments)
        remove('approvals','target_id',[*experiments,*candidates,*targets])
        remove('optimization_triggers','optimization_run_id',experiments)
        remove('candidate_configs','id',candidates)
        remove('experiments','id',experiments)
        # Task-scoped transient schedule overrides must not retain deleted identities.
        keys = [r[0] for r in db.execute('SELECT key FROM paid_schedule_settings') if any(value in r[0] for value in [*experiments,*candidates,*targets])]
        remove('paid_schedule_settings','key',keys)
        after = protected_digest(db,targets)
        if before != after:
            raise ValueError('保护数据校验失败，事务回滚')
    for stale in directory.glob('task019a-before-delete-*.db'):
        if stale != path and stale.is_file() and not stale.is_symlink():
            stale.unlink()
    return {'backup_path':str(path.resolve()),'experiment_ids':experiments,'candidate_ids':candidates,
        'evaluation_ids':targets,'deleted':deleted,'protected_sha256_before':before,'protected_sha256_after':after,
        'completed_at':datetime.now(timezone.utc).isoformat()}
