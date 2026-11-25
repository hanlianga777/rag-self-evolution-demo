import json
from unittest.mock import Mock

import pytest

from app import rules, verdict
from app.agent_mechanism import validate_mechanism
from app.agent_round_contract import round_opportunities
from app.composite import validate_d_refinement
from app.optimization import build_agent_prompt, validate_round_contract

from test_task118a_verdict import OfflineEvaluation, scored


@pytest.fixture
def setup(tmp_path, monkeypatch):
    env = OfflineEvaluation(tmp_path, monkeypatch, {
        'Q01': scored(False), 'Q02': scored(False), 'Q03': scored(True),
    })
    production = {**rules.BASELINE, 'candidate_k': 24, 'top_k': 6}
    baseline_config = {**production, 'run_target': 'baseline'}
    with env.store.connection() as db:
        db.execute("UPDATE evaluation_runs SET config_json=? WHERE id=?", (json.dumps(baseline_config), env.base))
        db.execute("UPDATE production_versions SET status='archived' WHERE status='active'")
        db.execute("INSERT INTO production_versions (id,status,config_json,created_at) VALUES ('A','active',?,'fixture')",
                   (json.dumps(production),))
    env.stable_baseline()
    preview = tmp_path / 'retrieval_preview' / f'{env.base}.json'
    preview.parent.mkdir()
    preview.write_text(json.dumps({'baseline_run_id': env.base, 'rules_version': rules.RULES_VERSION,
                                   'knowledge_identity': env.snapshot['corpus_fingerprint'], 'configs': []}))
    return env, preview


def generation_target():
    return {'question_id': 'Q01', 'diagnostic_view': {'display_question_id': 'Q01'},
            'mechanism_fault': {'code': 'generation', 'stage': '生成', 'subtype': None, 'reason': '保存的生成错误'}}


def test_agent_allows_high_excludes_max_from_proposals_and_prompt():
    proposals = [{'id': 'A', 'config_diff': {'generation_thinking': 'high'}}]
    validate_round_contract(proposals, rules.BASELINE, [], labels=['A'])
    proposals[0]['config_diff']['generation_thinking'] = 'max'
    with pytest.raises(ValueError, match='generation_thinking'):
        validate_round_contract(proposals, rules.BASELINE, [], labels=['A'])
    with pytest.raises(ValueError, match='generation_thinking'):
        validate_d_refinement({'proposed_config_diff': {'generation_thinking': 'max'}},
                              {'config': rules.BASELINE}, [], rules.BASELINE, {})
    _, prompt = build_agent_prompt([], rules.BASELINE, [], [], ['A'])
    assert prompt['allowed_parameter_values']['generation_thinking']['allowed'] == ['off', 'low', 'high']
    assert 'max' in rules.PIPELINE_VALUES['generation_thinking']
    rows = [{'base_id': 'Baseline', 'question_id': 'Q01', 'status': '修好',
             'changes': {'generation_thinking': level}, 'candidate_id': 'probe', 'candidate_run_id': 'diag',
             'source': '生成诊断'} for level in ('high', 'max')]
    opportunities = round_opportunities([generation_target()], {'id': 'Baseline', 'changes': {}},
                                        rules.BASELINE, [], {}, rows, [])
    assert [option['changes'] for option in opportunities['Q01']['available']] == [{'generation_thinking': 'high'}]


def test_continuous_launch_checks_production_two_bad_cases_and_preview(setup):
    env, preview = setup
    store = env.store
    with pytest.raises(ValueError, match='少于 5'):
        store.create_experiment(env.base)
    experiment = store.create_experiment(env.base, mode='continuous')
    assert store.experiment(experiment)['result']['mode'] == 'continuous'
    with store.connection() as db:
        db.execute("UPDATE production_versions SET config_json=? WHERE id='A'", (json.dumps(rules.BASELINE),))
    with pytest.raises(ValueError, match='生产版本'):
        store.create_experiment(env.base, mode='continuous')
    with store.connection() as db:
        db.execute("UPDATE production_versions SET config_json=? WHERE id='A'",
                   (json.dumps({**rules.BASELINE, 'candidate_k': 24, 'top_k': 6}),))
    preview.unlink()
    with pytest.raises(ValueError, match='检索预演'):
        store.create_experiment(env.base, mode='continuous')


def test_probe_saves_independent_trials_and_unlocks_same_base_only(setup):
    from app.generation_probe import run_probe
    from app.telemetry import record_usage

    env, _ = setup
    exp = env.store.create_experiment(env.base, mode='continuous')
    _, _, _, _, token = env.store.claim_agent_generation(env.base, experiment_id=exp)
    old_ledger = env.store.experiment(exp)['result']['parameter_effect_ledger']
    change = {'generation_thinking': 'high'}
    target = generation_target()

    def decision(changes, ledger, base='Baseline'):
        return validate_mechanism({'config_diff': changes}, [target], base, {}, ledger)[0]['decision']

    assert decision(change, []) == '拒绝'

    def answer(question, config, *, saved_trace):
        assert config['candidate_k'] == 24 and config['top_k'] == 6
        assert config['generation_thinking'] == 'high'
        assert saved_trace['final'][0]['content'] == '原样本'
        record_usage({'provider': 'fixture', 'status': 'ok', 'total_tokens': 8})
        return {'answer': question}

    env.answer.side_effect = answer
    env.responses = {'Q01': [scored(True, '回答一'), scored(False, '回答二'), scored(True, '回答三')],
                     'Q03': [scored(False, f'保护题{i}') for i in range(3)]}
    [diagnostic] = run_probe(env.store, env.runner, exp, env.base, [change], ['Q01', 'Q03'])
    env.store.save_agent_round(exp, [], {'parameter_effect_ledger': old_ledger}, generation_token=token)
    rows = env.store.experiment(exp)['result']['parameter_effect_ledger']['current']
    assert rows[0] == {'candidate_id': f"PROBE-{diagnostic['id']}-1", 'candidate_run_id': diagnostic['id'],
                       'base_id': 'Baseline', 'question_id': 'Q01', 'changes': change, 'status': '修好',
                       'final_added': None, 'final_lost': None, 'source': '生成诊断',
                       'confidence': '生成诊断，3 份多数，未经全量 Sandbox'}
    assert rows[1]['status'] == '弄坏'
    assert decision(change, rows) == '放行'
    assert decision(change, rows, 'other') == '拒绝'
    assert decision({'generation_thinking': 'low'}, rows) == '拒绝'
    assert env.store.job_checkpoints(diagnostic['id'])['generation_probe']['questions'] == diagnostic['questions']
    trials = diagnostic['questions'][0]['trials']
    assert [t['answer'] for t in trials] == ['回答一', '回答二', '回答三']
    assert [t['judge_result']['reason'] for t in trials] == ['回答一', '回答二', '回答三']
    assert all(t['latency_ms'] == 1000 and t['usage'][0]['total_tokens'] == 8 for t in trials)
    assert len({t['id'] for t in trials}) == 3


def test_probe_does_not_create_candidate_consume_sandbox_budget_or_run_regression(setup, monkeypatch):
    from app.generation_probe import run_probe

    env, _ = setup
    exp = env.store.create_experiment(env.base, mode='continuous')
    env.store.save_candidate(exp, 'A', {**rules.BASELINE, 'generation_thinking': 'low'},
                             {'candidate_label': 'A', 'round': 1})
    before = env.store.experiment(exp)
    recommendation = env.store.recommendation(exp)
    no_regression = Mock(side_effect=AssertionError('生成诊断不得运行 Regression'))
    for invalid in ({'top_k': 6}, {'generation_thinking': 'max'}):
        with pytest.raises(ValueError):
            run_probe(env.store, env.runner, exp, env.base, [{'generation_thinking': 'low'}, invalid], ['Q01'])
    wrong_base = Mock()
    with pytest.raises(ValueError):
        run_probe(env.store, wrong_base, exp, env.base, [{'generation_thinking': 'low'}], ['Q01'], base_key='other')
    wrong_base.diagnostic_retest.assert_not_called()

    env.answer.side_effect = lambda question, config, **kwargs: {'answer': question}
    env.responses = {'Q01': [scored(False) for _ in range(3)]}
    with monkeypatch.context() as patch:
        patch.setattr('app.governance.evaluate_regression', no_regression)
        [diagnostic] = run_probe(env.store, env.runner, exp, env.base, [{'generation_thinking': 'low'}], ['Q01'])
    after = env.store.experiment(exp)
    assert after['candidates'] == before['candidates']
    assert after['evaluation_budget'] == before['evaluation_budget']
    assert env.store.recommendation(exp) == recommendation
    assert env.store.evaluation_run(diagnostic['id']) is None
    no_regression.assert_not_called()


def test_historical_qualifications_and_recommendations_stay_readable(setup):
    env, _ = setup
    store = env.store
    for label, version in [('E2', '2026-11-20b'), ('E3', '2026-11-20b'), ('E4', '2026-11-24')]:
        experiment = f'EXP-{label}'
        candidate = f'{experiment}-A'
        versioned = {'verdict_version': version} if label == 'E4' else {}
        qualification = {'rule_version': version, 'qualified': True}
        recommendation = {'status': 'Recommended', 'recommended_candidate': candidate}
        with store.connection() as db:
            db.execute("INSERT INTO experiments VALUES (?, ?, 'completed', ?, 'fixture')",
                       (experiment, env.base, json.dumps(versioned)))
            db.execute("INSERT INTO recommendations VALUES (?, ?, 'Recommended', ?, 'fixture')",
                       (experiment, candidate, json.dumps(recommendation)))
        store.save_candidate(experiment, 'A', {**rules.BASELINE, 'generation_thinking': 'max'},
                             {'candidate_label': 'A', 'round': 1})
        store.finish_candidate(candidate, 'evaluated', {**versioned, 'qualification': qualification,
            **({'qualification_reassessment': {'qualified': False}} if label == 'E4' else {})})
        saved = store.experiment(experiment)
        assert saved['candidates'][0]['result']['qualification'] == qualification
        assert saved['candidates'][0]['config']['generation_thinking'] == 'max'
        assert store.recommendation(experiment)['result'] == recommendation
        if label == 'E4':
            assert verdict.uses_final(saved['result'])


def test_d_probe_facts_require_winner_and_remaining_question(setup):
    from app.generation_probe import winner_probe_evidence

    env, _ = setup
    change = {'generation_thinking': 'high'}
    common = {'source': '生成诊断', 'status': '修好', 'question_id': 'Q01', 'changes': change}
    rows = [{**common, 'base_id': 'Baseline'}, {**common, 'base_id': 'Winner', 'question_id': 'Q03'},
            {**common, 'base_id': 'Winner', 'status': '弄坏'}, {**common, 'base_id': 'Winner'}]
    assert winner_probe_evidence(rows, 'Winner', [{'question_id': 'Q01'}]) == [rows[-1]]
