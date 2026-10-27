"""Explicit owner-authorized serial quality run; no automatic retry or approval."""
import argparse
import hashlib
import json
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
RUN = 'GGEN-20261012120721324996'
CORPUS = 'CORPUS-38c90d5628b68c76d53e'
PLAN = 'PLAN-89801791985fdfe13f1421cf'


def identity():
    from app.corpus import current_manifest, manifest_identity
    with sqlite3.connect((ROOT/'backend/data/demo.db').as_uri()+'?mode=ro',uri=True) as db:
        artifact = json.loads(db.execute('SELECT hard_validation_json FROM golden_generation_artifacts WHERE generation_run_id=?',(RUN,)).fetchone()[0])
    return {'knowledge':manifest_identity(current_manifest()),'run':RUN,'plan':artifact['frozen_plan']['plan_id']}


def quality(authorization):
    from app.paid_run import PaidRun, REQUEST_LIMITS
    current = identity()
    if current['knowledge']['corpus_snapshot_id']!=CORPUS or current['plan']!=PLAN:
        raise RuntimeError('Owner scope identity changed')
    text = authorization.read_text()
    if RUN not in text or '所有者委托' not in text:
        raise ValueError('Explicit owner authorization attachment required')
    output = ROOT/'output/playwright/golden-delegated-20261012'
    output.mkdir(exist_ok=True)
    prices = {'deepseek-v4-flash':{'provider':'DeepSeek','input':2.1,'output':8.4,'max_output':32768},
              'text-embedding-v4':{'provider':'Alibaba','input':.5,'output':0,'max_output':0},
              'qwen3-rerank':{'provider':'Alibaba','input':.5,'output':0,'max_output':0}}
    run = PaidRun(output/'paid-calls.json',None,prices,current,identity_check=identity,output_limits=REQUEST_LIMITS)
    (output/'owner-authorization.json').write_text(json.dumps({'source':'direct_user_instruction','attachment_sha256':hashlib.sha256(authorization.read_bytes()).hexdigest(),
        'delegated_by':'project_owner','review_actor_type':'ai_agent','review_actor':'Codex','generation_run':RUN,
        'output_limits':REQUEST_LIMITS,'price_basis':'2026-10-12 official peak rates, CNY conversion 6.7313 with planning buffer; not account debit'},ensure_ascii=False,indent=2))
    from app import main
    if not main.ai_service.live_enabled: raise RuntimeError('Live Provider required')
    main.store.claim_quality_resume(RUN,current['knowledge'])
    print('QUALITY_STARTED '+RUN,flush=True)
    main._run_mini_generation(RUN,main.store,main.ai_service,main.corpus,resume_quality=True,paid_run=run)
    result = main.store.generation_run(RUN)
    (output/'quality-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print('QUALITY_FINISHED '+result['status'],flush=True)
    if result['status']!='completed': raise RuntimeError('Quality execution incomplete; no automatic retry')


def next_step(stage, changes_file=None, identifier=None):
    from app.paid_run import PaidRun,controlled_run
    output=ROOT/'output/playwright/golden-delegated-20261012'
    run=PaidRun.next_stage(output/'paid-calls.json',stage,identity)
    from app import main
    from fastapi.testclient import TestClient
    client=TestClient(main.app)
    def post(path,payload=None):
        response=client.post(path,json=payload,headers={'Origin':'http://127.0.0.1:5174'})
        (output/f'{stage}-last-api.json').write_text(response.text)
        if response.status_code>=400: raise RuntimeError(f'Formal API {path}: {response.status_code} {response.text}')
        return response.json()
    def wait_revision(key):
        deadline=time.monotonic()+1800
        while time.monotonic()<deadline:
            try: revision=main.store.revision_run(key)
            except sqlite3.OperationalError as error:
                if 'locked' not in str(error): raise
                time.sleep(1)
                continue
            if revision['status'] in {'preview_ready','completed','failed_quality','failed'}: return revision
            time.sleep(3)
        raise RuntimeError('Revision exceeded bounded wait')
    with controlled_run(run):
        if stage in {'repair-1','repair-2','repair-1-resume'}:
            changes=json.loads(changes_file.read_text())
            records=[]
            for key,change in changes.get('changes',{}).items():
                if stage=='repair-1-resume' and any(r['status']=='completed' and key in r['question_ids'] and r.get('changes',{}).get(key)==change['fields'] for r in main.store.revision_runs(RUN)):
                    continue
                created=post(f'/api/governance/questions/{key}/revision',{'mode':'manual_edit','reason':change['reason'],
                    'paired':False,'changes':{key:change['fields']},'tags':['其他'],'actor':'Codex'})
                prepared=wait_revision(created['id'])
                (output/f'{stage}-{key}-preview.json').write_text(json.dumps(prepared,ensure_ascii=False,indent=2))
                if prepared['status']!='preview_ready' or not prepared['validation']['passed']: raise RuntimeError('Controlled revision validation failed')
                post(f'/api/governance/revisions/{created["id"]}/apply')
                finished=wait_revision(created['id'])
                records.append(finished)
                if finished['status']!='completed' and finished.get('error'): raise RuntimeError('Controlled revision execution failed')
            peers=[main.store.question(key) for key in main.store.generation_run(RUN,qualification=False)['question_ids']]
            for key in changes.get('audit_only',[]):
                candidate=main.store.question(key)
                audited=main.ai_service.business_quality_audit(candidate,[p['question'] for p in peers if p['id']!=key])
                main.store.save_quality_audit(key,audited)
            (output/f'{stage}-results.json').write_text(json.dumps(records,ensure_ascii=False,indent=2))
        elif stage=='baseline':
            started=post('/api/evaluations/run',{'fresh':True})
            wait_evaluation(main,output,stage,started['id'])
        elif stage.startswith('agent-'):
            result=post(f'/api/experiments/{identifier}/continue' if identifier else '/api/experiments/run')
            (output/f'{stage}-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
        elif stage.startswith('candidate-'):
            started=post(f'/api/candidates/{identifier}/run')
            wait_evaluation(main,output,stage,started['id'])


def wait_evaluation(main,output,stage,key):
    deadline=time.monotonic()+10800
    print('EVALUATION_STARTED '+key,flush=True)
    while time.monotonic()<deadline:
        saved=main.store.evaluation_run(key)
        if saved['status'] in {'completed','partial','failed'}:
            (output/f'{stage}-result.json').write_text(json.dumps(saved,ensure_ascii=False,indent=2))
            print('EVALUATION_FINISHED '+saved['status'],flush=True)
            if saved['status']!='completed': raise RuntimeError('Evaluation incomplete; no automatic retry')
            return
        time.sleep(5)
    raise RuntimeError('Evaluation exceeded bounded wait')


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--authorization',type=Path)
    parser.add_argument('--stage',default='quality',choices=['quality','repair-1','repair-1-resume','repair-2','baseline','agent-1','agent-2',
        'candidate-A1','candidate-B1','candidate-C1','candidate-A2','candidate-B2','candidate-C2'])
    parser.add_argument('--changes',type=Path)
    parser.add_argument('--identifier')
    args = parser.parse_args()
    if args.stage=='quality': quality(args.authorization.resolve())
    else: next_step(args.stage,args.changes,args.identifier)
