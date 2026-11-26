"""123b acceptance with frozen fixture runs and a temporary SQLite store."""
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app import rules, verdict
from app.paid_schedule import set_settings
from app.workflow_engine import WorkflowEngine
from test_task118a_verdict import mark_legacy_planning, scored
from test_task120a2_layered import saved_runs


def hypothesis(changes=None, *, kind='retrieval', targets=('Q01',), risks=('Q07',)):
    changes = changes or {'top_k': 6}
    return {'root_cause': '标准证据没有进入最终资料', 'changes': changes,
            'predicted_fixed_question_ids': list(targets), 'predicted_regression_question_ids': list(risks),
            'checks': [{'kind': kind, 'changes': changes, 'target_question_ids': list(targets),
                        'risk_question_ids': list(risks)}]}


def setup(saved_runs):
    env, _ = saved_runs
    set_settings(env.store, False)
    return env, env.store, env.store.create_experiment(env.base)


def test_new_requests_are_bounded_and_legacy_request_is_preserved(saved_runs, tmp_path):
    from app.agent_planning import VERSION

    env, store, experiment = setup(saved_runs)
    _, _, legacy = setup(saved_runs)
    mark_legacy_planning(store, legacy)
    directory = tmp_path / 'retrieval_preview'
    directory.mkdir()
    old_preview = {'baseline_run_id': env.base, 'rules_version': rules.RULES_VERSION,
                   'knowledge_identity': env.snapshot['corpus_fingerprint'],
                   'configs': [{'change': {'top_k': 6}, 'evidence_enters_final': ['Q01'], 'marker': '176 组'}]}
    (directory / f'{env.base}.json').write_text(json.dumps(old_preview))
    proposal = hypothesis()
    calls, phases = [], []

    def retrieve(question, config):
        assert store.job_checkpoint(experiment, 'directed:1')['pre_review_prediction'] == [proposal]
        assert config['top_k'] == 6
        calls.append(question)
        final = [{'chunk_id': 'standard', 'content': '冻结题卷的标准证据原文'}]
        return final, {'generation_allowed': True}, [], {'final': final}, []

    def complete(system, user, **kwargs):
        prompt = json.loads(user)
        phase = prompt.get('planning_stage')
        phases.append(phase)
        if phase == 'hypotheses':
            assert 'retrieval_preview' not in prompt and 'round_opportunities' not in prompt
            return json.dumps({'hypotheses': [proposal]})
        if phase == 'candidates':
            [check] = prompt['directed_checks']
            assert {row['question_id'] for row in check['results']} == {'Q01', 'Q07'}
            assert 'retrieval_preview' not in prompt
        else:
            assert prompt['retrieval_preview']['configs'] == old_preview['configs']
        return json.dumps({'candidates': [], 'insufficient_evidence': '保留底座'})

    runtime = SimpleNamespace(provider=SimpleNamespace(complete=complete), retrieve_context=retrieve)
    result = WorkflowEngine(store, runtime, experiment).generate_next()
    assert result['result']['agent_planning_version'] == VERSION
    plan = result['result']['round_planning']['1']
    assert plan['pre_review_prediction'] == [proposal]
    assert plan['post_review_prediction'] == []
    assert len(calls) == 2
    WorkflowEngine(store, runtime, legacy).generate_next()
    assert phases == ['hypotheses', 'candidates', None]


def test_immutable_prediction_and_cumulative_group_limits(saved_runs):
    from app.agent_planning import DirectedPlanning

    env, store, experiment = setup(saved_runs)
    engine = WorkflowEngine(store, SimpleNamespace(), experiment)
    session = DirectedPlanning(engine, 1, 'Baseline', env.base)
    first = hypothesis()
    session.submit_hypotheses([first])
    session = DirectedPlanning(engine, 1, 'Baseline', env.base)
    with pytest.raises(ValueError, match='不可覆盖'):
        session.submit_hypotheses([hypothesis({'candidate_k': 24})])
    assert session.state['pre_review_prediction'] == [first]
    session.request_checks([hypothesis(change)['checks'][0] for change in (
        {'min_score': 0.1}, {'min_score': 0.2}, {'min_score': 0.3}, {'query_rewrite': True}, {'hyde': True})])
    with pytest.raises(ValueError, match='6 组'):
        session.request_checks([hypothesis({'candidate_k': 24})['checks'][0]])
    assert len(session.state['checks']) == 6
    d = DirectedPlanning(engine, 'D', 'Baseline', env.base)
    d.submit_hypotheses([first])
    with pytest.raises(ValueError, match='2 组'):
        d.request_checks([hypothesis({'min_score': value})['checks'][0] for value in (0.1, 0.2)])
    assert len(d.state['checks']) == 1


def test_resume_keeps_first_prediction_and_reuses_completed_retrieval(saved_runs):
    env, store, experiment = setup(saved_runs)
    first = hypothesis()
    queries = []
    completed_phases = []

    def complete(system, user, **kwargs):
        phase = json.loads(user)['planning_stage']
        completed_phases.append(phase)
        return json.dumps({'hypotheses': [first]} if phase == 'hypotheses' else {
            'candidates': [], 'insufficient_evidence': '没有可提交的方案'})

    def retrieve(question, config):
        queries.append(question)
        if queries == ['Q01', 'Q07']:
            raise InterruptedError('夹具中断')
        return [], {'generation_allowed': True}, [], {'final': []}, []

    runtime = SimpleNamespace(provider=SimpleNamespace(complete=complete), retrieve_context=retrieve)
    engine = WorkflowEngine(store, runtime, experiment)
    with pytest.raises(InterruptedError, match='夹具中断'):
        engine.generate_next()
    result = engine.generate_next()
    assert queries == ['Q01', 'Q07', 'Q07']
    assert completed_phases == ['hypotheses', 'candidates']
    assert result['result']['round_planning']['1']['pre_review_prediction'] == [first]


def test_generation_runs_automatically_and_reserves_three_samples_per_question(saved_runs, monkeypatch):
    from app.agent_planning import DirectedPlanning
    from app.evaluation import EvaluationRunner

    env, store, experiment = setup(saved_runs)
    proposal = hypothesis({'generation_thinking': 'low'}, kind='generation', targets=('Q01', 'Q02'))
    answer = Mock(side_effect=lambda question, config, saved_trace: {'answer': question})
    judge = Mock(side_effect=lambda item, execution: scored(True, item['id']))
    monkeypatch.setattr(EvaluationRunner, 'score_execution', lambda self, *args: judge(*args))

    def complete(system, user, **kwargs):
        prompt = json.loads(user)
        if prompt['planning_stage'] == 'hypotheses':
            return json.dumps({'hypotheses': [proposal]})
        assert prompt['directed_checks'][0]['results'][0]['passed'] == 3
        if len(prompt['directed_checks']) == 1:
            return json.dumps({'checks': [{**proposal['checks'][0], 'target_question_ids': ['Q02', 'Q03']}]})
        assert prompt['generation_samples_remaining'] == 24
        return json.dumps({'candidates': [], 'insufficient_evidence': '验证完成'})

    runtime = SimpleNamespace(model='fixture', answer=answer, provider=SimpleNamespace(complete=complete))
    engine = WorkflowEngine(store, runtime, experiment)
    engine.generate_next()
    assert answer.call_count == judge.call_count == 12
    assert all(call.args[1]['generation_thinking'] == 'low' and call.kwargs['saved_trace']['final']
               for call in answer.call_args_list)
    assert store.experiment(experiment)['evaluation_budget']['used'] == 0
    session = DirectedPlanning(engine, 2, 'Baseline', env.base)
    session.submit_hypotheses([])
    group = hypothesis({'generation_thinking': 'low'}, kind='generation',
                       targets=('Q01', 'Q02', 'Q03'))['checks'][0]
    session.request_checks([group, {**group, 'changes': {'generation_thinking': 'high'}},
                            {**group, 'changes': {'prompt_strategy': rules.SAFE}}])
    with pytest.raises(ValueError, match='36 份'):
        session.request_checks([{**group, 'changes': {'prompt_strategy': rules.LOOSER}}])


@pytest.mark.parametrize(('same_request', 'kind'), [(True, 'generation'), (False, 'generation'), (True, 'retrieval')])
def test_sandbox_candidate_requires_a_real_effect(saved_runs, monkeypatch, same_request, kind):
    from app.evaluation import EvaluationRunner

    env, store, experiment = setup(saved_runs)
    before = verdict.records(store, env.base)
    for record in before.values():
        for sample in record['samples']:
            sample['generation_request_sha256'] = 'same-request'
    with store.connection() as db:
        db.execute("UPDATE job_checkpoints SET checkpoint_json=? WHERE run_id=? AND question_id=?",
                   (json.dumps(before), env.base, verdict.RECORDS_KEY))
    by_text = {q['question']: q['id'] for q in env.snapshot['questions']}

    def retrieve(question, config):
        final = before[by_text[question]]['samples'][0]['final_context']
        return final, {'generation_allowed': True}, [], {'final': final}, []

    def faults(_baseline, _cases, rows, **kwargs):
        return {row['question_id']: {'code': 'generation', 'subtype': None, 'reason': '夹具生成故障'}
                for row in rows}

    monkeypatch.setattr('app.agent_mechanism.faults_for_cases', faults)
    monkeypatch.setattr(EvaluationRunner, 'score_execution', lambda self, item, execution: scored(True, item['id']))
    changes = {'generation_thinking': 'low'} if kind == 'generation' else {'top_k': 6}
    request = hypothesis(changes, kind=kind)
    phases = []

    def complete(system, user, **kwargs):
        prompt = json.loads(user)
        phases.append(prompt['planning_stage'])
        if prompt['planning_stage'] == 'hypotheses':
            return json.dumps({'hypotheses': [request]})
        if 'validation_rejection' in prompt:
            assert '该参数没有起作用' in prompt['validation_rejection'], prompt['validation_rejection']
            assert prompt['no_effect'][0]['matching_runs'] == [env.base]
            return json.dumps({'candidates': [], 'insufficient_evidence': '该参数没有起作用'})
        conclusion = {'id': 'C1', 'conclusion': '生成诊断多数判对'}
        return json.dumps({
            'prior_round_review': {'summary': '无', 'plans': [], 'conclusions': [conclusion],
                                   'baseline_remaining_assessment': '当前仍有错题'},
            'bad_case_summary': {'groups': prompt['bad_case_groups'], 'focus': '生成', 'conclusions': [conclusion]},
            'hypothesis_plan': {'hypothesis': '推理改善回答', 'test_candidate': 'A',
                                'if_true': {'action': 'stop'}, 'if_false': {'action': 'stop'}},
            'candidates': [{'id': 'A', 'config_diff': changes, 'target_bad_cases': ['Q01'],
                            'hypothesis': '推理改善回答', 'why': '生成多数结果', 'risk': '可能退步',
                            'direction': '生成策略', 'expected_improvement': '修好 Q01',
                            'bad_case_conclusion_ids': ['C1'], 'review_conclusion_ids': ['C1'],
                            'predicted_fixed_question_ids': ['Q01'],
                            'adjustments': [{'parameter': 'generation_thinking', 'candidate_value': 'low',
                                             'baseline_value': 'off', 'expected_impact': '改善 Q01'}],
                            'risks': [{'question_ids': ['Q07'], 'metric': None, 'reason': '可能退步'}]}],
        })

    runtime = SimpleNamespace(model='fixture', answer=lambda q, config, saved_trace: {'answer': q},
        provider=SimpleNamespace(complete=complete), retrieve_context=retrieve,
        generation_request_fingerprint=lambda *args: 'same-request' if same_request else 'new-request')
    generated = WorkflowEngine(store, runtime, experiment).generate_next()
    assert generated['evaluation_budget']['used'] == 0
    post = generated['result']['round_planning']['1']['post_review_prediction']
    if same_request:
        assert generated['candidates'] == post == []
        assert phases == ['hypotheses', 'candidates', 'candidates']
    else:
        [candidate] = generated['candidates']
        assert candidate['status'] == 'generated'
        assert post[0]['candidate_id'] == candidate['id']
        assert post[0]['predicted_fixed_question_ids'] == ['Q01']
        assert phases == ['hypotheses', 'candidates']


def test_round_review_and_light_api_publish_actual_metrics(saved_runs, monkeypatch):
    from fastapi.testclient import TestClient
    from app import main
    from app.agent_strategy import conclude_round

    env, store, experiment = setup(saved_runs)
    cid, _ = saved_runs[1](experiment, 'A', 1, {'Q01', 'Q03'}, top_k=6)
    prediction = hypothesis(targets=('Q01', 'Q02'))
    with store.connection() as db:
        db.execute("UPDATE experiments SET result_json=json_set(result_json,'$.round_planning',json(?)) WHERE id=?",
                   (json.dumps({'1': {'base_run_id': env.base, 'pre_review_prediction': [prediction],
                                      'post_review_prediction': []}}), experiment))

    def complete(system, user, **kwargs):
        prompt = json.loads(user)
        assert prompt['prediction_metrics']['pre_review_precision']['rate'] == 0.5
        return json.dumps({'plans': [{'candidate_id': cid, 'unmatched_reason': '其余题未修好',
                                      'parameter_assessment': '待验证', 'evidence_reason': '依据冻结逐题判定',
                                      'conclusion': '核对两道已修复题'}], 'lessons': ['关注未修复题']})

    saved = conclude_round(store, SimpleNamespace(provider=SimpleNamespace(complete=complete)), experiment)
    assert saved['prediction_metrics']['repair_coverage'] == {'hits': 1, 'total': 2, 'rate': 0.5}
    assert saved['prediction_metrics']['risk_hit_rate']['rate'] is None
    assert saved['review']['prediction_metrics'] == saved['prediction_metrics']
    monkeypatch.setattr(main, 'store', store)
    response = TestClient(main.app).get(f'/api/experiments/{experiment}?light=true')
    assert response.status_code == 200
    assert response.json()['result']['round_conclusions']['1']['prediction_metrics'] == saved['prediction_metrics']


def test_composite_uses_its_own_directed_checks_without_legacy_preview(saved_runs, monkeypatch):
    env, store, experiment = setup(saved_runs)
    save = saved_runs[1]
    winner, _ = save(experiment, 'A', 1, {'Q01', 'Q02'}, top_k=6)
    source, _ = save(experiment, 'B', 4, {'Q03'}, candidate_k=24)
    store.confirm_experiment_report(experiment, winner, '用户')
    change = {'candidate_k': 24}
    request = hypothesis(change, targets=('Q03',), risks=('Q01',))
    phases = []

    def retrieve(question, config):
        assert config['top_k'] == 6 and config['candidate_k'] == 24
        final = [{'chunk_id': 'standard', 'content': '冻结题卷的标准证据原文'}]
        return final, {'generation_allowed': True}, [], {'final': final}, []

    def complete(system, user, **kwargs):
        prompt = json.loads(user)
        phases.append(prompt['planning_stage'])
        assert 'retrieval_preview' not in prompt
        if prompt['planning_stage'] == 'hypotheses':
            assert prompt['current_base']['id'] == winner
            assert prompt['check_limit'] == 2
            return json.dumps({'hypotheses': [request]})
        assert prompt['remaining_checks'] == 1
        assert len(prompt['directed_checks'][0]['results']) == 2
        return json.dumps({
            'should_generate_d': True, 'proposed_config_diff': change,
            'combination_mode': 'partial_fusion', 'mode_reason': '取用互补的合格方案',
            'root_cause_alignment': '复查召回', 'complementary_capabilities': '两组已保存结果互补',
            'expected_improvement': '核对组合效果', 'risks': '可能回退 Q01', 'explanation': '试验组合',
            'hypothesis': '合并可提供额外证据', 'root_cause': '召回遗漏',
            'intervention_direction': 'candidate_recall', 'evidence_assertions': [],
            'bad_case_summary': {'groups': prompt['bad_case_groups'], 'focus': '召回',
                                 'conclusions': [{'id': 'B1', 'conclusion': '核对召回'}]},
            'bad_case_conclusion_ids': ['B1'], 'predicted_regression_question_ids': ['Q01'],
            'changes': [{'parameter': 'candidate_k', 'source_type': 'partial', 'source_candidates': [source],
                         'reason': '组合核验', 'target_question_ids': [], 'evidence_basis': '本实验方案 B',
                         'expected_fixed_count': 0, 'possible_broken_count': 1,
                         'side_effect_check': {'historical_effects': '未观察到', 'protected_overlap': [],
                                               'winner_fixed_risk': '核对 Q01', 'gate_risk': '观察耗时',
                                               'mitigation': '复核最终判定', 'same_premise_evidence': '未观察到',
                                               'different_premise_evidence': '方案 B 的底座不同',
                                               'risk_checklist': '核对 Q01'}}],
        })

    monkeypatch.setattr('app.optimization.load_retrieval_preview', Mock(side_effect=AssertionError('legacy preview')))
    engine = WorkflowEngine(store, SimpleNamespace(provider=SimpleNamespace(complete=complete),
                                                   retrieve_context=retrieve), experiment)
    d = engine.generate_composite()
    assert d['status'] == 'generated', d.get('reason')
    assert phases == ['hypotheses', 'candidates']
    plan = store.experiment(experiment)['result']['round_planning']['D']
    assert plan['pre_review_prediction'] == [request]
    assert plan['post_review_prediction'][0]['predicted_regression_question_ids'] == ['Q01']


def test_prediction_metrics_use_actual_finals_and_show_unknown_denominators():
    from app.agent_planning import prediction_metrics

    hypotheses = [hypothesis(targets=('Q01', 'Q02'), risks=('Q04',)),
                  hypothesis({'candidate_k': 24}, targets=('Q02', 'Q06'), risks=('Q04',))]
    result = prediction_metrics(hypotheses, [{'fixed': ['Q01', 'Q03'], 'regressed': ['Q04', 'Q05']}])
    assert result['pre_review_precision'] == {'hits': 1, 'total': 3, 'rate': 1 / 3}
    assert result['repair_coverage'] == {'hits': 1, 'total': 2, 'rate': 0.5}
    assert result['risk_hit_rate'] == {'hits': 1, 'total': 2, 'rate': 0.5}
    assert prediction_metrics([], [])['pre_review_precision']['rate'] is None
