"""Authorized optimization loop; unattended work always stops before release."""
import json
import logging
import os
import threading
from datetime import datetime, timezone

from .evaluation import EvaluationRunner
from .full_text import CORPUS_LOCK
from .optimization import OptimizationAgent, ProposalValidationExhausted
from .paid_schedule import wait_for_off_peak, unattended_authorization
from .policy import MAX_EVALS, candidate_rank


def _save_state(store, experiment_id, **state):
    with store.connection() as connection:
        connection.execute('BEGIN IMMEDIATE')
        row = connection.execute('SELECT result_json FROM experiments WHERE id=?', (experiment_id,)).fetchone()
        result = json.loads(row['result_json'])
        result['optimization_cycle'] = {**result.get('optimization_cycle', {}), **state,
            'updated_at': datetime.now(timezone.utc).isoformat()}
        connection.execute('UPDATE experiments SET result_json=? WHERE id=?',
                           (json.dumps(result, ensure_ascii=False, allow_nan=False), experiment_id))


def claim_cycle(store, experiment_id, *, current_round_only=False):
    """Called before starting the worker, so duplicate clicks cannot own two cycles."""
    with CORPUS_LOCK, store.connection() as connection:
        connection.execute('BEGIN IMMEDIATE')
        experiment = store.experiment(experiment_id, light=True)
        if not experiment:
            raise ValueError('实验不存在')
        store.require_current_baseline(experiment['baseline_run_id'], connection)
        if experiment['result'].get('optimization_cycle', {}).get('status') == 'running':
            raise ValueError('优化批次正在运行')
        if experiment['status'] == 'generating' or any(c['status'] in {'queued', 'running'} for c in experiment['candidates']):
            raise ValueError('当前方案或评测仍在运行')
        if experiment['result'].get('report_confirmation'):
            raise ValueError('报告已确认，不能继续改变实验')
        if current_round_only and not any(c['reasoning'].get('candidate_label') in {'A','B','C'} for c in experiment['candidates']):
            raise ValueError('当前没有可续跑的 A/B/C 方案')
        state = {'status':'running', 'phase':'analysis', 'owner_pid':os.getpid(), 'current_round_only':current_round_only,
                 'resume_stopped_runs':[c['result']['evaluation_run_id'] for c in experiment['candidates']
                     if c['status']=='failed' and c['result'].get('stop_request') and c['result'].get('evaluation_run_id')],
                 'used':experiment['evaluation_budget']['used'],
                 'remaining':max(0, MAX_EVALS-experiment['evaluation_budget']['used']),
                 'reserved_for_d':1, 'last_error':None}
        result = {**experiment['result'], 'optimization_cycle':state}
        from .paid_policy import current_binding
        if current_binding():result['paid_run']=current_binding()
        connection.execute('UPDATE experiments SET result_json=? WHERE id=?',
                           (json.dumps(result, ensure_ascii=False), experiment_id))
    from .paid_schedule import clear_run_now
    for kind in ('cycle:', 'agent:'):
        clear_run_now(store, kind + experiment_id)
    return state


def check_cycle_stop(store, experiment_id):
    state=(store.experiment(experiment_id,light=True) or {}).get('result',{}).get('optimization_cycle',{})
    if state.get('status')=='running' and state.get('stop_request'):
        raise InterruptedError('用户停止运行，断点已保存')


def request_cycle_stop(store, experiment_id):
    with CORPUS_LOCK, store.connection() as connection:
        connection.execute('BEGIN IMMEDIATE')
        row=connection.execute('SELECT result_json FROM experiments WHERE id=?',(experiment_id,)).fetchone()
        if not row:raise ValueError('实验不存在')
        result=json.loads(row['result_json'])
        state=result.get('optimization_cycle',{})
        if state.get('status')=='running':
            state.setdefault('stop_request',{'requested_at':datetime.now(timezone.utc).isoformat(),'reason':'用户停止运行'})
            connection.execute('UPDATE experiments SET result_json=? WHERE id=?',(json.dumps(result,ensure_ascii=False),experiment_id))
        runs=connection.execute("""SELECT e.id FROM evaluation_runs e JOIN candidate_configs c
            ON json_extract(e.config_json,'$.candidate_id')=c.id
            WHERE c.experiment_id=? AND e.status IN ('queued','running')""",(experiment_id,)).fetchall()
    for run in runs:store.request_evaluation_stop(run['id'])
    return store.experiment(experiment_id,light=True)['result'].get('optimization_cycle',{})


def run_until_qualified(store, runtime, experiment_id, *, claimed=False):
    """Continue the authorized batch, reusing saved Sandbox checkpoints."""
    from .paid_run import current_paid_run
    binding=store.experiment(experiment_id,light=True)['result'].get('paid_run')
    if binding and current_paid_run() is None:
        from .paid_policy import restore_paid_context
        with restore_paid_context(store,binding):
            return run_until_qualified(store,runtime,experiment_id,claimed=claimed)
    if not claimed:
        claim_cycle(store, experiment_id)
    runner, agent = EvaluationRunner(store, runtime), OptimizationAgent(store, runtime.provider)
    empty_rounds = 0
    state = dict(store.experiment(experiment_id, light=True)['result'].get('optimization_cycle', {}))
    state.update(owner_pid=os.getpid(), worker_thread=threading.get_ident())

    def save(status, phase, error=None):
        experiment = store.experiment(experiment_id, light=True)
        used = experiment['evaluation_budget']['used']
        state.update(status=status, phase=phase, used=used, remaining=max(0, MAX_EVALS-used),
                     reserved_for_d=1, last_error=error,
                     round=max([c['reasoning'].get('round', 1) for c in experiment['candidates']] or [0]))
        _save_state(store, experiment_id, **state)
        return dict(state)

    def advance_qualified(experiment, qualified):
        confirmation = experiment['result'].get('report_confirmation')
        authorization = unattended_authorization(store)
        if not confirmation:
            for candidate in experiment['candidates']:
                if candidate['status']=='generated' and candidate['reasoning'].get('candidate_label') in {'A','B','C'}:
                    store.skip_candidate(candidate['id'], '自动循环', '出现合格方案，已跳过（未运行）', automatic=True)
            if not authorization.get('enabled'):
                return save('qualified', 'review')
            winner = min(qualified, key=candidate_rank)
            actor = '按用户授权自动确认：' + authorization['actor']
            store.confirm_experiment_report(experiment_id, winner['id'], actor)
        if not authorization.get('enabled'):
            return save('qualified', 'review')
        check_cycle_stop(store,experiment_id)
        save('running', 'composite')
        composite = store.create_composite(experiment_id, runtime.provider)
        if composite.get('status') in {'analyzing','unknown'}:
            return save('failed', 'composite', 'D分析结果未知，保留记录，不重复付费调用')
        experiment = store.experiment(experiment_id, light=True)
        d = next((c for c in experiment['candidates'] if c['reasoning'].get('candidate_label')=='D'), None)
        if d is None or d['status']=='evaluated':
            store.refresh_recommendation(experiment_id)
            return save('recommended', 'before_release')
        return None

    try:
        while True:
            check_cycle_stop(store,experiment_id)
            experiment = store.experiment(experiment_id, light=True)
            store.require_current_baseline(experiment['baseline_run_id'])
            qualified = [c for c in experiment['candidates'] if c['reasoning'].get('candidate_label') in {'A','B','C'}
                         and c['status']=='evaluated' and c['result'].get('qualification',{}).get('qualified') is True]
            if qualified:
                if terminal := advance_qualified(experiment, qualified):
                    return terminal
                experiment = store.experiment(experiment_id, light=True)
            labels = {'D'} if qualified else {'A','B','C'}
            pending = [c for c in experiment['candidates'] if c['reasoning'].get('candidate_label') in labels
                       and (c['status'] in {'generated','running'} or c['status']=='failed' and c['result'].get('evaluation_run_id'))]
            if qualified and not pending:
                return save('failed','composite','D没有可安全续跑的结果或断点')
            for candidate in pending:
                check_cycle_stop(store,experiment_id)
                limit = MAX_EVALS if candidate['reasoning'].get('candidate_label')=='D' else MAX_EVALS-1
                if candidate['status']=='generated' and store.experiment(experiment_id, light=True)['evaluation_budget']['used'] >= limit:
                    store.skip_candidate(candidate['id'], '自动循环', 'A/B/C预算已用完，D保留一次；已跳过（未运行）', automatic=True)
                    return save('budget_exhausted', 'review')
                save('running', 'sandbox')
                finished = candidate
                while True:
                    if finished['status']=='running':
                        runner.recover_run(finished['result']['evaluation_run_id'])
                        finished = store.candidate(candidate['id'])
                    elif finished['status']=='generated':
                        finished = runner.run_candidate(candidate['id'], automatic=True)
                    check_cycle_stop(store,experiment_id)
                    if finished['status']=='evaluated':break
                    run = store.evaluation_run(finished['result'].get('evaluation_run_id'))
                    if not run:
                        return save('failed','sandbox','试跑没有可用断点，不能安全续跑')
                    result = run['result']
                    if result.get('stop_request') and run['id'] not in state.get('resume_stopped_runs',[]):
                        return save('stopped','sandbox','用户已停止试跑，保留断点')
                    errors=result.get('technical_errors',[])
                    if any(e.get('provider_error',{}).get('status_code') in {400,401,402,403}
                           or e.get('provider_error',{}).get('http_status') in {400,401,402,403} for e in errors):
                        return save('failed','sandbox',run.get('error_message') or 'Provider请求、权限或余额错误，已停止')
                    error = run.get('error_message') or str(result.get('technical_errors') or '试跑未完整结束')
                    failures = state.setdefault('sandbox_recovery', {})
                    recovery = failures.setdefault(candidate['id'], {'resumes':0, 'error':error})
                    if recovery['error'] != error:
                        recovery.update(error=error, resumes=0)
                    if recovery['resumes'] >= 2:
                        return save('failed','sandbox',f'同一故障连续2次续跑仍未恢复：{error}')
                    plan = runner.candidate_resume_plan(candidate['id'])
                    if not plan['can_resume']:
                        return save('failed','sandbox',plan.get('reason') or '冻结身份或费用账本不允许续跑')
                    recovery['resumes'] += 1
                    save('running','sandbox',f"断点续跑第{recovery['resumes']}次：{error}")
                    finished = runner.run_candidate(candidate['id'], automatic=True)
                if finished['result'].get('qualification',{}).get('qualified') is True:
                    break
            experiment = store.experiment(experiment_id, light=True)
            if any(c['status']=='evaluated' and c['result'].get('qualification',{}).get('qualified') is True for c in experiment['candidates']):
                continue
            if state.get('current_round_only'):
                return save('round_completed','review')
            if experiment['evaluation_budget']['used'] >= MAX_EVALS-1:
                return save('budget_exhausted', 'review')
            save('running', 'analysis')
            before = len(experiment['candidates'])
            try:
                def price_state(pause):
                    state['price_pause']=pause
                    save('running','analysis')
                wait_for_off_peak(store,'cycle:'+experiment_id,price_state,lambda:check_cycle_stop(store,experiment_id))
                agent.generate(experiment['baseline_run_id'], experiment_id=experiment_id)
            except ProposalValidationExhausted as error:
                return save('analysis_exhausted','analysis',str(error))
            experiment = store.experiment(experiment_id, light=True)
            empty_rounds = empty_rounds+1 if len(experiment['candidates'])==before else 0
            if empty_rounds >= 3:
                return save('analysis_exhausted', 'analysis', '连续3轮没有合法草案，已停止；试跑预算未额外扣减')
    except InterruptedError as error:
        return save('stopped',state.get('phase','sandbox'),str(error))
    except Exception as error:
        return save('failed', state.get('phase','analysis'), str(error))


def recover_optimization_cycles(store, runtime):
    """Restart only persisted authorized cycles whose worker has exited."""
    with store.connection() as connection:
        rows = connection.execute("SELECT id,json_extract(result_json,'$.optimization_cycle') cycle FROM experiments WHERE json_extract(result_json,'$.optimization_cycle.status')='running'").fetchall()
    for row in rows:
        state = json.loads(row['cycle'])
        owner = state.get('owner_pid')
        if owner == os.getpid():
            if any(t.ident==state.get('worker_thread') and t.is_alive() for t in threading.enumerate()):continue
            # A claim made by this process has not entered its thread yet.
            if not state.get('worker_thread'):continue
        elif type(owner) is int:
            try:os.kill(owner,0)
            except ProcessLookupError:pass
            except PermissionError:continue
            else:continue
        with CORPUS_LOCK, store.connection() as connection:
            connection.execute('BEGIN IMMEDIATE')
            current = connection.execute('SELECT result_json FROM experiments WHERE id=?',(row['id'],)).fetchone()
            context = json.loads(current['result_json'])
            if context.get('optimization_cycle') != state:continue
            context['optimization_cycle'].update(owner_pid=os.getpid(), worker_thread=None)
            connection.execute('UPDATE experiments SET result_json=? WHERE id=?',(json.dumps(context,ensure_ascii=False),row['id']))
        threading.Thread(target=run_until_qualified,args=(store,runtime,row['id']),kwargs={'claimed':True},daemon=True).start()


def recover_agent_generations(store, runtime):
    """Recover standalone generation; active batch generations belong to their cycle."""
    with store.connection() as connection:
        rows=connection.execute("SELECT id,baseline_run_id,json_extract(result_json,'$.agent_generation.owner_pid') owner_pid FROM experiments WHERE status='generating' AND coalesce(json_extract(result_json,'$.optimization_cycle.status'),'')!='running'").fetchall()
    def recover(row):
        try:OptimizationAgent(store,runtime.provider).generate(row['baseline_run_id'],experiment_id=row['id'])
        except Exception:logging.exception('Agent generation recovery failed: %s',row['id'])
    for row in rows:
        owner=row['owner_pid']
        if type(owner) is int:
            try:os.kill(owner,0)
            except ProcessLookupError:pass
            except PermissionError:continue
            else:continue
        threading.Thread(target=recover,args=(dict(row),),daemon=True).start()
