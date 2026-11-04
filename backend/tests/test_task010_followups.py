"""Offline follow-up orchestration, temporary files only."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from app.followups import FollowupJobs


class FollowupTests(unittest.TestCase):
    def test_calibration_continues_after_technical_error_and_keeps_checkpoint(self):
        with TemporaryDirectory() as directory:
            store = SimpleNamespace(database_path=Path(directory) / 'empty.db')
            jobs = FollowupJobs(store, None)
            source = {'id': 'fixture', 'judge': {'model': 'fixture'}}
            cases = [{'question_id': 'one'}]
            runner = Mock()
            def run(_runner, _source, _cases, _effort, state, save):
                state['cases']['one'] = {'attempts': [], 'technical_error': 'fixture failure'}
                save()
                state['cases']['two'] = {'attempts': [], 'scored_result': {'passed': True}}
                save()
            with patch('app.followups.read_baseline', return_value=(source, cases)), patch('app.followups.calibration_plan', return_value={}), patch('app.followups.run_calibration', side_effect=run), patch('app.followups.comparison_rows', return_value=[{'题号': 'Q01'}]), patch('app.followups.EvaluationRunner', return_value=runner):
                jobs._run('fixture', 'low')
            result = jobs.progress('fixture', 'low')
            self.assertEqual(result['status'], 'failed')
            self.assertEqual(result['technical_failed'], 1)
            self.assertEqual(result['completed'], 1)
            self.assertNotIn('error', result)
            state = json.loads(jobs.path('fixture', 'low').read_text())
            self.assertEqual(state['cases']['one']['technical_error'], 'fixture failure')
            self.assertTrue(state['cases']['two']['scored_result']['passed'])
            runner.answer.assert_not_called()

    def test_repeated_start_does_not_launch_second_worker(self):
        with TemporaryDirectory() as directory:
            store = SimpleNamespace(database_path=Path(directory) / 'empty.db')
            jobs = FollowupJobs(store, None)
            source = {'id': 'fixture'}
            with patch('app.followups.read_baseline', return_value=(source, [])), patch('app.followups.threading.Thread') as thread:
                jobs.start('fixture', 'low')
                jobs.start('fixture', 'low')
            self.assertEqual(thread.return_value.start.call_count, 1)

    def test_review_summary_counts_runs_not_questions(self):
        with TemporaryDirectory() as directory:
            jobs = FollowupJobs(SimpleNamespace(database_path=Path(directory) / 'empty.db'), None)
            path = jobs.path('fixture', 'review')
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({'_job': {'status': 'running'}, 'cases': {'one': {'regression_review': {'runs': [{'scored_result': {'passed': False}}, {'execution': {}}]}}}}))
            result = jobs.progress('fixture', 'review')
            self.assertEqual(result['completed'], 1)
            self.assertEqual(result['planned'], 4)
            self.assertFalse(result['complete'])
