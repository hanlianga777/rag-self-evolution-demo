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


def test_e6_sandbox_reuses_exhausted_judge_and_adopts_two_votes(tmp_path, monkeypatch):
    store = GovernanceStore(tmp_path / 'sandbox.db')
    runner = EvaluationRunner(store, None)
    monkeypatch.setattr('app.request_reuse.experiment_scope', lambda *_: nullcontext())
    monkeypatch.setattr('app.paid_run.current_paid_run', lambda: SimpleNamespace(identity={'task': '124c'}))
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
