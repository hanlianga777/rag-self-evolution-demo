import json
import unittest
from copy import deepcopy
from app.product_diagnostics import objective_metrics, thinking_comparison
from app.diagnostics import diagnostic_view

class ProductMetricsTests(unittest.TestCase):
    def case(self):
        return {'question_id':'Q01','question':'测试','test_category':'positive','passed':False,'model_answer':'漏答',
          'judge_result':{'verdict':'FAIL'},'standard_evidence':['证据甲','证据乙'],
          'programmatic_metrics':{'retrieval_trace':{'status':'completed','candidates':[{'content':'证据甲证据乙'}],
          'reranked':[{'content':'证据甲证据乙'}],'final':[{'content':'无关'},{'content':'证据甲'}]},
          'ttft_ms':100,'input_tokens':10,'output_tokens':20,'cost_estimation':{'amount':0.1,'currency':'USD'},
          'token_usage':{'auxiliary_queries':[{'task':'hyde','status':'ok'}]},
          'stages':[{'stage_name':'retrieval','parent':None,'duration_ms':20},{'stage_name':'vector_search','parent':'retrieval','duration_ms':10},
          {'stage_name':'query_embedding','parent':'vector_search','duration_ms':8},{'stage_name':'generation','parent':None,'duration_ms':80},
          {'stage_name':'judge','parent':None,'duration_ms':500}]}}
    def test_macro_metrics_no_nested_double_count_no_judge_or_mutation(self):
        c=self.case();before=deepcopy(c)
        m=objective_metrics([c],{})
        self.assertEqual((m['recall_at_k'],m['precision_at_k'],m['mrr']),(50,50,0.5))
        self.assertEqual(m['enhancement_counts'],{'hyde':1,'query_rewrite':0,'multi_query':0})
        self.assertEqual(sum(s['total_ms'] for s in m['stage_breakdown']),100)
        self.assertEqual(sum(s['share_percent'] for s in m['stage_breakdown']),100)
        self.assertEqual(m['average_tokens'],30);self.assertEqual(m['average_estimated_cost']['amount'],0.1)
        self.assertEqual(c,before)
    def test_missing_usage_and_negative_evidence_not_fake_zero(self):
        c=self.case();c['test_category']='negative';c['programmatic_metrics']={'retrieval_trace':{}}
        m=objective_metrics([c],{})
        for k in ('recall_at_k','precision_at_k','mrr','average_tokens','ttft_median_ms'):
            self.assertIsNone(m[k])
        self.assertIsNone(m['average_estimated_cost']['amount'])
        self.assertEqual(m['enhancement_counts'],dict.fromkeys(('hyde','query_rewrite','multi_query'),None))
    def test_clarify_not_safety_and_ranks_saved(self):
        c=self.case();c.update(test_category='negative',negative_subtype='clarify')
        v=diagnostic_view(c);self.assertEqual((v['diagnosis_category'],v['subfeature'],v['severity_label']),('回答问题','澄清不足','中等'))
        c['test_category']='positive';v=diagnostic_view(c)
        self.assertEqual(v['diagnosis_category'],'检索噪声');self.assertEqual(v['retrieval_positions'][1]['candidate_rank'],1)
    def test_cross_judge_comparison_blocked(self):
        run={'id':'a','config':{'generation_thinking':'high'},'judge':{'evaluation_identity':'one'},'result':{},'dataset_snapshot_json':'{}'}
        other={**run,'id':'b','judge':{'evaluation_identity':'two'}}
        comparison=thinking_comparison([(run,[self.case()]),(other,[self.case()])],'a')
        self.assertEqual(comparison['columns'],[])
        self.assertIn('判分身份',comparison['note'])
