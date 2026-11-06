"""Prerequisite-aware D decisions, with Stub transport and disposable databases."""
import json
import unittest
from copy import deepcopy
from unittest.mock import Mock

import test_task021a_composite as refinement
from test_evaluation_context import Settings
from app.composite import build_d_facts
from app.policy import DEFAULT_PIPELINE_CONFIG


class PrerequisiteTests(unittest.TestCase):
    result = refinement.RefinementTests.result
    validate = refinement.RefinementTests.validate
    def setUp(self):
        refinement.RefinementTests.setUp(self)
        self.replace_case( {'passed':False, 'programmatic_metrics':{'retrieval_trace':{
            'candidates':[{'chunk_id':'c'}], 'reranked':[{'chunk_id':str(i)} for i in range(5)]+[{'chunk_id':'c'}], 'final':[]}}})
        self.refresh_facts()

    def replace_case(self, value):
        with self.store.connection() as db:
            db.execute('update evaluation_case_results set result_json=? where run_id=? and question_id=?',
                       (json.dumps(value),self.winner['result']['evaluation_run_id'],'q2'))

    def refresh_facts(self):
        self.facts = build_d_facts(self.store, self.store.evaluation_run(self.baseline), self.winner, [self.winner,self.other])

    def suggestion(self):
        value = refinement.RefinementTests.suggestion(self)
        value['changes'][0]['side_effect_check'].update(
            same_premise_evidence='没有前提相同的Top6观察',
            different_premise_evidence='来源候选池12、思考max；赢家候选池24、思考high，前提不同',
            risk_checklist='重点核对q3和赢家修好的q；安全拒答95门槛、P99不超过60秒')
        return value

    def provider(self, *values):
        return Mock(complete=Mock(side_effect=[json.dumps(v) for v in values]),settings=Settings('fixture','https://example.invalid','fixture'))

    def decline(self):
        value=self.suggestion()
        value.update(should_generate_d=False,proposed_config_diff={},changes=[],explanation='预测Top6副作用，拒绝生成')
        return value

    def test_profiles_compare_other_parameters_with_winner(self):
        p=next(p for p in self.facts['parameter_profiles']['top_k'] if p['value']==6)
        observation=p['observations'][0]
        self.assertEqual(observation['prerequisite_differences'],{
            'candidate_k':{'observed':12,'winner':24},'generation_thinking':{'observed':'max','winner':'high'}})
        self.assertIn('前提不同',observation['premise_label'])
        self.assertIn('候选',observation['premise_label'])
        with self.store.connection() as db:
            db.execute('update candidate_configs set config_json=? where id=?',(json.dumps({**self.winner_config,'top_k':6}),self.other['id']))
        self.other=self.store.candidate(self.other['id']);self.refresh_facts()
        observation=next(p for p in self.facts['parameter_profiles']['top_k'] if p['value']==6)['observations'][0]
        self.assertEqual(observation['premise_label'],'前提与 Winner 相同')
        self.assertEqual(observation['winner_config_diff'],{'top_k':6})

    def test_available_repair_forces_retry_instead_of_predictive_decline(self):
        result=self.store.create_composite(self.experiment,self.provider(self.decline(),self.suggestion()))
        self.assertEqual(result['status'],'generated',result)
        state=self.store.experiment(self.experiment)['result']['composite']
        self.assertEqual(state['provider_calls'],2)
        self.assertIn('必须生成D',state['attempts'][0]['validation_error'])
        repair=next(r for r in state['facts']['usable_repairs'] if r['parameter']=='top_k')
        self.assertEqual((repair['question_id'],repair['value']),('q2',6))
        self.assertIn('6',repair['evidence_basis'])

    def test_three_predictive_declines_are_noncompliant(self):
        result=self.store.create_composite(self.experiment,self.provider(*[self.decline()]*3))
        self.assertEqual((result['status'],result['outcome'],result['provider_calls']),('failed','validation_failed',3))
        self.assertNotIn('candidate_id',result)

    def test_no_usable_repair_allows_decline(self):
        self.replace_case({'passed':False})
        result=self.store.create_composite(self.experiment,self.provider(self.decline()))
        self.assertEqual(result['outcome'],'declined')
        self.assertEqual(result['facts']['usable_repairs'],[])

    def test_out_of_reach_evidence_and_winner_reversal_are_not_usable(self):
        self.replace_case({'passed':False,'programmatic_metrics':{'retrieval_trace':{
            'candidates':[{'chunk_id':'c'}], 'reranked':[{'chunk_id':str(i)} for i in range(6)]+[{'chunk_id':'c'}], 'final':[]}}})
        self.refresh_facts()
        self.assertEqual(self.facts['usable_repairs'],[])
        self.replace_case({'passed':False,'programmatic_metrics':{'retrieval_trace':{
            'candidates':[{'chunk_id':'c'}], 'reranked':[{'chunk_id':str(i)} for i in range(5)]+[{'chunk_id':'c'}], 'final':[]}}})
        with self.store.connection() as db:
            db.execute('update candidate_configs set config_json=? where id=?',(json.dumps({**DEFAULT_PIPELINE_CONFIG,'top_k':6,'generation_thinking':'low'}),self.other['id']))
        self.other=self.store.candidate(self.other['id']);self.refresh_facts()
        self.assertEqual(self.facts['usable_repairs'],[])

    def test_invalid_pipeline_option_does_not_force_a_d(self):
        with self.store.connection() as db:
            db.execute('update candidate_configs set config_json=? where id=?',
                       (json.dumps({**DEFAULT_PIPELINE_CONFIG,'top_k':7}),self.other['id']))
        self.other=self.store.candidate(self.other['id']);self.refresh_facts()
        self.assertEqual(self.facts['usable_repairs'],[])

    def test_missing_prerequisite_risk_check_is_rejected(self):
        value=self.suggestion();del value['changes'][0]['side_effect_check']['different_premise_evidence']
        with self.assertRaisesRegex(ValueError,'前提'):self.validate(value)

    def test_old_decline_is_archived_but_latest_decision_is_idempotent(self):
        old={'status':'no_effective_composite','outcome':'declined','facts':{'version':'winner-refinement-1'},
             'suggestion':self.decline(),'provider_calls':2,'attempts':[{'provider_raw_text':'old exact text'}]}
        with self.store.connection() as db:
            state=json.loads(db.execute('select result_json from experiments where id=?',(self.experiment,)).fetchone()[0])
            state['composite']=deepcopy(old)
            db.execute('update experiments set result_json=? where id=?',(json.dumps(state),self.experiment))
        provider=self.provider(self.suggestion())
        result=self.store.create_composite(self.experiment,provider)
        self.assertEqual(result['status'],'generated',result)
        state=self.store.experiment(self.experiment)['result']
        self.assertEqual(state['composite_history'],[old])
        self.assertEqual(self.store.create_composite(self.experiment,provider)['id'],result['id'])
        self.assertEqual(state['composite']['provider_calls'],1)
