"""Offline synthetic comparison fixtures, never Provider or business evidence."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

path=Path(__file__).with_name('report_judge_replay_20261031.py')
spec=importlib.util.spec_from_file_location('report_replay',path)
report=importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)

class ReplayReportTests(unittest.TestCase):
    def fixture(self):
        final=[{'chunk_id':'saved-child','document':'saved.pdf','page_start':3,'content':'ACTUAL FINAL'}]
        bundle={'source_run_id':'old-run','source_sha256':'source','cases':[{'question_id':'id1','answer':'ACTUAL ANSWER','retrieval_trace':{'final':final}}]}
        snapshot={'id':'new-snapshot','question_ids':['id1'],'scoring_contract_manifest':{'sha256':'manifest'},'questions':[{'id':'id1','coverage_slot':'Q01','question':'question','business_requirements':{'sources':[{'chunk_id':'norm-child','quote':'GOLDEN NORM','pages':[9]}]}}]}
        audit={'binding':'bound','source_run_id':'old-run','source_sha256':'source','target_snapshot_id':'new-snapshot','target_scoring_manifest':{'sha256':'manifest'},'cases':[{'question_id':'id1','answer_sha256':hashlib.sha256(b'ACTUAL ANSWER').hexdigest(),'stages':{'final':{'sha256':report.digest(final)}}}]}
        replay={'binding':'bound','status':'running','cases':[]}
        old={'id1':{'passed':True,'evaluation_outcome':{'execution_complete':True,'verdict':'PASS'}}}
        return audit,bundle,snapshot,replay,old

    def test_unrun_is_not_evaluable_without_borrowing_old_pass(self):
        self.assertTrue(callable(getattr(report,'build_report',None)), 'comparison helper is missing')
        result=report.build_report(*self.fixture())
        self.assertEqual(result['counts'],{'PASS':0,'FAIL':0,'NOT_EVALUABLE':1})
        self.assertEqual(result['cases'][0]['comparison'],'NOT_COMPARABLE')

    def completed(self,args):
        audit,bundle,snapshot,replay,old=args
        judgment={'verdict':'FAIL','reason':'ACTUAL JUDGE REASON','atomic_results':[{'atomic_id':'R1','state':'NOT_MET','reason':'ACTUAL ATOM REASON'}], 'checks':[{'met':False,'reason':'ACTUAL CHECK'}],'issues':[{'description':'ACTUAL ISSUE'}]}
        replay['cases']=[{'question_id':'id1','status':'completed','business_result':'FAIL','answer_sha256':audit['cases'][0]['answer_sha256'],'final_sha256':audit['cases'][0]['stages']['final']['sha256'],'judgment':judgment}]
        return args

    def test_flip_preserves_judgment_and_separates_final_from_golden(self):
        args=self.completed(self.fixture());before=copy.deepcopy(args)
        result=report.build_report(*args);row=result['flips'][0]
        self.assertEqual(row['old_verdict'],'PASS');self.assertEqual(row['new_verdict'],'FAIL')
        self.assertEqual(row['judge_reason'],'ACTUAL JUDGE REASON')
        self.assertEqual(row['actual_final'][0]['content'],'ACTUAL FINAL')
        self.assertEqual(row['golden_norms'][0]['quote'],'GOLDEN NORM')
        self.assertEqual(row['new_atomic_results'][0]['reason'],'ACTUAL ATOM REASON')
        self.assertEqual(args,before)

    def test_inconsistent_completed_is_technical_not_business(self):
        args=self.completed(self.fixture());args[3]['cases'][0]['judgment']['verdict']='PASS'
        row=report.build_report(*args)['cases'][0]
        self.assertEqual(row['new_verdict'],'NOT_EVALUABLE')
        self.assertEqual(row['comparison'],'NOT_COMPARABLE')

    def test_binding_mismatch_and_tampered_final_block_report(self):
        args=self.fixture();args[3]['binding']='other'
        with self.assertRaisesRegex(ValueError,'binding'):report.build_report(*args)
        args=self.fixture();args[1]['cases'][0]['retrieval_trace']['final'][0]['content']='ALTERED'
        with self.assertRaisesRegex(ValueError,'saved provenance'):report.build_report(*args)

    def test_technical_failure_retains_error_and_does_not_flip(self):
        args=self.fixture();args[3]['cases']=[{'question_id':'id1','status':'NOT_EVALUABLE','error':{'error_type':'ProviderTimeout'}}]
        result=report.build_report(*args)
        self.assertEqual(result['flips'],[])
        self.assertEqual(result['cases'][0]['technical_error'],{'error_type':'ProviderTimeout'})

    def test_explicit_incomplete_old_result_is_not_recast_from_passed(self):
        args=self.completed(self.fixture())
        args[4]['id1']['evaluation_outcome']['execution_complete']=False
        row=report.build_report(*args)['cases'][0]
        self.assertEqual(row['old_verdict'],'NOT_EVALUABLE')
        self.assertEqual(row['comparison'],'NOT_COMPARABLE')

    def test_old_database_read_is_readonly_and_hash_bound(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'fixture.db';db=sqlite3.connect(p)
            db.execute('CREATE TABLE evaluation_runs(id TEXT, result_json TEXT)')
            db.execute('CREATE TABLE evaluation_case_results(id INTEGER, run_id TEXT, question_id TEXT, result_json TEXT)')
            db.execute('INSERT INTO evaluation_runs VALUES(?,?)',('old-run','{}'))
            db.execute('INSERT INTO evaluation_case_results VALUES(?,?,?,?)',(1,'old-run','id1','{"passed": true}'))
            db.commit();db.close();before=p.read_bytes()
            bound=report.digest({'run':{'id':'old-run','result_json':'{}'},'cases':[('id1','{"passed": true}')]})
            self.assertEqual(report.load_old_cases(p,{'source_run_id':'old-run','source_sha256':bound}),{'id1':{'passed':True}})
            self.assertEqual(p.read_bytes(),before)
            with self.assertRaisesRegex(ValueError,'source hash'):report.load_old_cases(p,{'source_run_id':'old-run','source_sha256':'wrong'})

class CorrectionViewTests(unittest.TestCase):
    fixture=ReplayReportTests.fixture

    def correction_fixture(self,directory,question_id="id1",single_call_source=False):
        args=self.fixture()
        if question_id!='id1':
            args=tuple(json.loads(json.dumps(args).replace('\"id1\"',json.dumps(question_id))))
        audit,bundle,snapshot,replay,old=args
        audit.update(judge_versions={'prompt_version':'judge-vnext-6.3-nonclaim-checks'},judge_prompt_sha256='prompt')
        fields={'question':'question','reference_answer':'reference','actual_answer':'ACTUAL ANSWER','final_context':bundle['cases'][0]['retrieval_trace']['final'],
                'scoring_contract':{'compiled_contract_hash':'contract','question_id':question_id}}
        original_wire={'model':'deepseek-flash','max_tokens':65536,'messages':[{'role':'system','content':'PROMPT'},{'role':'user','content':json.dumps(fields,ensure_ascii=False)}]}
        old_sha=hashlib.sha256(json.dumps(original_wire).encode()).hexdigest()
        audit['requests']=[{'question_id':question_id,'request':{'request_sha256':old_sha,'max_tokens':65536,'model':'deepseek-flash'},'compiled_contract_hash':'contract'}]
        original_row={'question_id':question_id,'status':'NOT_EVALUABLE','business_result':None,'answer_sha256':audit['cases'][0]['answer_sha256'],'final_sha256':audit['cases'][0]['stages']['final']['sha256'],
                      'error':{'error_type':'ProviderInvalidResponse','raw_response':'ORIGINAL ERROR RESPONSE'}}
        replay.update(cases=[original_row],network_calls=1)
        fields['judge_correction']={'previous_response':'ORIGINAL ERROR RESPONSE','error':'technical correction only'}
        wire=copy.deepcopy(original_wire);wire['messages'][1]['content']=json.dumps(fields,ensure_ascii=False)
        new_sha=hashlib.sha256(json.dumps(wire).encode()).hexdigest()
        review=directory/'review';review.mkdir();recovery=directory/'recovery';recovery.mkdir()
        source=directory/'ledger.json';source.write_text(json.dumps({'calls':[{'request_payload':original_wire,'usage':{'request_sha256':old_sha}}]}))
        for name,value in (('request_input.json',fields),('request_wire_body.json',wire)):(review/name).write_text(json.dumps(value))
        if single_call_source:(review/'source_call.json').write_text(json.dumps(json.loads(source.read_text())['calls'][0]))
        plan={'question_id':question_id,'common50_binding':'bound','target_snapshot_id':'new-snapshot','versions':audit['judge_versions'],'judge_prompt_sha256':'prompt',
              'request':{'request_sha256':new_sha,'max_tokens':65536,'model':'deepseek-flash'},'additional_network_calls_if_authorized':1,'max_attempts':1,
              'source_files':[] if single_call_source else [{'path':str(source),'sha256':hashlib.sha256(source.read_bytes()).hexdigest()}],
              'artifact_file_sha256':{name:hashlib.sha256((review/name).read_bytes()).hexdigest() for name in ('request_input.json','request_wire_body.json')+(('source_call.json',) if single_call_source else ())}}
        plan['review_binding']=report.digest(plan);(review/'request_plan.json').write_text(json.dumps(plan))
        auth={'approved':True,'source':'direct_user_instruction_async_reply','user_answer':'批准额外1次，零重试','question_id':question_id,'additional_max_calls':1,
              'max_attempts_per_sample':1,'automatic_retries':0,'request_sha256':new_sha,'review_binding':plan['review_binding'],'common50_binding':'bound','target_snapshot_id':'new-snapshot'}
        authorization=directory/'authorization.json';authorization.write_text(json.dumps(auth))
        judgment={'verdict':'FAIL','atomic_results':[{'atomic_id':'R1','state':'NOT_MET'}],'checks':[{'met':False}],'issues':[],
                  'reason':'ACTUAL CORRECTION REASON','raw_provider_response':'CORRECTION RESPONSE'}
        fresh={**original_row,'status':'completed','business_result':'FAIL','judgment':judgment};fresh.pop('error')
        usage={'status':'ok','provider':'DeepSeek','requested_model':'deepseek-flash','prompt_tokens':3,'completion_tokens':4,'request_sha256':new_sha}
        response=recovery/'response.json';response.write_text(json.dumps({'choices':[{'message':{'content':'CORRECTION RESPONSE'}}],'usage':{'prompt_tokens':3,'completion_tokens':4}}))
        ledger={'identity':plan['review_binding'],'calls':[{'status':'ok','provider':'DeepSeek','model':'deepseek-flash','task':'judge','max_tokens':65536,
            'request_payload':wire,'request_sha256':hashlib.sha256(json.dumps(wire,ensure_ascii=False).encode()).hexdigest(),'usage':usage,'raw_response_path':str(response)}]}
        recovered={'binding':plan['review_binding'],'common50_binding':'bound','network_calls':1,'cases':[fresh]}
        recovered_audit={'review_binding':plan['review_binding'],'common50_binding':'bound','question_id':question_id,'request':plan['request'],'execute':True}
        for name,value in (('ledger.json',ledger),('replay.json',recovered),('audit.json',recovered_audit)):(recovery/name).write_text(json.dumps(value))
        return args,recovery,review,authorization

    def test_effective_view_preserves_superseded_error_and_extra_attempt_trace(self):
        self.assertTrue(callable(getattr(report,'with_correction',None)),'explicit correction view is missing')
        with tempfile.TemporaryDirectory() as directory:
            args,recovery,review,auth=self.correction_fixture(Path(directory));before=copy.deepcopy(args)
            updated=report.with_correction(args[0],args[1],args[3],recovery,review,auth)
            result=report.build_report(args[0],args[1],args[2],updated,args[4])
            self.assertEqual(result['counts'],{'PASS':0,'FAIL':1,'NOT_EVALUABLE':0})
            self.assertEqual(result['historical_judge_attempt_count'],2)
            self.assertEqual(result['correction_trace']['superseded_original']['status'],'NOT_EVALUABLE')
            self.assertNotEqual(result['correction_trace']['original_request_sha256'],result['correction_trace']['correction_request_sha256'])
            self.assertEqual(args,before)

    def test_multiple_corrections_keep_all_original_errors_and_single_call_artifact_proof(self):
        with tempfile.TemporaryDirectory() as directory:
            one=Path(directory)/'one';two=Path(directory)/'two';one.mkdir();two.mkdir()
            first,rec1,review1,auth1=self.correction_fixture(one)
            second,rec2,review2,auth2=self.correction_fixture(two,question_id='id2',single_call_source=True)
            audit,bundle,snapshot,replay,old=copy.deepcopy(first)
            for name in ('cases','requests'):audit[name]+=second[0][name]
            bundle['cases']+=second[1]['cases'];snapshot['question_ids']+=second[2]['question_ids'];snapshot['questions']+=second[2]['questions']
            replay['cases']+=second[3]['cases'];replay['network_calls']=2;old.update(second[4])
            view=report.with_correction(audit,bundle,replay,rec1,review1,auth1)
            view=report.with_correction(audit,bundle,view,rec2,review2,auth2)
            result=report.build_report(audit,bundle,snapshot,view,old)
            self.assertEqual(result['counts'],{'PASS':0,'FAIL':2,'NOT_EVALUABLE':0})
            self.assertEqual(result['historical_judge_attempt_count'],4)
            self.assertEqual([t['question_id'] for t in result['correction_traces']],['id1','id2'])
            self.assertTrue(all(t['superseded_original']['status']=='NOT_EVALUABLE' for t in result['correction_traces']))
            self.assertEqual(result['correction_trace']['question_id'],'id2')
            with self.assertRaisesRegex(ValueError,'Duplicate'):report.with_correction(audit,bundle,view,rec2,review2,auth2)

    def test_wrong_question_binding_source_and_duplicate_correction_block(self):
        for change in ('question','binding','source','duplicate'):
            with self.subTest(change=change),tempfile.TemporaryDirectory() as directory:
                args,recovery,review,auth=self.correction_fixture(Path(directory))
                if change=='source':(Path(directory)/'ledger.json').write_text('ALTERED')
                else:
                    p=recovery/'replay.json';value=json.loads(p.read_text())
                    if change=='question':value['cases'][0]['question_id']='other'
                    elif change=='binding':value['common50_binding']='other'
                    else:value['cases']*=2
                    p.write_text(json.dumps(value))
                with self.assertRaises(ValueError):report.with_correction(args[0],args[1],args[3],recovery,review,auth)

    def test_failed_correction_keeps_original_not_evaluable(self):
        with tempfile.TemporaryDirectory() as directory:
            args,recovery,review,auth=self.correction_fixture(Path(directory));p=recovery/'replay.json';value=json.loads(p.read_text());row=value['cases'][0]
            row.update(status='NOT_EVALUABLE',business_result=None,error={'error_type':'ProviderInvalidResponse','raw_response':'CORRECTION RESPONSE'});row.pop('judgment')
            p.write_text(json.dumps(value));updated=report.with_correction(args[0],args[1],args[3],recovery,review,auth)
            self.assertEqual(updated['cases'][0],args[3]['cases'][0]);self.assertFalse(updated['correction_trace']['applied'])

    def test_inconsistent_raw_or_usage_cannot_supply_completed_verdict(self):
        for change in ('raw','usage','answer'):
            with self.subTest(change=change),tempfile.TemporaryDirectory() as directory:
                args,recovery,review,auth=self.correction_fixture(Path(directory))
                if change=='raw':(recovery/'response.json').write_text('{}')
                elif change=='usage':
                    p=recovery/'ledger.json';value=json.loads(p.read_text());value['calls'][0]['usage']['completion_tokens']=None;p.write_text(json.dumps(value))
                else:
                    p=recovery/'replay.json';value=json.loads(p.read_text());value['cases'][0]['answer_sha256']='altered';p.write_text(json.dumps(value))
                with self.assertRaises(ValueError):report.with_correction(args[0],args[1],args[3],recovery,review,auth)

if __name__=='__main__':unittest.main()
