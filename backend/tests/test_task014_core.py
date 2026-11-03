import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.policy import DEFAULT_PIPELINE_CONFIG, search_space_contract, validate_candidate_config
from app.context_budget import budget_context
from app.evaluation import candidate_comparison
from app.agent_inputs import prepare_baseline_rows, is_optimization_target
from app.diagnostics import diagnostic_view


class Task014CoreTests(unittest.TestCase):
    def test_twelve_real_parameters(self):
        contract = search_space_contract()
        self.assertEqual(len(contract), 12)
        self.assertFalse(set(contract) & {'query_decompose', 'alias_mapping', 'metadata_filter'})
        self.assertEqual(contract['retrieval_max_tokens']['allowed'], [False, 8192, 4096])
        self.assertIn(0.4, contract['min_score']['allowed'])
        for effort in ('off', 'low', 'high', 'max'):
            self.assertTrue(validate_candidate_config({**DEFAULT_PIPELINE_CONFIG, 'generation_thinking': effort})['valid'])

    def test_missing_tokenizer_uses_estimate_and_limits_whole_sources(self):
        entries = [{'chunk_id': str(i), 'content': '中文证据' * 500} for i in range(3)]
        with patch('app.context_budget._tokenizer', side_effect=ValueError('missing')):
            selected, trace = budget_context(entries, 4096)
        self.assertLess(len(selected), len(entries))
        self.assertLessEqual(trace['tokens_after'], 4096)
        self.assertIn('估算', trace['count_method'])
        self.assertEqual(len(budget_context(entries, False)[0]), 3)

    def test_single_pass_failures_always_count(self):
        baseline = {'q': {'passed': True, 'test_category': 'positive'}}
        candidate = {'q': {'passed': False, 'regression_review': {'status': 'fluctuation'}}}
        result = candidate_comparison(baseline, candidate, [])
        self.assertEqual(result['new_regressions'], 1)
        self.assertEqual(result['bad_case_count'], 1)
        self.assertNotIn('复核', result['regression_interpretation'])

    def test_saved_old_review_does_not_filter_current_diagnosis(self):
        case = {'question_id': 'Q01', 'passed': False, 'test_category': 'negative', 'negative_subtype': 'clarify',
                'model_answer': '答复', 'judge_result': {'verdict': 'FAIL'}}
        baseline = {'dataset_snapshot_json': json.dumps({'questions': []}), 'config': {}, 'result': {
            'bad_case_count': 1, 'baseline_review': {'cases': {'Q01': {'regression_review': {'status': 'fluctuation', 'failed_votes': 1, 'total_votes': 3}}}}}}
        row = prepare_baseline_rows(baseline, [{'question_id': 'Q01', 'result': case}])[0]
        self.assertTrue(is_optimization_target(row))
        self.assertEqual(row['diagnostic_view']['diagnosis_category'], '生成层问题')
        self.assertEqual(row['diagnostic_view']['subfeature'], '召回成功但答案漏要点')
        self.assertNotIn('随机波动', json.dumps(row, ensure_ascii=False))

    def test_failed_latency_gate_is_in_shared_priorities(self):
        from app.optimization import optimization_priorities
        gates = [{'metric': 'latency_p50_seconds', 'actual': 30, 'threshold': 25,
                  'operator': '<=', 'passed': False}]
        rows = optimization_priorities([], gates)
        self.assertEqual(rows[0]['label'], '性能问题')
        self.assertEqual(rows[0]['priority'], 1)
        self.assertEqual(rows[0]['count'], 0)  # No fabricated question failures.

    def test_online_config_has_business_name_without_changing_identifier(self):
        from app.governance import GovernanceStore
        with tempfile.TemporaryDirectory() as directory:
            store = GovernanceStore(Path(directory) / 'fixture.db')
            production = store.active_production()
            self.assertEqual(production['display_name'], '当前线上配置')
            self.assertEqual(production['id'], 'baseline-v1')

    def test_normal_failed_questions_are_never_automatically_reviewed(self):
        from test_baseline_resume import ResumeTests
        fixture = ResumeTests()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        fixture.runtime.fail = None
        baseline = fixture.runner.execute_baseline(*fixture.runner.start_baseline())
        self.assertEqual(fixture.runtime.answers, ['Q1', 'Q2', 'Q3', 'Q4'])
        experiment = fixture.store.create_experiment(baseline['id'], 'completed')
        fixture.store.save_candidate(experiment, 'R1-A', {**DEFAULT_PIPELINE_CONFIG, 'generation_thinking': 'low'},
                                     {'candidate_label': 'A', 'observed_evidence': ['Q1']})
        fixture.runtime.answers.clear(); fixture.runtime.judges.clear()
        judge = fixture.runtime.judge
        def fail_judge(*args, **kwargs):
            return {**judge(*args, **kwargs), 'correctness': 0, 'faithfulness': 0,
                    'completeness': 0, 'behavior_pass': False}
        with patch.object(fixture.runtime, 'judge', side_effect=fail_judge), patch.object(
                fixture.runner, 'review_regression', side_effect=AssertionError('review is forbidden')):
            candidate = fixture.runner.execute_candidate(*fixture.runner.start_candidate(experiment + '-R1-A'))
        self.assertEqual(fixture.runtime.answers, ['Q1', 'Q2', 'Q3', 'Q4'])
        self.assertEqual(fixture.runtime.judges, ['Q1', 'Q2', 'Q3', 'Q4'])
        self.assertEqual(candidate['result']['bad_case_count'], 4)

    def test_generation_uses_selected_thinking_and_lowest_temperature(self):
        from types import SimpleNamespace
        from app.ai_service import AiService
        from app.providers import thinking_config
        calls = []
        class Stub:
            settings = SimpleNamespace(configured=True, model='fixture')
            def complete_with_metrics(self, *args, **kwargs):
                calls.append((thinking_config(), kwargs['temperature']))
                return {'content': '回答', 'ttft_ms': 1, 'input_tokens': 1, 'output_tokens': 1}
        service = AiService(object(), object(), Stub(), False)
        service.retriever = SimpleNamespace(retrieve=lambda *a, **k: [{'chunk_id': 'c', 'content': '来源'}])
        for effort in ('off', 'low', 'high', 'max'):
            service.answer('问题', {'run_target': 'sandbox_candidate', 'generation_thinking': effort})
        self.assertEqual([c[0].get('reasoning_effort', 'off') for c in calls], ['off', 'low', 'high', 'max'])
        self.assertEqual([c[1] for c in calls], [0, 0, 0, 0])
