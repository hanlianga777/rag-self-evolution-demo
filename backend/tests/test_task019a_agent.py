"""019a contracts: saved facts, retrospective and exact repeat prohibition."""
import json
import unittest

from app.optimization import build_agent_prompt, prepare_response, validate_round_contract
from app.policy import DEFAULT_PIPELINE_CONFIG, select_final_candidate
import test_optimization_contract as contract


def result_candidate(cid, *, bad=3, p99=30, cost=2, release=True, diff=None):
    return {'id':cid,'status':'evaluated','config':{**DEFAULT_PIPELINE_CONFIG,**(diff or {})},
            'reasoning':{'candidate_label':'D' if cid=='D' else 'A','changed_parameters':diff or {}},
            'result':{'qualification':{'qualified':True},'release_qualification':{'qualified':release},
                      'bad_case_count':bad,'new_regression_question_ids':[],'latency_p99_seconds':p99,
                      'estimated_cost':{'amount':cost,'currency':'USD'}}}


class AgentFactsTests(unittest.TestCase):
    def test_harmful_hyde_allows_thinking_compensation_but_rejects_exact_repeat(self):
        gate={'id':'latency_p99_seconds','passed':True,'actual':42,'operator':'<='}
        prior=result_candidate('old',diff={'hyde':True})
        prior['result']['gates']={'gates':[{**gate,'passed':False,'actual':72}]}
        new=contract.drafts()['candidates']
        new[0].update(config_diff={'top_k':6})
        new[1].update(config_diff={'generation_thinking':'high','hyde':True})
        validate_round_contract(new,DEFAULT_PIPELINE_CONFIG,[prior],[gate])
        new[1]['config_diff']={'generation_thinking':'high','min_score':.1}
        new[0]['config_diff']={'hyde':True}
        with self.assertRaisesRegex(ValueError,'照搬'):
            validate_round_contract(new,DEFAULT_PIPELINE_CONFIG,[prior],[gate])

    def test_agent_new_failure_facts_use_canonical_regression_ids_and_frozen_evidence(self):
        old=result_candidate('old',diff={'hyde':True})
        old['result'].update(new_regression_question_ids=['Q07','Q13'],bad_case_count=2)
        questions=[{'id':q,'evidence':[{'chunk_id':'c'}],'business_requirements':{'required':[{'id':'r','text':'必须答'}]}} for q in ['Q07','Q13']]
        cases=[{'question_id':q,'passed':False,'test_category':'positive','judge_result':{'reason':'缺一条'},
                'programmatic_metrics':{'retrieval_trace':{'candidates':[{'chunk_id':'c'}],'final':[]}}} for q in ['Q07','Q13']]
        _,prompt=build_agent_prompt([],DEFAULT_PIPELINE_CONFIG,[old],[],list('ABC'),
            baseline_result={'metrics':{'latency_p50_seconds':20,'latency_p99_seconds':42}},
            candidate_cases={'old':cases},golden_questions=questions)
        facts=prompt['prior_sandbox_results'][0]
        self.assertEqual([r['question_id'] for r in facts['question_changes']['new_failures']],['Q07','Q13'])
        self.assertEqual(facts['question_changes']['new_failures'][0]['retrieval_facts']['standard_evidence_positions'][0]['candidates'],1)
        self.assertEqual(facts['question_changes']['new_failures'][0]['retrieval_facts']['standard_evidence_positions'][0]['final'],'未进入')
        self.assertEqual(len(facts['failed_questions']),2)
        self.assertIn('enhancement_latency_deltas',prompt)

    def test_retrospective_is_required_and_every_proposal_references_a_conclusion(self):
        drafts=contract.drafts()
        drafts.pop('prior_round_review')
        for candidate in drafts['candidates']:candidate.pop('review_conclusion_ids')
        audit={}
        with self.assertRaisesRegex(ValueError,'复盘'):
            prepare_response(json.dumps(drafts),DEFAULT_PIPELINE_CONFIG,[],[],0,1,list('ABC'),None,[],audit)
        drafts['prior_round_review']={'plans':[],'baseline_remaining_assessment':'首轮只有Baseline事实','conclusions':[{'id':'base','conclusion':'从Baseline诊断开始'}]}
        with self.assertRaisesRegex(ValueError,'复盘'):
            prepare_response(json.dumps(drafts),DEFAULT_PIPELINE_CONFIG,[],[],0,1,list('ABC'),None,[],{})

    def test_d_must_strictly_improve_release_eligible_winner(self):
        winner=result_candidate('A')
        self.assertEqual(select_final_candidate([winner],result_candidate('D',bad=4))['candidate_id'],'A')
        self.assertEqual(select_final_candidate([winner],result_candidate('D',p99=29,cost=2))['candidate_id'],'A')
        self.assertEqual(select_final_candidate([winner],result_candidate('D',p99=29,cost=1))['candidate_id'],'D')
        self.assertEqual(select_final_candidate([winner],result_candidate('D',bad=2))['candidate_id'],'D')
        winner['result']['release_qualification']['qualified']=False
        self.assertIsNone(select_final_candidate([winner],result_candidate('D',release=False))['candidate_id'])

class CompositeSourceTests(unittest.TestCase):
    def test_multi_parameter_source_must_be_taken_whole_and_have_reason(self):
        from app.policy import validate_composite_sources
        base=DEFAULT_PIPELINE_CONFIG
        source=result_candidate('source',diff={'hyde':True,'generation_thinking':'high'})
        source['result']['regression']={'passed':True,'new_critical_failures':0}
        with self.assertRaisesRegex(ValueError,'整组'):
            validate_composite_sources([source],{**base,'hyde':True},base,{'source':'修复召回'})
        validate_composite_sources([source],source['config'],base,{'source':'整组有改善，无法单独归因'})
        with self.assertRaisesRegex(ValueError,'理由'):
            validate_composite_sources([source],source['config'],base,{})
        source['result']['regression']['new_critical_failures']=1
        with self.assertRaisesRegex(ValueError,'关键'):
            validate_composite_sources([source],source['config'],base,{'source':'有改善'})

class CostFactsTests(unittest.TestCase):
    def test_d_cost_comparison_uses_saved_full_sandbox_cost_and_unknown_stays_unknown(self):
        from app.evaluation import sandbox_cost
        cases=[{'programmatic_metrics':{'cost_estimation':{'amount':.01,'currency':'USD'},'judge_cost_estimation':{'amount':.02,'currency':'USD'}}}]*50
        cost=sandbox_cost(cases)
        self.assertAlmostEqual(cost['amount'],1.5)
        self.assertEqual(cost['currency'],'USD')
        cases.append({'programmatic_metrics':{}})
        self.assertIsNone(sandbox_cost(cases)['amount'])

class NegativeEvidenceTests(unittest.TestCase):
    def test_safety_question_with_saved_standard_evidence_keeps_its_positions(self):
        from app.agent_inputs import retrieval_facts
        question={'id':'Q35','evidence':[{'source_chunk_ids':['safety']} ]}
        facts=retrieval_facts({'test_category':'negative','programmatic_metrics':{'retrieval_trace':{'candidates':[{'chunk_id':'safety'}],'final':[]}}},question)
        self.assertEqual(facts['standard_evidence_positions'][0]['candidates'],1)
