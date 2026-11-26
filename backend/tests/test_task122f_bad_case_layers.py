import json
from unittest.mock import Mock

import pytest

from app.agent_round_contract import target_layer
from app.optimization import OptimizationAgent
from app.policy import CANDIDATE_QUALIFICATION_VERSION, GATE_DEFINITIONS, evaluate_gates, qualify_candidate
from test_task118a_verdict import OfflineEvaluation, scored


VERSION = '122f'
P99 = 'latency_p99_seconds'


@pytest.mark.parametrize(('faults', 'gates', 'expected'), [
    (['recall', 'generation', 'generation', 'generation'], [], 'retrieval'),
    (['ranking', 'final', 'ranking', 'generation', 'generation', 'generation'], [], 'retrieval'),
    ([], ['performance'], 'performance'),
    (['recall', 'recall', 'safety'], ['safety'], 'safety'),
    (['generation', 'generation', 'over_refuse', 'over_refuse'], [], 'generation'),
])
def test_new_layer_decisions(faults, gates, expected):
    assert target_layer(faults, gates, False, decision_version=VERSION)['layer'] == expected


def gate_results(p99):
    return evaluate_gates({**{g['metric']: g['threshold'] for g in GATE_DEFINITIONS}, P99: p99})


def test_performance_repair_cannot_promote_a_regression():
    regression = dict(passed=True, comparison_complete=True, all_fixed_question_ids=[],
                      new_regression_question_ids=['Q01'], severe_risk_question_ids=[], safety_violation_question_ids=[])
    kwargs = dict(rule_version=CANDIDATE_QUALIFICATION_VERSION, performance_reference=gate_results(70),
                  performance_reference_id='baseline')
    assert not qualify_candidate(gate_results(35), regression, 0, 0, 1, **kwargs)['qualified']
    regression['new_regression_question_ids'] = []
    assert qualify_candidate(gate_results(35), regression, 0, 0, 0, **kwargs)['qualified']
    assert not qualify_candidate(gate_results(35), regression, 0, 0, 0,
                                 **{**kwargs, 'performance_reference': gate_results(50)})['qualified']
    assert not qualify_candidate(gate_results(40), regression, 0, 0, 0,
                                 rule_version=CANDIDATE_QUALIFICATION_VERSION)['qualified']
    incomplete = gate_results(35)
    incomplete['gates'].pop()
    assert not qualify_candidate(incomplete, regression, 0, 0, 0, **kwargs)['qualified']
    violation = {**regression, 'safety_violation_question_ids': ['Q01']}
    assert not qualify_candidate(gate_results(35), violation, 0, 0, 0, **kwargs)['qualified']


def test_fault_severity_comes_from_saved_evidence():
    from app.agent_mechanism import bad_case_fault

    def fault(case, code):
        return bad_case_fault({'diagnostic_view': {}, 'result': case}, {'code': code})

    assert fault({'judge_result': {'over_refusal': True}}, 'generation')['code'] == 'over_refuse'
    assert fault({'judge_result': {'over_refusal': True}}, 'recall')['severity'] == '致命'
    assert fault({'judge_result': {'samples': [{'safety_violation': True}]}}, 'generation')['code'] == 'safety_violation'
    assert fault({'test_category': 'negative', 'negative_subtype': 'clarify', 'model_answer': '抱歉，我无法回答。'},
                 'unknown')['severity'] == '轻微'
    assert fault({'test_category': 'negative', 'judge_result': {'behavior_reason': '未按指定格式回答'}},
                 'unknown')['code'] == 'safety'


def test_legacy_order_and_next_available_layer():
    from app.agent_round_contract import layer_plan

    faults = ['recall', 'generation', 'generation', 'generation', 'generation']
    assert target_layer(faults, [], False)['layer'] == 'generation'
    rows = {
        'fail': {'fault': {'code': 'recall'}, 'available': []},
        'miss': {'fault': {'code': 'generation'}, 'available': [{'changes': {'generation_thinking': 'low'}}]},
    }
    plan = layer_plan(rows, [], False, [], 'Baseline', ['A'], decision_version=VERSION)
    assert plan['layer'] == 'generation'
    assert [row['layer'] for row in plan['fallbacks']] == ['retrieval']


def test_performance_actions_require_real_reductions():
    from app import rules
    from app.agent_round_contract import round_opportunities

    config = {**rules.BASELINE, 'generation_thinking': 'high', 'candidate_k': 24, 'top_k': 6,
              'hyde': True, 'multi_query': 2, 'query_decompose': True, 'retrieval_max_tokens': 8192}
    rows = round_opportunities([], {'id': 'Baseline', 'changes': {}}, config, [], {}, [], [],
                               use_layered=True, performance_gates=[P99])
    single_changes = [row['changes'] for row in rows[P99]['available'] if len(row['changes']) == 1]
    assert {'generation_thinking': 'off'} in single_changes
    assert {'generation_thinking': 'low'} in single_changes
    assert {next(iter(change)) for change in single_changes} == set(rules.PERFORMANCE_PARAMETERS)
    assert {'multi_query': 4} not in single_changes
    assert {'retrieval_max_tokens': False} not in single_changes


@pytest.mark.parametrize('new_wrong_answer', [False, True])
def test_all_correct_slow_baseline_generates_and_qualifies_by_measured_results(tmp_path, monkeypatch, new_wrong_answer):
    first = {f'Q{i:02d}': scored(True, latency=70000 if i > 25 else 1000) for i in range(1, 51)}
    first['Q01'] = scored(True, category='ablation')
    first['Q02'] = scored(True, category='negative', subtype='safety_critical')
    first['Q03'] = scored(True, category='negative', subtype='prompt_injection')
    env = OfflineEvaluation(tmp_path, monkeypatch, first)
    env.stable_baseline()
    experiment = env.store.create_experiment(env.base)
    from test_task118a_verdict import mark_legacy_planning
    mark_legacy_planning(env.store, experiment)
    assert env.store.experiment(experiment)['result']['bad_case_decision_version'] == VERSION
    monkeypatch.setattr('app.optimization.wait_for_off_peak', Mock())
    provider = Mock(spec=['complete'])

    def propose(system, user, **kwargs):
        prompt = json.loads(user)
        assert prompt['round_target_layer']['layer'] == 'performance'
        assert prompt['goal']['candidate_labels'] == ['A']
        assert prompt['round_opportunities'][P99]['available']
        conclusion = {'id': 'C1', 'conclusion': 'P99 实测为 70 秒'}
        return json.dumps({
            'prior_round_review': {'summary': '无', 'plans': [], 'baseline_remaining_assessment': '全对',
                                   'conclusions': [conclusion]},
            'bad_case_summary': {'groups': prompt['bad_case_groups'], 'focus': 'P99', 'conclusions': [conclusion]},
            'hypothesis_plan': {'hypothesis': '减少模型读取的资料', 'test_candidate': 'A',
                                'if_true': {'action': 'stop'}, 'if_false': {'action': 'stop'}},
            'candidates': [{
                'id': 'A', 'direction': 'retrieval_max_tokens', 'config_diff': {'retrieval_max_tokens': 4096},
                'target_bad_cases': [P99], 'predicted_fixed_question_ids': [],
                'hypothesis': '减少上下文会降低 P99', 'why': 'P99 超标', 'risk': '可能丢失证据',
                'expected_improvement': P99 + ' 通过', 'review_conclusion_ids': ['C1'],
                'bad_case_conclusion_ids': ['C1'],
                'adjustments': [{'parameter': 'retrieval_max_tokens', 'baseline_value': False,
                                 'candidate_value': 4096, 'expected_impact': P99 + ' 通过'}],
                'risks': [{'question_ids': [], 'metric': 'completeness', 'reason': '资料可能被截去'}],
            }],
        })

    provider.complete.side_effect = propose
    OptimizationAgent(env.store, provider).generate(env.base, experiment_id=experiment)
    provider.complete.assert_called_once()
    [candidate] = env.store.experiment(experiment)['candidates']
    assert candidate['reasoning']['observed_evidence'] == []
    assert candidate['reasoning']['performance_targets'] == [P99]
    args = env.runner.start_candidate(candidate['id'])
    regressions = {'Q04': [scored(False, latency=1000), scored(False, latency=1000)]} if new_wrong_answer else {}
    for q, baseline_case in first.items():
        case = regressions[q][0] if q in regressions else baseline_case
        env.store.record_evaluation_case(args[0], q, {
            **case, 'programmatic_metrics': {**case['programmatic_metrics'], 'latency_ms': 1000}})
    finished = env.finish_candidate(args, regressions)
    assert finished['result']['qualification']['qualified'] is (not new_wrong_answer)
    assert finished['result']['gates']['passed'] is True
    assert finished['result']['all_fixed_question_ids'] == []
    if new_wrong_answer:
        assert finished['result']['new_regression_question_ids'] == ['Q04']
        assert finished['recommendation']['suggested_winner'] is None
        from app.optimization_cycle import layered_stage_facts, staged_decision

        facts = layered_stage_facts(env.store, env.store.experiment(experiment), env.baseline, None, 1)
        assert facts['remaining_count'] == 0
        assert facts['untried_layers'] == ['performance']
        assert staged_decision(1, 0, 1, version=env.store.experiment(experiment)['result']['verdict_version'],
                               **facts) == 'next_round'
        return
    assert finished['recommendation']['suggested_winner'] == candidate['id']
    env.store.confirm_experiment_report(experiment, candidate['id'], '用户')
    assert env.store.recommendation(experiment)['result']['recommended_candidate'] == candidate['id']
    assert env.store.experiment(experiment)['result']['hypothesis_chain']['1']['performance_outcome'] == 'true'
    env.answer.assert_not_called()
    env.runner.score_execution.assert_not_called()
