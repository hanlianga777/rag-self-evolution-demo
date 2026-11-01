"""Task006 launch failures stop the new batch without another request."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from api_fixture import main
from app.providers import ProviderUnavailable


class Task006QualityStartTests(unittest.TestCase):
    def run_failed_probe(self, probe):
        state = {'attempt_id': 'fixture'}
        items = [{'id': key, 'raw': {'coverage_slot': key}, 'probe_status': 'probe_pending'} for key in ('Q01', 'Q02')]
        class Store:
            def generation_run(self, *args, **kwargs):
                return {'question_ids': ['Q01', 'Q02'], 'artifacts': {'hard_validation': {
                    'stop_on_technical_error': True, 'quality_rerun': state}}}
            def update_quality_rerun(self, _, changes): state.update(deepcopy(changes))
            def question(self, key): return next(q for q in items if q['id'] == key)
            def capture_quality(self, key, **kwargs): return self.question(key), {'content_hash': key}
            def candidate_rows(self, keys): return [{'quality_audit': None}]
            def probe_history(self, key): return []
        store = Store()
        store.run_probe = Mock(side_effect=probe if isinstance(probe, Exception) else None,
                               return_value=probe if not isinstance(probe, Exception) else None)
        service = SimpleNamespace(retriever=None, answerability_check=None, negative_subtype_check=None,
                                  quality_check=Mock())
        with patch('app.golden_v2.validate_golden_candidate', return_value={'valid': True}):
            main._run_quality_rerun('fixture', ['Q01', 'Q02'], store, service,
                                    SimpleNamespace(chunks=lambda: []))
        self.assertEqual(store.run_probe.call_count, 1)
        service.quality_check.assert_not_called()
        self.assertEqual(state['status'], 'failed')
        self.assertEqual(state['technical_failed'], 1)
        self.assertNotIn('Q02', state['slots'])
        return state

    def test_first_technical_error_stops_without_trying_next_question(self):
        state = self.run_failed_probe(ProviderUnavailable('fixture: provider connection unavailable'))
        self.assertIn('fixture: provider connection unavailable', state['error'])

    def test_uncertain_probe_is_not_counted_as_completed_machine_check(self):
        self.run_failed_probe({'status': 'failed', 'probe_details': {'probe_execution_status': 'uncertain',
            'negative_checks': {'answerability': {'answerable': None, 'reason': 'fixture invalid provider JSON'}}}})


if __name__ == '__main__':
    unittest.main()
