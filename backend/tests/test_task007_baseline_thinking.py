"""Task 007 regressions: mocked HTTP and disposable databases only."""
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from test_round0_thinking import Response
from app.ai_service import AiService
from app.config import Settings, load_settings
from app.providers import DeepSeekProvider, ProviderRequestError, thinking_task
from app.evaluation import EvaluationRunner
import test_reviewed_csv_machine_checks as machine_fixture


class BaselineThinkingTests(unittest.TestCase):
    def setUp(self):
        judge=patch.dict('os.environ', {'JUDGE_THINKING':'low'})
        judge.start();self.addCleanup(judge.stop)

    def test_backend_setting_default_and_validation(self):
        from pathlib import Path
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            empty = Path(directory) / 'missing.env'
            self.assertEqual(load_settings({}, empty).baseline_thinking, 'max')
            for effort in ('off', 'low', 'high', 'max'):
                self.assertEqual(load_settings({'BASELINE_THINKING': effort}, empty).baseline_thinking, effort)
            with self.assertRaisesRegex(ValueError, 'BASELINE_THINKING'):
                load_settings({'BASELINE_THINKING': 'typo'}, empty)

    def test_baseline_high_reaches_http_and_judge_remains_independent_low(self):
        provider = DeepSeekProvider(Settings('fixture', 'https://invalid', 'deepseek-flash'))
        service = AiService(object(), object(), provider, False)
        service.retriever = SimpleNamespace(retrieve=lambda *a, **k: [{'chunk_id': 'C1', 'content': 'source'}])
        requests = []
        def http(request, **kwargs):
            body = json.loads(request.data)
            requests.append(body)
            if body.get('stream'):
                return Response(b'data: {"choices":[{"delta":{"content":"answer"},"finish_reason":"stop"}]}\n\ndata: {"choices":[],"usage":{"prompt_tokens":1,"completion_tokens":2}}\n\ndata: [DONE]\n\n')
            return Response(b'{"choices":[{"message":{"content":"ok"},"finish_reason":"stop"}],"usage":{"prompt_tokens":1,"completion_tokens":2}}')
        with patch('urllib.request.urlopen', side_effect=http), patch('app.paid_run.payment_usage'):
            result = service.answer('question', {'run_target': 'baseline', 'generation_thinking': 'high'})
            default = service.answer('question', {'run_target': 'baseline'})
            with thinking_task('judge'):
                provider.complete('judge', 'answer')
            with thinking_task('judge','off'), self.assertRaises(ProviderRequestError):
                provider.complete('judge','answer')
        self.assertEqual(result['generation_thinking'], 'high')
        self.assertEqual(default['generation_thinking'], 'max')
        self.assertEqual([r['reasoning_effort'] for r in requests], ['high', 'max', 'low'])
        with self.assertRaises(ProviderRequestError):
            service.answer('question', {'run_target': 'baseline', 'generation_thinking': 'typo'})

    def test_baseline_freezes_effort_and_configuration_identity(self):
        from app.evaluation_contract import experiment_config_identity
        items = [{'id': str(i), 'question': 'q', 'reference_answer': None, 'evidence': [], 'raw': {},
                  'test_category': group, 'negative_subtype': subtype}
                 for i, (group, subtype) in enumerate([('positive', None), ('ablation', None),
                    ('negative', 'safety_critical'), ('negative', 'prompt_injection')])]
        store = SimpleNamespace(dataset_snapshots=lambda: [{'snapshot': {'question_ids': [i['id'] for i in items]}}],
                                active_production=lambda: None)
        runtime = SimpleNamespace(model='fixture', provider=SimpleNamespace(settings=SimpleNamespace(baseline_thinking='high')))
        runner = EvaluationRunner(store, runtime)
        with patch.object(runner, 'snapshot_items', return_value=items):
            _, _, config, judge = runner.baseline_inputs()
        self.assertEqual(config['generation_thinking'], 'high')
        self.assertEqual(judge['execution_snapshot']['generation_thinking']['reasoning_effort'], 'high')
        self.assertEqual(judge['judge_thinking']['reasoning_effort'], 'low')
        self.assertNotEqual(experiment_config_identity(config), experiment_config_identity({**config, 'generation_thinking': 'max'}))


class BatchReasonTests(unittest.TestCase):
    setUp = machine_fixture.MachineChecksImportTests.setUp
    machine_import = machine_fixture.MachineChecksImportTests.machine_import
    def test_machine_review_batch_http_preserves_reason(self):
        from api_fixture import main
        from fastapi.testclient import TestClient
        imported = self.machine_import()
        ids = imported['question_ids']
        rows = [{'id': key, 'qualification_status': 'machine_qualified'} for key in ids]
        with patch.object(main, 'store', self.store), patch.object(self.store, 'candidate_rows', return_value=rows), \
             patch.object(self.store, 'gate_summary', return_value={'status': 'ready'}), \
             patch.object(self.store, '_finalize_golden_validation', side_effect=lambda item, *a, **k: (item['raw'], {})):
            response = TestClient(main.app).post('/api/governance/review-batch',
                json={'question_ids': ids, 'actor': '用户', 'confirmed_manual_review': True, 'reason': '本次确认原因'},
                headers={'Origin': 'http://localhost:5174'})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.store.review_history(ids[0])[0]['reason'], '本次确认原因')
