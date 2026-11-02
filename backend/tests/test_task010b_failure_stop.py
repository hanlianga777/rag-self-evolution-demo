"""Technical Judge recovery must never become a confirmed review target."""
import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from app.agent_inputs import prepare_baseline_rows, baseline_review_summary
from app.optimization import build_agent_prompt
from app.ai_service import AiService
from app.providers import ProviderInvalidResponse


class StopTests(unittest.TestCase):
    def test_followup_stops_before_ai_service_internal_retry(self):
        from app.providers import judge_fail_fast
        runtime=SimpleNamespace(provider=SimpleNamespace(judge=Mock(side_effect=ProviderInvalidResponse('fixture citation failure'))),model='fixture')
        with judge_fail_fast(), self.assertRaises(ProviderInvalidResponse):
            AiService.judge(runtime,'q','ref','answer','positive')
        self.assertEqual(runtime.provider.judge.call_count,1)

    def test_recovered_invalid_review_is_unknown_and_not_unstable_or_target(self):
        baseline={'dataset_snapshot_json':json.dumps({'questions':[]}), 'result':{'calibration_import':{},'bad_case_count':1,
            'baseline_review':{'cases':{'Q46':{'regression_review':{'status':'confirmed_regression','confirmed_regression':True,'failed_votes':2,'total_votes':3,
                'runs':[{'scored_result':{'judge_result':{'response_recovery':[{'error':'invalid support'}]}}}]}}}}}}
        baseline['result']['calibration_import']={'judge_thinking':'low'}
        rows=prepare_baseline_rows(baseline,[{'id':'b','question_id':'Q46','result':{'passed':False,'test_category':'negative'}}])
        self.assertFalse(rows[0]['result']['optimization_target'])
        self.assertIn('未知',rows[0]['result']['baseline_review_label'])
        self.assertIsNone(rows[0]['result']['baseline_review']['confirmed_regression'])
        self.assertEqual(baseline_review_summary(baseline)['target_count'],0)
        self.assertEqual(baseline_review_summary(baseline)['pending_count'],1)
        gate={'metric':'safe_rejection_rate','operator':'>=','actual':90,'threshold':95,'passed':False}
        _,prompt=build_agent_prompt(rows,{},[],[gate],list('ABC'))
        self.assertEqual(prompt['bad_cases'],[])
        self.assertEqual(prompt['unstable_cases'],[])
        self.assertEqual(len(prompt['review_pending_cases']),1)
        self.assertIn('归因未知',prompt['baseline_diagnosis_summary'][0]['root_cause_note'])
