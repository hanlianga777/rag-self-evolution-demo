"""Inheritance and bounded proposal recovery; disposable databases and Mock calls only."""
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.diagnostics import diagnostic_view
from app.governance import GovernanceStore
from app.optimization import prepare_response, ProposalValidationExhausted
from app.policy import DEFAULT_PIPELINE_CONFIG
from identity_fixture import completed_baseline, comparison_identity
from test_optimization_contract import drafts, trace_case


class InheritanceTests(unittest.TestCase):
    def setUp(self):
        self.base = dict(DEFAULT_PIPELINE_CONFIG)
        self.inherited = {'retrieval_max_tokens':8192,'generation_thinking':'high'}
        self.prior = [{'id':'R1-A','status':'evaluated','config':{**self.base, **self.inherited},
                       'reasoning':{'round':1,'candidate_label':'A','changed_parameters':self.inherited},
                       'result':{'qualification':{'qualified':True}}}]
        case = trace_case()
        self.bad = [{'id':'BC-Q1','question_id':'Q1','result':case,'diagnostic_view':diagnostic_view(case)}]
        self.response = drafts()
        self.response['prior_round_review'].update(summary='历史A合格', plans=[{
            'candidate_id':'R1-A','changes':self.inherited,'fixed_question_ids':[], 'new_failure_question_ids':[],
            'evidence_reason':'保存结果','conclusion':'合格','most_likely_parameter':'未知','attribution_reason':'无法单独确定'}])
        self.response['bad_case_summary'] = {'groups':[],'focus':'召回','conclusions':[{'id':'B1','conclusion':'保存事实'}]}
        for c in self.response['candidates']:
            c['config_diff'].pop('generation_thinking',None)
            c.update(inherited_from='R1-A',inherited_parameters=self.inherited,
                     changed_parameters=c.pop('config_diff'),bad_case_conclusion_ids=['B1'],predicted_fixed_question_ids=['Q1'],
                     risks=[{'question_ids':[],'metric':'latency_p99_seconds','reason':'耗时风险'}])
            c['adjustments']=[{'parameter':k,'baseline_value':self.base[k],'candidate_value':v,'expected_impact':'预计修好Q1'} for k,v in c['changed_parameters'].items()]
        self.audit = {'strategy_contract':'agent-strategy-4','round_policy':{'mode':'full_rounds'},'bad_case_groups':[]}

    def prepare(self, raw=None):
        return prepare_response(raw if raw is not None else json.dumps(self.response),self.base,self.bad,self.prior,3,2,list('ABC'),None,[],self.audit)

    def test_shared_inheritance_and_final_config_and_adjustments(self):
        _, batch = self.prepare()
        self.assertEqual(len(batch),3)
        for (_, config, reasoning), c in zip(batch,self.response['candidates']):
            self.assertEqual(config,{**self.base,**self.inherited,**c['changed_parameters']})
            self.assertEqual(reasoning['changed_parameters'],c['changed_parameters'])
            self.assertEqual(reasoning['changed_parameters_vs_baseline'],{**self.inherited,**c['changed_parameters']})
            self.assertEqual(reasoning['inherited_from'],'R1-A')
            self.assertEqual(reasoning['adjustments'],c['adjustments'])

    def test_reject_unknown_unqualified_later_source_or_wrong_value(self):
        for kind in ('unknown','unqualified','later','value','type','extra'):
            with self.subTest(kind=kind):
                test = InheritanceTests(); test.setUp()
                if kind=='unknown':test.response['candidates'][0]['inherited_from']='missing'
                elif kind=='unqualified':test.prior[0]['result']['qualification']['qualified']=False
                elif kind=='later':test.prior[0]['reasoning']['round']=2
                elif kind=='value':test.response['candidates'][0]['inherited_parameters']={'retrieval_max_tokens':4096}
                elif kind=='type':test.response['candidates'][0]['inherited_parameters']={'retrieval_max_tokens':True}
                else:test.response['candidates'][0]['inherited_parameters']={'top_k':6}
                with test.assertRaises(ValueError):test.prepare()

    def test_new_change_can_tune_inherited_parameter_against_inherited_base(self):
        c=self.response['candidates'][0]
        c['changed_parameters']={'retrieval_max_tokens':4096}
        c['adjustments']=[{'parameter':'retrieval_max_tokens','baseline_value':8192,'candidate_value':4096,'expected_impact':'预计修好Q1'}]
        _, batch=self.prepare()
        self.assertEqual(batch[0][1]['retrieval_max_tokens'],4096)
        self.assertEqual(batch[0][2]['changed_parameters_vs_baseline']['retrieval_max_tokens'],4096)

    def test_reject_repeated_config_overlap_new_changes_and_wrong_adjustment(self):
        for kind in ('duplicate','overlap','range','missing_prediction'):
            with self.subTest(kind=kind):
                test=InheritanceTests();test.setUp()
                if kind=='duplicate':test.prior.append({'id':'R1-B','status':'evaluated','config':{**test.base,**test.inherited,'top_k':6},'reasoning':{},'result':{}});test.response['prior_round_review']['plans'].append({**test.response['prior_round_review']['plans'][0],'candidate_id':'R1-B','changes':{'top_k':6}})
                elif kind=='overlap':test.response['candidates'][1]['changed_parameters']={'top_k':8}
                elif kind=='adjustment':test.response['candidates'][0]['adjustments'][0]['baseline_value']=99
                elif kind=='range':test.response['candidates'][0]['changed_parameters']={'top_k':999}
                else:test.response['candidates'][0].pop('predicted_fixed_question_ids')
                with test.assertRaises(ValueError):test.prepare()

    def test_wrong_adjustment_baseline_value_is_repaired_to_truth(self):
        # 055 起：调整项里写错的基线值按程序真值规整（记入 normalized_fields），不再让整轮规划失败。
        self.response['candidates'][0]['adjustments'][0]['baseline_value']=99
        _, batch=self.prepare()
        self.assertNotEqual(batch[0][2]['adjustments'][0]['baseline_value'],99)

    def test_missing_closing_brackets_only_repaired_with_audit(self):
        raw=json.dumps(self.response)
        _,batch=self.prepare(raw[:-2])
        self.assertEqual(len(batch),3)
        self.assertEqual(self.audit['syntax_repair'],{'appended':raw[-2:],'original_length':len(raw)-2})
        self.assertEqual(self.audit['parsed_json'],self.response)

    def test_braces_inside_strings_escaped_quotes_and_nested_arrays(self):
        self.response['extra']=['literal { [ \\" \\ string',{'x':[1]}]
        raw=json.dumps(self.response)
        self.prepare(raw[:-3])
        self.assertEqual(self.audit['parsed_json'],self.response)

    def test_content_errors_truncated_string_and_mismatched_brackets_rejected(self):
        for raw in ('{"candidates":[,', '{"candidates":[}', '{"x":"unfinished', '{"x":1,', '{"x":NaN', '{"x":1,"x":2'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):self.prepare(raw)

    def test_legacy_without_inheritance_unchanged(self):
        response=drafts();audit={}
        _, batch=prepare_response(json.dumps(response),self.base,self.bad,[],0,1,list('ABC'),None,[],audit)
        self.assertEqual(len(batch),3)
        self.assertNotIn('inherited_parameters',batch[0][2])
        self.assertEqual(batch[0][2]['changed_parameters'],{'top_k':6})
        self.audit.pop('round_policy')
        with self.assertRaises(ValueError):self.prepare()

    def test_prompt_explains_inheritance_without_recommended_values(self):
        from app.optimization import build_agent_prompt
        system,prompt=build_agent_prompt([],self.base,self.prior,[],list('ABC'),round_policy={'mode':'full_rounds'})
        self.assertIn('inherited_from',system)
        self.assertIn('changed_parameters',system)
        self.assertIn('基线参数',system)
        self.assertEqual(prompt['prior_sandbox_results'][0]['changed_parameters'],self.inherited)


class SavedGenerationTests(unittest.TestCase):
    def test_four_refusals_keep_raw_audit_and_fresh_batch_uses_distinct_requests(self):
        from app.optimization import OptimizationAgent
        from test_optimization_contract import OptimizationContractTests
        fixture=OptimizationContractTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        store=fixture.store
        exp=store.create_experiment('EVAL-test')
        with store.connection() as db:
            db.execute('UPDATE experiments SET result_json=json_set(result_json,\'$.round_policy\',json(?)) WHERE id=?',
                       (json.dumps({'mode':'full_rounds','max_rounds':3}),exp))
        from app.paid_schedule import set_settings
        set_settings(store,False)
        class Provider:
            calls=[]
            def complete(provider, system, user, **kwargs):
                provider.calls.append(json.loads(user))
                return '{"candidates":[]}'
        provider=Provider();agent=OptimizationAgent(store,provider)
        for number in range(3):
            with self.assertRaises(ProposalValidationExhausted):agent.generate('EVAL-test',experiment_id=exp)
            with store.connection() as db:
                state=json.loads(db.execute('SELECT result_json FROM experiments WHERE id=?',(exp,)).fetchone()[0])
                state['optimization_cycle']={'proposal_generation_failures':[{'round':1,'reason':'Mock拒绝','sandbox_budget_used':0} for _ in range(number+1)]}
                db.execute('UPDATE experiments SET result_json=? WHERE id=?',(json.dumps(state),exp))
        self.assertEqual(len(provider.calls),12)
        self.assertEqual([len(provider.calls[n]['proposal_generation']['prior_failed_batches']) for n in (0,4,8)],[0,1,2])
        with store.connection() as db:
            traces=[json.loads(r[0]) for r in db.execute('SELECT result_json FROM agent_traces WHERE experiment_id=?',(exp,))]
        self.assertEqual(len(traces),3)
        self.assertTrue(all(len(t['validation_retries'])==3 and t['provider_raw_text']=='{"candidates":[]}' for t in traces))
        self.assertEqual(store.experiment(exp)['evaluation_budget']['used'],0)

    def test_inherited_candidate_passes_sandbox_input_boundary_and_tamper_is_rejected(self):
        from app.evaluation import EvaluationRunner
        from test_optimization_contract import OptimizationContractTests
        from app.composite import pipeline_config
        fixture=OptimizationContractTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        store=fixture.store
        data=InheritanceTests();data.setUp()
        exp=store.create_experiment('EVAL-test')
        with store.connection() as db:
            db.execute('UPDATE experiments SET result_json=? WHERE id=?',(json.dumps({'round_policy':{'mode':'full_rounds'}}),exp))
        store.save_candidate(exp,'R1-A',data.prior[0]['config'],data.prior[0]['reasoning'])
        store.finish_candidate(exp+'-R1-A','evaluated',data.prior[0]['result'])
        # The serialized source ID is the actual saved Candidate ID.
        data.prior[0]['id']=exp+'-R1-A'
        data.response['prior_round_review']['plans'][0]['candidate_id']=exp+'-R1-A'
        for candidate in data.response['candidates']:candidate['inherited_from']=exp+'-R1-A'
        _,batch=data.prepare()
        for cid,config,reasoning in batch:store.save_candidate(exp,cid,config,reasoning)
        runner=EvaluationRunner(store,SimpleNamespace(provider=object(),model='fixture'))
        with patch.object(runner,'_require_generation_contract'), patch.object(runner,'snapshot_items', return_value=[]), patch('app.diagnostics.standard_evidence', return_value=trace_case()['standard_evidence']):
            approved,config,candidate,baseline=runner.candidate_inputs(exp+'-R2-A')
            self.assertEqual(pipeline_config(config),batch[0][1])
            with store.connection() as db:
                reasoning=json.loads(db.execute('SELECT reasoning_json FROM candidate_configs WHERE id=?',(exp+'-R2-A',)).fetchone()[0])
                reasoning['inherited_parameters']['retrieval_max_tokens']=4096
                db.execute('UPDATE candidate_configs SET reasoning_json=? WHERE id=?',(json.dumps(reasoning),exp+'-R2-A'))
            with self.assertRaises(ValueError):runner.candidate_inputs(exp+'-R2-A')


class ProposalCycleTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.store=GovernanceStore(Path(temp.name)/'test.db');completed_baseline(self.store,run_id='BASE')
        self.exp=self.store.create_experiment('BASE')
        from app.paid_schedule import set_settings,set_unattended_authorization
        set_settings(self.store,False);set_unattended_authorization(self.store,True,'用户')

    def run_cycle(self, full=True, qualified=True, succeeds=False):
        from app.optimization_cycle import run_until_qualified
        store,exp=self.store,self.exp;calls=[]
        with store.connection() as db:
            db.execute('update experiments set result_json=? where id=?',(json.dumps({'round_policy':{'mode':'full_rounds','max_rounds':3}} if full else {}),exp))
        store.save_candidate(exp,'R1-A',DEFAULT_PIPELINE_CONFIG,{'round':1,'candidate_label':'A'})
        store.finish_candidate(exp+'-R1-A','evaluated',{**comparison_identity(store,'BASE'),'evaluation_complete':True,'qualification':{'qualified':qualified},'bad_case_count':1})
        class Agent:
            def __init__(self,*a):pass
            def generate(self,*a,**kw):
                calls.append('generate')
                if succeeds and len(calls)==2:raise InterruptedError('second fresh round reached')
                raise ProposalValidationExhausted('Mock四次均拒绝')
        def composite(*a):
            if store.candidate(exp+'-D'):return store.candidate(exp+'-D')
            calls.append('D')
            with store.connection() as db:
                db.execute('INSERT INTO candidate_configs VALUES (?,?,?,?,?,?,?)', (exp+'-D',exp,'generated',json.dumps(DEFAULT_PIPELINE_CONFIG),'{"candidate_label":"D"}','{}','2026-11-14'))
            return store.candidate(exp+'-D')
        class Runner:
            def __init__(self,*a):pass
            def run_candidate(self,cid,**kw):
                calls.append('evaluate D')
                return store.finish_candidate(cid,'evaluated',{'qualification':{'qualified':False}})
        with patch('app.optimization_cycle.OptimizationAgent',Agent),patch('app.optimization_cycle.EvaluationRunner',Runner),patch('app.agent_strategy.conclude_round'),patch.object(store,'create_composite',side_effect=composite):
            state=run_until_qualified(store,SimpleNamespace(provider=object()),exp)
        return state,calls,store.experiment(exp)

    def test_full_rounds_retry_twice_then_gate2_d_before_release(self):
        state,calls,exp=self.run_cycle()
        self.assertEqual(calls,['generate']*3+['D','evaluate D'])
        self.assertEqual(state['status'],'recommended')
        self.assertEqual(state['phase'],'before_release')
        self.assertEqual(len(state['proposal_generation_failures']),3)
        self.assertIn('第 2 轮未能生成合法方案',state['proposal_round_end']['reason'])
        self.assertEqual(exp['evaluation_budget']['used'],2)  # R1 and D only; refusals use no Sandbox.
        self.assertEqual(exp['result']['report_confirmation']['actor'],'用户')
        with self.store.connection() as db:
            approvals=[dict(r) for r in db.execute('select * from approvals')]
            self.assertFalse(any(r['gate']=='human_release' for r in approvals))
            self.assertEqual(exp['result']['report_confirmation']['audit_note'],'用户 2026-11-16 预先授权')

    def test_fresh_retry_is_reached(self):
        state,calls,_=self.run_cycle(succeeds=True)
        self.assertEqual(calls,['generate','generate'])
        self.assertEqual(state['status'],'stopped')

    def test_without_qualified_still_exhausted(self):
        state,calls,_=self.run_cycle(qualified=False)
        self.assertEqual(calls,['generate']*3)
        self.assertEqual(state['status'],'analysis_exhausted')

    def test_legacy_exhausts_once_and_does_not_retry(self):
        state,calls,_=self.run_cycle(full=False,qualified=False)
        self.assertEqual(calls,['generate'])
        self.assertEqual(state['status'],'analysis_exhausted')
