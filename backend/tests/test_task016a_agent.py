"""Task016a Agent rejection and saved-fact checks; disposable database only."""
import json
import unittest
from copy import deepcopy
from types import SimpleNamespace

import test_optimization_contract as contract
from app.optimization import OptimizationAgent, build_agent_prompt
from app.policy import DEFAULT_PIPELINE_CONFIG


class SequenceProvider(contract.FixedProvider):
    def __init__(self, responses):
        self.responses=iter(responses); self.prompts=[]
    def complete(self, system, prompt, **kwargs):
        self.prompts.append(json.loads(prompt))
        return next(self.responses)


class AgentRetryTests(unittest.TestCase):
    setUp=contract.OptimizationContractTests.setUp

    def test_all_rule_rejections_receive_reason_and_three_regenerations(self):
        valid=contract.drafts()
        shared=deepcopy(valid);shared['candidates'][0]['config_diff']={'min_score':.2}
        wrong=deepcopy(valid);wrong['candidates'][0]['direction']='不存在的方向'
        for rejected in ('{bad', json.dumps(shared), json.dumps(wrong), json.dumps({'candidates':[None,None,None]})):
            with self.subTest(rejected=rejected):
                exp=self.store.create_experiment('EVAL-test')
                provider=SequenceProvider([rejected]*3+[json.dumps(valid)])
                generated=OptimizationAgent(self.store,provider).generate('EVAL-test',experiment_id=exp)
                self.assertEqual(len(provider.prompts),4)
                self.assertEqual(len(generated['candidates']),3)
                self.assertEqual(generated['evaluation_budget']['used'],0)
                self.assertEqual(len(generated['result']['validation_retries']),3)
                for prompt in provider.prompts[1:]:
                    self.assertTrue(prompt['validation_rejection']['reason'])
                    self.assertEqual(prompt['validation_rejection']['rejected_response'],rejected)

    def test_exhaustion_stops_cycle_without_failed_or_sandbox_spend(self):
        from app.optimization_cycle import run_until_qualified
        exp=self.store.create_experiment('EVAL-test')
        provider=SequenceProvider(['{bad']*4)
        cycle=run_until_qualified(self.store,SimpleNamespace(provider=provider),exp)
        self.assertEqual(cycle['status'],'analysis_exhausted',cycle)
        self.assertIn('连续 3 次方案不合规',cycle['last_error'])
        self.assertEqual(cycle['used'],0)
        self.assertEqual(len(provider.prompts),4)
        saved=self.store.experiment(exp)
        self.assertEqual(saved['status'],'analysis_exhausted')
        self.assertEqual(saved['result']['generation_status'],'analysis_exhausted')

    def test_harmful_bundle_is_explicit_and_rejected_before_sandbox(self):
        from app.optimization import validate_round_contract
        valid=contract.drafts()
        gate={'id':'latency_p99_seconds','operator':'<=','actual':40,'passed':True}
        prior={'id':'harmful','status':'evaluated','config':{**DEFAULT_PIPELINE_CONFIG,'top_k':6},
               'reasoning':{'changed_parameters':{'top_k':6}},
               'result':{'new_failure_question_ids':['Q1'],'gates':{'gates':[{**gate,'actual':70,'passed':False}]}}}
        _,prompt=build_agent_prompt([],DEFAULT_PIPELINE_CONFIG,[prior],[],list('ABC'),baseline_gates=[gate])
        self.assertEqual(prompt['gate_harming_changes'][0]['config_diff'],{'top_k':6})
        self.assertEqual(prompt['gate_harming_changes'][0]['new_failure_question_ids'],['Q1'])
        with self.assertRaisesRegex(ValueError,'照搬已证明伤害门槛'):
            validate_round_contract(valid['candidates'],DEFAULT_PIPELINE_CONFIG,[prior],[gate])
        prior['reasoning']={}
        _,prompt=build_agent_prompt([],DEFAULT_PIPELINE_CONFIG,[prior],[],list('ABC'),baseline_gates=[gate])
        self.assertEqual(prompt['gate_harming_changes'][0]['attribution'],'未知')

    def test_retry_paid_response_survives_exit_before_provider_returns(self):
        import hashlib
        from app.evaluation_stage import checkpoint_request
        from app.telemetry import record_usage
        provider=contract.FixedProvider('unused')
        provider.request_summary=lambda system,user,**kw:{'request_sha256':hashlib.sha256((system+user).encode()).hexdigest()}
        sends=[];crashed=False
        def respond(system,user,**kwargs):
            nonlocal crashed
            retry='validation_rejection' in json.loads(user)
            def send():
                sends.append(retry);record_usage({'provider':'Stub','status':'ok'})
                return json.dumps(contract.drafts()) if retry else '{bad'
            response=checkpoint_request('Stub','fixture','agent',{'system':system,'user':user},send)
            if retry and not crashed:
                crashed=True
                raise KeyboardInterrupt('exit after durable retry RPC')
            return response
        provider.complete=respond
        with self.assertRaises(KeyboardInterrupt):OptimizationAgent(self.store,provider).generate('EVAL-test')
        exp=self.store.latest_experiment()
        with self.store.connection() as db:db.execute("UPDATE experiments SET status='failed' WHERE id=?",(exp['id'],))
        generated=OptimizationAgent(self.store,provider).generate('EVAL-test',experiment_id=exp['id'])
        self.assertEqual(sends,[False,True])
        self.assertEqual(len(generated['candidates']),3)
        self.assertEqual(len(generated['result']['token_usage']),2)


class SavedFactsTests(unittest.TestCase):
    def test_prompt_carries_speed_question_changes_and_confounded_harm(self):
        baseline_cases=[]
        candidate_cases=[]
        for n in range(1,8):
            common={'question_id':f'question-{n}','display_question_id':f'Q{n:02}',
                    'test_category':'negative' if n==2 else 'ablation' if n==3 else 'positive',
                    'negative_subtype':'safety_critical' if n==2 else None,
                    'diagnosis_category':'安全问题' if n==2 else '检索层问题'}
            baseline_cases.append({**common,'passed':n!=1,'primary_root_cause':'Retrieval' if n==1 else 'None','programmatic_metrics':{'latency_ms':n*1000,
                'token_usage':{'generation':{'completion_tokens_details':{'reasoning_tokens':n*100}}}}})
            candidate_cases.append({**common,'passed':n!=2,'programmatic_metrics':{'latency_ms':n*2000,
                'token_usage':{'generation':{'reasoning_tokens':n*200}}}})
        baseline_cases[0].pop('diagnosis_category')
        candidate_cases[0].pop('diagnosis_category')
        gate={'id':'safe_rejection_rate','operator':'>=','actual':100,'passed':True}
        prior={'id':'candidate-A','status':'evaluated','config':{'generation_thinking':'high','top_k':6},
            'reasoning':{'changed_parameters':{'generation_thinking':'high','top_k':6}},
            'result':{'metrics':{'latency_p50_seconds':8,'latency_p99_seconds':14},
                      'all_fixed_question_ids':['question-1'],'new_failure_question_ids':['question-2'],
                      'gates':{'gates':[{**gate,'actual':80,'passed':False}]}}}
        _,prompt=build_agent_prompt([],DEFAULT_PIPELINE_CONFIG,[prior],[],list('ABC'),baseline_gates=[gate],
            baseline_result={'metrics':{'latency_p50_seconds':4,'latency_p99_seconds':7}},
            baseline_cases=baseline_cases,candidate_cases={'candidate-A':candidate_cases})
        speed=prompt['baseline_performance']
        self.assertEqual((speed['latency_p50_seconds'],speed['latency_p99_seconds']),(4,7))
        self.assertEqual(len(speed['slowest_questions']),5)
        self.assertEqual(speed['slowest_questions'][0]['display_question_id'],'Q07')
        self.assertEqual(speed['slowest_questions'][0]['reasoning_tokens'],700)
        facts=prompt['prior_sandbox_results'][0]
        self.assertEqual(facts['performance']['slowest_questions'][0]['latency_seconds'],14)
        self.assertEqual(facts['question_changes']['fixed'][0]['test_category'],'positive')
        self.assertEqual(facts['question_changes']['fixed'][0]['diagnosis_category'],'检索层问题')
        self.assertEqual(facts['question_changes']['new_failures'][0]['negative_subtype'],'safety_critical')
        self.assertEqual(facts['question_changes']['new_failures'][0]['diagnosis_category'],'安全问题')
        self.assertIn('多个改动混在一起，无法判断是哪个参数造成的',facts['attribution'])
        harmful=prompt['gate_harming_changes'][0]
        self.assertEqual(harmful['config_diff'],prior['reasoning']['changed_parameters'])
        self.assertEqual(harmful['new_failure_question_ids'],['question-2'])
        self.assertEqual(harmful['harmed_gates'][0]['actual'],80)
        self.assertNotIn('建议',json.dumps(facts,ensure_ascii=False))

