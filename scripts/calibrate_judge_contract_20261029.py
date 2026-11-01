#!/usr/bin/env python3
"""Up to four source-bound synthetic-answer calibrations of production Judge.

Default dry-run; --execute runs the selected sample set.
Input JSON: source_files:[{path,sha256}], cases:[{id,fixture_label,golden_item,
answer,context,expected_verdict}]. Frozen golden_item and original Final are
provided by the reviewed sample preparation, never generated in this script.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--samples', type=Path, required=True)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    data = json.loads(args.samples.read_text())
    cases = data.get('cases', [])
    if not 1 <= len(cases) <= 4:
        raise SystemExit('Require 1 to 4 reviewed calibration cases')
    if any(not isinstance(c,dict) or not isinstance(c.get('id'),str) or not c['id'].strip() for c in cases) or len({c['id'] for c in cases})!=len(cases):
        raise SystemExit('Duplicate or missing sample ID; each sample may be called once')
    if not data.get('source_files'):
        raise SystemExit('Frozen source file hashes are required')
    for source in data['source_files']:
        if hashlib.sha256(Path(source['path']).read_bytes()).hexdigest() != source['sha256']:
            raise SystemExit('Frozen source hash changed')
    credential_file = Path(os.environ.get('RAG_DEMO_ENV_PATH') or ROOT / '.env')
    with tempfile.TemporaryDirectory(prefix='judge-calibration-isolated-') as isolated:
        for key, suffix in {'RAG_DEMO_DB_PATH':'unused.sqlite', 'RAG_DEMO_ENV_PATH':'empty.env',
                            'RAG_DEMO_INDEX_DIR':'index', 'RAG_DEMO_DOCUMENTS_DIR':'documents',
                            'RAG_DEMO_UPLOADS_DIR':'uploads'}.items():
            os.environ[key] = str(Path(isolated) / suffix)
        sys.path.insert(0, str(ROOT / 'backend'))
        from app.config import load_settings
        from app.providers import DeepSeekProvider, provider_error_details
        from app.paid_run import PaidRun, accounting_only, controlled_run, provider_task, execution_limits, REQUEST_LIMITS
        from app.scoring_contract import compile_contract
        from app.evaluation_contract import BUSINESS_JUDGE_PROMPT, business_judge_input, VERSIONS
        provider = DeepSeekProvider(load_settings(env_file=credential_file))
        route = urlsplit(provider.settings.base_url)
        if (route.scheme != 'https' or route.netloc != 'api.deepseek.com' or route.path != ''
                or route.query or route.fragment or provider.settings.model != 'deepseek-flash'):
            raise SystemExit('Configured official Flash route is required; no route/model fallback')
        judge_limit = REQUEST_LIMITS['judge']
        plans = []
        with provider_task('judge'), execution_limits({'judge':judge_limit}):
            for case in cases:
                if case.get('fixture_label') != 'approved_direction_synthetic_answer' or case.get('expected_verdict') not in {'PASS','FAIL'}:
                    raise SystemExit('Explicit synthetic-answer label and reviewed expected verdict required')
                item = case['golden_item']
                contract = compile_contract(item)
                context = {**case['context'], 'contract_version':'business-vnext-1',
                           'category':item['test_category'], 'scoring_contract':contract}
                if not isinstance(context.get('final_context'), list):
                    raise SystemExit('Complete source-bound Final is required')
                question = item['question']
                expected = item.get('reference_answer') or item.get('expected_behavior') or item.get('raw',{}).get('expected_behavior')
                if not expected:
                    raise SystemExit('Frozen reference/expected behavior required')
                user = business_judge_input(question, expected, case['answer'], context)
                summary = provider.request_summary(BUSINESS_JUDGE_PROMPT, user, True, temperature=0)
                assert summary['reasoning_effort'] == 'max'
                plans.append({'id':case['id'], 'question':question, 'expected':expected, 'answer':case['answer'],
                              'context':context, 'expected_verdict':case['expected_verdict'], 'request':summary})
        report = {'execute':args.execute, 'network_calls':0, 'samples_sha256':hashlib.sha256(args.samples.read_bytes()).hexdigest(),
                  'versions':VERSIONS, 'judge_prompt_sha256':hashlib.sha256(BUSINESS_JUDGE_PROMPT.encode()).hexdigest(),
                  'source_files':data['source_files'], 'status':'dry_run', 'results':[],
                  'requests':[{'id':p['id'],'request':p['request'],
                               'compiled_contract_hash':p['context']['scoring_contract']['compiled_contract_hash']} for p in plans],
                  'scope':'approved_direction_synthetic_answer_not_human_gold_or_formal_evaluation',
                  'actual_cost':None, 'cost_status':'not_reported_by_provider', 'retry_policy':'none'}
        if not args.execute:
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0
        if args.output is None:
            raise SystemExit('--execute requires a new explicit --output directory')
        args.output.mkdir(parents=True, exist_ok=False)
        identity = {'scope':'judge_contract_calibration_20261029', 'samples_sha256':report['samples_sha256'],
                    'requests':[p['request']['request_sha256'] for p in plans]}
        ledger = PaidRun(args.output / 'ledger.json', identity=identity, identity_check=lambda:identity, output_limits={'judge':judge_limit})
        report['status']='running'
        def save():
            (args.output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        save()
        with accounting_only(), controlled_run(ledger), provider_task('judge'):
            for plan in plans:
                result = {'id':plan['id'], 'fixture_label':'approved_direction_synthetic_answer',
                          'expected_verdict':plan['expected_verdict'], 'request':plan['request']}
                report['results'].append(result)
                try:
                    judged = provider.judge(plan['question'], plan['expected'], plan['answer'], context=plan['context'])
                    result.update(status='ok', judgment=judged, expected_match=judged['verdict']==plan['expected_verdict'])
                    if not result['expected_match']:
                        report['status']='stopped_semantic_mismatch_no_retry'
                except Exception as error:
                    result.update(status='technical_error', error=provider_error_details(error, 'judge_calibration'))
                    report['status']='stopped_technical_error_no_retry'
                    ledger.stop(type(error).__name__)
                report['network_calls']=len(ledger.calls)
                save()
                print(json.dumps({'id':plan['id'],'status':result['status'],'expected_match':result.get('expected_match')}), flush=True)
                if report['status']!='running':
                    break
        if report['status']=='running':
            report['status']='completed'
        report['finished_at']=datetime.now(timezone.utc).isoformat()
        report['storage_files_created']=sorted(str(p.relative_to(isolated)) for p in Path(isolated).rglob('*') if p.is_file())
        report['app_main_imported']='app.main' in sys.modules
        save()
        return 0 if report['status']=='completed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
