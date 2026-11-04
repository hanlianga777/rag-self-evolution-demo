"""Scoring-only migration must retain execution identity and reject stale QC."""
import json
import unittest
from copy import deepcopy
from unittest.mock import patch

from app.diagnostic_evidence import digest
from app.scoring_revision import revision_changes, historical_replay_candidates
import test_judge_replay_v5 as replay


class ScoringRevisionTests(unittest.TestCase):
    def test_invalid_citation_feedback_identifies_bad_source_and_actual_final(self):
        from app.evaluation_contract import validate_business_judgment
        value = {'verdict': 'PASS', 'reason': 'fixture', 'issues': [], 'checks': [{
            'check_type': 'fact', 'requirement': 'saved fact', 'met': True, 'answer_quotes': ['saved'],
            'support': [{'source_id': 'golden-only', 'quote': 'real source text'}]}]}
        original = deepcopy(value)
        with self.assertRaises(ValueError) as failure:
            validate_business_judgment(value, 'saved', [{'chunk_id': 'actual-final', 'content': 'real source text'}],
                category='positive')
        self.assertIn('golden-only', str(failure.exception))
        self.assertIn('actual-final', str(failure.exception))
        self.assertEqual(value, original)

    def example(self):
        source, cases, old, config, judge, chunks = replay.JudgeReplayTests().example()
        old['questions'][0]['business_requirements'] = {'required_checks': [
            {'id': 'R1', 'requirement': 'old', 'source_chunk_ids': ['child-new']}], 'auxiliary_information': [],
            'conditional_checks': [], 'acceptable_equivalents': [], 'prohibited': ['danger'],
            'sources': [{'chunk_id': 'child-new', 'quote': '切断电池。'}]}
        source['dataset_snapshot_json'] = json.dumps(old)
        new = deepcopy(old)
        new['id'] = 'revised'
        new['questions'][0]['business_requirements']['required_checks'][0]['requirement'] = 'new'
        from app.scoring_contract import snapshot_manifest
        new['scoring_contract_manifest'] = snapshot_manifest(new)
        new['scoring_revision'] = {'parent_id': old['id'], 'parent_sha256': digest(old),
            'actor': 'task017a', 'reason': 'authorized', 'draft_sha256': 'csv',
            'changed_question_ids': ['q-new'], 'qc': {'q-new': {
                'question_sha256': digest(new['questions'][0]), 'result': {'score': 95, 'priority': 'P2',
                    'content_validation': {'status': 'supported'}}}}}
        return source, cases, old, new, config, judge, chunks

    def test_only_scoring_changes_with_bound_qc_are_accepted(self):
        source, cases, old, new, config, judge, chunks = self.example()
        self.assertEqual(revision_changes(old, new), ['q-new'])
        with patch('app.scoring_contract.validate_snapshot_manifest'):
            result = replay.replay_eligibility(source, cases, new, config, judge, chunks, 'fp')
        self.assertTrue(result['can_replay'], result)
        self.assertEqual(result['generation_calls'], 0)
        for mutate in (lambda n: n['questions'][0].update(question='changed'),
                       lambda n: n['questions'][0]['business_requirements'].update(prohibited=[]),
                       lambda n: n['questions'][0]['business_requirements'].update(required_checks=['tampered']),
                       lambda n: n['scoring_revision'].update(changed_question_ids=[]),
                       lambda n: n['scoring_revision']['qc']['q-new']['result'].update(priority='P0'),
                       lambda n: n.update(corpus_fingerprint='other')):
            bad = deepcopy(new); mutate(bad)
            with self.assertRaises(ValueError): revision_changes(old, bad)

    def test_archived_sandbox_metadata_is_not_reused_as_candidate_ownership(self):
        source, cases, old, new, config, judge, chunks = self.example()
        source['config'] = {**config, 'run_target': 'sandbox_candidate', 'candidate_id': 'old-A'}
        cases[0]['programmatic_metrics']['retrieval_trace']['config'] = deepcopy(source['config'])
        with patch('app.scoring_contract.validate_snapshot_manifest'):
            result = replay.replay_eligibility(source, cases, new, config, judge, chunks, 'fp')
        self.assertTrue(result['can_replay'], result)
        changed = {**config, 'top_k': 6}
        with patch('app.scoring_contract.validate_snapshot_manifest'):
            self.assertFalse(replay.replay_eligibility(source, cases, new, changed, judge, chunks, 'fp')['can_replay'])

    def test_unrelated_or_incomplete_historical_replay_is_rejected(self):
        from types import SimpleNamespace
        baseline = {'id': 'base', 'dataset_version_id': 'new', 'judge': {'evaluation_identity': 'same'}}
        run = {'id': 'replay', 'status': 'completed', 'dataset_version_id': 'old',
               'judge': baseline['judge'], 'result': {'evaluation_complete': True,
                   'judge_replay': {'source_run_id': 'original'}}}
        store = SimpleNamespace(evaluation_run=lambda _: run, candidate=lambda _: {
            'result': {'evaluation_run_id': 'original'}, 'config': {}, 'reasoning': {}})
        with self.assertRaises(ValueError):
            historical_replay_candidates(store, baseline, [{'candidate_id': 'A', 'replay_run_id': 'replay'}])

    def test_historical_facts_are_recomputed_from_new_verdicts_without_spending_budget(self):
        from types import SimpleNamespace
        from app.optimization import build_agent_prompt
        from app.policy import DEFAULT_PIPELINE_CONFIG
        frozen = {'questions': [{'id': 'Q1'}, {'id': 'Q2'}]}
        baseline = {'id': 'base', 'dataset_version_id': 'new', 'dataset_snapshot_json': json.dumps(frozen),
            'judge': {'evaluation_identity': 'same'}}
        config = {**DEFAULT_PIPELINE_CONFIG, 'generation_thinking': 'high', 'top_k': 6}
        gate = {'id': 'latency', 'metric': 'latency_p99_seconds', 'operator': '<=', 'actual': 70, 'passed': False}
        run = {'id': 'replay', 'status': 'completed', 'dataset_version_id': 'new', 'judge': baseline['judge'],
            'config': {**config, 'run_target': 'baseline'}, 'result': {'evaluation_complete': True,
                'gates': {'passed': False, 'gates': [gate]}, 'judge_replay': {'source_run_id': 'original'}}}
        original = {'config': {**config, 'candidate_id': 'A', 'run_target': 'sandbox_candidate'}}
        candidate = {'id': 'A', 'config': config, 'status': 'evaluated',
            'result': {'evaluation_run_id': 'original', 'all_fixed_question_ids': ['WRONG_OLD_FACT']},
            'reasoning': {'observed_evidence': ['Q1'], 'changed_parameters': {'generation_thinking': 'high', 'top_k': 6}}}
        cases = {'base': [{'question_id': 'Q1', 'passed': False}, {'question_id': 'Q2', 'passed': True}],
                 'replay': [{'question_id': 'Q1', 'passed': True}, {'question_id': 'Q2', 'passed': False}]}
        store = SimpleNamespace(candidate=lambda _: candidate, evaluation_run=lambda key: {'replay': run, 'original': original}[key],
            evaluation_case_results=lambda key: cases[key])
        rows = historical_replay_candidates(store, baseline, [{'candidate_id': 'A', 'replay_run_id': 'replay'}])
        self.assertEqual(rows[0]['result']['all_fixed_question_ids'], ['Q1'])
        self.assertEqual(rows[0]['result']['new_failure_question_ids'], ['Q2'])
        self.assertEqual(candidate['result']['all_fixed_question_ids'], ['WRONG_OLD_FACT'])
        _, prompt = build_agent_prompt([], DEFAULT_PIPELINE_CONFIG, rows, [], list('ABC'),
            baseline_gates=[{**gate, 'actual': 30, 'passed': True}])
        self.assertEqual(prompt['evaluation_budget']['used'], 0)
        self.assertEqual(prompt['gate_harming_changes'][0]['candidate_id'], 'A')
        self.assertIn('无法判断', prompt['prior_sandbox_results'][0]['attribution'])

    def test_freeze_is_append_only_idempotent_and_start_binds_new_snapshot(self):
        import tempfile
        from pathlib import Path
        from types import SimpleNamespace
        from unittest.mock import Mock
        from app.governance import GovernanceStore
        from app.evaluation import EvaluationRunner
        from app.scoring_revision import freeze_scoring_revision
        source, cases, old, new, config, judge, chunks = self.example()
        with tempfile.TemporaryDirectory() as temporary:
            store = GovernanceStore(Path(temporary) / 'isolated.db')
            original = json.dumps(old)
            with store.connection() as db:
                db.execute('INSERT INTO dataset_versions VALUES (?,?,?,?,?)',
                    (old['id'], 'approved', 'fixture', original, '2000'))
                original_count = db.execute('SELECT count(*) FROM dataset_versions').fetchone()[0]
            qc = new['scoring_revision']['qc']
            with patch('app.corpus.CorpusStore.chunks', return_value=chunks), patch(
                    'app.golden_v2.validate_qc_content', return_value={'status': 'supported'}):
                frozen = freeze_scoring_revision(store, old['id'], new['questions'], qc,
                    actor='task017a', reason='authorized', draft_sha256='csv')
                again = freeze_scoring_revision(store, old['id'], new['questions'], qc,
                    actor='task017a', reason='authorized', draft_sha256='csv')
            self.assertEqual(frozen['id'], again['id'])
            with store.connection() as db:
                self.assertEqual(db.execute('SELECT count(*) FROM dataset_versions').fetchone()[0], original_count + 1)
                self.assertEqual(db.execute('SELECT snapshot_json FROM dataset_versions WHERE id=?', (old['id'],)).fetchone()[0], original)
            source['config'] = {**config, 'run_target': 'sandbox_candidate', 'candidate_id': 'archived-A'}
            fake = SimpleNamespace(evaluation_run=lambda _: source, dataset_snapshots=lambda: [{'snapshot': frozen}],
                create_baseline_run=Mock(return_value='new-replay'))
            runner = EvaluationRunner(fake, SimpleNamespace())
            runner.judge_replay_preflight = Mock(return_value={'can_replay': True, 'new_judge': judge})
            runner.snapshot_items = Mock(return_value=['saved-item'])
            run_id, items, target_config = runner.start_judge_replay('old')
            self.assertEqual(run_id, 'new-replay')
            self.assertEqual(target_config, config)
            self.assertEqual(fake.create_baseline_run.call_args.args[0], frozen)
            self.assertEqual(items, ['saved-item'])

    def test_same_thinking_saved_answers_are_not_labeled_as_thinking_comparison(self):
        import tempfile
        from pathlib import Path
        from app.governance import GovernanceStore
        _, _, frozen, _, _, judge, _ = self.example()
        with tempfile.TemporaryDirectory() as temporary:
            store = GovernanceStore(Path(temporary) / 'isolated.db')
            with store.connection() as db:
                db.execute('INSERT INTO dataset_versions VALUES (?,?,?,?,?)',
                    (frozen['id'], 'approved', 'fixture', json.dumps(frozen), '9999'))
            runs = []
            for prompt in ('Grounded', 'Tiered'):
                run = store.create_evaluation_run(frozen, {'run_target': 'baseline',
                    'generation_thinking': 'max', 'prompt_strategy': prompt}, judge)
                store.record_evaluation_case(run, 'q-new', {'passed': True})
                store.finish_evaluation_run(run, 'completed', {'evaluation_complete': True, 'technical_failed': 0})
                runs.append(run)
            designation = store.designate_baseline(*runs, 'task017a', '同卷历史方案对照')
            self.assertIn('保存回答对照', designation['comparison_label'])
            self.assertNotIn('思考档位对照', designation['comparison_label'])


class PaidRecoveryTests(unittest.TestCase):
    def setUp(self):
        import test_optimization_contract as fixture
        fixture.OptimizationContractTests.setUp(self)

    def test_agent_and_cycle_restore_the_same_ledger_in_a_fresh_context(self):
        from pathlib import Path
        from types import SimpleNamespace
        import test_optimization_contract as fixture
        from app.paid_run import PaidRun, current_paid_run, controlled_run
        from app.optimization import OptimizationAgent
        from app.optimization_cycle import claim_cycle, run_until_qualified
        policy = {'kind': 'off_peak_usd_cap_v1', 'budget_usd': 5,
            'ledger_directory': self.directory.name, 'database_path': str(self.store.database_path)}
        paid = PaidRun(Path(self.directory.name) / 'cycle.ledger.json', identity='cycle',
            identity_check=lambda: 'cycle', request_policy=policy)
        with controlled_run(paid):
            generated = OptimizationAgent(self.store, fixture.FixedProvider(json.dumps(fixture.drafts()))).generate('EVAL-test')
            claim_cycle(self.store, generated['id'], current_round_only=True)
        self.assertEqual(self.store.experiment(generated['id'])['result']['paid_run']['ledger_identity'], 'cycle')
        self.assertIsNone(current_paid_run())
        def check_context(*_args, **_kwargs):
            self.assertEqual(current_paid_run().identity, 'cycle')
            self.assertEqual(current_paid_run().request_policy, policy)
            raise LookupError('context verified before any RPC')
        with patch('app.optimization_cycle.EvaluationRunner', side_effect=check_context), self.assertRaises(LookupError):
            run_until_qualified(self.store, SimpleNamespace(), generated['id'], claimed=True)
        with patch.object(self.store, 'claim_agent_generation', side_effect=check_context), self.assertRaises(LookupError):
            OptimizationAgent(self.store, fixture.FixedProvider('unused')).generate('EVAL-test', experiment_id=generated['id'])
        self.assertIsNone(current_paid_run())


if __name__ == '__main__': unittest.main()
