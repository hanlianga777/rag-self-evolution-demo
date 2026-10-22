"""New cases have no preinstalled historical review; semantic judgments are offline."""
import unittest
from copy import deepcopy
from app.evidence_resolver import resolve_case,request_identity

class ResolverTests(unittest.TestCase):
    def example(self):
        source={'chunk_id':'norm-new','document_id':'new-doc','product':'new-product','version':'v2','chunk_text':'维护前切断电池。'}
        hit={**source,'content':source['chunk_text']};noise={**hit,'chunk_id':'noise-new','content':'操作目录。','chunk_text':'操作目录。'}
        q={'id':'new-question','question':'如何维护？','reference_answer':'维护前切断电池。','test_category':'positive','evidence':[{'source_chunk_ids':['norm-new'],'evidence_key_points':['维护前']}],'product':'new-product','version':'v2'}
        case={'run_id':'new-run','question_id':q['id'],'question':q['question'],'reference_answer':q['reference_answer'],'test_category':'positive','model_answer':'检查外观。','judge_result':{'checks':[{'requirement':q['reference_answer'],'met':False,'answer_quotes':[],'support':[]}]},'evaluation_outcome':{'contract_version':'business-vnext-1','execution_complete':True,'verdict':'FAIL'},'programmatic_metrics':{'retrieval_trace':{'status':'completed','corpus_fingerprint':'new-corpus','parent_expand':False,'config':{'top_k':4},'candidates':[noise],'reranked':[noise],'final':[noise]}}}
        identity={'run_id':'new-run','question_id':q['id'],'snapshot_sha256':'snap','evaluation_identity':'eval','config_sha256':'cfg','corpus_fingerprint':'new-corpus'}
        return q,case,[source,noise],hit,identity
    def semantic(self,payload):
        # Stand-in judges coverage against the whole request; never returns a root.
        fact=payload['question']['reference_answer'];observations={}
        for stage,entries in payload['stages'].items():
            found=[{'source_id':e['chunk_id'],'quote':fact} for e in entries if fact in e['content']]
            observations[stage]={'coverage':'complete' if found else 'absent','support':found,'reviewed_source_ids':[e['chunk_id'] for e in entries],'reason':'reviewed every supplied entry including equivalents'}
        observations['answer']={'coverage':'absent','answer_quotes':[],'reason':'necessary instruction omitted'}
        return {'requirements_complete':True,'check_roles':[{'check_index':i,'role':'required','reason':'retain required context'} for i,c in enumerate(payload['checks']) if c.get('met') is True],'facts':[{'check_index':0,'golden_quote':fact,'reference_support':[{'source_id':payload['golden_norms'][0]['chunk_id'],'quote':fact}],'source_applicability':{'resolved':True,'purpose':'normative_requirement_only','reason':'same manual normative requirement; no authorization of unknown field condition'},'stages':observations}]}
    def test_new_retrieval_ranking_generation_cases_without_manual_json(self):
        for expected in ['Retrieval','Ranking','Generation']:
            q,c,chunks,hit,identity=self.example();trace=c['programmatic_metrics']['retrieval_trace']
            if expected!='Retrieval':trace['candidates'].append(hit);trace['reranked'].append(hit)
            if expected=='Generation':trace['final'].append(hit)
            r=resolve_case(c,q,chunks,identity,semantic=self.semantic)
            self.assertEqual(r['findings'][0][0],expected);self.assertEqual(r['status'],'resolved')
    def test_negative_fact_failure_uses_canonical_norm_without_promoting_anchor(self):
        q,c,chunks,hit,identity=self.example()
        q.update(test_category='negative',expected_behavior='safe_rejection');c['test_category']='negative'
        result=resolve_case(c,q,chunks,identity,semantic=self.semantic)
        self.assertEqual(result['status'],'resolved',result['blockers'])
        self.assertEqual(result['findings'][0][0],'Retrieval')
        self.assertFalse(result['findings'][0][2]['support'])

    def test_negative_mixed_behavior_and_fact_failures_keep_distinct_evidence(self):
        q,c,chunks,hit,identity=self.example()
        q.update(test_category='negative',expected_behavior='safe_rejection');c['test_category']='negative'
        c['judge_result'].update(verdict='FAIL',issues=[],reason='offline mixed failure')
        c['judge_result']['checks'].append({'requirement':'拒绝越权指令','check_type':'negative_behavior','met':False,'answer_quotes':[c['model_answer']],'support':[]})
        result=resolve_case(c,q,chunks,identity,semantic=self.semantic)
        self.assertEqual(result['status'],'resolved',result['blockers'])
        self.assertEqual({f[0] for f in result['findings']},{'Safety','Retrieval'})

    def test_no_semantic_authorization_does_not_infer_absence(self):
        q,c,chunks,hit,identity=self.example();r=resolve_case(c,q,chunks,identity)
        self.assertEqual(r['status'],'needs_semantic');self.assertFalse(r['findings'])
    def test_wrong_model_partial_unresolved_and_lying_absence_block(self):
        for mutation in ['cross_model','unresolved','partial','lie']:
            q,c,chunks,hit,identity=self.example()
            def semantic(payload):
                r=self.semantic(payload);f=r['facts'][0]
                if mutation=='unresolved':f['source_applicability']['resolved']=False
                elif mutation=='partial':f['stages']['candidates'].update(coverage='partial',support=[])
                elif mutation=='cross_model':chunks[0]['product']='another-product'
                else:c['programmatic_metrics']['retrieval_trace']['final'].append(hit)
                return r
            r=resolve_case(c,q,chunks,identity,semantic=semantic)
            self.assertFalse(r['findings']);self.assertTrue(r['blockers'])
    def test_arbitrary_ids_and_new_norm_do_not_require_a_lookup(self):
        import json,uuid
        q,c,chunks,hit,identity=self.example()
        raw=json.dumps([q,c,chunks,hit,identity],ensure_ascii=False)
        for token in ['new-question','new-run','norm-new','noise-new','new-doc','new-product']:
            raw=raw.replace(token,uuid.uuid4().hex)
        raw=raw.replace('维护前切断电池。','检修前隔离外部电源。')
        q,c,chunks,hit,identity=json.loads(raw)
        result=resolve_case(c,q,chunks,identity,semantic=self.semantic)
        self.assertEqual(result['findings'][0][0],'Retrieval')
    def test_semantic_equivalent_quote_locates_without_exact_fact_string(self):
        q,c,chunks,hit,identity=self.example();alias='保养作业前，须先隔离电池供电。'
        chunks[1]['chunk_text']=alias;chunks[1]['content']=alias
        trace=c['programmatic_metrics']['retrieval_trace']
        for stage in ['candidates','reranked']:trace[stage][0]['content']=alias
        trace['final']=[]
        def semantic(payload):
            r=self.semantic(payload)
            for stage in ['candidates','reranked']:
                r['facts'][0]['stages'][stage].update(coverage='complete',support=[{'source_id':chunks[1]['chunk_id'],'quote':alias}])
            return r
        result=resolve_case(c,q,chunks,identity,semantic=semantic)
        self.assertEqual(result['findings'][0][0],'Ranking')
    def test_same_product_different_remote_branch_is_rejected(self):
        q,c,chunks,hit,identity=self.example();alias='保养前先隔离电池供电。'
        chunks[0]['page_start']=2;chunks[1].update(page_start=5,chunk_text=alias,content=alias)
        base={k:chunks[0][k] for k in ['document_id','product','version']}
        chunks[:0]=[{**base,'chunk_id':'r1-title','page_start':1,'chunk_text':'R1遥控器'}]
        chunks.insert(2,{**base,'chunk_id':'r3-title','page_start':4,'chunk_text':'R3遥控器'})
        trace=c['programmatic_metrics']['retrieval_trace']
        for stage in ['candidates','reranked']:trace[stage][0].update(page_start=5,content=alias)
        trace['final']=[]
        def semantic(payload):
            r=self.semantic(payload)
            for stage in ['candidates','reranked']:
                r['facts'][0]['stages'][stage].update(coverage='complete',support=[{'source_id':'noise-new','quote':alias}])
            return r
        result=resolve_case(c,q,chunks,identity,semantic=semantic)
        self.assertFalse(result['findings']);self.assertIn('different_model_branch',str(result['blockers']))
    def test_identity_changes_invalidate_evidence(self):
        q,c,chunks,hit,identity=self.example();old=request_identity(c,q,chunks,identity)
        for key in ['run_id','config_sha256','corpus_fingerprint','evaluation_identity']:
            changed={**identity,key:'different'};self.assertNotEqual(old,request_identity(c,q,chunks,changed))

class PersistedResolverTests(ResolverTests):
    def test_independent_persistence_revalidated_cross_run_reuse_and_invalidation(self):
        import tempfile,os
        from pathlib import Path
        from unittest.mock import patch
        from app.governance import GovernanceStore
        from app.evidence_resolver import resolve_persisted,saved_findings
        q,c,chunks,hit,identity=self.example()
        with tempfile.TemporaryDirectory() as temporary,patch.dict(os.environ,{'RAG_DIAGNOSTIC_DIR':temporary+'/evidence','RAG_DEMO_DB_PATH':temporary+'/isolated.db'}):
            store=GovernanceStore(Path(temporary)/'isolated.db')
            snapshot={'id':'new-gd','questions':[q],'question_ids':[q['id']],'corpus_fingerprint':'new-corpus'}
            run=store.create_evaluation_run(snapshot,{'top_k':4},{'evaluation_identity':'new-eval'})
            store.record_evaluation_case(run,q['id'],c)
            result=resolve_persisted(store,run,q['id'],chunks,'new-corpus',semantic=self.semantic,persist=True)
            self.assertEqual(result['status'],'resolved')
            actual={**c,'run_id':run,'question_id':q['id']}
            self.assertEqual(saved_findings(actual,chunks,'new-corpus')[0][0][0],'Retrieval')
            again=resolve_persisted(store,run,q['id'],chunks,'new-corpus')
            self.assertEqual(again['status'],'resolved')
            another=store.create_evaluation_run(snapshot,{'top_k':4},{'evaluation_identity':'new-eval'})
            store.record_evaluation_case(another,q['id'],c)
            self.assertEqual(saved_findings({**actual,'run_id':another},chunks,'new-corpus')[0][0][0],'Retrieval')
            with store.connection() as connection:connection.execute('UPDATE evaluation_runs SET config_json=? WHERE id=?',('{"top_k":6}',run))
            findings,gaps=saved_findings(actual,chunks,'new-corpus');self.assertFalse(findings);self.assertTrue(gaps)
    def test_model_root_label_is_not_a_program_decision(self):
        q,c,chunks,hit,identity=self.example()
        def semantic(payload):return {**self.semantic(payload),'root_cause':'Safety','target_eligible':True}
        r=resolve_case(c,q,chunks,identity,semantic=semantic)
        self.assertEqual(r['findings'][0][0],'Retrieval')

class CompositeRequirementTests(ResolverTests):
    def test_satisfied_part_of_failed_composite_does_not_block_missing_part(self):
        q,c,chunks,hit,identity=self.example();parts=['检查外观。','维护前切断电池。'];q['reference_answer']=''.join(parts);c['reference_answer']=q['reference_answer'];c['model_answer']=parts[0]
        c['judge_result']['checks'][0]['requirement']=q['reference_answer'];chunks[0]['chunk_text']=q['reference_answer']
        for stage in ('candidates','reranked','final'):
            c['programmatic_metrics']['retrieval_trace'][stage][0]['content']=parts[0]
        chunks[1]['chunk_text']=parts[0];chunks[1]['content']=parts[0]
        def semantic(payload):
            facts=[]
            for i,part in enumerate(parts):
                stages={s:{'coverage':'complete' if i==0 else 'absent','support':[{'source_id':'noise-new','quote':part}] if i==0 else [],'reviewed_source_ids':['noise-new'],'reason':'full stage reviewed'} for s in ('candidates','reranked','final')}
                stages['answer']={'coverage':'complete' if i==0 else 'absent','answer_quotes':[part] if i==0 else [],'reason':'composite split reviewed'}
                facts.append({'check_index':0,'golden_quote':part,'reference_support':[{'source_id':'norm-new','quote':part}],'source_applicability':{'resolved':True,'purpose':'normative_requirement_only','reason':'same source'},'stages':stages})
            return {'requirements_complete':True,'facts':facts}
        result=resolve_case(c,q,chunks,identity,semantic=semantic)
        self.assertEqual(result['status'],'resolved',result['blockers']);self.assertEqual(result['findings'][0][0],'Retrieval')
        self.assertEqual(result['findings'][0][2]['preserve_support'],[{'source_id':'noise-new','quote':parts[0]}])
