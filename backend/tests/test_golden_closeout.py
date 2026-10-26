"""Golden workflow checks; every Provider response and approval is an isolated fixture."""
from contextlib import closing
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from api_fixture import main
from app.governance import GovernanceStore
from app.golden_v2 import validate_golden_candidate

ROOT = Path(__file__).resolve().parents[2]


def semantic_reply(item, chunks, score=90, priority='P2'):
    by_id = {c['chunk_id']: c for c in chunks}; req = item['raw']['business_requirements']
    checks = []
    for c in req['required_checks'] + req['conditional_checks']:
        refs = c['source_chunk_ids']
        checks.append({'id': c['id'], 'applicable': True, 'met': True, 'reason': 'offline fixture',
                       'support': [{'chunk_id': refs[0], 'quote': by_id[refs[0]]['chunk_text']}] if refs else []})
    return {'score': score, 'priority': priority, 'issues': [], 'reason': 'offline fixture, not Provider acceptance',
            'ablation_valid': True, 'ablation_reason':'offline fixture', 'content_review': {'checks': checks, 'scope_valid': True, 'safety_valid': True, 'prohibited_clear': True, 'disputes': []}}


class CloseoutTests(unittest.TestCase):
    def setUp(self):
        if not (ROOT/'backend/data/demo.db').is_file() or not (ROOT/'backend/data/index/chunks.json').is_file():
            self.skipTest('requires local current 50-question database and Corpus for read-only copy')
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.store = GovernanceStore(Path(self.tmp.name) / 'fixture.db')
        # Read current records, copy only Golden-owned rows to the disposable database.
        with closing(sqlite3.connect((ROOT/'backend/data/demo.db').resolve().as_uri()+'?mode=ro', uri=True)) as source, self.store.connection() as target:
            for table in ('questions','dataset_versions','golden_generation_runs','golden_generation_artifacts','review_events','approvals','probe_results','qc_results','question_quality_audits','candidate_revision_runs'):
                target.execute('DELETE FROM '+table)
            for table in ('questions','golden_generation_runs','golden_generation_artifacts'):
                rows = source.execute('SELECT * FROM '+table).fetchall()
                columns=[r[1] for r in source.execute('PRAGMA table_info('+table+')')]
                target.executemany('INSERT INTO '+table+' ('+','.join(columns)+') VALUES ('+','.join('?' for _ in rows[0])+')', rows)
        self.chunks = json.loads((ROOT/'backend/data/index/chunks.json').read_text())
        self.manifest = json.loads((ROOT/'backend/data/index/manifest.json').read_text())
        self.run_id = self.store.questions()[0]['raw']['generation_run_id']
        for name in ('app.governance.current_manifest','app.ai_service.current_manifest','app.corpus.current_manifest'):
            p=patch(name,return_value=self.manifest);p.start();self.addCleanup(p.stop)
        p=patch('app.corpus.CorpusStore.chunks',return_value=self.chunks);p.start();self.addCleanup(p.stop)
        self.calls = []
        owner = self
        class Service:
            model='offline-fixture'
            def __init__(self):
                class Retriever:
                    def search(self,question,limit):return owner.hits(question)
                    def full_text_probe(self,question):return {'coverage':{'status':'complete'},'matches':[]}
                self.retriever = Retriever()
            def answerability_check(self,*a,**kw):return {'answerable':False,'reason':'offline negative boundary'}
            def negative_subtype_check(self,q,h,s):return {'matched':True,'detected_subtype':s['negative_subtype'],'reason':'offline'}
            def business_quality_audit(self,item,peers):
                from app.business_golden import CHECKS,QUALITY_CONTRACT
                owner.calls.append(('audit',item['id']))
                return {'checks':dict.fromkeys(CHECKS,True),'reason':'fixture','audit_version':QUALITY_CONTRACT}
            def quality_check(self,item):
                owner.calls.append(('qc',item['id'])); return semantic_reply(item,owner.chunks)
        self.service = Service(); self.corpus = SimpleNamespace(chunks=lambda:self.chunks)

    def hits(self, question):
        q=next(q for q in self.store.questions() if q['question']==question)
        ids={i for e in q['evidence'] for i in e['source_chunk_ids']}
        return [{**c,'content':c['chunk_text'],'score':1} for c in self.chunks if c['chunk_id'] in ids]

    def probe(self, key):
        return self.store.run_probe(key,self.service.retriever,self.chunks,self.service.answerability_check,subtype_judge=self.service.negative_subtype_check)

    def test_all_50_prechecks_allow_paraphrase_without_final_review(self):
        for item in self.store.questions():
            result=validate_golden_candidate({**item['raw'],**item},self.chunks)
            self.assertTrue(result['valid'], (item['id'],result['blocking_errors']))
            self.assertFalse(result['freeze_valid'])

    def test_84_85_p0_and_p1_are_consistent(self):
        key=self.store.questions()[0]['id'];self.assertTrue(self.probe(key)['passed'])
        for score,priority,expected in [(84,'P2','qc_failed'),(85,'P2','qc_passed'),(95,'P0','qc_failed'),(90,'P1','qc_passed')]:
            reply=semantic_reply(self.store.question(key),self.chunks,score,priority)
            saved=self.store.record_qc(key,reply,'passed')
            self.assertEqual(saved['status'],expected)
            row=self.store.candidate_rows([key])[0]
            if expected=='qc_failed' or priority=='P1':self.assertEqual(row['qualification_status'],'needs_human_review')
        with self.assertRaises(ValueError):self.store.review_generation_batch([key],'fixture',confirmed_manual_review=True)

    def test_50_batch_quality_recovers_then_freezes_only_with_explicit_gate(self):
        self.store.update_quality_rerun(self.run_id,{'status':'running'},start=True)
        main._run_quality_rerun(self.run_id,[q['id'] for q in self.store.questions()],self.store,self.service,self.corpus)
        run=self.store.generation_run(self.run_id)
        self.assertEqual(run['artifacts']['hard_validation']['quality_rerun']['status'],'completed',run['artifacts']['hard_validation']['quality_rerun'])
        self.assertEqual(run['human_gate']['machine_qualified'],50)
        self.assertEqual(self.store.dataset_snapshots(),[])
        before=list(self.calls)
        self.store.update_quality_rerun(self.run_id,{'status':'running'},start=True)
        main._run_quality_rerun(self.run_id,run['question_ids'],self.store,self.service,self.corpus)
        self.assertEqual(self.calls,before,'successful paid phases repeated')
        with self.assertRaises(ValueError):self.store.review_generation_batch(run['question_ids'],'fixture')
        result=self.store.review_generation_batch(run['question_ids'],'fixture-human',confirmed_manual_review=True)
        snapshot=result['snapshot']
        self.assertEqual(set(snapshot['question_ids']),set(run['question_ids']))
        self.assertEqual({q['id']:q['reference_answer'] for q in snapshot['questions']},{q['id']:q['reference_answer'] for q in self.store.questions()})
        self.assertEqual(len(self.store.dataset_snapshots()),1)
        from app.evaluation import EvaluationRunner
        selected,items,config,judge=EvaluationRunner(self.store,SimpleNamespace(model='offline-fixture')).baseline_inputs()
        self.assertEqual(selected['id'],snapshot['id']);self.assertEqual(len(items),50)

    def test_failed_probe_blocks_qc_and_old_quality_identity_is_rejected(self):
        key=self.store.questions()[0]['id']
        self.store.record_probe_result(key,{'question_quality':0,'golden_answer_quality':0,'evidence_support':0,'evidence_direct_failure':True})
        with self.assertRaises(ValueError):self.store.record_qc(key,semantic_reply(self.store.question(key),self.chunks),'passed')
        self.assertTrue(self.probe(key)['passed']);_,identity=self.store.capture_quality(key,qc=True)
        with self.store.connection() as c:
            q=self.store.question(key);raw=q['raw'];raw['business_requirements']['prohibited'].append('changed fixture constraint')
            c.execute('UPDATE questions SET raw_json=? WHERE id=?',(json.dumps(raw),key))
        with self.assertRaisesRegex(ValueError,'过期'):self.store.record_qc(key,semantic_reply(self.store.question(key),self.chunks),'passed',execution=identity)

    def test_unknown_checkpoint_blocks_paid_resume(self):
        with self.store.connection() as c:
            row=c.execute('SELECT hard_validation_json FROM golden_generation_artifacts WHERE generation_run_id=?',(self.run_id,)).fetchone();raw=json.loads(row[0])
            raw['quality_rerun']={'status':'failed','checkpoints':{'q':{'inflight':'qc','attempts':[]}}}
            c.execute('UPDATE golden_generation_artifacts SET hard_validation_json=? WHERE generation_run_id=?',(json.dumps(raw),self.run_id))
        with self.assertRaises(ValueError):self.store.update_quality_rerun(self.run_id,{'status':'running'},start=True)

    def complete_quality(self):
        self.store.update_quality_rerun(self.run_id,{'status':'running'},start=True)
        main._run_quality_rerun(self.run_id,[q['id'] for q in self.store.questions()],self.store,self.service,self.corpus)

    def test_p1_safety_dispute_requires_current_explicit_resolution(self):
        self.complete_quality();key=self.store.questions()[0]['id']
        reply=semantic_reply(self.store.question(key),self.chunks,90,'P1')
        reply['content_review']['safety_valid']=False
        reply['content_review']['disputes']=['fixture safety ambiguity']
        self.store.record_qc(key,reply,'passed')
        self.assertEqual(self.store.candidate_rows([key])[0]['qualification_status'],'needs_human_review')
        with self.assertRaisesRegex(ValueError,'复核结论'):self.store.review_question(key,'approved','fixture')
        self.store.review_question(key,'approved','fixture-human',reason='fixture explicit scope and safety disposition')
        self.assertEqual(self.store.candidate_rows([key])[0]['qualification_status'],'human_approved')
        self.store.record_qc(key,semantic_reply(self.store.question(key),self.chunks,95,'P0'),'passed')
        self.assertEqual(self.store.candidate_rows([key])[0]['qualification_status'],'needs_human_review')
        with self.assertRaises(ValueError):self.store.review_question(key,'approved','fixture',accept_qc_p0=True,reason='cannot waive')
        with self.assertRaises(ValueError):self.store.create_dataset_snapshot([self.store.question(key)],self.run_id)

    def test_forged_qc_citations_and_missing_checks_cannot_qualify(self):
        key=self.store.questions()[0]['id'];self.probe(key)
        for mutate in (lambda r:r['content_review']['checks'].clear(),
                       lambda r:r['content_review']['checks'][0]['support'][0].update(quote='fabricated citation')):
            reply=semantic_reply(self.store.question(key),self.chunks);mutate(reply)
            with self.assertRaises(ValueError):self.store.record_qc(key,reply,'passed')
        self.assertEqual(self.store.qc_history(key),[])

    def test_partial_quality_failure_resumes_without_losing_success(self):
        original=self.service.quality_check;failed_key=self.store.questions()[1]['id']
        def fail(item):
            if item['id']==failed_key:raise ValueError('fixture known failure')
            return original(item)
        self.service.quality_check=fail;self.complete_quality()
        self.assertEqual(self.store.generation_run(self.run_id,qualification=False)['artifacts']['hard_validation']['quality_rerun']['status'],'failed')
        success=self.store.questions()[0]['id'];self.assertEqual(len(self.store.qc_history(success)),1)
        self.service.quality_check=original;self.complete_quality()
        self.assertEqual(len(self.store.qc_history(success)),1)
        self.assertEqual(self.calls.count(('qc',success)),1)
        self.assertEqual(self.store.generation_run(self.run_id)['human_gate']['machine_qualified'],50)

    def test_unapproved_snapshot_cannot_be_injected(self):
        with self.assertRaises(ValueError):self.store.create_dataset_snapshot(self.store.questions(),self.run_id)
        self.assertEqual(self.store.dataset_snapshots(),[])

    def test_qc_request_includes_persisted_business_rules(self):
        from app.ai_service import AiService
        item=self.store.questions()[0];sent=[]
        def complete(system,user,**kwargs):
            sent.append((system,json.loads(user)));return json.dumps(semantic_reply(item,self.chunks))
        service=AiService(self.store,self.corpus,SimpleNamespace(complete=complete,settings=SimpleNamespace(configured=True,model='offline-fixture')),False)
        result=service._quality_check(item)
        self.assertEqual(result['content_validation']['status'],'supported')
        self.assertEqual(sent[0][1]['business_requirements'],item['raw']['business_requirements'])
        self.assertIn('auxiliary_information遗漏不作失败',sent[0][0])

    def test_known_invalid_rpc_can_retry_but_successful_rpc_is_reused(self):
        from app.evaluation_stage import checkpoint_request
        from app.golden_v2 import validate_qc_content
        requests={};failed_key=self.store.questions()[1]['id']
        def qc(item):
            def remote():
                key=item['id'];requests[key]=requests.get(key,0)+1
                reply=semantic_reply(item,self.chunks)
                if key==failed_key and requests[key]==1:reply['content_review']['checks']=[]
                return reply
            reply=checkpoint_request('fixture','fixture','qc',{'id':item['id']},remote)
            validate_qc_content(item,reply,self.chunks)
            return reply
        self.service.quality_check=qc;self.complete_quality()
        self.assertEqual(self.store.generation_run(self.run_id,qualification=False)['artifacts']['hard_validation']['quality_rerun']['status'],'failed')
        self.complete_quality()
        self.assertEqual(requests[failed_key],2)
        self.assertEqual(requests[self.store.questions()[0]['id']],1)
        self.assertEqual(self.store.generation_run(self.run_id)['human_gate']['machine_qualified'],50)
        cp=self.store.generation_run(self.run_id,qualification=False)['artifacts']['hard_validation']['quality_rerun']['checkpoints'][failed_key]
        self.assertTrue(cp['manual_resume_history'][0]['provider_requests'])

    def test_documented_content_issue_cannot_be_closed_by_high_qc(self):
        self.complete_quality();item=self.store.questions()[0];key=item['id']
        with self.store.connection() as c:
            c.execute("INSERT INTO review_events(question_id,gate,decision,actor,created_at,metadata_json) VALUES (?,?,?,?,?,?)",
                (key,'dataset','content_review_required','fixture-ai-audit','2026-10-26',json.dumps({'content_hash':self.store._quality_content(item),'issues':['fixture unresolved safety scope']})))
        self.assertEqual(self.store.candidate_rows([key])[0]['qualification_status'],'needs_human_review')
        with self.assertRaises(ValueError):self.store.review_question(key,'approved','fixture')
        self.store.review_question(key,'approved','fixture-human',reason='explicit fixture disposition')
        self.assertEqual(self.store.candidate_rows([key])[0]['qualification_status'],'human_approved')

    def test_existing_batch_endpoint_accepts_current_full_working_set(self):
        from unittest.mock import Mock
        worker=Mock()
        with patch.object(main,'store',self.store),patch.object(main.threading,'Thread',return_value=worker) as thread:
            reply=main.rerun_generation_quality(self.run_id,False)
        self.assertEqual(reply['status'],'running')
        self.assertEqual(len(thread.call_args.kwargs['args'][1]),50)
        worker.start.assert_called_once()
        self.assertEqual(self.calls,[],'entry check must not execute Provider')

    def test_entire_batch_precheck_precedes_any_paid_phase(self):
        item=self.store.questions()[-1];raw=item['raw']
        raw['business_requirements']['sources']=[{'chunk_id':'forged'}]
        with self.store.connection() as c:c.execute('UPDATE questions SET raw_json=? WHERE id=?',(json.dumps(raw),item['id']))
        self.complete_quality()
        self.assertEqual(self.calls,[])
        self.assertEqual(self.store.generation_run(self.run_id,qualification=False)['artifacts']['hard_validation']['quality_rerun']['status'],'failed')

    def test_current_50_with_documented_exceptions_reaches_gate_after_review(self):
        with closing(sqlite3.connect((ROOT/'backend/data/demo.db').resolve().as_uri()+'?mode=ro',uri=True)) as source,self.store.connection() as target:
            for row in source.execute("SELECT question_id,gate,decision,actor,created_at,metadata_json FROM review_events WHERE decision='content_review_required'"):
                target.execute('INSERT INTO review_events(question_id,gate,decision,actor,created_at,metadata_json) VALUES (?,?,?,?,?,?)',row)
        self.complete_quality();rows=self.store.candidate_rows()
        exceptions=[row for row in rows if row['qualification_status']=='needs_human_review']
        self.assertEqual(len(exceptions),2)
        ids=[q['id'] for q in self.store.questions()]
        with self.assertRaises(ValueError):self.store.review_generation_batch(ids,'fixture-human',confirmed_manual_review=True)
        for row in exceptions:self.store.review_question(row['id'],'approved','fixture-human',reason='explicit offline fixture resolution, not actual review')
        snapshot=self.store.review_generation_batch(ids,'fixture-human',confirmed_manual_review=True)['snapshot']
        self.assertEqual(len(snapshot['questions']),50)
        self.assertTrue(all(q['validation']['freeze_valid'] for q in snapshot['questions']))

    def test_new_quality_cannot_reuse_old_human_gate_to_create_snapshot(self):
        self.complete_quality();ids=[q['id'] for q in self.store.questions()]
        self.store.review_generation_batch(ids,'fixture-human',confirmed_manual_review=True)
        key=ids[0]
        self.store.record_qc(key,semantic_reply(self.store.question(key),self.chunks,90,'P1'),'passed')
        with self.assertRaises(ValueError):self.store.create_dataset_snapshot(self.store.questions(),self.run_id)
        self.store.record_qc(key,semantic_reply(self.store.question(key),self.chunks,90,'P2'),'passed')
        with self.assertRaises(ValueError):self.store.create_dataset_snapshot(self.store.questions(),self.run_id)
