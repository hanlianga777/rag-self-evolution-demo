"""Audited scoring-only Golden versions and saved Sandbox comparison facts."""
import copy
import json
from datetime import datetime, timezone

from .diagnostic_evidence import digest


def revision_changes(parent, target):
    receipt = target.get('scoring_revision') or {}
    if (receipt.get('parent_id') != parent.get('id') or receipt.get('parent_sha256') != digest(parent)
            or not all(receipt.get(k) for k in ('actor', 'reason', 'draft_sha256'))):
        raise ValueError('Scoring revision parent or authorization mismatch')
    ignored = {'id', 'questions', 'scoring_contract_manifest', 'scoring_revision'}
    if {k:v for k,v in parent.items() if k not in ignored} != {k:v for k,v in target.items() if k not in ignored}:
        raise ValueError('Scoring revision changed frozen dataset metadata')
    old, new = parent['questions'], target['questions']
    if len(old) != len(new) or [q['id'] for q in old] != target['question_ids']:
        raise ValueError('Scoring revision changed question membership')
    changed = []
    from .golden_v2 import qc_outcome
    for before, after in zip(old, new):
        if {k:v for k,v in before.items() if k != 'business_requirements'} != {k:v for k,v in after.items() if k != 'business_requirements'}:
            raise ValueError('Scoring revision changed question, reference or evidence')
        a, b = before.get('business_requirements', {}), after.get('business_requirements', {})
        allowed = {'required_checks', 'auxiliary_information'}
        if {k:v for k,v in a.items() if k not in allowed} != {k:v for k,v in b.items() if k not in allowed}:
            raise ValueError('Scoring revision changed prohibited items or canonical sources')
        if a != b:
            key = after['id']; changed.append(key)
            qc = receipt.get('qc', {}).get(key, {})
            result = qc.get('result', {})
            if (qc.get('question_sha256') != digest(after) or not qc_outcome(result)['passed']
                    or result.get('content_validation', {}).get('status') != 'supported'):
                raise ValueError('Scoring revision lacks current supported QC: ' + key)
    if not changed or changed != receipt.get('changed_question_ids') or set(receipt.get('qc', {})) != set(changed):
        raise ValueError('Scoring revision changed-question receipt mismatch')
    from .scoring_contract import validate_snapshot_manifest
    validate_snapshot_manifest(target)
    return changed


def freeze_scoring_revision(store, parent_id, questions, qc, *, actor, reason, draft_sha256):
    from .full_text import CORPUS_LOCK
    from .corpus import CorpusStore
    from .golden_v2 import validate_qc_content
    from .scoring_contract import snapshot_manifest
    with CORPUS_LOCK, store.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute("SELECT * FROM dataset_versions WHERE id=? AND status='approved'", (parent_id,)).fetchone()
        if not row: raise ValueError('Approved scoring revision parent missing')
        parent = {'id': parent_id, **json.loads(row['snapshot_json'])}
        target = copy.deepcopy(parent)
        target.update(id='GD-' + datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S'), questions=questions)
        changed = [q['id'] for a,q in zip(parent['questions'], questions) if a != q]
        chunks = CorpusStore().chunks()
        for q in questions:
            if q['id'] in changed:
                result = qc[q['id']]['result']
                if validate_qc_content({**q, 'raw': q}, result, chunks) != result.get('content_validation'):
                    raise ValueError('QC content binding changed')
        target['scoring_contract_manifest'] = snapshot_manifest(target)
        target['scoring_revision'] = {'parent_id': parent_id, 'parent_sha256': digest(parent),
            'actor': actor, 'reason': reason, 'draft_sha256': draft_sha256,
            'changed_question_ids': changed, 'qc': qc}
        revision_changes(parent, target)
        existing = db.execute("SELECT id,snapshot_json FROM dataset_versions WHERE source='scoring_revision' ORDER BY created_at DESC").fetchall()
        for saved in existing:
            value = json.loads(saved['snapshot_json'])
            if value.get('scoring_revision') == target['scoring_revision'] and value.get('questions') == questions:
                return {'id': saved['id'], **value}
        db.execute('INSERT INTO dataset_versions(id,status,source,snapshot_json,created_at) VALUES (?,?,?,?,?)',
            (target['id'], 'approved', 'scoring_revision', json.dumps(target, ensure_ascii=False), datetime.now(timezone.utc).isoformat()))
        return target


def historical_replay_candidates(store, baseline, references):
    from .evaluation import candidate_comparison
    from .policy import evaluate_regression, qualify_candidate
    rows = []
    for reference in references:
        candidate = copy.deepcopy(store.candidate(reference['candidate_id']))
        run = store.evaluation_run(reference['replay_run_id'])
        if (not candidate or not run or run['status'] != 'completed'
                or run['dataset_version_id'] != baseline['dataset_version_id']
                or run['judge'].get('evaluation_identity') != baseline['judge'].get('evaluation_identity')
                or not run['result'].get('evaluation_complete') or run['result'].get('technical_failed', 0)
                or run['result'].get('judge_replay', {}).get('source_run_id') != candidate['result'].get('evaluation_run_id')):
            raise ValueError('Historical Sandbox replay identity or completeness mismatch')
        expected = {k:v for k,v in store.evaluation_run(candidate['result']['evaluation_run_id'])['config'].items() if k not in {'candidate_id', 'run_target'}}
        if {k:v for k,v in run['config'].items() if k != 'run_target'} != expected:
            raise ValueError('Historical Sandbox replay configuration mismatch')
        base = {c['question_id']:c for c in store.evaluation_case_results(baseline['id'])}
        saved = {c['question_id']:c for c in store.evaluation_case_results(run['id'])}
        target_references = set(candidate['reasoning'].get('observed_evidence', []))
        failed = [q for q,c in base.items() if c.get('passed') is False]
        targets = [q for q in failed if q in target_references or any(r.endswith('-' + q) for r in target_references)]
        frozen = {q['id']:q for q in json.loads(baseline['dataset_snapshot_json'])['questions']}
        comparison = candidate_comparison(base, saved, targets, frozen)
        if not comparison['comparison_complete']: raise ValueError('Historical replay cases incomplete')
        regression = {**evaluate_regression(new_critical_failures=comparison['new_critical_failures'],
            new_ordinary_failures=comparison['new_ordinary_failures']), **comparison}
        candidate.update(status='evaluated', result={**run['result'], **comparison,
            'new_failure_question_ids': comparison['new_regression_question_ids'],
            'evaluation_run_id': run['id'], 'regression': regression,
            'qualification': qualify_candidate(run['result']['gates'], regression,
                comparison['target_bad_cases_fixed'], len(failed), comparison['bad_case_count']),
            'historical_replay': reference})
        rows.append(candidate)
    return rows
