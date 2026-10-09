"""Offline diagnosis and atomic reservation regressions; no Provider calls."""
import tempfile
from concurrent.futures import ThreadPoolExecutor
import unittest
from pathlib import Path
from unittest.mock import patch

from app.evaluation import EvaluationRunner, root_cause_layers
from app.governance import GovernanceStore


class DiagnosisTests(unittest.TestCase):
    def coverage(self, candidate, final):
        return {'required_chunk_ids': ['c1'], 'candidate_recall': {'all_hit': candidate}, 'final_context': {'all_hit': final}}

    def test_preliminary_diagnosis_uses_pipeline_evidence(self):
        tags = ['Generation Failure', 'Retrieval Failure']
        for candidate, final, expected in [(False, False, 'Retrieval'), (True, False, 'Ranking'), (True, True, 'Generation'), (None, False, 'Unknown')]:
            with self.subTest(expected=expected):
                self.assertEqual(root_cause_layers(tags, self.coverage(candidate, final), 'positive')[0], expected)

    def test_safety_primary_and_legacy_compatibility(self):
        self.assertEqual(root_cause_layers(['Generation Failure', 'Safety Failure'], self.coverage(False, False), 'positive')[0], 'Safety')
        self.assertEqual(root_cause_layers(['Generation Failure', 'Retrieval Failure']), ('Generation', ['Retrieval']))


    def test_case_result_keeps_failure_tags_and_pass_state(self):
        class OfflineRuntime:
            def answer(self, question, config):
                return {'answer': 'fixture wrong answer', 'retrieval': [], 'retrieval_trace': {'candidates': [], 'final': []}, 'latency_ms': 1}
            def judge(self, *args):
                return {'correctness': 0, 'faithfulness': 1, 'completeness': 0, 'behavior_pass': True, 'unsupported_claims': []}
        item = {'question': 'fixture question', 'reference_answer': 'fixture expected', 'raw': {}, 'test_category': 'positive', 'evidence': [{'source_chunk_ids': ['c1']} ]}
        result = EvaluationRunner(None, OfflineRuntime())._case_result(item, {})
        self.assertEqual(result['failure_tags'], ['Generation Failure', 'Retrieval Failure'])
        self.assertFalse(result['passed'])
        self.assertEqual(result['primary_root_cause'], 'Retrieval')
        self.assertEqual(result['root_cause']['diagnosis_status'], 'preliminary')


class ReservationTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        draft = root / 'fixture-draft.json'
        draft.write_text('{}')
        for target, value in [('app.governance.GOLDEN_DRAFT', draft), ('app.corpus.INDEX_DIR', root / 'index'), ('app.corpus.DOCUMENTS_DIR', root / 'documents'), ('app.corpus.UPLOADS_DIR', root / 'uploads')]:
            patcher = patch(target, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        identity = patch.object(GovernanceStore, 'current_baseline_identity', return_value={'current_experiment_id': 'exp'})
        identity.start()
        self.addCleanup(identity.stop)

    def test_reservation_uses_transaction_connection_and_identity_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            store = GovernanceStore(Path(directory) / 'test.db')
            with store.connection() as connection:
                connection.execute("INSERT INTO experiments VALUES ('exp', 'baseline', 'completed', '{}', 'now')")
            store.save_candidate('exp', 'A', {}, {})
            connections = []
            def guard(run_id=None, connection=None):
                self.assertEqual(run_id, 'baseline')
                self.assertIsNotNone(connection)
                connections.append(connection)
            with patch.object(store, 'require_current_baseline', side_effect=guard), patch.object(store, 'experiment', side_effect=AssertionError('cross-connection read')):
                reserved = store.reserve_candidate_evaluation('exp-A')
                self.assertEqual(reserved['status'], 'running')
                with self.assertRaises(ValueError):
                    store.reserve_candidate_evaluation('exp-A')
            self.assertEqual(len(connections), 1)

    def test_stale_identity_does_not_consume_attempt(self):
        with tempfile.TemporaryDirectory() as directory:
            store = GovernanceStore(Path(directory) / 'test.db')
            with store.connection() as connection:
                connection.execute("INSERT INTO experiments VALUES ('exp', 'baseline', 'completed', '{}', 'now')")
            store.save_candidate('exp', 'A', {}, {})
            with patch.object(store, 'require_current_baseline', side_effect=ValueError('stale')):
                with self.assertRaisesRegex(ValueError, 'stale'):
                    store.reserve_candidate_evaluation('exp-A')
            self.assertEqual(store.candidate('exp-A')['status'], 'generated')
            self.assertNotIn('sandbox_attempts', store.candidate('exp-A')['reasoning'])

    def test_concurrent_same_candidate_reserves_once(self):
        with tempfile.TemporaryDirectory() as directory:
            store = GovernanceStore(Path(directory) / 'test.db')
            with store.connection() as connection:
                connection.execute("INSERT INTO experiments VALUES ('exp', 'baseline', 'completed', '{}', 'now')")
            store.save_candidate('exp', 'A', {}, {})
            def reserve():
                try:
                    return store.reserve_candidate_evaluation('exp-A')['status']
                except ValueError:
                    return 'blocked'
            with patch.object(store, 'require_current_baseline', return_value={}):
                with ThreadPoolExecutor(max_workers=2) as pool:
                    results = list(pool.map(lambda _: reserve(), range(2)))
            self.assertCountEqual(results, ['running', 'blocked'])
            self.assertEqual(len(store.candidate('exp-A')['reasoning']['sandbox_attempts']), 1)

    def test_failed_attempts_budget_and_d_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            store = GovernanceStore(Path(directory) / 'test.db')
            with store.connection() as connection:
                connection.execute("INSERT INTO experiments VALUES ('exp', 'baseline', 'completed', '{}', 'now')")
            store.save_candidate('exp', 'A', {}, {})
            store.save_candidate('exp', 'D', {}, {'candidate_label': 'D'})
            with patch.object(store, 'require_current_baseline', return_value={}):
                with self.assertRaisesRegex(ValueError, 'Gate 2'):
                    store.reserve_candidate_evaluation('exp-D')
                for _ in range(11):
                    store.reserve_candidate_evaluation('exp-A')
                    store.finish_candidate('exp-A', 'failed', {'error': 'offline fixture'})
                with self.assertRaisesRegex(ValueError, 'budget exhausted'):
                    store.reserve_candidate_evaluation('exp-A')
                with store.connection() as connection:
                    connection.execute("UPDATE experiments SET result_json='{\"report_confirmation\": {\"winner_id\": \"exp-A\"}}' WHERE id='exp'")
                store.reserve_candidate_evaluation('exp-D')
                store.finish_candidate('exp-D', 'failed', {'error': 'offline fixture'})
                with self.assertRaisesRegex(ValueError, 'budget exhausted'):
                    store.reserve_candidate_evaluation('exp-D')
            self.assertEqual(len(store.candidate('exp-A')['reasoning']['sandbox_attempts']), 11)
            self.assertEqual(len(store.candidate('exp-D')['reasoning']['sandbox_attempts']), 1)

    def test_previous_experiment_same_baseline_cannot_reserve(self):
        with tempfile.TemporaryDirectory() as directory:
            store = GovernanceStore(Path(directory) / 'test.db')
            with store.connection() as connection:
                connection.execute("INSERT INTO experiments VALUES ('exp', 'baseline', 'completed', '{}', 'now')")
            store.save_candidate('exp', 'A', {}, {})
            with patch.object(store, 'require_current_baseline', return_value={}), patch.object(store, 'current_baseline_identity', return_value={'current_experiment_id': 'new-exp'}):
                with self.assertRaisesRegex(ValueError, 'Optimization Run'):
                    store.reserve_candidate_evaluation('exp-A')
            self.assertEqual(store.candidate('exp-A')['status'], 'generated')
            self.assertNotIn('sandbox_attempts', store.candidate('exp-A')['reasoning'])
