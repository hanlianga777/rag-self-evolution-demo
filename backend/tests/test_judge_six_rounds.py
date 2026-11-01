"""Deterministic six-round contract regressions; no Provider calls."""
import unittest
from app.evaluation import summarize_evaluation_cases, gate_details
from app.diagnostics import business_analysis

class FrozenSafetyTests(unittest.TestCase):
    def test_issue_severity_cannot_change_specialized_denominator(self):
        cases = [dict(question_id='safety', test_category='negative', negative_subtype='safety_critical', severity='ordinary', judge_result={'behavior_pass':True}),
                 dict(question_id='other', test_category='negative', negative_subtype='clarify', severity='critical', judge_result={'behavior_pass':False})]
        result = summarize_evaluation_cases(cases)
        self.assertEqual(result['metrics']['safety_critical_accuracy'], 100)
        details = gate_details(cases, [{'metric':'safety_critical_accuracy','threshold':95,'operator':'>='}])
        self.assertEqual([c['question_id'] for c in details[0]['contributing_cases']], ['safety'])

    def test_pass_diagnosis_is_not_insufficient_evidence(self):
        result = business_analysis({'evaluation_outcome':{'contract_version':'business-vnext-1','execution_complete':True,'verdict':'PASS'}})
        self.assertEqual(result['analysis_category'], 'not_applicable')
        self.assertFalse(result['target_eligible'])

class IndependentJudgeTests(unittest.TestCase):
    def test_role_and_baseline_findings_do_not_enter_judge_payload(self):
        from app.evaluation_contract import business_judge_input
        import json
        common={'category':'positive','final_context':[]}
        baseline=json.loads(business_judge_input('q','r','a',common))
        candidate=json.loads(business_judge_input('q','r','a',{**common,'baseline_findings':[{'description':'target'}]}))
        self.assertEqual(candidate,baseline)

class PostScoreComparisonTests(unittest.TestCase):
    def test_identical_independently_scored_defect_can_map_without_judge_anchor(self):
        from app.evaluation_contract import compare_cases
        import copy
        issue={'description':'禁止带电拆装','critical':True,'answer_quotes':['带电拆装'],'support':[]}
        def case():return {'evaluation_outcome':{'contract_version':'business-vnext-1','execution_complete':True,'verdict':'FAIL'},'judge_result':{'issues':[copy.deepcopy(issue)]}}
        baseline={'q':case()};candidate={'q':case()};before=copy.deepcopy(candidate)
        result=compare_cases(baseline,candidate,[])
        self.assertTrue(result['comparison_complete'])
        self.assertEqual(result['continued_failure_new_critical_question_ids'],[])
        self.assertEqual(candidate,before)

class HistoricalGateTests(unittest.TestCase):
    def test_old_gate_details_use_saved_statistics_contract(self):
        cases=[{'question_id':'old','test_category':'negative','negative_subtype':'clarify','severity':'critical','judge_result':{'behavior_pass':False}}]
        gates=[{'metric':'safety_critical_accuracy','threshold':95,'operator':'>='}]
        rows=gate_details(cases,gates,statistics_version=None)
        self.assertEqual(rows[0]['included_cases'],1)

class MissingMetricTests(unittest.TestCase):
    def test_missing_quality_never_averages_only_completed_values(self):
        rows=[{'test_category':'positive','judge_result':{'correctness':4},'programmatic_metrics':{'latency_ms':10}},
              {'test_category':'positive','judge_result':{},'programmatic_metrics':{}}]
        result=summarize_evaluation_cases(rows)
        self.assertIsNone(result['metrics']['positive_correctness'])
        self.assertIsNone(result['metrics']['latency_p50_seconds'])

class StableAtomicRegressionTests(unittest.TestCase):
    def test_omission_paraphrase_maps_by_same_frozen_atomic_predicate(self):
        from app.evaluation_contract import compare_cases
        def case(description):return {'evaluation_outcome':{'contract_version':'business-vnext-1','execution_complete':True,'verdict':'FAIL'},'judge_result':{'compiled_contract_hash':'same','atomic_failure_keys':['R1:NOT_MET'], 'issues':[{'description':description,'critical':False,'failure_kind':'omission','atomic_ids':['R1']}]}}
        r=compare_cases({'q':case('遗漏关机')},{'q':case('没有说明应关闭设备')},[])
        self.assertTrue(r['comparison_complete'])
        self.assertEqual(r['continued_failure_new_issues'],{})
