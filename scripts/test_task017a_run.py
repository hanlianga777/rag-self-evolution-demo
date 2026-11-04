"""No network: cap and price boundary enforced at each individual request."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import task017a_run as task
from app.paid_run import paid_request, controlled_run, accounting_only
from app.telemetry import record_usage


class BillingTests(unittest.TestCase):
    def test_existing_resume_child_is_recovered_when_marker_still_points_to_parent(self):
        self.recovered_child = True
        self.test_interrupted_replay_uses_formal_resume_and_keeps_saved_answers()

    def test_completed_status_with_technical_failure_resumes_only_missing_case(self):
        self.resume_status = 'completed'
        self.test_interrupted_replay_uses_formal_resume_and_keeps_saved_answers()

    def test_interrupted_replay_uses_formal_resume_and_keeps_saved_answers(self):
        from contextlib import redirect_stdout, nullcontext
        from io import StringIO
        from types import SimpleNamespace
        from unittest.mock import Mock
        cases = [{'question_id': str(i), 'model_answer': 'saved', 'programmatic_metrics': {
            'latency_ms': 10, 'ttft_ms': 1, 'retrieval_trace': {'final': []}}} for i in range(50)]
        old = {'id': 'partial', 'status': getattr(self, 'resume_status', 'partial'), 'result': {
            'evaluation_complete': False, 'technical_failed': 1, 'judge_replay': {'source_run_id': 'original'}}}
        active = {'id': 'resumed', 'status': 'running', 'config': {'run_target': 'baseline'},
            'result': {'judge_replay': {'source_run_id': 'original'}}}
        finished = {**active, 'status': 'completed', 'result': {'bad_case_count': 0, 'technical_failed': 0}}
        store = SimpleNamespace(dataset_snapshots=lambda: [{'id': 'target'}],
            evaluation_run=lambda key: {'partial': old, 'resumed': active}[key],
            evaluation_case_results=lambda _: cases,
            connection=lambda: nullcontext(SimpleNamespace(execute=lambda sql, args: SimpleNamespace(
                fetchone=lambda: ('resumed',) if getattr(self, 'recovered_child', False) and args[0] == 'partial' else None))))
        runner = Mock(); runner.start_baseline.return_value = ('resumed', [], active['config'])
        runner.execute_baseline.return_value = finished
        with tempfile.TemporaryDirectory() as temporary, patch.object(task, 'OUT', Path(temporary)), \
                patch.object(task, 'SOURCES', {'max': 'original'}), patch.object(task, 'ledger', return_value=None), \
                patch('app.evaluation.EvaluationRunner', return_value=runner), redirect_stdout(StringIO()):
            (Path(temporary) / 'frozen.json').write_text(json.dumps({'id': 'target'}))
            marker = Path(temporary) / 'replay-max.json'
            marker.write_text(json.dumps({'id': 'partial'}))
            task.replays(SimpleNamespace(store=store, ai_service=None))
            result = json.loads(marker.read_text())
        if getattr(self, 'recovered_child', False): runner.start_baseline.assert_not_called()
        else: runner.start_baseline.assert_called_once_with('partial', automatic=True)
        runner.start_judge_replay.assert_not_called()
        self.assertEqual(result['id'], 'resumed')
        self.assertEqual(result['previous_run_ids'], ['partial'])

    def test_price_is_rechecked_after_waiting_for_the_budget_lock(self):
        from app.governance import GovernanceStore
        flat = {'off_peak_only': True, 'peak_now': False}
        with tempfile.TemporaryDirectory() as temporary, patch.object(task, 'OUT', Path(temporary)):
            GovernanceStore(Path(temporary) / 'isolated.db')
            paid = task.ledger('boundary')
            with patch('app.paid_schedule.schedule_status', side_effect=[flat, {**flat, 'peak_now': True}, flat, flat]) as status, \
                    controlled_run(paid), accounting_only():
                with paid_request('DeepSeek', 'deepseek-flash', {'max_tokens': 128}): pass
            self.assertEqual(status.call_count, 4)
            self.assertFalse(paid.calls[0]['price_check']['peak_now'])

    def test_plain_paidrun_restore_keeps_request_guard_and_context_binding(self):
        from types import SimpleNamespace
        from app.paid_run import PaidRun, current_paid_run
        from app.paid_policy import restore_paid_context
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'restored.ledger.json'
            policy = {'kind': 'off_peak_usd_cap_v1', 'budget_usd': 5,
                'ledger_directory': temporary, 'database_path': temporary + '/isolated.db'}
            from app.governance import GovernanceStore
            GovernanceStore(Path(policy['database_path']))
            original = PaidRun(path, identity='bound', identity_check=lambda: 'bound', request_policy=policy)
            loaded = PaidRun.load_accounting(path, lambda: 'bound')
            self.assertEqual(loaded.request_policy, policy)
            store = SimpleNamespace(database_path=Path(policy['database_path']))
            binding = {'ledger_path': str(path), 'ledger_identity': 'bound'}
            with restore_paid_context(store, binding):
                self.assertEqual(current_paid_run().identity, 'bound')
                with patch('app.paid_policy.policy_cost', return_value={'budget_used_upper_usd': 5}), \
                        patch('app.paid_schedule.schedule_status', return_value={'off_peak_only': True, 'peak_now': False}), \
                        self.assertRaisesRegex(RuntimeError, 'limit'):
                    with paid_request('DeepSeek', 'deepseek-flash', {'max_tokens': 128}):
                        self.fail('restored policy must reject before RPC')
            self.assertIsNone(current_paid_run())

    def test_peak_wait_budget_and_unknown_charge_bound(self):
        flat = {'off_peak_only': True, 'peak_now': False, 'price_config_version': 'fixture'}
        with tempfile.TemporaryDirectory() as temporary, patch.object(task, 'OUT', Path(temporary)):
            from app.governance import GovernanceStore
            GovernanceStore(Path(temporary) / 'isolated.db')
            ledger = task.ledger('fixture')
            with patch('app.paid_schedule.schedule_status', side_effect=[{**flat, 'peak_now': True}, flat, flat]), \
                    patch('app.paid_policy.time.sleep') as sleep, controlled_run(ledger), accounting_only():
                with paid_request('DeepSeek', 'deepseek-flash', {'max_tokens': 128}):
                    record_usage({'provider': 'DeepSeek', 'requested_model': 'deepseek-flash', 'status': 'ok',
                        'prompt_tokens': 10, 'completion_tokens': 10, 'prompt_cache_hit_tokens': 0,
                        'prompt_cache_miss_tokens': 10, 'call_started_at': '2026-11-04T12:00:00+00:00'})
            sleep.assert_called_once_with(1)
            self.assertFalse(ledger.calls[0]['price_check']['peak_now'])
            self.assertEqual(task.money()['deepseek_calls'], 1)
            with patch('app.paid_schedule.schedule_status', return_value=flat), \
                    patch('app.paid_policy.policy_cost', return_value={'budget_used_upper_usd': 5}), \
                    controlled_run(ledger), accounting_only(), self.assertRaisesRegex(RuntimeError, 'limit'):
                with paid_request('DeepSeek', 'deepseek-flash', {'max_tokens': 128}):
                    self.fail('must stop before sending')
            self.assertEqual(len(ledger.calls), 1)
            ledger.stopped = None
            with patch('app.paid_schedule.schedule_status', return_value=flat), \
                    controlled_run(ledger), accounting_only():
                with paid_request('DeepSeek', 'deepseek-flash', {'max_tokens': 128}): pass
            cost = task.money()
            self.assertEqual(cost['unknown'], 1)
            self.assertGreater(cost['budget_used_upper_usd'], cost['known_usd'])
            self.assertEqual(len(json.loads(ledger.path.read_text())['calls']), 2)


if __name__ == '__main__': unittest.main()
