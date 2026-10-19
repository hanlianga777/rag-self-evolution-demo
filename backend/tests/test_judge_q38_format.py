"""Offline output-contract and retry-window regression; no real Provider."""
import unittest,json
from unittest.mock import patch
import test_baseline_resume as fixture
from app.providers import DeepSeekProvider,ProviderInvalidResponse
from app.config import Settings
from app.evaluation import EvaluationRunner

class JudgeFormatTests(unittest.TestCase):
    def setUp(self):self.provider=DeepSeekProvider(Settings('fixture','https://invalid','fixture'))
    def response(self):
        return {'correctness':1,'completeness':0,'faithfulness':0,'behavior_pass':False,'reason':'未支持操作','missing_points':[],'unsupported_claims':[],
                'evidence_sufficiency':{'status':'not_applicable','source_applicable':None,'reason':'negative','conflicts':[],'fact_support':[]},'claim_reviews':[],'behavior_evidence':'换电池'}
    def test_complete_example_and_strict_evidence_type(self):
        body=self.response()
        with patch.object(self.provider,'complete',return_value=json.dumps(body)) as call:
            result=self.provider.judge('q','拒答','不要盲目换电池',context={'category':'negative','final_context':[]})
        self.assertFalse(result['behavior_pass']);self.assertEqual(result['faithfulness'],0)
        system=call.call_args.args[0];example=json.JSONDecoder().raw_decode(system.split('完整输出形状示例：')[1])[0]
        self.assertEqual(set(example),set(body));self.assertIsInstance(example['behavior_evidence'],str)
        self.assertTrue(call.call_args.kwargs['json_mode']);self.assertEqual(call.call_args.kwargs['temperature'],0)
        body['behavior_evidence']=['换电池']
        with patch.object(self.provider,'complete',return_value=json.dumps(body)):
            with self.assertRaisesRegex(ProviderInvalidResponse,'behavior_evidence.*list') as error:self.provider.judge('q','拒答','换电池',context={})
        self.assertEqual(error.exception.response_metadata['validation_error']['category'],'schema_contract')

    def test_error_categories_and_no_fabricated_evidence(self):
        for raw,category in [('{','json_syntax'),(json.dumps({'score':88}),'missing_field'),(json.dumps({**self.response(),'behavior_evidence':'不在答案'}),'schema_contract')]:
            with patch.object(self.provider,'complete',return_value=raw):
                with self.assertRaises(ProviderInvalidResponse) as error:self.provider.judge('q','expected','换电池',context={})
            self.assertEqual(error.exception.response_metadata['validation_error']['category'],category)
            self.assertEqual(error.exception.raw_provider_response,raw)

class RetryWindowTests(unittest.TestCase):
    setUp=fixture.ResumeTests.setUp
    tearDown=fixture.ResumeTests.tearDown
    def test_explicit_resume_keeps_history_but_does_not_charge_old_retry_window(self):
        first=self.runner.execute_baseline(*self.runner.start_baseline())
        source=self.store.evaluation_run(first['id']);cp=source['result']['checkpoints']['Q2']
        cp['attempts'] += [{'phase':'judge','status':'error','error_type':'ProviderInvalidResponse','recorded_by_run_id':first['id']}]*6
        self.store.finish_evaluation_run(first['id'],'partial',source['result'],source['error_message'])
        old=self.store.evaluation_run(first['id']);self.runtime.fail=None
        original=self.runtime.judge;calls=[]
        def judge(q,*args,**kw):
            calls.append(q)
            if q=='Q2' and calls.count(q)==1:raise ProviderInvalidResponse('fixture format')
            return original(q,*args,**kw)
        self.runtime.judge=judge
        key,items,config=self.runner.start_baseline(first['id'],automatic=True)
        with patch('app.evaluation.time.sleep'):result=self.runner.execute_baseline(key,items,config)
        self.assertEqual(result['status'],'completed');self.assertEqual(calls.count('Q2'),2)
        self.assertEqual(self.runtime.answers.count('Q1'),1);self.assertEqual(self.runtime.answers.count('Q2'),1)
        self.assertEqual(self.store.evaluation_run(first['id']),old);self.assertEqual(result['judge'],first['judge'])
        self.assertEqual(len(result['result']['checkpoints']['Q2']['attempts']),len(cp['attempts'])+2)

    def test_same_run_restart_retains_limit_not_infinite_retries(self):
        runtime=fixture.Runtime(fail=None);runner=EvaluationRunner(self.store,runtime)
        key,items,config=runner.start_baseline(automatic=True)
        result=self.store.evaluation_run(key)['result']
        result['checkpoints']={'Q1':{'execution':runtime.answer('Q1',config),'attempts':[{'phase':'judge','status':'error','error_type':'ProviderInvalidResponse','recorded_by_run_id':key}]*2}}
        self.store.update_evaluation_progress(key,result)
        def judge(*a,**kw):runtime.judges.append(a[0]);raise ProviderInvalidResponse('fixture contract')
        runtime.judge=judge
        completed=runner.execute_baseline(key,items,config)
        self.assertEqual(completed['status'],'partial');self.assertEqual(runtime.judges,[])
        self.assertEqual(len(completed['result']['checkpoints']['Q1']['attempts']),2)
