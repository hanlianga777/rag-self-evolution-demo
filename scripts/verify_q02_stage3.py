"""Offline real-asset copies: linked transaction, SQL faults and actual SIGKILL recovery.

Default runs verification only. Every mutable target is a temporary copy.
No import of app.main, no credentials, no Provider/network calls.
"""
import argparse
import json
import os
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.full_text import checksum,validate_bundle
from app.golden_v2 import validate_golden_candidate
from app.knowledge_pipeline import index_for_config
from build_q02_stage1 import save
from q02_switch_transaction import LinkedSwitch
from repair_golden_index_offline import RUN,database_rows

STAGE1=ROOT/'output/playwright/golden-q02-stage1-20261012'


def worker(root,case,action):
    switch=LinkedSwitch(root)
    def fault(point):
        if point==case:
            print('READY '+point,flush=True)
            signal.pause()
        if case=='pointer_exception' and point=='pointer_swapped':
            raise RuntimeError('injected interruption')
    if action=='recover':
        switch.recover(fault=fault)
        return
    preview=json.loads((STAGE1/'working-set-preview.json').read_text())
    if case=='sql_failure':
        with sqlite3.connect(switch.db) as db:
            db.execute("CREATE TRIGGER stage3_fault BEFORE UPDATE ON golden_generation_artifacts BEGIN SELECT RAISE(ABORT,'injected database failure'); END")
    replace=os.replace
    def interrupted_replace(source,target):
        replace(source,target)
        if case=='old_archived' and Path(source)==switch.index and str(target).endswith('-previous'):
            fault('old_archived')
    with patch('app.corpus_management.os.replace',interrupted_replace):
        switch.switch(Path(root)/'new',preview,fault=fault)


def subprocess_worker(root,case,action='switch'):
    env={**os.environ,'PYTHONPATH':str(ROOT/'backend'),'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1',
         'RAG_DEMO_DB_PATH':str(root/'demo.db'),'RAG_DEMO_INDEX_DIR':str(root/'index'),
         'RAG_DEMO_ENV_PATH':str(root/'absent.env')}
    command=[sys.executable,str(Path(__file__).resolve()),'--worker',str(root),'--case',case,'--action',action]
    killed=case in {'prepared','old_archived','pointer_swapped','db_written','db_committed','state_written','before_complete','database_restored'}
    with subprocess.Popen(command,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) as child:
        if killed:
            # Read only the explicit checkpoint; parent kills the real process, not an exception.
            line=child.stdout.readline()
            if line.strip()!='READY '+case:
                _,error=child.communicate(timeout=60)
                raise AssertionError('Worker did not reach checkpoint: '+line+error)
            child.kill()
        stdout,stderr=child.communicate(timeout=60)
        expected=-signal.SIGKILL if killed else (1 if case in {'pointer_exception','sql_failure'} else 0)
        if child.returncode!=expected: raise AssertionError(f'{case} unexpected exit {child.returncode}: {stderr}')
        return child.returncode


def verify(output):
    output.mkdir(parents=True,exist_ok=False)
    live_db=ROOT/'backend/data/demo.db';active=ROOT/'backend/data/index'
    stage_report=json.loads((STAGE1/'report.json').read_text());new=Path(stage_report['staging'])
    old_bundle=validate_bundle(active,require_full_text=True);new_bundle=validate_bundle(new,require_full_text=True)
    old=old_bundle['manifest']['knowledge_identity'];new_id=new_bundle['manifest']['knowledge_identity']
    if old['corpus_snapshot_id']!='CORPUS-c6bbb042130820be7a1a' or new_id['corpus_snapshot_id']!='CORPUS-38c90d5628b68c76d53e':raise ValueError('Expected source identity differs')
    with sqlite3.connect(live_db.as_uri()+'?mode=ro',uri=True) as db,sqlite3.connect(output/'before.db') as backup:
        db.backup(backup);before=database_rows(db)
        protected_ids=json.loads(db.execute('SELECT question_ids_json FROM golden_generation_runs WHERE id=?',(RUN,)).fetchone()[0])
        protected_rowids={row[0] for row in db.execute('SELECT rowid FROM questions WHERE id IN ('+','.join('?' for _ in protected_ids)+')',protected_ids)}
        run_rowid=db.execute('SELECT rowid FROM golden_generation_runs WHERE id=?',(RUN,)).fetchone()[0]
        artifact_rowid=db.execute('SELECT rowid FROM golden_generation_artifacts WHERE generation_run_id=?',(RUN,)).fetchone()[0]
        historical_configs=[(key,json.loads(value)) for key,value in db.execute("SELECT id,config_json FROM evaluation_runs WHERE id='EVAL-20261012024220100135'")]
        historical_configs += [(key,json.loads(value)) for key,value in db.execute('SELECT id,config_json FROM production_versions')]
    assets={str(p.relative_to(ROOT)):checksum(p.read_bytes()) for folder in [active,ROOT/'backend/data/index_versions',ROOT/'backend/documents'] for p in folder.rglob('*') if p.is_file()}
    provider_ledger=checksum((STAGE1/'provider-calls.json').read_bytes())
    allowed={'questions':protected_rowids,'golden_generation_runs':{run_rowid},'golden_generation_artifacts':{artifact_rowid}}
    results=[]
    cases=['success','pointer_exception','sql_failure','prepared','old_archived','pointer_swapped','db_written','db_committed','state_written','before_complete','recovery_interrupted']
    for case in cases:
        with tempfile.TemporaryDirectory(prefix='q02-stage3-') as directory:
            root=Path(directory)
            shutil.copytree(active,root/'index');shutil.copytree(new,root/'new')
            shutil.copyfile(output/'before.db',root/'demo.db')
            shutil.copyfile(ROOT/'backend/data/corpus_state.json',root/'corpus_state.json')
            shutil.copyfile(ROOT/'backend/data/legacy_index.json',root/'legacy_index.json')
            switch=LinkedSwitch(root)
            actual_case='db_committed' if case=='recovery_interrupted' else case
            code=subprocess_worker(root,actual_case)
            gate_blocked=False
            if case not in {'success','pointer_exception','sql_failure'}:
                try:switch.startup_check()
                except ValueError:gate_blocked=True
                else:raise AssertionError('Incomplete journal did not block startup')
            if case=='recovery_interrupted':
                subprocess_worker(root,'database_restored','recover')
            if case!='success':subprocess_worker(root,'none','recover')
            switch.startup_check()
            expected=new_id if case=='success' else old
            switch.verify_pair(expected)
            # Recovery is idempotent and a completed operation is never retried.
            assert switch.recover() in {'old_consistent','completed_consistent'}
            with sqlite3.connect(root/'demo.db') as db:
                after=database_rows(db)
                assert before.keys()==after.keys()
                for table in before:
                    assert before[table].keys()==after[table].keys()
                    for key,value in before[table].items():
                        if value!=after[table][key]:assert case=='success' and key in allowed.get(table,set()),(case,table,key)
                if case!='success':assert before==after
                questions=[json.loads(db.execute('SELECT raw_json FROM questions WHERE id=?',(key,)).fetchone()[0]) for key in protected_ids]
                audit=json.loads(db.execute('SELECT hard_validation_json FROM golden_generation_artifacts WHERE generation_run_id=?',(RUN,)).fetchone()[0])
            hard=None
            if case=='success':
                data=validate_bundle(root/'index',require_full_text=True)
                checks=[validate_golden_candidate(q,data['chunks'],audit['frozen_plan'],{'slot_id':q['coverage_slot'],'corpus_fingerprint':new_id,'seen':[a['question'] for a in questions if a is not q]}) for q in questions]
                assert all(v['valid'] for v in checks);hard='50/50'
                for key,config in historical_configs:
                    path=index_for_config(root/'index',config)
                    resolved=validate_bundle(path,require_full_text=False)
                    if config.get('knowledge_identity'):assert resolved['manifest']['knowledge_identity']==config['knowledge_identity']
                # Current Baseline becomes unavailable across Corpus identities; history is not migrated.
                with sqlite3.connect(root/'demo.db') as db:
                    snapshot=json.loads(db.execute("SELECT snapshot_json FROM dataset_versions WHERE status='approved' ORDER BY created_at DESC,rowid DESC LIMIT 1").fetchone()[0])
                assert snapshot['corpus_fingerprint']!=new_id
            journal=json.loads(switch.journal.read_text())
            result={'case':case,'passed':True,'worker_exit':code,'startup_blocked_when_incomplete':gate_blocked,
                    'pointer_and_golden_corpus':expected['corpus_snapshot_id'],'journal_phase':journal['phase'],
                    'history_unchanged':True,'old_rows_fully_restored':case!='success','hard_validation':hard}
            save(output/(case+'.json'),{'result':result,'journal':journal})
            results.append(result)
            print(case+' passed',flush=True)
    with sqlite3.connect(live_db.as_uri()+'?mode=ro',uri=True) as db:assert database_rows(db)==before
    assert all(checksum((ROOT/name).read_bytes())==value for name,value in assets.items())
    assert checksum((STAGE1/'provider-calls.json').read_bytes())==provider_ledger
    assert json.loads((active/'manifest.json').read_text())['knowledge_identity']==old
    report={'status':'passed','cases':results,'case_count':len(results),'paid_requests':0,'all_formal_database_rows_unchanged':True,
            'protected_tables':len(before),'prior_asset_files_unchanged':len(assets),'stage1_provider_ledger_unchanged':True,
            'formal_corpus_unchanged':True,'new_identity':new_id,'current_working_set':RUN,
            'formal_switch_authorized':False,'historical_baseline_requires_new_identity_workflow':True}
    save(output/'report.json',report);save(output/'protected-assets.json',assets)
    print(json.dumps(report,ensure_ascii=False,indent=2))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--worker',type=Path)
    parser.add_argument('--case',default='success')
    parser.add_argument('--action',default='switch')
    args=parser.parse_args()
    def denied(*args,**kwargs):raise RuntimeError('Stage3 verification forbids all network calls')
    socket.socket.connect=denied
    if args.worker:
        if not str(args.worker.resolve()).startswith('/private/var/folders/') and not str(args.worker.resolve()).startswith('/private/tmp/'):
            raise ValueError('Worker writes only to temporary verification copies')
        worker(args.worker,args.case,args.action)
    else:
        if args.output is None:parser.error('--output is required')
        verify(args.output.resolve())


if __name__=='__main__':main()
