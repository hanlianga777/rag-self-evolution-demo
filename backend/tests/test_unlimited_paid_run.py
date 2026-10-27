"""Offline regression for payment accounting without a monetary ceiling."""
import json
import tempfile
import unittest
from pathlib import Path

from app.paid_run import PaidRun, controlled_run, paid_request
from app.telemetry import record_usage


class UnlimitedPaidRunTests(unittest.TestCase):
    def test_missing_price_keeps_usage_and_marks_cost_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            run = PaidRun(Path(directory) / 'ledger.json', None, {}, {}, identity_check=lambda: {})
            with controlled_run(run), paid_request('DeepSeek', 'configured-model', {'max_tokens': 10}):
                record_usage({'provider': 'DeepSeek', 'requested_model': 'configured-model', 'status': 'ok', 'prompt_tokens': 100, 'completion_tokens': 100})
            saved = json.loads(run.path.read_text())
            self.assertTrue(saved['cost_unknown'])
            self.assertEqual(saved['calls'][0]['usage']['prompt_tokens'], 100)
            self.assertIsNone(saved['calls'][0]['upper_estimate_yuan'])

    def test_usd_estimate_is_not_recorded_as_yuan(self):
        with tempfile.TemporaryDirectory() as directory:
            prices = {'model': {'provider': 'DeepSeek', 'input': 2, 'output': 8, 'max_output': 100, 'currency': 'USD'}}
            run = PaidRun(Path(directory) / 'ledger.json', None, prices, {}, identity_check=lambda: {})
            with controlled_run(run), paid_request('DeepSeek', 'model', {'max_tokens': 10}):
                record_usage({'provider': 'DeepSeek', 'requested_model': 'model', 'status': 'ok', 'prompt_tokens': 100, 'completion_tokens': 100})
            call = run.calls[0]
            self.assertIsNone(call['upper_estimate_yuan'])
            self.assertEqual(call['estimated_cost']['currency'], 'USD')
            self.assertGreater(call['estimated_cost']['amount'], 0)
            self.assertTrue(json.loads(run.path.read_text())['cost_unknown'])

    def test_legacy_low_budget_is_accounted_without_blocking(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'ledger.json'
            prices = {'model': {'provider': 'DeepSeek', 'input': 2, 'output': 8, 'max_output': 100}}
            run = PaidRun(path, 0.000001, prices, {'id': 1}, identity_check=lambda: {'id': 1})
            with controlled_run(run), paid_request('DeepSeek', 'model', {'max_tokens': 100}):
                record_usage({'provider': 'DeepSeek', 'requested_model': 'model', 'status': 'ok',
                              'prompt_tokens': 100, 'completion_tokens': 100})
            ledger = json.loads(path.read_text())
            self.assertFalse(ledger['budget_enforcement'])
            self.assertIsNone(ledger['available_yuan'])
            self.assertGreater(ledger['spent_yuan'], ledger['budget_yuan'])
            self.assertEqual(ledger['calls'][0]['status'], 'ok')

    def test_no_budget_and_unknown_request_still_stop(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'ledger.json'
            prices = {'model': {'provider': 'DeepSeek', 'input': 2, 'output': 8, 'max_output': 100}}
            run = PaidRun(path, None, prices, {'id': 1}, identity_check=lambda: {'id': 1})
            with controlled_run(run):
                with self.assertRaises(OSError):
                    with paid_request('DeepSeek', 'model', {'max_tokens': 10}):
                        raise OSError('network failure')
                with self.assertRaises(RuntimeError):
                    with paid_request('DeepSeek', 'model', {'max_tokens': 10}):
                        self.fail('must not repeat unknown request')
            saved = json.loads(path.read_text())
            self.assertNotEqual(saved['calls'][0]['status'], 'ok')
            self.assertIsNone(saved['calls'][0].get('upper_estimate_yuan'))
            self.assertTrue(saved['cost_unknown'])
