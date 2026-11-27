from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import json

import pytest

from app import verdict
from app.evaluation import EvaluationRunner
from app.governance import GovernanceStore
from app.workflow_engine import WorkflowEngine
from test_task118a_verdict import scored
from test_task120a2_layered import saved_runs


@pytest.mark.parametrize('task', ['124c', '125b'])
def test_m2_sandbox_reuses_exhausted_judge_and_adopts_two_votes(tmp_path, monkeypatch, task):
    store = GovernanceStore(tmp_path / 'sandbox.db')
    runner = EvaluationRunner(store, None)
    monkeypatch.setattr('app.request_reuse.experiment_scope', lambda *_: nullcontext())
    monkeypatch.setattr('app.paid_run.current_paid_run', lambda: SimpleNamespace(identity={'task': task}))
    failure = {'phase': 'judge', 'status': 'error', 'error_type': 'ProviderInvalidResponse',
               'provider_error': {'failure_class': 'bounded_retry_stopped'},
               'retryable': False, 'request_execution_unknown': False, 'error': 'invalid fact'}
    item = {'id': 'q', 'raw': {}}
    case = {'question_id': 'q', **scored(True)}
    missing = {'execution': {'answer': 'saved answer'}, 'attempts': [failure]}
    third = verdict.make_sample(case, item['raw'], 3, 'recheck', 'third')
    monkeypatch.setattr(runner, '_verdict_trial', lambda _, __, trial, *args, **kw: (
        third if trial.get('scored_result') else pytest.fail('saved failed slot was retried')))
    rows = runner._collect_verdicts({'id': 'sandbox', 'config': {}}, [item], [case],
        {'q': {'verdict_trials': {'2': missing, '3': {'scored_result': case}}}},
        lambda _: None, lambda: None, experiment_id='EXP-1', baseline={'q': False})
    assert rows['q']['final_passed'] is True
    assert rows['q']['samples'][1]['answer'] == 'saved answer'


def test_e6_rollback_rehearsal_writes_only_disposable_store(tmp_path, monkeypatch):
    from app import corpus

    store = GovernanceStore(tmp_path / 'formal.db')
    workflow = WorkflowEngine(store, None, 'EXP-test')
    active = store.active_production()
    active['snapshot'].update(knowledge_identity={'id': 'current'}, embedding_model='current-embedding')
    index = tmp_path / 'index'
    index.mkdir()
    (index / 'manifest.json').write_text(json.dumps({'knowledge_identity': {'id': 'current'}}))
    (index / 'faiss.index').touch()
    monkeypatch.setattr(corpus, 'INDEX_DIR', index)
    monkeypatch.setattr(corpus.CorpusStore, 'index_info', lambda self: {
        'embedding_model': 'current-embedding', 'knowledge_identity': {'id': 'current'}})
    seen = []
    original_rollback = GovernanceStore.rollback_to

    def rollback(isolated, target, actor):
        assert isolated.database_path != store.database_path
        assert isolated.active_production()['id'] == 'rollback-rehearsal'
        assert target == active['id']
        seen.append(Path(isolated.database_path))
        return original_rollback(isolated, target, actor)

    monkeypatch.setattr(GovernanceStore, 'rollback_to', rollback)
    result = workflow.rehearse_rollback(active, {'config': {'top_k': 5}})
    assert result['restored_version'] == active['id']
    assert seen and not seen[0].exists()
    assert store.active_production()['id'] == active['id']
    assert 'knowledge_identity' not in store.active_production()['snapshot']


@pytest.fixture
def bound_baseline(tmp_path, monkeypatch):
    from app.evaluation_snapshot import run_snapshot
    from app.paid_schedule import set_settings
    from test_task118a_verdict import OfflineEvaluation

    identity = {'pipeline_version_id': 'M2', 'sources': [{'id': 'M2'}]}
    manifest = {'sources': identity['sources'], 'knowledge_identity': identity}
    cases = {f'Q{i:02}': scored(i > 6, 'evidence') for i in range(1, 8)}
    for case in cases.values():
        case['programmatic_metrics']['retrieval_trace']['corpus_fingerprint'] = identity
    env = OfflineEvaluation(tmp_path, monkeypatch, cases, manifest=manifest, evidence=[
        {'source_chunk_ids': ['evidence'], 'quote': 'evidence'}])
    config = {**env.baseline['config'], 'knowledge_identity': identity}
    judge = {**env.baseline['judge'], 'run_snapshot': run_snapshot(env.snapshot, config, env.baseline['judge'])}
    with env.store.connection() as db:
        db.execute('UPDATE evaluation_runs SET config_json=?, judge_json=? WHERE id=?',
                   (json.dumps(config), json.dumps(judge), env.base))
    env.stable_baseline()
    set_settings(env.store, False)
    return env, env.store.create_experiment(env.base), identity


@pytest.mark.parametrize('number', [1, 'D'])
def test_directed_retrieval_binds_frozen_index(bound_baseline, number):
    from unittest.mock import Mock

    env, experiment, frozen = bound_baseline
    trace = {'final': [], 'corpus_fingerprint': frozen}
    runtime = SimpleNamespace(retrieve_context=Mock(return_value=([], {}, [], trace, [])))
    planning = WorkflowEngine(env.store, runtime, experiment).directed_planning(number, 'Baseline', env.base)
    assert planning._retrieve('Q01', planning._config({'top_k': 6}))['trace'] == trace
    assert runtime.retrieve_context.call_args.args[1]['knowledge_identity'] == frozen


@pytest.mark.parametrize('fault', ['missing_binding', 'wrong_binding', 'wrong_trace', 'missing_trace', 'wrong_checkpoint'])
def test_directed_identity_fault_blocks_before_planning_conclusion(bound_baseline, fault):
    from unittest.mock import Mock

    from app import rules
    from app.providers import ProviderIdentityError

    env, experiment, frozen = bound_baseline
    trace = {'final': [], 'corpus_fingerprint': [{'id': 'legacy'}]}
    runtime = SimpleNamespace(retrieve_context=Mock(return_value=([], {}, [], trace, [])),
                              generation_request_fingerprint=Mock(return_value='fixture-request'))
    engine = WorkflowEngine(env.store, runtime, experiment)
    if fault in {'missing_binding', 'wrong_binding'}:
        config = dict(env.store.evaluation_run(env.base)['config'])
        config.pop('knowledge_identity')
        if fault == 'wrong_binding':
            config['knowledge_identity'] = {'pipeline_version_id': 'wrong'}
        with env.store.connection() as db:
            db.execute('UPDATE evaluation_runs SET config_json=? WHERE id=?', (json.dumps(config), env.base))
    if fault == 'missing_trace':
        trace.pop('corpus_fingerprint')
    key = None
    with pytest.raises(ProviderIdentityError, match='知识库身份'):
        planning = engine.directed_planning(1, 'Baseline', env.base)
        config = planning._config({'top_k': 6})
        effective = {k: v for k, v in config.items() if k != 'hybrid_alpha' or config['hybrid_search']}
        key = planning.key + ':retrieval:' + rules.canonical_hash([effective, 'Q01'])
        if fault == 'wrong_checkpoint':
            env.store.save_job_checkpoint(experiment, key, {'retrieval': {'trace': trace, 'request': None}})
        planning._retrieve('Q01', config)
    assert runtime.retrieve_context.call_count == int(fault in {'wrong_trace', 'missing_trace'})
    runtime.generation_request_fingerprint.assert_not_called()
    if key and fault != 'wrong_checkpoint':
        assert 'retrieval' not in env.store.job_checkpoint(experiment, key)
    assert not env.store.experiment(experiment)['result'].get('decision_stop')


@pytest.mark.parametrize('saved_trace', [False, True], ids=['fresh-retrieval', 'saved-final'])
def test_bound_answer_rejects_wrong_fingerprint_before_generation(monkeypatch, saved_trace):
    from unittest.mock import Mock

    from app.ai_service import AiService
    from app.providers import ProviderIdentityError

    runtime = object.__new__(AiService)
    trace = {'final': [], 'corpus_fingerprint': [{'id': 'legacy'}]}
    monkeypatch.setattr(runtime, 'retrieve_context', Mock(return_value=([], {}, [], trace, [])))
    monkeypatch.setattr(runtime, '_generate', Mock())
    with pytest.raises(ProviderIdentityError, match='知识库身份'):
        runtime.answer('fixture', {'knowledge_identity': {'pipeline_version_id': 'M2'}},
                       saved_trace=trace if saved_trace else None)
    runtime._generate.assert_not_called()


def test_sandbox_and_final_retest_keep_baseline_identity(bound_baseline, monkeypatch):
    from unittest.mock import Mock

    from app.workflow_engine import CheckpointedRetest

    env, experiment, frozen = bound_baseline
    store = env.store
    baseline = store.evaluation_run(env.base)

    def answer(question, config, **kwargs):
        assert config['knowledge_identity'] == frozen
        if 'saved_trace' in kwargs:
            assert kwargs['saved_trace']['corpus_fingerprint'] == frozen
        return {'answer': question, 'retrieval_trace': {'final': [], 'corpus_fingerprint': frozen}}

    runtime = SimpleNamespace(model='fixture', answer=Mock(side_effect=answer))
    def score(self, item, execution, **kwargs):
        case = scored(True)
        case['programmatic_metrics']['retrieval_trace'] = execution['retrieval_trace']
        return case

    monkeypatch.setattr(EvaluationRunner, 'score_execution', score)
    runner = EvaluationRunner(store, runtime)
    config = {k: v for k, v in baseline['config'].items() if k not in {'knowledge_identity', 'run_target'}}
    store.save_candidate(experiment, 'R1-A', {**config, 'top_k': 6},
                         {'round': 1, 'candidate_label': 'A', 'changed_parameters': {'top_k': 6}})
    args = runner.start_candidate(experiment + '-R1-A')
    assert args[2]['knowledge_identity'] == frozen
    runner.execute_candidate(*args)
    assert store.evaluation_run(args[0])['result']['evaluation_complete'] is True
    assert runtime.answer.call_count >= len(env.snapshot['question_ids'])
    runtime.answer.reset_mock()
    diagnostic = CheckpointedRetest(WorkflowEngine(store, runtime, experiment), 'workflow:')
    diagnostic.diagnostic_retest(env.base, ['Q01'], repetitions=1)
    diagnostic.diagnostic_retest(args[0], ['Q01'], repetitions=1)
    diagnostic.diagnostic_retest(env.base, ['Q01'], repetitions=1, config_override={'generation_thinking': 'low'})
    assert runtime.answer.call_count == 3


def test_scheme_preview_requires_frozen_candidate_binding(bound_baseline, monkeypatch):
    from unittest.mock import Mock

    from fastapi.testclient import TestClient
    from app import main

    env, experiment, frozen = bound_baseline
    baseline = env.store.evaluation_run(env.base)
    config = {k: v for k, v in baseline['config'].items() if k not in {'knowledge_identity', 'run_target'}}
    env.store.save_candidate(experiment, 'R1-A', {**config, 'top_k': 6}, {'round': 1, 'candidate_label': 'A'})
    candidate = experiment + '-R1-A'
    answer = Mock(return_value={'answer': 'fixture', 'retrieval': [],
                                'retrieval_trace': {'corpus_fingerprint': frozen}})
    monkeypatch.setattr(main, 'store', env.store)
    monkeypatch.setattr(main, 'ai_service', SimpleNamespace(answer=answer))
    client = TestClient(main.app)

    def preview(scheme):
        return client.post('/api/preview/scheme', json={'scheme_id': scheme, 'question': 'fixture'},
                           headers={'Origin': 'http://127.0.0.1:5174'})

    assert preview(candidate).status_code == 409
    answer.assert_not_called()
    run = env.store.create_evaluation_run(env.snapshot,
        {**config, 'knowledge_identity': frozen, 'run_target': 'sandbox_candidate', 'candidate_id': candidate},
        baseline['judge'])
    env.store.finish_candidate(candidate, 'evaluated', {'evaluation_run_id': run})
    assert preview(candidate).status_code == 200
    assert answer.call_args.args[1]['knowledge_identity'] == frozen


def test_directed_revision_identity_fault_skips_proposal_validation_retry(bound_baseline):
    from unittest.mock import Mock

    from test_task123b_directed_planning import hypothesis

    env, experiment, _ = bound_baseline
    check = hypothesis(risks=())['checks'][0]
    provider = SimpleNamespace(complete=Mock(side_effect=[
        json.dumps({'hypotheses': []}), json.dumps({'checks': [check]})]))
    trace = {'final': [], 'corpus_fingerprint': [{'id': 'legacy'}]}
    runtime = SimpleNamespace(provider=provider, retrieve_context=Mock(return_value=([], {}, [], trace, [])))
    with pytest.raises(ValueError, match='知识库身份'):
        WorkflowEngine(env.store, runtime, experiment).generate_next()
    assert provider.complete.call_count == 2
    runtime.retrieve_context.assert_called_once()
    saved = env.store.experiment(experiment)
    assert not saved['candidates']
    assert not saved['result'].get('decision_stop')


@pytest.mark.parametrize('finish', ['stopped', 'finish_winner', 'composite'])
def test_zero_candidate_round_is_saved_and_dispatched_once(saved_runs, monkeypatch, finish):
    from unittest.mock import Mock

    from app import optimization_cycle

    env, save_candidate = saved_runs
    store = env.store
    experiment = store.create_experiment(env.base)
    winner = save_candidate(experiment, 'A', 1, {'Q01', 'Q02'}, top_k=6)[0] if finish != 'stopped' else None
    if finish == 'composite':
        save_candidate(experiment, 'B', 1, {'Q03'}, candidate_k=24)
    number = 2 if winner else 1
    stop = {'round': number, 'reason': '零候选夹具'}
    with store.connection() as db:
        db.execute("UPDATE experiments SET status='generating', result_json=json_set(result_json,'$.seed_round_planned',json(?)) WHERE id=?",
                   ('true' if winner else 'false', experiment))
    store.save_agent_round(experiment, [], {'round': number, 'hypothesis_plan': {},
                                             'decision_stop': stop, 'generated_candidate_count': 0})
    saved = store.experiment(experiment)
    assert saved['result']['hypothesis_chain'][str(number)] == {}
    assert saved['result']['seed_round_planned'] is True
    assert saved['result']['decision_stop'] == stop

    replan = Mock(side_effect=AssertionError('zero-candidate round repeated'))
    monkeypatch.setattr(WorkflowEngine, 'generate_next', replan)
    advance = Mock(return_value={'status': 'recommended'})
    state = {}
    result = optimization_cycle._run_staged(store, None, experiment, state,
        lambda status, phase, reason=None: {'status': status, 'phase': phase, 'reason': reason},
        advance, None, None)
    replan.assert_not_called()
    if winner:
        assert result['status'] == 'recommended'
        assert state['staged_decision']['decision'] == finish
        assert advance.call_args.args[1][0]['id'] == winner
        assert advance.call_args.kwargs.get('do_composite', True) == (finish == 'composite')
    else:
        assert result == {'status': 'stopped', 'phase': 'review', 'reason': stop['reason']}
        advance.assert_not_called()
