"""Maintenance-only Q02 pointer/Golden transaction. No Provider or activation CLI.

The caller must stop API/other writers first and obtain separate switch authorization.
An incomplete journal always restores the old pair before service may start.
"""
import copy
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.corpus import CorpusStore
from app.corpus_management import CorpusManager, require_consistent_switch
from app.full_text import checksum, validate_bundle
from app.golden_v2 import validate_golden_candidate
from app.retrieval import VectorRetriever
from build_q02_stage1 import save
from repair_golden_index_offline import RUN, database_rows, encode


def sync_directory(path):
    descriptor = os.open(path, os.O_RDONLY)
    try: os.fsync(descriptor)
    finally: os.close(descriptor)


class LinkedSwitch:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.index, self.db = self.root/'index', self.root/'demo.db'
        self.journal = self.root/'q02-switch.json'

    def binding(self):
        with sqlite3.connect(self.db) as db:
            raw = db.execute('SELECT hard_validation_json FROM golden_generation_artifacts WHERE generation_run_id=?',(RUN,)).fetchone()
        return json.loads(raw[0])['corpus_fingerprint']

    def verify_pair(self, expected):
        identity = validate_bundle(self.index,require_full_text=True)['manifest']['knowledge_identity']
        if identity != expected or self.binding() != expected: raise ValueError('Corpus pointer/Golden binding inconsistent')
        state = json.loads((self.root/'corpus_state.json').read_text())
        if state['knowledge_identity'] != expected: raise ValueError('Corpus State differs')
        return identity

    def checkpoint(self, record):
        save(self.journal,record)
        sync_directory(self.root)

    def recover(self, *, fault=lambda point:None):
        if not self.journal.exists(): return 'no_pending_switch'
        record = json.loads(self.journal.read_text())
        if record['phase'] == 'completed':
            self.verify_pair(record['new_identity'])
            return 'completed_consistent'
        if record['phase'] == 'rolled_back':
            self.verify_pair(record['old_identity'])
            return 'old_consistent'
        backup = Path(record['backup'])
        if checksum(backup.read_bytes()) != record['backup_sha256']: raise ValueError('Recovery backup checksum differs')
        candidates = [Path(record['old_archived_path']),Path(record['old_initial_path'])]
        prior = next((p for p in candidates if (p/'manifest.json').exists() and
                      json.loads((p/'manifest.json').read_text())['knowledge_identity']==record['old_identity']),None)
        if prior is None: raise ValueError('Old bundle unavailable; service must remain stopped')
        validate_bundle(prior,require_full_text=True)
        # Caller is in maintenance mode: no concurrent writer can lose newer work.
        with sqlite3.connect(backup.as_uri()+'?mode=ro',uri=True) as old,sqlite3.connect(self.db) as current:
            old.backup(current)
            if database_rows(current) != database_rows(old): raise ValueError('Database restoration differs')
        fault('database_restored')
        if self.index.resolve() != prior.resolve() or not self.index.exists():
            pointer = self.root/'q02-recovery.link'
            pointer.unlink(missing_ok=True);pointer.symlink_to(prior,target_is_directory=True)
            os.replace(pointer,self.index)
            sync_directory(self.root)
        fault('pointer_restored')
        state = self.root/'corpus_state.json'
        if record['old_state'] is None: state.unlink(missing_ok=True)
        else:
            temporary = self.root/'q02-state.restore'
            with temporary.open('w') as stream:
                stream.write(record['old_state']);stream.flush();os.fsync(stream.fileno())
            os.replace(temporary,state)
        sync_directory(self.root)
        fault('state_restored')
        # Real corpora always have State; restored absence is retained as absence.
        if self.binding()!=record['old_identity'] or validate_bundle(self.index,require_full_text=True)['manifest']['knowledge_identity']!=record['old_identity']:
            raise ValueError('Recovered pointer/Golden binding differs')
        record['phase']='rolled_back';self.checkpoint(record)
        return 'rolled_back'

    def switch(self, staging, preview, *, operation='Q02-CONTROLLED', fault=lambda point:None):
        if self.journal.exists(): raise ValueError('Existing switch journal requires recovery; no implicit retry')
        staging=Path(staging).resolve()
        old=validate_bundle(self.index,require_full_text=True)['manifest']['knowledge_identity']
        self.verify_pair(old)
        new_bundle=validate_bundle(staging,require_full_text=True)
        new=new_bundle['manifest']['knowledge_identity']
        if self.binding()!=old or preview['corpus_fingerprint']!=new or preview['plan']['corpus_fingerprint']!=new:
            raise ValueError('Switch input identity differs')
        with sqlite3.connect(self.db) as db:
            for table in ['evaluation_runs','golden_generation_runs','agent_traces','candidate_revision_runs']:
                if db.execute(f"SELECT 1 FROM {table} WHERE status IN ('running','queued','coverage','generating','validation','probing','qc')").fetchone():
                    raise ValueError('Active task; cannot switch')
            ids=json.loads(db.execute('SELECT question_ids_json FROM golden_generation_runs WHERE id=?',(RUN,)).fetchone()[0])
            if len(ids)!=50 or ids!=[q['id'] for q in preview['questions']]: raise ValueError('Working set IDs differ')
            allowed={'plan_id','validation','evidence_locations','coverage_match','pdf_supplement'}
            for q in preview['questions']:
                if q.get('plan_id')!=preview['plan']['plan_id']: raise ValueError('Question Plan binding differs')
                row=db.execute('SELECT raw_json,stage,review_status,probe_status,qc_status FROM questions WHERE id=?',(q['id'],)).fetchone()
                if tuple(row[1:])!=('candidate','human_review_pending','probe_pending','qc_pending'): raise ValueError('Question qualification changed')
                original=json.loads(row[0])
                if {k:v for k,v in original.items() if k not in allowed}!={k:v for k,v in q.items() if k not in allowed}: raise ValueError('Question content differs')
                validated=validate_golden_candidate(q,new_bundle['chunks'],preview['plan'],{'slot_id':q['coverage_slot'],'corpus_fingerprint':new,'seen':[a['question'] for a in preview['questions'] if a is not q]})
                if not validated['valid']:
                    raise ValueError('New hard validation failed')
            backup=self.root/'q02-before.db'
            with sqlite3.connect(backup) as copy_db:db.backup(copy_db)
        initial=self.index.resolve()
        archived=initial if self.index.is_symlink() else self.root/'index_versions'/(operation+'-previous')
        record={'phase':'prepared','old_identity':old,'new_identity':new,'old_initial_path':str(initial),
                'old_archived_path':str(archived),'backup':str(backup),'backup_sha256':checksum(backup.read_bytes()),
                'old_state':(self.root/'corpus_state.json').read_text() if (self.root/'corpus_state.json').exists() else None,
                'new_plan_id':preview['plan']['plan_id']}
        self.checkpoint(record);fault('prepared')
        manager=CorpusManager(VectorRetriever(CorpusStore(self.index)),index_dir=self.index)
        def finish():
            sync_directory(self.root);sync_directory(self.root/'index_versions')
            fault('pointer_swapped')
            with sqlite3.connect(self.db) as db:
                db.execute('BEGIN IMMEDIATE')
                audit=json.loads(db.execute('SELECT hard_validation_json FROM golden_generation_artifacts WHERE generation_run_id=?',(RUN,)).fetchone()[0])
                if audit['corpus_fingerprint']!=old: raise ValueError('Golden binding changed before commit')
                for q in preview['questions']:
                    db.execute('UPDATE questions SET raw_json=? WHERE id=?',(encode(q),q['id']))
                audit.setdefault('corpus_binding_history',[]).append({'previous_identity':old,'previous_plan_id':audit['frozen_plan']['plan_id'],'backup_sha256':record['backup_sha256']})
                audit.update(corpus_fingerprint=new,frozen_plan=copy.deepcopy(preview['plan']),status='passed',
                             hard_validation={'status':'passed','blocked_questions':{}},quality_not_run=True)
                audit.pop('error',None);audit.pop('failed_stage',None)
                audit['progress']={**audit.get('progress',{}),'stage':'completed'}
                db.execute('UPDATE golden_generation_artifacts SET coverage_plan_json=?,hard_validation_json=? WHERE generation_run_id=?',(encode(preview['plan']['slots']),encode(audit),RUN))
                db.execute("UPDATE golden_generation_runs SET status='completed' WHERE id=?",(RUN,))
                fault('db_written')
                db.commit()
            fault('db_committed')
            save(self.root/'corpus_state.json',{**json.loads(record['old_state']),
                 'changed_at':datetime.now(timezone.utc).isoformat(),'fingerprint':new['sources'],'knowledge_identity':new})
            sync_directory(self.root);fault('state_written')
        try:
            manager.activate_bundle(staging,operation,after_activate=finish,expected_active=initial)
            self.verify_pair(new);fault('before_complete')
            record['phase']='completed';self.checkpoint(record)
        except BaseException:
            self.recover()
            raise
        return new

    def startup_check(self):
        require_consistent_switch(self.index,self.db)


if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser(description='Read-only Q02 startup gate; never switches or recovers automatically')
    parser.add_argument('--check-startup',action='store_true',required=True)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]/'backend/data')
    args=parser.parse_args()
    LinkedSwitch(args.root).startup_check()
