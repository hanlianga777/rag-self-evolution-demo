"""Offline admission uses saved evidence and complete ABC rounds."""
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
    c.update(passed=False,standard_evidence=[q['reference_answer']])
    c['judge_result'].update(verdict='FAIL',issues=[],reason='fixture incomplete answer')
    c['judge_result']['checks'][0]['check_type']='fact'
    c['programmatic_metrics']['evidence_coverage']={'required_chunk_ids':[hit['chunk_id']]}
    c['programmatic_metrics']['retrieval_trace']['config']=deepcopy(DEFAULT_PIPELINE_CONFIG)
    if stage in {'context','answer'}:
        for key in ['candidates','reranked']:c['programmatic_metrics']['retrieval_trace'][key].append(hit)
    if stage=='answer':c['programmatic_metrics']['retrieval_trace']['final'].append(hit)
    return q,c,chunks


def proposal(c, direction='candidate_recall', observation='recall_missing', diff=None):
    return {'target_bad_cases':[c['question_id']],'root_cause':diagnostic_view(c)['primary_root_cause'],
        'intervention_direction':direction,'config_diff':diff or {'candidate_k':24},'supporting_directions':[],
        'evidence_assertions':[{'target_id':c['question_id'],'observation':observation}], 'parameter_dependencies':[],
        'hypothesis':'按保存证据验证参数调整','why':'冻结规范与保存检索记录存在覆盖差距',
        'expected_improvement':'验证失败要求覆盖改善','risk':'噪声和延迟增加',
        'falsification':'相同冻结50题中目标仍FAIL或新增安全失败则不能推荐'}


class ExplorationTests(unittest.TestCase):
    def test_saved_evidence_has_falsifiable_plan_without_current_corpus(self):
        q,c,chunks=example()
        with patch('app.diagnostics._current_corpus',side_effect=AssertionError('must use saved evidence')):
            view=diagnostic_view(c)
            self.assertEqual(view['primary_root_cause'],'Retrieval')
            self.assertTrue(view['target_eligible'])
            self.assertEqual(view['experiment_plan']['status'],'ready')
            self.assertTrue(view['experiment_plan']['falsification'])
            validate_intervention(proposal(c),{q['id']:c},DEFAULT_PIPELINE_CONFIG)

    def test_priority_directions_are_advisory_but_required_fields_are_checked(self):
        q,c,chunks=example()
        validate_intervention(proposal(c,'grounded_generation','recall_missing',{'prompt_strategy':'Completeness'}),{q['id']:c},DEFAULT_PIPELINE_CONFIG)
        for change in [{'hypothesis':''}, {'why':''}, {'expected_improvement':''}, {'risk':''}]:
            p={**proposal(c),**change}
            with self.subTest(change=change),self.assertRaises(ValueError):validate_intervention(p,{q['id']:c},DEFAULT_PIPELINE_CONFIG)

    def test_context_and_generation_are_located_from_saved_stage_text(self):
        for stage,root,direction,observation,diff in [('context','Ranking','context_selection','ranking_omission',{'top_k':6}),
                ('answer','Generation','grounded_generation','final_sufficient',{'prompt_strategy':'Completeness'})]:
            q,c,chunks=example(stage)
            with patch('app.diagnostics._current_corpus',return_value=(chunks,'new-corpus')):
                self.assertEqual(diagnostic_view(c)['primary_root_cause'],root)
                self.assertTrue(diagnostic_view(c)['target_eligible'])
                validate_intervention(proposal(c,direction,observation,diff),{q['id']:c},DEFAULT_PIPELINE_CONFIG)

    def test_missing_saved_evidence_judgment_or_trace_requires_repair(self):
        for broken in ['source','judge','trace','status']:
            q,c,chunks=example()
            if broken=='source':c['standard_evidence']=[]
            if broken=='judge':c.update(judge_result={},evaluation_outcome={},passed=None)
            if broken=='trace':c['programmatic_metrics']['retrieval_trace'].pop('final')
            if broken=='status':c['programmatic_metrics']['retrieval_trace']['status']='running'
            with patch('app.diagnostics._current_corpus',return_value=(chunks,'new-corpus')):
                plan=diagnostic_view(c)['experiment_plan']
                self.assertEqual(diagnostic_view(c)['primary_root_cause'],'MissingRecord')
                self.assertEqual(plan['status'],'capability_gap',plan)
                self.assertTrue(plan['next_action'])
                with self.assertRaises(ValueError):validate_intervention(proposal(c),{q['id']:c},DEFAULT_PIPELINE_CONFIG)


class AgentExplorationTests(unittest.TestCase):
    setUp=contracts.OptimizationContractTests.setUp
    def test_saved_evidence_persists_ready_diagnosis_and_complete_abc(self):
        q,c,chunks=example();c['question_id']='Q1'
        self.store.record_bad_case('EVAL-test','Q1','Unknown','ordinary',c)
        provider=contracts.FixedProvider(json.dumps(contracts.drafts()))
        with patch.dict(os.environ,{'RAG_DEMO_DB_PATH':str(self.store.database_path)}),patch('app.diagnostics._current_corpus',return_value=(chunks,'new-corpus')):
            result=OptimizationAgent(self.store,provider).generate('EVAL-test')
        self.assertEqual(result['result']['diagnostic_tasks'][0]['status'],'ready_for_experiment')
        self.assertEqual(len(result['candidates']),3)
        self.assertEqual(result['candidates'][0]['reasoning']['experiment_kind'],'confirmed')
        self.assertEqual(result['candidates'][0]['reasoning']['root_cause'],'Retrieval')

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
        response=contracts.drafts()
        response['prior_round_review']['plans']=[{
            'candidate_id':candidate['id'],'changes':'offline saved configuration',
            'fixed_question_ids':ids,'new_failure_question_ids':[],
            'evidence_reason':'offline saved candidate result','conclusion':'keep configuration results separate',
        } for candidate,ids in zip(exp['candidates'],[['Q1'],['Q2'],[]])]
        for row,diff in zip(response['candidates'],[{'query_rewrite':True},{'generation_thinking':'low','hyde':True},{'prompt_strategy':'Tiered'}]):
            row['config_diff']=diff
            row['hypothesis']+=' second round'
        response['candidates'][2]['direction']='回答策略'
        next_round=OptimizationAgent(self.store,contracts.FixedProvider(json.dumps(response))).generate('EVAL-test',experiment_id=exp['id'])
        progress=next_round['result']['processing_progress']
        self.assertEqual(len(progress['fixed_question_ids']),1)
        self.assertEqual(len(progress['remaining_question_ids']),1)
        self.assertIn(progress['verified_configuration_id'],[c['id'] for c in exp['candidates'][:2]])
