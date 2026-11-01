#!/usr/bin/env python3
"""One explicitly reviewed saved-answer Judge correction; no generation or DB writes."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def verify_review(directory):
    plan=json.loads((directory/'request_plan.json').read_text())
    binding=plan['review_binding'];payload={k:v for k,v in plan.items() if k!='review_binding'}
    if digest(payload)!=binding or plan.get('additional_network_calls_if_authorized')!=1 or plan.get('max_attempts')!=1:
        raise ValueError('Single-call reviewed plan binding is invalid')
    for source in plan['source_files']:
        if hashlib.sha256(Path(source['path']).read_bytes()).hexdigest()!=source['sha256']:
            raise ValueError('Reviewed source file changed: '+source['path'])
    for name,sha in plan['artifact_file_sha256'].items():
        path=(directory/name).resolve()
        if not path.is_relative_to(directory.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest()!=sha:
            raise ValueError('Reviewed request artifact changed: '+name)
    return plan,json.loads((directory/'request_input.json').read_text())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--review-dir',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--expected-review-binding')
    parser.add_argument('--expected-request-sha256')
    args=parser.parse_args();plan,fields=verify_review(args.review_dir)
    if args.execute and (args.expected_review_binding!=plan['review_binding'] or args.expected_request_sha256!=plan['request']['request_sha256']):
        raise SystemExit('Blocked: exact reviewed binding and request SHA required for the additional single call')
    credential_file=Path(os.environ.get('RAG_DEMO_ENV_PATH') or ROOT/'.env')
    with tempfile.TemporaryDirectory(prefix='saved-judge-correction-isolated-') as isolated:
        for key,name in {'RAG_DEMO_DB_PATH':'unused.sqlite','RAG_DEMO_ENV_PATH':'empty.env','RAG_DEMO_INDEX_DIR':'index','RAG_DEMO_DOCUMENTS_DIR':'documents','RAG_DEMO_UPLOADS_DIR':'uploads'}.items():
            os.environ[key]=str(Path(isolated)/name)
        sys.path.insert(0,str(ROOT/'backend'))
        from app.config import Settings,load_settings
        from app.providers import DeepSeekProvider
        from app.evaluation_contract import BUSINESS_JUDGE_PROMPT,VERSIONS,business_judge_input
        from app.paid_run import REQUEST_LIMITS,provider_task,execution_limits
        settings=load_settings(env_file=credential_file);address=urlsplit(settings.base_url)
        if address.scheme!='https' or address.netloc!='api.deepseek.com' or address.path not in ('','/v1') or address.query or address.fragment or settings.model!='deepseek-flash':
            raise SystemExit('Official reviewed Flash route required')
        provider=DeepSeekProvider(settings if settings.configured else Settings('dry-run',settings.base_url,settings.model,settings.timeout_seconds))
        if VERSIONS!=plan['versions'] or hashlib.sha256(BUSINESS_JUDGE_PROMPT.encode()).hexdigest()!=plan['judge_prompt_sha256']:
            raise SystemExit('Reviewed common Judge identity changed')
        context={k:v for k,v in fields.items() if k not in ('question','reference_answer','actual_answer')}
        with provider_task('judge'),execution_limits({'judge':REQUEST_LIMITS['judge']}):
            summary=provider.request_summary(BUSINESS_JUDGE_PROMPT,business_judge_input(fields['question'],fields['reference_answer'],fields['actual_answer'],context),True,temperature=0)
        if summary!=plan['request']:
            raise SystemExit('Current official request differs from reviewed request')
        if args.execute and not settings.configured:
            raise SystemExit('Configured credentials required')
        args.output.mkdir(parents=True,exist_ok=False)
        audit={'artifact_type':'explicit_single_judge_correction_not_formal_baseline','execute':args.execute,'review_binding':plan['review_binding'],
            'request':summary,'question_id':plan['question_id'],'common50_binding':plan['common50_binding'],'network_calls':0,'generation_calls':0,
            'production_database_writes':0,'formal_baseline_created':False,'original_result_unchanged':True,'retry_policy':'none'}
        (args.output/'audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps({'output':str(args.output),'execute':args.execute,'request_sha256':summary['request_sha256'],'review_binding':plan['review_binding'],'network_calls':0}),flush=True)
        if not args.execute:return 0
        verify_review(args.review_dir)
        spec=importlib.util.spec_from_file_location('saved_replay',ROOT/'scripts/replay_saved_answers_judge_only_20261030.py')
        replay=importlib.util.module_from_spec(spec);spec.loader.exec_module(replay)
        # Keep the original local Canonical validation context; never serialized to the Provider.
        context['_canonical_chunks']=json.loads(Path(plan['canonical_chunks_file']).read_text())
        execution=[{'question_id':plan['question_id'],'question':fields['question'],'expected':fields['reference_answer'],'answer':fields['actual_answer'],'context':context,'request':summary}]
        result=replay.execute_plans(execution,provider,args.output,plan['review_binding'],'historical_generation_only_not_new_v2_or_max_performance')
        result.update(artifact_type='explicit_single_judge_correction_not_formal_baseline',common50_binding=plan['common50_binding'],
            formal_baseline_created=False,production_database_writes=0,original_result_unchanged=True,app_main_imported='app.main' in sys.modules,
            isolated_storage_files=sorted(str(p.relative_to(isolated)) for p in Path(isolated).rglob('*') if p.is_file()))
        (args.output/'replay.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        return 0 if result['status']=='completed' else 1


if __name__=='__main__':
    raise SystemExit(main())
