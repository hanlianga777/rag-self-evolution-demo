import unittest
from app.optimization import validate_round_contract


class RoundContractTests(unittest.TestCase):
    def proposals(self):
        return [
            {'id':'A','direction':'检索召回增强','config_diff':{'candidate_k':24}},
            {'id':'B','direction':'回答策略','config_diff':{'prompt_strategy':'Tiered'}},
            {'id':'C','direction':'效率（降档 + 检索补偿）','config_diff':{'generation_thinking':'high','hyde':True}},
        ]

    def test_valid(self):
        validate_round_contract(self.proposals(), {'generation_thinking':'max'}, [])

    def test_reject_shared_parameter_missing_efficiency_quality_downgrade(self):
        for mutation in ('shared','missing','downgrade','missing_candidate','no_compensation'):
            with self.subTest(mutation=mutation):
                rows=self.proposals()
                if mutation=='shared': rows[0]['config_diff']['hyde']=True
                if mutation=='missing': rows[2]['direction']='排序与过滤'
                if mutation=='downgrade': rows[0]['config_diff']['generation_thinking']='low'
                if mutation=='missing_candidate': rows.pop()
                if mutation=='no_compensation': rows[2]['config_diff'].pop('hyde')
                with self.assertRaises(ValueError):validate_round_contract(rows, {'generation_thinking':'max'}, [])

    def test_gate_harming_change_cannot_repeat(self):
        prior=[{'config':{'candidate_k':24},'reasoning':{'changed_parameters':{'candidate_k':24}},'result':{'gates':{'gates':[{'id':'quality','passed':False}]}},'status':'evaluated'}]
        with self.assertRaises(ValueError):validate_round_contract(self.proposals(), {'generation_thinking':'max'}, prior)


class AgentRetryTests(unittest.TestCase):
    def test_stub_rejection_retries_once_without_sandbox_budget(self):
        import json
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from app.governance import GovernanceStore
        from app.optimization import OptimizationAgent
        from identity_fixture import completed_baseline
        from test_optimization_contract import trace_case
        from diagnostic_fixture import retrieval_case
        proposals=RoundContractTests().proposals()
        for row in proposals:
            row.update(review_conclusion_ids=['L1'],hypothesis=row['id'],why='保存证据',target_bad_cases=['Q1'],expected_improvement='修好Q1',risk='耗时')
        class Stub:
            def __init__(self):self.calls=[]
            def complete(self,system,user,**kwargs):
                self.calls.append(json.loads(user))
                from test_optimization_contract import drafts
                return json.dumps({'prior_round_review':drafts()['prior_round_review'],'candidates':proposals if len(self.calls)>1 else proposals[:2]})
        with tempfile.TemporaryDirectory() as directory, patch('app.diagnostics._current_corpus',return_value=(retrieval_case()[1],{'corpus':'one'})):
            store=GovernanceStore(Path(directory)/'test.db')
            completed_baseline(store,run_id='EVAL-test')
            store.record_bad_case('EVAL-test','Q1','Retrieval','ordinary',trace_case())
            provider=Stub()
            result=OptimizationAgent(store,provider).generate('EVAL-test')
            self.assertEqual(len(provider.calls),2)
            self.assertIn('恰好',provider.calls[1]['validation_rejection']['reason'])
            self.assertEqual(len(result['candidates']),3)
            self.assertEqual(result['evaluation_budget']['used'],0)
            self.assertEqual(result['candidates'][2]['config']['generation_thinking'],'high')
            self.assertEqual(result['candidates'][2]['reasoning']['direction'],'效率（降档 + 检索补偿）')


class CompositeEfficiencyTests(unittest.TestCase):
    def test_gate_safe_efficiency_without_fixed_question_enters_d_sources(self):
        import json
        import tempfile
        from pathlib import Path
        from app.governance import GovernanceStore
        from app.policy import DEFAULT_PIPELINE_CONFIG
        from identity_fixture import completed_baseline, comparison_identity
        class Stub:
            def complete(self,system,user,**kwargs):
                self.system=system
                self.prompt=json.loads(user)
                return json.dumps({'source_reasons':{self.prompt['winner']['id']:'保留单参数质量改善',self.prompt['sources'][0]['id']:'保留效率整组'},'should_generate_d':True,'source_candidates':[self.prompt['winner']['id'], self.prompt['sources'][0]['id']],
                    'proposed_config_diff':{'generation_thinking':'off','hyde':True},
                    'hypothesis':'检索补偿支持降档','root_cause':'生成层问题','intervention_direction':'stage_performance',
                    'evidence_assertions':[{'target_id':'Q1','observation':'final_sufficient'}],
                    'root_cause_alignment':'相同题卷','complementary_capabilities':'降档与检索补偿',
                    'expected_improvement':'降低耗时','risks':'质量','explanation':'合并已验证的质量与效率改动'})
        with tempfile.TemporaryDirectory() as directory:
            store=GovernanceStore(Path(directory)/'demo.db')
            baseline=completed_baseline(store)
            with store.connection() as connection:
                config=store.evaluation_run(baseline)['config'] | {'generation_thinking':'max'}
                connection.execute('UPDATE evaluation_runs SET config_json=? WHERE id=?',(json.dumps(config),baseline))
            experiment=store.create_experiment(baseline)
            for label,diff,direction,fixed in (
                ('A',{'top_k':6},'排序与过滤',['Q1']),
                ('B',{'generation_thinking':'off','hyde':True},'效率（降档 + 检索补偿）',[]),
            ):
                store.save_candidate(experiment,label,{**DEFAULT_PIPELINE_CONFIG,'generation_thinking':'max',**diff},
                    {'round':1,'candidate_label':label,'direction':direction,'changed_parameters':diff,
                     'observed_evidence':['Q1'],'hypothesis':'保存证据支持改动','proposal':'组合质量与效率','risk':'质量','expected_improvement':'质量或耗时改善',
                     'unstable_cases':['Q1'],'review_pending_cases':['Q1']})
                store.finish_candidate(experiment+'-'+label,'evaluated',{**comparison_identity(store,baseline),
                    'qualification':{'qualified':label=='A'},'gates':{'passed':True},
                    'regression':{'passed':True,'new_critical_failures':0,'new_ordinary_failures':1,
                                  'fluctuation_question_ids':['Q1'],'pending_regression_question_ids':['Q1'],
                                  'regression_interpretation':'不稳定题 / 随机波动 / 复核未完成'},
                    'all_fixed_question_ids':fixed})
            store.confirm_experiment_report(experiment,experiment+'-A','fixture')
            provider=Stub()
            composite=store.create_composite(experiment,provider,True)
            self.assertEqual([row['id'] for row in provider.prompt['sources']],[experiment+'-B'])
            self.assertEqual(composite['status'],'generated',composite)
            self.assertEqual(composite['config']['generation_thinking'],'off')
            self.assertEqual(composite['config']['top_k'],6)
            self.assertTrue(composite['config']['hyde'])
            self.assertIn(experiment+'-B',[s['candidate_id'] for s in composite['reasoning']['sources']])
            for field in ('unstable_cases','review_pending_cases','fluctuation_question_ids',
                          'pending_regression_question_ids','不稳定题','随机波动','复核未完成'):
                self.assertNotIn(field,json.dumps(provider.prompt,ensure_ascii=False))
            self.assertEqual(provider.prompt['bad_cases'][0]['category'],'生成层问题')
            for category in ('检索层问题','生成层问题','安全边界问题','性能问题'):
                self.assertIn(category,provider.system)
