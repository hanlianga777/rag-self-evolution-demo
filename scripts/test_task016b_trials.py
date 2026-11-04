"""Offline checks of 016b billing guards and checkpoint reuse; no formal database."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
import task016b_trials as trials
from app.paid_run import paid_request
from app.telemetry import record_usage


class TrialChecks(unittest.TestCase):
    def test_interrupted_requests_keep_bounded_cost_without_repeating(self):
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary)
            (out / 'jobs').mkdir()
            saved = {'calls': [{'provider': 'DeepSeek', 'model': 'deepseek-flash',
                                'status': 'unknown', 'reservation_usd': .06}]}
            (out / 'jobs/interrupted.ledger.json').write_text(json.dumps(saved))
            with patch.object(trials, 'OUT', out):
                cost = trials.money()
                self.assertEqual(cost['unknown'], 1)
                self.assertEqual(cost['unbounded_unknown'], 0)
                self.assertEqual(cost['known_usd'], 0)
                self.assertEqual(cost['usd'], .06)
                self.assertIsNone(trials.job('interrupted', 'judge', lambda: self.fail('duplicate request')))
                with patch('app.paid_schedule.schedule_status', return_value={'off_peak_only': True, 'peak_now': False}):
                    def independent():
                        with paid_request('DeepSeek', 'deepseek-flash', {'max_tokens': 65536}):
                            record_usage({'provider': 'DeepSeek', 'requested_model': 'deepseek-flash',
                                          'status': 'ok', 'prompt_tokens': 100, 'completion_tokens': 100,
                                          'prompt_cache_hit_tokens': 0, 'prompt_cache_miss_tokens': 100,
                                          'call_started_at': '2026-11-04T04:30:00+00:00'})
                        return 'completed'
                    self.assertEqual(trials.job('independent', 'judge', independent), 'completed')
                saved['calls'][0].pop('reservation_usd')
                (out / 'jobs/interrupted.ledger.json').write_text(json.dumps(saved))
                self.assertEqual(trials.money()['unbounded_unknown'], 1)

    def test_parallel_reservations_reuse_budget_and_unknown(self):
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary)
            (out / 'jobs').mkdir()
            sent = []
            def action():
                with paid_request('DeepSeek', 'deepseek-flash', {'max_tokens': 65536}):
                    sent.append(1)
                    record_usage({'provider': 'DeepSeek', 'requested_model': 'deepseek-flash',
                                  'status': 'ok', 'prompt_tokens': 100, 'completion_tokens': 100,
                                  'prompt_cache_hit_tokens': 0, 'prompt_cache_miss_tokens': 100,
                                  'call_started_at': '2026-11-04T04:30:00+00:00'})
                return {'saved': True}
            with patch.object(trials, 'OUT', out), patch('app.paid_schedule.schedule_status', return_value={'off_peak_only': True, 'peak_now': False}):
                with ThreadPoolExecutor(max_workers=3) as pool:
                    rows = list(pool.map(lambda n: trials.job(str(n), 'judge', action), range(3)))
                self.assertTrue(all(r == {'saved': True} for r in rows))
                trials.job('0', 'judge', action)
                self.assertEqual(len(sent), 3)
                self.assertEqual(trials.money()['unknown'], 0)
                with patch.object(trials, '_money_unlocked', return_value={'usd': 2.99, 'unknown': 0}):
                    self.assertIsNone(trials.job('over-budget', 'judge', action))
                self.assertEqual(len(sent), 3)
                with patch.object(trials, '_money_unlocked', return_value={'usd': 0, 'unknown': 1}):
                    self.assertIsNone(trials.job('unknown', 'judge', action))
                self.assertEqual(len(sent), 3)
                self.assertIn('超过3美元', json.loads((out / 'jobs/over-budget.json').read_text())['error'])
                def invalid():
                    from app.providers import ProviderInvalidResponse
                    action()
                    raise ProviderInvalidResponse('support not located', raw_provider_response='saved invalid JSON')
                self.assertIsNone(trials.job('format', 'judge', invalid))
                self.assertIsNone(trials.job('format', 'judge', action))
                self.assertEqual(len(sent), 4)
                self.assertEqual(trials.job('format', 'judge', action, repair_invalid=True), {'saved': True})
                self.assertEqual(len(sent), 5)
                self.assertEqual(len(json.loads((out / 'jobs/format.ledger.json').read_text())['calls']), 2)


if __name__ == '__main__':
    unittest.main()
