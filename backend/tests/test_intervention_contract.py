"""Offline evidence/intervention checks; no Provider and no persistence."""
import os
import tempfile
from pathlib import Path

# Isolation precedes all app imports, including when this module runs alone.
_isolation = tempfile.TemporaryDirectory()
for _name, _leaf in [('RAG_DEMO_DB_PATH','demo.db'),('RAG_DEMO_ENV_PATH','missing.env'),('RAG_DEMO_INDEX_DIR','index'),('RAG_DEMO_DOCUMENTS_DIR','documents'),('RAG_DEMO_UPLOADS_DIR','uploads')]:
    os.environ.setdefault(_name, str(Path(_isolation.name) / _leaf))

import unittest
from copy import deepcopy
from app.diagnostics import diagnostic_view
from app.optimization import validate_intervention
from app.evaluation_contract import compare_cases


def target(root='Generation', final=True):
    return {'primary_root_cause':root,'diagnosis':{'status':'confirmed','findings':[{'kind':'unsupported_instruction'}]},
        'programmatic_metrics':{'evidence_coverage':{'required_chunk_ids':['c']},
            'evidence_sufficiency':{'sufficient':final},'retrieval_trace':{'candidates':[{'chunk_id':'c'}],'final':[{'chunk_id':'c'}] if final else []}}}


def proposal(direction='grounded_generation', diff=None, observation='confirmed_claim'):
    return {'intervention_direction':direction,'config_diff':diff or {'prompt_strategy':'Grounded'},
        'target_bad_cases':['q'],'root_cause':'Generation','evidence_assertions':[{'target_id':'q','observation':observation}],
        'parameter_dependencies':[],'hypothesis':'只移除无来源操作','why':'原回答有定位主张','expected_improvement':'减少无来源操作','risk':'遗漏有据步骤'}


class InterventionTests(unittest.TestCase):
    def test_final_complete_cannot_be_called_recall_failure(self):
        case=target();p=proposal('query_expansion',{'query_rewrite':True},'recall_missing')
        with self.assertRaisesRegex(ValueError,'Trace'):validate_intervention(p,{'q':case},{'query_rewrite':False})
        validate_intervention(proposal(),{'q':case},{'prompt_strategy':'Abstention'})

    def test_complete_semantic_evidence_suppresses_missing_source_id_hypothesis(self):
        case=target()
        case['programmatic_metrics']['retrieval_trace']={'candidates':[{'chunk_id':'alternative'}],'final':[{'chunk_id':'alternative'}]}
        view=diagnostic_view(case)
        self.assertIn('final_sufficient',view['trace_observations'])
        self.assertNotIn('recall_missing',view['trace_observations'])
        p=proposal('candidate_recall',{'candidate_k':24},'recall_missing')
        with self.assertRaisesRegex(ValueError,'Trace'):validate_intervention(p,{'q':case},{'candidate_k':12})

    def test_ranking_omission_and_recall_gap_are_distinct(self):
        case=target(final=False);p=proposal('context_selection',{'top_k':6},'ranking_omission')
        validate_intervention(p,{'q':case},{'top_k':4})
        p.update(intervention_direction='candidate_recall',config_diff={'candidate_k':24},evidence_assertions=[{'target_id':'q','observation':'recall_missing'}])
        with self.assertRaisesRegex(ValueError,'Trace'):validate_intervention(p,{'q':case},{'candidate_k':12})
        case['programmatic_metrics']['retrieval_trace']['candidates']=[]
        validate_intervention(p,{'q':case},{'candidate_k':12})

    def test_cross_direction_rejected_dependencies_required(self):
        p=proposal(diff={'prompt_strategy':'Grounded','metadata_filter':'STRICT'})
        with self.assertRaisesRegex(ValueError,'方向'):validate_intervention(p,{'q':target()},{'prompt_strategy':'Abstention','metadata_filter':'OFF'})
        case=target(final=False);case['programmatic_metrics']['retrieval_trace']['candidates']=[]
        p=proposal('query_expansion',{'query_rewrite':True,'multi_query':2},'recall_missing')
        with self.assertRaisesRegex(ValueError,'依赖'):validate_intervention(p,{'q':case},{'query_rewrite':False,'multi_query':False})
        p['parameter_dependencies']=[{'parameters':['query_rewrite','multi_query'],'reason':'两种查询分别覆盖原问别名与同义表达缺口'}]
        validate_intervention(p,{'q':case},{'query_rewrite':False,'multi_query':False})

    def test_performance_requires_corresponding_observed_bottleneck(self):
        case=target('Performance')
        case['failure_tags']=['Performance Failure']
        case['programmatic_metrics'].update(latency_ms=70000,stages=[{'stage_name':'retrieval','duration_ms':60000},
            {'stage_name':'rerank','duration_ms':55000,'parent':'retrieval'}, {'stage_name':'generation','duration_ms':10000}])
        p=proposal('stage_performance',{'rerank':False},'measured_latency')
        p.update(root_cause='Performance',performance_stage='rerank')
        validate_intervention(p,{'q':case},{'rerank':True})
        p.update(performance_stage='generation')
        with self.assertRaisesRegex(ValueError,'瓶颈'):validate_intervention(p,{'q':case},{'rerank':True})

    def test_missing_behavior_is_not_zero_and_gate_detail_does_not_crash(self):
        from app.evaluation import summarize_evaluation_cases,gate_details
        value=summarize_evaluation_cases([{'test_category':'negative','question_id':'q','programmatic_metrics':{},'judge_result':{}}])
        self.assertIsNone(value['metrics']['safe_rejection_rate'])
        gate=next(g for g in value['gates']['gates'] if g['metric']=='safe_rejection_rate')
        self.assertEqual(gate['status'],'NOT_EVALUABLE')
        details=gate_details([{'test_category':'negative','question_id':'q'}],[gate])
        self.assertIsNone(details[0]['contributing_cases'][0]['value'])

    def test_confirmed_candidate_to_final_omission_is_retrieval_with_ranking_stage(self):
        from app.evaluation import EvaluationRunner
        judgment={'correctness':0,'faithfulness':1,'completeness':0,'behavior_pass':True,'reason':'缺少必要事实','unsupported_claims':[],
                  'evidence_sufficiency':{'status':'insufficient','source_applicable':True,'conflicts':[],'fact_support':[]}}
        runtime=type('Saved',(),{'judge':lambda *_a,**_kw:deepcopy(judgment)})()
        item={'id':'fixture','question':'问题','reference_answer':'必要事实','test_category':'positive','evidence':[{'source_chunk_ids':['c']}],'raw':{}}
        execution={'answer':'未回答','retrieval':[],'retrieval_trace':{'candidates':[{'chunk_id':'c','content':'必要事实'}],'final':[]},'latency_ms':1}
        case=EvaluationRunner(None,runtime).score_execution(item,execution)
        self.assertEqual(case['primary_root_cause'],'Retrieval')
        self.assertEqual(case['diagnosis']['retrieval_failure_stage'],'ranking_context_selection')
        self.assertEqual(case['diagnosis']['status'],'confirmed')
        self.assertIn('Ranking Failure',case['failure_tags'])
        self.assertEqual(case['evaluation_outcome']['confirmed_failure_tags'],['Ranking Failure'])
        self.assertFalse(case['passed'])

    def test_materialize_preserves_only_real_optional_source_version(self):
        from app.retrieval import VectorRetriever
        chunk={'document_id':'doc','chunk_id':'c','chunk_text':'原文','version':'R3'}
        self.assertEqual(VectorRetriever._materialize(chunk,1)['version'],'R3')
        chunk.pop('version')
        self.assertNotIn('version',VectorRetriever._materialize(chunk,1))

    def test_target_requires_actual_trace_and_all_confirmed_roots(self):
        case=target();case['programmatic_metrics']['retrieval_trace']={}
        with self.assertRaisesRegex(ValueError,'Trace'):validate_intervention(proposal(),{'q':case},{'prompt_strategy':'Abstention'})
        case=target('Safety')
        with self.assertRaisesRegex(ValueError,'根因'):validate_intervention(proposal(),{'q':case},{'prompt_strategy':'Abstention'})

    def test_formal_blocking_is_not_confirmed_business_regression(self):
        baseline={k:{'passed':True} for k in ['a','b','c']}
        candidate={'a':{'passed':False,'evaluation_outcome':{'status':'pending_review'}},
                   'b':{'passed':False,'evaluation_outcome':{'status':'disputed'}},
                   'c':{'passed':False,'evaluation_outcome':{'status':'confirmed_failure'}}}
        value=compare_cases(baseline,candidate,[])
        self.assertEqual(value['new_regressions'],3)
        self.assertEqual(value['confirmed_regression_question_ids'],['c'])
        self.assertEqual(value['pending_regression_question_ids'],['a'])
        self.assertEqual(value['disputed_regression_question_ids'],['b'])
        self.assertEqual(candidate['a']['passed'],False)
        self.assertEqual(compare_cases({'missing':{'passed':True}},{},[])['unclassified_regression_question_ids'],['missing'])

    def test_diagnostic_observations_do_not_invent_corpus_coverage(self):
        case=target(final=False);view=diagnostic_view(case)
        self.assertIn('ranking_omission',view['trace_observations'])
        self.assertNotIn('recall_missing',view['trace_observations'])
        self.assertEqual(case['primary_root_cause'],'Generation')

    def test_alternative_sufficient_final_source_is_not_a_retrieval_failure_phenomenon(self):
        case=target(final=True)
        case['programmatic_metrics']['retrieval_trace']['final']=[{'chunk_id':'alternative'}]
        case['programmatic_metrics']['evidence_coverage']['final_context']={'all_hit':False}
        view=diagnostic_view(case)
        self.assertNotIn('检索失败',[p['name'] for p in view['phenomena']])
        self.assertNotIn('recall_missing',view['trace_observations'])
        self.assertNotIn('ranking_omission',view['trace_observations'])

    def test_structured_operation_and_injection_failures_keep_distinct_phenomena(self):
        case=target();case['negative_subtype']='prompt_injection'
        case['programmatic_metrics']['claim_assessment']={'confirmed':[{'kind':'unsupported_instruction','changes_operation':True}]}
        case['programmatic_metrics']['behavior_contract']={'effective_pass':False}
        names=[p['name'] for p in diagnostic_view(case)['phenomena']]
        self.assertIn('无依据技术操作',names)
        self.assertIn('提示词注入失败',names)
        case['programmatic_metrics']['behavior_contract']['effective_pass']=True
        self.assertNotIn('提示词注入失败',[p['name'] for p in diagnostic_view(case)['phenomena']])


class HistoricalAuditPairs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import csv
        import json
        path=Path(__file__).resolve().parents[2]/'output/baseline-ab-root-cause-audit-20261014/Baseline_A_B_50题逐题对照.csv'
        if not path.exists():raise unittest.SkipTest('Private read-only audit CSV not distributed with source')
        csv.field_size_limit(100_000_000)
        with path.open(encoding='utf-8-sig') as source:cls.rows={r['题号']:r for r in csv.DictReader(source)}
        cls.json=json

    def test_disputed_pairs_depend_on_structured_fields_not_reason_wording(self):
        from app.evaluation_contract import assess_claims
        for key in ['Q20','Q33','Q34','Q42','Q45','Q49','Q50']:
            row=self.rows[key];raw=self.json.loads(row['Golden原始快照_JSON'])
            item={'test_category':row['题型'],'negative_subtype':raw.get('negative_subtype'),'raw':raw}
            for side in ['Baseline','A','B']:
                with self.subTest(question=key,side=side):
                    judge=self.json.loads(row[side+'_Judge原始完整结果_JSON'])
                    entries=self.json.loads(row[side+'_完整检索Trace_JSON'])['final']
                    before=deepcopy(judge)
                    original=assess_claims(row[side+'_回答'],judge,entries,item=item)
                    contrary=deepcopy(judge)
                    for review in contrary.get('claim_reviews',[]):review['reason']='该主张不阻断；但这里的文字不得代替结构化依据'
                    repeated=assess_claims(row[side+'_回答'],contrary,entries,item=item)
                    def signature(result):return {k:[(r.get('unsupported_claim_index'),r.get('kind'),r['verification_issues']) for r in rows] for k,rows in result.items()}
                    self.assertEqual(signature(original),signature(repeated))
                    self.assertEqual(judge,before)
                    if key=='Q50' and side in ['A','B']:
                        self.assertTrue(any(r['kind']=='supported_abstention' for r in original['accepted']))
                        self.assertFalse(original['confirmed'])
                        self.assertFalse(original['pending'])

    def test_historical_targets_cannot_misdescribe_fully_recalled_evidence(self):
        checked=0
        for key in ['Q07','Q22','Q23','Q30','Q38','Q39','Q47','Q48']:
            row=self.rows[key]
            for side in ['Baseline','A','B']:
                matcher=self.json.loads(row[side+'_Evidence_Matcher_JSON'])
                trace=self.json.loads(row[side+'_完整检索Trace_JSON'])
                # Audit structure retains the original coverage/sufficiency separately.
                case={'primary_root_cause':row[side+'_primary_root_cause'],
                      'diagnosis':self.json.loads(row[side+'_diagnosis_JSON']),
                      'programmatic_metrics':{'retrieval_trace':trace,'evidence_coverage':matcher.get('evidence_coverage',{}),
                                              'evidence_sufficiency':matcher.get('evidence_sufficiency',{})}}
                view=diagnostic_view(case)
                required=set(case['programmatic_metrics']['evidence_coverage'].get('required_chunk_ids') or [])
                candidates={c for e in trace['candidates'] for c in e.get('matched_child_ids',[e.get('chunk_id')])}
                if required and required<=candidates:
                    checked+=1
                    self.assertNotIn('recall_missing',view['trace_observations'])
        self.assertGreater(checked,0)

if __name__=='__main__':unittest.main()
