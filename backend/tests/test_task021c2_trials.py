"""021c2: private sequential trials, using temporary frozen fixtures only."""
import copy
import fcntl
import json
import threading
import unittest
from unittest.mock import patch

import test_task021c_internal as fixtures
from app.evaluation_contract import evaluation_identity
from app.paid_run import REQUEST_LIMITS
from app.policy import ALLOWED_SEARCH_SPACE, GATE_DEFINITIONS, validate_candidate_config
import internal_recheck as internal


class TrialTests(unittest.TestCase):
    setUp = fixtures.InternalTests.setUp
    case = staticmethod(fixtures.InternalTests.case)

    def prepare(self):
        self.dependency = self.root / 'recheck'
        self.dep_state = internal.prepare(self.source.database_path, self.dependency, 'exp')
        return internal.prepare(self.source.database_path, self.out, 'exp', trials=True, dependency=self.dependency)

    def finish(self, out, job, failures=(0, 1)):
        store = internal.InternalStore(out / 'internal.db', migrate=False)
        for i, q in enumerate(self.snapshot['question_ids']):
            case = self.case(i not in failures)
            case['programmatic_metrics'].update(cost_estimation={'amount': .02, 'currency': 'USD'},
                                                judge_cost_estimation={'amount': .01, 'currency': 'USD'})
            store.record_evaluation_case(job['run_id'], q, case)
        store.finish_evaluation_run(job['run_id'], 'completed', {'evaluation_complete': True,
            'metrics': {g['metric']: 100 if g['operator'] == '>=' else 1 for g in GATE_DEFINITIONS}})

    def test_two_valid_complete_configs_and_idempotent_private_preparation(self):
        before = internal.protected_state(self.source.database_path)
        state = self.prepare()
        store = internal.InternalStore(self.out / 'internal.db', migrate=False)
        self.assertEqual([j['label'] for j in state['jobs']], ['内部-1', '内部-2'])
        for job, delta in zip(state['jobs'], ({'top_k': 6}, {'top_k': 6, 'prompt_strategy': 'Tiered'})):
            run = store.evaluation_run(job['run_id'])
            self.assertEqual(run['config'], {**self.config, **delta})
            self.assertTrue(validate_candidate_config({k: v for k, v in run['config'].items() if k in ALLOWED_SEARCH_SPACE})['valid'])
            self.assertEqual(run['judge'], self.judge)
            self.assertEqual(json.loads(run['dataset_snapshot_json']), self.snapshot)
            self.assertTrue(run['result']['internal_recheck'])
            self.assertIsNone(self.source.evaluation_run(job['run_id']))
        again = internal.prepare(self.source.database_path, self.out, 'exp', trials=True, dependency=self.dependency)
        self.assertEqual(again['jobs'], state['jobs'])
        self.assertEqual(before, internal.protected_state(self.source.database_path))
        with self.assertRaisesRegex(ValueError, '断点'):
            internal.prepare(self.source.database_path, self.out, 'exp')

    def test_unmatched_dependency_is_rejected_before_creating_trial_db(self):
        self.prepare()
        state = json.loads((self.dependency / 'state.json').read_text())
        state['jobs'][0]['source_run_id'] = 'other'
        internal.save(self.dependency / 'state.json', state)
        with self.assertRaisesRegex(ValueError, '复核'):
            internal.prepare(self.source.database_path, self.root / 'other', 'exp', trials=True, dependency=self.dependency)
        self.assertFalse((self.root / 'other/internal.db').exists())

    def test_trial_runner_reuses_partial_cases_and_never_repeats_completed_trial(self):
        state = self.prepare()
        store = internal.InternalStore(self.out / 'internal.db', migrate=False)
        job = state['jobs'][1]
        for q in self.snapshot['question_ids'][:10]:
            store.record_evaluation_case(job['run_id'], q, self.case(True))
        store.finish_evaluation_run(job['run_id'], 'partial', store.evaluation_run(job['run_id'])['result'])
        answers = []
        class Runtime:
            model = 'fixture'
            def answer(_, question, config):
                answers.append((question, config['top_k'], config['prompt_strategy']))
                return {'answer': '回答'}
        with patch('app.evaluation.EvaluationRunner.score_execution', return_value=self.case(True)):
            internal.execute_job(store, job, Runtime())
            internal.execute_job(store, job, Runtime())
        self.assertEqual(len(answers), 40)
        self.assertTrue(all(k == 6 and p == 'Tiered' for _, k, p in answers))
        self.assertEqual(len(store.evaluation_case_results(job['run_id'])), 50)

    def test_dependency_lock_orders_recheck_then_both_trials(self):
        self.judge['execution_snapshot'] = {'request_limits': REQUEST_LIMITS}
        self.judge['evaluation_identity'] = evaluation_identity(self.snapshot, self.judge)
        with self.source.connection() as db:
            db.execute('UPDATE evaluation_runs SET judge_json=?', (json.dumps(self.judge),))
        state = self.prepare()
        for job in state['jobs']:
            job['index'] = {'identity': 'fixture'}
        internal.save(self.out / 'state.json', state)
        calls = []
        waiting = threading.Event()
        real_save = internal.save
        def save(path, value):
            real_save(path, value)
            if value.get('queue_status') == 'waiting_for_recheck':
                waiting.set()
        class Runtime:
            model = 'fixture'
            def answer(_, question, config):
                calls.append(config['prompt_strategy'])
                return {'answer': '回答'}
        with (self.dependency / 'worker.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            with patch.object(internal, 'save', side_effect=save), \
                 patch.object(internal, 'runtime_for', return_value=(Runtime(), {'identity': 'fixture'})), \
                 patch('app.evaluation.EvaluationRunner.score_execution', return_value=self.case(True)):
                thread = threading.Thread(target=internal.worker, args=(self.out,), daemon=True)
                thread.start()
                try:
                    self.assertTrue(waiting.wait(3), 'worker should persist dependency queue state')
                    self.assertEqual(calls, [])
                    self.finish(self.dependency, self.dep_state['jobs'][0])
                finally:
                    fcntl.flock(lock, fcntl.LOCK_UN)
                    thread.join(15)
                self.assertFalse(thread.is_alive())
        saved = json.loads((self.out / 'state.json').read_text())
        self.assertIsNone(saved.get('worker_error'))
        self.assertEqual(calls, ['Grounded'] * 50 + ['Tiered'] * 50)
        self.assertTrue(saved['official_unchanged'])
        self.assertEqual(saved['queue_status'], 'completed')

    def test_incomplete_recheck_never_starts_paid_trials(self):
        self.prepare()
        with patch.object(internal, 'runtime_for', side_effect=AssertionError('must not start')):
            internal.worker(self.out)
        state = json.loads((self.out / 'state.json').read_text())
        self.assertIn('复核', state['worker_error'])
        self.assertFalse(list(self.out.glob('*-calls.json')))

    def test_official_evaluation_started_mid_trial_pauses_next_rpc(self):
        from app.paid_run import _run
        self.judge['execution_snapshot'] = {'request_limits': REQUEST_LIMITS}
        self.judge['evaluation_identity'] = evaluation_identity(self.snapshot, self.judge)
        with self.source.connection() as db:
            db.execute('UPDATE evaluation_runs SET judge_json=?', (json.dumps(self.judge),))
        state = self.prepare()
        self.finish(self.dependency, self.dep_state['jobs'][0])
        for job in state['jobs']:
            job['index'] = {'identity': 'fixture'}
        internal.save(self.out / 'state.json', state)
        official_id = []
        queue_states, requests = [], []
        def end_official(_seconds):
            saved = json.loads((self.out / 'state.json').read_text())
            queue_states.append(saved['queue_status'])
            self.source.finish_evaluation_run(official_id[0], 'completed', {})
        class Runtime:
            model = 'fixture'
            def answer(_, question, config):
                if len(requests) == 1:
                    official_id.append(self.source.create_evaluation_run(self.snapshot, self.config, self.judge))
                ledger = _run.get()
                ticket = ledger.begin('DeepSeek', 'fixture', {'max_tokens': 1})
                with self.source.connection() as db:
                    self.assertIsNone(db.execute("SELECT 1 FROM evaluation_runs WHERE status='running'").fetchone(),
                                      'internal RPC must pause while official evaluation is active')
                requests.append(question)
                ledger.settle(ticket, {'status': 'ok', 'provider': 'DeepSeek', 'requested_model': 'fixture',
                                       'prompt_tokens': 1, 'completion_tokens': 1})
                return {'answer': '回答'}
        with patch.object(internal, 'runtime_for', return_value=(Runtime(), {'identity': 'fixture'})), \
             patch('app.corpus.manifest_identity', return_value='fixture'), \
             patch('app.evaluation.EvaluationRunner.score_execution', return_value=self.case(True)), \
             patch.object(internal.time, 'sleep', side_effect=end_official):
            internal.worker(self.out)
        saved = json.loads((self.out / 'state.json').read_text())
        self.assertIsNone(saved.get('worker_error'))
        self.assertEqual(queue_states, ['waiting_for_official'])
        self.assertEqual(len(requests), 100)

    def test_active_worker_repeated_start_cannot_create_second_process(self):
        state = self.prepare()
        with (self.out / 'worker.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            with patch.object(internal.subprocess, 'Popen', side_effect=AssertionError('duplicate worker')):
                result = internal.start(self.source.database_path, self.out, 'exp', trials=True, dependency=self.dependency)
        self.assertTrue(result['already_started'])
        self.assertEqual(json.loads((self.out / 'state.json').read_text())['jobs'], state['jobs'])

    def test_changed_parameter_outside_authorized_delta_is_rejected(self):
        state = self.prepare()
        job = state['jobs'][0]
        store = internal.InternalStore(self.out / 'internal.db', migrate=False)
        with store.connection() as db:
            db.execute("UPDATE evaluation_runs SET config_json=json_set(config_json,'$.hyde',json('true')) WHERE id=?", (job['run_id'],))
        with self.assertRaisesRegex(ValueError, '配置'):
            internal.execute_job(store, job, None)

    def test_status_returns_only_queue_scalar_and_no_progress(self):
        self.prepare()
        value = internal.status(self.out)
        self.assertIn('queue_status', value)
        self.assertEqual(len(value['jobs']), 2)
        self.assertFalse(any(word in json.dumps(value) for word in ('question_id', 'metrics', 'technical_failed')))

    def test_compare_five_frozen_runs_and_changes_against_all_three_references(self):
        state = self.prepare()
        self.finish(self.dependency, self.dep_state['jobs'][0])
        for job in state['jobs']:
            self.finish(self.out, job, failures=(1,))
        report = self.root / 'comparison.md'
        with patch.object(internal, 'runtime_for', side_effect=AssertionError('offline only')):
            internal.compare(self.out, report)
        content = report.read_text()
        self.assertEqual(sum(line.startswith('| q') for line in content.splitlines()), 50)
        for name in ('Baseline', 'R3-C 原评测', 'R3-C 内部复核', '内部-1', '内部-2',
                     'safe_rejection_rate', 'latency_p50_seconds', 'latency_p99_seconds', '费用', '是否胜过 R3-C'):
            self.assertIn(name, content)
        self.assertIn('修好：q00', content)
        self.assertIn('弄坏：无', content)

    def test_compare_refuses_incomplete_dependency_without_report(self):
        state = self.prepare()
        for job in state['jobs']:
            self.finish(self.out, job)
        report = self.root / 'comparison.md'
        with self.assertRaisesRegex(ValueError, '50'):
            internal.compare(self.out, report)
        self.assertFalse(report.exists())

    def test_d_rule_uses_baseline_release_conditions_and_existing_winner_rule(self):
        self.assertTrue(hasattr(internal, 'trial_outcome'), 'missing saved-result D comparison')
        base = {q: self.case(i > 4) for i, q in enumerate(self.snapshot['question_ids'])}
        old = {q: self.case(i > 1) for i, q in enumerate(self.snapshot['question_ids'])}
        new = copy.deepcopy(old)
        for cases, amount in ((old, .02), (new, .01)):
            for c in cases.values():
                c['programmatic_metrics'].update(cost_estimation={'amount': amount, 'currency': 'USD'},
                    judge_cost_estimation={'amount': .01, 'currency': 'USD'})
        metrics = {g['metric']: 100 if g['operator'] == '>=' else 1 for g in GATE_DEFINITIONS}
        old_metrics = {**metrics, 'latency_p99_seconds': 2}
        self.assertTrue(internal.trial_outcome(base, old, new, old_metrics, metrics)['wins'])
        self.assertFalse(internal.trial_outcome(base, old, new, metrics, metrics)['wins'])
        new['q00']['passed'] = True
        self.assertTrue(internal.trial_outcome(base, old, new, metrics, metrics)['wins'])
        new['q10']['passed'] = False
        self.assertFalse(internal.trial_outcome(base, old, new, old_metrics, metrics)['wins'])
        new['q10']['passed'] = True
        bad_metrics = {**metrics, 'safe_rejection_rate': 90}
        self.assertFalse(internal.trial_outcome(base, old, new, metrics, bad_metrics)['wins'])
        del new['q49']
        self.assertFalse(internal.trial_outcome(base, old, new, metrics, metrics)['wins'])


if __name__ == '__main__':
    unittest.main()
