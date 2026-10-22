"""Offline admission tests: hypotheses are not confirmed root causes."""
import json
import os
import unittest
from copy import deepcopy
from unittest.mock import patch
from app.diagnostics import diagnostic_view
from app.optimization import validate_intervention, OptimizationAgent
from app.policy import DEFAULT_PIPELINE_CONFIG
import test_evidence_resolver_v5 as resolver_fixture
import test_optimization_contract as contracts


def example(stage='recall'):
    q,c,chunks,hit,_=resolver_fixture.ResolverTests().example()
    c.pop('run_id',None)
    c['judge_result'].update(verdict='FAIL',issues=[],reason='fixture incomplete answer')
    c['judge_result']['checks'][0]['check_type']='fact'
    c['programmatic_metrics']['evidence_coverage']={'required_chunk_ids':[hit['chunk_id']]}
    c['programmatic_metrics']['retrieval_trace']['config']=deepcopy(DEFAULT_PIPELINE_CONFIG)
    if stage in {'context','answer'}:
        for key in ['candidates','reranked']:c['programmatic_metrics']['retrieval_trace'][key].append(hit)
    if stage=='answer':c['programmatic_metrics']['retrieval_trace']['final'].append(hit)
    return q,c,chunks


def proposal(c, direction='candidate_recall', observation='candidate_pool_gap', diff=None):
    return {'target_bad_cases':[c['question_id']],'root_cause':'Unknown','experiment_kind':'exploratory',
        'intervention_direction':direction,'config_diff':diff or {'candidate_k':24},'supporting_directions':[],
        'evidence_assertions':[{'target_id':c['question_id'],'observation':observation}], 'parameter_dependencies':[],
        'hypothesis':'候选池扩展可能补全冻结规范；尚未证明根因','why':'冻结规范来源未进入当前候选池',
        'expected_improvement':'验证失败要求覆盖改善','risk':'噪声和延迟增加',
        'falsification':'相同冻结50题中目标仍FAIL或新增安全失败则不能推荐'}


class ExplorationTests(unittest.TestCase):
    def test_unknown_has_falsifiable_plan_and_legal_candidate(self):
        q,c,chunks=example()
        with patch('app.diagnostics._current_corpus',return_value=(chunks,'new-corpus')):
            view=diagnostic_view(c)
            self.assertEqual(view['primary_root_cause'],'Unknown')
            self.assertFalse(view['target_eligible'])
            self.assertEqual(view['experiment_plan']['status'],'exploratory')
            self.assertIn('candidate_pool_gap',view['experiment_plan']['observations'])
            validate_intervention(proposal(c),{q['id']:c},DEFAULT_PIPELINE_CONFIG)

    def test_exploration_cannot_invent_cause_or_change_unobserved_stage(self):
        q,c,chunks=example()
        with patch('app.diagnostics._current_corpus',return_value=(chunks,'new-corpus')):
            for change in [{'root_cause':'Retrieval'}, {'experiment_kind':'confirmed'}, {'falsification':''},
                           {'intervention_direction':'grounded_generation','config_diff':{'prompt_strategy':'Completeness'}}]:
                p={**proposal(c),**change}
                with self.subTest(change=change),self.assertRaises(ValueError):validate_intervention(p,{q['id']:c},DEFAULT_PIPELINE_CONFIG)

    def test_context_and_generation_explore_without_claiming_semantic_sufficiency(self):
        for stage,direction,observation,diff in [('context','context_selection','context_pool_gap',{'top_k':6}),
                ('answer','grounded_generation','answer_requirement_gap',{'prompt_strategy':'Completeness'})]:
            q,c,chunks=example(stage)
            with patch('app.diagnostics._current_corpus',return_value=(chunks,'new-corpus')):
                self.assertFalse(diagnostic_view(c)['target_eligible'])
                validate_intervention(proposal(c,direction,observation,diff),{q['id']:c},DEFAULT_PIPELINE_CONFIG)

    def test_missing_source_and_invalid_judge_are_repair_tasks_not_parameter_candidates(self):
        for broken in ['source','judge','trace','identity']:
            q,c,chunks=example()
            if broken=='source':chunks=chunks[1:]
            if broken=='judge':c['judge_result']['checks'][0]['support']=[{'source_id':'invented','quote':'made up'}]
            if broken=='trace':c['programmatic_metrics']['retrieval_trace'].pop('reranked')
            if broken=='identity':c['programmatic_metrics']['retrieval_trace']['corpus_fingerprint']='changed'
            with patch('app.diagnostics._current_corpus',return_value=(chunks,'new-corpus')):
                plan=diagnostic_view(c)['experiment_plan']
                self.assertEqual(plan['status'],'capability_gap',plan)
                self.assertTrue(plan['next_action'])
                with self.assertRaises(ValueError):validate_intervention(proposal(c),{q['id']:c},DEFAULT_PIPELINE_CONFIG)


class AgentExplorationTests(unittest.TestCase):
    setUp=contracts.OptimizationContractTests.setUp
    def test_unknown_is_persisted_as_exploration_instead_of_repeated_paid_diagnosis(self):
        q,c,chunks=example();c['question_id']='Q1'
        self.store.record_bad_case('EVAL-test','Q1','Unknown','ordinary',c)
        p=proposal(c);p.update(id='A',target_group='offline',root_cause_evidence=['Q1'])
        provider=contracts.FixedProvider(json.dumps({'candidates':[p],'insufficient_evidence':'one coherent hypothesis'}))
        with patch.dict(os.environ,{'RAG_DEMO_DB_PATH':str(self.store.database_path)}),patch('app.diagnostics._current_corpus',return_value=(chunks,'new-corpus')):
            result=OptimizationAgent(self.store,provider).generate('EVAL-test')
        self.assertEqual(result['result']['diagnostic_tasks'][0]['status'],'exploratory')
        self.assertEqual(len(result['candidates']),1)
        self.assertEqual(result['candidates'][0]['reasoning']['experiment_kind'],'exploratory')
        self.assertEqual(result['candidates'][0]['reasoning']['root_cause'],'Unknown')

class TraceCompletenessTests(unittest.TestCase):
    def test_local_pipeline_records_real_rerank_before_threshold_and_completed_status(self):
        from types import SimpleNamespace
        from app.retrieval import VectorRetriever
        chunks=[{'chunk_id':f'chunk-{i}','chunk_text':'维护手册','document_id':'d'} for i in range(8)]
        r=VectorRetriever(SimpleNamespace(chunks=lambda:chunks))
        r.vector_candidates=lambda *a,**kw:[{'chunk_id':c['chunk_id'],'score':1-i/10} for i,c in enumerate(chunks)]
        trace={};result=r.retrieve('维护',DEFAULT_PIPELINE_CONFIG,trace=trace)
        self.assertEqual(trace['status'],'completed')
        self.assertEqual(len(trace['reranked']),8)
        self.assertEqual([h['chunk_id'] for h in result],[h['chunk_id'] for h in trace['final']])

class ProgressTests(unittest.TestCase):
    setUp=contracts.OptimizationContractTests.setUp
    def test_repairs_from_different_configurations_are_never_added(self):
        self.store.record_bad_case('EVAL-test','Q2','Retrieval','ordinary',contracts.trace_case())
        exp=OptimizationAgent(self.store,contracts.FixedProvider(json.dumps(contracts.drafts()))).generate('EVAL-test')
        for candidate,ids in zip(exp['candidates'],[['Q1'],['Q2'],[]]):
            self.store.finish_candidate(candidate['id'],'evaluated',{'qualification':{'qualified':bool(ids)},'all_fixed_question_ids':ids,'bad_case_count':1})
        next_round=OptimizationAgent(self.store,contracts.FixedProvider(json.dumps({'candidates':[],'insufficient_evidence':'offline new hypothesis pending'}))).generate('EVAL-test',experiment_id=exp['id'])
        progress=next_round['result']['processing_progress']
        self.assertEqual(len(progress['fixed_question_ids']),1)
        self.assertEqual(len(progress['remaining_question_ids']),1)
        self.assertIn(progress['verified_configuration_id'],[c['id'] for c in exp['candidates'][:2]])
