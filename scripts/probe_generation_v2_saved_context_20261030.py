#!/usr/bin/env python3
"""One production Generation V2 request, default dry-run, never formal evaluation.

The retriever is an explicit saved-Canonical-context substitute: no search,
Embedding, Rerank, Golden, Judge or database. --execute additionally requires
an exact dry-run binding and a new output
folder. Network permission/approval remains the caller's responsibility.
"""
import argparse
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from types import SimpleNamespace
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST=ROOT/'docs/judge_vnext_20261030/generation_v2_saved_context_manifest.json'
BANNED_INPUT_FIELDS=('reference_answer','business_requirements','scoring_contract','atomic_results','expected_verdict','golden_snapshot')


def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode()).hexdigest()


def load_manifest(path):
    manifest=json.loads(Path(path).read_text())
    if manifest.get('schema_version')!='generation-v2-saved-context-probe-1' or manifest.get('max_requests')!=1:
        raise ValueError('One-request saved-context manifest required')
    for source in manifest['source_files']:
        if hashlib.sha256(Path(source['path']).read_bytes()).hexdigest()!=source['sha256']:
            raise ValueError('Public source binding changed')
    canonical={c['chunk_id']:c for c in json.loads(Path(manifest['canonical_chunks_path']).read_text())}
    if [s['chunk_id'] for s in manifest['saved_final']]!=['DOC-001-C-00140','DOC-001-C-00141']:
        raise ValueError('Only the two reviewed manual fragments are allowed')
    for entry in manifest['saved_final']:
        child=canonical[entry['chunk_id']]
        if entry['content']!=child['chunk_text'] or any(entry.get(k)!=child.get(k) for k in ('document_id','product','version','page_start','page_end')):
            raise ValueError('Saved context differs from actual Canonical manual body/scope')
    if any(field in json.dumps(manifest,ensure_ascii=False) for field in BANNED_INPUT_FIELDS):
        raise ValueError('Generation manifest must not contain Golden/scoring fields')
    return manifest


class DryRequest(RuntimeError):
    """Local control signal after production request construction, before sending."""


def instrumented_provider(settings, *, send=False, expected_wire_sha=None):
    from app.providers import DeepSeekProvider
    class SingleRequestProvider(DeepSeekProvider):
        def __init__(self):
            super().__init__(settings)
            self.calls=0;self.captured=None
        def complete_with_metrics(self,system,user,json_mode=False,*,stream=False,temperature=0.2):
            self.calls+=1
            if self.calls!=1:
                raise RuntimeError('Single generation request cap exceeded; no retries or auxiliary requests')
            request=self._request(system,user,json_mode,stream,temperature)
            payload=json.loads(request.data)
            wire_sha=hashlib.sha256(request.data).hexdigest()
            if request.full_url!='https://api.deepseek.com/chat/completions':
                raise ValueError('Only the exact approved official endpoint is allowed')
            if any(field in json.dumps(payload,ensure_ascii=False) for field in BANNED_INPUT_FIELDS):
                raise ValueError('Scoring information cannot enter generation')
            self.captured={'endpoint':request.full_url,'request_payload':payload,
                'request_summary':self.request_summary(system,user,json_mode,stream=stream,temperature=temperature),
                'request_wire_sha256':wire_sha}
            if expected_wire_sha is not None and wire_sha!=expected_wire_sha:
                raise ValueError('Production generation request changed after dry-run')
            if not send:
                raise DryRequest('Dry-run: request constructed, not sent')
            return super().complete_with_metrics(system,user,json_mode,stream=stream,temperature=temperature)
    return SingleRequestProvider()


def make_service(provider,manifest):
    from app.ai_service import AiService
    from app.retrieval import VectorRetriever
    chunks=[{**e,'chunk_text':e['content'],'text':e['content'],'document_name':e['document']} for e in manifest['saved_final']]
    corpus=SimpleNamespace(chunks=lambda:deepcopy(chunks))
    class SavedContextRetriever(VectorRetriever):
        @contextmanager
        def snapshot(self):
            yield {'chunks':deepcopy(chunks)}
        def retrieve(self,question,config,*,aliases,queries,stages,trace):
            if aliases or queries:
                raise ValueError('No auxiliary search or query calls are allowed')
            evidence=deepcopy(manifest['saved_final'])
            trace.update(status='saved_context_replayed',artifact_schema_version=3,
                retrieval_mode='explicit_saved_context_substitute_no_search',full_corpus_retrieval_performed=False,
                question=question,config=deepcopy(config),corpus_fingerprint=manifest['corpus_fingerprint'],
                candidates=None,reranked=None,final=deepcopy(evidence),parent_expand=False)
            return evidence
    service=AiService(object(),corpus,provider,False,generation_prompt_version='generation-vnext-2')
    service.retriever=SavedContextRetriever(corpus)
    return service


def probe_config():
    from app.policy import DEFAULT_PIPELINE_CONFIG
    return {**DEFAULT_PIPELINE_CONFIG,'prompt_strategy':'Grounded','generation_thinking':'max',
        'query_rewrite':False,'multi_query':False,'hyde':False,'query_decompose':False,
        'metadata_filter':'OFF','alias_mapping':False,'retrieval_max_tokens':False,
        'run_target':'generation_probe_saved_context'}


def prepare_plan(manifest,settings):
    from app.paid_run import REQUEST_LIMITS,execution_limits
    provider=instrumented_provider(settings)
    service=make_service(provider,manifest)
    with execution_limits({'answer':REQUEST_LIMITS['answer']}):
        try:
            service.answer(manifest['question'],probe_config())
        except DryRequest:
            pass
        else:
            raise RuntimeError('Dry-run did not stop at the production generation request')
    if provider.calls!=1 or provider.captured is None:
        raise RuntimeError('Exactly one production generation request must be planned')
    plan={**provider.captured,'generation_identity':service.generation_contract,
        'config':probe_config(),'saved_final':deepcopy(manifest['saved_final']),
        'manifest_sha256':digest(manifest),'planned_requests':1,'network_calls':0,
        'full_corpus_retrieval_performed':False,'retry_policy':'none','actual_cost':None}
    plan['binding']=digest(plan)
    return plan


def source_display_observation(answer,final):
    machine=re.findall(r'\bDOC-\d+-[CP]-\d+\b',answer)
    normalized=lambda text:re.sub(r'[\s_《》〈〉“”「」（）().·\-]','',text.casefold().removesuffix('.pdf'))
    document_names=[s['document'] for s in final]
    document_found=any(normalized(name) in normalized(answer) for name in document_names)
    sections={s.get('section_path') or s.get('section') for s in final}
    section_found=any(section and section in answer for section in sections)
    pages=[{'start':int(start),'end':int(end or start)} for start,end in re.findall(r'(?:第|P\.?\s*)(\d+)(?:\s*[-—–～至]\s*(\d+))?',answer,re.I)]
    allowed={p for s in final for p in range(s['page_start'],s.get('page_end',s['page_start'])+1)}
    page_ranges_valid=all(p['start']<=p['end'] and all(page in allowed for page in range(p['start'],p['end']+1)) for p in pages) if pages else None
    return {'machine_chunk_ids':machine,'saved_document_name_found':document_found,'saved_section_name_found':section_found,
        'page_references_found':pages,'all_page_ranges_within_saved_context':page_ranges_valid,
        'status':'observed_human_source_metadata' if not machine and (document_found or section_found) and page_ranges_valid is True else 'needs_manual_source_review',
        'validation_scope':'surface_observation_only_not_semantic_support_or_business_judgment',
        'answer_rewritten':False}


def execute_probe(manifest,settings,plan,output,authorization=None):
    from app.paid_run import PaidRun,REQUEST_LIMITS,accounting_only,controlled_run
    from app.providers import provider_error_details,_response_metadata
    provider=instrumented_provider(settings,send=True,expected_wire_sha=plan['request_wire_sha256'])
    service=make_service(provider,manifest)
    ledger=PaidRun(output/'ledger.json',identity=plan['binding'],identity_check=lambda:plan['binding'],output_limits={'answer':REQUEST_LIMITS['answer']})
    report={'scope':'one_generation_v2_saved_context_probe_not_baseline_or_retrieval_acceptance',
        'authorization_evidence':authorization,'binding':plan['binding'],'generation_identity':service.generation_contract,
        'status':'running','network_calls':0,'max_requests':1,'retries':0,'generation_calls':0,
        'actual_cost':None,'cost_status':'not_reported_by_provider','full_corpus_retrieval_performed':False,
        'formal_runs_created':0,'production_database_writes':0,
        'usage_accounting_semantics':'reasoning_tokens_are_already_in_completion_tokens_do_not_add_twice',
        'timing_provenance':'saved_context_copy_plus_generation_not_full_live_RAG_performance'}
    def save():
        (output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    save()
    try:
        with accounting_only(),controlled_run(ledger):
            result=service.answer(manifest['question'],probe_config())
        report.update(status='completed',result=result,response_metadata=_response_metadata.get(),
            source_display_observation=source_display_observation(result['answer'],result['retrieval_trace']['final']))
    except Exception as error:
        ledger.stop(type(error).__name__)
        report.update(status='stopped_error_no_retry',error=provider_error_details(error,'generation_v2_saved_context_probe'))
    report.update(network_calls=len(ledger.calls),generation_calls=len(ledger.calls),finished_at=datetime.now(timezone.utc).isoformat())
    save()
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,default=DEFAULT_MANIFEST)
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--expected-binding',help='binding from the reviewed dry-run')
    parser.add_argument('--output',type=Path,help='new directory required for execution')
    args=parser.parse_args()
    credential_file=Path(os.environ.get('RAG_DEMO_ENV_PATH') or ROOT/'.env')
    with tempfile.TemporaryDirectory(prefix='generation-v2-probe-isolated-') as isolated:
        for key in ('RAG_DEMO_DB_PATH','RAG_DEMO_ENV_PATH','RAG_DEMO_INDEX_DIR','RAG_DEMO_DOCUMENTS_DIR','RAG_DEMO_UPLOADS_DIR'):
            os.environ[key]=str(Path(isolated)/key)
        sys.path.insert(0,str(ROOT/'backend'))
        from app.config import Settings,load_settings
        actual=load_settings(env_file=credential_file)
        address=urlsplit(actual.base_url)
        if actual.base_url!='https://api.deepseek.com' or address.query or address.fragment or actual.model!='deepseek-flash':
            raise SystemExit('Exact official DeepSeek route and configured Flash model required; no fallback')
        manifest=load_manifest(args.manifest)
        settings=actual if actual.configured else Settings('dry-run',actual.base_url,actual.model,actual.timeout_seconds)
        plan=prepare_plan(manifest,settings)
        plan['execute']=False;plan['app_main_imported']='app.main' in sys.modules
        plan['isolated_storage_files']=sorted(str(p.relative_to(isolated)) for p in Path(isolated).rglob('*') if p.is_file())
        if not args.execute:
            print(json.dumps(plan,ensure_ascii=False,indent=2))
            return 0
        if not args.output or args.expected_binding!=plan['binding'] or not actual.configured:
            raise SystemExit('Execution requires a new output, exact --expected-binding and credentials')
        args.output.mkdir(parents=True,exist_ok=False)
        (args.output/'request_plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n')
        report=execute_probe(manifest,actual,plan,args.output)
        print(json.dumps({'status':report['status'],'network_calls':report['network_calls'],'output':str(args.output)},ensure_ascii=False))
        return 0 if report['status']=='completed' else 1


if __name__=='__main__':
    raise SystemExit(main())
