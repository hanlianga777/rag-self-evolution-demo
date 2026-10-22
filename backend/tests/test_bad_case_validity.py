"""Isolated Mock acceptance: every FAIL reaches Agent, specific interventions keep evidence constraints."""
import os
import tempfile
from pathlib import Path
_isolation=tempfile.TemporaryDirectory()
for name,leaf in [('RAG_DEMO_DB_PATH','demo.db'),('RAG_DEMO_ENV_PATH','missing.env'),('RAG_DEMO_INDEX_DIR','index'),('RAG_DEMO_DOCUMENTS_DIR','documents'),('RAG_DEMO_UPLOADS_DIR','uploads')]:
    os.environ.setdefault(name,str(Path(_isolation.name)/leaf))
import json
import unittest
from copy import deepcopy
from unittest.mock import patch
from app.diagnostics import diagnostic_view
from app.governance import GovernanceStore
from app.optimization import OptimizationAgent
from diagnostic_fixture import retrieval_case,generation_case
from identity_fixture import completed_baseline


def audit_only():
    quote='该资料未给出版本号。'
    return {'test_category':'positive','passed':False,'model_answer':quote,'judge_result':{
        'correctness':4,'faithfulness':1,'completeness':1,'behavior_pass':True,'missing_points':[],
        'unsupported_claims':[quote],'claim_reviews':[{'unsupported_claim_index':0,'claim':quote,'kind':'unresolved',
        'changes_operation':False,'operation_basis':{'effect':'none','source_applicable':None},'support':[]}]},
        'programmatic_metrics':{'evidence_sufficiency':{'sufficient':True,'source_applicable':True},
        'retrieval_trace':{'candidates':[],'final':[]}}}


class EvidenceMock:
    """Deterministic local strategies chosen from observed roots; no network client."""
    def complete(self,system,user,**kwargs):
        self.prompt=json.loads(user)
        row=next(row for row in self.prompt['bad_cases'] if row['diagnostic_view']['target_eligible']);root=row['diagnostic_view']['primary_root_cause'];qid=row['question_id']
        direction,diff,observation={
            'Retrieval':('candidate_recall',{'candidate_k':24},'recall_missing'),
            'Generation':('grounded_generation',{'prompt_strategy':'Completeness'},'confirmed_claim'),
            'Safety':('grounded_generation',{'prompt_strategy':'Abstention'},'safety_failure'),
            'Performance':('stage_performance',{'rerank':False},'measured_latency')}[root]
        candidate={'id':'A','hypothesis':root+' 独立单一假设','why':'依据实际回答、必要事实与阶段Trace',
            'root_cause':root,'target_bad_cases':[qid],'root_cause_evidence':[qid],'target_group':'离线Mock',
            'intervention_direction':direction,'config_diff':diff,'evidence_assertions':[{'target_id':qid,'observation':observation}],
            'parameter_dependencies':[],'expected_improvement':'由同身份Sandbox验证指定失败改善','risk':'其他题质量或耗时可能退化'}
        if root=='Performance':candidate['performance_stage']='rerank'
        return json.dumps({'candidates':[candidate],'insufficient_evidence':'只验证一个有据假设，不凑满三个'})


class BadCaseValidityTests(unittest.TestCase):
    def test_pending_addition_does_not_veto_independent_recall_proof(self):
        case,chunks=retrieval_case();audit=audit_only();case['model_answer']+=audit['model_answer']
        case['judge_result'].update({k:audit['judge_result'][k] for k in ('unsupported_claims','claim_reviews')})
        before=deepcopy(case)
        view=diagnostic_view(case,corpus_chunks=chunks,corpus_fingerprint={'corpus':'one'})
        self.assertTrue(view['is_technical_bad_case']);self.assertEqual(view['primary_root_cause'],'Retrieval')
        self.assertIn('candidate_recall',view['optimization_directions'])
        # Pending is also retained in the persisted matcher audit, as in real runs.
        case['programmatic_metrics']['claim_assessment']={'pending':[audit['judge_result']['claim_reviews'][0]]}
        self.assertTrue(diagnostic_view(case,corpus_chunks=chunks,corpus_fingerprint={'corpus':'one'})['evaluation_quality_audit']['blocking'])
        case['programmatic_metrics']['claim_assessment']=before['programmatic_metrics']['claim_assessment'];self.assertEqual(case,before)
        case['programmatic_metrics']['evidence_sufficiency']['unresolved_conflicts']=[{'scope':'necessary fact scope unknown'}]
        self.assertFalse(diagnostic_view(case,corpus_chunks=chunks,corpus_fingerprint={'corpus':'one'})['is_technical_bad_case'])

    def test_four_roots_generate_distinct_validated_mock_strategies_without_audit_input(self):
        audit=audit_only();before=deepcopy(audit);view=diagnostic_view(audit)
        self.assertEqual(view['analysis_category'],'evaluation_issue');self.assertFalse(view['is_technical_bad_case'])
        self.assertTrue(view['evaluation_quality_audit']['blocking']);self.assertEqual(audit,before)
        plans=[]
        for root in ('Retrieval','Generation','Safety','Performance'):
            with self.subTest(root=root),tempfile.TemporaryDirectory() as directory,patch('app.diagnostics._current_corpus',return_value=(retrieval_case()[1],{'corpus':'one'})):
                store=GovernanceStore(Path(directory)/'isolated.db');completed_baseline(store,run_id='mock')
                case=retrieval_case()[0] if root=='Retrieval' else generation_case(root)
                if root=='Performance':
                    case.update(failure_tags=['Performance Failure'])
                    case['programmatic_metrics'].update(latency_ms=61001,stages=[{'stage_name':'rerank','duration_ms':61001}])
                store.record_bad_case('mock','Q1',root,'ordinary',case)
                store.record_bad_case('mock','Q-audit','Unknown','ordinary',audit_only())
                provider=EvidenceMock();result=OptimizationAgent(store,provider).generate('mock')
                self.assertEqual(len(result['candidates']),1)
                self.assertIn('Q-audit',provider.prompt['target_reference_map'])
                self.assertEqual(len(provider.prompt['bad_cases']),2)
                self.assertNotIn('all_bad_case_audit',provider.prompt)
                self.assertNotIn('evaluation_quality_audit',next(row for row in provider.prompt['bad_cases'] if row['question_id']=='Q1')['diagnostic_view'])
                self.assertEqual(len(store.bad_case_rows()),2)
                plans.append(result['candidates'][0]['reasoning']['changed_parameters'])
        self.assertEqual(len({json.dumps(plan,sort_keys=True) for plan in plans}),4)

if __name__=='__main__':unittest.main()
