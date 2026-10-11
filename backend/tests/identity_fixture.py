"""Disposable, auditable baseline fixtures for identity guard regressions."""
import json
from app.corpus import current_manifest, manifest_identity
from app.policy import DEFAULT_PIPELINE_CONFIG
from app.evaluation_contract import VERSIONS, evaluation_identity


def completed_baseline(store, target='baseline', snapshot=None, run_id=None):
    if snapshot is None:
        snapshot = {'id': 'GD-current', 'question_ids': ['Q1'], 'questions': [{'id': 'Q1', 'question': '测试'}], 'corpus_fingerprint': manifest_identity(current_manifest())}
        with store.connection() as connection:
            connection.execute("INSERT OR IGNORE INTO dataset_versions VALUES (?, 'approved', 'human_review', ?, '2026-09-30')", (snapshot['id'], json.dumps(snapshot)))
    config = {**DEFAULT_PIPELINE_CONFIG}
    if target is not None:
        config['run_target'] = target
    judge = {'model': 'fixture', **VERSIONS}
    judge['evaluation_identity'] = evaluation_identity(snapshot, judge)
    created_id = store.create_evaluation_run(snapshot, config, judge)
    if run_id:
        with store.connection() as connection:
            connection.execute('UPDATE evaluation_runs SET id=? WHERE id=?', (run_id, created_id))
    else:
        run_id = created_id
    store.record_evaluation_case(run_id, 'Q1', {'passed': False, 'primary_root_cause': 'Retrieval', 'diagnosis': {'status': 'confirmed', 'reason': 'offline fixture verified omission'}})
    store.finish_evaluation_run(run_id, 'completed', {'gates': {'passed': False}})
    store.record_bad_case(run_id, 'Q1', 'Retrieval', 'ordinary', {'reason': 'test', 'primary_root_cause': 'Retrieval', 'diagnosis': {'status': 'confirmed', 'reason': 'offline fixture verified omission'}})
    return run_id


def context_judgment(scores, context):
    """Exact support in explicit fixture final text; never used by production."""
    observation = (context or {}).get('programmatic_evidence_observation', {})
    support = [{'fact': f['fact'], 'chunk_id': loc['chunk_id'], 'quote': loc['quote']} for f in observation.get('facts', []) for loc in f.get('locations', [])[:1]]
    sufficient = bool(support) and len(support) == len(observation.get('facts', []))
    return {**scores, 'evidence_sufficiency': {'status': 'sufficient' if sufficient else 'insufficient', 'source_applicable': True, 'conflicts': [], 'reason': 'Offline fixture exact final text coverage', 'fact_support': support}}


def comparison_identity(store, baseline):
    return {'evaluation_identity': store.evaluation_run(baseline)['judge']['evaluation_identity'], 'comparison_version': 'target-v2', 'all_fixed_question_ids': ['Q1'], 'net_improvement': 1}
