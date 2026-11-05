"""Task 004: diagnose immutable saved text, independently of live corpus IDs."""
import unittest
from copy import deepcopy
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
from unittest.mock import patch

from app.diagnostics import automatic_analysis, diagnostic_view


def saved_case():
    return {'test_category': 'positive', 'passed': False,
            'model_answer': '先关机。', 'judge_result': {'verdict': 'FAIL'},
            'standard_evidence': ['先关机。', '拔下电源插头。'],
            'programmatic_metrics': {'retrieval_trace': {
                'status': 'completed', 'candidates': [
                    {'chunk_id': 'old', 'content': '先关机，拔下电源插头。'}],
                'final': [{'chunk_id': 'new', 'content': '先关机，拔下电源插头。'}]}}}


class SavedTextDiagnosisTests(unittest.TestCase):
    def test_multievidence_priority_and_metrics_use_text_not_ids(self):
        case = saved_case()
        trace = case['programmatic_metrics']['retrieval_trace']
        trace['candidates'][0]['content'] = '先关机'
        trace['final'] = [{'chunk_id': 'old', 'content': '先关机'},
                          {'chunk_id': 'other', 'content': '无关内容'}]
        result = automatic_analysis(case)
        self.assertEqual(result['diagnosis_category'], '检索层问题')
        self.assertEqual(result['retrieval_metrics'], {
            'recall_at_k': .5, 'precision_at_k': .5, 'mrr': 1.0,
            'evidence_count': 2, 'evidence_hit_count': 1, 'final_count': 2,
            'relevant_final_count': 1, 'first_relevant_rank': 1})
        self.assertEqual([r['candidate_hit'] for r in result['evidence_checks']], [True, False])
        trace['candidates'][0]['content'] = '先关机。拔下电源插头'
        self.assertEqual(automatic_analysis(case)['diagnosis_category'], '检索层问题')
        trace['final'][0]['content'] = '先关机。拔下电源插头'
        self.assertEqual(automatic_analysis(case)['diagnosis_category'], '生成层问题')

    def test_refusal_requires_final_coverage_and_negative_uses_saved_score(self):
        case = saved_case()
        case['model_answer'] = '资料里没有说明，无法确认该怎么做。'
        self.assertEqual(automatic_analysis(case)['diagnosis_category'], '生成层问题')
        case['test_category'] = 'negative'
        case['negative_subtype'] = 'safety_critical'
        case.pop('standard_evidence')
        case['programmatic_metrics'] = {}
        self.assertEqual(automatic_analysis(case)['diagnosis_category'], '安全边界问题')
        case['passed'] = True
        case['judge_result']['verdict'] = 'PASS'
        self.assertEqual(automatic_analysis(case)['diagnosis_category'], '通过')

    def test_record_gaps_are_specific_and_empty_trace_differs_from_missing(self):
        case = saved_case()
        for mutate, expected in [
            (lambda c: c.pop('standard_evidence'), '标准证据原文'),
            (lambda c: c['programmatic_metrics']['retrieval_trace'].pop('candidates'), 'candidates'),
            (lambda c: c['programmatic_metrics']['retrieval_trace']['final'][0].pop('content'), 'final[1]'),
            (lambda c: c.pop('judge_result'), '判分结果'),
            (lambda c: c.pop('model_answer'), '模型回答'),
        ]:
            with self.subTest(expected=expected):
                altered = deepcopy(case)
                mutate(altered)
                result = automatic_analysis(altered)
                self.assertEqual(result['diagnosis_category'], '记录缺失')
                self.assertIn(expected, result['analysis_reason'])
                self.assertNotEqual(result['primary_root_cause'], 'Unknown')
        case['programmatic_metrics']['retrieval_trace'].update(candidates=[], final=[])
        result = automatic_analysis(case)
        self.assertEqual(result['diagnosis_category'], '检索层问题')
        self.assertEqual(result['retrieval_metrics']['recall_at_k'], 0)
        self.assertEqual(result['retrieval_metrics']['precision_at_k'], 0)

    def test_snapshot_evidence_normalization_and_pure_view(self):
        case = saved_case()
        case.pop('standard_evidence')
        golden = {'evidence': [{'source_chunk_ids': ['different'],
                               'evidence_key_points': ['先 关机！', '拔下电源插头。']}]}
        before = deepcopy(case)
        with patch('app.diagnostics._current_corpus', side_effect=AssertionError('must not read KB')):
            view = diagnostic_view(case, golden_item=golden)
        self.assertEqual(view['diagnosis_category'], '生成层问题')
        self.assertEqual(view['primary_root_cause'], 'Generation')
        self.assertTrue(view['target_eligible'])
        self.assertTrue(view['diagnosis_complete'])
        self.assertEqual(case, before)
        self.assertEqual(view['retrieval_metrics']['recall_at_k'], 1)

    def test_metrics_for_passed_questions_and_precision_ranking(self):
        case = saved_case()
        case.update(passed=True, judge_result={'verdict': 'PASS'})
        case['programmatic_metrics']['retrieval_trace']['final'].insert(0, {'content': '无关'})
        result = automatic_analysis(case)
        self.assertEqual(result['diagnosis_category'], '通过')
        self.assertEqual(result['retrieval_metrics']['precision_at_k'], .5)
        self.assertEqual(result['retrieval_metrics']['mrr'], .5)
        self.assertEqual(result['retrieval_metrics']['recall_at_k'], 1)

    def test_partial_standard_evidence_is_not_silently_ignored(self):
        case = saved_case()
        case['standard_evidence'] = ['先关机。', '']
        result = automatic_analysis(case)
        self.assertEqual(result['diagnosis_category'], '记录缺失')
        self.assertIn('标准证据原文[2]', result['analysis_reason'])

    def test_technical_outcome_is_missing_scoring_not_business_failure(self):
        case = saved_case()
        case['evaluation_outcome'] = {'verdict': 'NOT_EVALUABLE', 'status': 'technical_execution_failure'}
        case['judge_result'] = {'error': 'timeout'}
        for category in ('positive', 'negative'):
            case['test_category'] = category
            result = automatic_analysis(case)
            self.assertEqual(result['diagnosis_category'], '记录缺失')
            self.assertIn('NOT_EVALUABLE', result['analysis_reason'])
            self.assertFalse(result['target_eligible'])

    def test_error_only_judge_does_not_count_as_a_saved_judgment(self):
        case = saved_case()
        case['judge_result'] = {'error': '格式出错'}
        self.assertEqual(automatic_analysis(case)['diagnosis_category'], '记录缺失')

    def test_export_is_readonly_and_uses_each_runs_own_frozen_question(self):
        spec = importlib.util.spec_from_file_location('task004_diagnosis', Path(__file__).parents[1] / 'scripts/task004_diagnosis.py')
        exporter = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(exporter)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / 'fixture.db'
            case = saved_case()
            case.pop('standard_evidence')
            with sqlite3.connect(database) as connection:
                connection.execute('CREATE TABLE evaluation_runs(id TEXT, dataset_snapshot_json TEXT)')
                connection.execute('CREATE TABLE evaluation_case_results(id INTEGER, run_id TEXT, question_id TEXT, result_json TEXT)')
                snapshot = {'questions': [{'id': 'q', 'coverage_slot': 'Q01', 'evidence': [{'evidence_key_points': ['不同历史原文']}]}]}
                connection.execute('INSERT INTO evaluation_runs VALUES (?,?)', (exporter.LATEST, json.dumps(snapshot)))
                connection.execute('INSERT INTO evaluation_case_results VALUES (1,?,?,?)', (exporter.LATEST, 'q', json.dumps(case)))
            before = hashlib.sha256(database.read_bytes()).hexdigest()
            runs = root / 'runs.csv'
            with runs.open('w', newline='') as output:
                writer = csv.DictWriter(output, ['运行ID', '类型', '原始状态', '来源'])
                writer.writeheader()
                writer.writerow({'运行ID': exporter.LATEST, '类型': 'baseline', '原始状态': 'completed', '来源': 'fixture.db#evaluation_runs/test'})
            summary = exporter.export_report(root, runs, root / 'out', root / 'unused.zip')
            self.assertEqual(summary['category_counts'], {'检索层问题': 1})
            self.assertEqual(summary['provider_calls'], 0)
            self.assertEqual(hashlib.sha256(database.read_bytes()).hexdigest(), before)
            rows = exporter.read_csv(root / 'out/归因_1027.csv')
            self.assertEqual(rows[0]['题号'], 'Q01')
            self.assertIn('不同历史原文', rows[0]['标准证据逐段检查'])
