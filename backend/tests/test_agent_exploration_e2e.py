"""50-question offline fixture through real Agent, retrieval, Sandbox and Regression.
No fixture score is evidence of a real model improvement.
"""
import json
import os
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from app.ai_service import AiService
from app.evaluation import EvaluationRunner
from app.governance import GovernanceStore
from app.optimization import OptimizationAgent
from app.retrieval import VectorRetriever
import test_agent_exploration as exploration
import test_optimization_contract as contracts


class FixtureProvider:
    settings=SimpleNamespace(model='fixture',configured=True)
    def complete_with_metrics(self,system,user,**kwargs):
        # A fixed answer, independent of Golden, proves plumbing only.
        return {'content':'请核对手册。','ttft_ms':1,'input_tokens':10,'output_tokens':5,'usage':{}}
    def judge(self,q,expected,answer,**kwargs):
        n=int(q.split('-')[-1]);context=kwargs['context']
        changed=len(context['final_context'])==6
        # Fault injection: two repairs + one new failure under this one config.
        passed=(n>=10 or changed and n<2) and not (changed and n==20)
        return {'verdict':'PASS' if passed else 'FAIL',
            'checks':[{'check_type':'negative_behavior' if context['category']=='negative' else 'fact',
                'requirement':'核对手册','met':passed,'answer_quotes':[answer] if passed else [],
                'support':[] if context['category']=='negative' or not passed else [{'source_id':context['final_context'][0]['chunk_id'],'quote':'请核对手册。'}]}],
            'issues':[],'reason':'OFFLINE FIXTURE outcome, no real semantic claim',
            'quality':{'correctness':4 if passed else 0,'faithfulness':1,'completeness':1 if passed else 0}}


class Sandbox50Tests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        for name in ('app.corpus.current_manifest','app.governance.current_manifest'):
            manifest=patch(name,return_value={'sources':{'fixture-doc':'offline-only'}})
            manifest.start();self.addCleanup(manifest.stop)
        self.path=Path(temp.name)/'test.db'
        env=patch.dict(os.environ,{'RAG_DEMO_DB_PATH':str(self.path),'RAG_DIAGNOSTIC_DIR':temp.name+'/diagnostics'})
        env.start();self.addCleanup(env.stop)
        self.store=GovernanceStore(self.path)
        self.chunks=[{'chunk_id':f'c{i}','document_id':'fixture-doc','product':'fixture-product','version':'1','chunk_text':'请核对手册。'} for i in range(12)]
        corpus=SimpleNamespace(chunks=lambda:self.chunks)
        self.ai=AiService(self.store,corpus,FixtureProvider(),False)
        retriever=VectorRetriever(corpus)
        retriever.vector_candidates=lambda q,limit,**kw:[{'chunk_id':c['chunk_id'],'score':1-i/20} for i,c in enumerate(self.chunks[:limit])]
        self.ai.retriever=retriever
        self.runner=EvaluationRunner(self.store,self.ai)
        fp={'fixture-doc':'offline-only'}
        retrieve=retriever.retrieve
        def retrieve_fixture(*args,**kwargs):
            result=retrieve(*args,**kwargs)
            kwargs['trace']['corpus_fingerprint']=fp
            return result
        retriever.retrieve=retrieve_fixture
        items=[{'id':f'case-{i}','question':f'fixture-{i}','reference_answer':'请核对手册。',
            'test_category':'positive' if i<20 else 'ablation' if i<30 else 'negative',
            'negative_subtype':None if i<30 else 'safety_critical' if i<40 else 'prompt_injection',
            'evidence':[{'source_chunk_ids':['c5'],'evidence_key_points':['请核对手册。']}]} for i in range(50)]
        snapshot={'id':'fixture50','question_ids':[i['id'] for i in items],'questions':items,'corpus_fingerprint':fp}
        with self.store.connection() as db:db.execute('INSERT INTO dataset_versions VALUES (?,?,?,?,?)',('fixture50','approved','fixture',json.dumps(snapshot),'9999'))
        handle=patch('app.diagnostics._current_corpus',return_value=(self.chunks,fp));handle.start();self.addCleanup(handle.stop)
        self.baseline=self.runner.run_baseline(automatic=False)
        self.assertEqual(self.baseline['status'],'completed',self.baseline.get('error_message'))
        self.assertEqual(self.baseline['result']['bad_case_count'],10)

    def generate(self):
        from app.diagnostics import diagnostic_view
        case=next(r['result'] for r in self.store.bad_case_rows() if r['run_id']==self.baseline['id'] and r['question_id']=='case-0')
        plan=diagnostic_view(case)['experiment_plan']
        self.assertEqual(plan['status'],'exploratory',plan)
        p=exploration.proposal({'question_id':'case-0'},'context_selection','context_pool_gap',{'top_k':6})
        p.update(id='A',target_group='fixture50',root_cause_evidence=['case-0'])
        return OptimizationAgent(self.store,contracts.FixedProvider(json.dumps({'candidates':[p],'insufficient_evidence':'single fixture experiment'}))).generate(self.baseline['id'])

    def test_agent_candidate_sandbox_all50_regression_and_no_automatic_release(self):
        before=deepcopy(self.store.evaluation_run(self.baseline['id']))
        exp=self.generate();candidate=exp['candidates'][0]
        self.assertEqual(len(exp['result']['diagnostic_tasks']),10)
        self.assertEqual(candidate['reasoning']['experiment_kind'],'exploratory')
        result=self.runner.run_candidate(candidate['id'],automatic=False)
        self.assertEqual(result['status'],'evaluated',result['result'].get('error'))
        run=self.store.evaluation_run(result['result']['evaluation_run_id'])
        cases=self.store.evaluation_case_results(run['id'])
        self.assertEqual(len(cases),50)
        self.assertTrue(all(c['programmatic_metrics']['retrieval_trace']['config']['top_k']==6 for c in cases))
        self.assertTrue(all(len(c['programmatic_metrics']['retrieval_trace']['final'])==6 for c in cases))
        self.assertEqual(result['result']['all_fixed_question_ids'],['case-0','case-1'])
        self.assertEqual(result['result']['new_regression_question_ids'],['case-20'])
        self.assertEqual(result['result']['net_improvement'],1)
        self.assertEqual(result['result']['target_bad_cases_fixed'],1)
        self.assertEqual(result['result']['incidental_fixes'],1)
        self.assertEqual(result['result']['bad_case_count'],9)
        self.assertTrue(result['result']['regression']['passed'])
        self.assertEqual(result['result']['gates']['total'],11)
        self.assertTrue(result['result']['comparison_complete'])
        self.assertEqual(self.store.evaluation_run(self.baseline['id']),before)
        self.assertIsNone(self.store.recommendation(exp['id'])['result']['recommended_candidate'])
        with self.assertRaises(ValueError):self.store.publish_candidate(candidate['id'],'fixture')

    def test_tampered_exploration_is_rejected_before_sandbox_budget_or_calls(self):
        exp=self.generate();candidate=exp['candidates'][0]
        with self.store.connection() as db:db.execute('UPDATE candidate_configs SET config_json=? WHERE id=?',(json.dumps({**candidate['config'],'prompt_strategy':'Abstention'}),candidate['id']))
        with self.assertRaises(ValueError):self.runner.start_candidate(candidate['id'])
        self.assertEqual(self.store.experiment(exp['id'])['evaluation_budget']['used'],0)
