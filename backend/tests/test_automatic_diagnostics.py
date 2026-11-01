"""Offline diagnostic evidence fixtures; no imports of app.main or live stores."""
import unittest
from copy import deepcopy
from app.diagnostics import diagnostic_view


def recall_case():
    source={'chunk_id':'covered','document_id':'manual','product':'device','chunk_text':'检查外壳'}
    missing={**source,'chunk_id':'missing','chunk_text':'检查传感器是否脏污'}
    final={**source,'content':source['chunk_text'],'matched_child_ids':['covered']}
    case={'test_category':'positive','passed':False,'primary_root_cause':'Unknown','diagnosis':{'status':'needs_review'},
        'standard_evidence':['检查外壳','检查传感器是否脏污'],'model_answer':'请检查外壳。','failure_tags':['Generation Failure'],
        'judge_result':{'correctness':2,'completeness':.5,'missing_points':['未列出“检查传感器是否脏污”。'],
            'evidence_sufficiency':{'status':'insufficient','source_applicable':True,'fact_support':[{'fact':'检查外壳','chunk_id':'covered','quote':'检查外壳'}]}},
        'programmatic_metrics':{'claim_assessment':{'pending':[]},'evidence_coverage':{'required_chunk_ids':['covered','missing']},
            'evidence_sufficiency':{'sufficient':False,'source_applicable':True,'unresolved_conflicts':[],
                'facts':[{'fact':'检查外壳','locations':[{'chunk_id':'covered'}]},{'fact':'检查传感器是否脏污','locations':[]}],
                'judge_support':[{'fact':'检查外壳','chunk_id':'covered','quote':'检查外壳'}]},
            'retrieval_trace':{'status':'completed','candidate_stage':'post_metadata_filter_fusion_candidate_cap_pre_rerank',
                'corpus_fingerprint':{'corpus':'one'},'candidates':[final],'reranked':[final],'final':[final]}}}
    return case,[source,missing]


class AutomaticDiagnosticTests(unittest.TestCase):
    def test_saved_text_ignores_current_corpus_and_original_case_is_unchanged(self):
        case,chunks=recall_case();before=deepcopy(case)
        from unittest.mock import patch
        with patch('app.diagnostics._current_corpus',side_effect=AssertionError('live KB must not be read')):
            view=diagnostic_view(case,corpus_chunks=[],corpus_fingerprint='changed')
        self.assertEqual(view['diagnosis_category'],'检索失败')
        self.assertTrue(view['target_eligible'])
        self.assertEqual(view['retrieval_failure_stage'],'candidate_recall')
        self.assertEqual(case,before)

    def test_explicit_empty_stages_are_different_from_missing_stages(self):
        case,_=recall_case();trace=case['programmatic_metrics']['retrieval_trace']
        trace.update(candidates=[],final=[])
        self.assertEqual(diagnostic_view(case)['diagnosis_category'],'检索失败')
        trace['candidates']=None
        self.assertEqual(diagnostic_view(case)['diagnosis_category'],'记录缺失')
        trace['candidates']=[]
        for status in ('failed','running','not_collected'):
            trace['status']=status
            self.assertEqual(diagnostic_view(case)['diagnosis_category'],'记录缺失')

    def test_candidate_missing_dominates_incorrect_answer_and_saved_cause(self):
        case,_=recall_case();case.update(model_answer='无需检查外壳。',primary_root_cause='Generation')
        case['judge_result'].update(behavior_pass=False,unsupported_claims=['无需检查外壳。'])
        self.assertEqual(diagnostic_view(case)['diagnosis_category'],'检索失败')

    def test_saved_pending_or_disputed_status_does_not_hide_text_based_result(self):
        case,_=recall_case()
        for status in ('confirmed','needs_review','disputed'):
            case['diagnosis']['status']=status
            case['programmatic_metrics']['claim_assessment']['pending']=[{'claim':'未闭合的附加主张'}]
            self.assertEqual(diagnostic_view(case)['diagnosis_category'],'检索失败')

    def test_final_source_ids_can_differ_and_parent_expansion_is_plain_saved_text(self):
        case,chunks=recall_case();trace=case['programmatic_metrics']['retrieval_trace']
        trace['candidates'].append({'chunk_id':'unrelated-id','content':chunks[1]['chunk_text']})
        trace['final']=[{'chunk_id':'parent','content':'父段落：检查外壳，检查传感器是否脏污。'}]
        trace['parent_expand']=True
        self.assertEqual(diagnostic_view(case)['diagnosis_category'],'回答问题')
