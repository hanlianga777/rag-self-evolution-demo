import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app import rules
from app.evaluation import EvaluationRunner
from app.governance import GovernanceStore
from app.policy import DEFAULT_PIPELINE_CONFIG
from identity_fixture import completed_baseline
from test_task113b_mechanism import target


def candidate(name, count, qualified, **changes):
    return {'id': name, 'status': 'evaluated', 'config': {**DEFAULT_PIPELINE_CONFIG, **changes},
            'reasoning': {'round': 1, 'candidate_label': name[-1]},
            'result': {'bad_case_count': count, 'qualification': {'qualified': qualified}}}


def test_only_the_full_qualified_winner_is_the_base():
    from app.agent_round_contract import round_base, validate_base

    baseline = DEFAULT_PIPELINE_CONFIG
    winner = candidate('R1-A', 2, True, top_k=6)
    other = candidate('R1-B', 3, True, min_score=0.2)
    faster = candidate('R1-C', 1, False, query_decompose=True)
    base = round_base(baseline, [faster, other, winner], 2)
    assert base == {'id': 'R1-A', 'changes': {'top_k': 6}}
    assert round_base(baseline, [faster], 2) == {'id': 'Baseline', 'changes': {}}
    validate_base({'inherited_from': 'R1-A', 'inherited_parameters': {'top_k': 6}}, base)
    for plan in ({}, {'inherited_from': 'R1-B', 'inherited_parameters': {'min_score': 0.2}},
                 {'inherited_from': 'R1-A', 'inherited_parameters': {}},
                 {'inherited_from': 'R1-A', 'inherited_parameters': {'top_k': 6}, 'config_diff': {'top_k': 4}}):
        with pytest.raises(ValueError, match='底座'):
            validate_base(plan, base)


def test_untried_actions_use_mechanism_and_keep_per_question_blockers():
    from app.agent_round_contract import round_opportunities

    retrieval = target('Q17', [(6, 10, '未进入')])
    table = target('Q15', [(1, 1, 1)], '表格读取或归类错误')
    change = {'top_k': 6}
    preview = {'configs': [{'change': change, 'evidence_enters_final': ['Q17'],
                            'context_changed_question_ids': ['Q15']}]}
    base = {'id': 'Baseline', 'changes': {}}
    rows = round_opportunities([retrieval, table], base, DEFAULT_PIPELINE_CONFIG, [], preview, [], [])
    assert rows['Q17']['available'] == [{'changes': change, 'decision': '放行'}]
    assert rows['Q15']['available'] == [{'changes': change, 'decision': '补证'}]
    tried = candidate('R1-A', 3, False, **change)
    rows = round_opportunities([retrieval, table], base, DEFAULT_PIPELINE_CONFIG, [tried], preview, [], [])
    assert all(not row['available'] for row in rows.values())
    assert '表格结构化' in rows['Q15']['next_action']
    assert rows['Q17']['fault']['code'] == 'ranking'


def test_round_hypothesis_checks_observed_branch_and_requires_reason_for_deviation():
    from app.agent_round_contract import check_commitment, previous_commitment, validate_hypothesis

    candidates = [{'id': 'A', 'config_diff': {'top_k': 6}, 'predicted_fixed_question_ids': ['Q17']}]
    plan = {'hypothesis': '增加交付片段可找回证据', 'test_candidate': 'A',
            'if_true': {'action': 'try', 'changes': {'query_decompose': True}},
            'if_false': {'action': 'stop'}}
    previous_plan = {**plan, 'candidate_id': 'R1-B', 'question_ids': ['Q17']}
    context = {'hypothesis_chain': {'1': previous_plan}, 'parameter_effect_ledger': {'current': [
        {'candidate_id': 'R1-B', 'question_id': 'Q17', 'status': '修好'}]}}
    commitment = previous_commitment(context, 2)
    assert commitment['expected'] == plan['if_true']
    with pytest.raises(ValueError, match='理由'):
        validate_hypothesis(plan, candidates, [], [], commitment)
    saved = validate_hypothesis({**plan, 'deviation_reason': '剩余题只在预演中支持扩大交付'},
                                candidates, [], [], commitment)
    assert saved['previous_check']['fulfilled'] is False
    assert saved['previous_check']['reason']
    candidates[0]['config_diff'] = {'query_decompose': True}
    assert validate_hypothesis(plan, candidates, [], [], commitment)['previous_check']['fulfilled']
    context['parameter_effect_ledger']['current'][0]['status'] = '无效'
    failed = previous_commitment(context, 2)
    assert failed['expected'] == plan['if_false']
    assert check_commitment(failed, 'stop')['fulfilled']
    assert check_commitment(failed, 'D', reason='已有多个合格方案')['fulfilled'] is False
    context['parameter_effect_ledger']['current'].clear()
    assert previous_commitment(context, 2)['outcome'] == 'unknown'


def test_combinations_must_be_labeled_and_unique():
    from app.agent_round_contract import validate_combinations

    single = {'config_diff': {'top_k': 6}}
    combo = {'config_diff': {'query_decompose': True, 'candidate_k': 24}}
    validate_combinations([single])
    with pytest.raises(ValueError, match='标注'):
        validate_combinations([single, combo])
    combo['attribution'] = '组合探索，不可归因'
    validate_combinations([single, combo])
    with pytest.raises(ValueError, match='最多'):
        validate_combinations([combo, combo])


def test_diagnostic_retest_bypasses_existing_reuse_and_is_isolated(tmp_path):
    from app.request_reuse import reuse_result, reuse_scope

    store = GovernanceStore(tmp_path / 'retest.db')
    from app.corpus import current_manifest, manifest_identity

    snapshot = {'id': 'GD-retest', 'question_ids': ['Q1'], 'questions': [
        {'id': 'Q1', 'question': '安全样题', 'coverage_slot': 'Q43', 'test_category': 'negative',
         'negative_subtype': 'safety_critical'}], 'corpus_fingerprint': manifest_identity(current_manifest())}
    run_id = completed_baseline(store, snapshot=snapshot)
    run = store.evaluation_run(run_id)
    generation = Mock(return_value={'answer': 'same answer'})
    judge = Mock(side_effect=[
        {'passed': True, 'judge_result': {'safety_violation': False, 'samples': [
            {'safety_violation': False}, {'safety_violation': True}, {'safety_violation': False}]}},
        {'passed': False},
        {'passed': True},
    ])
    runtime = SimpleNamespace(model=run['judge']['model'],
        answer=lambda *_: reuse_result('generation', ['same'], generation))
    runner = EvaluationRunner(store, runtime)
    runner.score_execution = lambda *_: reuse_result('judge', ['same'], judge)
    with reuse_scope(store, run):
        reuse_result('generation', ['same'], lambda: {'answer': 'old'})
        reuse_result('judge', ['same'], lambda: {'passed': False})
        result = runner.diagnostic_retest(run_id, ['Q43'])
        assert reuse_result('generation', ['same'], generation)['answer'] == 'old'
    [row] = result['questions']
    assert row['distribution'] == '2/3'
    assert row['risk'] is True
    assert [trial['risk'] for trial in row['trials']] == [True, True, False]
    assert len({trial['id'] for trial in row['trials']}) == 3
    assert generation.call_count == judge.call_count == 3
    with store.connection() as db:
        assert db.execute('SELECT count(*) FROM model_request_reuse').fetchone()[0] == 2
        assert db.execute('SELECT count(*) FROM evaluation_runs').fetchone()[0] == 1
        assert db.execute('SELECT count(*) FROM experiments').fetchone()[0] == 0
    with pytest.raises(ValueError, match='题号'):
        runner.diagnostic_retest(run_id, ['missing'])
    with pytest.raises(ValueError, match='正整数'):
        runner.diagnostic_retest(run_id, ['Q1'], repetitions=0)


def test_gate2_authorization_is_saved_and_gate3_rejects_delegation():
    from app.policy import gate_audit

    with pytest.raises(ValueError, match='授权'):
        gate_audit('gate2', 'Codex')
    for actor in ('用户', '当前用户'):
        assert gate_audit('gate2', 'Codex', authorization={
            'enabled': True, 'actor': actor, 'authorized_at': 'fixture'}) == rules.AGENT_GATE_AUDIT
    for actor in ('Codex', 'Agent'):
        with pytest.raises(ValueError, match='用户授权'):
            gate_audit('gate2', 'Codex', authorization={'enabled': True, 'actor': actor, 'authorized_at': 'fixture'})
    assert gate_audit('gate3', 'local_user')['executed_by'] == 'local_user'
    for actor in ('Codex', '总指挥'):
        with pytest.raises(ValueError, match='发布'):
            gate_audit('gate3', actor)
    with pytest.raises(ValueError, match='双审'):
        gate_audit('gate2', '总指挥', reviews={'claude':'pass', 'gpt':'pass'})


def test_no_evidence_stops_staged_cycle_without_calling_provider(tmp_path, monkeypatch):
    from app.optimization_cycle import run_until_qualified

    store = GovernanceStore(tmp_path / 'stop.db')
    run_id = completed_baseline(store)
    experiment = store.create_experiment(run_id, decision_contract_v2=True)
    with store.connection() as db:
        db.execute("UPDATE experiments SET result_json=json_set(result_json, '$.round_policy', json(?)) WHERE id=?",
                   (json.dumps({'mode': 'full_rounds', 'stop_rule': 'staged-v1'}), experiment))
    monkeypatch.setattr('app.optimization_cycle.wait_for_off_peak', Mock())
    provider = Mock(spec=['complete'])
    cycle = run_until_qualified(store, SimpleNamespace(provider=provider), experiment)
    saved = store.experiment(experiment)
    assert cycle['status'] == 'stopped'
    assert saved['result']['decision_stop']['reason'] == '证据不足以继续'
    [blocker] = saved['result']['decision_stop']['questions'].values()
    assert not blocker['available'] and blocker['next_action'] and blocker['fault']['stage']
    assert saved['candidates'] == [] and saved['evaluation_budget']['used'] == 0
    provider.complete.assert_not_called()


def test_e2_gate2_correction_preserves_approval_and_is_idempotent(tmp_path):
    from app.gate_audit_correction import E2_ID, E2_APPROVAL_ID, append_e2_gate2_correction

    store = GovernanceStore(tmp_path / 'correction.db')
    approval = (E2_APPROVAL_ID, 'experiment_report', E2_ID, 'approved', 'Codex', '2026-11-23T02:43:18.458+00:00')
    original = {'actor': 'Codex', 'confirmed_at': '2026-11-23T02:43:18.448+00:00',
                'winner_id': f'{E2_ID}-R2-B'}
    patched = {'report_confirmation': {**original, **rules.AGENT_GATE_AUDIT}, 'other': 'preserved'}
    with store.connection() as db:
        db.execute('INSERT INTO approvals VALUES (?, ?, ?, ?, ?, ?)', approval)
        db.execute('INSERT INTO experiments VALUES (?, ?, ?, ?, ?)',
                   (E2_ID, 'fixture', 'completed', json.dumps(patched), 'fixture'))
        db.execute('INSERT INTO recommendations VALUES (?, ?, ?, ?, ?)',
                   (E2_ID, original['winner_id'], 'Recommended', json.dumps({'report_confirmation': original}), 'fixture'))
    with pytest.raises(ValueError, match='补录记录不一致'):
        append_e2_gate2_correction(store)
    assert store.experiment(E2_ID)['result'] == patched
    with store.connection() as db:
        db.execute('UPDATE recommendations SET result_json=? WHERE experiment_id=?', (json.dumps(patched), E2_ID))
    event = append_e2_gate2_correction(store)
    assert event['original_approval']['id'] == E2_APPROVAL_ID
    assert event['corrected_by'] == 'Codex' and event['corrected_at'] and event['reason']
    assert event['audit'] == rules.AGENT_GATE_AUDIT
    assert append_e2_gate2_correction(store) == event
    assert store.experiment(E2_ID)['result'] == {'report_confirmation': original, 'other': 'preserved',
                                                 'gate2_audit_correction': event}
    assert store.recommendation(E2_ID)['result'] == {'report_confirmation': original, 'other': 'preserved'}
    with store.connection() as db:
        assert tuple(db.execute('SELECT * FROM approvals').fetchone()) == approval
        assert db.execute('SELECT count(*) FROM gate_audit_corrections').fetchone()[0] == 1


def test_sandbox_preflight_revalidates_the_saved_full_winner_base(tmp_path, monkeypatch):
    from app.agent_mechanism import CONTRACT
    from diagnostic_fixture import retrieval_case
    from test_optimization_contract import trace_case

    monkeypatch.setattr('app.diagnostics._current_corpus', lambda *_args, **_kwargs: (retrieval_case()[1], {'corpus': 'one'}))
    store = GovernanceStore(tmp_path / 'winner.db')
    from app.corpus import current_manifest, manifest_identity

    snapshot = {'id': 'GD-winner', 'question_ids': ['Q1'], 'questions': [
        {'id': 'Q1', 'question': '测试', 'test_category': 'positive'}],
        'corpus_fingerprint': manifest_identity(current_manifest())}
    with store.connection() as db:
        db.execute('INSERT INTO dataset_versions VALUES (?, ?, ?, ?, ?)',
                   (snapshot['id'], 'approved', 'human_review', json.dumps(snapshot), 'fixture'))
    run_id = completed_baseline(store, snapshot=snapshot)
    baseline = store.evaluation_run(run_id)
    store.record_bad_case(run_id, 'Q1', 'Retrieval', 'ordinary', trace_case())
    experiment = store.create_experiment(run_id, decision_contract_v2=True)
    winner_id = f'{experiment}-R1-A'
    base_changes = {'query_decompose': True, 'candidate_k': 24}
    winner_config = {**DEFAULT_PIPELINE_CONFIG, **base_changes}
    store.save_candidate(experiment, 'R1-A', winner_config, {'round': 1, 'candidate_label': 'A'})
    identity = baseline['judge']['evaluation_identity']
    with store.connection() as db:
        db.execute("UPDATE candidate_configs SET status='evaluated',result_json=? WHERE id=?",
                   (json.dumps({'qualification': {'qualified': True}, 'evaluation_identity': identity,
                                'evaluation_complete': True, 'bad_case_count': 1}), winner_id))
    candidate_id = f'{experiment}-R2-A'
    changes = {'top_k': 6}
    config = {**winner_config, **changes}
    history = {'round': 2, 'candidate_label': 'A', 'intervention_contract_version': 'agent-closure-4',
               'round_base': {'id': winner_id, 'changes': base_changes}, 'inherited_from': winner_id,
               'inherited_parameters': base_changes, 'changed_parameters': changes, 'observed_evidence': ['Q1'],
               'changed_parameters_vs_baseline': {**base_changes, **changes}, 'hypothesis': '试交付更多资料',
               'proposal': '逐题核对最终资料', 'expected_improvement': '改善 Q1', 'risk': '时延增加'}
    store.save_candidate(experiment, 'R2-A', config, history)
    assert store.experiment(experiment)['result']['mechanism_contract'] == CONTRACT
    runner = EvaluationRunner(store, SimpleNamespace(model=baseline['judge']['model']))
    _, prepared, _, _ = runner.candidate_inputs(candidate_id)
    assert all(prepared[key] == value for key, value in {**base_changes, **changes}.items())
    with store.connection() as db:
        db.execute("UPDATE candidate_configs SET result_json=json_set(result_json,'$.qualification.qualified',json('false')) WHERE id=?",
                   (winner_id,))
    with pytest.raises(ValueError, match='底座与合格 Winner 不一致'):
        runner.candidate_inputs(candidate_id)


def test_inherited_repairs_follow_the_current_winner_lineage():
    from app.agent_round_contract import inherited_repairs

    first = candidate('R1-A', 3, True, query_decompose=True)
    second = candidate('R2-B', 2, True, query_decompose=True, top_k=6)
    second['reasoning']['inherited_from'] = first['id']
    base = {'id': second['id'], 'changes': {'query_decompose': True, 'top_k': 6}}
    rows = [
        {'candidate_id': first['id'], 'question_id': 'Q27', 'status': '修好', 'changes': {'query_decompose': True}},
        {'candidate_id': second['id'], 'question_id': 'Q21', 'status': '修好', 'changes': {'top_k': 6}},
        {'candidate_id': second['id'], 'question_id': 'Q17', 'status': '修好', 'changes': {'candidate_k': 24, 'top_k': 6}},
        {'candidate_id': 'R1-C', 'question_id': 'Q21', 'status': '修好', 'changes': {'query_decompose': True}},
    ]
    assert inherited_repairs(base, [first, second], rows, {'Q17', 'Q21', 'Q27'}) == rows[:2]
    assert inherited_repairs(base, [first, second], rows, {'Q17', 'Q21'}) == rows[1:2]


def test_gate_routes_reject_unrecognized_actor_and_keep_manual_paths(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app import main

    store = GovernanceStore(tmp_path / 'gates.db')
    baseline = completed_baseline(store)
    experiment = store.create_experiment(baseline)
    monkeypatch.setattr(main, 'store', store)
    client = TestClient(main.app)
    gate2 = f'/api/experiments/{experiment}/recommendation'
    response = client.post(gate2, json={'candidate_id': 'fixture', 'actor': 'Agent'})
    assert response.status_code == 409 and '用户确认入口' in response.json()['detail']
    assert '用户授权' in client.post(gate2, json={'candidate_id': 'fixture', 'actor': 'Codex'}).json()['detail']
    assert '合格' in client.post(gate2, json={'candidate_id': 'fixture', 'actor': 'human'}).json()['detail']
    gate3 = '/api/candidates/fixture/publish'
    assert '用户确认入口' in client.post(gate3, json={'decision': 'approved', 'actor': 'Agent'}).json()['detail']
    assert 'Sandbox' in client.post(gate3, json={'decision': 'approved'}).json()['detail']
    assert client.post('/api/runtime-settings/unattended', json={'enabled': True, 'actor': 'Agent'}).status_code == 422
    assert client.post('/api/runtime-settings/unattended', json={'enabled': True, 'actor': '当前用户'}).status_code == 200
