"""Revalidate an already-paid response and append a recovery; never call a Provider."""
import hashlib
import json
import sqlite3
from pathlib import Path

from .diagnostics import diagnostic_view
from .full_text import CORPUS_LOCK
from .governance import _json, _now
from .optimization import prepare_response
from .policy import DEFAULT_PIPELINE_CONFIG, MAX_EVALS


def digest(value):
    return hashlib.sha256(_json(value).encode()).hexdigest()


def recovery_inputs(store,trace_id,connection):
    trace=connection.execute('SELECT * FROM agent_traces WHERE id=?',(trace_id,)).fetchone()
    if not trace:raise ValueError('来源Trace不存在')
    trace=dict(trace)
    source=connection.execute('SELECT * FROM experiments WHERE id=?',(trace['experiment_id'],)).fetchone()
    if not source:raise ValueError('来源Experiment不存在')
    source=dict(source);audit=json.loads(trace['result_json'])
    baseline=store.require_current_baseline(source['baseline_run_id'],connection)
    rows=[dict(row) for row in connection.execute('SELECT * FROM bad_cases WHERE run_id=? ORDER BY created_at DESC',(source['baseline_run_id'],))]
    binding=digest({'trace':trace,'experiment':source,'baseline':baseline,'bad_cases':rows})
    return trace,source,audit,baseline,rows,binding


def recover_saved_response(store,trace_id,*,apply=False,expected_binding=None,backup_path=None):
    with CORPUS_LOCK,store.connection() as connection:
        trace,source,saved,baseline,rows,binding=recovery_inputs(store,trace_id,connection)
    # Idempotence is based on immutable source provenance, never on a matching hypothesis.
    with store.connection() as connection:
        experiments=[dict(r) for r in connection.execute('SELECT id,result_json FROM experiments')]
    for experiment in experiments:
        recovery=json.loads(experiment['result_json']).get('response_recovery',{})
        if recovery.get('source_trace_id')==trace_id:
            if recovery.get('source_trace_sha256')!=digest(trace):raise ValueError('已恢复Trace发生变化')
            return {'status':'already_recovered','experiment_id':experiment['id'],'provider_calls':0}
    if trace['status']!='failed' or source['status']!='failed':raise ValueError('仅允许恢复已失败的完整审计响应')
    if not isinstance(saved.get('provider_raw_text'),str) or not any(u.get('status')=='ok' for u in saved.get('token_usage',[])):
        raise ValueError('缺少已付费完整原始响应或成功Usage记录')
    if saved.get('baseline_id')!=baseline['id'] or saved.get('baseline_gate_results')!=baseline['result'].get('gates'):
        raise ValueError('来源Baseline或Gate绑定已变化')
    previous=json.loads(source['result_json'])
    if previous.get('report_confirmation') or previous.get('composite'):raise ValueError('已确认或组合的实验不能恢复')
    if store.candidates(source['id']):raise ValueError('来源已有持久化候选，不追加重复轮次')
    by_id={r['id']:r for r in rows}
    frozen=saved.get('all_bad_case_audit',[])
    if not frozen or set(r['id'] for r in frozen)!=set(by_id):raise ValueError('来源Bad Case范围已变化')
    for r in frozen:
        actual=json.loads(by_id[r['id']]['result_json'])
        actual.update(run_id=by_id[r['id']]['run_id'],question_id=by_id[r['id']]['question_id'])
        if actual!=r['result']:raise ValueError('来源题目、评分、回答或Trace已变化')
    bad_cases=[{**r,'result':json.loads(r['result_json'])} for r in rows]
    for r in bad_cases:
        r['result'].update(run_id=r['run_id'],question_id=r['question_id'])
        r['diagnostic_view']=diagnostic_view(r['result'])
    base={**DEFAULT_PIPELINE_CONFIG,**baseline['config']}
    for key in ('run_target','knowledge_identity'):base.pop(key,None)
    audit=dict(saved)
    for key in ('validation_error','provider_error'):audit.pop(key,None)
    used=store.experiment(source['id'])['evaluation_budget']['used']
    labels=['A','B','C'][:min(3,MAX_EVALS-1-used)]
    result,batch=prepare_response(saved['provider_raw_text'],base,bad_cases,[],used,1,labels,None,[],audit)
    if saved.get('parsed_json') is not None and saved['parsed_json']!=result:
        raise ValueError('保存的解析内容与原始响应不一致，禁止恢复')
    plan={'status':'validated' if batch else 'no_candidates','binding':binding,'source_trace_id':trace_id,
          'returned_candidates':len(result['candidates']),'legal_candidates':[c[0] for c in batch],
          'rejected_candidates':audit['rejected_candidates'],'provider_calls':0}
    if not apply or not batch:return plan
    if expected_binding!=binding:raise ValueError('恢复预检绑定不匹配，必须重新只读预检')
    backup=Path(backup_path) if backup_path else None
    if backup is None or backup.exists() or backup.resolve()==store.database_path.resolve():raise ValueError('恢复须指定新的SQLite备份路径')
    backup.parent.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(store.database_path.as_uri()+'?mode=ro',uri=True) as reader,sqlite3.connect(backup) as target:
        reader.backup(target)
    with CORPUS_LOCK,store.connection() as connection:
        connection.execute('BEGIN IMMEDIATE')
        *_,current_binding=recovery_inputs(store,trace_id,connection)
        if current_binding!=binding:raise ValueError('事务前来源或评测身份已变化，禁止恢复')
        if store.current_baseline_identity(connection)['current_experiment_id']!=source['id']:
            raise ValueError('已有更新Experiment，禁止恢复为当前实验')
        # An independent recovery experiment leaves the paid failure and its costs byte-for-byte intact.
        experiment_id='EXP-RECOVERY-'+_now().replace('-','').replace(':','').replace('.','').replace('+','')
        audit.update(optimization_run_id=experiment_id,response_recovery={'source_trace_id':trace_id,
            'source_experiment_id':source['id'],'source_trace_sha256':digest(trace),'binding':binding,
            'evaluation_identity':baseline['judge']['evaluation_identity'],'new_provider_calls':0,'recovered_at':_now(),
            'source_failure':saved.get('validation_error')},round=1,
            generation_status='partial' if audit['rejected_candidates'] else 'completed',
            evaluation_budget={'used':used,'max':MAX_EVALS,'reserved_for_d':1})
        connection.execute('INSERT INTO experiments VALUES (?,?,?,?,?)',(experiment_id,baseline['id'],'completed',_json({**result,**audit}),_now()))
        for label,config,reasoning in batch:
            connection.execute("INSERT INTO candidate_configs VALUES (?,?,'generated',?,?,'{}',?)",
                (experiment_id+'-'+label,experiment_id,_json(config),_json(reasoning),_now()))
        connection.execute("INSERT INTO agent_traces(experiment_id,status,result_json,created_at) VALUES (?,'completed',?,?)",
            (experiment_id,_json({**result,**audit}),_now()))
    return {**plan,'status':'recovered','experiment_id':experiment_id,'backup_path':str(backup)}
