#!/usr/bin/env python3
"""Explicitly exclude one interrupted tail and call only previously unattempted Judges.

The original reserved ledger and unknown Usage/cost remain immutable. Default dry-run;
no retry, automatic resume, release, generation, formal Run or database writes.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
CORE=ROOT/'scripts/replay_saved_answers_judge_only_20261030.py'
spec=importlib.util.spec_from_file_location('frozen_replay_controller',CORE)
core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)


def file_sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare_interrupted_parent(directory,plans,binding,receipt_path,*,exclude_interrupted_tail=False,continue_known_invalid=False):
    if not exclude_interrupted_tail:raise ValueError('Explicit --exclude-interrupted-tail required; default unknown guard unchanged')
    directory=directory.resolve();files={};visiting=set()
    def read(path):
        raw=path.read_bytes();files[str(path.resolve())]=hashlib.sha256(raw).hexdigest();return json.loads(raw)
    receipt=read(receipt_path);snapshot_path=Path(receipt['process_snapshot_file']);snapshot=read(snapshot_path)
    if (receipt.get('owner_absent') is not True or receipt.get('matching_replay_processes')!=[]
        or snapshot.get('matching_replay_processes')!=[] or receipt.get('common_binding')!=binding
        or Path(receipt['parent_directory']).resolve()!=directory or files[str(snapshot_path.resolve())]!=receipt.get('process_snapshot_sha256')
        or core.digest(receipt.get('ps_command'))!=receipt.get('ps_command_sha256')
        or snapshot.get('observed_at')!=receipt.get('observed_at')
        or snapshot.get('complete_process_inventory_sha256')!=receipt.get('process_inventory_sha256')
        or receipt.get('retry_permitted') is not False or receipt.get('budget_attempt_consumed') is not True
        or receipt.get('response_available') is not False or receipt.get('token_usage') is not None
        or receipt.get('request_execution_status')!='Unknown' or receipt.get('cost_status')!='Unknown'):
        raise ValueError('Bound read-only absent-owner/unknown-execution observation required')
    required={str(directory/name) for name in ('audit.json','replay.json','ledger.json')}|{str(CORE)}
    if not required<={str(Path(path).resolve()) for path in receipt['source_file_sha256']}:raise ValueError('Interruption receipt lacks exact parent/controller source hashes')
    for path,sha in receipt['source_file_sha256'].items():
        if file_sha(Path(path))!=sha:raise ValueError('Interruption receipt source files changed')
        files[str(Path(path).resolve())]=sha
    requests=[{'question_id':p['question_id'],'request':p['request'],'compiled_contract_hash':p['compiled_contract_hash']} for p in plans]
    if len(plans)!=50 or len({p['question_id'] for p in plans})!=50:raise ValueError('Exact unique complete 50-plan source required')
    def chain(parent,top=False):
        parent=parent.resolve()
        if parent in visiting:raise ValueError('Continuation parent chain cycle')
        visiting.add(parent)
        audit=read(parent/'audit.json');replay=read(parent/'replay.json');ledger=read(parent/'ledger.json')
        if (audit.get('binding')!=binding or replay.get('binding')!=binding or ledger.get('identity')!=binding or audit.get('requests')!=requests):
            raise ValueError('Recursive parent binding/request plan changed')
        rows=replay.get('cases') or [];calls=ledger.get('calls') or [];prefix=[]
        link=replay.get('continuation_parent')
        if link:
            for path,sha in link['file_sha256'].items():
                if file_sha(Path(path))!=sha:raise ValueError('Immutable ancestor file changed')
                files[str(Path(path).resolve())]=sha
            prefix=chain(Path(link['parent_directory']))
            if (link.get('common_binding')!=binding or link.get('attempted_count')!=len(prefix)
                or rows[:len(prefix)]!=prefix or link.get('skipped_question_ids')!=[r['question_id'] for r in prefix]):
                raise ValueError('Inherited attempted prefix differs from its immutable parent')
        offset=len(prefix);segment=rows[offset:]
        if (not rows or len(rows)>=50 or len(calls)!=len(segment)
            or [r.get('question_id') for r in rows]!=[p['question_id'] for p in plans[:len(rows)]]
            or len({r.get('question_id') for r in rows})!=len(rows) or replay.get('generation_calls')!=0):
            raise ValueError('Recursive ledger/result must form one exact attempted prefix')
        for i,(row,call) in enumerate(zip(segment,calls)):
            plan=plans[offset+i];payload=call.get('request_payload')
            if (row.get('answer_sha256')!=core.text_sha(plan['answer']) or row.get('final_sha256')!=core.digest(plan['context']['final_context'])
                or not isinstance(payload,dict) or hashlib.sha256(json.dumps(payload).encode()).hexdigest()!=plan['request']['request_sha256']
                or hashlib.sha256(json.dumps(payload,ensure_ascii=False).encode()).hexdigest()!=call.get('request_sha256')
                or call.get('provider')!='DeepSeek' or call.get('model')!=plan['request']['model']
                or call.get('task')!='judge' or call.get('max_tokens')!=plan['request']['max_tokens']):
                raise ValueError('Recursive request/answer/Final source drift')
            interrupted=top and i==len(segment)-1
            if interrupted:
                if (row.get('status')!='inflight' or row.get('business_result') is not None or call.get('status')!='reserved'
                    or call.get('usage') is not None or call.get('raw_response_path') is not None
                    or (parent/f'ledger-response-{i+1:04d}.json').exists()
                    or receipt.get('interrupted_question_id')!=row['question_id'] or receipt.get('original_case_preserved')!=row
                    or receipt.get('original_call_sha256')!=core.digest(call)
                    or replay.get('status')!='running' or ledger.get('stopped') is not None):
                    raise ValueError('Only one final inflight/reserved request without response/Usage may be excluded')
                if datetime.fromisoformat(receipt['observed_at'])<=datetime.fromisoformat(call['started_at']):
                    raise ValueError('Owner absence must have been observed after the interrupted request')
                continue
            if not core.settled_call(call,plan['request']):raise ValueError('Unknown or unsettled ancestor/middle request cannot be bypassed')
            if row.get('status')=='completed' and row.get('business_result') in {'PASS','FAIL'} and (row.get('judgment') or {}).get('verdict')==row['business_result']:
                original=row['judgment'].get('raw_provider_response')
            elif row.get('status')=='NOT_EVALUABLE' and row.get('business_result') is None and continue_known_invalid and core.known_invalid_response(row.get('error') or {},call,plan['request']):
                original=row['error'].get('raw_response')
            else:raise ValueError('Ancestor/middle result is not completed or explicitly known-invalid')
            raw_path=Path(call.get('raw_response_path') or '')
            raw_path=raw_path.resolve() if raw_path.is_absolute() else (ROOT/raw_path).resolve()
            if not raw_path.is_relative_to(parent):raise ValueError('Ancestor raw response outside its directory')
            body=read(raw_path)
            if ((body.get('choices') or [{}])[0].get('message',{}).get('content')!=original
                or any((body.get('usage') or {}).get(k)!=call['usage'][k] for k in ('prompt_tokens','completion_tokens'))):
                raise ValueError('Ancestor raw response/Usage differs')
        settled=len(calls)-(1 if top else 0)
        if (replay.get('network_calls')!=offset+settled
            or link and (replay.get('parent_network_calls')!=offset or replay.get('new_network_calls')!=settled)):
            raise ValueError('Interrupted counter mismatch; reserved tail must remain separately consumed')
        visiting.remove(parent)
        return rows
    rows=chain(directory,True);projected=json.loads(json.dumps(rows));tail=projected[-1]
    tail.update(status='NOT_EVALUABLE',business_result=None,error={'error_type':'RequestExecutionUnknown',
        'detail':'Owner absent after interrupted reserved request; permanently excluded from this remaining-question execution, never retried',
        'request_execution_unknown':True,'usage_status':'Unknown','cost_status':'Unknown','original_call_sha256':receipt['original_call_sha256']},
        interrupted_original_row=rows[-1],budget_attempt_consumed=True)
    files[str(CORE)]=file_sha(CORE);files[str(Path(__file__).resolve())]=file_sha(Path(__file__).resolve())
    evidence={'parent_directory':str(directory),'attempted_count':len(rows),'skipped_question_ids':[r['question_id'] for r in rows],
        'common_binding':binding,'file_sha256':files,'interruption_receipt':str(receipt_path.resolve()),
        'interrupted_original_row':rows[-1],'interrupted_tail_excluded':True,'unknown_prior_attempts':1,
        'known_settled_prior_calls':len(rows)-1,'continue_known_invalid':continue_known_invalid}
    evidence['continuation_binding']=core.digest(evidence)
    evidence['claim_key']=core.digest({'common_binding':binding,'attempted_question_ids':sorted(r['question_id'] for r in rows)})
    return plans[len(rows):],{**evidence,'cases':projected}


def claim_once(parent,output,claim_directory):
    claim_directory.mkdir(parents=True,exist_ok=True)
    path=claim_directory/(parent['claim_key']+'.json')
    with path.open('x') as stream:
        json.dump({'common_binding':parent['common_binding'],'attempted_question_ids':parent['skipped_question_ids'],
            'continuation_binding':parent['continuation_binding'],'output':str(output.resolve()),'owner_pid':os.getpid(),
            'claimed_at':datetime.now(timezone.utc).isoformat(),'automatic_release':False},stream,indent=2)
        stream.flush();os.fsync(stream.fileno())
    return path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent-dir',type=Path,required=True);parser.add_argument('--interruption-receipt',type=Path,required=True)
    parser.add_argument('--exclude-interrupted-tail',action='store_true');parser.add_argument('--continue-known-invalid',action='store_true')
    parser.add_argument('--target-snapshot',required=True);parser.add_argument('--database',type=Path,default=ROOT/'backend/data/demo.db')
    parser.add_argument('--index-dir',type=Path,default=ROOT/'backend/data/index');parser.add_argument('--documents-dir',type=Path,default=ROOT/'backend/documents')
    parser.add_argument('--execute',action='store_true');parser.add_argument('--expected-binding');parser.add_argument('--expected-continuation-binding')
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    if not args.exclude_interrupted_tail:parser.error('default unknown guard retained; explicit --exclude-interrupted-tail required')
    credential_file=Path(os.environ.get('RAG_DEMO_ENV_PATH') or ROOT/'.env')
    args.output.mkdir(parents=True,exist_ok=False);preflight=args.output/'full_preflight'
    old_argv=sys.argv
    try:
        sys.argv=[str(CORE),'--database',str(args.database),'--index-dir',str(args.index_dir),'--documents-dir',str(args.documents_dir),
            '--target-snapshot',args.target_snapshot,'--output',str(preflight)]
        core.main()
    finally:sys.argv=old_argv
    audit=json.loads((preflight/'audit.json').read_text());bundle=json.loads((preflight/'saved_execution_bundle.json').read_text())
    if not audit['can_execute']:raise SystemExit('Current complete read-only preflight is blocked')
    with tempfile.TemporaryDirectory(prefix='unattempted-judge-isolated-') as isolated:
        for key,name in {'RAG_DEMO_DB_PATH':'unused.sqlite','RAG_DEMO_ENV_PATH':'empty.env','RAG_DEMO_INDEX_DIR':'index','RAG_DEMO_DOCUMENTS_DIR':'documents','RAG_DEMO_UPLOADS_DIR':'uploads'}.items():os.environ[key]=str(Path(isolated)/name)
        from app.config import Settings,load_settings
        from app.providers import DeepSeekProvider
        settings=load_settings(env_file=credential_file)
        provider=DeepSeekProvider(settings if settings.configured else Settings('dry-run',settings.base_url,settings.model,settings.timeout_seconds))
        db=sqlite3.connect(args.database.resolve().as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
        try:
            db.execute('PRAGMA query_only=ON');db.execute('BEGIN')
            source=json.loads(db.execute('SELECT dataset_snapshot_json FROM evaluation_runs WHERE id=?',(audit['source_run_id'],)).fetchone()[0])
            target,blockers=core.load_target(db,args.target_snapshot)
        finally:db.close()
        if blockers:raise SystemExit('Approved frozen target changed')
        manifest,chunks,corpus_audit,blockers=core.load_corpus(args.index_dir,args.documents_dir)
        rows={r['question_id']:{'model_answer':r['answer'],'programmatic_metrics':{'retrieval_trace':r['retrieval_trace']}} for r in bundle['cases']}
        plans,blockers2=core.prepare_plans(target,source,rows,chunks,provider)
        if blockers or blockers2 or corpus_audit!=audit['corpus_audit'] or [{'question_id':p['question_id'],'request':p['request'],'compiled_contract_hash':p['compiled_contract_hash']} for p in plans]!=audit['requests']:
            raise SystemExit('Complete source/request plan changed after read-only audit')
        remaining,parent=prepare_interrupted_parent(args.parent_dir,plans,audit['binding'],args.interruption_receipt,
            exclude_interrupted_tail=args.exclude_interrupted_tail,continue_known_invalid=args.continue_known_invalid)
        report={**audit,'continuation_parent':{k:v for k,v in parent.items() if k!='cases'},'remaining_question_ids':[p['question_id'] for p in remaining],
            'budget_attempts_consumed':parent['attempted_count'],'unknown_prior_attempts':1,'known_settled_prior_calls':parent['known_settled_prior_calls'],
            'retry_interrupted_question':False,'release_interrupted_ledger':False,'cost_status':'Unknown'}
        (args.output/'audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        (args.output/'saved_execution_bundle.json').write_bytes((preflight/'saved_execution_bundle.json').read_bytes())
        print(json.dumps({'output':str(args.output),'can_execute':True,'binding':audit['binding'],'continuation_binding':parent['continuation_binding'],
            'consumed_attempts':parent['attempted_count'],'remaining':len(remaining),'unknown_preserved':1,'claim_key':parent['claim_key'],'network_calls':0}),flush=True)
        if not args.execute:return 0
        if not settings.configured or args.expected_binding!=audit['binding'] or args.expected_continuation_binding!=parent['continuation_binding']:
            raise SystemExit('Exact common/continuation bindings and configured credentials required')
        for path,sha in parent['file_sha256'].items():
            if file_sha(Path(path))!=sha:raise SystemExit('Parent/proof/controller changed after preflight')
        claim=claim_once(parent,args.output,ROOT/'docs/judge_vnext_20261030/.judge_replay_claims')
        (args.output/'owner.json').write_text(json.dumps({'pid':os.getpid(),'claim_file':str(claim),'automatic_restart':False},indent=2)+'\n')
        result=core.execute_plans(remaining,provider,args.output,audit['binding'],audit['timing_provenance'],continue_known_invalid=args.continue_known_invalid,parent=parent)
        result.update(unknown_prior_attempts=1,known_settled_prior_calls=parent['known_settled_prior_calls'],budget_attempts_consumed=result['network_calls'],
            interrupted_question_id=parent['interrupted_original_row']['question_id'],retry_interrupted_question=False,release_interrupted_ledger=False,
            cost_status='Unknown',formal_baseline_created=False,production_database_writes=0,app_main_imported='app.main' in sys.modules)
        (args.output/'replay.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        return 0 if result['status'] in {'completed','processed_all_with_technical_errors'} else 1


if __name__=='__main__':raise SystemExit(main())
