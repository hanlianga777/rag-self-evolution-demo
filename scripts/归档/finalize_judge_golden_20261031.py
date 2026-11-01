"""Offline preparation by default; consume independent review and freeze via GovernanceStore.

No Provider, human impersonation, content edits, or automatic resumption. The explicit
review-freeze authorization and current-content owner delegation are separate inputs.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import hashlib
import os
from pathlib import Path
import shutil
import socket

import execute_judge_golden_revisions_20261030 as common

ROOT = common.ROOT


def load(path):
    return json.loads(Path(path).read_text())


def checked_plan(path):
    value = load(path)
    if common.digest({k: v for k, v in value.items() if k != 'plan_sha256'}) != value['plan_sha256']:
        raise ValueError('Reviewed plan changed: ' + str(path))
    return value


def no_network(*args, **kwargs):
    raise RuntimeError('Network/Provider forbidden during review-freeze')


def protected_history(before, after, targets, *, frozen):
    """Only three current question rows, three reviews/approvals, one new Snapshot."""
    with common.readonly(before) as db:
        old = common.table_hashes(db, exclude_questions=targets)
    with common.readonly(after) as db:
        new = common.table_hashes(db, exclude_questions=targets)
    appended = {'review_events': 3, 'approvals': 3, 'dataset_versions': 1} if frozen else {}
    if old.keys() != new.keys():
        raise RuntimeError('Database schema/table set changed')
    for table, rows in old.items():
        if Counter(rows) - Counter(new[table]) or len(new[table]) != len(rows) + appended.get(table, 0):
            raise RuntimeError('Protected history changed: ' + table)


def reuse_reviews(store, ids, targets):
    result = []
    for key in ids:
        if key in targets:
            continue
        item, identity = store.capture_quality(key)
        row = store.candidate_rows([key])[0]
        history = store.review_history(key)
        qc_id = row.get('qc', {}).get('id')
        eligible = store.approval_eligibility(key)
        valid = (item['stage'] == 'golden' and item['review_status'] == 'approved'
                 and eligible['can_approve'] and history
                 and history[0].get('quality_identity') == identity
                 and history[0].get('review_qc_id') == qc_id)
        result.append({'question_id': key, 'reusable': bool(valid), 'quality_identity': identity,
                       'qc_id': qc_id, 'latest_review': history[0] if history else None,
                       'blocking_reasons': eligible['blocking_reasons']})
    return result


def assert_bound(plan):
    for key in ('source_files', 'assets'):
        for path, expected in plan[key].items():
            if common.file_sha(path) != expected:
                raise ValueError('Bound file changed: ' + path)
    if common.asset_hashes(plan['index'], plan['documents']) != plan['assets']:
        raise ValueError('Corpus/index asset set changed')
    with common.readonly(plan['database']) as db:
        common.ensure_no_active_tasks(db)
        if common.table_fingerprints(db) != plan['source_tables']:
            raise ValueError('Post-quality database changed; no implicit resume')


def prepare(args):
    recovery = checked_plan(args.qc_output / 'plan.json')
    result = load(args.qc_output / 'result.json')
    if result.get('status') != 'quality_complete_review_required' or result.get('calls') != 1:
        raise ValueError('Successful actual one-shot Q36 QC result required')
    original = checked_plan(args.original_plan)
    ids = original['question_ids']
    targets = [row['question_id'] for row in original['targets']]
    if len(ids) != 50 or len(set(ids)) != 50 or len(targets) != 3 or len(set(targets)) != 3:
        raise ValueError('Exactly 50 questions and three revised targets required')
    args.output.mkdir(parents=True, exist_ok=False)
    common.backup_database(recovery['database'], args.output / 'before.db')
    isolated = args.output / 'isolated'
    isolated.mkdir()
    shutil.copytree(recovery['index'], isolated / 'index')
    shutil.copytree(recovery['documents'], isolated / 'documents')
    (isolated / 'empty.env').write_text('')
    (isolated / 'uploads').mkdir()
    common.bind_environment(args.output / 'before.db', isolated / 'index', isolated / 'documents',
                            isolated / 'empty.env', isolated / 'uploads')
    socket.socket.connect = no_network
    socket.create_connection = no_network
    from app.governance import GovernanceStore
    from app.delegated_review import CHECKS
    from app.business_golden import CHECKS as BUSINESS_CHECKS
    from app.corpus import current_manifest, manifest_identity
    store = GovernanceStore(args.output / 'before.db', migrate=False)
    with common.readonly(args.output / 'before.db') as db:
        common.ensure_no_active_tasks(db)
        tables = common.table_fingerprints(db)
        old_snapshot = db.execute('SELECT snapshot_json FROM dataset_versions WHERE id=?', (original['snapshot_id'],)).fetchone()[0]
    if hashlib.sha256(old_snapshot.encode()).hexdigest() != original['source_snapshot_sha256']:
        raise ValueError('Original frozen Snapshot changed')
    if manifest_identity(current_manifest()) != original['corpus']:
        raise ValueError('Corpus identity differs from original Snapshot')
    run = store.generation_run(original['generation_run_id'], qualification=False)
    if run['question_ids'] != ids or run['status'] != 'completed':
        raise ValueError('Completed original 50-question run required')
    reuse = reuse_reviews(store, ids, targets)
    items = {key: store.question(key) for key in ids}
    rows = store.candidate_rows(ids)
    target_materials = []
    for key in targets:
        row = next(row for row in rows if row['id'] == key)
        if row['qc_status'] != 'qc_passed' or row['probe_status'] != 'probe_passed':
            raise ValueError('Current actual QC/Probe incomplete: ' + key)
        target_materials.append({'question': items[key], 'qualification': row,
                                'probe': store.probe_history(key)[0], 'qc': store.qc_history(key)[0],
                                'quality_identity': store.capture_quality(key)[1]})
    files = {str(Path(path).resolve()): common.file_sha(path) for path in
             [args.original_plan, args.qc_output / 'plan.json', args.qc_output / 'result.json',
              Path(__file__), Path(common.__file__), *[ROOT / 'backend/app' / name for name in common.CODE]]}
    files.update(recovery['source_files'])
    files.update(recovery['original_execution_files'])
    state = run['artifacts']['hard_validation']
    materials = {'schema': 'post-quality-independent-review-input-1', 'generation_run': run,
                 'all_50_content_hashes': {key: store._quality_content(item) for key, item in items.items()},
                 'all_50_qualification': rows, 'targets': target_materials, 'reuse_47': reuse,
                 'review_requirements': {'checks': list(CHECKS), 'business_checks': list(BUSINESS_CHECKS),
                    'actor': 'Codex AI Agent / Owner Delegated AI Review', 'decision': 'A', 'risk': 'none',
                    'required_authored_fields': ['question_id', 'content_hash', 'reviewed_at', 'basis', 'sources'],
                    'sources_fields': ['chunk_id', 'document_id', 'page', 'quote'],
                    'rule': 'Independent semantic/PDF review after current quality timestamps. Do not prefill approvals. Disposition all attention reasons; material anchors are not answer evidence.'},
                 'delegation_requirements': {'authorization_id': 'NEW_EXTERNALLY_AUTHORED_ID',
                    'source': 'direct_user_instruction', 'delegated_by': 'project_owner', 'actor': 'Codex',
                    'source_file': 'EXACT_AUTHORIZED_USER_INSTRUCTION_PATH', 'source_sha256': 'SHA256_OF_SOURCE_FILE',
                    'expires_at': 'FUTURE_TIME_WITH_UTC_OFFSET', 'generation_run_id': run['id'],
                    'profile': run['profile'], 'corpus': state['corpus_fingerprint'],
                    'plan_id': state['frozen_plan']['plan_id'], 'content_identity': state.get('content_identity'),
                    'content_hashes': {key: store._quality_content(item) for key, item in items.items()}}}
    common.save(args.output / 'independent-review-input.json', materials)
    plan = {'schema': 'judge-golden-post-quality-finalize-1', 'prepared_at': datetime.now(timezone.utc).isoformat(),
            'database': recovery['database'], 'index': recovery['index'], 'documents': recovery['documents'],
            'env_file': str((isolated / 'empty.env').resolve()), 'generation_run_id': run['id'],
            'question_ids': ids, 'targets': targets, 'source_snapshot_id': original['snapshot_id'],
            'source_tables': tables, 'source_files': files, 'assets': recovery['assets'],
            'content_hashes': materials['all_50_content_hashes'], 'reuse_47': reuse,
            'review_input_sha256': common.file_sha(args.output / 'independent-review-input.json'),
            'blockers': [r['question_id'] + ': stale review/quality' for r in reuse if not r['reusable']],
            'paid_calls': 0, 'formal_writes': 0}
    plan['plan_sha256'] = common.digest(plan)
    common.save(args.output / 'plan.json', plan)
    assert_bound(plan)
    return {'status': 'independent_review_required', 'plan_sha256': plan['plan_sha256'],
            'reuse_47': sum(r['reusable'] for r in reuse), 'blockers': plan['blockers'],
            'paid_calls': 0, 'formal_writes': 0}


def freeze(store, plan, auth, reviews):
    store.review_owner_delegated_batch(plan['generation_run_id'], auth['authorization_id'], reviews)
    run = store.generation_run(plan['generation_run_id'], qualification=False)
    gate = store.gate_summary(run, store.candidate_rows(plan['question_ids']))
    if gate['status'] != 'ready':
        raise RuntimeError('Full 50-question Gate is not ready')
    snapshot = store.create_dataset_snapshot([store.question(key) for key in plan['question_ids']],
                                             generation_run_id=plan['generation_run_id'])
    if {key: store._quality_content(store.question(key)) for key in plan['question_ids']} != plan['content_hashes']:
        raise RuntimeError('Evaluated question content changed during review-freeze')
    return snapshot


def execute(args):
    plan = checked_plan(args.output / 'plan.json')
    common.require_authorization(load(args.authorization), plan['plan_sha256'], 'review-freeze')
    if plan['blockers']:
        raise ValueError('Prepared plan has blockers')
    if common.file_sha(args.output / 'independent-review-input.json') != plan['review_input_sha256']:
        raise ValueError('Independent review materials changed')
    assert_bound(plan)
    auth, reviews = load(args.delegation), load(args.reviews)
    authorization = load(args.authorization)
    if any(auth.get(key) != authorization.get(key) for key in ('source_file', 'source_sha256')):
        raise ValueError('Delegation differs from explicit execution instruction')
    if len(reviews) != 3 or {r['question_id'] for r in reviews} != set(plan['targets']):
        raise ValueError('Exactly three independent current-content reviews required')
    common.bind_environment(plan['database'], plan['index'], plan['documents'], plan['env_file'], args.output / 'isolated/uploads')
    socket.socket.connect = no_network
    socket.create_connection = no_network
    from app.governance import GovernanceStore
    from app.delegated_review import validate_delegation
    store = GovernanceStore(plan['database'], migrate=False)
    items = {key: store.question(key) for key in plan['question_ids']}
    validate_delegation(args.delegation, auth['authorization_id'], store.generation_run(plan['generation_run_id'], qualification=False),
                        store.candidate_rows(plan['question_ids']), items, reviews, store._quality_content)
    for review in reviews:
        key = review['question_id']
        quality_at = max(datetime.fromisoformat(history[0]['created_at'])
                         for history in (store.qc_history(key), store.probe_history(key)))
        if datetime.fromisoformat(review['reviewed_at']) < quality_at:
            raise ValueError('Independent review must follow actual current QC/Probe: ' + key)
    common.backup_database(plan['database'], args.output / 'before-review-freeze.db')
    # Run the same official methods on a disposable copy before any formal write.
    rehearsal = args.output / 'rehearsal'
    rehearsal.mkdir()
    common.backup_database(plan['database'], rehearsal / 'demo.db')
    shutil.copy2(args.delegation, rehearsal / 'owner-delegated-review.json')
    test_store = GovernanceStore(rehearsal / 'demo.db', migrate=False)
    freeze(test_store, plan, auth, reviews)
    protected_history(args.output / 'before-review-freeze.db', rehearsal / 'demo.db', plan['targets'], frozen=True)
    assert_bound(plan)
    destination = Path(plan['database']).parent / 'owner-delegated-review.json'
    if destination.exists():
        shutil.copy2(destination, args.output / 'previous-owner-delegated-review.json')
    for name, path in [('authorization.json', args.authorization), ('delegation.json', args.delegation), ('reviews.json', args.reviews)]:
        if Path(path).resolve() != (args.output / name).resolve():
            shutil.copy2(path, args.output / name)
    temporary = destination.with_suffix('.pending.json')
    shutil.copy2(args.delegation, temporary)
    temporary.chmod(0o600)
    os.replace(temporary, destination)
    try:
        snapshot = freeze(store, plan, auth, reviews)
        protected_history(args.output / 'before-review-freeze.db', plan['database'], plan['targets'], frozen=True)
        if common.asset_hashes(plan['index'], plan['documents']) != plan['assets']:
            raise RuntimeError('Corpus/index changed during freeze')
    except Exception as error:
        common.save(args.output / 'execution-failure.json', {'status': 'stopped_no_auto_resume', 'error': str(error), 'error_type': type(error).__name__})
        raise
    common.save(args.output / 'new-snapshot.json', snapshot)
    result = {'status': 'frozen', 'snapshot_id': snapshot['id'], 'questions': len(snapshot['question_ids']),
              'paid_calls': 0, 'baseline_started': False, 'history_preserved': True}
    common.save(args.output / 'result.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--qc-output', type=Path, default=ROOT / 'docs/judge_vnext_20261030/q36_qc_recovery_final')
    parser.add_argument('--original-plan', type=Path, default=ROOT / 'docs/judge_vnext_20261030/golden_authorized_execution/plan.json')
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--authorization', type=Path)
    parser.add_argument('--delegation', type=Path)
    parser.add_argument('--reviews', type=Path)
    args = parser.parse_args()
    if args.execute and any(getattr(args, key) is None for key in ('authorization', 'delegation', 'reviews')):
        parser.error('--execute requires separate authorization, delegation and independent reviews')
    print(json.dumps(execute(args) if args.execute else prepare(args), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
