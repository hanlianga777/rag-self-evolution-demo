"""Successful internal Judge recovery is a valid review vote (decision 14)."""
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

    def test_recovered_invalid_review_is_valid_target(self):
        baseline={'dataset_snapshot_json':json.dumps({'questions':[]}), 'result':{'calibration_import':{},'bad_case_count':1,
            'baseline_review':{'cases':{'Q46':{'regression_review':{'status':'confirmed_regression','confirmed_regression':True,'failed_votes':2,'total_votes':3,
                'runs':[{'scored_result':{'passed':True,'judge_result':{'response_recovery':[{'error':'invalid support'}]}}}]}}}}}}
        baseline['result']['calibration_import']={'judge_thinking':'low'}
        rows=prepare_baseline_rows(baseline,[{'id':'b','question_id':'Q46','result':{'passed':False,'test_category':'negative'}}])
        self.assertTrue(rows[0]['result']['optimization_target'])
        self.assertEqual(rows[0]['result']['baseline_review_label'],'真错（3 次错 2 次）')
        self.assertTrue(rows[0]['result']['baseline_review']['confirmed_regression'])
        self.assertEqual(baseline_review_summary(baseline)['target_count'],1)
        self.assertEqual(baseline_review_summary(baseline)['pending_count'],0)
        gate={'metric':'safe_rejection_rate','operator':'>=','actual':90,'threshold':95,'passed':False}
        _,prompt=build_agent_prompt(rows,{},[],[gate],list('ABC'))
        self.assertEqual(len(prompt['bad_cases']),1)
        self.assertEqual(prompt['unstable_cases'],[])
        self.assertEqual(prompt['review_pending_cases'],[])
        self.assertEqual(prompt['baseline_diagnosis_summary'][0]['root_causes'][0]['priority'],1)

    def test_unrecovered_review_stays_unknown(self):
        from app.agent_inputs import review_summary
        summary=review_summary({'technical_error':{'error':'retry exhausted'},
                                'regression_review':{'runs':[]}})
        self.assertEqual(summary['status'],'technical_failure')
        self.assertIsNone(summary['confirmed_regression'])

    def test_followup_recovered_stage_does_not_stop_or_count_as_failed(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path
        from unittest.mock import patch
        from app.followups import FollowupJobs
        checkpoint={'regression_review':{'status':'confirmed_regression','failed_votes':2,'total_votes':3,
            'runs':[{'attempts':[{'status':'error','error':'transport recovered'}],
                     'scored_result':{'passed':True,'judge_result':{'response_recovery':[{'error':'citation recovered'}]}}}]}}
        with TemporaryDirectory() as directory:
            jobs=FollowupJobs(SimpleNamespace(database_path=Path(directory)/'fixture.db'),None)
            runner=Mock()
            runner.review_baseline_errors.side_effect=lambda run_id,**kw:kw['on_progress']({'cases':{'Q46':checkpoint},'complete':True})
            with patch('app.followups.read_baseline',return_value=({'judge':{'model':'fixture'}},[{'passed':False}])),patch('app.followups.EvaluationRunner',return_value=runner):
                jobs._run('fixture','review')
            progress=jobs.progress('fixture','review')
            self.assertEqual(progress['status'],'completed')
            self.assertEqual(progress['technical_failed'],0)
            self.assertTrue(progress['complete'])
