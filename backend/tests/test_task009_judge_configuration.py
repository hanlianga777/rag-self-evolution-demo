"""Task009 Judge effort and standalone scripts: mock calls, temporary SQLite only."""
import asyncio
from contextlib import closing
from copy import deepcopy
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from app.config import load_settings
from app.evaluation_contract import VERSIONS, evaluation_identity
from app.judge_replay import resolve_question_ids
from app.paid_run import provider_task
from app.providers import judge_thinking, thinking_config, thinking_task
from scripts import judge_calibration, task007_review


class JudgeConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.empty = Path(self.tmp.name) / '.env'
        self.empty.write_text('')
        self.env = patch.dict(os.environ, {'RAG_DEMO_ENV_PATH': str(self.empty)}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_settings_default_file_and_validation(self):
        self.assertEqual(load_settings({}, self.empty).judge_thinking, 'max')
        self.empty.write_text('JUDGE_THINKING=low\n')
        self.assertEqual(load_settings({}, self.empty).judge_thinking, 'low')
        self.assertEqual(load_settings({'JUDGE_THINKING': 'high'}, self.empty).judge_thinking, 'high')
        for effort in ('off', '', 'typo'):
            with self.assertRaisesRegex(ValueError, 'JUDGE_THINKING'):
                load_settings({'JUDGE_THINKING': effort}, self.empty)

    def test_judge_context_is_frozen_and_independent_from_generation(self):
        with judge_thinking('low'):
            os.environ['JUDGE_THINKING'] = 'high'
            with thinking_task('candidate', 'off'):
                self.assertEqual(thinking_config()['thinking']['type'], 'disabled')
                with provider_task('judge'):
                    self.assertEqual(thinking_config()['reasoning_effort'], 'low')
                with provider_task('agent'):
                    self.assertEqual(thinking_config()['reasoning_effort'], 'high')
            with judge_thinking('max'):
                self.assertEqual(thinking_config('judge')['reasoning_effort'], 'max')
            self.assertEqual(thinking_config('judge')['reasoning_effort'], 'low')
        self.assertEqual(thinking_config('judge')['reasoning_effort'], 'high')
        with self.assertRaises(ValueError):
            with judge_thinking('off'):
                self.fail('invalid Judge effort must not enter context')

    def test_concurrent_runs_do_not_share_effort(self):
        async def run(effort):
            with judge_thinking(effort):
                await asyncio.sleep(0)
                return thinking_config('judge')['reasoning_effort']
        async def all_runs():
            return await asyncio.gather(run('low'), run('high'), run('max'))
        self.assertEqual(asyncio.run(all_runs()), ['low', 'high', 'max'])
        self.assertEqual(thinking_config('judge')['reasoning_effort'], 'max')


class JudgeScriptTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.database = Path(self.tmp.name) / 'synthetic.sqlite'
        questions = [{'id': f'fixture-{index}', 'coverage_slot': f'Q{index + 36:02d}',
                      'question': f'模拟问题{index}', 'test_category': 'negative' if subtype else 'positive',
                      'negative_subtype': subtype} for index, subtype in enumerate((None, 'clarify', 'safety_critical', 'prompt_injection'), 1)]
        self.snapshot = {'id': 'fixture-golden', 'question_ids': [q['id'] for q in questions], 'questions': questions, 'corpus_fingerprint': 'fixture-corpus'}
        judge = {**VERSIONS, 'model': 'fixture', 'common_identity_version': 'round0-common-1',
                 'judge_thinking': {'task': 'judge', 'thinking': {'type': 'enabled'}, 'reasoning_effort': 'max'}}
        judge['evaluation_identity'] = evaluation_identity(self.snapshot, judge)
        self.source = {'id': 'any-baseline', 'run_mode': 'real', 'data_source': 'real', 'status': 'completed',
                       'dataset_snapshot_json': json.dumps(self.snapshot), 'judge': judge, 'config': {'run_target': 'baseline'},
                       'result': {'evaluation_complete': True, 'technical_failed': 0}}
        self.cases = [{'question_id': q['id'], 'run_id': self.source['id'], 'passed': index % 2 == 0,
                       'model_answer': '已保存的回答', 'retrieved_chunks': [],
                       'programmatic_metrics': {'retrieval_trace': {'final': []}}} for index, q in enumerate(questions)]
        with closing(sqlite3.connect(self.database)) as db, db:
            db.execute('CREATE TABLE evaluation_runs(id TEXT, run_mode TEXT, data_source TEXT, status TEXT, dataset_snapshot_json TEXT, judge_json TEXT, config_json TEXT, result_json TEXT)')
            db.execute('INSERT INTO evaluation_runs VALUES(?,?,?,?,?,?,?,?)', tuple(self.source[k] if k not in {'judge', 'config', 'result'} else json.dumps(self.source[k]) for k in ('id', 'run_mode', 'data_source', 'status', 'dataset_snapshot_json', 'judge', 'config', 'result')))
            db.execute('CREATE TABLE evaluation_case_results(id INTEGER PRIMARY KEY,run_id TEXT,question_id TEXT,result_json TEXT)')
            for case in self.cases:
                db.execute('INSERT INTO evaluation_case_results(run_id,question_id,result_json) VALUES(?,?,?)', (self.source['id'], case['question_id'], json.dumps(case)))

    def test_resolve_arbitrary_display_numbers_and_reject_missing(self):
        self.assertEqual(resolve_question_ids(self.snapshot, ['Q38', 'fixture-3', 'Q38']), ['fixture-2', 'fixture-3'])
        with self.assertRaisesRegex(ValueError, '题号'):
            resolve_question_ids(self.snapshot, ['Q99'])

    def test_dry_script_entrypoints_never_import_main_write_db_or_call_provider(self):
        before = self.database.read_bytes()
        loaded = sys.modules.get('app.main')
        with patch('socket.create_connection', side_effect=AssertionError('offline only')):
            plan = judge_calibration.main(['--baseline', 'any-baseline', '--judge-thinking', 'low', '--output', str(Path(self.tmp.name) / 'compare.csv'), '--database', str(self.database)])
            review = task007_review.main(['--baseline', 'any-baseline', '--questions', 'Q38', 'Q40', '--database', str(self.database)])
        self.assertTrue(plan['dry_run'])
        self.assertEqual(plan['generation_calls'], 0)
        self.assertEqual(plan['provider_calls'], 0)
        self.assertEqual(review['question_ids'], ['fixture-2', 'fixture-4'])
        self.assertFalse(review['formal_scores_changed'])
        self.assertIs(sys.modules.get('app.main'), loaded)
        self.assertEqual(self.database.read_bytes(), before)
        self.assertEqual(sorted(p.name for p in Path(self.tmp.name).iterdir()), ['synthetic.sqlite'])

    def test_plan_identity_and_csv_focus_labels(self):
        low = judge_calibration.calibration_plan(self.source, self.cases, 'low')
        high = judge_calibration.calibration_plan(self.source, self.cases, 'high')
        self.assertNotEqual(low['new_evaluation_identity'], high['new_evaluation_identity'])
        self.assertNotEqual(low['new_evaluation_identity'], self.source['judge']['evaluation_identity'])
        rows = judge_calibration.comparison_rows(self.source, self.cases, {'fixture-1': {'scored_result': {'passed': True}}}, 'low')
        self.assertEqual([r['重点标记'] for r in rows], ['', '负向题', '安全关键题', '提示注入题'])
        self.assertEqual(rows[0]['是否一致'], '是')
        self.assertEqual(rows[1]['新判分'], '未知')
        self.assertEqual(rows[1]['负向子类型'], 'clarify')

    def test_calibration_reuses_saved_answers_resumes_and_does_not_write_formal_rows(self):
        before = deepcopy(self.source), deepcopy(self.cases), self.database.read_bytes()
        state = {'plan': judge_calibration.calibration_plan(self.source, self.cases, 'low'), 'cases': {}, 'complete': False}
        runner = SimpleNamespace(snapshot_items=lambda snapshot: snapshot['questions'], _require_generation_contract=Mock(),
                                 answer=Mock(side_effect=AssertionError('must never generate')), score_execution=Mock())
        def score(item, execution, **kwargs):
            self.assertEqual(execution['answer'], '已保存的回答')
            self.assertEqual(thinking_config('judge')['reasoning_effort'], 'low')
            return {'passed': True}
        runner.score_execution.side_effect = score
        with patch('app.corpus.manifest_identity', return_value='fixture-corpus'), patch('socket.create_connection', side_effect=AssertionError('offline only')):
            judge_calibration.run_calibration(runner, self.source, self.cases, 'low', state, lambda *a, **k: None)
            judge_calibration.run_calibration(runner, self.source, self.cases, 'low', state, lambda *a, **k: None)
        self.assertTrue(state['complete'])
        self.assertEqual(runner.score_execution.call_count, 4)
        runner.answer.assert_not_called()
        self.assertEqual((self.source, self.cases, self.database.read_bytes()), before)

    def test_tampered_source_or_target_blocks_before_calls(self):
        source = deepcopy(self.source)
        source['judge']['evaluation_identity'] = 'wrong'
        with self.assertRaisesRegex(ValueError, '身份'):
            judge_calibration.calibration_plan(source, self.cases, 'low')
        with self.assertRaisesRegex(ValueError, '相同'):
            judge_calibration.calibration_plan(self.source, self.cases, 'max')
        state = {'plan': judge_calibration.calibration_plan(self.source, self.cases, 'low'), 'cases': {}}
        runner = Mock()
        with self.assertRaisesRegex(ValueError, '变化'):
            judge_calibration.run_calibration(runner, self.source, self.cases, 'high', state, Mock())
        runner.score_execution.assert_not_called()


if __name__ == '__main__':
    unittest.main()
