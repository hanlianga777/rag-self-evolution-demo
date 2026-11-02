"""Explicitly started A/B/C batches; D and release keep their existing decisions."""
import json
import os
from datetime import datetime, timezone

from .evaluation import EvaluationRunner
from .full_text import CORPUS_LOCK
from .optimization import OptimizationAgent
from .policy import MAX_EVALS


def _save_state(store, experiment_id, **state):
    with store.connection() as connection:
        connection.execute('BEGIN IMMEDIATE')
        row = connection.execute('SELECT result_json FROM experiments WHERE id=?', (experiment_id,)).fetchone()
        result = json.loads(row['result_json'])
        result['optimization_cycle'] = {**result.get('optimization_cycle', {}), **state,
            'updated_at': datetime.now(timezone.utc).isoformat()}
        connection.execute('UPDATE experiments SET result_json=? WHERE id=?',
                           (json.dumps(result, ensure_ascii=False, allow_nan=False), experiment_id))


def claim_cycle(store, experiment_id):
    """Called before starting the worker, so duplicate clicks cannot own two cycles."""
    with CORPUS_LOCK, store.connection() as connection:
        connection.execute('BEGIN IMMEDIATE')
        experiment = store.experiment(experiment_id)
        if not experiment:
            raise ValueError('实验不存在')
        store.require_current_baseline(experiment['baseline_run_id'], connection)
        if experiment['result'].get('optimization_cycle', {}).get('status') == 'running':
            raise ValueError('优化批次正在运行')
        if experiment['status'] == 'generating' or any(c['status'] in {'queued', 'running'} for c in experiment['candidates']):
            raise ValueError('当前方案或评测仍在运行')
        if experiment['result'].get('report_confirmation'):
            raise ValueError('报告已确认，不能继续改变实验')
        state = {'status':'running', 'phase':'analysis', 'owner_pid':os.getpid(),
                 'used':experiment['evaluation_budget']['used'],
                 'remaining':max(0, MAX_EVALS-experiment['evaluation_budget']['used']),
                 'reserved_for_d':1, 'last_error':None}
        result = {**experiment['result'], 'optimization_cycle':state}
        connection.execute('UPDATE experiments SET result_json=? WHERE id=?',
                           (json.dumps(result, ensure_ascii=False), experiment_id))
        return state


def run_until_qualified(store, runtime, experiment_id, *, claimed=False):
    """Only this explicit batch action loops; technical failures never auto-resume."""
    if not claimed:
        claim_cycle(store, experiment_id)
    runner, agent = EvaluationRunner(store, runtime), OptimizationAgent(store, runtime.provider)
    empty_rounds = 0
    state = {}

    def save(status, phase, error=None):
        experiment = store.experiment(experiment_id)
        used = experiment['evaluation_budget']['used']
        state.update(status=status, phase=phase, used=used, remaining=max(0, MAX_EVALS-used),
                     reserved_for_d=1, last_error=error,
                     round=max([c['reasoning'].get('round', 1) for c in experiment['candidates']] or [0]))
        _save_state(store, experiment_id, **state)
        return dict(state)

    try:
        while True:
            experiment = store.experiment(experiment_id)
            store.require_current_baseline(experiment['baseline_run_id'])
            pending = [c for c in experiment['candidates'] if c['status']=='generated' and c['reasoning'].get('candidate_label') in {'A','B','C'}]
            for candidate in pending:
                if store.experiment(experiment_id)['evaluation_budget']['used'] >= MAX_EVALS-1:
                    return save('budget_exhausted', 'review')
                save('running', 'sandbox')
                finished = runner.run_candidate(candidate['id'], automatic=True)
                if finished['status'] != 'evaluated':
                    return save('failed', 'sandbox', '试跑未完整结束，请检查已保存断点后再处理')
            experiment = store.experiment(experiment_id)
            if any(c['status']=='evaluated' and c['result'].get('qualification',{}).get('qualified') is True for c in experiment['candidates']):
                return save('qualified', 'review')
            if experiment['evaluation_budget']['used'] >= MAX_EVALS-1:
                return save('budget_exhausted', 'review')
            save('running', 'analysis')
            before = len(experiment['candidates'])
            try:
                agent.generate(experiment['baseline_run_id'], experiment_id=experiment_id)
            except ValueError:
                # A rejected draft is saved for audit and costs no Sandbox trial.
                audit = store.experiment(experiment_id)['result']
                if audit.get('provider_raw_text') is None or not audit.get('rejected_candidates'):
                    raise
            experiment = store.experiment(experiment_id)
            empty_rounds = empty_rounds+1 if len(experiment['candidates'])==before else 0
            if empty_rounds >= 3:
                return save('analysis_exhausted', 'analysis', '连续3轮没有合法草案，已停止；试跑预算未额外扣减')
    except Exception as error:
        return save('failed', state.get('phase','analysis'), str(error))
