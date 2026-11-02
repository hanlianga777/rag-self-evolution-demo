"""Task 009: synthetic records and recording Providers only; no network/real DB."""
import hashlib
import json
import unittest
from copy import deepcopy
from unittest.mock import patch

from app.optimization import build_agent_prompt, prepare_response
from app.policy import DEFAULT_PIPELINE_CONFIG, search_space_contract, validate_candidate_config
import test_generation_vnext as generation_fixture
from test_task008b_agent_input import fixture
from app.agent_inputs import prepare_baseline_rows


class Task009AgentRulesTests(unittest.TestCase):
    def rows(self):
        baseline, row = fixture()
        return prepare_baseline_rows(baseline, [row])

    def test_frozen_full_prompts_and_identity(self):
        from app.ai_service import generation_contract
        self.assertEqual(generation_contract()['generation_boundary_sha256'], 'ecc0a21cfb29dca1febb48f3c4f46f128cb12f8b94a8409b9ded08db427715af')
        service, provider = generation_fixture.GenerationVNextTests().service()
        expected = {'Grounded': 'c6add1d575f33d70a8f62d32edde885bd6a7d8dc0a0a9c2843728be987634d5f', 'Completeness': '32ed7d08d045b32d4e87351b321208faf6e0ffd755ebdeba5012bb5a26f804b7'}
        for strategy, digest in expected.items():
            service.answer('问题', {'prompt_strategy': strategy})
            self.assertEqual(hashlib.sha256(provider.requests[-1][0].encode()).hexdigest(), digest)
        service.answer('问题', {'prompt_strategy': 'Tiered'})
        for term in ('1–2', '能确定', '售后', '安全警告'):
            self.assertIn(term, provider.requests[-1][0])

    def test_disabled_budget_never_offers_tokenizer_values(self):
        self.assertEqual(search_space_contract()['retrieval_max_tokens']['allowed'], [False])
        for limit in (8192, 16384, 32768, 65536, True):
            self.assertFalse(validate_candidate_config({**DEFAULT_PIPELINE_CONFIG, 'retrieval_max_tokens': limit})['valid'])

    def test_program_summary_includes_failed_and_near_threshold_and_budget(self):
        gates = [{'metric':'safe_rejection_rate','operator':'>=','actual':90,'threshold':95,'passed':False},
                 {'metric':'positive_correctness','operator':'>=','actual':81,'threshold':80,'passed':True},
                 {'metric':'positive_completeness','operator':'>=','actual':90,'threshold':75,'passed':True}]
        _, prompt = build_agent_prompt(self.rows(), DEFAULT_PIPELINE_CONFIG, [], gates[:1], list('ABC'), baseline_gates=gates, evaluation_budget={'used':3,'max':12,'reserved_for_d':1})
        summary = prompt['baseline_diagnosis_summary']
        self.assertEqual([r['dimension'] for r in summary], ['safe_rejection_rate','positive_correctness'])
        self.assertEqual(summary[0]['gap'],5)
        self.assertEqual(prompt['evaluation_budget']['remaining_for_abc'],8)
        self.assertEqual(prompt['next_action'],'analyze_and_propose')
        self.assertNotIn('人工分析秘密', json.dumps(prompt,ensure_ascii=False))

    def candidate(self, label='A', diff=None):
        return {'id':label,'action_name':'补齐证据','hypothesis':'提高可用证据覆盖','why':'Q1候选中有标准证据',
                'target_bad_cases':['Q1'],'config_diff':diff or {'top_k':6},
                'expected_improvement':'预计修好Q1','risk':'可能增加耗时'}

    def prepare(self, candidates, audit=None, prior=None):
        audit = {} if audit is None else audit
        _, batch = prepare_response(json.dumps({'candidates':candidates},ensure_ascii=False),DEFAULT_PIPELINE_CONFIG,self.rows(),prior or [],0,1,list('ABC'),None,[],audit)
        return batch,audit

    def test_distinct_directions_and_multivalue_same_parameter_is_rejected(self):
        batch, audit = self.prepare([self.candidate('A',{'min_score':0.1}),self.candidate('B',{'min_score':0.2}),self.candidate('C',{'query_rewrite':True,'candidate_k':24})])
        self.assertEqual([r[2]['candidate_label'] for r in batch], ['A','C'])
        self.assertIn('方向',audit['rejected_candidates'][0]['reason'])
        reasoning=batch[0][2]
        self.assertTrue(reasoning['strategy_name'].startswith('「'))
        self.assertEqual(reasoning['core_idea'],'提高可用证据覆盖')
        self.assertEqual(reasoning['adjustments'][0], {'parameter':'min_score','baseline_value':0,'candidate_value':0.1,'expected_impact':'预计修好Q1'})
        self.assertEqual(reasoning['risks'],[{'question_ids':[],'metric':None,'reason':'可能增加耗时'}])

    def test_structured_risk_must_name_question_or_metric(self):
        proposal=self.candidate()
        proposal['risks']=[{'question_ids':[],'metric':None,'reason':'可能变差'}]
        with self.assertRaises(ValueError):self.prepare([proposal])
        proposal['risks'][0]['metric']='latency_p99_seconds'
        batch,_=self.prepare([proposal])
        self.assertEqual(batch[0][2]['risks'][0]['metric'],'latency_p99_seconds')

    def test_rejected_combination_signature_blocks_later_repetition(self):
        candidate=self.candidate(diff={'top_k':6,'candidate_k':24})
        broken={**candidate,'target_bad_cases':['invented']}
        with self.assertRaises(ValueError):
            self.prepare([broken], audit := {})
        self.assertEqual(len(audit['failed_parameter_signatures']),1)
        with self.assertRaisesRegex(ValueError,'失败'):
            self.prepare([candidate], {'failed_parameter_signatures':deepcopy(audit['failed_parameter_signatures'])})


if __name__ == '__main__': unittest.main()
