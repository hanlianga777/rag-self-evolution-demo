"""Saved objective facts, frozen diagnosis reuse, and ready-state planning."""
from copy import deepcopy
import json
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from app.optimization import build_agent_prompt
from app.policy import DEFAULT_PIPELINE_CONFIG
from test_task004_agent import failed_case


def fixture():
    case = failed_case()
    case['judge_result']['checks'] = [
        {'requirement': '操作前关闭设备', 'met': False},
        {'requirement': '可选补充', 'met': False, 'check_type': 'auxiliary'},
        {'requirement': '已完成要求', 'met': True}]
    entries = [{'chunk_id': 'other', 'content': '无关'},
               {'chunk_id': 'norm', 'content': '操作前关闭设备。'}]
    case['programmatic_metrics']['retrieval_trace'].update(
        candidates=entries, reranked=entries[::-1], final=entries[:1])
    question = {'id': 'Q1', 'display_id': 'Q01', 'test_category': 'positive',
                'evidence': [{'source_chunk_ids': ['norm', 'absent'],
                              'evidence_key_points': ['操作前关闭设备。']} ]}
    review = {'regression_review': {'status': 'confirmed_regression',
              'failed_votes': 3, 'total_votes': 3},
              'analysis': {'reason': '人工分析秘密', 'suggested_parameters': {'top_k': 6}}}
    baseline = {'id': 'base', 'config': {'candidate_k': 12, 'top_k': 4},
                'dataset_snapshot_json': json.dumps({'questions': [question]}),
                'result': {'baseline_review': {'cases': {'Q1': review}}}}
    row = {'id': 'bad', 'question_id': 'Q1', 'run_id': 'base', 'result': case}
    return baseline, row


class Task008bInputTests(unittest.TestCase):
    def prepare(self, baseline=None, row=None):
        from app.agent_inputs import prepare_baseline_rows
        if baseline is None:
            baseline, row = fixture()
        return prepare_baseline_rows(baseline, [row])[0]

    def test_positions_entered_absent_missing_and_parent_children(self):
        baseline, row = fixture()
        before = deepcopy((baseline, row))
        facts = self.prepare(baseline, row)['retrieval_facts']
        self.assertEqual(facts['standard_evidence_positions'], [
            {'chunk_id': 'norm', 'candidates': 2, 'reranked': 1, 'final': '未进入'},
            {'chunk_id': 'absent', 'candidates': '未进入', 'reranked': '未进入', 'final': '未进入'}])
        self.assertEqual((facts['candidate_k'], facts['top_k']), (12, 4))
        self.assertEqual(facts['unmet_required_points'], ['操作前关闭设备'])
        self.assertEqual(facts['baseline_review'], {'conclusion': '单遍判错'})
        self.assertEqual((baseline, row), before)
        trace = row['result']['programmatic_metrics']['retrieval_trace']
        trace.pop('reranked')
        trace['final'] = [{'chunk_id': 'parent', 'matched_child_ids': ['norm']}]
        positions = self.prepare(baseline, row)['retrieval_facts']['standard_evidence_positions']
        self.assertEqual(positions[0]['reranked'], '记录缺失')
        self.assertEqual(positions[0]['final'], 1)
        trace['final'] = [{}]
        self.assertEqual(self.prepare(baseline, row)['retrieval_facts']['standard_evidence_positions'][0]['final'], '记录缺失')

    def test_prompt_has_facts_but_no_manual_review_analysis(self):
        row = self.prepare()
        _, prompt = build_agent_prompt([row], DEFAULT_PIPELINE_CONFIG, [], [], list('ABC'))
        self.assertEqual(prompt['bad_cases'][0]['retrieval_facts'], row['retrieval_facts'])
        serialized = json.dumps(prompt, ensure_ascii=False)
        for forbidden in ('人工分析秘密', 'suggested_parameters'):
            self.assertNotIn(forbidden, serialized)

    def test_generate_uses_prepared_facts_in_actual_provider_request(self):
        from app.governance import GovernanceStore
        from app.optimization import OptimizationAgent
        from identity_fixture import completed_baseline
        from test_optimization_contract import FixedProvider, drafts
        with tempfile.TemporaryDirectory() as directory:
            store = GovernanceStore(Path(directory) / 'fixture.db')
            completed_baseline(store, run_id='base')
            baseline, row = fixture()
            with store.connection() as connection:
                connection.execute('UPDATE evaluation_runs SET dataset_snapshot_json=?,result_json=? WHERE id=?',
                                   (baseline['dataset_snapshot_json'], json.dumps(baseline['result']), 'base'))
            store.record_bad_case('base', 'Q1', 'Retrieval', 'ordinary', row['result'])
            provider = FixedProvider(json.dumps(drafts()))
            with patch.object(store, 'require_current_baseline'):
                OptimizationAgent(store, provider).generate('base')
            sent = provider.prompt['bad_cases'][0]['retrieval_facts']
            self.assertEqual(sent['standard_evidence_positions'][0]['candidates'], 2)
            self.assertEqual(sent['baseline_review']['conclusion'], '单遍判错')
            self.assertNotIn('人工分析秘密', json.dumps(provider.prompt, ensure_ascii=False))

    def test_preview_is_readonly_and_rebuilds_the_same_full_prompt(self):
        import sqlite3
        path = Path(__file__).parents[1] / 'scripts/preview_agent_input.py'
        spec = importlib.util.spec_from_file_location('preview', path)
        preview = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(preview)
        baseline, row = fixture()
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / 'fixture.db'
            with sqlite3.connect(database) as connection:
                connection.execute('CREATE TABLE evaluation_runs(id, dataset_version_id, config_json, result_json, dataset_snapshot_json)')
                connection.execute('INSERT INTO evaluation_runs VALUES (?,?,?,?,?)', ('base', 'golden', json.dumps(baseline['config']), json.dumps(baseline['result']), baseline['dataset_snapshot_json']))
                connection.execute('CREATE TABLE bad_cases(id, run_id, question_id, result_json, created_at)')
                connection.execute('INSERT INTO bad_cases VALUES (?,?,?,?,?)', ('bad', 'base', 'Q1', json.dumps(row['result']), 'now'))
            before = hashlib.sha256(database.read_bytes()).hexdigest()
            value = preview.preview(database, 'base')
            self.assertEqual(value['provider_calls'], 0)
            self.assertEqual(value['golden_id'], 'golden')
            self.assertEqual(value['prompt']['bad_cases'][0]['retrieval_facts'], self.prepare()['retrieval_facts'])
            self.assertEqual(hashlib.sha256(database.read_bytes()).hexdigest(), before)

    def test_missing_records_and_incomplete_review_are_not_guessed(self):
        baseline, row = fixture()
        baseline['dataset_snapshot_json'] = '{}'
        baseline['config'] = {}
        baseline['result'] = {}
        row['result']['judge_result'].pop('checks')
        facts = self.prepare(baseline, row)['retrieval_facts']
        self.assertEqual(facts['standard_evidence_positions'], '记录缺失')
        self.assertEqual(facts['candidate_k'], '记录缺失')
        self.assertEqual(facts['unmet_required_points'], '记录缺失：未保存完整的要点判分记录')
        self.assertEqual(facts['baseline_review'], {'conclusion': '单遍判错'})
        baseline, row = fixture()
        review = baseline['result']['baseline_review']['cases']['Q1']['regression_review']
        review.update(status='fluctuation', failed_votes=1)
        self.assertEqual(self.prepare(baseline, row)['retrieval_facts']['baseline_review']['conclusion'], '单遍判错')
        review['status'] = 'running'
        self.assertEqual(self.prepare(baseline, row)['retrieval_facts']['baseline_review']['conclusion'], '单遍判错')

    def test_ready_and_exploratory_plan_but_missing_records_block(self):
        from app.agent_coverage import plan_coverage
        row = self.prepare()
        self.assertEqual(row['diagnostic_view']['experiment_plan']['status'], 'ready')
        for status in ('ready', 'exploratory'):
            row['diagnostic_view']['experiment_plan']['status'] = status
            plan = plan_coverage([row], DEFAULT_PIPELINE_CONFIG, [])
            self.assertEqual(plan['planned_count'], 1)
            self.assertEqual(plan['covered_count'], 0)
            proposal = plan['proposals'][0]
            candidate = {'id': 'saved-A', 'config': {**DEFAULT_PIPELINE_CONFIG, **proposal['config_diff']},
                         'reasoning': {**proposal, 'candidate_label': 'A', 'round': 1,
                             'observed_evidence': ['Q1'], 'proposal': proposal['why'],
                             'changed_parameters': proposal['config_diff']}}
            self.assertEqual(plan_coverage([row], DEFAULT_PIPELINE_CONFIG, [candidate])['covered_count'], 1)
        row['result']['programmatic_metrics']['retrieval_trace'].pop('candidates')
        # A stale ready flag must not bypass actual saved-record validation.
        self.assertEqual(plan_coverage([row], DEFAULT_PIPELINE_CONFIG, [])['planned_count'], 0)

    def test_coverage_and_list_reuse_same_frozen_diagnosis(self):
        from app.agent_coverage import coverage_inputs
        from api_fixture import main
        baseline, row = fixture()
        row['result']['standard_evidence'] = ['过时的标准文字']
        store = Mock()
        store.evaluation_run.return_value = baseline
        store.bad_case_rows.return_value = [row]
        store.experiment.return_value = {'baseline_run_id': 'base', 'candidates': []}
        _, _, rows, _, _ = coverage_inputs(store, 'exp')
        self.assertEqual(rows[0]['diagnostic_view']['diagnosis_category'], '检索层问题')
        with patch.object(main, 'store', store):
            direct = main.case_list_row(row)['result']['diagnostic_view']
            with patch('app.agent_inputs.diagnostic_view', side_effect=AssertionError('reuse')):
                reused = main.case_list_row(rows[0])['result']['diagnostic_view']
        self.assertEqual(direct, rows[0]['diagnostic_view'])
        self.assertEqual(direct, reused)
