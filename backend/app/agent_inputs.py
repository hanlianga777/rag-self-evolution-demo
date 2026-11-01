"""Objective Agent inputs from saved Baseline records; no service calls or writes."""
import json

from .diagnostics import diagnostic_view, standard_evidence

MISSING = '记录缺失'


def evidence_positions(question, trace):
    raw = question.get('raw') or {}
    evidence = (question.get('evidence') or raw.get('evidence')
                or question.get('evidence_locations') or raw.get('evidence_locations')
                or (question.get('business_requirements') or raw.get('business_requirements') or {}).get('sources') or [])
    ids = []
    for entry in evidence:
        keys = (entry.get('source_chunk_ids') or [entry.get('chunk_id') or entry.get('source_id')]) if isinstance(entry, dict) else [None]
        for key in keys:
            if key not in ids:
                ids.append(key)
    if not ids:
        return MISSING

    def position(chunk_id, stage):
        entries = trace.get(stage)
        if not chunk_id or not isinstance(entries, list) or trace.get('status') not in (None, 'completed'):
            return MISSING
        for index, entry in enumerate(entries, 1):
            if isinstance(entry, dict) and (entry.get('chunk_id') == chunk_id or chunk_id in (entry.get('matched_child_ids') or [])):
                return index
        if any(not isinstance(entry, dict) or not (entry.get('chunk_id') or entry.get('matched_child_ids')) for entry in entries):
            return MISSING
        return '未进入'

    return [{'chunk_id': key or MISSING, **{stage: position(key, stage) for stage in ('candidates', 'reranked', 'final')}} for key in ids]


def retrieval_facts(case, question=None, config=None, review=None):
    """Project only facts; baseline_review.analysis is deliberately never read."""
    question = question or {}
    trace = (case.get('programmatic_metrics') or {}).get('retrieval_trace') or {}
    saved_config = {**(config or {}), **(trace.get('config') or {})}
    checks = (case.get('judge_result') or {}).get('checks')
    requirements = (question.get('business_requirements') or (question.get('raw') or {}).get('business_requirements') or {}).get('required_checks')
    required_names = {r.get('requirement') for r in requirements} if isinstance(requirements, list) else None
    if not isinstance(checks, list) or any(not isinstance(c, dict) or type(c.get('met')) is not bool or not c.get('requirement') for c in checks):
        unmet = MISSING
    elif required_names and not required_names.issubset({c['requirement'] for c in checks}):
        unmet = MISSING
    else:
        unmet = [c['requirement'] for c in checks if c['met'] is False and
                 (c['requirement'] in required_names if required_names is not None else c.get('check_type') not in {'auxiliary', 'optional'})]
    summary = (review or {}).get('regression_review') or {}
    failed, total = summary.get('failed_votes'), summary.get('total_votes')
    conclusion = {'confirmed_regression': '真错题', 'fluctuation': '随机波动'}.get(summary.get('status'), MISSING)
    if (conclusion == MISSING or type(failed) is not int or type(total) is not int
            or not 0 <= failed <= total or total <= 0):
        conclusion, failed, total = MISSING, MISSING, MISSING
    return {'standard_evidence_positions': evidence_positions(question, trace),
            'candidate_k': saved_config.get('candidate_k', MISSING), 'top_k': saved_config.get('top_k', MISSING),
            'unmet_required_points': unmet,
            'baseline_review': {'conclusion': conclusion, 'failed_votes': failed, 'total_votes': total}}


def prepare_baseline_rows(baseline, rows):
    """Use the same frozen question for Agent, coverage planning and case lists."""
    snapshot = json.loads(baseline['dataset_snapshot_json']) if baseline else {}
    questions = {q['id']: q for q in snapshot.get('questions', [])}
    reviews = ((baseline or {}).get('result', {}).get('baseline_review') or {}).get('cases') or {}
    prepared = []
    for row in rows:
        question = questions.get(row['question_id'])
        case = {**row['result']}
        if question is not None:
            case['standard_evidence'] = standard_evidence(question) or case.get('standard_evidence', [])
        prepared.append({**row, 'result': case,
                         'diagnostic_view': diagnostic_view(case, golden_item=question),
                         'retrieval_facts': retrieval_facts(case, question, (baseline or {}).get('config'), reviews.get(row['question_id']))})
    return prepared
