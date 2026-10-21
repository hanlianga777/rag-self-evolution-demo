"""New paid entrypoints require explicit authorization; GET cannot start work."""
import unittest
from unittest.mock import patch,Mock
from fastapi.testclient import TestClient
from api_fixture import main

class ReplayApiTests(unittest.TestCase):
    def test_preflight_readonly_and_post_authorization_required(self):
        runner=Mock();runner.judge_replay_preflight.return_value={'can_replay':True,'reusable':50}
        with patch.object(main,'EvaluationRunner',return_value=runner),TestClient(main.app) as client:
            self.assertEqual(client.get('/api/evaluations/source/judge-replay/preflight').json()['reusable'],50)
            self.assertEqual(client.post('/api/evaluations/source/judge-replay',json={'authorize_provider':False},headers={'Origin':'http://127.0.0.1:5174'}).status_code,409)
            runner.start_judge_replay.assert_not_called()
    def test_invalid_eligibility_does_not_start_thread_or_generate(self):
        runner=Mock();runner.start_judge_replay.side_effect=ValueError('Final source incomplete')
        with patch.object(main,'EvaluationRunner',return_value=runner),patch.object(main.threading,'Thread') as thread,TestClient(main.app) as client:
            thread.reset_mock()  # App startup monitor is separate from this explicit action.
            response=client.post('/api/evaluations/source/judge-replay',json={'authorize_provider':True},headers={'Origin':'http://127.0.0.1:5174'})
            self.assertEqual(response.status_code,409);thread.assert_not_called()
    def test_diagnostic_enrichment_requires_explicit_authorization(self):
        with patch.object(main.ai_service,'resolve_diagnostic') as semantic,TestClient(main.app) as client:
            response=client.post('/api/evaluations/source/cases/q/resolve-diagnostics',json={'authorize_provider':False},headers={'Origin':'http://127.0.0.1:5174'})
            self.assertEqual(response.status_code,409);semantic.assert_not_called()
