"""V4 final acceptance: explicit offline responses; no Provider calls."""
import copy,json,unittest
from unittest.mock import patch
from app.evaluation_contract import validate_business_judgment
from app.evaluation import EvaluationRunner,summarize_evaluation_cases
from app.providers import DeepSeekProvider,ProviderInvalidResponse
from app.config import Settings

class NegativeFinalContractTests(unittest.TestCase):
    def setUp(self):
        self.answer='当前不能确定路线，请先确认区域。示教前必须划分清洁分区。'
        self.final=[{'chunk_id':'actual','product':'robot','version':'v1','content':'示教前必须划分清洁分区。'}]
        self.behavior={'check_type':'negative_behavior','requirement':'区域未知时拒绝猜测路线并澄清','met':True,'answer_quotes':['当前不能确定路线，请先确认区域。'],'support':[]}
        self.fact={'check_type':'fact','requirement':'示教前划分清洁分区','met':True,'answer_quotes':['示教前必须划分清洁分区。'],'support':[]}
        self.value={'verdict':'PASS','checks':[self.behavior,self.fact],'issues':[],'reason':'离线明确响应','quality':{'correctness':4,'faithfulness':1,'completeness':1}}
    def validate(self,value=None,final=None,category='negative'):
        return validate_business_judgment(value or self.value,self.answer,self.final if final is None else final,category=category,constraints={'product':'robot','version':'v1'})
    def test_correct_negative_fact_without_final_must_not_silently_pass(self):
        with self.assertRaisesRegex(ValueError,'Final support'):self.validate()
    def test_only_explicit_negative_behavior_is_exempt_and_source_scoping_still_applies(self):
        v=copy.deepcopy(self.value);v['checks']=v['checks'][:1]
        self.assertEqual(self.validate(v,[])['verdict'],'PASS')
        for kind in [None,'unknown',1]:
            bad=copy.deepcopy(v)
            if kind is None:bad['checks'][0].pop('check_type')
            else:bad['checks'][0]['check_type']=kind
            with self.subTest(kind=kind),self.assertRaises(ValueError):self.validate(bad,[])
        with self.assertRaises(ValueError):self.validate(v,category='positive')
    def test_mixed_behavior_and_fact_needs_real_applicable_final_not_anchor_or_candidate(self):
        v=copy.deepcopy(self.value);v['checks'][1]['support']=[{'source_id':'actual','quote':self.final[0]['content']}]
        self.assertEqual(self.validate(v)['verdict'],'PASS')
        for key,value in [('chunk_id','wrong'),('product','other'),('version','v2')]:
            bad=copy.deepcopy(self.final);bad[0][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):self.validate(v,bad)
        with self.assertRaises(ValueError):validate_business_judgment(v,self.answer,[],category='negative',candidates=self.final)
    def test_real_evidence_missing_can_be_business_fail_not_parser_rewrite(self):
        v=copy.deepcopy(self.value);v.update(verdict='FAIL',reason='实际Final不足');v['checks'][1]['met']=False
        self.assertEqual(self.validate(v,[])['verdict'],'FAIL')
        v['verdict']='PASS'
        with self.assertRaises(ValueError):self.validate(v,[])
    def test_provider_and_scorer_share_strict_rejection_and_preserve_raw(self):
        raw=json.dumps(self.value,ensure_ascii=False);provider=DeepSeekProvider(Settings('offline','https://invalid','offline'))
        with patch.object(provider,'complete',return_value=raw),patch('urllib.request.urlopen',side_effect=AssertionError('offline')):
            with self.assertRaises(ProviderInvalidResponse) as error:provider.judge('q','先澄清',self.answer,context={'contract_version':'business-vnext-1','category':'negative','final_context':self.final})
        self.assertEqual(error.exception.raw_provider_response,raw)
        with self.assertRaises(ProviderInvalidResponse):EvaluationRunner(None,None)._score_business({'question':'q','test_category':'negative','raw':{},'evidence':[]},{'answer':self.answer,'retrieval_trace':{'final':self.final}},self.value,'先澄清')
    def test_incomplete_summary_does_not_issue_overall_or_gate_success(self):
        case={'test_category':'positive','passed':True,'judge_result':{'correctness':4,'faithfulness':1,'completeness':1},'programmatic_metrics':{'latency_ms':1}}
        result=summarize_evaluation_cases([case],complete=False)
        self.assertIsNone(result['overall_score']);self.assertEqual(result['overall_score_status'],'NOT_EVALUABLE');self.assertIsNone(result['gates']['passed'])
        self.assertTrue(all(g['status']=='NOT_EVALUABLE' for g in result['gates']['gates']))
    def test_partial_and_failed_replay_never_publish_aggregate_or_bad_case(self):
        import test_baseline_resume as fixture
        holder=fixture.ResumeTests();holder.setUp()
        try:
            for completed in [0,1]:
                runtime=fixture.Runtime(fail=None);runner=EvaluationRunner(holder.store,runtime);key,items,config=runner.start_baseline()
                original=runner.score_execution;calls=[0]
                def score(item,execution):
                    calls[0]+=1
                    if calls[0]>completed:raise ProviderInvalidResponse('explicit invalid Judge')
                    return original(item,execution)
                executions={q['id']:runtime.answer(q['question'],config) for q in items}
                with patch.object(runner,'score_execution',side_effect=score):result=runner.execute_replay(key,items,executions)
                self.assertEqual(result['status'],'partial' if completed else 'failed')
                self.assertIsNone(result['result']['overall_score']);self.assertIsNone(result['result']['gates']['passed'])
                self.assertEqual(result['result']['bad_case_count'],0)
                self.assertFalse(any(b['run_id']==key for b in holder.store.bad_case_rows()))
        finally:holder.tearDown()
