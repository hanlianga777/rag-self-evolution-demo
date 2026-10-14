"""Whole-object retention and an explicitly authorized experiment reset. No Providers."""
import json
from datetime import datetime, timezone

RETAINED_TABLES = {'schema_migrations', 'tool_registry', 'pipeline_config_draft', 'alias_mappings'}
EXPERIMENT_TABLES = (
    'evaluation_case_results', 'bad_cases', 'agent_traces', 'tool_calls', 'recommendations',
    'candidate_configs', 'optimization_triggers', 'monitoring_events', 'experiments', 'evaluation_runs',
    'review_events', 'probe_results', 'qc_results', 'question_quality_audits', 'candidate_revision_runs',
    'golden_generation_artifacts', 'golden_generation_runs', 'coverage_plan_previews',
    'questions', 'dataset_versions', 'approvals', 'rollback_history', 'business_import_batches', 'demo_state',
)
ACTIVE = ('queued', 'running', 'generating', 'coverage', 'validation', 'validating', 'probing', 'qc')


def table_counts(connection):
    return {r[0]: connection.execute('SELECT count(*) FROM "'+r[0]+'"').fetchone()[0]
            for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()}


def require_idle(connection):
    for table in ('evaluation_runs', 'experiments', 'candidate_configs', 'golden_generation_runs', 'candidate_revision_runs'):
        if connection.execute('SELECT 1 FROM '+table+' WHERE status IN ('+','.join('?' for _ in ACTIVE)+') LIMIT 1', ACTIVE).fetchone():
            raise ValueError('存在活动任务，禁止破坏性清理：'+table)


def reset_experiments(store, corpus_identity=None):
    """Caller must stop writers and take exactly one SQLite Backup API backup first."""
    with store.connection() as c:
        c.execute('BEGIN IMMEDIATE')
        require_idle(c)
        before=table_counts(c)
        unknown=set(before)-set(EXPERIMENT_TABLES)-RETAINED_TABLES-{'production_versions'}
        if any(before[t] for t in unknown):
            raise ValueError('存在未知关联表，先完成依赖审查：'+','.join(sorted(unknown)))
        active=c.execute("SELECT * FROM production_versions WHERE status='active'").fetchall()
        if len(active)!=1:raise ValueError('活动运行配置不是唯一记录，停止清理')
        old=active[0];snapshot=json.loads(old['snapshot_json'])
        # Keep the exact existing Knowledge binding (including unbound Legacy semantics).
        binding={k:snapshot[k] for k in ('knowledge_identity','embedding_model','rerank_mode') if k in snapshot}
        binding['reset_provenance']='runtime_configuration_only; unassessed; not published'
        for table in EXPERIMENT_TABLES:
            if table in before:c.execute('DELETE FROM '+table)
        c.execute('DELETE FROM production_versions')
        now=datetime.now(timezone.utc).isoformat()
        c.execute('INSERT INTO production_versions VALUES (?,?,?,?,?,?,?,?,?)',
                  ('runtime-initial-'+datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f'),'active',old['config_json'],None,None,None,None,now,json.dumps(binding,ensure_ascii=False)))
        if corpus_identity and corpus_identity.get('corpus_snapshot_id'):
            c.execute('INSERT OR REPLACE INTO schema_migrations(name,applied_at) VALUES (?,?)',
                      ('experiment-reset-v1:'+corpus_identity['corpus_snapshot_id'],now))
        # Preserve migration markers, so restart cannot seed legacy questions again.
        return {'before':before,'after':table_counts(c),'runtime_config':json.loads(old['config_json']),
                'runtime_binding':binding,'old_active_version':old['id']}


def _delete_except(c, table, field, ids):
    # Temporary sets avoid SQLite variable limits for full question/trace collections.
    c.execute('CREATE TEMP TABLE IF NOT EXISTS retained_ids(id TEXT PRIMARY KEY)')
    c.execute('DELETE FROM retained_ids')
    c.executemany('INSERT INTO retained_ids VALUES (?)',((i,) for i in ids if i))
    c.execute(f'DELETE FROM {table} WHERE {field} NOT IN (SELECT id FROM retained_ids)')


def prune_history(store, limit=50):
    """Retain complete referenced objects; the limit never applies to case/trace rows."""
    if type(limit) is not int or not 1<=limit<=50:raise ValueError('history limit must be 1..50')
    with store.connection() as c:
        c.execute('BEGIN IMMEDIATE')
        # Project only relationship fields; do not deserialize large saved checkpoint payloads.
        evals={r['id']:dict(r) for r in c.execute("SELECT id,status,dataset_version_id,created_at,json_extract(config_json,'$.candidate_id') candidate_id,json_extract(result_json,'$.resume_source_id') source_id,coalesce(json_extract(config_json,'$.source_evaluation_id'),json_extract(judge_json,'$.source_evaluation_id')) replay_source_id FROM evaluation_runs ORDER BY created_at DESC,rowid DESC")}
        exps={r['id']:dict(r) for r in c.execute('SELECT id,status,baseline_run_id FROM experiments ORDER BY created_at DESC,rowid DESC')}
        candidates={r['id']:dict(r) for r in c.execute("SELECT id,status,experiment_id,json_extract(result_json,'$.evaluation_run_id') run_id FROM candidate_configs")}
        datasets={r['id']:dict(r) for r in c.execute("SELECT id,status,json_extract(snapshot_json,'$.generation_run_id') generation_id,json_extract(snapshot_json,'$.question_ids') question_ids FROM dataset_versions ORDER BY created_at DESC,rowid DESC")}
        generations={r['id']:dict(r) for r in c.execute('SELECT id,status,question_ids_json question_ids FROM golden_generation_runs ORDER BY created_at DESC,rowid DESC')}
        keep_e=set(list(k for k,r in evals.items() if r['status'] not in ACTIVE)[:limit])|{k for k,r in evals.items() if r['status'] in ACTIVE}
        keep_x=set(list(k for k,r in exps.items() if r['status'] not in ACTIVE+('pending_agent',))[:limit])|{k for k,r in exps.items() if r['status'] in ACTIVE+('pending_agent',)}
        keep_g=set(list(generations)[:limit])|{k for k,r in generations.items() if r['status'] in ACTIVE+('needs_regeneration','interrupted')}
        keep_d=set(list(datasets)[:limit]);keep_q=set();keep_c=set()
        current=store.current_baseline_identity(c)
        if current.get('current_baseline_id'):keep_e.add(current['current_baseline_id'])
        if current.get('current_experiment_id'):keep_x.add(current['current_experiment_id'])
        if current.get('current_golden_id'):keep_d.add(current['current_golden_id'])
        # Published versions retain their audit chains for rollback; referenced objects are exempt.
        for r in c.execute("SELECT evaluation_run_id,dataset_version_id,json_extract(snapshot_json,'$.candidate_id') candidate_id FROM production_versions"):
            if r['evaluation_run_id']:keep_e.add(r['evaluation_run_id'])
            if r['dataset_version_id']:keep_d.add(r['dataset_version_id'])
            if r['candidate_id']:keep_c.add(r['candidate_id'])
        questions={r['id']:dict(r) for r in c.execute("SELECT id,stage,json_extract(raw_json,'$.generation_run_id') generation_id,json_extract(raw_json,'$.source_positive_id') positive_id,json_extract(raw_json,'$.replaces_question_id') replaces_id,json_extract(raw_json,'$.source_reference.question_id') source_id FROM questions")}
        keep_q.update(k for k,r in questions.items() if r['stage']=='candidate' and not r['generation_id'])
        imports={r['sha256']:json.loads(r['ids'] or '[]') for r in c.execute("SELECT sha256,json_extract(result_json,'$.question_ids') ids FROM business_import_batches ORDER BY rowid DESC")}
        keep_i=set(list(imports)[:limit])
        for r in c.execute("SELECT generation_run_id,json_extract(audit_json,'$.question_ids') ids FROM candidate_revision_runs WHERE status IN ('queued','generating','validating','probing','qc','preview_ready','interrupted')"):
            keep_g.add(r[0]);keep_q.update(json.loads(r[1] or '[]'))
        recent_triggers=list(c.execute('SELECT optimization_run_id,status FROM optimization_triggers ORDER BY created_at DESC,rowid DESC'))
        keep_x.update(r['optimization_run_id'] for i,r in enumerate(recent_triggers)
                      if r['optimization_run_id'] and (i<limit or r['status']=='pending_human_confirm'))
        # Trace resumptions, whole Golden groups and source ancestry form one reachability closure.
        while True:
            size=sum(map(len,(keep_e,keep_x,keep_g,keep_d,keep_q,keep_c,keep_i)))
            for k in list(keep_x):
                if k in exps:keep_e.add(exps[k]['baseline_run_id'])
            for k,r in candidates.items():
                if r['experiment_id'] in keep_x or k in keep_c or r['status'] in ACTIVE:
                    keep_c.add(k);keep_x.add(r['experiment_id'])
                    if r['run_id']:keep_e.add(r['run_id'])
            for k in list(keep_e):
                r=evals.get(k,{})
                if r.get('dataset_version_id'):keep_d.add(r['dataset_version_id'])
                if r.get('candidate_id'):keep_c.add(r['candidate_id'])
                if r.get('source_id'):keep_e.add(r['source_id'])
                if r.get('replay_source_id'):keep_e.add(r['replay_source_id'])
            for k in list(keep_d):
                r=datasets.get(k,{})
                if r.get('generation_id'):keep_g.add(r['generation_id'])
                keep_q.update(json.loads(r.get('question_ids') or '[]'))
            for k in list(keep_g):keep_q.update(json.loads(generations.get(k,{}).get('question_ids') or '[]'))
            for key,ids in imports.items():
                if key in keep_i or any(q in keep_q for q in ids):
                    keep_i.add(key);keep_q.update(q for q in ids if q in questions)
            for k in list(keep_q):
                r=questions.get(k,{})
                if r.get('generation_id'):keep_g.add(r['generation_id'])
                keep_q.update(r[f] for f in ('positive_id','replaces_id','source_id') if r.get(f) in questions)
            if size==sum(map(len,(keep_e,keep_x,keep_g,keep_d,keep_q,keep_c,keep_i))):break
        for table,field,ids in (
            ('evaluation_case_results','run_id',keep_e),('bad_cases','run_id',keep_e),
            ('agent_traces','experiment_id',keep_x),('tool_calls','experiment_id',keep_x),('recommendations','experiment_id',keep_x),
            ('candidate_configs','id',keep_c),('experiments','id',keep_x),('evaluation_runs','id',keep_e),
            ('review_events','question_id',keep_q),('probe_results','question_id',keep_q),('qc_results','question_id',keep_q),
            ('question_quality_audits','question_id',keep_q),('candidate_revision_runs','generation_run_id',keep_g),
            ('golden_generation_artifacts','generation_run_id',keep_g),('golden_generation_runs','id',keep_g),
            ('questions','id',keep_q),('dataset_versions','id',keep_d)):
            _delete_except(c,table,field,ids)
        # Monitoring events referenced by any retained trigger/experiment/approval remain intact.
        events={r[0] for r in c.execute('SELECT id FROM monitoring_events ORDER BY created_at DESC,rowid DESC LIMIT ?', (limit,))}
        triggers=[]
        for r in c.execute('SELECT * FROM optimization_triggers ORDER BY created_at DESC,rowid DESC'):
            if r['optimization_run_id'] in keep_x or r['status']=='pending_human_confirm' or len(triggers)<limit:
                triggers.append(r['id']);events.add(r['event_id'])
        _delete_except(c,'optimization_triggers','id',triggers)
        _delete_except(c,'monitoring_events','id',events)
        targets=keep_e|keep_x|keep_c|keep_d|keep_g|keep_q|set(triggers)|events|{r[0] for r in c.execute('SELECT id FROM production_versions')}
        approvals={r[0] for r in c.execute('SELECT id FROM approvals WHERE target_id IN (SELECT id FROM production_versions)')}
        approvals.update(r[0] for r in c.execute('SELECT approval_id FROM production_versions WHERE approval_id IS NOT NULL'))
        approvals.update(r['id'] for r in c.execute('SELECT id,target_id FROM approvals') if r['target_id'] in targets)
        _delete_except(c,'approvals','id',approvals)
        # Previews/import receipts are caches, not Golden identity or Provider configuration.
        _delete_except(c,'business_import_batches','sha256',keep_i)
        for table in ('coverage_plan_previews',):
            key='id' if table=='coverage_plan_previews' else 'sha256'
            ids=[r[0] for r in c.execute(f'SELECT {key} FROM {table} ORDER BY rowid DESC LIMIT ?', (limit,))]
            _delete_except(c,table,key,ids)
        return {'retained_evaluations':len(keep_e&set(evals)), 'retained_experiments':len(keep_x&set(exps)),
                'history_limit':limit,'referenced_objects_exempt':True}
