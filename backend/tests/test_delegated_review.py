"""Offline owner delegation validation; not human or Provider acceptance."""
import hashlib
import json
import os
import tempfile
import unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
from unittest.mock import patch

# Isolation precedes all app imports; these are offline fixtures only.
_isolation=tempfile.TemporaryDirectory()
for _name,_leaf in [('RAG_DEMO_DB_PATH','demo.db'),('RAG_DEMO_ENV_PATH','missing.env'),('RAG_DEMO_INDEX_DIR','index'),('RAG_DEMO_DOCUMENTS_DIR','documents'),('RAG_DEMO_UPLOADS_DIR','uploads')]:
    os.environ[_name]=str(Path(_isolation.name)/_leaf)

from app.delegated_review import validate_delegation, pdf_page_text, CHECKS


class DelegatedReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        source=self.root/'user.txt';source.write_text('Explicit owner delegation fixture')
        self.auth={'authorization_id':'fixture-owner','source_file':str(source),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
                   'source':'direct_user_instruction','generation_run_id':'fixture-run','corpus':{'corpus_snapshot_id':'fixture'},'plan_id':'fixture-plan',
                   'delegated_by':'project_owner','actor':'Codex','expires_at':(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()}
        self.path=self.root/'owner-delegated-review.json';self.path.write_text(json.dumps(self.auth))
        self.rows=[{'id':str(i),'qualification_status':'machine_qualified'} for i in range(50)]
        self.items={r['id']:{'id':r['id'],'question':'fixture','test_category':'negative','raw':{'validation':{'valid':True},'coverage_anchor_chunk_ids':['C']},'evidence':[]} for r in self.rows}
        for i,item in enumerate(self.items.values()):
            item['test_category']='positive' if i<20 else 'ablation' if i<30 else 'negative'
            item['evidence']=[{'source_chunk_ids':['C']}]
        self.reviews=[{'question_id':r['id'],'content_hash':'fixture-hash','decision':'A','checks':dict.fromkeys(CHECKS,True),
                       'risk':'none','basis':'Independent fixture review, not model self-confirmation',
                       'sources':[{'document_id':'D','chunk_id':'C','page':1,'quote':'source fact'}]} for r in self.rows]
        self.run={'profile':{'name':'medium','positive_count':20,'ablation_count':10,'negative_count':20,'expected_count':50},'id':'fixture-run','status':'completed','question_ids':[r['id'] for r in self.rows],'artifacts':{'hard_validation':{'corpus_fingerprint':self.auth['corpus'],'frozen_plan':{'plan_id':'fixture-plan','clusters':[{}]*9}}}}

    def check(self):
        return validate_delegation(self.path,'fixture-owner',self.run,self.rows,self.items,self.reviews,
                                   lambda item:'fixture-hash',verify_sources=lambda sources:True)

    def test_fifty_scoped_reviews_preserve_ai_actor_and_owner_source(self):
        result=self.check()
        self.assertEqual(result['approval_mode'],'owner_delegated')
        self.assertEqual(result['review_actor_type'],'ai_agent')
        self.assertEqual(result['delegated_by'],'project_owner')
        self.assertEqual(len(result['reviews']),50)

    def mini(self):
        self.rows=self.rows[:20]
        self.items={row['id']:self.items[row['id']] for row in self.rows}
        for i,item in enumerate(self.items.values()):
            item['test_category']='positive' if i<8 else 'ablation' if i<12 else 'negative'
        self.reviews=self.reviews[:20]
        self.run['question_ids']=[row['id'] for row in self.rows]
        self.run['profile']={'name':'mini','positive_count':8,'ablation_count':4,'negative_count':8,'expected_count':20}
        self.auth['profile']=dict(self.run['profile'])
        self.path.write_text(json.dumps(self.auth))

    def test_twenty_scoped_reviews_require_explicit_matching_mini_profile(self):
        self.mini()
        result=self.check()
        self.assertEqual(len(result['reviews']),20)
        self.assertEqual(result['review_actor_type'],'ai_agent')
        self.assertEqual(result['authorization_source_sha256'],self.auth['source_sha256'])

    def test_mini_rejects_missing_unknown_wrong_or_partial_authorization_scope(self):
        self.mini()
        for field,value in [('profile',None),('profile',{'name':'full'}),('profile',{'name':'mini'}),
                            ('authorization_id','unknown'),('generation_run_id','other'),('plan_id','other')]:
            with self.subTest(field=field,value=value):
                self.path.write_text(json.dumps({**self.auth,field:value}))
                with self.assertRaises(ValueError):self.check()
        self.path.write_text(json.dumps(self.auth))

    def test_profile_and_counts_cannot_be_relabelled_to_expand_authorization(self):
        self.mini()
        for profile in [{**self.run['profile'],'name':'medium'}, {**self.run['profile'],'positive_count':7},
                        {**self.run['profile'],'expected_count':50}, {}]:
            with self.subTest(profile=profile):
                original=self.run['profile'];self.run['profile']=profile
                with self.assertRaises(ValueError):self.check()
                self.run['profile']=original
        self.items['0']['test_category']='negative'
        with self.assertRaises(ValueError):self.check()

    def test_mini_does_not_waive_pdf_quality_or_review_identity(self):
        self.mini()
        with self.assertRaises(ValueError):
            validate_delegation(self.path,'fixture-owner',self.run,self.rows,self.items,self.reviews,
                                lambda item:'fixture-hash',verify_sources=lambda sources:False)
        self.rows[0]['qualification_status']='needs_human_review'
        with self.assertRaises(ValueError):self.check()
        self.rows[0]['qualification_status']='machine_qualified'
        self.reviews[0]['content_hash']='stale'
        with self.assertRaises(ValueError):self.check()
        self.reviews[0]['content_hash']='fixture-hash'
        self.reviews[-1]=self.reviews[0]
        with self.assertRaises(ValueError):self.check()

    def test_failed_quality_risk_stale_content_and_incomplete_set_rejected(self):
        for field,value in [('decision','C'),('risk','unresolved'),('content_hash','stale')]:
            old=self.reviews[0][field];self.reviews[0][field]=value
            with self.assertRaises(ValueError):self.check()
            self.reviews[0][field]=old
        self.rows[0]['qualification_status']='needs_human_review'
        with self.assertRaises(ValueError):self.check()
        self.rows[0]['qualification_status']='machine_qualified'
        self.reviews.pop()
        with self.assertRaises(ValueError):self.check()

    def test_expiry_wrong_corpus_and_altered_authorization_rejected(self):
        for field,value in [('expires_at','2000-01-01T00:00:00+00:00'),('source_sha256','wrong'),('corpus',{'corpus_snapshot_id':'other'})]:
            changed={**self.auth,field:value};self.path.write_text(json.dumps(changed))
            with self.assertRaises(ValueError):self.check()
            self.path.write_text(json.dumps(self.auth))

    def test_pdf_private_glyph_uses_local_ocr_but_ordinary_text_does_not(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        document=Mock()
        document.__enter__=Mock(return_value=document)
        document.__exit__=Mock(return_value=False)
        document.__len__=Mock(return_value=1)
        page=Mock()
        document.__getitem__=Mock(return_value=page)
        page.get_pixmap.return_value.tobytes.return_value=b'local-image'
        ocr=Mock(return_value=SimpleNamespace(txts=['www.kaercher.com/dealersearch']))
        with patch('pymupdf.open',return_value=document),patch('app.delegated_review.local_ocr',return_value=ocr):
            page.get_text.return_value=''
            self.assertEqual(pdf_page_text('fixture-private-glyph.pdf',1,1),'www.kaercher.com/dealersearch')
            ocr.assert_called_once_with(b'local-image')
            ocr.reset_mock()
            page.get_text.return_value='真实设备资料 IPX3'
            self.assertEqual(pdf_page_text('fixture-readable.pdf',1,1),'真实设备资料 IPX3')
            ocr.assert_not_called()
        pdf_page_text.cache_clear()

    def test_missing_pdf_support_rejected(self):
        with self.assertRaises(ValueError):
            validate_delegation(self.path,'fixture-owner',self.run,self.rows,self.items,self.reviews,
                                lambda item:'fixture-hash',verify_sources=lambda sources:False)

    def test_only_passed_probe_qc_retrieval_warning_can_be_explicitly_accepted(self):
        self.rows[0].update(qualification_status='needs_human_review',attention_reasons=['检索不连贯'],probe_status='probe_passed',qc_status='qc_passed',probe={'id':123})
        with self.assertRaises(ValueError):self.check()
        self.reviews[0]['retrieval_risk_acceptance']={'classification':'RETRIEVAL_INCOHERENT','retrieval_not_fixed':True,'probe_id':123,'reason':'PDF facts verified; actual recall defect retained for Baseline diagnosis'}
        self.check()
        self.rows[0]['probe']['id']=124
        with self.assertRaises(ValueError):self.check()
        self.rows[0]['probe']['id']=123
        self.rows[0].update(attention_reasons=['QC P1','检索不连贯'],qc={'id':456})
        with self.assertRaises(ValueError):self.check()
        self.reviews[0]['retrieval_risk_acceptance'].update(qc_id=456,qc_issue_disposition='P1 retrieval gap accepted; existing answer stops faulty equipment, no unsafe omission')
        self.check()
        self.rows[0]['probe_status']='needs_revision'
        with self.assertRaises(ValueError):self.check()
        self.rows[0].update(probe_status='probe_passed',attention_reasons=['检索不连贯','QC P0'])
        with self.assertRaises(ValueError):self.check()

    def test_business_audit_receives_verified_version_and_chapter_scope(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from app.ai_service import AiService
        from app.business_golden import CHECKS as AUDIT_CHECKS
        service=object.__new__(AiService)
        chunks=[{'chunk_id':'C','document_id':'D','page_start':4,'chunk_text':'source'},
                {'chunk_id':'CHAPTER','document_id':'D','page_start':2,'chunk_text':'R3遥控器'},
                {'chunk_id':'HISTORY','document_id':'D','page_start':13,'chunk_text':'修订历史 2.1 2025-4-18'}]
        service.corpus=SimpleNamespace(chunks=lambda:chunks)
        service.provider=Mock()
        service.provider.complete.return_value=json.dumps({'checks':dict.fromkeys(AUDIT_CHECKS,True),'reason':'fixture','difficulty_observed':'基础'})
        item={'question':'fixture','reference_answer':'source','test_category':'positive','evidence':[{'source_chunk_ids':['C']}],
              'raw':{'user_role':'operator','business_scenario':'fixture','user_intent':'fixture','product_scope':'R3',
                     'source_scope':{'documents':['D'],'chapter_anchor':'CHAPTER','manual_revision':'V2.1 / 2025-04-18'}}}
        service.business_quality_audit(item,[])
        payload=json.loads(service.provider.complete.call_args.args[1])
        self.assertEqual(payload['metadata']['product_scope'],'R3')
        self.assertEqual({c['chunk_id'] for c in payload['sources']},{'C','CHAPTER','HISTORY'})

    def test_metadata_only_revision_keeps_lineage_and_resets_quality(self):
        from app.governance import GovernanceStore
        store=GovernanceStore(self.root/'fixture.db')
        candidates=[{'test_category':group,'coverage_slot':f'Q{i:02d}','question':f'设备检查要求{i}是什么？',
                     'reference_answer':None if group=='negative' else '必须先确认状态','expected_behavior':'insufficient_evidence' if group=='negative' else None,
                     'evidence':[] if group=='negative' else [{'source_chunk_ids':['C'],'evidence_key_points':['必须先确认状态']}]} for i,group in enumerate(['positive']*8+['ablation']*4+['negative']*8,1)]
        item=store.save_mini_golden_candidates(candidates,'fixture')[0]
        raw={**item['raw'],'generation_strategy':'business_v2','difficulty':'中等','user_role':'现场运维','business_scenario':'检查设备','user_intent':'核对检查要求'}
        with store.connection() as db:db.execute('UPDATE questions SET raw_json=? WHERE id=?',(json.dumps(raw),item['id']))
        chunks=[{'chunk_id':'C','document_id':'D','document_name':'fixture.pdf','chunk_text':'必须先确认状态'}]
        run=store.start_revision(item['id'],'manual_edit','修正实际难度标签',False,{item['id']:{'difficulty':'基础'}},chunks,actor='Codex')
        prepared=store.prepare_revision(run['id'],chunks,similarity=lambda a,b:0.)
        self.assertTrue(prepared['validation']['passed'],prepared['validation'])
        applied=store.apply_revision(run['id'],chunks,similarity=lambda a,b:0.)
        current=store.question(item['id'])
        self.assertEqual(current['raw']['difficulty'],'基础')
        self.assertEqual(current['question'],item['question'])
        self.assertEqual(current['probe_status'],'probe_pending')
        self.assertEqual(current['qc_status'],'qc_pending')
        self.assertEqual(applied['actor'],'Codex')

    def test_delegated_transaction_records_ai_provenance_and_idempotent_snapshot(self):
        from app.governance import GovernanceStore
        store=GovernanceStore(self.root/'fixture-transaction.db')
        ids=[r['id'] for r in self.rows]
        slots=[];qualified=[]
        with store.connection() as db:
            for i,key in enumerate(ids):
                group='positive' if i<20 else 'ablation' if i<30 else 'negative'
                raw={'id':key,'question':f'fixture question {key}','generation_run_id':'fixture-run','coverage_slot':f'Q{i+1:02d}',
                     'topic_cluster':f'T{i%9}','test_category':group,'reference_answer':None,'evidence':[]}
                db.execute("INSERT INTO questions(id,stage,legacy_question_type,test_category,review_status,probe_status,qc_status,question,evidence_json,raw_json,created_at,updated_at) VALUES (?,'candidate','v1_mini',?,'human_review_pending','probe_passed','qc_passed',?,'[]',?,'fixture','fixture')",(key,group,raw['question'],json.dumps(raw)))
                slots.append({'slot_id':raw['coverage_slot'],'evaluation_group':group,'topic_cluster':raw['topic_cluster']})
                qualified.append({'id':key,'slot':raw['coverage_slot'],'test_category':group,'topic_cluster':raw['topic_cluster'],
                    'qualification_status':'machine_qualified','qualification_source':'machine','probe_status':'probe_passed','qc_status':'qc_passed'})
            profile={'name':'medium','positive_count':20,'ablation_count':10,'negative_count':20,'expected_count':50}
            artifact={'corpus_fingerprint':self.auth['corpus'],'frozen_plan':{'plan_id':'fixture-plan','slots':slots,'clusters':[{}]*9}}
            db.execute("INSERT INTO golden_generation_runs VALUES ('fixture-run',?,'fixture','completed',?,'fixture')",(json.dumps(profile),json.dumps(ids)))
            db.execute("INSERT INTO golden_generation_artifacts VALUES ('fixture-run','[]','[]',?)",(json.dumps(artifact),))
        delegated={'approval_mode':'owner_delegated','review_actor_type':'ai_agent','delegated_by':'project_owner','actor':'Codex',
                   'authorization_id':'fixture-owner','reviews':{r['question_id']:r for r in self.reviews}}
        with patch('app.delegated_review.validate_delegation',return_value=delegated),patch.object(store,'candidate_rows',return_value=qualified),patch('app.governance.current_manifest',return_value={}),patch('app.governance.manifest_identity',return_value=self.auth['corpus']),patch.object(store,'qc_history',return_value=[{'created_at':'fixture'}]):
            first=store.review_owner_delegated_batch('fixture-run','fixture-owner',self.reviews)
            second=store.review_owner_delegated_batch('fixture-run','fixture-owner',self.reviews)
        self.assertEqual(first['snapshot']['id'],second['snapshot']['id'])
        with store.connection() as db:
            events=db.execute("SELECT decision,actor,metadata_json FROM review_events WHERE decision='owner_delegated_confirmed'").fetchall()
            self.assertEqual(len(events),50)
            self.assertEqual(db.execute("SELECT source FROM dataset_versions WHERE id=?",(first['snapshot']['id'],)).fetchone()[0],'owner_delegated')
            self.assertTrue(all(r[1]=='Codex' and json.loads(r[2])['review_actor_type']=='ai_agent' for r in events))


if __name__=='__main__':unittest.main()
