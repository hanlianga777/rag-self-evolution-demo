#!/usr/bin/env python3
"""Read-only audit, then opt-in Judge-only replay of 50 unchanged saved answers.

No generation, formal Run creation, database writes, retries, or automatic resume.
Explicit continuation skips every attempted question and only accepts settled
HTTP200 Judge contract errors; unknown execution always stops.
A real approved target Snapshot with the current scoring manifest is mandatory
for --execute. Historical generation V1 is valid input, never new Max latency.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import time
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
SOURCE_RUN = 'EVAL-20261027122116244939'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def text_sha(value):
    return hashlib.sha256(value.encode()).hexdigest()


def category(question):
    return question.get('test_category', question.get('evaluation_group'))


def load_target(db, snapshot_id):
    from app.scoring_contract import validate_snapshot_manifest
    if snapshot_id is None:
        return None, ['explicit_target_snapshot_required']
    row = db.execute('SELECT id,status,snapshot_json FROM dataset_versions WHERE id=?', (snapshot_id,)).fetchone()
    if row is None:
        return None, ['target_snapshot_not_frozen_in_database']
    snapshot = {'id':row['id'], **json.loads(row['snapshot_json'])}
    blockers = [] if row['status']=='approved' else ['target_snapshot_not_approved']
    try:
        validate_snapshot_manifest(snapshot)
    except (ValueError, KeyError, TypeError):
        blockers.append('target_scoring_manifest_invalid')
    return snapshot, blockers


def audit_case(question, case, checkpoint, config, fingerprint, chunks):
    from app.diagnostics import _canonical_final
    from app.judge_replay import saved_selection_error
    by_id = {c['chunk_id']:c for c in chunks}
    metrics = case.get('programmatic_metrics') or {}
    trace = metrics.get('retrieval_trace') or {}
    usage = (metrics.get('token_usage') or {}).get('generation') or {}
    answer = case.get('model_answer')
    blockers, warnings = [], []
    if not isinstance(answer,str) or not answer.strip():
        blockers.append('saved_answer_missing')
    if any(case.get(k)!=question.get(k) for k in ('question','negative_subtype')) or case.get('test_category')!=category(question):
        blockers.append('source_question_identity_mismatch')
    if not isinstance(trace,dict) or trace.get('status')!='completed' or trace.get('artifact_schema_version')!=3:
        blockers.append('complete_trace_schema_missing')
        trace = trace if isinstance(trace,dict) else {}
    if trace.get('question')!=question['question'] or trace.get('config')!=config or trace.get('corpus_fingerprint')!=fingerprint:
        blockers.append('trace_question_config_or_corpus_mismatch')
    stages = {}
    for stage in ('candidates','reranked','final'):
        entries = trace.get(stage)
        valid = isinstance(entries,list) and bool(entries) and all(isinstance(e,dict) and isinstance(e.get('content'),str) and e['content'].strip() for e in entries)
        if valid:
            try:
                valid = _canonical_final({'final':entries,'parent_expand':trace.get('parent_expand') if stage=='final' else False}, by_id)
            except (ValueError, KeyError, TypeError):
                valid = False
        if not valid:
            blockers.append(stage+'_canonical_mismatch')
        stages[stage] = {'count':len(entries) if isinstance(entries,list) else None,'sha256':digest(entries), 'canonical_match':valid}
    stage_entries = {name:trace[name] if isinstance(trace.get(name),list) else [] for name in ('candidates','reranked','final')}
    candidates = {e['chunk_id']:e for e in stage_entries['candidates'] if isinstance(e,dict) and e.get('chunk_id')}
    if any(e.get('chunk_id') not in candidates or e.get('content')!=candidates[e['chunk_id']].get('content') for e in stage_entries['reranked']):
        blockers.append('rerank_ancestry_mismatch')
    for entry in stage_entries['final']:
        members = entry.get('matched_child_ids') or [entry.get('chunk_id')]
        if any(key not in by_id or key not in candidates or by_id[key].get('parent_chunk_id')!=entry.get('parent_chunk_id') for key in members):
            blockers.append('final_child_parent_ancestry_mismatch')
    if all(s['canonical_match'] for s in stages.values()):
        selection_error = saved_selection_error(trace,chunks)
        if selection_error:
            blockers.append(selection_error)
    valid_usage = (usage.get('status')=='ok' and usage.get('provider')=='DeepSeek'
        and isinstance(usage.get('requested_model'),str) and bool(usage['requested_model'])
        and isinstance(usage.get('request_sha256'),str) and len(usage['request_sha256'])==64
        and all(type(usage.get(k)) is int and usage[k]>=0 for k in ('prompt_tokens','completion_tokens')))
    if not valid_usage:
        blockers.append('generation_usage_unknown_or_incomplete')
    if not usage.get('request_id'):
        warnings.append('historical_request_id_not_saved')
    if not usage.get('response_model'):
        warnings.append('historical_served_model_revision_not_saved')
    requests = [p for p in checkpoint.get('provider_requests',{}).values() if p.get('phase')=='generation' and p.get('provider')=='DeepSeek']
    matches = [p for p in requests if p.get('status')=='completed' and p.get('result',{}).get('content')==answer
               and p.get('result',{}).get('usage',{}).get('request_sha256')==usage.get('request_sha256')]
    if not matches:
        blockers.append('generation_checkpoint_content_or_usage_mismatch')
    if checkpoint.get('inflight')=='generation' or checkpoint.get('unknown_execution',{}).get('generation'):
        blockers.append('generation_execution_unknown')
    return {'question_id':question['id'],'coverage_slot':question.get('coverage_slot'),
        'source_replayable':not blockers,'blockers':sorted(set(blockers)),'warnings':warnings,
        'answer_sha256':text_sha(answer) if isinstance(answer,str) else None,'answer_characters':len(answer) if isinstance(answer,str) else None,
        'trace_sha256':digest(trace),'stages':stages,'generation_usage':usage,
        'generation_checkpoint_matches':len(matches),'source_case_sha256':digest(case),
        'final_sources':[{'chunk_id':e.get('chunk_id'),'parent_chunk_id':e.get('parent_chunk_id'),
            'matched_child_ids':e.get('matched_child_ids'),'body_sha256':text_sha(e['content']),
            'document_id':e.get('document_id'),'product':e.get('product'),'version':e.get('version')}
            for e in stage_entries['final'] if isinstance(e,dict) and isinstance(e.get('content'),str)]}


def load_corpus(index, documents_dir):
    manifest_raw = (index/'manifest.json').read_bytes()
    manifest = json.loads(manifest_raw)
    files, raw_files = {}, {}
    blockers = []
    for name in ('chunks.json','parents.json','documents.json','faiss.index','embeddings.npy','source-manifest.json'):
        path = index/name
        raw_files[name] = path.read_bytes() if path.is_file() else None
        actual = hashlib.sha256(raw_files[name]).hexdigest() if raw_files[name] is not None else None
        expected = manifest.get('artifacts',{}).get(name)
        files[name] = {'sha256':actual,'manifest_sha256':expected,'match':actual is not None and actual==expected}
        if not files[name]['match']:
            blockers.append('corpus_artifact_hash_mismatch:'+name)
    parents = {p['chunk_id']:p for p in json.loads(raw_files['parents.json'])}
    chunks = [{**c,'canonical_parent':parents.get(c.get('parent_chunk_id'))} for c in json.loads(raw_files['chunks.json'])]
    source_hashes = []
    for doc in json.loads(raw_files['documents.json']):
        path = documents_dir/doc['name']
        sha = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        expected = manifest['sources'].get(doc['id'])
        source_hashes.append({'document_id':doc['id'],'path':str(path),'sha256':sha,'expected_sha256':expected,'match':sha is not None and sha==expected})
        if sha is None or sha!=expected:
            blockers.append('source_pdf_hash_mismatch:'+doc['id'])
    legacy = json.loads(raw_files['source-manifest.json'])
    return manifest,chunks,{'manifest_sha256':hashlib.sha256(manifest_raw).hexdigest(),
        'artifact_hashes':files,'pdf_source_hashes':source_hashes,
        'source_manifest_identity':legacy.get('knowledge_identity'),
        'source_manifest_lineage_matches_current':legacy.get('knowledge_identity')==manifest.get('knowledge_identity')}, blockers


def prepare_plans(snapshot, source_snapshot, rows, chunks, provider):
    from app.canonical_evidence import full_norms
    from app.context_budget import render_generation_context
    from app.evaluation_contract import BUSINESS_JUDGE_PROMPT,business_judge_input,observe_evidence
    from app.paid_run import provider_task,execution_limits,REQUEST_LIMITS
    from app.scoring_contract import compile_contract
    blockers, plans = [], []
    source_questions = {q['id']:q for q in source_snapshot['questions']}
    if snapshot['question_ids']!=source_snapshot['question_ids'] or len(snapshot['questions'])!=50:
        blockers.append('target_question_ids_or_order_changed')
    if snapshot['corpus_fingerprint']!=source_snapshot['corpus_fingerprint']:
        blockers.append('target_corpus_or_index_changed')
    for raw in snapshot['questions']:
        old = source_questions.get(raw['id'])
        if old is None or raw.get('question')!=old.get('question') or category(raw)!=category(old) or raw.get('negative_subtype')!=old.get('negative_subtype'):
            blockers.append('target_question_text_category_or_subtype_changed:'+raw['id'])
            continue
        case = rows[raw['id']]
        trace = case['programmatic_metrics']['retrieval_trace']
        item = {'id':raw['id'],'question':raw['question'],'test_category':category(raw),'negative_subtype':raw.get('negative_subtype'),'raw':raw}
        contract = compile_contract(item)
        norms = full_norms(raw,chunks)
        final = trace['final']
        scope_ids = {(e.get('source_scope') or {}).get('source_id') for e in final}
        context = {'scoring_contract':contract,'contract_version':'business-vnext-1','retrieval_candidates':trace['candidates'],
            'sources_legend':json.loads(render_generation_context(final).split('\n',1)[0])['sources'],
            'golden_evidence':raw.get('evidence',raw.get('acceptable_evidence',[])),'golden_norms':norms,
            '_canonical_chunks':chunks,'scope_sources':[{**c,'content':c.get('chunk_text',c.get('text',''))} for c in chunks if c['chunk_id'] in scope_ids],
            'final_context':final,'category':category(raw),'negative_subtype':raw.get('negative_subtype'),
            'expected_behavior':raw.get('expected_behavior'),'source_constraints':observe_evidence(item,final)['source_constraints']}
        expected = raw.get('reference_answer') or raw.get('expected_behavior')
        if not expected:
            blockers.append('target_reference_or_behavior_missing:'+raw['id'])
            continue
        with provider_task('judge'),execution_limits({'judge':REQUEST_LIMITS['judge']}):
            summary = provider.request_summary(BUSINESS_JUDGE_PROMPT,business_judge_input(raw['question'],expected,case['model_answer'],context),True,temperature=0)
        plans.append({'question_id':raw['id'],'question':raw['question'],'expected':expected,'answer':case['model_answer'],
            'context':context,'request':summary,'compiled_contract_hash':contract['compiled_contract_hash']})
    return plans,blockers


def settled_call(call, request):
    usage = call.get('usage') or {}
    return (call.get('status') == 'ok' and call.get('provider') == 'DeepSeek'
        and call.get('model') == request.get('model') and call.get('task') == 'judge'
        and call.get('max_tokens') == request.get('max_tokens')
        and usage.get('status') == 'ok' and usage.get('provider') == 'DeepSeek'
        and usage.get('requested_model') == request.get('model')
        and usage.get('request_sha256') == request.get('request_sha256')
        and usage.get('request_execution_unknown') is not True
        and all(type(usage.get(k)) is int and usage[k] >= 0 for k in ('prompt_tokens','completion_tokens')))


def known_invalid_response(error, call, request):
    metadata = error.get('response_metadata') or {}
    usage = metadata.get('usage') or {}
    return (error.get('error_type') == 'ProviderInvalidResponse' and error.get('http_status') == 200
        and error.get('request_execution_unknown') is not True
        and metadata.get('http_response_received') is True and metadata.get('http_status') == 200
        and metadata.get('request_execution_unknown') is not True
        and (metadata.get('validation_error') or {}).get('category') == 'business_contract'
        and settled_call(call,request)
        and all(usage.get(k) == call['usage'].get(k) for k in ('status','provider','requested_model','request_sha256','prompt_tokens','completion_tokens')))


def continuation_plan(directory, plans, binding, continue_known_invalid):
    directory = directory.resolve()
    files = {name:directory/name for name in ('audit.json','replay.json','ledger.json')}
    audit, replay, ledger = [json.loads(files[name].read_text()) for name in files]
    if any(value != binding for value in (audit.get('binding'),replay.get('binding'),ledger.get('identity'))):
        raise ValueError('Continuation parent binding differs from current complete preflight')
    requests = [{'question_id':p['question_id'],'request':p['request'],'compiled_contract_hash':p['compiled_contract_hash']} for p in plans]
    if audit.get('requests') != requests or len(plans) != 50:
        raise ValueError('Continuation requires the unchanged complete 50-question request plan')
    attempted = replay.get('cases') or []; calls = ledger.get('calls') or []
    count = len(attempted)
    if (not 1 <= count < 50 or len(calls) != count or replay.get('network_calls') != count
        or replay.get('generation_calls') != 0 or replay.get('status') not in {'stopped_technical_error_no_retry','completed','processed_all_with_technical_errors'}
        or [r.get('question_id') for r in attempted] != [p['question_id'] for p in plans[:count]]
        or len({r.get('question_id') for r in attempted}) != count):
        raise ValueError('Continuation parent must contain one unique contiguous attempted prefix')
    for index,(row,call,plan) in enumerate(zip(attempted,calls,plans)):
        if (row.get('answer_sha256') != text_sha(plan['answer'])
            or row.get('final_sha256') != digest(plan['context']['final_context'])):
            raise ValueError('Continuation source answer/Final changed')
        payload = call.get('request_payload')
        if (not settled_call(call,plan['request']) or not isinstance(payload,dict)
            or hashlib.sha256(json.dumps(payload).encode()).hexdigest() != plan['request']['request_sha256']
            or hashlib.sha256(json.dumps(payload,ensure_ascii=False).encode()).hexdigest() != call.get('request_sha256')):
            raise ValueError('Continuation parent request or Usage is unknown, changed or unsettled')
        if row.get('status') == 'completed':
            judgment = row.get('judgment') or {}
            if row.get('business_result') not in {'PASS','FAIL'} or judgment.get('verdict') != row['business_result']:
                raise ValueError('Continuation completed parent judgment is inconsistent')
            original = judgment.get('raw_provider_response')
        elif row.get('status') == 'NOT_EVALUABLE' and row.get('business_result') is None:
            if not continue_known_invalid or not known_invalid_response(row.get('error') or {},call,plan['request']):
                raise ValueError('Continuation requires explicit known-invalid mode; unknown/transport failures cannot continue')
            original = row['error'].get('raw_response')
        else:
            raise ValueError('Continuation parent has an in-flight or unsupported result')
        raw = Path(call.get('raw_response_path') or '')
        raw = raw.resolve() if raw.is_absolute() else (ROOT/raw).resolve()
        if not raw.is_relative_to(directory) or not raw.is_file():
            raise ValueError('Continuation raw response must exist inside the parent directory')
        body = json.loads(raw.read_text()); usage = body.get('usage') or {}
        if (not isinstance(original,str) or (body.get('choices') or [{}])[0].get('message',{}).get('content') != original
            or any(usage.get(k) != call['usage'][k] for k in ('prompt_tokens','completion_tokens'))):
            raise ValueError('Continuation raw response differs from saved outcome or Usage')
        files['response_'+str(index+1)] = raw
    hashes = {str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in files.values()}
    evidence = {'parent_directory':str(directory),'attempted_count':count,'skipped_question_ids':[r['question_id'] for r in attempted],
        'file_sha256':hashes,'common_binding':binding,'continue_known_invalid':continue_known_invalid}
    evidence['continuation_binding'] = digest(evidence)
    return plans[count:],{**evidence,'cases':attempted}


def execute_plans(plans, provider, output, binding, timing_provenance, *, continue_known_invalid=False, parent=None):
    from app.paid_run import PaidRun,accounting_only,controlled_run,provider_task,REQUEST_LIMITS
    from app.providers import provider_error_details
    parent_cases = parent['cases'] if parent else []
    if not 1 <= len(plans) or len(plans)+len(parent_cases) > 50:
        raise ValueError('Replay requires 1 to 50 bounded plans including previous attempts')
    keys = [p['question_id'] for p in plans] + [r['question_id'] for r in parent_cases]
    if len(set(keys)) != len(keys):
        raise ValueError('Replay cannot repeat any attempted question')
    if parent:
        for path,sha in parent['file_sha256'].items():
            if hashlib.sha256(Path(path).read_bytes()).hexdigest() != sha:
                raise ValueError('Continuation parent files changed after preflight')
    ledger = PaidRun(output/'ledger.json',identity=binding,identity_check=lambda:binding,output_limits={'judge':REQUEST_LIMITS['judge']})
    result = {'artifact_type':'judge_only_replay_not_formal_baseline','binding':binding,'status':'running',
              'cases':json.loads(json.dumps(parent_cases)), 'generation_calls':0,'network_calls':len(parent_cases),
              'new_network_calls':0,'parent_network_calls':len(parent_cases),'timing_provenance':timing_provenance,'actual_cost':None,
              'continue_known_invalid':continue_known_invalid,'continuation_parent':{k:v for k,v in parent.items() if k!='cases'} if parent else None}
    def save():
        (output/'replay.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    save()
    with accounting_only(),controlled_run(ledger),provider_task('judge'):
        for plan in plans:
            row={'question_id':plan['question_id'],'status':'inflight','business_result':None,
                 'answer_sha256':text_sha(plan['answer']),'final_sha256':digest(plan['context']['final_context'])}
            result['cases'].append(row);save()
            started=time.perf_counter(); before=len(ledger.calls); accepted_invalid=False
            try:
                judged=provider.judge(plan['question'],plan['expected'],plan['answer'],context=plan['context'])
                row.update(status='completed',business_result=judged['verdict'],judgment=judged)
            except Exception as error:
                details=provider_error_details(error,'judge_only_replay')
                row.update(status='NOT_EVALUABLE',error=details)
                accepted_invalid=(continue_known_invalid and ledger.stopped is None and len(ledger.calls)==before+1
                    and known_invalid_response(details,ledger.calls[-1],plan['request']))
                row['continued_after_known_invalid']=accepted_invalid
                if not accepted_invalid:
                    result['status']='stopped_technical_error_no_retry';ledger.stop(type(error).__name__)
            row['judge_ms']=round((time.perf_counter()-started)*1000)
            result['new_network_calls']=len(ledger.calls)
            result['network_calls']=len(parent_cases)+len(ledger.calls);save()
            if row['status']!='completed' and not accepted_invalid:
                break
    if result['status']=='running':
        result['status']='processed_all_with_technical_errors' if any(r['status']!='completed' for r in result['cases']) else 'completed'
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database',type=Path,default=ROOT/'backend/data/demo.db')
    parser.add_argument('--index-dir',type=Path,default=ROOT/'backend/data/index')
    parser.add_argument('--documents-dir',type=Path,default=ROOT/'backend/documents')
    parser.add_argument('--source-run',default=SOURCE_RUN,choices=[SOURCE_RUN])
    parser.add_argument('--target-snapshot',help='actual approved dataset_versions id; never an in-memory or fabricated manifest')
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--expected-binding',help='exact binding printed by a prior target-bound dry-run')
    parser.add_argument('--output',type=Path)
    parser.add_argument('--skip-attempted-from',type=Path,help='explicit parent audit/Replay/ledger directory; skip every attempted prefix case')
    parser.add_argument('--continue-known-invalid',action='store_true',help='continue to unused questions only after settled HTTP200 Judge contract errors; never retry')
    parser.add_argument('--expected-continuation-binding',help='exact continuation_binding from the current parent-bound dry-run')
    args = parser.parse_args()
    credential_file = Path(os.environ.get('RAG_DEMO_ENV_PATH') or ROOT/'.env')
    with tempfile.TemporaryDirectory(prefix='judge-only-replay-isolated-') as isolated:
        for key,suffix in {'RAG_DEMO_DB_PATH':'unused.sqlite','RAG_DEMO_ENV_PATH':'empty.env','RAG_DEMO_INDEX_DIR':'index',
                           'RAG_DEMO_DOCUMENTS_DIR':'documents','RAG_DEMO_UPLOADS_DIR':'uploads'}.items():
            os.environ[key]=str(Path(isolated)/suffix)
        sys.path.insert(0,str(ROOT/'backend'))
        from app.config import Settings,load_settings
        from app.evaluation_contract import BUSINESS_JUDGE_PROMPT,VERSIONS
        from app.providers import DeepSeekProvider
        manifest,chunks,corpus_audit,blockers = load_corpus(args.index_dir,args.documents_dir)
        db = sqlite3.connect(args.database.resolve().as_uri()+'?mode=ro',uri=True)
        db.row_factory=sqlite3.Row
        db.execute('PRAGMA query_only=ON')
        db.execute('BEGIN')
        raw_run = db.execute('SELECT * FROM evaluation_runs WHERE id=?',(args.source_run,)).fetchone()
        if raw_run is None:
            raise SystemExit('Source real run not found')
        run = dict(raw_run)
        source_snapshot = json.loads(run['dataset_snapshot_json'])
        config = json.loads(run['config_json'])
        old_judge = json.loads(run['judge_json'])
        old_result = json.loads(run['result_json'])
        saved = list(db.execute('SELECT question_id,result_json FROM evaluation_case_results WHERE run_id=? ORDER BY id',(args.source_run,)))
        rows = {r['question_id']:json.loads(r['result_json']) for r in saved}
        target,target_blockers = load_target(db,args.target_snapshot)
        db.close()
        if run['run_mode']!='real' or run['data_source']!='real' or run['status'] not in {'partial','failed','completed'}:
            blockers.append('source_not_inactive_real_execution')
        if len(saved)!=50 or len(rows)!=50 or set(rows)!=set(source_snapshot['question_ids']):
            blockers.append('source_requires_exact_50_unique_saved_cases')
        fingerprint = manifest['knowledge_identity']
        if fingerprint!=source_snapshot['corpus_fingerprint'] or config.get('knowledge_identity')!=fingerprint:
            blockers.append('source_corpus_or_index_not_current_canonical')
        audits=[]
        for question in source_snapshot['questions']:
            if question['id'] not in rows:
                audits.append({'question_id':question['id'],'source_replayable':False,'blockers':['saved_case_missing']})
            else:
                audits.append(audit_case(question,rows[question['id']],old_result.get('checkpoints',{}).get(question['id'],{}),config,fingerprint,chunks))
        settings = load_settings(env_file=credential_file)
        address = urlsplit(settings.base_url)
        if (address.scheme!='https' or address.netloc!='api.deepseek.com' or address.path not in ('','/v1') or address.query or address.fragment or settings.model!='deepseek-flash'):
            blockers.append('configured_official_flash_route_required')
        provider = DeepSeekProvider(settings if settings.configured else Settings('dry-run',settings.base_url,settings.model,settings.timeout_seconds))
        plans=[]
        if target is not None and not target_blockers and all(r['source_replayable'] for r in audits) and not blockers:
            try:
                plans,plan_blockers=prepare_plans(target,source_snapshot,rows,chunks,provider)
                target_blockers.extend(plan_blockers)
            except (ValueError,KeyError,TypeError) as error:
                target_blockers.append('target_contract_or_normative_source_invalid:'+str(error))
        blockers.extend(target_blockers)
        if any(not r['source_replayable'] for r in audits):
            blockers.append('source_case_audit_incomplete')
        source_hash = digest({'run':run,'cases':[(r['question_id'],r['result_json']) for r in saved]})
        binding = digest({'source':source_hash,'target':target,'corpus':corpus_audit,'judge_versions':VERSIONS,
            'judge_prompt_sha256':text_sha(BUSINESS_JUDGE_PROMPT),'requests':[p['request'] for p in plans]})
        report = {'artifact_type':'judge_only_replay_readonly_audit','source_run_id':args.source_run,
            'target_snapshot_id':args.target_snapshot,'target_is_approved_frozen_snapshot':target is not None and not target_blockers,
            'source_snapshot_id':source_snapshot['id'],'source_sha256':source_hash,'binding':binding,
            'source_run_status':run['status'],'source_run_mode':run['run_mode'],'source_data_source':run['data_source'],
            'source_generation_contract':old_judge.get('generation_prompt_version'),
            'source_generation_model':old_judge.get('execution_snapshot',{}).get('generation_model'),
            'source_generation_thinking':'historically_not_frozen_no_max_inference',
            'timing_provenance':'historical_generation_only_not_new_v2_or_max_performance',
            'formal_baseline_created':False,'production_database_writes':0,'generation_calls':0,'network_calls':0,
            'source_replayable_count':sum(r['source_replayable'] for r in audits),'can_execute':not blockers and len(plans)==50,
            'blockers':sorted(set(blockers)),'corpus_identity':fingerprint,'corpus_audit':corpus_audit,
            'cases':audits,'judge_versions':VERSIONS,'judge_prompt_sha256':text_sha(BUSINESS_JUDGE_PROMPT),
            'target_scoring_manifest':target.get('scoring_contract_manifest') if target else None,
            'requests':[{'question_id':p['question_id'],'request':p['request'],'compiled_contract_hash':p['compiled_contract_hash']} for p in plans],
            'legacy_scores_used_as_truth':False,'max_calls':50,'max_attempts_per_question':1,'retry_policy':'none',
            'actual_cost':None,'cost_status':'not_reported_by_provider','app_main_imported':'app.main' in sys.modules}
        execution_plans, parent = plans, None
        if args.skip_attempted_from and report['can_execute']:
            try:
                execution_plans,parent=continuation_plan(args.skip_attempted_from,plans,binding,args.continue_known_invalid)
                report['continuation_parent']={k:v for k,v in parent.items() if k!='cases'}
                report['remaining_question_ids']=[p['question_id'] for p in execution_plans]
            except (ValueError,KeyError,TypeError,OSError) as error:
                report['blockers'].append('continuation_parent_invalid:'+str(error));report['can_execute']=False
        report['continue_known_invalid']=args.continue_known_invalid
        output = args.output or ROOT/'docs/judge_vnext_20261029'/('judge_only_source_audit_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
        output.mkdir(parents=True,exist_ok=False)
        (output/'audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        # Export original saved text as-is for local inspection. Never send this
        # complete bundle to a Provider; each Judge receives only its own case.
        (output/'saved_execution_bundle.json').write_text(json.dumps({'source_run_id':args.source_run,'source_sha256':source_hash,
            'cases':[{'question_id':q,'answer':rows[q]['model_answer'],'retrieval_trace':rows[q]['programmatic_metrics'].get('retrieval_trace'),
                      'generation_usage':rows[q]['programmatic_metrics'].get('token_usage',{}).get('generation')} for q in source_snapshot['question_ids'] if q in rows]},ensure_ascii=False,indent=2)+'\n')
        print(json.dumps({'output':str(output),'network_calls':0,'source_replayable':report['source_replayable_count'],
            'can_execute':report['can_execute'],'binding':binding,'blockers':report['blockers'],
            'remaining_questions':len(execution_plans),'continuation_binding':parent['continuation_binding'] if parent else None},ensure_ascii=False),flush=True)
        if not args.execute:
            return 0
        if not report['can_execute'] or args.expected_binding!=binding or not settings.configured:
            raise SystemExit('Blocked: complete target-bound audit, exact --expected-binding, and configured credentials required')
        if parent and args.expected_continuation_binding!=parent['continuation_binding']:
            raise SystemExit('Blocked: exact parent-bound --expected-continuation-binding required')
        result=execute_plans(execution_plans,provider,output,binding,report['timing_provenance'],continue_known_invalid=args.continue_known_invalid,parent=parent)
        def save():
            (output/'replay.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        result['formal_baseline_created']=False
        result['production_database_writes']=0
        result['app_main_imported']='app.main' in sys.modules
        result['isolated_storage_files']=sorted(str(p.relative_to(isolated)) for p in Path(isolated).rglob('*') if p.is_file())
        save()
        return 0 if result['status'] in {'completed','processed_all_with_technical_errors'} else 1


if __name__=='__main__':
    raise SystemExit(main())
