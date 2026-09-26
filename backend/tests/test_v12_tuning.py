import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from app.governance import GovernanceStore
from app.policy import DEFAULT_PIPELINE_CONFIG


class TuningV12Tests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.store = GovernanceStore(Path(self.directory.name) / 'demo.db')
        self.baseline = self.store.create_evaluation_run({'id': 'GD-fixture', 'question_ids': [], 'questions': []}, DEFAULT_PIPELINE_CONFIG, {'model': 'fixture'})
        self.store.finish_evaluation_run(self.baseline, 'completed', {})
        self.experiment = self.store.create_experiment(self.baseline)

    def candidate(self, label, diff, qualified=True, fixed=1):
        self.store.save_candidate(self.experiment, label, {**DEFAULT_PIPELINE_CONFIG, **diff}, {'round': 1, 'candidate_label': label, 'changed_parameters': diff})
        key = f'{self.experiment}-{label}'
        self.store.finish_candidate(key, 'evaluated', {'qualification': {'qualified': qualified}, 'regression': {'passed': True}, 'gates': {'passed': qualified}, 'target_bad_cases_fixed': fixed})
        return key

    def test_report_accepts_one_qualified_after_all_started_work_finishes(self):
        winner = self.candidate('A', {'top_k': 6})
        self.candidate('B', {'candidate_k': 24}, False)
        result = self.store.confirm_experiment_report(self.experiment, winner, 'test_human')
        self.assertEqual(result['winner_id'], winner)
        self.assertEqual(result['actor'], 'test_human')

    def test_report_cannot_confirm_while_a_candidate_is_running(self):
        winner = self.candidate('A', {'top_k': 6})
        pending = self.candidate('B', {'candidate_k': 24}, False)
        self.store.finish_candidate(pending, 'running', {})
        with self.assertRaises(ValueError):
            self.store.confirm_experiment_report(self.experiment, winner, 'test_human')

    def test_d_uses_effective_failed_source_and_preserves_winner_conflicts(self):
        winner = self.candidate('A', {'top_k': 6})
        source = self.candidate('B', {'candidate_k': 24}, False)
        self.candidate('C', {'top_k': 4, 'min_score': .1}, False, fixed=0)
        self.store.confirm_experiment_report(self.experiment, winner, 'test_human')
        composite = self.store.create_composite(self.experiment)
        self.assertEqual(composite['config']['top_k'], 6)
        self.assertEqual(composite['config']['candidate_k'], 24)
        self.assertEqual(composite['config']['min_score'], 0)
        self.assertIn(source, [item['candidate_id'] for item in composite['reasoning']['sources']])
        self.assertEqual(composite['status'], 'generated')

    def test_no_effective_composite_keeps_winner_without_fake_d(self):
        winner = self.candidate('A', {'top_k': 6})
        self.store.confirm_experiment_report(self.experiment, winner, 'test_human')
        result = self.store.create_composite(self.experiment)
        self.assertEqual(result['status'], 'no_effective_composite')
        self.assertEqual(result['winner_id'], winner)
        self.assertEqual(len(self.store.candidates(self.experiment)), 1)

    def test_reservation_is_counted_on_start_and_keeps_one_slot_for_d(self):
        for number in range(11):
            self.store.save_candidate(self.experiment, str(number), DEFAULT_PIPELINE_CONFIG, {'candidate_label': 'A'})
            self.store.reserve_candidate_evaluation(f'{self.experiment}-{number}')
        self.store.save_candidate(self.experiment, 'extra', DEFAULT_PIPELINE_CONFIG, {'candidate_label': 'B'})
        with self.assertRaises(ValueError):
            self.store.reserve_candidate_evaluation(f'{self.experiment}-extra')
        with self.assertRaises(ValueError):
            self.store.reserve_candidate_evaluation(f'{self.experiment}-0')
        self.assertEqual(self.store.experiment(self.experiment)['evaluation_budget']['used'], 11)

    def test_late_agent_trace_cannot_erase_report(self):
        winner = self.candidate('A', {'top_k': 6})
        self.store.confirm_experiment_report(self.experiment, winner, 'test_human')
        self.store.create_composite(self.experiment)
        before = self.store.experiment(self.experiment)['result']
        self.store.save_agent_trace(self.experiment, 'failed', {}, 'late response')
        after = self.store.experiment(self.experiment)['result']
        self.assertEqual(after['report_confirmation'], before['report_confirmation'])
        self.assertEqual(after['composite'], before['composite'])

    def test_restart_terminalizes_reserved_execution_without_refunding_budget(self):
        self.store.save_candidate(self.experiment, 'A', DEFAULT_PIPELINE_CONFIG, {'candidate_label': 'A'})
        key = f'{self.experiment}-A'
        self.store.reserve_candidate_evaluation(key)
        self.store.interrupt_evaluation_runs()
        self.assertEqual(self.store.candidate(key)['status'], 'failed')
        self.assertEqual(self.store.experiment(self.experiment)['evaluation_budget']['used'], 1)
        self.store.reserve_candidate_evaluation(key)
        self.assertEqual(self.store.experiment(self.experiment)['evaluation_budget']['used'], 2)

    def test_parallel_reservations_do_not_exceed_abc_allowance(self):
        for number in range(12):
            self.store.save_candidate(self.experiment, str(number), DEFAULT_PIPELINE_CONFIG, {'candidate_label': 'A'})
        def reserve(number):
            try:
                self.store.reserve_candidate_evaluation(f'{self.experiment}-{number}')
                return True
            except ValueError:
                return False
        with ThreadPoolExecutor(max_workers=4) as pool:
            self.assertEqual(sum(pool.map(reserve, range(12))), 11)
        self.assertEqual(self.store.experiment(self.experiment)['evaluation_budget']['used'], 11)

    def test_restart_of_d_restores_winner_recommendation(self):
        winner = self.candidate('A', {'top_k': 6})
        self.candidate('B', {'candidate_k': 24}, False)
        self.store.confirm_experiment_report(self.experiment, winner, 'test_human')
        composite = self.store.create_composite(self.experiment)
        self.store.reserve_candidate_evaluation(composite['id'])
        self.store.refresh_recommendation(self.experiment)
        self.store.interrupt_evaluation_runs()
        result = self.store.recommendation(self.experiment)['result']
        self.assertEqual(result['recommended_candidate'], winner)
        self.assertEqual(result['status'], 'Recommended')
