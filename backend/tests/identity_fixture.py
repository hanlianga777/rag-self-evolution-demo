"""Disposable, auditable baseline fixtures for identity guard regressions."""
import json
from app.corpus import current_manifest
from app.policy import DEFAULT_PIPELINE_CONFIG


def completed_baseline(store, target='baseline', snapshot=None, run_id=None):
    if snapshot is None:
        snapshot = {'id': 'GD-current', 'question_ids': ['Q1'], 'questions': [{'id': 'Q1', 'question': '测试'}], 'corpus_fingerprint': current_manifest()['sources']}
        with store.connection() as connection:
            connection.execute("INSERT OR IGNORE INTO dataset_versions VALUES (?, 'approved', 'human_review', ?, '2026-09-30')", (snapshot['id'], json.dumps(snapshot)))
    config = {**DEFAULT_PIPELINE_CONFIG}
    if target is not None:
        config['run_target'] = target
    created_id = store.create_evaluation_run(snapshot, config, {'model': 'fixture', 'prompt_version': 'judge-v1', 'scoring_policy': 'v1.0.1-gates'})
    if run_id:
        with store.connection() as connection:
            connection.execute('UPDATE evaluation_runs SET id=? WHERE id=?', (run_id, created_id))
    else:
        run_id = created_id
    store.record_evaluation_case(run_id, 'Q1', {'passed': False})
    store.finish_evaluation_run(run_id, 'completed', {'gates': {'passed': False}})
    store.record_bad_case(run_id, 'Q1', 'Retrieval', 'ordinary', {'reason': 'test'})
    return run_id
