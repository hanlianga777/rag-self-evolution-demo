"""Task 004: concise Agent input and multi-parameter proposals, no Provider calls."""
import json
import unittest

from app.optimization import prepare_response
from app.policy import DEFAULT_PIPELINE_CONFIG


def failed_case():
    return {'question_id':'Q1','test_category':'positive','passed':False,
            'standard_evidence':['操作前关闭设备。'], 'model_answer':'打开设备。',
            'judge_result':{'verdict':'FAIL','reason':'回答遗漏关闭设备'},
            'programmatic_metrics':{'retrieval_trace':{'status':'completed',
                'candidates':[{'content':'操作前关闭设备。'}],
                'final':[{'content':'操作前关闭设备。'}]}}}


class AgentTask004Tests(unittest.TestCase):
    def rows(self):
        from app.diagnostics import diagnostic_view
        case=failed_case()
        return [{'id':'BC-1','question_id':'Q1','result':case,'diagnostic_view':diagnostic_view(case)}]

    def prepare(self, candidate):
        audit={}
        result,batch=prepare_response(json.dumps({'candidates':[candidate]},ensure_ascii=False),
            DEFAULT_PIPELINE_CONFIG,self.rows(),[],0,1,['A','B','C'],None,[],audit)
        return batch,audit

    def proposal(self):
        return {'id':'A','action_name':'关闭深度思考 + 扩大候选池',
            'hypothesis':'降档节省回答时间，扩大候选池补足质量',
            'why':'回答遗漏，先调整思考档位并扩大可用证据',
            'target_bad_cases':['Q1'],'config_diff':{'generation_thinking':'off','candidate_k':24},
            'expected_improvement':'修好目标且速度门槛通过','risk':'仍可能漏答'}

    def test_cross_stage_proposal_is_accepted_and_action_is_saved(self):
        batch,audit=self.prepare(self.proposal())
        self.assertEqual(len(batch),1)
        self.assertEqual(batch[0][1]['generation_thinking'],'off')
        self.assertEqual(batch[0][1]['candidate_k'],24)
        self.assertEqual(batch[0][2]['action_name'],'关闭深度思考 + 扩大候选池')
        self.assertEqual(audit['rejected_candidates'],[])

    def test_priority_map_is_advice_and_does_not_forbid_cross_layer_changes(self):
        candidate={**self.proposal(),'config_diff':{'query_rewrite':True,'prompt_strategy':'Completeness'}}
        batch,_=self.prepare(candidate)
        self.assertEqual(len(batch),1)

    def test_illegal_parameter_and_unknown_target_still_rejected(self):
        for changes in ({'config_diff':{'candidate_k':999}}, {'target_bad_cases':['made-up']}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                self.prepare({**self.proposal(),**changes})

    def test_prompt_carries_five_class_diagnosis_and_all_fifteen_parameters(self):
        from app.optimization import build_agent_prompt
        system,prompt=build_agent_prompt(self.rows(),DEFAULT_PIPELINE_CONFIG,[],[],['A','B','C'])
        self.assertIn('action_name',system)
        self.assertEqual(len(prompt['allowed_parameter_values']),15)
        self.assertEqual(prompt['bad_cases'][0]['question_id'],'Q1')
        self.assertEqual(prompt['bad_cases'][0]['diagnosis_category'],'回答问题')
        self.assertTrue(prompt['bad_cases'][0]['reason'])
        self.assertIn('retrieval_trace',self.rows()[0]['result']['programmatic_metrics'])
        self.assertNotIn('retrieval_trace',prompt['bad_cases'][0])
        self.assertNotIn('coverage_obligations',prompt)
        self.assertEqual(prompt['priority_parameters']['回答问题'],['prompt_strategy','generation_thinking'])
