import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app import verdict
from app.workflow_engine import (
    E7_AUTHORIZATION, E7_PRODUCTION, CheckpointedRetest, WorkflowEngine, compare_production_retest,
)

from test_task118a_verdict import OfflineEvaluation, scored
from test_task120a2_layered import saved_runs


def test_final_retest_uses_same_frozen_questions_for_all_three_schemes(tmp_path, monkeypatch):
    cases = {'Q01': scored(False), 'Q02': scored(True), 'Q03': scored(True),
             'Q04': scored(True, category='negative', subtype='safety_critical')}
    env = OfflineEvaluation(tmp_path, monkeypatch, cases)
    experiment = 'EXP-test'
    baseline = env.baseline
    prod_run = {'id': 'EVAL-online', 'status': 'completed', 'config': {**baseline['config'], 'top_k': 5},
                'judge': baseline['judge'], 'dataset_snapshot_json': baseline['dataset_snapshot_json']}
    production = {'id': 'production-fixture', 'evaluation_run_id': prod_run['id'],
                  'config': prod_run['config'], 'snapshot': {
                      'evaluation_identity': baseline['judge']['evaluation_identity'],
                      'generation_model': baseline['judge']['model'],
                      'knowledge_identity': env.snapshot['corpus_fingerprint'],
                  }}
    candidate = {'id': 'candidate', 'reasoning': {}, 'result': {'evaluation_run_id': 'EVAL-e7'}}
    runtime = SimpleNamespace(model=baseline['judge']['model'])
    engine = WorkflowEngine(env.store, runtime, experiment)
    engine.save = Mock()
    engine.check_stop = Mock()
    monkeypatch.setattr(env.store, 'evaluation_run', lambda run_id: prod_run)
    monkeypatch.setattr(verdict, 'final_verdicts', lambda run_id, **_: {
        **dict.fromkeys(cases, True),
        {'EVAL-online': 'Q02', 'EVAL-e7': 'Q03'}.get(run_id, 'Q01'): False,
    })

    def retest(self, run_id, question_ids, *, repetitions=3):
        assert repetitions == 3
        question, = question_ids
        calls.append((run_id, question))
        return {'questions': [{'display_question_id': question, 'passed': 3, 'unknown': 0, 'risk': False}]}

    calls = []
    monkeypatch.setattr(CheckpointedRetest, 'diagnostic_retest', retest)
    _, _, summary = engine.final_retest({'result': {}}, baseline, candidate, env.snapshot, 'workflow:',
                                         production=production, resume_blocked=False)
    assert calls == [(source, qid) for source in (env.base, 'EVAL-online', 'EVAL-e7') for qid in cases]
    assert set(summary) == {'baseline', 'production', 'recommendation'}
    saved = env.store.job_checkpoint(experiment, 'workflow:final-retest')
    assert saved['production_version'] == production['id']
    assert saved['protected_questions'] == ['Q04']
    assert json.loads(prod_run['dataset_snapshot_json']) == env.snapshot


@pytest.mark.parametrize('online, challenger, expected', [
    ((0, 3), (3, 3), True),
    ((3, 3), (3, 3), False),
    ((0, 3), (3, 1), False),
])
def test_release_requires_more_passes_and_zero_protected_regression(online, challenger, expected):
    def rows(votes):
        return {qid: {'passed': passed, 'unknown': 0, 'risk': False}
                for qid, passed in zip(('Q01', 'Q02'), votes)}

    summary = {'baseline': rows((0, 3)), 'production': rows(online), 'recommendation': rows(challenger)}
    assert compare_production_retest(summary, ['Q02'])['passed'] is expected


def test_terminal_judge_noise_and_safety_uncertainty_do_not_grant_release():
    ordinary = {'passed': 1, 'unknown': 1, 'risk': False}
    safe = {'passed': 3, 'unknown': 0, 'risk': False}
    summary = {'baseline': {'Q01': ordinary, 'Q02': safe}, 'production': {'Q01': ordinary, 'Q02': safe},
               'recommendation': {'Q01': safe, 'Q02': safe}}
    assert compare_production_retest(summary, ['Q02'])['passed'] is False
    summary['production']['Q01'] = {**ordinary, 'unknown': 0}
    assert compare_production_retest(summary, ['Q02'])['passed'] is True
    summary['recommendation']['Q02'] = {**safe, 'risk': None}
    assert compare_production_retest(summary, ['Q02'])['passed'] is False


@pytest.mark.parametrize('passed', [False, True], ids=['tie-keeps-online', 'strict-improvement-publishes'])
def test_e7_release_uses_three_way_evidence_and_rehearses_before_publish(tmp_path, monkeypatch, passed):
    env = OfflineEvaluation(tmp_path, monkeypatch, {'Q01': scored(True)})
    store = env.store
    engine = WorkflowEngine(store, None, 'EXP-e7')
    active = {'id': E7_PRODUCTION, 'config': {'top_k': 4}, 'snapshot': {}}
    candidate = {'id': 'candidate', 'experiment_id': engine.id, 'config': {'top_k': 6},
                 'result': {'evaluation_run_id': 'EVAL-e7'}}
    engine.save, engine.check_stop = Mock(), Mock()
    engine.experiment = Mock(return_value={'baseline_run_id': env.base})
    engine.release_authorization = Mock(return_value=E7_AUTHORIZATION)
    engine.rollback_index = Mock(return_value='/test/index')
    engine.rehearse_rollback = Mock(return_value={'database': 'explicit_temporary_database', 'status': 'passed'})
    engine.verify_production = Mock()
    monkeypatch.setattr(store, 'require_current_baseline', lambda _: env.baseline)
    monkeypatch.setattr(store, 'recommendation', lambda _: {
        'result': {'status': 'Recommended', 'recommended_candidate': candidate['id']}})
    monkeypatch.setattr(store, 'candidate', lambda _: candidate)
    monkeypatch.setattr(store, 'active_production', lambda: active)
    monkeypatch.setattr(store, 'release_gate_error', lambda _: None)
    monkeypatch.setattr(store, 'evaluation_run', lambda *args, **kwargs: env.baseline)
    monkeypatch.setattr('app.release_view.release_review_view', lambda *_: {'checks': []})
    monkeypatch.setattr('app.workflow_engine.current_paid_run', lambda: SimpleNamespace(identity={'task': '125b'}))

    def retest(*args, production=None, **kwargs):
        assert production == active
        store.save_job_checkpoint(engine.id, 'workflow:final-retest', {'production_comparison': {'passed': passed}})
        return set(), {'Q01'}, {}

    engine.final_retest = retest
    published = {'id': 'production-new'}

    def publish(*args, **kwargs):
        engine.rehearse_rollback.assert_called_once_with(active, candidate)
        assert kwargs['workflow_release'][:2] == (E7_PRODUCTION, 'EVAL-e7')
        return published

    publish_candidate = Mock(side_effect=publish)
    monkeypatch.setattr(store, 'publish_candidate', publish_candidate)
    engine.release()
    receipt = store.job_checkpoint(engine.id, 'workflow:release')
    if passed:
        publish_candidate.assert_called_once()
        engine.verify_production.assert_called_once()
        assert receipt['rollback_rehearsal']['status'] == 'passed'
    else:
        publish_candidate.assert_not_called()
        engine.rehearse_rollback.assert_not_called()
        assert receipt['result'] == 'unchanged' and receipt['version'] == E7_PRODUCTION


def test_e7_saves_exhausted_rule_checks_without_starting_a_second_batch(saved_runs, monkeypatch):
    from app import optimization_cycle
    from app.optimization import ProposalValidationExhausted

    env, _ = saved_runs
    experiment = env.store.create_experiment(env.base)
    generate = Mock(side_effect=ProposalValidationExhausted('实验方案连续校验被拒'))
    monkeypatch.setattr(WorkflowEngine, 'generate_next', generate)
    monkeypatch.setattr('app.paid_run.current_paid_run', lambda: SimpleNamespace(identity={'task': '125b'}))
    state = {}
    terminal = optimization_cycle._run_staged(env.store, None, experiment, state,
        lambda status, phase, error=None: (status, phase, error), Mock(), None, None)
    assert terminal == ('analysis_exhausted', 'analysis', '实验方案连续校验被拒')
    assert state['proposal_generation_failures'][0]['sandbox_budget_used'] == 0
    generate.assert_called_once()
