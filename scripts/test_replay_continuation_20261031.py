"""Offline bounded continuation fixtures; no formal DB or Provider calls."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
isolated=tempfile.TemporaryDirectory(prefix='replay-continuation-tests-')
for key in ('RAG_DEMO_DB_PATH','RAG_DEMO_ENV_PATH','RAG_DEMO_INDEX_DIR','RAG_DEMO_DOCUMENTS_DIR','RAG_DEMO_UPLOADS_DIR'):os.environ[key]=str(Path(isolated.name)/key)
for key in ('DEEPSEEK_API_KEY','DASHSCOPE_API_KEY','MINERU_API_KEY'):os.environ[key]=''
sys.path.insert(0,str(ROOT/'backend'))
spec=importlib.util.spec_from_file_location('replay',ROOT/'scripts/replay_saved_answers_judge_only_20261030.py')
replay=importlib.util.module_from_spec(spec);spec.loader.exec_module(replay)

class ContinuationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        for name in ('socket.create_connection','urllib.request.urlopen'):
            guard=patch(name,side_effect=AssertionError('offline only'));guard.start();self.addCleanup(guard.stop)

    def fixture(self):
        plans=[];rows=[];calls=[]
        for i in range(50):
            payload={'messages':[{'role':'user','content':'source'+str(i)}],'model':'deepseek-flash','max_tokens':65536}
            sha=hashlib.sha256(json.dumps(payload).encode()).hexdigest()
            plan={'question_id':'id'+str(i),'answer':'answer'+str(i),'context':{'final_context':[{'content':'final'+str(i)}]},'request':{'request_sha256':sha,'model':'deepseek-flash','max_tokens':65536},'compiled_contract_hash':'contract'+str(i),'question':'q','expected':'e'}
            plans.append(plan)
            if i>=4:continue
            raw=json.dumps({'verdict':'PASS' if i<3 else 'FAIL'})
            usage={'status':'ok','provider':'DeepSeek','requested_model':'deepseek-flash','prompt_tokens':1,'completion_tokens':2,'request_sha256':sha}
            metadata={'http_status':200,'http_response_received':True,'usage':usage,'validation_error':{'category':'business_contract'}}
            error={'error_type':'ProviderInvalidResponse','http_status':200,'response_metadata':metadata,'raw_response':raw}
            row={'question_id':plan['question_id'],'status':'completed' if i<3 else 'NOT_EVALUABLE','business_result':'PASS' if i<3 else None,'answer_sha256':replay.text_sha(plan['answer']),'final_sha256':replay.digest(plan['context']['final_context'])}
            row.update(judgment={'verdict':'PASS','raw_provider_response':raw} if i<3 else None,error=error if i==3 else None);rows.append(row)
            response=self.root/f'raw-{i}.json';response.write_text(json.dumps({'choices':[{'message':{'content':raw}}],'usage':{'prompt_tokens':1,'completion_tokens':2}}))
            calls.append({'status':'ok','provider':'DeepSeek','model':'deepseek-flash','task':'judge','max_tokens':65536,'request_payload':payload,'request_sha256':hashlib.sha256(json.dumps(payload,ensure_ascii=False).encode()).hexdigest(),'usage':usage,'raw_response_path':str(response)})
        audit={'binding':'b','requests':[{'question_id':p['question_id'],'request':p['request'],'compiled_contract_hash':p['compiled_contract_hash']} for p in plans]}
        for name,data in [('audit.json',audit),('replay.json',{'binding':'b','status':'stopped_technical_error_no_retry','cases':rows,'network_calls':4,'generation_calls':0}),('ledger.json',{'identity':'b','calls':calls})]:(self.root/name).write_text(json.dumps(data))
        return plans

    def test_skips_all_attempted_including_technical_and_binds_parent_files(self):
        self.assertTrue(callable(getattr(replay,'continuation_plan',None)),'controlled continuation missing')
        plans=self.fixture();remaining,parent=replay.continuation_plan(self.root,plans,'b',True)
        self.assertEqual([p['question_id'] for p in remaining],['id'+str(i) for i in range(4,50)])
        self.assertEqual(parent['attempted_count'],4);self.assertEqual(len(parent['file_sha256']),7)
        self.assertEqual(parent['cases'][3]['status'],'NOT_EVALUABLE')

    def test_binding_duplicate_prefix_request_and_source_drift_block(self):
        for mutate in ('binding','duplicate','prefix','request','source'):
            with self.subTest(mutate=mutate):
                plans=self.fixture()
                if mutate=='binding':
                    p=self.root/'replay.json';d=json.loads(p.read_text());d['binding']='other';p.write_text(json.dumps(d))
                elif mutate=='duplicate':
                    p=self.root/'replay.json';d=json.loads(p.read_text());d['cases'][1]=copy.deepcopy(d['cases'][0]);p.write_text(json.dumps(d))
                elif mutate=='prefix':plans[0],plans[1]=plans[1],plans[0]
                elif mutate=='request':plans[0]['request']['request_sha256']='altered'
                else:plans[0]['answer']='altered answer'
                with self.assertRaises(ValueError):replay.continuation_plan(self.root,plans,'b',True)

    def test_unknown_usage_or_inflight_parent_blocks(self):
        for mutate in ('usage','unknown','inflight'):
            with self.subTest(mutate=mutate):
                plans=self.fixture();p=self.root/'ledger.json';d=json.loads(p.read_text())
                if mutate=='usage':d['calls'][3]['usage']['completion_tokens']=None
                elif mutate=='unknown':d['calls'][3]['usage']['request_execution_unknown']=True
                else:d['calls'][3]['status']='reserved'
                p.write_text(json.dumps(d))
                with self.assertRaises(ValueError):replay.continuation_plan(self.root,plans,'b',True)

    def test_changed_parent_file_changes_continuation_binding(self):
        plans=self.fixture();_,first=replay.continuation_plan(self.root,plans,'b',True)
        p=self.root/'raw-3.json';p.write_text(p.read_text()+'\n')
        _,second=replay.continuation_plan(self.root,plans,'b',True)
        self.assertNotEqual(first['continuation_binding'],second['continuation_binding'])

    def test_known_invalid_classifier_rejects_transport_permission_and_unsettled(self):
        plans=self.fixture();call=json.loads((self.root/'ledger.json').read_text())['calls'][3]
        error=json.loads((self.root/'replay.json').read_text())['cases'][3]['error']
        self.assertTrue(replay.known_invalid_response(error,call,plans[3]['request']))
        for field,value in (('error_type','ProviderTimeout'),('http_status',403),('request_execution_unknown',True)):
            altered=copy.deepcopy(error);altered[field]=value
            self.assertFalse(replay.known_invalid_response(altered,call,plans[3]['request']))

    def execute_fixture(self, continue_invalid, unknown=False):
        from app.paid_run import paid_request,payment_usage,current_paid_run
        from app.providers import ProviderInvalidResponse,ProviderTimeout
        plans=self.fixture()[4:6]
        payloads=[{'messages':[{'role':'user','content':'source'+str(i)}],'model':'deepseek-flash','max_tokens':65536} for i in (4,5)]
        calls=[]
        class Provider:
            def judge(_self,question,expected,answer,context):
                i=len(calls);calls.append(answer);payload=payloads[i]
                usage={'status':'ok','provider':'DeepSeek','requested_model':'deepseek-flash','prompt_tokens':1,'completion_tokens':2,
                       'request_sha256':hashlib.sha256(json.dumps(payload).encode()).hexdigest()}
                with paid_request('DeepSeek','deepseek-flash',payload):
                    if unknown:raise ProviderTimeout('OFFLINE transport unknown')
                    current_paid_run().response({'choices':[{'message':{'content':'OFFLINE'}}],'usage':{'prompt_tokens':1,'completion_tokens':2}})
                    payment_usage(usage)
                if i==0:
                    raise ProviderInvalidResponse('OFFLINE schema error',raw_provider_response='OFFLINE',metadata={'http_status':200,'http_response_received':True,'usage':usage,'validation_error':{'category':'business_contract'}})
                return {'verdict':'PASS'}
        output=self.root/'execute';output.mkdir()
        result=replay.execute_plans(plans,Provider(),output,'b','historical',continue_known_invalid=continue_invalid)
        return result,calls

    def test_default_stops_even_known_schema_error(self):
        result,calls=self.execute_fixture(False)
        self.assertEqual(len(calls),1);self.assertEqual(result['status'],'stopped_technical_error_no_retry')

    def test_explicit_mode_continues_known_invalid_once_without_retry(self):
        result,calls=self.execute_fixture(True)
        self.assertEqual(calls,['answer4','answer5']);self.assertEqual(result['network_calls'],2)
        self.assertEqual(result['status'],'processed_all_with_technical_errors')
        self.assertEqual(result['cases'][0]['status'],'NOT_EVALUABLE');self.assertIsNone(result['cases'][0]['business_result'])
        self.assertTrue(result['cases'][0]['continued_after_known_invalid'])

    def test_explicit_mode_still_stops_transport_unknown(self):
        result,calls=self.execute_fixture(True,unknown=True)
        self.assertEqual(len(calls),1);self.assertEqual(result['status'],'stopped_technical_error_no_retry')
        self.assertFalse(result['cases'][0]['continued_after_known_invalid'])

    def test_parent_files_cannot_drift_after_review(self):
        plans=self.fixture();remaining,parent=replay.continuation_plan(self.root,plans,'b',True)
        (self.root/'raw-3.json').write_text('ALTERED')
        output=self.root/'execute';output.mkdir()
        with self.assertRaisesRegex(ValueError,'changed after preflight'):
            replay.execute_plans(remaining,None,output,'b','historical',continue_known_invalid=True,parent=parent)

    def test_global_attempt_cap_and_duplicate_questions_hold(self):
        plans=self.fixture();_,parent=replay.continuation_plan(self.root,plans,'b',True)
        output=self.root/'execute';output.mkdir()
        with self.assertRaisesRegex(ValueError,'previous attempts'):
            replay.execute_plans(plans[3:],None,output,'b','historical',parent=parent)
        with self.assertRaisesRegex(ValueError,'repeat'):
            replay.execute_plans(plans[:2],None,output,'b','historical',parent=parent)

if __name__=='__main__':unittest.main()
