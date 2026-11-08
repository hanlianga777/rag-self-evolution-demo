import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from app.governance import GovernanceStore
from app.policy import DEFAULT_PIPELINE_CONFIG
from identity_fixture import completed_baseline, comparison_identity
from app.corpus import current_manifest, manifest_identity
from test_optimization_contract import trace_case
from test_v11_e2e import FixtureProvider


class TuningV12Tests(unittest.TestCase):
    def setUp(self):
        from diagnostic_fixture import install_corpus
        install_corpus(self)
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.store = GovernanceStore(Path(self.directory.name) / 'demo.db')
        snapshot={'id':'GD-current','question_ids':['Q1','Q2'],'questions':[{'id':key,'question':key,'test_category':'positive','evidence':[{'evidence_key_points':['操作前关闭设备。']}]} for key in ('Q1','Q2')], 'corpus_fingerprint':manifest_identity(current_manifest())}
        with self.store.connection() as db:
            db.execute("INSERT INTO dataset_versions VALUES (?, 'approved', 'human_review', ?, '2026-09-30')", (snapshot['id'],json.dumps(snapshot)))
        self.baseline = completed_baseline(self.store,snapshot=snapshot)
        self.store.record_evaluation_case(self.baseline,'Q2',trace_case())
        self.store.record_bad_case(self.baseline,"Q1","Retrieval","ordinary",trace_case())
        self.experiment = self.store.create_experiment(self.baseline)

    def candidate(self, label, diff, qualified=True, fixed=1):
        self.store.save_candidate(self.experiment, label, {**DEFAULT_PIPELINE_CONFIG, **diff}, {'round': 1, 'candidate_label': label, 'changed_parameters': diff, 'observed_evidence':['Q1']})
        key = f'{self.experiment}-{label}'
        snapshot=json.loads(self.store.evaluation_run(self.baseline)['dataset_snapshot_json'])
        run=self.store.create_evaluation_run(snapshot,self.store.candidate(key)['config'],self.store.evaluation_run(self.baseline)['judge'])
        repaired=['Q1' if label=='A' else 'Q2'] if fixed else []
        for question in ('Q1','Q2'):
            self.store.record_evaluation_case(run,question,{'passed':question in repaired})
        self.store.finish_evaluation_run(run,'completed',{'evaluation_complete':True})
        self.store.finish_candidate(key, 'evaluated', {**comparison_identity(self.store,self.baseline), 'evaluation_run_id':run, 'qualification': {'qualified': qualified},'release_qualification':{'qualified':qualified},'bad_case_count':2-len(repaired), 'regression': {'passed': True, 'new_critical_failures': 0}, 'gates': {'passed': qualified}, 'target_bad_cases_fixed': fixed, 'all_fixed_question_ids':repaired, 'net_improvement':fixed})
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
        source = self.candidate('B', {'top_k':4,'min_score':.2}, False)
        ineffective = self.candidate('C', {'top_k': 4, 'min_score': .1}, False, fixed=0)
        self.store.confirm_experiment_report(self.experiment, winner, 'test_human')
        composite = self.store.create_composite(self.experiment, FixtureProvider(), True)
        self.assertEqual(composite['config']['top_k'], 6)
        self.assertEqual(composite['config']['candidate_k'], DEFAULT_PIPELINE_CONFIG['candidate_k'])
        self.assertEqual(composite['config']['min_score'], .2)
        self.assertIn(source, [cid for item in composite['reasoning']['sources'] for cid in item['source_candidates']])
        self.assertNotIn(ineffective,[cid for item in composite['reasoning']['sources'] for cid in item['source_candidates']])
        self.assertEqual(self.store.candidate(source)['config']['top_k'],4)
        self.assertEqual(composite['reasoning']['intervention_direction'],'context_selection')
        self.assertEqual(composite['status'], 'generated')

    def test_no_effective_composite_keeps_winner_without_fake_d(self):
        winner = self.candidate('A', {'top_k': 6})
        self.store.confirm_experiment_report(self.experiment, winner, 'test_human')
        result = self.store.create_composite(self.experiment, FixtureProvider(), True)
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
        self.store.create_composite(self.experiment, FixtureProvider(), True)
        before = self.store.experiment(self.experiment)['result']
        self.store.save_agent_trace(self.experiment, 'failed', {}, 'late response')
        after = self.store.experiment(self.experiment)['result']
        self.assertEqual(after['report_confirmation'], before['report_confirmation'])
        self.assertEqual(after['composite'], before['composite'])

    def test_restart_terminalizes_execution_and_resume_reuses_one_budget_slot(self):
        self.store.save_candidate(self.experiment, 'A', DEFAULT_PIPELINE_CONFIG, {'candidate_label': 'A'})
        key = f'{self.experiment}-A'
        self.store.reserve_candidate_evaluation(key)
        self.store.interrupt_evaluation_runs()
        self.assertEqual(self.store.candidate(key)['status'], 'failed')
        self.assertEqual(self.store.experiment(self.experiment)['evaluation_budget']['used'], 0)
        self.store.reserve_candidate_evaluation(key)
        self.assertEqual(self.store.experiment(self.experiment)['evaluation_budget']['used'], 1)
        self.assertEqual(len(self.store.candidate(key)['reasoning']['sandbox_attempts']), 1)

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
        self.candidate('B', {'min_score':.2}, False)
        self.store.confirm_experiment_report(self.experiment, winner, 'test_human')
        composite = self.store.create_composite(self.experiment, FixtureProvider(), True)
        self.store.reserve_candidate_evaluation(composite['id'])
        self.store.refresh_recommendation(self.experiment)
        self.store.interrupt_evaluation_runs()
        result = self.store.recommendation(self.experiment)['result']
        self.assertEqual(result['recommended_candidate'], winner)
        self.assertEqual(result['status'], 'Recommended')
