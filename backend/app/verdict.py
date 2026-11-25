"""Final evaluation verdicts and the samples that establish them."""

import json
from statistics import median

from . import rules

BASELINE_ORIGINAL_ID = 'EVAL-20261120213645613191'
RECORDS_KEY = 'verdict:final'
DIMENSIONS = ('correctness', 'faithfulness', 'completeness')
PREVIOUS_VERDICT_VERSION = '2026-11-24'


def resolve(samples):
    if len(samples) not in (1, 3) or any(type(sample.get('passed')) is not bool or type(sample.get('risk')) is not bool for sample in samples):
        raise ValueError('最终判定需要 1 份或 3 份有效样本')
    return not any(sample['risk'] for sample in samples) and sum(s['passed'] for s in samples) > len(samples) // 2


def recheck_reason(first, baseline, winner=None):
    if first != baseline:
        return 'changed_vs_baseline'
    if winner is not None and first != winner:
        return 'changed_vs_winner'
    return None


def median_scores(samples):
    return {key: median(s['rubric_scores'][key] for s in samples)
            for key in DIMENSIONS if all(s['rubric_scores'].get(key) is not None for s in samples)}


def protected_risk(case, question):
    from .policy import protected_question

    judge = case.get('judge_result') or {}
    return protected_question(case, question) and (
        judge.get('safety_violation') is True
        or any(v.get('safety_violation') is True for v in (judge.get('samples') or []))
    )


def make_sample(case, question, position, source, diagnostic_id):
    from .evaluation import policy_behavior

    metrics = case.get('programmatic_metrics') or {}
    trace = metrics.get('retrieval_trace') or {}
    judge = case.get('judge_result') or {}
    generation = (metrics.get('token_usage') or {}).get('generation') or {}
    return {
        'sample_no': position, 'source': source, 'passed': case.get('passed'),
        'rubric_scores': (case.get('evaluation_outcome') or {}).get('rubric_scores') or {},
        'risk': protected_risk(case, question), 'answer': case.get('model_answer'),
        'decompose_ref': trace.get('query_decompose'), 'candidates': trace.get('candidates'),
        'reranked': trace.get('reranked'), 'final_context': trace.get('final'),
        'generation_request_sha256': (metrics.get('generation_request_sha256')
                                      or generation.get('request_sha256')
                                      or (case.get('reused_from') or {}).get('request_sha256')),
        'judge_raw': judge, 'latency_ms': metrics.get('latency_ms'), 'diagnostic_id': diagnostic_id,
        'behavior_pass': policy_behavior(case),
        'case': {
            **{k: v for k, v in case.items() if k not in {'model_answer', 'judge_result', 'programmatic_metrics'}},
            'programmatic_metrics': {**metrics, 'retrieval_trace': {
                k: v for k, v in trace.items() if k not in {'candidates', 'reranked', 'final'}}},
        },
    }


def record(run_id, question_id, samples, reason=None):
    return {'question_id': question_id, 'run_id': run_id, 'final_passed': resolve(samples),
            'samples': samples, 'rechecked': len(samples) == 3, 'recheck_reason': reason}


def records(store, run_id, *, connection=None):
    if not run_id:
        return {}
    if connection is None:
        with store.connection() as db:
            return records(store, run_id, connection=db)
    if not connection.execute("SELECT 1 FROM sqlite_master WHERE name='job_checkpoints'").fetchone():
        return {}
    row = connection.execute('SELECT checkpoint_json FROM job_checkpoints WHERE run_id=? AND question_id=?',
                             (run_id, RECORDS_KEY)).fetchone()
    return json.loads(row[0]) if row else {}


def save_records(store, run_id, values):
    """Publish the completed wave together. Partial samples live in checkpoints."""
    with store.connection() as db:
        db.execute('INSERT INTO job_checkpoints VALUES (?,?,?) ON CONFLICT(run_id,question_id) DO NOTHING',
                   (run_id, RECORDS_KEY, json.dumps(values, ensure_ascii=False)))
        return records(store, run_id, connection=db)


def final_verdicts(run_id, *, store=None, connection=None, cases=None, use_final=True, saved=None):
    """Read the current verdict or the untouched historical single-sample result."""
    if not run_id:
        return {}
    if store is None and connection is None:
        import os
        from .governance import GovernanceStore
        store = GovernanceStore(os.getenv('RAG_DEMO_DB_PATH') or None, read_only=True)
    if use_final and saved is None:
        saved = records(store, run_id, connection=connection)
    if use_final and saved:
        return {key: row['final_passed'] for key, row in saved.items()}
    if cases is None:
        if connection is None:
            cases = store.evaluation_case_results(run_id)
        else:
            cases = [{'question_id': row[0], **json.loads(row[1])} for row in connection.execute(
                'SELECT question_id,result_json FROM evaluation_case_results WHERE run_id=?', (run_id,))]
    return {case['question_id']: case['passed'] for case in cases if type(case.get('passed')) is bool}


def final_cases(store, run_id, *, use_final=True, connection=None, cases=None):
    """Project the verdict and the matching sample's evidence for decision consumers."""
    if not run_id:
        return []
    if cases is None:
        cases = store.evaluation_case_results(run_id)
    if not use_final:
        return cases
    saved = records(store, run_id, connection=connection)
    if not saved:
        return cases
    passed = final_verdicts(run_id, store=store, connection=connection, cases=cases, saved=saved)
    return [decision_case(case, saved[case['question_id']], passed[case['question_id']])
            if case['question_id'] in saved else case for case in cases]


def decision_case(case, row, passed):
    samples = row['samples']
    chosen = next((sample for sample in samples if sample['risk']), None)
    if chosen is None:
        chosen = next(sample for sample in samples if sample['passed'] == passed)
    evidence = chosen['case']
    metrics = evidence['programmatic_metrics']
    trace = {**metrics['retrieval_trace'], 'candidates': chosen['candidates'],
             'reranked': chosen['reranked'], 'final': chosen['final_context']}
    state = 'PASS' if passed else 'FAIL'
    return {**case, **evidence, 'run_id': row['run_id'], 'question_id': row['question_id'],
            'model_answer': chosen['answer'], 'judge_result': chosen['judge_raw'],
            'programmatic_metrics': {**metrics, 'retrieval_trace': trace},
            'passed': passed, 'final_passed': passed,
            'evaluation_outcome': {**(evidence.get('evaluation_outcome') or {}), 'verdict': state},
            'verdict_sample_no': chosen['sample_no']}


def gate_cases(store, run_id):
    saved = records(store, run_id)
    return [gate_case(case, saved[case['question_id']]) if case['question_id'] in saved else case
            for case in store.evaluation_case_results(run_id)]


def gate_case(case, row):
    """Keep the gate reducer's original units and the first run's latency."""
    samples = row['samples']
    scores = median_scores(samples)
    judge = dict(case.get('judge_result') or {})
    judge.update({name: score / (25 if name == 'correctness' else 100) for name, score in scores.items()})
    behavior = [s['behavior_pass'] for s in samples]
    effective = sum(v is True for v in behavior) > len(behavior) // 2 if None not in behavior else None
    return {**case, 'passed': row['final_passed'], 'judge_result': judge,
            'programmatic_metrics': {**case['programmatic_metrics'],
                'behavior_contract': {'effective_pass': effective}, 'latency_ms': samples[0]['latency_ms']}}


def require_baseline(store, run, *, connection=None, saved=None):
    expected = set(json.loads(run['dataset_snapshot_json'])['question_ids'])
    if saved is None:
        saved = records(store, run['id'], connection=connection)
    if not expected or set(saved) != expected or any(len(row['samples']) != 3 for row in saved.values()):
        raise ValueError('Baseline 每题须保存三份有效样本并生成最终判定')


def current(experiment_result):
    return experiment_result.get('verdict_version') == rules.RULES_VERSION


def uses_final(result):
    """Read E4 with its original majority verdict after newer rules take effect."""
    return current(result) or result.get('verdict_version') == PREVIOUS_VERDICT_VERSION


def require_empty_history(ledger):
    if (ledger or {}).get('historical'):
        raise ValueError('E4 参数效果账本 historical 必须为空')
