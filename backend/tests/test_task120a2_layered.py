import json
from unittest.mock import Mock

import pytest

from app import rules, verdict
from app.optimization import OptimizationAgent
from app.policy import GATE_DEFINITIONS

from test_task118a_verdict import OfflineEvaluation, scored


@pytest.fixture
def saved_runs(tmp_path, monkeypatch):
    first = {f'Q{i:02d}': scored(i > 6, f'Q{i:02d}') for i in range(1, 8)}
    env = OfflineEvaluation(tmp_path, monkeypatch, first, evidence=[
        {'source_chunk_ids': ['standard'], 'quote': '冻结题卷的标准证据原文'}])
    env.stable_baseline()
    store = env.store

    def save_candidate(experiment, label, round_number, fixes, **changes):
        cid = f'R{round_number}-{label}'
        reasoning = {'candidate_label': label, 'round': round_number, 'changed_parameters': changes}
        config = {key: value for key, value in env.baseline['config'].items() if key != 'run_target'} | changes
        store.save_candidate(experiment, cid, config, reasoning)
        full_id = f'{experiment}-{cid}'
        run = store.create_evaluation_run(env.snapshot, {**config, 'run_target': 'sandbox_candidate', 'candidate_id': full_id},
                                          env.baseline['judge'])
        finals = {}
        for q, raw in first.items():
            case = scored(raw['passed'] or q in fixes, 'standard' if q in {'Q05', 'Q06'} else q)
            store.record_evaluation_case(run, q, case)
            sample = verdict.make_sample(case, env.questions[q], 1, 'fixture', None)
            finals[q] = verdict.record(run, q, [sample])
        verdict.save_records(store, run, finals)
        result = {'evaluation_run_id': run, 'baseline_run_id': env.base, 'evaluation_complete': True, 'total': len(finals),
                  'evaluation_identity': env.baseline['judge']['evaluation_identity'],
                  'verdict_version': store.experiment(experiment)['result']['verdict_version'], 'bad_case_count': 6 - len(fixes),
                  'all_fixed_question_ids': sorted(fixes), 'qualification': {'qualified': True},
                  'gates': {'passed': True, 'gates': [{**g, 'passed': True} for g in GATE_DEFINITIONS]}}
        store.finish_evaluation_run(run, 'completed', result)
        store.finish_candidate(full_id, 'evaluated', result)
        return full_id, run

    return env, save_candidate


def test_target_layer_counts_primary_faults_and_priorities():
    from app.agent_round_contract import target_layer

    faults = ['recall', 'ranking', 'final', 'generation', 'generation']
    assert target_layer(faults, [], False)['layer'] == 'retrieval'
    assert target_layer(faults, [], True)['layer'] == 'safety'
    assert target_layer(faults[1:], [], False)['layer'] == 'retrieval'
    assert target_layer(faults, ['generation'], False)['layer'] == 'generation'
    assert target_layer(faults, [], False)['counts'] == {'safety': 0, 'retrieval': 3, 'generation': 2}


def test_off_layer_requires_a_shortage_and_a_reason():
    from app.agent_round_contract import validate_target_layer

    candidate = {'id': 'B', 'config_diff': {'generation_thinking': 'high'}}
    target = {'layer': 'retrieval', 'capacity': 1, 'proposal_count': 2}
    selected = [{'question_id': 'Q05'}]
    opportunities = {'Q05': {'fault': {'code': 'generation'}}}
    with pytest.raises(ValueError, match='layer_reason'):
        validate_target_layer(candidate, selected, opportunities, target)
    candidate['layer_reason'] = '同轮仅有一个独立检索手段'
    validate_target_layer(candidate, selected, opportunities, target)
    with pytest.raises(ValueError, match='目标层'):
        validate_target_layer(candidate, selected, opportunities, {**target, 'capacity': 2})


def test_generation_precondition_blocks_without_stop(saved_runs, tmp_path, monkeypatch):
    env, _ = saved_runs
    exp = env.store.create_experiment(env.base, decision_contract_v2=True)
    directory = tmp_path / 'retrieval_preview'
    directory.mkdir()
    (directory / f'{env.base}.json').write_text(json.dumps({
        'baseline_run_id': env.base, 'rules_version': rules.RULES_VERSION,
        'knowledge_identity': env.snapshot['corpus_fingerprint'], 'configs': []}))
    monkeypatch.setattr('app.agent_mechanism.fault_stage', lambda row: {
        'code': 'generation', 'subtype': None, 'reason': '已进入 Final'})
    provider = Mock(spec=['complete'])
    with pytest.raises(ValueError, match='前置条件未满足：需先对当前底座做生成诊断'):
        OptimizationAgent(env.store, provider).generate(env.base, experiment_id=exp)
    state = env.store.experiment(exp)['result']
    assert not state.get('decision_stop')
    assert state['round_target_layer']['layer'] == 'generation'
    provider.complete.assert_not_called()


def test_more_fixes_cannot_erase_previous_winner_repair(saved_runs):
    from app.agent_round_contract import layered_winner

    env, save = saved_runs
    exp = env.store.create_experiment(env.base)
    a, _ = save(exp, 'A', 1, {'Q01', 'Q02'}, top_k=6)
    save(exp, 'B', 2, {'Q02', 'Q03', 'Q04'}, candidate_k=24)
    experiment = env.store.experiment(exp)
    assert layered_winner(env.store, env.baseline, experiment['candidates'])['id'] == a
    assert env.store.refresh_recommendation(exp)['suggested_winner'] == a
    c, _ = save(exp, 'C', 2, {'Q01', 'Q02', 'Q04'}, candidate_k=24, top_k=6)
    assert env.store.refresh_recommendation(exp)['suggested_winner'] == c


def test_staged_decision_waits_for_generation_evidence_even_with_two_qualifiers():
    from app.optimization_cycle import staged_decision

    facts = {'remaining_count': 2, 'untried_layers': ['generation'], 'has_combination': True}
    assert staged_decision(1, 2, 3, version='2026-11-25', **facts) == 'next_round'
    assert staged_decision(1, 2, 3, version='2026-11-24', **facts) == 'composite'
    assert staged_decision(2, 2, 6, version='2026-11-25', **{**facts, 'untried_layers': []}) == 'composite'
    assert staged_decision(4, 2, 11, version='2026-11-25', **facts) == 'composite'
    assert staged_decision(4, 2, 11, version='2026-11-25', **{**facts, 'remaining_count': 0}) == 'finish_winner'
    assert staged_decision(4, 2, 11, version='2026-11-25', **{**facts, 'has_combination': False}) == 'finish_winner'


def test_saved_stage_findings_use_current_winner_and_skip_d_when_all_pass(saved_runs):
    from app.optimization_cycle import layered_stage_facts, staged_decision

    env, save = saved_runs
    store = env.store
    exp = store.create_experiment(env.base)
    a, _ = save(exp, 'A', 1, {'Q01', 'Q02', 'Q03', 'Q04'}, candidate_k=24)
    save(exp, 'B', 1, {'Q02', 'Q05'}, top_k=6)
    experiment = store.experiment(exp)
    facts = layered_stage_facts(store, experiment, env.baseline, store.candidate(a), 1)
    assert facts == {'remaining_count': 2, 'untried_layers': ['generation'], 'has_combination': True}
    assert staged_decision(1, 2, experiment['evaluation_budget']['used'],
                           version=rules.RULES_VERSION, **facts) == 'next_round'
    final, _ = save(exp, 'A', 2, {f'Q{i:02d}' for i in range(1, 7)}, candidate_k=24, generation_thinking='high')
    store.confirm_experiment_report(exp, final, '用户')
    confirmed = store.experiment(exp)
    assert confirmed['result']['optimization_cycle']['staged_decision']['decision'] == 'finish_winner'
    assert not confirmed['result'].get('composite')
    assert store.recommendation(exp)['result']['recommended_candidate'] == final


def test_cumulative_changes_include_inherited_parameters():
    from app.agent_round_contract import validate_layered_limits

    winner = {**rules.BASELINE, 'top_k': 6, 'candidate_k': 24}
    validate_layered_limits({**winner, 'generation_thinking': 'high'}, winner, rules.BASELINE)
    with pytest.raises(ValueError, match='相对 Baseline 最多改 3'):
        validate_layered_limits({**winner, 'generation_thinking': 'high', 'prompt_strategy': 'Safe'}, winner, rules.BASELINE)


def test_seed_a_reuses_saved_run_and_keeps_round_one_open(saved_runs, tmp_path, monkeypatch):
    env, save = saved_runs
    store = env.store
    source = store.create_experiment(env.base)
    with store.connection() as db:
        db.execute("UPDATE experiments SET result_json=json_set(result_json, '$.verdict_version', '2026-11-24') WHERE id=?",
                   (source,))
    a, run = save(source, 'A', 1, {'Q01', 'Q02', 'Q03'}, candidate_k=24)
    b, _ = save(source, 'B', 1, {'Q04'}, top_k=6)
    original = store.experiment(source)
    env.answer.reset_mock()
    env.runner.score_execution.reset_mock()
    with pytest.raises(ValueError, match='第 1 轮 A'):
        store.create_experiment(env.base, seed_candidates=[{'experiment_id': source, 'candidate_id': b}])
    reference = [{'experiment_id': source, 'candidate_id': a}]
    with store.connection() as db:
        original_judge = db.execute('SELECT judge_json FROM evaluation_runs WHERE id=?', (run,)).fetchone()[0]
        db.execute("UPDATE evaluation_runs SET judge_json=json_set(judge_json, '$.model', 'other') WHERE id=?", (run,))
    count = store.latest_experiment()['id']
    with pytest.raises(ValueError, match='Judge 合同'):
        store.create_experiment(env.base, seed_candidates=reference)
    assert store.latest_experiment()['id'] == count
    with store.connection() as db:
        db.execute("UPDATE evaluation_runs SET judge_json=? WHERE id=?", (original_judge, run))
    e5 = store.create_experiment(env.base, decision_contract_v2=True,
                                 seed_candidates=reference)
    exp = store.experiment(e5)
    [seed] = exp['candidates']
    provenance = {'source_experiment_id': source, 'source_candidate_id': a, 'source_run_id': run,
                  'generated_by': 'Agent', 'reuse': '用户授权沿用'}
    assert seed['id'] == f'{e5}-R1-A'
    assert all(seed['reasoning'][key] == value for key, value in provenance.items())
    assert seed['result']['qualification']['rule_version'] == '2026-11-25'
    assert seed['result']['qualification']['qualified']
    assert seed['result']['evaluation_run_id'] == run
    assert seed['result']['total'] == len(env.questions)
    assert exp['evaluation_budget']['used'] == 0
    assert not exp['rounds'][0]['complete']
    assert not store.round_completion(seed)['complete']
    ledger = exp['result']['parameter_effect_ledger']
    assert ledger['historical'] == []
    assert {row['question_id'] for row in ledger['current'] if row['status'] == '修好'} == {'Q01', 'Q02', 'Q03'}
    assert all(all(row[k] == v for k, v in provenance.items()) for row in ledger['current'])
    assert store.experiment(source) == original
    env.answer.assert_not_called()
    env.runner.score_execution.assert_not_called()

    directory = tmp_path / 'retrieval_preview'
    directory.mkdir()
    options = [('B', 'min_score', 0.3, 'Q04'), ('C', 'query_rewrite', True, 'Q05')]
    (directory / f'{env.base}.json').write_text(json.dumps({
        'baseline_run_id': env.base, 'rules_version': rules.RULES_VERSION,
        'knowledge_identity': env.snapshot['corpus_fingerprint'],
        'configs': [{'change': {key: value}, 'evidence_enters_final': [q]}
                    for _, key, value, q in options]}))
    monkeypatch.setattr('app.optimization.wait_for_off_peak', Mock())
    provider = Mock(spec=['complete'])

    def propose(system, user, **kwargs):
        prompt = json.loads(user)
        assert prompt['goal']['candidate_labels'] == ['B', 'C']
        assert prompt['round_base'] == {'id': 'Baseline', 'changes': {}}
        assert prompt['round_target_layer']['layer'] == 'retrieval'
        [source_a] = prompt['seed_candidates']
        assert source_a['source'] == provenance
        assert source_a['result']['all_fixed_question_ids'] == ['Q01', 'Q02', 'Q03']
        conclusion = {'id': 'C1', 'conclusion': '基于保存证据'}
        return json.dumps({
            'hypothesis_plan': {'hypothesis': '扩大证据入口', 'test_candidate': 'B',
                                'if_true': {'action': 'stop'}, 'if_false': {'action': 'stop'}},
            'prior_round_review': {
                'summary': '沿用 A 的保存结果', 'baseline_remaining_assessment': '从原底座试 B/C',
                'conclusions': [conclusion], 'plans': [{
                    'candidate_id': seed['id'], 'changes': {'candidate_k': 24},
                    'fixed_question_ids': ['Q01', 'Q02', 'Q03'], 'new_failure_question_ids': [],
                    'evidence_reason': '原 Sandbox 有最终判定', 'conclusion': '修好三题',
                    'causal_claims': [{'question_id': q, 'conclusion': '不确定'} for q in ('Q01', 'Q02', 'Q03')],
                }]},
            'bad_case_summary': {'groups': prompt['bad_case_groups'], 'focus': '检索', 'conclusions': [conclusion]},
            'candidates': [{
                'id': label, 'config_diff': {key: value}, 'target_bad_cases': [q],
                'predicted_fixed_question_ids': [q], 'direction': key, 'hypothesis': key + ' 会扩大证据入口',
                'why': '保存的检索预演', 'risk': '可能改变结果', 'expected_improvement': q + ' 补足证据',
                'review_conclusion_ids': ['C1'], 'bad_case_conclusion_ids': ['C1'],
                'adjustments': [{'parameter': key, 'baseline_value': env.baseline['config'][key],
                                 'candidate_value': value, 'expected_impact': q + ' 补足证据'}],
                'risks': [{'question_ids': [], 'metric': 'P99', 'reason': '可能变慢'}],
            } for label, key, value, q in options],
        })

    provider.complete.side_effect = propose
    OptimizationAgent(store, provider).generate(env.base, experiment_id=e5)
    provider.complete.assert_called_once()
    assert [c['reasoning']['candidate_label'] for c in store.experiment(e5)['candidates']] == ['A', 'B', 'C']
    assert store.experiment(source) == original
    env.answer.assert_not_called()
    env.runner.score_execution.assert_not_called()


def test_old_versions_keep_saved_qualification_and_staged_policy(saved_runs):
    from app.optimization_cycle import staged_decision

    env, save = saved_runs
    for version in ('2026-11-20b', '2026-11-24'):
        exp = env.store.create_experiment(env.base)
        a, _ = save(exp, 'A', 1, {'Q01'}, top_k=6)
        with env.store.connection() as db:
            row = db.execute('SELECT result_json FROM experiments WHERE id=?', (exp,)).fetchone()
            db.execute('UPDATE experiments SET result_json=? WHERE id=?',
                       (json.dumps({**json.loads(row[0]), 'verdict_version': version}), exp))
        assert env.store.candidate(a)['result']['qualification']['qualified']
        assert staged_decision(1, 2, 3, version=version) == 'composite'
        assert env.store.experiment(exp)['evaluation_budget']['reserved_for_d'] == 0
