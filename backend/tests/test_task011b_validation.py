"""Offline task011a response replay: no production DB and no Provider."""
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from app.optimization import prepare_response, build_agent_prompt
from app.policy import DEFAULT_PIPELINE_CONFIG
from diagnostic_fixture import retrieval_case
from test_optimization_contract import drafts


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.historical_raw=Path(__file__).with_name('fixtures').joinpath('task011a_drafts.json').read_text()
        self.baseline={**DEFAULT_PIPELINE_CONFIG,'generation_thinking':'high'}
        response=drafts()
        for candidate,targets in zip(response['candidates'],(['Q29','Q24'],['Q27','Q06','Q04'],['Q29','Q24'])):
            candidate['target_bad_cases']=targets
        response['candidates'][1]['config_diff']['generation_thinking']='low'
        self.raw=json.dumps(response)
        self.rows=[]
        for number in (4,6,24,27,29,46):
            question=f'CSV-20261101100758945425-{number:02}'
            self.rows.append({'id':'BC-EVAL-fixture-'+question,'question_id':question,
                'result':retrieval_case()[0], 'diagnostic_view':{'primary_root_cause':'Retrieval',
                    'display_question_id':f'Q{number:02}'}})
        self.corpus=patch('app.diagnostics._current_corpus',return_value=(retrieval_case()[1],{'corpus':'one'}))
        self.corpus.start();self.addCleanup(self.corpus.stop)

    def validate(self, raw=None):
        audit=self.audit={}
        result,batch=prepare_response(raw or self.raw,self.baseline,self.rows,[],0,1,list('ABC'),None,[],audit)
        return result,batch,audit

    def test_current_abc_passes_id_validation_and_preserves_raw_targets(self):
        result,batch,audit=self.validate()
        self.assertEqual([c[0] for c in batch],['R1-A','R1-B','R1-C'])
        self.assertEqual(result['candidates'][0]['target_bad_cases'],['Q29','Q24'])
        self.assertEqual(batch[0][2]['observed_evidence'],[self.rows[4]['question_id'],self.rows[2]['question_id']])
        self.assertEqual(audit['rejected_candidates'],[])
        self.assertEqual(audit['failed_parameter_signatures'],[])

    def test_historical_011a_drafts_do_not_bypass_current_round_contract(self):
        # Historical drafts predate the mandatory retrospective, checked before directions.
        with self.assertRaisesRegex(ValueError,'prior_round_review'):
            self.validate(self.historical_raw)
        self.assertEqual(self.audit.get('failed_parameter_signatures',[]),[])

    def test_expected_impact_must_name_a_target_question(self):
        data=json.loads(self.raw)
        data['candidates'][0]['adjustments']=[{'parameter':'top_k','baseline_value':4,
            'candidate_value':6,'expected_impact':'提高证据覆盖'}]
        with self.assertRaisesRegex(ValueError,'预期影响须点名目标题号'):
            self.validate(json.dumps(data))
        self.assertEqual(self.audit.get('failed_parameter_signatures',[]),[])

    def test_unknown_display_number_is_rejected_without_failed_signature(self):
        data=json.loads(self.raw);data['candidates'][0]['target_bad_cases']=['Q99']
        with self.assertRaisesRegex(ValueError,'Q99'):
            self.validate(json.dumps(data))
        audit=self.audit
        self.assertEqual(audit['rejected_candidates'][0]['field'],'target_bad_cases')
        self.assertIn('Q99',audit['rejected_candidates'][0]['reason'])
        self.assertEqual(audit.get('failed_parameter_signatures',[]),[])

    def test_formal_question_and_bad_case_ids_are_accepted(self):
        data=json.loads(self.raw)
        data['candidates'][0]['target_bad_cases']=[self.rows[4]['question_id'],self.rows[2]['id']]
        _,batch,_=self.validate(json.dumps(data))
        self.assertEqual(batch[0][0],'R1-A')

    def test_display_and_formal_alias_cannot_duplicate_same_target(self):
        data=json.loads(self.raw)
        data['candidates'][0]['target_bad_cases']=['Q29',self.rows[4]['question_id']]
        with self.assertRaisesRegex(ValueError,'重复引用'):
            self.validate(json.dumps(data))
        self.assertIn('重复引用',self.audit['rejected_candidates'][0]['reason'])

    def test_prompt_documents_display_numbers(self):
        system,_=build_agent_prompt([],DEFAULT_PIPELINE_CONFIG,[],[],list('ABC'))
        self.assertIn('可用展示题号',system)
        self.assertIn('"target_bad_cases":["Q04"]',system)
