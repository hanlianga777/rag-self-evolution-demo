#!/usr/bin/env python3
"""Eight synthetic Provider probes, opt-in only; no formal evaluation or DB access.

Default: dry-run. --execute: one serial pass, no retry/resume/fallback.
Uses production request/response parser and independent PaidRun accounting.
The tiny JSON judging task validates transport, not VNext business calibration.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import tempfile
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = ROOT / 'docs' / 'judge_vnext_20261029'
SYSTEM = ('Judge only the supplied synthetic arithmetic fact. Return a JSON object with exactly '
          'verdict (PASS or FAIL), met (boolean), answer_quote (the unchanged answer), '
          'final_quote (the unchanged Final). Example JSON: '
          '{"verdict":"PASS","met":true,"answer_quote":"2","final_quote":"1+1=2"}. '
          'Do not add explanation or markdown. This is a transport calibration, not robotics guidance.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true', help='send exactly the eight displayed short probes')
    parser.add_argument('--output', type=Path, help='new directory; existing paths are refused')
    args = parser.parse_args()
    # Establish isolated storage before importing any app module. Credentials are
    # loaded only by config.load_settings from the original configured env file.
    credential_file = Path(os.environ.get('RAG_DEMO_ENV_PATH') or ROOT / '.env')
    with tempfile.TemporaryDirectory(prefix='judge-provider-isolated-') as isolated:
        for name, suffix in {'RAG_DEMO_DB_PATH':'unused.sqlite', 'RAG_DEMO_ENV_PATH':'empty.env',
                             'RAG_DEMO_INDEX_DIR':'index', 'RAG_DEMO_DOCUMENTS_DIR':'documents',
                             'RAG_DEMO_UPLOADS_DIR':'uploads'}.items():
            os.environ[name] = str(Path(isolated) / suffix)
        sys.path.insert(0, str(ROOT / 'backend'))
        from app.config import load_settings
        from app.providers import DeepSeekProvider, thinking_task, provider_error_details, _response_metadata
        from app.paid_run import PaidRun, accounting_only, controlled_run, execution_limits, provider_task
        from app.telemetry import collect_usage
        settings = load_settings(env_file=credential_file)
        address = urlsplit(settings.base_url)
        if (address.scheme != 'https' or address.netloc != 'api.deepseek.com'
                or address.path not in ('', '/v1') or address.query or address.fragment):
            raise SystemExit('Blocked: configured endpoint is not the approved official DeepSeek route')
        if settings.model != 'deepseek-flash':
            raise SystemExit('Blocked: configured model differs from deepseek-flash; no silent model switch')
        provider = DeepSeekProvider(settings)
        plans = []
        with execution_limits({'provider_validation':4096}), provider_task('provider_validation'):
            for effort in ('off', 'low', 'high', 'max'):
                for stream in (False, True):
                    answer = '3' if stream else '2'
                    user = json.dumps({'question':'What is 1+1?', 'final':'1+1=2', 'answer':answer})
                    with thinking_task('provider_validation', effort):
                        summary = provider.request_summary(SYSTEM, user, True, stream=stream)
                    plans.append({'effort':effort, 'stream':stream, 'answer':answer, 'user':user, 'summary':summary})
        manifest = {'execute':args.execute, 'network_calls':0, 'endpoint':settings.base_url + '/chat/completions',
                    'requested_model':settings.model, 'configured':settings.configured,
                    'app_main_imported':'app.main' in sys.modules,
                    'storage_isolated':all(str(os.environ[k]).startswith(isolated) for k in
                                          ('RAG_DEMO_DB_PATH', 'RAG_DEMO_INDEX_DIR', 'RAG_DEMO_ENV_PATH')),
                    'requests':[p['summary'] for p in plans], 'retry_policy':'none',
                    'actual_cost':None, 'cost_status':'not_reported_by_provider',
                    'scope':'synthetic_transport_only_not_formal_baseline_or_business_calibration'}
        if not args.execute:
            print(json.dumps(manifest, ensure_ascii=False, indent=2))
            return 0
        if not settings.configured:
            raise SystemExit('Blocked: Provider credential is not configured')
        # A previous uncertain attempt must be reconciled, never silently reissued.
        for ledger in OUTPUT_ROOT.glob('provider_*/ledger.json'):
            prior = json.loads(ledger.read_text())
            if any(call.get('status') not in {'ok', 'rejected'} for call in prior.get('calls', [])):
                raise SystemExit('Blocked: a previous Provider probe ledger has unknown/inflight usage')
        output = args.output or OUTPUT_ROOT / ('provider_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
        output.mkdir(parents=True, exist_ok=False)
        identity = {'scope':'provider_validation_20261029', 'requests':[p['summary']['request_sha256'] for p in plans]}
        ledger = PaidRun(output / 'ledger.json', identity=identity, identity_check=lambda:identity,
                         output_limits={'provider_validation':4096})
        report = {**manifest, 'results':[], 'status':'running', 'started_at':datetime.now(timezone.utc).isoformat()}
        report_path = output / 'report.json'
        def save():
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        save()
        with accounting_only(), controlled_run(ledger), provider_task('provider_validation'):
            for plan in plans:
                item = {'effort':plan['effort'], 'stream':plan['stream'], 'request':plan['summary']}
                report['results'].append(item)
                try:
                    with collect_usage() as usage, thinking_task('provider_validation', plan['effort']):
                        result = provider.complete_with_metrics(SYSTEM, plan['user'], True, stream=plan['stream'])
                    report['network_calls'] = len(ledger.calls)
                    content = json.loads(result['content'])
                    expected = {'verdict':'FAIL' if plan['stream'] else 'PASS', 'met':not plan['stream'],
                                'answer_quote':plan['answer'], 'final_quote':'1+1=2'}
                    valid = content == expected and type(content.get('met')) is bool
                    item.update(status='ok' if valid else 'json_semantic_mismatch', result=result,
                                response_metadata=_response_metadata.get(), json_valid=True, expected=expected,
                                usage=usage, actual_cost=None, cost_status='not_reported_by_provider')
                    save()
                    print(json.dumps({'effort':plan['effort'], 'stream':plan['stream'], 'status':item['status'],
                                      'latency_ms':result['generation_ms'], 'usage':result['usage']}, ensure_ascii=False), flush=True)
                    if not valid:
                        report['status']='stopped_json_semantic_mismatch'
                        break
                except Exception as error:
                    report['network_calls'] = len(ledger.calls)
                    item.update(status='error', error=provider_error_details(error, 'provider_validation'))
                    report['status']='stopped_error_no_retry'
                    ledger.stop(type(error).__name__)
                    save()
                    print(json.dumps({'status':report['status'], 'error_type':type(error).__name__, 'report':str(report_path)}), flush=True)
                    break
        if report['status'] == 'running':
            report['status']='completed'
        report['finished_at']=datetime.now(timezone.utc).isoformat()
        report['storage_files_created']=sorted(str(p.relative_to(isolated)) for p in Path(isolated).rglob('*') if p.is_file())
        save()
        print(json.dumps({'status':report['status'], 'network_calls':report['network_calls'], 'report':str(report_path)}), flush=True)
        return 0 if report['status']=='completed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
