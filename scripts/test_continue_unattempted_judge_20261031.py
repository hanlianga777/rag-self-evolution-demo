"""Synthetic interruption/claim guards only. No Provider or formal database."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value
wrapper=module('unattempted',ROOT/'scripts/continue_unattempted_judge_20261031.py')
fixture_module=module('synthetic_prefix',ROOT/'scripts/test_replay_continuation_20261031.py')

class InterruptedTailTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        for name in ('socket.create_connection','urllib.request.urlopen'):
            guard=patch(name,side_effect=AssertionError('offline interruption guard'));guard.start();self.addCleanup(guard.stop)

    def fixture(self):
        plans=fixture_module.ContinuationTests.fixture(self)
        _,link=wrapper.core.continuation_plan(self.root,plans,'b',True)
        inherited=copy.deepcopy(link['cases']);child=self.root/'child';child.mkdir();calls=[]
        for index in range(4,17):
            plan=plans[index];payload={'messages':[{'role':'user','content':'source'+str(index)}],'model':'deepseek-flash','max_tokens':65536}
            row={'question_id':plan['question_id'],'status':'completed','business_result':'PASS','answer_sha256':wrapper.core.text_sha(plan['answer']),'final_sha256':wrapper.core.digest(plan['context']['final_context'])}
            raw='OFFLINE '+str(index);row['judgment']={'verdict':'PASS','raw_provider_response':raw}
            call={'status':'ok','provider':'DeepSeek','model':'deepseek-flash','task':'judge','max_tokens':65536,'request_payload':payload,
                  'request_sha256':hashlib.sha256(json.dumps(payload,ensure_ascii=False).encode()).hexdigest(),'started_at':'2026-10-31T07:57:34+00:00',
                  'usage':{'status':'ok','provider':'DeepSeek','requested_model':'deepseek-flash','prompt_tokens':1,'completion_tokens':2,'request_sha256':plan['request']['request_sha256']}}
            if index==16:
                row.update(status='inflight',business_result=None);row.pop('judgment');call.update(status='reserved');call.pop('usage')
            else:
                response=child/f'ledger-response-{index-3:04d}.json';response.write_text(json.dumps({'choices':[{'message':{'content':raw}}],'usage':{'prompt_tokens':1,'completion_tokens':2}}));call['raw_response_path']=str(response)
            inherited.append(row);calls.append(call)
        audit=json.loads((self.root/'audit.json').read_text())
        replay={'binding':'b','status':'running','cases':inherited,'network_calls':16,'parent_network_calls':4,'new_network_calls':12,'generation_calls':0,'continuation_parent':{k:v for k,v in link.items() if k!='cases'}}
        ledger={'identity':'b','calls':calls,'stopped':None}
        for name,value in (('audit.json',audit),('replay.json',replay),('ledger.json',ledger)):(child/name).write_text(json.dumps(value))
        snapshot=self.root/'process.json';snapshot.write_text(json.dumps({'observed_at':'2026-10-31T12:14:07+00:00','matching_replay_processes':[],'complete_process_inventory_sha256':'offline-inventory'}))
        receipt={'owner_absent':True,'matching_replay_processes':[],'common_binding':'b','parent_directory':str(child),
            'process_snapshot_file':str(snapshot),'process_snapshot_sha256':wrapper.file_sha(snapshot),'observed_at':'2026-10-31T12:14:07+00:00',
            'ps_command':['ps','-axo','pid,ppid,command'],'ps_command_sha256':wrapper.core.digest(['ps','-axo','pid,ppid,command']),
            'process_inventory_sha256':'offline-inventory','retry_permitted':False,'budget_attempt_consumed':True,'response_available':False,
            'token_usage':None,'request_execution_status':'Unknown','cost_status':'Unknown','interrupted_question_id':'id16',
            'original_case_preserved':inherited[-1],'original_call_sha256':wrapper.core.digest(calls[-1]),
            'source_file_sha256':{str(p):wrapper.file_sha(p) for p in [child/'audit.json',child/'replay.json',child/'ledger.json',wrapper.CORE]}}
        path=self.root/'receipt.json';path.write_text(json.dumps(receipt))
        return plans,child,path

    def prepare(self,plans,child,receipt):return wrapper.prepare_interrupted_parent(child,plans,'b',receipt,exclude_interrupted_tail=True,continue_known_invalid=True)

    def test_exact33_only_unknown_tail_consumed_and_original_files_immutable(self):
        plans,child,receipt=self.fixture();before={p:p.read_bytes() for p in child.iterdir()}
        remaining,parent=self.prepare(plans,child,receipt)
        self.assertEqual([p['question_id'] for p in remaining],['id'+str(i) for i in range(17,50)])
        self.assertEqual(parent['attempted_count'],17);self.assertEqual(parent['known_settled_prior_calls'],16)
        self.assertEqual(parent['cases'][-1]['status'],'NOT_EVALUABLE');self.assertEqual(parent['cases'][-1]['error']['error_type'],'RequestExecutionUnknown')
        self.assertEqual(parent['cases'][-1]['error']['cost_status'],'Unknown');self.assertIsNone(parent['cases'][-1]['business_result'])
        self.assertEqual(before,{p:p.read_bytes() for p in child.iterdir()})
        self.assertEqual(json.loads((child/'ledger.json').read_text())['calls'][-1]['status'],'reserved')

    def test_default_guard_or_present_owner_cannot_exclude(self):
        plans,child,receipt=self.fixture()
        with self.assertRaisesRegex(ValueError,'Explicit'):wrapper.prepare_interrupted_parent(child,plans,'b',receipt)
        value=json.loads(receipt.read_text());value['owner_absent']=False;receipt.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError,'absent-owner'):self.prepare(plans,child,receipt)

    def test_receipt_binding_source_drift_or_other_question_block(self):
        for change in ('binding','source','question'):
            with self.subTest(change=change):
                with tempfile.TemporaryDirectory() as separate:
                    original=self.root;self.root=Path(separate)
                    try:
                        plans,child,receipt=self.fixture();value=json.loads(receipt.read_text())
                        if change=='binding':value['common_binding']='other'
                        elif change=='question':value['interrupted_question_id']='id15'
                        else:(child/'ledger.json').write_text('{}')
                        receipt.write_text(json.dumps(value))
                        with self.assertRaises(ValueError):self.prepare(plans,child,receipt)
                    finally:self.root=original

    def test_middle_unknown_or_tail_response_cannot_be_skipped(self):
        plans,child,receipt=self.fixture();(child/'ledger-response-0013.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'without response'):self.prepare(plans,child,receipt)
        (child/'ledger-response-0013.json').unlink();p=child/'ledger.json';value=json.loads(p.read_text());value['calls'][0]['status']='reserved';p.write_text(json.dumps(value))
        proof=json.loads(receipt.read_text());proof['source_file_sha256'][str(p)]=wrapper.file_sha(p);receipt.write_text(json.dumps(proof))
        with self.assertRaisesRegex(ValueError,'ancestor/middle'):self.prepare(plans,child,receipt)

    def test_ancestor_drift_blocks(self):
        plans,child,receipt=self.fixture();p=self.root/'raw-0.json';p.write_text('ALTERED')
        with self.assertRaisesRegex(ValueError,'ancestor'):self.prepare(plans,child,receipt)

    def test_claim_stable_across_new_receipt_output_and_never_auto_released(self):
        plans,child,receipt=self.fixture();_,first=self.prepare(plans,child,receipt)
        proof=json.loads(receipt.read_text());proof['tool_session_observation']='new observation, same consumed attempts';receipt.write_text(json.dumps(proof))
        _,second=self.prepare(plans,child,receipt)
        self.assertNotEqual(first['continuation_binding'],second['continuation_binding']);self.assertEqual(first['claim_key'],second['claim_key'])
        claim=wrapper.claim_once(first,self.root/'output-one',self.root/'claims')
        with self.assertRaises(FileExistsError):wrapper.claim_once(second,self.root/'output-two',self.root/'claims')
        self.assertTrue(claim.is_file());self.assertIs(json.loads(claim.read_text())['automatic_release'],False)

if __name__=='__main__':unittest.main()
