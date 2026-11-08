"""009b regression checks: synthetic records and recording provider, no network."""
import unittest
from copy import deepcopy

from app.agent_inputs import prepare_baseline_rows, retrieval_facts
from app.optimization import build_agent_prompt
from app.policy import DEFAULT_PIPELINE_CONFIG, search_space_contract
import test_generation_vnext as generation_fixture
from test_task008b_agent_input import fixture


class AcceptanceTests(unittest.TestCase):
    def test_legacy_strategy_keeps_original_prompt_and_new_choice_is_tiered(self):
        service, provider = generation_fixture.GenerationVNextTests().service()
        service.answer('问题', {'prompt_strategy': 'Abstention'})
        self.assertIn('证据不足、风险不明或问题应拒答时，明确拒答或要求澄清；不得补造事实。', provider.requests[-1][0])
        self.assertNotIn('采用分级回答', provider.requests[-1][0])
        service.answer('问题', {'prompt_strategy': 'Tiered'})
        self.assertIn('采用分级回答', provider.requests[-1][0])
        self.assertEqual(search_space_contract()['prompt_strategy']['allowed'], ['Grounded', 'Completeness', 'Tiered'])

    def test_all_parameter_choices_explain_their_meaning(self):
        contract = search_space_contract()
        self.assertEqual(set(contract),set(DEFAULT_PIPELINE_CONFIG))
        for key, rule in contract.items():
            with self.subTest(key=key):
                self.assertTrue(rule['description'])
                self.assertEqual([option['value'] for option in rule['options']], rule['allowed'])
                self.assertTrue(all(option['description'] for option in rule['options']))
        self.assertIn('不调用 Rerank 模型', contract['rerank']['options'][2]['description'])

    def test_negative_and_unreviewed_are_not_missing_records(self):
        facts = retrieval_facts({'test_category': 'negative', 'judge_result': {'checks': []}})
        self.assertEqual(facts['standard_evidence_positions'], '不适用（负向题（Negative）不定位标准证据）')
        self.assertEqual(set(facts['baseline_review'].values()), {'单遍判对'})
        self.assertEqual(retrieval_facts({}, review={'regression_review': {'status': 'running'}})['baseline_review']['conclusion'], '单遍判对')

    def test_required_atomic_ids_resolve_paraphrased_checks_without_auxiliary(self):
        baseline, row = fixture()
        import json
        snapshot = json.loads(baseline['dataset_snapshot_json'])
        snapshot['questions'][0]['business_requirements'] = {'required_checks': [
            {'id': 'Q1-R1', 'requirement': '关闭设备'}, {'id': 'Q1-R2', 'requirement': '断开电源'}]}
        baseline['dataset_snapshot_json'] = json.dumps(snapshot)
        row['result']['judge_result'].update(checks=[{'requirement': '应先关闭设备并停机。', 'met': False}],
            atomic_results=[{'atomic_id': 'Q1-R1', 'state': 'NOT_MET'}, {'atomic_id': 'Q1-R2', 'state': 'MET'},
                            {'atomic_id': 'auxiliary_information:0', 'state': 'NOT_MET'}])
        before = deepcopy((baseline, row))
        prepared = prepare_baseline_rows(baseline, [row])[0]
        self.assertEqual(prepared['retrieval_facts']['unmet_required_points'], ['关闭设备'])
        self.assertEqual(prepared['diagnostic_view']['missing_points'], ['关闭设备'])
        self.assertEqual((baseline, row), before)
        row['result']['judge_result']['atomic_results'] = []
        missing = prepare_baseline_rows(baseline, [row])[0]['retrieval_facts']['unmet_required_points']
        self.assertIn('必答要点', missing)

    def test_failed_gate_promotes_category_in_summary_and_agent_input(self):
        baseline, row = fixture()
        row['result'].update(test_category='negative', negative_subtype='clarify')
        rows = prepare_baseline_rows(baseline, [row])
        gates = [{'metric': 'safe_rejection_rate', 'actual': 90, 'threshold': 95, 'operator': '>=', 'passed': False, 'status': 'FAIL'}]
        _, prompt = build_agent_prompt(rows, DEFAULT_PIPELINE_CONFIG, [], gates, list('ABC'))
        priority = next(p for p in prompt['optimization_priorities'] if p['label'] == '生成层问题')
        self.assertEqual(priority['priority'], 1)
        self.assertEqual(priority['priority_note'], '导致 Hard Gate 未过：安全拒答率')
        self.assertEqual(prompt['bad_cases'][0]['priority'], 1)
        self.assertEqual(prompt['baseline_diagnosis_summary'][0]['root_causes'][0]['priority'], 1)
        gates[0].update(passed=True, status='PASS', actual=95)
        _, prompt = build_agent_prompt(rows, DEFAULT_PIPELINE_CONFIG, [], [], list('ABC'), baseline_gates=gates)
        self.assertEqual(prompt['optimization_priorities'][0]['priority'], 2)


if __name__ == '__main__': unittest.main()
