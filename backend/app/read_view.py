"""Memoize pure presentation work only during one synchronous read response."""
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from functools import wraps
import json

_view = ContextVar('read_view', default=None)


@contextmanager
def read_view():
    token = _view.set({})
    try:yield
    finally:_view.reset(token)


def memoized_view(function):
    @wraps(function)
    def read(*args,**kwargs):
        cache = _view.get()
        if cache is None:return function(*args,**kwargs)
        key=(function.__module__,function.__qualname__,json.dumps([args,kwargs],sort_keys=True,ensure_ascii=False))
        if key not in cache:cache[key]=function(*args,**kwargs)
        return deepcopy(cache[key])
    return read


def generation_progress(store, run_id, *, include_plan=False):
    """Read progress fields in SQL; slot audits and Provider payloads stay in SQLite."""
    from datetime import datetime, timezone
    audit_keys = ('corpus_fingerprint','slot_persistence_v1','progress','quality_rerun','failed_stage','regeneration_count','error','price_pause')
    projection = ','.join("json_extract(a.hard_validation_json,'$."+key+"') AS "+key for key in audit_keys if key!='quality_rerun')
    quality_keys=('status','stage','slot','completed','total','probe_passed','probe_failed','qc_passed','qc_failed','qc_skipped','started_at','error')
    quality_fields=','.join("'"+key+"',json_extract(a.hard_validation_json,'$.quality_rerun."+key+"')" for key in quality_keys)
    projection+=",CASE WHEN json_type(a.hard_validation_json,'$.quality_rerun')='object' THEN json_set(json_object("+quality_fields+"),'$.slots',json((SELECT json_group_object(key,json_object('probe',json_extract(value,'$.probe'),'qc',json_extract(value,'$.qc'))) FROM json_each(a.hard_validation_json,'$.quality_rerun.slots')))) END quality_rerun"
    projection += ",CASE WHEN r.status='needs_regeneration' THEN (SELECT count(*) FROM json_each(a.hard_validation_json,'$.slot_audit')) ELSE 0 END audited_slots"
    if include_plan:
        projection += ",json_extract(a.hard_validation_json,'$.frozen_plan') AS frozen_plan"
    with store.connection() as c:
        row = c.execute('SELECT r.*, '+projection+' FROM golden_generation_runs r LEFT JOIN golden_generation_artifacts a ON a.generation_run_id=r.id WHERE r.id=?',(run_id,)).fetchone()
        if not row:return None
        ids=json.loads(row['question_ids_json'] or '[]')
        quality=c.execute("SELECT probe_status,qc_status,stage,EXISTS(SELECT 1 FROM probe_results p WHERE p.question_id=q.id) has_probe,EXISTS(SELECT 1 FROM qc_results p WHERE p.question_id=q.id) has_qc FROM questions q WHERE id IN ("+','.join('?' for _ in ids)+')',ids).fetchall() if ids else []
    audit={key:json.loads(row[key]) if key in {'corpus_fingerprint','progress','quality_rerun','price_pause'} and row[key] else row[key] for key in audit_keys if row[key] is not None}
    if include_plan and row['frozen_plan']:
        plan=json.loads(row['frozen_plan'])
        audit['frozen_plan']={**plan,'clusters':[{k:v for k,v in cluster.items() if k not in {'centroid','center','embedding'}} for cluster in plan.get('clusters',[])]}
    profile=json.loads(row['profile_json'] or '{}')
    run={'id':row['id'],'status':row['status'],'created_at':row['created_at'],'profile':profile,'question_ids':ids,'artifacts':{'hard_validation':audit}}
    expected=store._expected_count(run)
    run['human_gate']={'gate':1,'status':'pending','qualification_evaluated':False,'expected':expected,'generated':len(quality),'probe_passed':sum(q['probe_status']=='probe_passed' and q['has_probe'] for q in quality),'qc_completed':sum(q['qc_status'] in {'qc_passed','qc_failed'} and q['has_qc'] for q in quality),'qc_passed':sum(q['qc_status']=='qc_passed' and q['has_qc'] for q in quality),'approved':sum(q['stage']=='golden' for q in quality)}
    if not audit.get('slot_persistence_v1'):return run
    progress=audit.get('progress',{})
    valid=len(ids);probe=progress.get('probe_completed',0);qc=progress.get('qc_completed',0)+progress.get('qc_skipped',0)
    phase=audit.get('failed_stage') if row['status']=='failed' and audit.get('failed_stage') in {'generating','validation','probing','qc'} else progress.get('stage',row['status'])
    processed=len(progress['processed_slot_ids']) if 'processed_slot_ids' in progress else row['audited_slots'] if row['status']=='needs_regeneration' else valid
    done,total=(probe,expected) if phase=='probing' else (qc,expected) if phase in {'qc','completed'} else (progress.get('phase_processed',processed),progress.get('phase_total',expected))
    started=progress.get('started_at',row['created_at'])
    ended=datetime.fromisoformat(progress['finished_at']) if progress.get('finished_at') else datetime.now(timezone.utc)
    run['operation_progress']={'operation_id':progress.get('operation_id',run_id),'status':row['status'],'phase':phase,'phase_label':{'queued':'等待开始','coverage':'覆盖规划','generating':'补齐失败题' if audit.get('regeneration_count') else '逐题生成与校验','validation':'逐题生成与校验','needs_regeneration':'待补齐失败题','probing':'Probe','qc':'QC','completed':'已完成','failed':'运行失败'}.get(phase,phase),'completed_units':done,'total_units':total,'phase_processed':done,'phase_total':total,'phase_percent':round(done/total*100) if total else 0,'overall_percent':round((processed+probe+qc)/(expected*3)*100) if expected else 0,'processed_slots':processed,'expected_slots':expected,'hard_valid_completed':valid,'hard_valid_total':expected,'failed_count':max(0,expected-valid) if row['status']=='needs_regeneration' else max(0,processed-valid),'probe_processed':probe,'qc_processed':qc,'current_slot':progress.get('slot'),'current_item':progress.get('slot'),'attempt':progress.get('attempt'),'started_at':started,'elapsed_ms':max(0,round((ended-datetime.fromisoformat(started)).total_seconds()*1000)),'message':progress.get('message'),'error':audit.get('error'),**{key:progress.get(key) for key in ('refill_round','refill_max_rounds','refill_remaining')}}
    return run


def revision_progress(store, revision_id=None, *, generation_run_id=None, active_only=False):
    keys=('stage','progress','question_ids','error','error_detail','failed_stage','interrupted_stage','apply_blocked','quality_results','price_pause')
    projection=','.join("json_extract(audit_json,'$."+key+"') AS "+key for key in keys)
    projection+=",json_array(json_object('stage',json_extract(audit_json,'$.runtime_attempts[#-1].stage'),'provider',json_extract(audit_json,'$.runtime_attempts[#-1].provider'),'model',json_extract(audit_json,'$.runtime_attempts[#-1].model'),'attempt',json_extract(audit_json,'$.runtime_attempts[#-1].attempt'))) AS runtime_attempts"
    where=[];args=[]
    for key,value in (('id',revision_id),('generation_run_id',generation_run_id)):
        if value is not None:where.append(key+'=?');args.append(value)
    status="coalesce(json_extract(audit_json,'$.status'),status)"
    if active_only:where.append(status+" IN ('queued','generating','validating','probing','qc')")
    with store.connection() as c:
        rows=c.execute('SELECT id,generation_run_id,'+status+' AS status,created_at,updated_at,'+projection+' FROM candidate_revision_runs'+(' WHERE '+' AND '.join(where) if where else '')+' ORDER BY created_at DESC',args).fetchall()
    result=[{key:json.loads(row[key]) if key in {'progress','question_ids','quality_results','runtime_attempts','price_pause'} and row[key] else row[key] for key in row.keys()} for row in rows]
    if revision_id:
        if not result:raise KeyError(revision_id)
        return result[0]
    return result


def semantic_coverage(plan, chunks):
    """Rename document-name fallback labels only in the displayed copy."""
    from .golden_v2 import topic_label
    if not plan:return plan
    by_id={chunk['chunk_id']:chunk for chunk in chunks}
    clusters=[]
    for cluster in plan.get('clusters',[]):
        label=cluster.get('semantic_label') or cluster.get('label') or ''
        sources=[by_id[key] for key in cluster.get('chunk_ids',[]) if key in by_id]
        if sources and label.lower().endswith('.pdf'):
            cluster={**cluster,'semantic_label':topic_label(sources)}
        clusters.append(cluster)
    return {**plan,'clusters':clusters}
