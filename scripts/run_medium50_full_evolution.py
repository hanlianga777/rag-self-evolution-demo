"""Explicit 2026-10-14 owner scope; durable serial run, stops before Gate 2."""
import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
OUTPUT = ROOT / 'output/playwright/medium50-full-20261014'
SOURCE = Path('/Users/zhanghaohan/.codex/attachments/fbaa0811-e5ad-49a4-b3b7-13ad4b266be7/已粘贴的文本.txt')


def save(name, value):
    target = OUTPUT / name
    temporary = target.with_suffix('.tmp')
    with temporary.open('w') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.flush(); os.fsync(stream.fileno())
    os.replace(temporary, target)


def execute(stage):
    from app.corpus import current_manifest, manifest_identity
    from app.full_text import validate_bundle
    from app.paid_run import PaidRun, REQUEST_LIMITS, accounting_only, controlled_run
    current = manifest_identity(current_manifest())
    if stage == 'generate':
        OUTPUT.mkdir(parents=True, exist_ok=False)
        with sqlite3.connect(ROOT / 'backend/data/demo.db') as db:
            for table in ('golden_generation_runs', 'evaluation_runs', 'agent_traces', 'candidate_revision_runs'):
                if db.execute(f"SELECT 1 FROM {table} WHERE status IN ('running','queued','coverage','generating','validation','probing','qc')").fetchone():
                    raise RuntimeError('Active task; refused new owner run')
            with sqlite3.connect(OUTPUT / 'before.db') as backup:
                db.backup(backup)
        shutil.copytree(ROOT / 'backend/data/index', OUTPUT / 'index-before')
        shutil.copy2(ROOT / 'backend/data/corpus_state.json', OUTPUT / 'corpus-state-before.json')
        validate_bundle(ROOT / 'backend/data/index', require_full_text=True)
        protected = {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for folder in ('backend/documents','backend/data/index') for p in (ROOT / folder).rglob('*') if p.is_file()}
        save('protected-assets.json', protected)
        save('source-authorization.json', {'source_file':str(SOURCE),'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'scope':'new_medium50_single_abc_round','source':'direct_user_instruction','actor':'Codex','currency_cap':None,'stop_before':'Gate 2'})
    state = json.loads((OUTPUT / 'state.json').read_text()) if (OUTPUT / 'state.json').exists() else {}
    from app import main
    if not main.ai_service.live_enabled:
        raise RuntimeError('Live Provider unavailable')
    if stage == 'generate':
        from app.business_golden import medium_plan
        from app.governance import GENERATION_PROFILES
        base = json.loads((main.corpus.index_dir / 'coverage.json').read_text())
        plan = medium_plan(base, main.corpus.chunks(), {'name':'medium', **GENERATION_PROFILES['medium']})
        run_id = main.store.start_generation_run(main.ai_service.model, 'medium', coverage_plan=plan)
        identity = {'generation_run_id':run_id,'corpus':current,'plan_id':plan['plan_id']}
        state = {**identity,'status':'generating','pid':os.getpid()}
        save('state.json', state)
        auth = {'authorization_id':'OWNER-MEDIUM50-20261014-'+run_id,'source':'direct_user_instruction','generation_run_id':run_id,'delegated_by':'project_owner','actor':'Codex','expires_at':(datetime.now(timezone.utc)+timedelta(days=2)).isoformat(),'source_file':str(SOURCE),'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'corpus':current,'plan_id':plan['plan_id'],'profile':plan['profile'],'output_limits':REQUEST_LIMITS}
        # The existing server-owned verifier reads this exact scoped file.
        auth_path = main.store.database_path.parent / 'owner-delegated-review.json'
        if auth_path.exists(): shutil.copy2(auth_path, OUTPUT / 'previous-owner-delegation.json')
        auth_path.write_text(json.dumps(auth,ensure_ascii=False,indent=2)); auth_path.chmod(0o600)
        save('owner-delegation.json', auth)
        ledger = PaidRun(OUTPUT / 'provider-ledger.json', 1, {}, identity, identity_check=lambda:identity if manifest_identity(current_manifest())==current else None, output_limits=REQUEST_LIMITS)
        print('GENERATION_STARTED '+run_id,flush=True)
        with accounting_only(), controlled_run(ledger):
            main._run_mini_generation_work(run_id,main.store,main.ai_service,main.corpus)
        result = main.store.generation_run(run_id)
        save('generation-result.json', result)
        save('questions.json', [main.store.question(key) for key in result['question_ids']])
        state.update(status=result['status']); save('state.json', state)
        print('GENERATION_FINISHED '+result['status'],flush=True)
        return
    if current != state['corpus']:
        raise RuntimeError('Corpus identity changed')
    if stage == 'evaluate':
        # Reviews are independently authored by Codex after all actual PDF/quality checks.
        auth = json.loads((OUTPUT / 'owner-delegation.json').read_text())
        reviews = json.loads((OUTPUT / 'independent-reviews.json').read_text())
        if not state.get('snapshot'):
            result = main.store.review_owner_delegated_batch(state['generation_run_id'],auth['authorization_id'],reviews)
            save('gate1-result.json', result)
            state['snapshot'] = result; save('state.json',state)
        identity = {key:state[key] for key in ('generation_run_id','corpus','plan_id')}
        ledger = PaidRun.load_accounting(OUTPUT / 'provider-ledger.json',lambda:identity if manifest_identity(current_manifest())==current else None)
        from app.evaluation import EvaluationRunner
        from app.optimization import OptimizationAgent
        runner = EvaluationRunner(main.store, main.ai_service)
        with accounting_only(), controlled_run(ledger):
            if not state.get('baseline_id'):
                run_id, questions, config = runner.start_baseline(automatic=True)
                state['baseline_id']=run_id; save('state.json',state)
                result = runner.execute_baseline(run_id,questions,config)
                save('baseline-result.json',result)
            baseline = main.store.evaluation_run(state['baseline_id'])
            if baseline['status'] != 'completed':raise RuntimeError('Baseline incomplete')
            if not state.get('experiment_id'):
                result=OptimizationAgent(main.store,main.ai_service.provider).generate(baseline['id'])
                save('agent-result.json',result)
                state['experiment_id']=result['id']; save('state.json',state)
            experiment=main.store.experiment(state['experiment_id'])
            candidates=experiment['candidates']
            for candidate in sorted(candidates,key=lambda item:item['reasoning'].get('candidate_label','')):
                if candidate['status']=='evaluated':continue
                if candidate['status']!='generated':raise RuntimeError('Candidate requires checkpoint recovery')
                result=runner.run_candidate(candidate['id'],automatic=True)
                save('sandbox-'+candidate['reasoning']['candidate_label']+'.json',result)
                if result['status']!='evaluated':raise RuntimeError('Sandbox incomplete')
        state['status']='completed_before_gate2' if len(candidates)==3 else 'insufficient_candidates'
        save('state.json',state)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=('generate','evaluate'),required=True)
    args=parser.parse_args()
    try:execute(args.stage)
    except Exception as error:
        if OUTPUT.exists():save('execution-error.json',{'type':type(error).__name__,'error':str(error),'at':datetime.now(timezone.utc).isoformat()})
        raise
