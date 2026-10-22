"""Offline real-response replay and isolated 50-case batch failure injection."""
import copy,json,unittest
from pathlib import Path
from unittest.mock import patch
import test_baseline_resume as fixture
from app.evaluation import EvaluationRunner
from app.evaluation_contract import BUSINESS_JUDGE_PROMPT,validate_business_judgment
from app.providers import DeepSeekProvider,ProviderInvalidResponse,ProviderTimeout,ProviderAPIError
from app.config import Settings

REAL=Path(__file__).resolve().parents[1]/'reports/baseline-resilience-20261020/failed-case.json'

class BaselineResilienceTests(unittest.TestCase):
    setUp=fixture.ResumeTests.setUp
    tearDown=fixture.ResumeTests.tearDown

    def fifty(self):
        # Preserve the real frozen 20/10/20 shape and actual identities/questions.
        items=copy.deepcopy(json.loads(REAL.read_text())['snapshot_shape'])
        from app.corpus import current_manifest,manifest_identity
        snapshot={'question_ids':[q['id'] for q in items], 'corpus_fingerprint':manifest_identity(current_manifest())}
        for q in items:q['reference_answer']='事实';q['evidence']=[]
        with self.store.connection() as c:c.execute('update dataset_versions set snapshot_json=? where id=?',(json.dumps({**snapshot,'questions':items}), 'fixture-golden'))
        runtime=fixture.Runtime(fail=None);return runtime,EvaluationRunner(self.store,runtime),items

    def execute(self,runner,source=None):
        key,items,config=runner.start_baseline(source,automatic=True)
        with patch('app.evaluation.time.sleep'),patch('urllib.request.urlopen',side_effect=AssertionError('offline only')):
            return runner.execute_baseline(key,items,config)

    def test_real_responses_stay_technical_never_fabricate_final_or_business_fail(self):
        f=json.loads(REAL.read_text());e=f['checkpoint']['execution'];q=f['question']
        for a in f['checkpoint']['attempts']:
            if not a.get('raw_provider_response'):continue
            raw=a['raw_provider_response'];j=json.loads(raw);before=copy.deepcopy(j)
            with self.assertRaisesRegex(ValueError,'real Final support'):
                validate_business_judgment(j,e['answer'],e['retrieval_trace']['final'],category=q['test_category'])
            self.assertEqual(j,before)
        self.assertIn('行为审查',BUSINESS_JUDGE_PROMPT)

    def test_isolated_invalid_judge_continues_49_and_resumes_only_one(self):
        runtime,runner,items=self.fifty();target=items[17];original=runtime.judge
        def judge(q,*args,**kw):
            if q==target['question']:raise ProviderInvalidResponse('contract',raw_provider_response='{}')
            return original(q,*args,**kw)
        runtime.judge=judge;old=self.execute(runner)
        self.assertEqual(old['status'],'partial');self.assertEqual(old['result']['completed'],49)
        self.assertEqual(old['result']['technical_error_count'],1)
        self.assertIsNone(old['result']['overall_score']);self.assertIsNone(old['result']['gates']['passed'])
        self.assertFalse(any(b['run_id']==old['id'] for b in self.store.bad_case_rows()))
        cp=old['result']['checkpoints'][target['id']];self.assertIn('execution',cp)
        self.assertEqual(len([a for a in cp['attempts'] if a['status']=='error']),2)
        frozen=copy.deepcopy(old);runtime.judge=original;new=self.execute(runner,old['id'])
        self.assertEqual(new['status'],'completed');self.assertEqual(new['result']['completed'],50)
        self.assertEqual(new['result']['technical_error_count'],0)
        self.assertEqual(len(runtime.answers),50);self.assertEqual(len(set(runtime.answers)),50)
        self.assertEqual(self.store.evaluation_run(old['id']),frozen)

    def test_consecutive_contract_failure_stops_after_two_questions(self):
        runtime,runner,_=self.fifty()
        runtime.judge=lambda *_a,**_k:(_ for _ in ()).throw(ProviderInvalidResponse('invalid contract',raw_provider_response='{}'))
        result=self.execute(runner)
        self.assertEqual(len(runtime.answers),2);self.assertEqual(result['result']['technical_error_count'],2)
        self.assertIn('连续',result['error_message']);self.assertFalse(result['result']['evaluation_complete'])

    def test_generation_timeout_exhaustion_is_isolated_but_account_error_stops(self):
        for error,expected in [(ProviderTimeout('timeout'),49),(ProviderAPIError('account',status_code=401),2)]:
            runtime,runner,items=self.fifty();answer=runtime.answer;calls=[];target=items[2]
            def flaky(q,c):
                calls.append(q)
                if q==target['question']:raise error
                return answer(q,c)
            runtime.answer=flaky;result=self.execute(runner)
            self.assertEqual(result['result']['completed'],expected)
            self.assertEqual(calls.count(target['question']),3 if isinstance(error,ProviderTimeout) else 1)

    def test_real_invalid_response_is_persisted_and_batch_continues(self):
        runtime,runner,items=self.fifty();f=json.loads(REAL.read_text());e=f['checkpoint']['execution'];answer=runtime.answer;judge=runtime.judge
        target=items[0];raw=[a['raw_provider_response'] for a in f['checkpoint']['attempts'] if a.get('raw_provider_response')][-1]
        provider=DeepSeekProvider(Settings('offline','https://invalid','offline'))
        def saved_answer(q,c):return copy.deepcopy(e) if q==target['question'] else answer(q,c)
        def saved_judge(q,*args,context=None,**kw):
            if q==target['question']:
                with patch.object(provider,'complete',return_value=raw):return provider.judge(q,f['question']['reference_answer'],e['answer'],context=context)
            return judge(q,*args,context=context,**kw)
        runtime.answer=saved_answer;runtime.judge=saved_judge;result=self.execute(runner)
        self.assertEqual(result['result']['completed'],49);self.assertEqual(result['result']['technical_error_count'],1)
        cp=result['result']['checkpoints'][target['id']]
        self.assertEqual(cp['attempts'][-1]['raw_provider_response'],raw)
        self.assertEqual(cp['execution'],e)

    def test_correction_retry_receives_error_and_original_output(self):
        runtime=fixture.Runtime(fail=None);judge=runtime.judge;contexts=[]
        def flaky(q,*args,context=None,**kw):
            if q=='Q2':
                contexts.append(context)
                if len(contexts)==1:raise ProviderInvalidResponse('missing support',raw_provider_response='{"invalid":true}')
            return judge(q,*args,context=context,**kw)
        runtime.judge=flaky;result=self.execute(EvaluationRunner(self.store,runtime))
        self.assertEqual(result['status'],'completed')
        self.assertEqual(contexts[1]['judge_correction']['previous_response'],'{"invalid":true}')

    def test_missing_final_and_conflict_business_fail_still_scored_for_all_categories(self):
        from app.evaluation_contract import validate_business_judgment
        for category in ['positive','ablation','negative']:
            for kind in ['missing','conflict']:
                j={'verdict':'FAIL','checks':[{'requirement':'必要事实','met':False,'answer_quotes':[],'support':[]}], 'issues':[], 'reason':'必要证据缺失'}
                if kind=='conflict':
                    j['checks'][0]['answer_quotes']=['不关闭电源'];j['issues']=[{'description':'违反必要条件','answer_quotes':['不关闭电源'],'support':[{'source_id':'c','quote':'必须关闭电源'}],'critical':True}]
                self.assertEqual(validate_business_judgment(j,'不关闭电源',[{'chunk_id':'c','content':'必须关闭电源'}],category=category)['verdict'],'FAIL')

    def test_old_loaded_contract_stops_before_any_request(self):
        runner=EvaluationRunner(self.store,self.runtime);key,items,config=runner.start_baseline(automatic=True)
        old=self.store.evaluation_run(key)['judge'];old['prompt_version']='stale-process'
        with self.store.connection() as c:c.execute('update evaluation_runs set judge_json=? where id=?',(json.dumps(old),key))
        result=runner.execute_baseline(key,items,config)
        self.assertEqual(result['status'],'failed');self.assertFalse(self.runtime.answers)

    def test_reconciled_explicit_fixture_covers_actual_facts_without_unsupported_behavior_check(self):
        # Explicit offline Judge fixture, never a rewrite of a real response or a model claim.
        f=json.loads(REAL.read_text());e=f['checkpoint']['execution'];q=f['question']
        j=json.loads(f['checkpoint']['attempts'][-1]['raw_provider_response'])
        behavior=j['checks'].pop();j['reason']+=' 行为审查：'+behavior['requirement']
        case=EvaluationRunner(None,None)._score_business({**q,'raw':q},e,j,q['reference_answer'])
        self.assertTrue(case['passed'])
        for category in ['positive','ablation']:
            broken=copy.deepcopy(j);broken['checks'][0]['support']=[]
            with self.assertRaises(ValueError):validate_business_judgment(broken,e['answer'],e['retrieval_trace']['final'],category=category)

    def test_api_exposes_persisted_technical_error_without_bad_case_or_eligibility(self):
        from api_fixture import main
        runtime,runner,items=self.fifty();judge=runtime.judge;target=items[7]
        def flaky(q,*args,**kw):
            if q==target['question']:raise ProviderInvalidResponse('contract',raw_provider_response='{}')
            return judge(q,*args,**kw)
        runtime.judge=flaky;result=self.execute(runner)
        with patch.object(main,'store',self.store):
            api=main.evaluation(active_task=True)
            self.assertEqual(api['runtime_contract']['prompt_version'],'judge-vnext-5-fact-scope')
            self.assertEqual(set(api['runtime_contract']['loaded_code_sha256']),{'validator','provider_parser','scorer','batch_runner','diagnostic_view','agent_generate'})
            self.assertEqual(api['result']['completed'],49);self.assertEqual(api['result']['technical_error_count'],1)
            self.assertIsNone(api['current_baseline_id']);self.assertEqual(main.bad_cases(),[])
            self.assertEqual([g['status'] for g in api['result']['gates']['gates']],['NOT_EVALUABLE']*11)

    def test_stale_contract_keeps_existing_cases_and_checkpoint_audit(self):
        runner=EvaluationRunner(self.store,self.runtime);key,items,config=runner.start_baseline(automatic=True)
        cp={'Q1':{'execution':self.runtime.answer('Q1',config),'attempts':[{'phase':'judge','status':'error','raw_provider_response':'original'}]}}
        saved=self.store.evaluation_run(key);self.store.update_evaluation_progress(key,{**saved['result'],'checkpoints':cp})
        judge={**saved['judge'],'prompt_version':'stale'}
        with self.store.connection() as c:c.execute('update evaluation_runs set judge_json=? where id=?',(json.dumps(judge),key))
        result=runner.execute_baseline(key,items,config)
        self.assertEqual(result['result']['checkpoints'],cp)

    def test_known_retry_after_exhausting_deadline_is_isolated(self):
        runtime,runner,items=self.fifty();judge=runtime.judge;target=items[0];clock=[0.];calls=[]
        def flaky(q,*args,**kw):
            calls.append(q)
            if q==target['question']:raise ProviderAPIError('rate limit',status_code=429,retry_after=600)
            return judge(q,*args,**kw)
        def sleep(seconds):clock[0]+=seconds
        runtime.judge=flaky;key,approved,config=runner.start_baseline(automatic=True)
        with patch('app.evaluation.time.monotonic',side_effect=lambda:clock[0]),patch('app.evaluation.time.sleep',side_effect=sleep):
            result=runner.execute_baseline(key,approved,config)
        self.assertEqual(result['result']['completed'],49);self.assertEqual(calls.count(target['question']),1)
        self.assertEqual(result['result']['technical_error_count'],1)

    def test_actual_missing_final_is_business_fail_not_technical_error(self):
        runtime,runner,items=self.fifty();judge=runtime.judge;answer=runtime.answer;target=items[3]
        def missing(q,c):
            result=answer(q,c)
            if q==target['question']:result.update(retrieval=[],retrieval_trace={'candidates':[],'reranked':[],'final':[],'status':'completed'})
            return result
        def failing(q,*args,**kw):
            if q==target['question']:return {'verdict':'FAIL','checks':[{'requirement':'必要事实必须有实际Final支持','met':False,'answer_quotes':['事实'],'support':[]}],'issues':[],'reason':'实际Final缺少必要证据','quality':{'correctness':0,'faithfulness':0,'completeness':0}}
            return judge(q,*args,**kw)
        runtime.answer=missing;runtime.judge=failing;result=self.execute(runner)
        self.assertEqual(result['status'],'completed');self.assertEqual(result['result']['bad_case_count'],1)
        self.assertEqual(result['result']['technical_error_count'],0)
        case=next(c for c in self.store.evaluation_case_results(result['id']) if c['question_id']==target['id'])
        self.assertFalse(case['passed']);self.assertEqual(case['evaluation_outcome']['verdict'],'FAIL')

    def test_invalid_outputs_rejected_for_positive_ablation_negative(self):
        provider=DeepSeekProvider(Settings('fixture','https://invalid','fixture'))
        base={'verdict':'PASS','checks':[{'requirement':'必要要求','met':True,'answer_quotes':['事实'],'support':[{'source_id':'c','quote':'事实'}]}],'issues':[],'reason':'明确离线响应','quality':{'correctness':4,'faithfulness':1,'completeness':1}}
        for category in ['positive','ablation','negative']:
            variants=['{','null',json.dumps({**base,'verdict':'MAYBE'})]
            for field,bad in [('met','true'),('answer_quotes',['不存在']),('support',[{'source_id':'fake','quote':'事实'}])]:
                j=copy.deepcopy(base);j['checks'][0][field]=bad;variants.append(json.dumps(j))
            for raw in variants:
                with self.subTest(category=category,raw=raw),patch.object(provider,'complete',return_value=raw):
                    with self.assertRaises(ProviderInvalidResponse) as error:provider.judge('q','事实','事实',context={'contract_version':'business-vnext-1','category':category,'final_context':[{'chunk_id':'c','content':'事实'}]})
                    self.assertEqual(error.exception.raw_provider_response,raw)

    def test_crash_after_case_commit_clears_stale_error_without_rejudging(self):
        runtime=fixture.Runtime(fail=None);runner=EvaluationRunner(self.store,runtime)
        key,items,config=runner.start_baseline(automatic=True)
        execution=runtime.answer('Q1',config);case=runner.score_execution(items[0],execution)
        saved=self.store.evaluation_run(key)['result']
        cp={'Q1':{'execution':execution,'attempts':[],'technical_error':{'phase':'judge','error':'previous failure'}}}
        self.store.update_evaluation_progress(key,{**saved,'checkpoints':cp})
        self.store.record_evaluation_case(key,'Q1',case,with_bad_case=True)
        with patch('app.evaluation.time.sleep'):result=runner.execute_baseline(key,items,config)
        self.assertEqual(result['status'],'completed');self.assertEqual(result['result']['technical_error_count'],0)
        self.assertEqual(runtime.answers.count('Q1'),1);self.assertEqual(runtime.judges.count('Q1'),1)

    def test_known_late_complete_response_is_saved_and_resume_does_not_repeat_it(self):
        for stage in ['answer','judge']:
            runtime,runner,items=self.fifty();target=items[0];action=getattr(runtime,stage);clock=[0.];calls=[]
            def late(q,*args,**kw):
                calls.append(q);value=action(q,*args,**kw)
                if q==target['question']:clock[0]+=601
                return value
            setattr(runtime,stage,late);key,approved,config=runner.start_baseline(automatic=True)
            with patch('app.evaluation.time.monotonic',side_effect=lambda:clock[0]),patch('app.evaluation.time.sleep'):
                old=runner.execute_baseline(key,approved,config)
            self.assertEqual(old['result']['completed'],49);self.assertEqual(old['result']['technical_error_count'],1)
            self.assertIn('execution' if stage=='answer' else 'scored_result',old['result']['checkpoints'][target['id']])
            new=self.execute(runner,old['id'])
            self.assertEqual(new['status'],'completed');self.assertEqual(calls.count(target['question']),1)
