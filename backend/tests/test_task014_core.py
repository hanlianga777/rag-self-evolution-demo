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
