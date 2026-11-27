import pytest

from app import rules
from app.agent_round_contract import layer_plan, round_opportunities, validate_combinations, validate_layered_limits
from app.composite import validate_d_parameter_limit
from test_task120a2_layered import saved_runs


VERSION = '125a'
BASE = {'id': 'Baseline', 'changes': {}}
RERANK = {'rerank': False}
POOL = {'candidate_k': 24, 'top_k': 6}
QUERY = {'hybrid_alpha': 0.7, 'multi_query': 2}


def target(question_id, code='ranking'):
    return {'question_id': question_id, 'diagnostic_view': {},
            'mechanism_fault': {'code': code, 'subtype': None, 'reason': '已定位错因'}}


def retrieval_check(changes, question, *, before='未进入', after=1):
    return {'kind': 'retrieval', 'changes': changes, 'results': [{
        'question_id': question, 'before': [{'chunk_id': 'std', 'final': before}],
        'after': [{'chunk_id': 'std', 'final': after}], 'context_changed': True,
    }]}


def opportunities(targets, checks, *, base=BASE, version=VERSION, ledger=()):
    return round_opportunities(targets, base, rules.BASELINE, [], {'directed_checks': checks},
                               ledger, [], use_layered=True, decision_version=version)


def plan(rows, *, version=VERSION):
    return layer_plan(rows, [], False, [], BASE['id'], ['A', 'B', 'C'], decision_version=version, directed=True)


def test_e6_round_one_one_evidenced_and_two_exploratory():
    rows = opportunities([target('Q04')], [retrieval_check(RERANK, 'Q04')])
    available = rows['Q04']['available']
    assert plan(rows)['proposal_count'] == 3
    assert available[0] == {'changes': RERANK, 'decision': '有证据'}
    assert {row['decision'] for row in available[1:]} == {'探索性'}
    assert len({key for row in available[1:] for key in row['changes']} - RERANK.keys()) >= 2


def test_e6_round_two_keeps_both_disjoint_evidenced_pairs():
    base = {'id': 'R1-A', 'changes': RERANK}
    rows = opportunities([target('Q18'), target('Q24', 'recall')],
                         [retrieval_check(POOL, 'Q18'), retrieval_check(QUERY, 'Q24')], base=base)
    assert rows['Q18']['available'][0] == {'changes': POOL, 'decision': '有证据'}
    assert rows['Q24']['available'][0] == {'changes': QUERY, 'decision': '有证据'}
    assert not POOL.keys() & QUERY.keys()
    validate_combinations([{'config_diff': change, 'attribution': '组合探索，不可归因'}
                           for change in (POOL, QUERY)], decision_version=VERSION)
    checked_rows = {qid: {**row, 'available': row['available'][:1]} for qid, row in rows.items()}
    assert plan(checked_rows)['proposal_count'] == 2


def test_fill_uses_next_layer_when_larger_group_needs_it():
    rows = {
        'Q04': {'fault': {'code': 'recall'}, 'available': [{'changes': POOL}]},
        'Q12': {'fault': {'code': 'generation'}, 'available': [
            {'changes': {'candidate_k': 24}}, {'changes': {'top_k': 6}},
            {'changes': {'generation_thinking': 'low'}}]},
    }
    decision = plan(rows)
    assert decision['proposal_count'] == 3
    assert decision['layer'] == 'generation'
    assert decision['capacity'] == 3


@pytest.mark.parametrize('validate', [
    lambda config, current: validate_layered_limits(config, current, rules.BASELINE, decision_version=VERSION),
    lambda config, current: validate_d_parameter_limit(config, rules.BASELINE, decision_version=VERSION),
], ids=['winner-chain', 'D'])
def test_four_changes_pass_fifth_is_rejected(validate):
    current = {**rules.BASELINE, **RERANK, **POOL}
    fourth = {**current, 'multi_query': 2}
    validate(fourth, current)
    with pytest.raises(ValueError, match='最多改 4'):
        validate({**fourth, 'hyde': True}, current)


@pytest.mark.parametrize('harm', ['final-loss', 'generation-regression'])
def test_harm_on_a_different_question_rejects_config(harm):
    harmful = RERANK if harm == 'final-loss' else {'prompt_strategy': rules.SAFE}
    checks = [retrieval_check(harmful, 'Q07', before=1, after='未进入')] if harm == 'final-loss' else []
    ledger = [] if checks else [{'source': '生成诊断', 'base_id': 'Baseline', 'changes': harmful,
                                'question_id': 'Q07', 'status': '弄坏'}]
    fault = 'ranking' if checks else 'generation'
    row = opportunities([target('Q04', fault)], checks, ledger=ledger)['Q04']
    assert row['available']
    assert harmful not in [action['changes'] for action in row['available']]


def test_saved_122f_keeps_evidence_gate_and_three_parameter_limit(saved_runs):
    env, _ = saved_runs
    store = env.store
    old = store.create_experiment(env.base)
    with store.connection() as db:
        db.execute("UPDATE experiments SET result_json=json_set(result_json,'$.bad_case_decision_version','122f') WHERE id=?", (old,))
    new = store.create_experiment(env.base)
    old_version = store.experiment(old)['result']['bad_case_decision_version']
    assert old_version == '122f'
    old_rows = opportunities([target('Q04')], [retrieval_check(RERANK, 'Q04')], version=old_version)
    assert plan(old_rows, version=old_version)['proposal_count'] == 1
    with pytest.raises(ValueError, match='最多改 3'):
        validate_d_parameter_limit({**rules.BASELINE, **RERANK, **POOL, 'multi_query': 2},
                                   rules.BASELINE, decision_version=old_version)
    assert store.experiment(new)['result']['bad_case_decision_version'] == VERSION


def test_directed_round_retries_short_reply_and_persists_abc(saved_runs):
    import json
    from types import SimpleNamespace

    from app.paid_schedule import set_settings
    from app.workflow_engine import WorkflowEngine
    from test_task123b_directed_planning import hypothesis

    env, _ = saved_runs
    store = env.store
    set_settings(store, False)
    experiment = store.create_experiment(env.base)
    phases = []
    options = [('A', RERANK, '合并原召回顺序让标准段留在 Final'),
               ('B', {'candidate_k': 24}, '扩大池子召回低排名标准段'),
               ('C', {'query_decompose': True}, '拆问找回子问对应标准段')]

    def complete(system, user, **kwargs):
        prompt = json.loads(user)
        phase = prompt['planning_stage']
        phases.append(phase)
        if phase == 'hypotheses':
            return json.dumps({'hypotheses': [hypothesis(RERANK)]})
        assert prompt['goal']['candidate_labels'] == ['A', 'B', 'C']
        assert prompt['round_opportunities']['Q01']['available'][0]['decision'] == '有证据'
        if len(phases) == 2:
            return json.dumps({'candidates': [], 'insufficient_evidence': '只有 A 做过定向检查'})
        assert '须填满 A/B/C' in prompt['validation_rejection']
        assert json.loads(prompt['previous_response'])['candidates'] == []
        assert prompt['validation_rejection_history'] == [prompt['validation_rejection']]
        conclusion = {'id': 'C1', 'conclusion': '标准证据缺失'}
        return json.dumps({
            'prior_round_review': {'summary': '无', 'plans': [], 'conclusions': [conclusion],
                                   'baseline_remaining_assessment': '还有检索错题'},
            'bad_case_summary': {'groups': prompt['bad_case_groups'], 'focus': '检索', 'conclusions': [conclusion]},
            'hypothesis_plan': {'hypothesis': options[0][2], 'test_candidate': 'A',
                                'if_true': {'action': 'stop'}, 'if_false': {'action': 'stop'}},
            'candidates': [{'id': label, 'config_diff': change, 'target_bad_cases': ['Q01'],
                            'hypothesis': mechanism, 'why': mechanism, 'risk': '可能召回噪声',
                            'direction': next(iter(change)), 'expected_improvement': '修好 Q01',
                            'bad_case_conclusion_ids': ['C1'], 'review_conclusion_ids': ['C1'],
                            'predicted_fixed_question_ids': ['Q01'],
                            'cross_layer_mechanisms': {'Q01': mechanism},
                            'adjustments': [{'parameter': key, 'candidate_value': value,
                                             'baseline_value': rules.BASELINE[key], 'expected_impact': '改善 Q01'}
                                            for key, value in change.items()],
                            'risks': [{'question_ids': ['Q07'], 'metric': None, 'reason': '可能引入噪声'}]}
                           for label, change, mechanism in options],
        })

    def retrieve(question, config):
        assert config['rerank'] is False
        final = [{'chunk_id': 'standard', 'content': '冻结题卷的标准证据原文'}]
        return final, {}, [], {'final': final}, []

    runtime = SimpleNamespace(provider=SimpleNamespace(complete=complete), retrieve_context=retrieve)
    result = WorkflowEngine(store, runtime, experiment).generate_next()
    assert phases == ['hypotheses', 'candidates', 'candidates']
    assert result['evaluation_budget']['used'] == 0
    statuses = [(c['reasoning']['candidate_label'], c['reasoning']['evidence_status']) for c in result['candidates']]
    assert statuses == [('A', '有证据'), ('B', '探索性'), ('C', '探索性')]
    cases = env.raw_cases(env.base)
    for candidate in result['candidates']:
        args = env.runner.start_candidate(candidate['id'])
        for qid, case in cases.items():
            store.record_evaluation_case(args[0], qid, case)
        finished = env.finish_candidate(args, {qid: [case, case] for qid, case in cases.items()})
        assert finished['status'] == 'evaluated'
    assert store.experiment(experiment)['evaluation_budget']['used'] == 3


def test_three_inherited_edits_leave_a_next_round_before_d(saved_runs):
    from app.optimization_cycle import layered_stage_facts, staged_decision

    env, save = saved_runs
    store = env.store
    exp = store.create_experiment(env.base)
    save(exp, 'A', 1, {'Q01'}, **RERANK)
    cid, _ = save(exp, 'A', 2, {'Q01', 'Q02'}, **RERANK, **POOL)
    experiment = store.experiment(exp)
    winner = store.candidate(cid)
    facts = layered_stage_facts(store, experiment, env.baseline, winner, 2)
    assert facts['remaining_count'] == 4
    assert facts['untried_layers']
    assert staged_decision(2, 1, 6, version=rules.RULES_VERSION, **facts) == 'next_round'

    save(exp, 'B', 2, {'Q03'}, generation_thinking='low')
    experiment = store.experiment(exp)
    facts = layered_stage_facts(store, experiment, env.baseline, winner, 4)
    assert facts['has_combination']
    assert staged_decision(4, 1, 11, version=rules.RULES_VERSION, **facts) == 'composite'
    assert staged_decision(4, 1, 12, version=rules.RULES_VERSION, **facts) == 'finish_winner'


def test_saved_round_two_reply_can_repeat_unchanged_winner_value(saved_runs):
    import json

    from app.agent_inputs import baseline_bad_case_rows
    from app.optimization import prepare_response

    env, save = saved_runs
    experiment = env.store.create_experiment(env.base)
    winner, _ = save(experiment, 'C', 1, {'Q02'}, multi_query=2)
    prior = env.store.experiment(experiment)['candidates']
    cases = [row for row in baseline_bad_case_rows(env.store, env.baseline, use_final=True)
             if row['question_id'] == 'Q01']
    conclusion = {'id': 'C1', 'conclusion': '仍有错题'}
    candidate = {'id': 'A', 'inherited_from': winner, 'inherited_parameters': {'multi_query': 2},
                 'config_diff': {'multi_query': 2, 'top_k': 6}, 'hypothesis': '增加交付段数可以补证',
                 'why': '标准证据未进入交付', 'risk': '可能引入噪声', 'expected_improvement': '修好 Q01',
                 'direction': '检索排序', 'review_conclusion_ids': ['C1'], 'bad_case_conclusion_ids': ['C1'],
                 'target_bad_cases': ['Q01'], 'predicted_fixed_question_ids': ['Q01'],
                 'adjustments': [{'parameter': 'top_k', 'baseline_value': 4, 'candidate_value': 6,
                                  'expected_impact': '增加 Q01 的交付证据'}],
                 'risks': [{'question_ids': ['Q07'], 'reason': '可能引入噪声'}]}
    reply = {'candidates': [candidate], 'prior_round_review': {'summary': '复盘', 'plans': [
        {'candidate_id': winner, 'changes': {'multi_query': 2}, 'fixed_question_ids': ['Q02'],
         'new_failure_question_ids': [], 'evidence_reason': '增加召回路径', 'conclusion': '修好 Q02'}],
        'baseline_remaining_assessment': '仍有错题', 'conclusions': [conclusion]},
        'bad_case_summary': {'groups': [], 'focus': '检索', 'conclusions': [conclusion]},
        'hypothesis_plan': {'hypothesis': '扩大交付范围', 'test_candidate': 'A',
                            'if_true': {'action': 'D'},
                            'if_false': {'action': 'try', 'changes': {'multi_query': 2, 'candidate_k': 24}}}}
    audit = {'bad_case_decision_version': VERSION, 'round_base': {'id': winner, 'changes': {'multi_query': 2}},
             'ledger_inherit': [], 'ledger_exclude': [], 'bad_case_groups': [],
             'previous_commitment': {'expected': {'action': 'try', 'changes': {'top_k': 6}}},
             'strategy_contract': 'agent-strategy-4', 'optimization_run_id': experiment}

    def validate():
        return prepare_response(json.dumps(reply), rules.BASELINE, cases, prior, 1, 2, ['A'], None, [], audit)

    result, [(_, config, reasoning)] = validate()
    assert config['multi_query'] == 2
    assert reasoning['changed_parameters'] == {'top_k': 6}
    assert result['hypothesis_plan']['previous_check']['fulfilled'] is True
    assert result['hypothesis_plan']['if_false']['changes'] == {'candidate_k': 24}
    assert audit['parsed_candidates'][0]['config_diff'] == {'multi_query': 2, 'top_k': 6}
    candidate['config_diff']['multi_query'] = 3
    with pytest.raises(ValueError, match='保留 Winner 底座'):
        validate()


def test_pre_review_menu_excludes_winner_parameters(saved_runs):
    import json
    from types import SimpleNamespace

    from app.policy import search_space_contract
    from app.workflow_engine import WorkflowEngine
    from test_task123b_directed_planning import hypothesis

    env, save = saved_runs
    experiment = env.store.create_experiment(env.base)
    winner, run = save(experiment, 'A', 2, {'Q01', 'Q02'}, multi_query=2, top_k=6)
    planning = WorkflowEngine(env.store, SimpleNamespace(), experiment).directed_planning(3, winner, run)

    def ask(system, prompt):
        menu = prompt['search_space']
        changes = {'multi_query': 4} if 'multi_query' in menu else {'candidate_k': 24}
        return json.dumps({'hypotheses': [{**hypothesis(changes, targets=('Q03',)), 'checks': []}]})

    planning.begin({'search_space': search_space_contract(for_agent=True)}, ask)
    [prediction] = planning.review_input()['pre_review_prediction']
    assert prediction['changes'] == {'candidate_k': 24}


def test_formal_prompt_identifies_prior_results_with_inherited_multi_parameter_changes(saved_runs):
    from app.optimization import build_agent_prompt

    env, save = saved_runs
    experiment = env.store.create_experiment(env.base)
    save(experiment, 'C', 1, {'Q01'}, multi_query=2)
    candidate_id, _ = save(experiment, 'A', 2, {'Q01', 'Q02'}, multi_query=2, top_k=6)
    prior = env.store.experiment(experiment)['candidates']
    prior[1]['reasoning'].update(changed_parameters={'top_k': 6},
                                 changed_parameters_vs_baseline={'multi_query': 2, 'top_k': 6})

    _, prompt = build_agent_prompt([], rules.BASELINE, prior, [], ['A'], causal_evidence=True)

    assert prompt['prior_multi_parameter_reviews'] == [
        {'candidate_id': candidate_id, 'changes_vs_baseline': {'multi_query': 2, 'top_k': 6}},
    ]
    assert prompt['prior_round_review_inputs'][1] == {
        'candidate_id': candidate_id, 'fixed_question_ids': ['Q01', 'Q02'],
        'new_failure_question_ids': [],
    }


def test_e6_frozen_evaluation_rules_hash_still_passes_preflight():
    from app.evaluation_snapshot import require_resume_snapshot, run_snapshot

    snapshot = run_snapshot({'id': 'frozen-e6'}, rules.BASELINE, {})
    snapshot['rules_hash'] = '3b632b072857'
    require_resume_snapshot({'run_snapshot': snapshot}, for_candidate_baseline=True)
