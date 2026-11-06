"""Private runs must never enter the demo DB; all fixtures are temporary."""
import copy
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from api_fixture import main
from fastapi.testclient import TestClient
from app.governance import GovernanceStore
from app.evaluation_contract import VERSIONS, evaluation_identity
from app.policy import DEFAULT_PIPELINE_CONFIG
import internal_recheck as internal


class InternalTests(unittest.TestCase):
    def setUp(self):
        clock = patch('app.paid_schedule.utc_now', return_value=datetime(2026, 11, 7, 12, tzinfo=timezone.utc))
        clock.start()
        self.addCleanup(clock.stop)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = GovernanceStore(self.root / 'demo.db')
        self.snapshot = {'id': 'golden', 'question_ids': [f'q{i:02}' for i in range(50)],
                         'questions': [{'id': f'q{i:02}', 'question': f'问题{i}', 'test_category': 'positive',
                                        'reference_answer': '参考', 'evidence': []} for i in range(50)]}
        self.judge = {**VERSIONS, 'model': 'fixture'}
        self.judge['evaluation_identity'] = evaluation_identity(self.snapshot, self.judge)
        self.base = self.source.create_evaluation_run(self.snapshot, DEFAULT_PIPELINE_CONFIG, self.judge)
        self.config = {**DEFAULT_PIPELINE_CONFIG, 'candidate_k': 24, 'generation_thinking': 'high',
                       'candidate_id': 'exp-R3-C', 'run_target': 'sandbox_candidate'}
        self.original = self.source.create_evaluation_run(self.snapshot, self.config, self.judge)
        for rid in (self.base, self.original):
            for i, q in enumerate(self.snapshot['question_ids']):
                self.source.record_evaluation_case(rid, q, self.case(i > (4 if rid == self.base else 1)))
            self.source.finish_evaluation_run(rid, 'completed', {'evaluation_complete': True})
        with self.source.connection() as db:
            db.execute('INSERT INTO experiments VALUES (?,?,?,?,?)', ('exp', self.base, 'completed',
                       json.dumps({'optimization_cycle': {'status': 'recommended'},
                                   'composite': {'status': 'no_effective_composite'},
                                   'report_confirmation': {'winner_id': 'exp-R3-C'}}), 'now'))
            db.execute('INSERT INTO candidate_configs VALUES (?,?,?,?,?,?,?)',
                       ('exp-R3-C', 'exp', 'evaluated', json.dumps(self.config),
                        json.dumps({'candidate_label': 'C', 'round': 3}),
                        json.dumps({'evaluation_run_id': self.original, 'qualification': {'qualified': True}}), 'now'))
            db.execute('INSERT INTO recommendations VALUES (?,?,?,?,?)',
                       ('exp', 'exp-R3-C', 'Recommended', '{}', 'now'))
        self.out = self.root / 'private'

    @staticmethod
    def case(passed, answer='回答', chunks=('c',)):
        return {'passed': passed, 'model_answer': answer, 'test_category': 'positive', 'severity': 'normal',
                'root_cause': {'primary': 'None'}, 'judge_result': {'reason': '评分要点覆盖不明确'},
                'programmatic_metrics': {'retrieval_trace': {
                    stage: [{'chunk_id': c} for c in chunks] for stage in ('candidates', 'reranked', 'final')}}}

    def prepare(self):
        return internal.prepare(self.source.database_path, self.out, 'exp')

    def test_private_storage_preserves_config_and_source_hash_and_is_idempotent(self):
        before = internal.protected_state(self.source.database_path)
        state = self.prepare()
        store = internal.InternalStore(self.out / 'internal.db', migrate=False)
        job = state['jobs'][0]
        run = store.evaluation_run(job['run_id'])
        self.assertEqual(run['config'], self.config)
        self.assertEqual(run['judge'], self.judge)
        self.assertEqual(json.loads(run['dataset_snapshot_json']), self.snapshot)
        self.assertTrue(run['result']['internal_recheck'])
        store.update_evaluation_progress(job['run_id'], {'completed': 0})
        self.assertTrue(store.evaluation_run(job['run_id'])['result']['internal_recheck'])
        self.assertEqual(self.prepare()['jobs'], state['jobs'])
        self.assertEqual(before, internal.protected_state(self.source.database_path))
        self.assertIsNone(self.source.evaluation_run(job['run_id']))

    def test_waiting_recommendation_does_not_create_private_db(self):
        with self.source.connection() as db:
            db.execute("UPDATE recommendations SET status='Needs Composite Evaluation'")
        with self.assertRaisesRegex(ValueError, '推荐'):
            self.prepare()
        self.assertFalse((self.out / 'internal.db').exists())

    def test_d_winner_selects_both_d_and_first_qualified_c(self):
        with self.source.connection() as db:
            db.execute("INSERT INTO candidate_configs SELECT 'exp-D',experiment_id,status,config_json,?,result_json,created_at FROM candidate_configs", (json.dumps({'candidate_label': 'D'}),))
            db.execute("UPDATE recommendations SET candidate_id='exp-D'")
        state = self.prepare()
        self.assertEqual([j['candidate_id'] for j in state['jobs']], ['exp-D', 'exp-R3-C'])

    def test_incomplete_original_is_rejected_without_new_run(self):
        with self.source.connection() as db:
            db.execute('DELETE FROM evaluation_case_results WHERE run_id=? AND question_id=?', (self.original, 'q49'))
        with self.assertRaisesRegex(ValueError, '50'):
            self.prepare()

    def test_private_path_cannot_be_demo_database(self):
        self.out.mkdir()
        (self.out / 'internal.db').symlink_to(self.source.database_path)
        with self.assertRaisesRegex(ValueError, '隔离'):
            self.prepare()

    def test_marked_run_absent_from_all_demo_display_apis_and_direct_lookup(self):
        # These endpoints feed Baseline history, experiments, Agent, release,
        # saved-answer verification, overview and the workspace summary.
        paths = ['/api/evaluations', '/api/evaluation?light=true', '/api/optimization?light=true',
                 '/api/versions', '/api/overview?light=true', '/api/workspace', '/api/bad-cases?light=true']
        with patch.object(main, 'store', self.source), TestClient(main.app) as client:
            before = {p: client.get(p).json() for p in paths}
            state = self.prepare()
            job = state['jobs'][0]
            private = internal.InternalStore(self.out / 'internal.db', migrate=False)
            private.record_evaluation_case(job['run_id'], 'q00', self.case(False), with_bad_case=True)
            private.finish_evaluation_run(job['run_id'], 'completed', {'evaluation_complete': True})
            for p in paths:
                response = client.get(p)
                self.assertEqual(response.status_code, 200, p)
                self.assertEqual(response.json(), before[p], p)
                self.assertNotIn(job['run_id'], response.text, p)
                self.assertNotIn('内部复核', response.text, p)
            self.assertEqual(client.get('/api/evaluations/' + job['run_id']).status_code, 404)
            self.assertEqual(client.get('/api/experiments/' + job['run_id']).status_code, 404)

    def test_each_question_once_and_restart_reuses_saved_cases(self):
        state = self.prepare()
        store = internal.InternalStore(self.out / 'internal.db', migrate=False)
        job = state['jobs'][0]
        calls = []
        class Runtime:
            model = 'fixture'
            def answer(self, question, config):
                calls.append((question, copy.deepcopy(config)))
                return {'answer': '回答'}
        # Only external generation/scoring are replaced; the actual frozen runner,
        # checkpoint persistence, idempotence, and private DB are exercised.
        with patch('app.evaluation.EvaluationRunner.score_execution', return_value=self.case(True)):
            internal.execute_job(store, job, Runtime())
            internal.execute_job(store, job, Runtime())
        self.assertEqual(len(calls), 50)
        self.assertEqual(len({q for q, _ in calls}), 50)
        self.assertTrue(all(c == self.config for _, c in calls))
        self.assertTrue(store.evaluation_run(job['run_id'])['result']['internal_recheck'])
        self.assertEqual(len(store.evaluation_case_results(job['run_id'])), 50)

    def test_partial_resume_skips_saved_questions_and_paid_generation_checkpoint(self):
        state = self.prepare()
        store = internal.InternalStore(self.out / 'internal.db', migrate=False)
        job = state['jobs'][0]
        for q in self.snapshot['question_ids'][:10]:
            store.record_evaluation_case(job['run_id'], q, self.case(True))
        store.update_evaluation_progress(job['run_id'], {'checkpoints': {
            'q10': {'attempts': [], 'execution': {'answer': '已付费保存', 'retrieval_trace': {'final': []}}}}})
        store.finish_evaluation_run(job['run_id'], 'partial', store.evaluation_run(job['run_id'])['result'], '进程中断')
        calls = []
        class Runtime:
            model = 'fixture'
            def answer(self, question, config):
                calls.append(question)
                return {'answer': '回答'}
        with patch('app.evaluation.EvaluationRunner.score_execution', return_value=self.case(True)):
            internal.execute_job(store, job, Runtime())
        self.assertEqual(len(calls), 39)
        self.assertNotIn('问题10', calls)
        self.assertEqual(len(store.evaluation_case_results(job['run_id'])), 50)

    def test_compare_writes_all_fifty_rows_without_runtime_or_paid_calls(self):
        from app.policy import GATE_DEFINITIONS
        state = self.prepare()
        job = state['jobs'][0]
        store = internal.InternalStore(self.out / 'internal.db', migrate=False)
        for i, q in enumerate(self.snapshot['question_ids']):
            store.record_evaluation_case(job['run_id'], q, self.case(i > 1 and i != 5))
        metrics = {g['metric']: (100 if g['operator'] == '>=' else 1) for g in GATE_DEFINITIONS}
        store.finish_evaluation_run(job['run_id'], 'completed', {'evaluation_complete': True, 'metrics': metrics})
        report = self.root / 'comparison.md'
        with patch.object(internal, 'runtime_for', side_effect=AssertionError('compare must be offline')):
            result = internal.compare(self.out, report)
        content = report.read_text()
        self.assertTrue(result['official_unchanged'])
        self.assertEqual(sum(line.startswith('| q') for line in content.splitlines()), 50)
        self.assertIn('稳定修好：q02、q03、q04', content)
        self.assertIn('只一次新坏', content)
        self.assertIn('复核后仍满足候选合格条件：是', content)
        self.assertIn('latency_p50_seconds', content)
        self.assertIn('latency_p99_seconds', content)

    def test_compare_rejects_unfinished_run_without_emitting_report(self):
        self.prepare()
        report = self.root / 'comparison.md'
        with self.assertRaisesRegex(ValueError, '50'):
            internal.compare(self.out, report)
        self.assertFalse(report.exists())

    def test_weekday_peak_waits_then_resumes_without_override(self):
        from app.paid_schedule import wait_for_off_peak
        self.prepare()
        store = internal.InternalStore(self.out / 'internal.db', migrate=False)
        pauses = []
        times = [datetime(2026, 11, 6, 9, 30, tzinfo=timezone.utc),
                 datetime(2026, 11, 6, 10, 0, tzinfo=timezone.utc)]
        with patch('app.paid_schedule.utc_now', side_effect=times), patch('app.paid_schedule.time.sleep'):
            wait_for_off_peak(store, 'internal:test', pauses.append)
        self.assertEqual([p['paused'] for p in pauses], [True, False])
        self.assertEqual(pauses[0]['resume_at'], '2026-11-06T10:00:00+00:00')
        self.assertTrue(all(p['peak_price_override'] is False for p in pauses))

    def test_status_exposes_no_question_progress_or_results(self):
        state = self.prepare()
        result = internal.status(self.out)
        self.assertEqual(result['jobs'][0]['status'], 'running')
        self.assertTrue(result['official_unchanged'])
        self.assertFalse(result['worker_alive'])
        self.assertEqual(set(result['jobs'][0]), {'run_id', 'status', 'price_pause'})
        self.assertNotIn('question_id', json.dumps(result))
        self.assertNotIn('completed', json.dumps(result))


class ComparisonTests(unittest.TestCase):
    def test_all_binary_categories_including_unchanged_pass(self):
        wants = {(False, True, True): '稳定修好', (False, True, False): '只一次修好',
                 (False, False, True): '只一次修好', (False, False, False): '稳定仍错',
                 (True, False, False): '稳定新坏', (True, True, False): '只一次新坏',
                 (True, False, True): '只一次新坏', (True, True, True): '稳定答对'}
        for values, want in wants.items():
            self.assertEqual(internal.category(*values), want)

    def test_attribution_is_saved_evidence_only_and_conservative(self):
        a = InternalTests.case(True)
        examples = [(InternalTests.case(False, chunks=('x',)), '检索不同'),
                    (InternalTests.case(False, answer='不同回答'), '生成不同'),
                    (InternalTests.case(False), '判分边界'),
                    ({'passed': False}, '不确定')]
        for b, want in examples:
            label, reason = internal.attribute(a, b)
            self.assertEqual(label, want)
            self.assertTrue(reason)

    def test_attribution_preserves_sign_decimal_and_unit_case(self):
        for first, second in (('阈值-10', '阈值+10'), ('阈值1.5', '阈值15'), ('距离1m', '距离1M')):
            with self.subTest(first=first, second=second):
                label, _ = internal.attribute(InternalTests.case(True, answer=first),
                                               InternalTests.case(False, answer=second))
                self.assertEqual(label, '生成不同')

    def test_qualification_blocks_new_critical_but_allows_ordinary_new_failure(self):
        from app.policy import GATE_DEFINITIONS
        metrics = {g['metric']: (100 if g['operator'] == '>=' else 1) for g in GATE_DEFINITIONS}
        base = {f'q{i}': InternalTests.case(i > 2) for i in range(50)}
        rerun = copy.deepcopy(base)
        rerun['q0']['passed'] = rerun['q1']['passed'] = True
        rerun['q4']['passed'] = False
        golden = {q: {'severity': 'normal'} for q in base}
        self.assertTrue(internal.qualification(base, rerun, metrics, golden)['qualified'])
        golden['q4']['criticality'] = 'high'
        self.assertFalse(internal.qualification(base, rerun, metrics, golden)['qualified'])
        del rerun['q49']
        self.assertFalse(internal.qualification(base, rerun, metrics, golden)['qualified'])


if __name__ == '__main__':
    unittest.main()
