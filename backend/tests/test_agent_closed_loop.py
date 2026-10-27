"""Offline regression for admission versus executable action; no live Provider."""
import unittest
from copy import deepcopy
from unittest.mock import patch
from test_diagnostic_evidence import example
import test_optimization_contract as contracts
FixedProvider=contracts.FixedProvider
from app.optimization import OptimizationAgent, validate_intervention
from app.diagnostic_evidence import context_selection_options
from app.policy import DEFAULT_PIPELINE_CONFIG


class ClosedLoopTests(unittest.TestCase):
    setUp=contracts.OptimizationContractTests.setUp
    def test_all_business_fails_reach_agent_even_without_diagnosis(self):
        case,_=example()
        case['judge_result']['checks'][0].pop('candidate_support')
        case['judge_result']['checks'][0].pop('scope_resolved')
        self.store.record_bad_case('EVAL-test','new-missing-diagnosis','Unknown','ordinary',case)
        provider=FixedProvider('{"candidates":[],"insufficient_evidence":"先完成系统诊断任务"}')
        result=OptimizationAgent(self.store,provider).generate('EVAL-test')
        self.assertEqual(len(provider.prompt['bad_cases']),2)
        tasks=result['result']['diagnostic_tasks']
        self.assertTrue(any(t['question_id']=='new-missing-diagnosis' for t in tasks))
        self.assertIn('new-missing-diagnosis',provider.prompt['target_reference_map'])
        self.assertFalse(self.store.candidates())

    def test_pass_is_not_an_agent_target_even_with_old_technical_flag(self):
        case,_=example()
        case['evaluation_outcome']={'contract_version':'business-vnext-1','execution_complete':True,'verdict':'PASS'}
        case['passed']=True
        self.store.record_bad_case('EVAL-test','old-pass','Ranking','ordinary',case)
        provider=FixedProvider('{"candidates":[],"insufficient_evidence":"offline"}')
        from app.diagnostics import diagnostic_view
        def stale_view(case):
            return {**diagnostic_view(case),'target_eligible':True}
        with patch('app.optimization.diagnostic_view',side_effect=stale_view):
            OptimizationAgent(self.store,provider).generate('EVAL-test')
        self.assertNotIn('old-pass',[c['question_id'] for c in provider.prompt['bad_cases']])


class ActionContractTests(unittest.TestCase):
    def test_evidence_backed_two_stage_dependency_is_executable(self):
        case,_=example()
        view={'target_eligible':True,'primary_root_cause':'Retrieval','trace_observations':['recall_missing','ranking_omission']}
        proposal={'intervention_direction':'candidate_recall','supporting_directions':['context_selection'],
            'target_bad_cases':['new-case'],'root_cause':'Retrieval','config_diff':{'candidate_k':24,'top_k':6},
            'parameter_dependencies':[{'parameters':['candidate_k','top_k'],'reason':'扩大候选同时为缺失的多段规范留上下文；全集验证'}],
            'evidence_assertions':[{'target_id':'new-case','observation':o} for o in view['trace_observations']],
            'hypothesis':'补全多段规范','why':'候选与Final分别有已核验缺口','expected_improvement':'必要事实覆盖增加','risk':'噪声及延迟'}
        with patch('app.optimization.diagnostic_view',return_value=view):
            validate_intervention(proposal,{'new-case':case},DEFAULT_PIPELINE_CONFIG)
            bad=deepcopy(proposal);bad['evidence_assertions']=bad['evidence_assertions'][:1]
            with self.assertRaises(ValueError):validate_intervention(bad,{'new-case':case},DEFAULT_PIPELINE_CONFIG)

    def test_query_only_ranking_reads_only_query_and_saved_pool(self):
        from app.retrieval import query_only_order
        hits=[{'chunk_id':'a','content':'充电器检查','score':1.}, {'chunk_id':'b','content':'地图桌椅布局变化重新示教','score':.1}]
        before=deepcopy(hits)
        self.assertEqual(query_only_order('桌椅布局变化',hits)[0]['chunk_id'],'b')
        self.assertEqual(hits,before)
        self.assertTrue(all(h['score']==0 for h in query_only_order('unrelated',hits)))

    def test_only_verified_supplement_can_be_omitted(self):
        case,chunks=example();required,extra=chunks
        noise=[{**extra,'chunk_id':f'n{i}','content':'目录','score':.5} for i in range(7)]
        required={**required,'score':.5};extra={**extra,'score':.5}
        trace={'config':{'top_k':4,'rerank':True,'min_score':0},'candidates':[required,*noise,extra],'reranked':[*noise,required,extra],'final':[]}
        checks=[{'met':True,'support':[{'source_id':extra['chunk_id'],'quote':extra['content']}]}]
        finding=('Ranking',None,{'candidate_support':[{'source_id':required['chunk_id'],'quote':required['content']}],
             'supplemental_check_indices':[0]})
        options,_=context_selection_options(trace,[finding],chunks,checks)
        self.assertIn({'rerank':False},options)
        finding[2].pop('supplemental_check_indices')
        options,_=context_selection_options(trace,[finding],chunks,checks)
        self.assertNotIn({'rerank':False},options)

class EvidenceReuseTests(unittest.TestCase):
    def test_observation_identity_ignores_rescore_but_not_execution(self):
        from app.evidence_resolver import observation_identity
        from test_evidence_resolver_v5 import ResolverTests
        q,c,chunks,hit,identity=ResolverTests().example()
        original=observation_identity(c,q,chunks,identity)
        another=deepcopy(c);another['judge_result']['checks'].reverse();another['run_id']='replay'
        changed={**identity,'run_id':'replay','evaluation_identity':'new-scoring','snapshot_sha256':'new-snapshot'}
        self.assertEqual(original,observation_identity(another,q,chunks,changed))
        another['model_answer']='changed answer'
        self.assertNotEqual(original,observation_identity(another,q,chunks,changed))

class LifecycleTests(unittest.TestCase):
    setUp=contracts.OptimizationContractTests.setUp
    run_drafts=contracts.OptimizationContractTests.run_drafts
    def test_qualified_candidate_does_not_end_processing_remaining_cases(self):
        result=self.run_drafts(__import__('test_optimization_contract').drafts())[0]
        with self.store.connection() as connection:
            connection.execute("UPDATE candidate_configs SET status='evaluated',result_json=? WHERE experiment_id=?",('{"qualification":{"qualified":true},"bad_case_count":2}',result['id']))
        _,prior,round_number,used,token=self.store.claim_agent_generation('EVAL-test',experiment_id=result['id'])
        self.assertEqual(round_number,2)
        self.assertEqual(len(prior),3)
        self.store.save_agent_round(result['id'],[],{},generation_token=token)

class CompositionTests(unittest.TestCase):
    def test_d_composes_verified_different_stages_then_still_needs_sandbox(self):
        import json
        from test_evaluation_context import CompositeTests
        from test_optimization_contract import drafts
        fixture=CompositeTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        store=fixture.store
        proposals=drafts()['candidates']
        for candidate_id,proposal,diff in [(fixture.winner['id'],proposals[2],{'candidate_k':24}), (fixture.other['id'],proposals[0],{'top_k':6})]:
            reasoning={**proposal,'candidate_label':'A' if candidate_id==fixture.winner['id'] else 'B','round':1,
                'observed_evidence':['q'],'proposal':proposal['why'],'evidence_assertions':[{'target_id':'q','observation':'recall_missing' if 'candidate_k' in diff else 'ranking_omission'}]}
            with store.connection() as connection:
                connection.execute('UPDATE candidate_configs SET config_json=?,reasoning_json=? WHERE id=?',(json.dumps({**DEFAULT_PIPELINE_CONFIG,**diff}),json.dumps(reasoning),candidate_id))
        provider=fixture.provider(diff={'top_k':6})
        result=store.create_composite(fixture.experiment,provider,True)
        self.assertEqual(result['status'],'generated',result)
        self.assertEqual(result['config']['candidate_k'],24)
        self.assertEqual(result['config']['top_k'],6)
        self.assertFalse(result['result'].get('qualification',{}).get('qualified',False))

class BatchAndReplayTests(unittest.TestCase):
    def setup_saved(self,extra_check=False):
        import tempfile,os
        from pathlib import Path
        from app.governance import GovernanceStore
        from test_evidence_resolver_v5 import ResolverTests
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        patcher=patch.dict(os.environ,{'RAG_DIAGNOSTIC_DIR':temporary.name+'/evidence','RAG_DEMO_DB_PATH':temporary.name+'/isolated.db'})
        patcher.start();self.addCleanup(patcher.stop)
        fixture=ResolverTests();q,c,chunks,hit,identity=fixture.example()
        store=GovernanceStore(Path(temporary.name)/'isolated.db')
        snapshot={'id':'fresh-gd','questions':[q],'question_ids':[q['id']],'corpus_fingerprint':'new-corpus'}
        run=store.create_evaluation_run(snapshot,{'top_k':4},{'evaluation_identity':'new-eval'})
        if extra_check:c['judge_result']['checks'].append({'requirement':'目录补充','met':True,'answer_quotes':[],'support':[]})
        store.record_evaluation_case(run,q['id'],c)
        return store,run,snapshot,q,c,chunks,fixture

    def test_rescore_reorders_checks_and_reuses_only_observation(self):
        from app.evidence_resolver import resolve_persisted
        store,run,snapshot,q,c,chunks,fixture=self.setup_saved(extra_check=True)
        def omitted(payload):
            response=fixture.semantic(payload);response.pop('check_roles');return response
        self.assertIn('preservation_check_roles_incomplete',resolve_persisted(store,run,q['id'],chunks,'new-corpus',semantic=omitted)['blockers'])
        first=resolve_persisted(store,run,q['id'],chunks,'new-corpus',semantic=fixture.semantic,persist=True)
        self.assertEqual(first['status'],'resolved')
        another=store.create_evaluation_run(snapshot,{'top_k':4},{'evaluation_identity':'different-judge'})
        changed=deepcopy(c);changed['judge_result']['checks'].reverse()
        store.record_evaluation_case(another,q['id'],changed)
        reused=resolve_persisted(store,another,q['id'],chunks,'new-corpus')
        self.assertEqual(reused['status'],'resolved')
        self.assertEqual(reused['findings'][0][2]['check_index'],1)
        self.assertEqual(reused['reused_observation_from']['run_id'],run)
        changed['judge_result']['checks'][1]['requirement']='新增的必要安全条件'
        third=store.create_evaluation_run(snapshot,{'top_k':4},{'evaluation_identity':'third-judge'})
        store.record_evaluation_case(third,q['id'],changed)
        self.assertEqual(resolve_persisted(store,third,q['id'],chunks,'new-corpus')['status'],'needs_semantic')

    def test_same_request_cannot_repeat_after_technical_failure(self):
        from app.evidence_resolver import resolve_persisted
        store,run,snapshot,q,c,chunks,fixture=self.setup_saved()
        calls=[]
        def broken(payload):calls.append(True);raise ValueError('invalid semantic output')
        for _ in range(2):
            result=resolve_persisted(store,run,q['id'],chunks,'new-corpus',semantic=broken,persist=True)
            self.assertEqual(result['status'],'blocked')
        self.assertEqual(len(calls),1)

    def test_batch_needs_budget_and_validates_scope_before_calls(self):
        from app.evidence_resolver import resolve_batch
        store,run,snapshot,q,c,chunks,fixture=self.setup_saved()
        with self.assertRaisesRegex(ValueError,'PaidRun'):
            resolve_batch(store,run,[q['id']],chunks,'new-corpus',semantic=fixture.semantic,max_calls=1,persist=True)
        result=resolve_batch(store,run,[q['id']],chunks,'new-corpus')
        self.assertEqual(result['calls_attempted'],0)
        self.assertEqual(result['results'][0]['status'],'needs_semantic')

    def test_budget_exhaustion_is_unfinished_and_not_a_business_fix(self):
        from app.evidence_resolver import resolve_persisted
        store,run,snapshot,q,c,chunks,fixture=self.setup_saved()
        def exhausted(payload):raise RuntimeError('Payment budget insufficient')
        result=resolve_persisted(store,run,q['id'],chunks,'new-corpus',semantic=exhausted,persist=True)
        self.assertEqual(result['status'],'blocked')
        self.assertFalse(result['findings'])

    def test_identity_drift_after_response_stops_batch(self):
        from app.evidence_resolver import resolve_batch
        from types import SimpleNamespace
        store,run,snapshot,q,c,chunks,fixture=self.setup_saved()
        ledger=SimpleNamespace(path=store.database_path.parent/'offline-authorized.json',identity={'key':'before'},identity_check=lambda:{'key':'after'},calls=[],stopped=None)
        with patch('app.paid_run.current_paid_run',return_value=ledger):
            result=resolve_batch(store,run,[q['id']],chunks,'new-corpus',semantic=fixture.semantic,max_calls=1,persist=True)
        self.assertEqual(result['results'][0]['status'],'blocked')
        self.assertFalse(result['results'][0]['findings'])

    def test_source_preflight_does_not_turn_negative_anchor_into_answer(self):
        from app.canonical_evidence import optimization_preflight
        store,run,snapshot,q,c,chunks,fixture=self.setup_saved()
        q.update(test_category='negative',expected_behavior='safe_rejection')
        result=optimization_preflight(q,chunks)
        self.assertTrue(result['ready'])
        self.assertEqual(result['source_roles'],['material_anchor_only'])
        chunks[0]['chunk_text']=''
        self.assertFalse(optimization_preflight(q,chunks)['ready'])

class FourDirectionTests(unittest.TestCase):
    def test_new_behavior_failure_and_measured_performance_have_real_actions(self):
        from app.diagnostics import diagnostic_view
        for root in ['Safety','Performance']:
            c,chunks=example();c['question_id']='fresh-'+root
            if root=='Safety':
                c['test_category']='negative';c['negative_subtype']='prompt_injection'
                c['judge_result']['checks']=[{'requirement':'拒绝越权指令','check_type':'negative_behavior','met':False,'answer_quotes':[c['model_answer']],'support':[]}]
            else:
                c['programmatic_metrics'].update(latency_ms=70000,stages=[{'stage_name':'generation','duration_ms':65000}])
            view=diagnostic_view(c,corpus_chunks=chunks,corpus_fingerprint='isolated')
            self.assertEqual(view['primary_root_cause'],root,view)
            self.assertTrue(view['target_eligible'])
            proposal={'target_bad_cases':[c['question_id']],'root_cause':root,
                'intervention_direction':'grounded_generation' if root=='Safety' else 'stage_performance',
                'performance_stage':'generation','config_diff':{'prompt_strategy':'Abstention' if root=='Safety' else 'Completeness'},
                'evidence_assertions':[{'target_id':c['question_id'],'observation':'safety_failure' if root=='Safety' else 'measured_latency'}],
                'parameter_dependencies':[],'hypothesis':'验证已定位失败','why':'真实回答/阶段记录','expected_improvement':'完整题集验证','risk':'误拒答、越界与质量回归'}
            with patch('app.optimization.diagnostic_view',return_value=view):
                validate_intervention(proposal,{c['question_id']:c},DEFAULT_PIPELINE_CONFIG)
