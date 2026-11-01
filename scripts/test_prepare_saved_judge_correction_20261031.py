"""Offline selection/feedback guards; no app imports, DB or Provider calls."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('packet',Path(__file__).with_name('prepare_saved_judge_correction_20261031.py'))
packet=importlib.util.module_from_spec(spec);spec.loader.exec_module(packet)

class PacketSelectionTests(unittest.TestCase):
    def fixture(self,path):
        final=[{'chunk_id':'c','content':'ACTUAL FINAL'}]
        fields={'question':'q','reference_answer':'r','actual_answer':'ACTUAL ANSWER','final_context':final,
                'scoring_contract':{'question_id':'any-id','compiled_contract_hash':'contract'}}
        wire={'model':'deepseek-flash','max_tokens':65536,'messages':[{'role':'system','content':'PROMPT'},{'role':'user','content':json.dumps(fields,ensure_ascii=False)}]}
        request={'model':'deepseek-flash','max_tokens':65536,'request_sha256':hashlib.sha256(json.dumps(wire).encode()).hexdigest()}
        usage={'status':'ok','provider':'DeepSeek','requested_model':'deepseek-flash','prompt_tokens':2,'completion_tokens':3,'request_sha256':request['request_sha256']}
        error={'error_type':'ProviderInvalidResponse','http_status':200,'detail':'actual schema failure','raw_response':'ACTUAL RAW',
            'response_metadata':{'http_response_received':True,'http_status':200,'usage':usage,'validation_error':{'category':'business_contract'}}}
        row={'question_id':'any-id','status':'NOT_EVALUABLE','business_result':None,'error':error,
            'answer_sha256':packet.core.text_sha(fields['actual_answer']),'final_sha256':packet.core.digest(final)}
        raw=path/'response.json';raw.write_text(json.dumps({'choices':[{'message':{'content':'ACTUAL RAW'}}],'usage':{'prompt_tokens':2,'completion_tokens':3}}))
        call={'status':'ok','provider':'DeepSeek','model':'deepseek-flash','task':'judge','max_tokens':65536,
            'request_payload':wire,'request_sha256':hashlib.sha256(json.dumps(wire,ensure_ascii=False).encode()).hexdigest(),'usage':usage,'raw_response_path':str(raw)}
        values={'audit.json':{'binding':'common','source_run_id':'run','source_sha256':'source','requests':[{'question_id':'any-id','request':request,'compiled_contract_hash':'contract'}]},
            'saved_execution_bundle.json':{'source_run_id':'run','source_sha256':'source','cases':[{'question_id':'any-id','answer':fields['actual_answer'],'retrieval_trace':{'final':final}}]},
            'replay.json':{'binding':'common','cases':[row]},'ledger.json':{'identity':'common','calls':[call]}}
        for name,value in values.items():(path/name).write_text(json.dumps(value))
        return fields

    def test_exact_known_call_selected_without_source_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory);fields=self.fixture(path);before={p:p.read_bytes() for p in path.iterdir()}
            audit,saved,row,call,selected,raw,index=packet.select_known_schema_error(path,'any-id')
            self.assertEqual(selected,fields);self.assertEqual(index,0);self.assertEqual(call['status'],'ok')
            self.assertEqual(before,{p:p.read_bytes() for p in path.iterdir()})

    def test_unknown_execution_or_unsettled_usage_is_ineligible(self):
        for change in ('reserved','usage','unknown'):
            with self.subTest(change=change),tempfile.TemporaryDirectory() as directory:
                path=Path(directory);self.fixture(path);ledger=path/'ledger.json';value=json.loads(ledger.read_text())
                if change=='reserved':value['calls'][0]['status']='reserved'
                elif change=='usage':value['calls'][0]['usage']['completion_tokens']=None
                else:value['calls'][0]['usage']['request_execution_unknown']=True
                ledger.write_text(json.dumps(value))
                with self.assertRaisesRegex(ValueError,'Unknown'):packet.select_known_schema_error(path,'any-id')

    def test_generic_feedback_only_adds_actual_technical_response_and_error(self):
        fields={'scoring_contract':{'question_id':'unrelated-id'},'actual_answer':'original','final_context':[{'content':'verbatim'}]};before=copy.deepcopy(fields)
        corrected=packet.feedback_input(fields,'ACTUAL RAW','ACTUAL ERROR')
        self.assertEqual({k:v for k,v in corrected.items() if k!='judge_correction'},before)
        self.assertEqual(fields,before);self.assertEqual(corrected['judge_correction']['previous_response'],'ACTUAL RAW')
        self.assertIn('ACTUAL ERROR',corrected['judge_correction']['error']);self.assertIn('不把上次verdict、原子状态、quality当作正确值',corrected['judge_correction']['error'])
        self.assertNotIn('expected_verdict',corrected)
        with self.assertRaises(ValueError):packet.feedback_input(corrected,'again','error')

    def test_answer_drift_or_duplicate_identity_blocks(self):
        for change in ('answer','duplicate'):
            with self.subTest(change=change),tempfile.TemporaryDirectory() as directory:
                path=Path(directory);self.fixture(path)
                p=path/('saved_execution_bundle.json' if change=='answer' else 'replay.json');value=json.loads(p.read_text())
                if change=='answer':value['cases'][0]['answer']='ALTERED'
                else:value['cases']*=2
                p.write_text(json.dumps(value))
                with self.assertRaises(ValueError):packet.select_known_schema_error(path,'any-id')

if __name__=='__main__':unittest.main()
