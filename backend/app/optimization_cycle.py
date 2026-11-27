"""Authorized optimization loop; unattended work always stops before release."""
import json
import logging
import os
import threading
from contextvars import ContextVar
from datetime import datetime, timezone

from . import rules, task_leases
from .agent_mechanism import CONTRACT as MECHANISM_CONTRACT
from .agent_round_contract import layered, layered_winner
from .evaluation import EvaluationRunner
from .full_text import CORPUS_LOCK
from .optimization import OptimizationAgent, ProposalValidationExhausted
from .paid_schedule import wait_for_off_peak, unattended_authorization
from .policy import MAX_EVALS, candidate_rank, gate2_self_check_authorized


_pending_cycle = ContextVar('pending_cycle_lease', default=None)


def cycle_occupied(store, experiment):
    if not experiment:
        return False
    with store.connection() as connection:
        return task_leases.cycle_active(connection, experiment['id'],
                                        experiment['result'].get('optimization_cycle') or {})


def candidate_occupied(connection, candidate):
    run_id = candidate['result'].get('evaluation_run_id')
    if not run_id:
        return False
    run = connection.execute('SELECT * FROM evaluation_runs WHERE id=?', (run_id,)).fetchone()
    return run is not None and task_leases.evaluation_active(connection, run)


def _save_state(store, experiment_id, **state):
    with store.connection() as connection:
        connection.execute('BEGIN IMMEDIATE')
        row = connection.execute('SELECT result_json FROM experiments WHERE id=?', (experiment_id,)).fetchone()
        key = 'cycle:' + experiment_id
        task_leases.require(connection, key, task_leases.current(store, key), legacy=True)
        result = json.loads(row['result_json'])
        previous = result.get('optimization_cycle', {})
        updated = {**previous, **state, 'updated_at': datetime.now(timezone.utc).isoformat()}
        scope = updated.get('workflow_scope', {})
        if (scope.get('target') == 'release' and state.get('status') == 'recommended'
                and result.get('decision_contract_version') != '126c'):
            # The lease must remain recoverable between recommendation and retest.
            updated.update(status='running', phase='final_retest')
        if scope:
            changes = ('status', 'phase', 'active_candidate')
            audit = previous.get('workflow_audit', [])
            if any(updated.get(field) != previous.get(field) for field in changes):
                audit = [*audit, {'at': updated['updated_at'], **{field: updated.get(field) for field in changes},
                                 'reason': updated.get('last_error')}]
            updated['workflow_audit'] = audit
        result['optimization_cycle'] = updated
        connection.execute('UPDATE experiments SET result_json=? WHERE id=?',
                           (json.dumps(result, ensure_ascii=False, allow_nan=False), experiment_id))


        cycle = result['optimization_cycle']
        status = cycle.get('status')
        if status in {'running', 'recovering'}:
            business = task_leases.progress_state(cycle)
        elif status == 'stopped':
            business = 'paused'
        elif status in {'recommended', 'qualified', 'round_completed', 'round_limit', 'completed', 'awaiting_release_approval'}:
            business = 'completed'
        else:
            business = 'blocked' if status in {'blocked', 'budget_exhausted'} else 'failed'
        task_leases.update_state(connection, store, key, business)
    from .paid_run import current_paid_run
    if 'phase' in state and (ledger := current_paid_run()):
        ledger.phase = updated['phase']


def claim_cycle(store, experiment_id, *, current_round_only=False, workflow_scope=None):
    """Called before starting the worker, so duplicate clicks cannot own two cycles."""
    with CORPUS_LOCK, store.connection() as connection:
        connection.execute('BEGIN IMMEDIATE')
        experiment = store.experiment(experiment_id, light=True)
        if not experiment:
            raise ValueError('实验不存在')
        if experiment['status'] == 'archived':
            raise ValueError('实验已归档')
        store.require_current_baseline(experiment['baseline_run_id'], connection)
        prior_cycle = experiment['result'].get('optimization_cycle', {})
        if task_leases.cycle_active(connection, experiment_id, prior_cycle):
            raise ValueError('优化批次正在运行')
        if (task_leases.agent_active(connection, experiment_id, experiment['result'], legacy_generating=experiment['status'] == 'generating')
                or task_leases.active(connection, 'composite:' + experiment_id)
                or any(candidate_occupied(connection, c) for c in experiment['candidates'])):
            raise ValueError('当前方案或评测仍在运行')
        if workflow_scope and workflow_scope.get('target') is None:
            saved_scope = prior_cycle.get('workflow_scope') or {}
            if (prior_cycle.get('status') in {*task_leases.ACTIVE_STATES, 'blocked', 'stopped', 'failed'}
                    and saved_scope.get('target') in {'current_round', 'candidate', 'release'}):
                workflow_scope = {**saved_scope, 'entry': workflow_scope['entry']}
            else:
                workflow_scope = {**workflow_scope, 'target': 'cycle'}
            current_round_only = workflow_scope['target'] == 'current_round'
        v126 = experiment['result'].get('decision_contract_version') == '126c'
        if v126 and workflow_scope and workflow_scope['target'] == 'candidate':
            raise ValueError('126c 请用轮次或统一流程执行 Sandbox')
        confirmation = experiment['result'].get('report_confirmation')
        if confirmation:
            winner = next((c for c in experiment['candidates'] if c['id'] == confirmation['winner_id']), None)
            if not winner or winner['status'] != 'evaluated' or not winner['result'].get('qualification', {}).get('qualified'):
                raise ValueError('Winner资格失效，不能续跑D')
            if current_round_only:
                raise ValueError('报告已确认，只能续跑D')
        if workflow_scope:
            workflow_scope = dict(workflow_scope)
            if workflow_scope['target'] == 'next_round':
                if confirmation:
                    raise ValueError('报告已确认，不能继续改变实验')
                current_round = max((c['reasoning'].get('round', 1) for c in experiment['candidates']), default=0)
                workflow_scope['round'] = 1 if experiment['result'].get('seed_round_planned') is False else current_round + 1
            if workflow_scope['target'] == 'candidate' and not any(
                    c['id'] == workflow_scope['candidate_id'] for c in experiment['candidates']):
                raise ValueError('Candidate 不属于本实验')
        if current_round_only and not any(c['reasoning'].get('candidate_label') in {'A','B','C'} for c in experiment['candidates']):
            raise ValueError('当前没有可续跑的 A/B/C 方案')
        state = {'status':'running', 'phase':'composite' if confirmation else 'analysis', 'owner_pid':os.getpid(), 'current_round_only':current_round_only,
                 'resume_stopped_runs':[c['result']['evaluation_run_id'] for c in experiment['candidates']
                     if c['status']=='failed' and c['result'].get('stop_request') and c['result'].get('evaluation_run_id')],
                 'used':experiment['evaluation_budget']['used'],
                 'remaining':None if v126 else max(0, MAX_EVALS-experiment['evaluation_budget']['used']),
                 'reserved_for_d':experiment['evaluation_budget']['reserved_for_d'], 'last_error':None}
        if workflow_scope:
            if workflow_scope['target'] == 'release' and prior_cycle.get('phase') in {
                    'before_release', 'final_retest', 'release', 'production_smoke', 'published', 'unchanged'}:
                state['phase'] = 'final_retest'
            state.update(workflow_scope=workflow_scope, workflow_audit=[*prior_cycle.get('workflow_audit', []), {
                'at': datetime.now(timezone.utc).isoformat(), 'status': 'running', 'phase': state['phase'],
                'scope': workflow_scope,
            }])
        if v126 and prior_cycle.get('status') == 'budget_exhausted':
            state.update(reopen_paid_ledger=True, resume_blocked_runs=[
                c['result'].get('evaluation_run_id') for c in experiment['candidates'] if c['status'] == 'failed'])
        if prior_cycle.get('status') in {'blocked', 'stopped'} or (
                workflow_scope and prior_cycle.get('external_runner') and prior_cycle.get('status') == 'failed'):
            state['reopen_paid_ledger'] = True
        blocked = [c['result']['evaluation_run_id'] for c in experiment['candidates']
                   if c['status']=='failed' and c['result'].get('evaluation_run_id')
                   and c['result'].get('auto_recovery', {}).get('state') == 'blocked']
        if blocked:
            state.update(resume_blocked_runs=list(set(state.get('resume_blocked_runs', [])) | set(blocked)), reopen_paid_ledger=True)
        if layered(experiment['result']):
            previous_decision = experiment['result'].get('optimization_cycle', {}).get('staged_decision')
            if previous_decision:
                state['staged_decision'] = previous_decision
        token = task_leases.claim(connection, 'cycle:' + experiment_id)
        result = {**experiment['result'], 'optimization_cycle':state}
        from .paid_policy import current_binding
        if binding := current_binding():
            if result.get('paid_run') not in (None, binding):
                raise ValueError('实验已绑定另一份费用授权')
            result['paid_run'] = binding
        connection.execute('UPDATE experiments SET result_json=? WHERE id=?',
                           (json.dumps(result, ensure_ascii=False), experiment_id))
    _pending_cycle.set((store.database_path, experiment_id, token))
    from .paid_schedule import clear_run_now
    for kind in ('cycle:', 'agent:'):
        clear_run_now(store, kind + experiment_id)
    return state


def take_cycle_claim(store, experiment_id):
    pending = _pending_cycle.get()
    if pending and pending[:2] == (store.database_path, experiment_id):
        _pending_cycle.set(None)
        return pending[2]
    return None


def read_cycle_state(store, experiment_id):
    if reader := getattr(store, 'optimization_cycle_state', None):
        return reader(experiment_id)
    return (store.experiment(experiment_id, light=True) or {}).get('result', {}).get('optimization_cycle', {})


def check_cycle_stop(store, experiment_id):
    task_leases.check(store)
    state = read_cycle_state(store, experiment_id)
    if state.get('stop_request') and state.get('status') in {'running', 'queued', 'recovering', 'stopped'}:
        raise InterruptedError('用户停止运行，断点已保存')


def request_cycle_stop(store, experiment_id):
    with CORPUS_LOCK, store.connection() as connection:
        connection.execute('BEGIN IMMEDIATE')
        row = connection.execute('SELECT result_json FROM experiments WHERE id=?', (experiment_id,)).fetchone()
        if not row:
            raise ValueError('实验不存在')
        result = json.loads(row['result_json'])
        state = result.get('optimization_cycle', {})
        active = task_leases.cycle_active(connection, experiment_id, state)
        if state.get('status') in (*task_leases.ACTIVE_STATES, 'blocked') or active:
            state.setdefault('stop_request', {'requested_at': datetime.now(timezone.utc).isoformat(), 'reason': '用户停止运行'})
            if not active:
                state['status'] = 'stopped'
                task_leases.mark_paused(connection, 'cycle:' + experiment_id)
                if not task_leases.agent_active(connection, experiment_id, result):
                    task_leases.mark_paused(connection, 'agent:' + experiment_id)
            result['optimization_cycle'] = state
            connection.execute('UPDATE experiments SET result_json=? WHERE id=?', (json.dumps(result, ensure_ascii=False), experiment_id))
            runs = connection.execute("""SELECT e.id FROM evaluation_runs e JOIN candidate_configs c
                ON json_extract(e.config_json,'$.candidate_id')=c.id
                WHERE c.experiment_id=? AND e.status IN ('queued','running','recovering','completed')
                AND json_extract(c.result_json,'$.evaluation_run_id')=e.id""", (experiment_id,)).fetchall()
            for run in runs:
                store.request_evaluation_stop(run['id'], connection=connection)
    return state


def run_until_qualified(store, runtime, experiment_id, *, claimed=False, lease_token=None):
    """Continue the authorized batch, reusing saved Sandbox checkpoints."""
    from .workflow_engine import WorkflowEngine

    engine = WorkflowEngine(store, runtime, experiment_id)
    key = 'cycle:' + experiment_id
    if task_leases.current(store, key):
        return _run_owned_cycle(store, runtime, experiment_id)
    if not claimed and not lease_token:
        claim_cycle(store, experiment_id)
    token = lease_token or take_cycle_claim(store, experiment_id)
    try:
        with task_leases.work(store, key, token):
            return _run_owned_cycle(store, runtime, experiment_id)
    except task_leases.LeaseLost:
        return engine.state()


def _run_owned_cycle(store, runtime, experiment_id):
    from .workflow_engine import WorkflowEngine

    return WorkflowEngine(store, runtime, experiment_id).run()


def _candidate_block_error(run):
    result = run['result']
    recovery = result.get('auto_recovery', {})
    if recovery.get('state') == 'blocked' or any(
            (error.get('provider_error') or {}).get('http_status') in {400, 401, 402, 403}
            for error in result.get('technical_errors', [])):
        return run.get('error_message') or recovery.get('error') or 'Provider请求、权限或余额错误，已停止'
    return None


def _run_until_qualified(store, runtime, experiment_id):
    from .providers import permanent_provider_error
    from .workflow_engine import WorkflowEngine
    engine = WorkflowEngine(store, runtime, experiment_id)
    runner, agent = EvaluationRunner(store, runtime), OptimizationAgent(store, runtime.provider, runtime=runtime)
    empty_rounds = 0
    state = dict(store.experiment(experiment_id, light=True)['result'].get('optimization_cycle', {}))
    state.pop('provider_retry', None)
    state.pop('worker_thread', None)

    def save(status, phase, error=None):
        experiment = store.experiment(experiment_id, light=True)
        used = experiment['evaluation_budget']['used']
        legacy_staged = (experiment['result'].get('round_policy', {}).get('stop_rule') == STAGED_RULE
                         and not layered(experiment['result']))
        if phase != 'sandbox':
            state['active_candidate'] = None
        state.update(status=status, phase=phase, used=used, remaining=max(0, MAX_EVALS-used),
                     reserved_for_d=int(not legacy_staged), last_error=error,
                     round=max([c['reasoning'].get('round', 1) for c in experiment['candidates']] or [0]))
        if status == 'blocked':
            retry = experiment['result'].get('optimization_cycle', {}).get('provider_retry') or {}
            state['provider_retry'] = {**retry, 'state':'blocked', 'error':error,
                'resume_hint':'排除所列故障后，使用原实验和授权从断点手动续跑'}
        if experiment['result'].get('mechanism_contract') == MECHANISM_CONTRACT:
            from .agent_round_contract import check_commitment, previous_commitment

            if phase == 'before_release' and status == 'recommended':
                if state.get('staged_decision', {}).get('decision') == 'finish_winner' and layered(experiment['result']):
                    action, reason = 'stop', '按逐层规则保留 Winner'
                else:
                    action = 'D'
                    reason = ('按逐层规则转入 D' if layered(experiment['result'])
                              else '按合格方案数、轮次和剩余预算转入 D 决策')
            elif status in {'stopped', 'qualified', 'agent_failed', 'analysis_exhausted', 'budget_exhausted', 'round_limit'}:
                action, reason = 'stop', error or '按授权或实验预算停止本次循环'
            else:
                action = None
            if action:
                previous = previous_commitment(experiment['result'], state['round'] + 1)
                if check := check_commitment(previous, action, reason=reason):
                    state['hypothesis_terminal_check'] = check
        _save_state(store, experiment_id, **state)
        return dict(state)

    def advance_qualified(experiment, qualified, *, do_composite=True):
        confirmation = experiment['result'].get('report_confirmation')
        current_contract = experiment['result'].get('decision_contract_version') == '109c'
        authorization = engine.release_authorization() or unattended_authorization(store)
        if not confirmation:
            for candidate in experiment['candidates']:
                if candidate['status']=='generated' and candidate['reasoning'].get('candidate_label') in {'A','B','C'}:
                    store.skip_candidate(candidate['id'], '自动循环', '出现合格方案，已跳过（未运行）', automatic=True)
            from .agent_strategy import conclude_round
            conclude_round(store,runtime,experiment_id)
            rule = rules.AUTHORIZATION['gate2']
            if not gate2_self_check_authorized(authorization):
                return save('qualified', 'review')
            winner = min(qualified, key=candidate_rank)
            store.confirm_experiment_report(experiment_id, winner['id'], rule['self_check_executor'],
                                            audit_note=authorization.get('audit_note'))
        if not current_contract and not authorization.get('enabled'):
            return save('qualified', 'review')
        if not do_composite:
            store.refresh_recommendation(experiment_id)
            return save('recommended', 'before_release')
        check_cycle_stop(store,experiment_id)
        save('running', 'composite')
        composite = engine.generate_composite()
        if composite.get('outcome') == 'provider_blocked':
            return save('blocked', 'composite', composite.get('reason'))
        if composite.get('status') in {'analyzing','unknown'}:
            return save('failed', 'composite', 'D分析结果未知，保留记录，不重复付费调用')
        experiment = store.experiment(experiment_id, light=True)
        d = next((c for c in experiment['candidates'] if c['reasoning'].get('candidate_label')=='D'), None)
        if d is None or d['status']=='evaluated':
            if current_contract and d:
                from .agent_strategy import conclude_round
                save('running', 'composite_review')
                try:
                    conclude_round(store, runtime, experiment_id, final_d=True)
                except ValueError as error:
                    return save('blocked', 'composite_review', str(error))
            store.refresh_recommendation(experiment_id)
            return save('recommended', 'before_release')
        return None

    if store.experiment(experiment_id, light=True)['result'].get('round_policy', {}).get('stop_rule') == STAGED_RULE:
        return _run_staged(store, runtime, experiment_id, state, save, advance_qualified, runner, agent)

    try:
        while True:
            check_cycle_stop(store,experiment_id)
            experiment = store.experiment(experiment_id, light=True)
            store.require_current_baseline(experiment['baseline_run_id'])
            qualified = [c for c in experiment['candidates'] if c['reasoning'].get('candidate_label') in {'A','B','C'}
                         and c['status']=='evaluated' and c['result'].get('qualification',{}).get('qualified') is True]
            policy = experiment['result'].get('round_policy', {})
            full_rounds = policy.get('mode') == 'full_rounds'
            round_only = state.get('current_round_only')
            finishing = not round_only and (not full_rounds or bool(experiment['result'].get('report_confirmation'))
                                            or bool(state.get('proposal_round_end')))
            if qualified and finishing:
                if terminal := advance_qualified(experiment, qualified):
                    return terminal
                experiment = store.experiment(experiment_id, light=True)
            labels = {'D'} if qualified and finishing else {'A','B','C'}
            pending = [c for c in experiment['candidates'] if c['reasoning'].get('candidate_label') in labels
                       and (c['status'] in {'generated','running'} or c['status']=='failed' and c['result'].get('evaluation_run_id'))]
            if round_only:
                latest = max((c['reasoning'].get('round', 1) for c in experiment['candidates']), default=0)
                pending = [c for c in pending if c['reasoning'].get('round', 1) == latest]
            if qualified and finishing and not pending:
                return save('failed','composite','D没有可安全续跑的结果或断点')
            for candidate in pending:
                check_cycle_stop(store,experiment_id)
                limit = MAX_EVALS if candidate['reasoning'].get('candidate_label')=='D' else MAX_EVALS-1
                if candidate['status']=='generated' and store.experiment(experiment_id, light=True)['evaluation_budget']['used'] >= limit:
                    for unrun in store.experiment(experiment_id,light=True)['candidates']:
                        if unrun['status']=='generated' and unrun['reasoning'].get('candidate_label') in {'A','B','C'}:
                            store.skip_candidate(unrun['id'], '用户', 'A/B/C预算已用完，D保留一次；已跳过（未运行）', automatic=True)
                    from .agent_strategy import conclude_round
                    conclude_round(store,runtime,experiment_id)
                    if full_rounds:
                        break
                    return save('budget_exhausted', 'review')
                state['active_candidate'] = candidate['id']
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
                    if blocked := _candidate_block_error(run):
                        if run['id'] in state.get('resume_blocked_runs', []):
                            finished = runner.run_candidate(candidate['id'], automatic=True, manual_resume=True)
                            continue
                        return save('blocked','sandbox',blocked)
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
                if not round_only and not full_rounds and finished['result'].get('qualification',{}).get('qualified') is True:
                    break
            experiment = store.experiment(experiment_id, light=True)
            if not round_only and not full_rounds and any(c['status']=='evaluated' and c['result'].get('qualification',{}).get('qualified') is True for c in experiment['candidates']):
                for candidate in experiment['candidates']:
                    if candidate['status']=='generated' and candidate['reasoning'].get('candidate_label') in {'A','B','C'}:
                        store.skip_candidate(candidate['id'], '用户', '出现合格方案，已跳过（未运行）', automatic=True)
            from .agent_strategy import conclude_round
            conclude_round(store,runtime,experiment_id)
            experiment = store.experiment(experiment_id, light=True)
            qualified = [c for c in experiment['candidates'] if c['reasoning'].get('candidate_label') in {'A','B','C'}
                         and c['status']=='evaluated' and c['result'].get('qualification',{}).get('qualified') is True]
            if state.get('current_round_only'):
                # 只跑本轮：本轮跑完、复盘写完就停，不因出现合格方案而自动确认报告或进 D。
                return save('round_completed','review')
            if full_rounds:
                if experiment['result'].get('report_confirmation'):
                    continue
                number = max((c['reasoning'].get('round',1) for c in experiment['candidates']), default=0)
                if number >= policy['max_rounds'] or experiment['evaluation_budget']['used'] >= MAX_EVALS-1:
                    if not qualified:
                        return save('budget_exhausted','review')
                    if terminal := advance_qualified(experiment, qualified):
                        return terminal
                    continue
            elif qualified:
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
                if experiment['result'].get('mechanism_contract') != MECHANISM_CONTRACT:
                    wait_for_off_peak(store,'cycle:'+experiment_id,price_state,lambda:check_cycle_stop(store,experiment_id))
                generated = engine.generate_next(agent)
                if stop := (generated or {}).get('result', {}).get('decision_stop'):
                    return save('stopped', 'review', stop['reason'])
            except ProposalValidationExhausted as error:
                if not full_rounds:
                    return save('analysis_exhausted','analysis',str(error))
                number = max((c['reasoning'].get('round',1) for c in experiment['candidates']), default=0) + 1
                failures = state.setdefault('proposal_generation_failures', [])
                failures.append({'round':number, 'reason':str(error), 'sandbox_budget_used':0,
                                 'at':datetime.now(timezone.utc).isoformat()})
                if sum(f['round'] == number for f in failures) < 3:
                    save('running','analysis',str(error))
                    continue
                if not qualified:
                    return save('analysis_exhausted','analysis',str(error))
                state['proposal_round_end'] = {'round':number, 'reason':f'第 {number} 轮未能生成合法方案'}
                save('running','review',state['proposal_round_end']['reason'])
                continue
            experiment = store.experiment(experiment_id, light=True)
            empty_rounds = empty_rounds+1 if len(experiment['candidates'])==before else 0
            if empty_rounds >= 3:
                return save('analysis_exhausted', 'analysis', '连续3轮没有合法草案，已停止；试跑预算未额外扣减')
    except task_leases.LeaseLost:
        raise
    except InterruptedError as error:
        return save('stopped',engine.state().get('phase','sandbox'),str(error))
    except Exception as error:
        return save('blocked' if permanent_provider_error(error) or isinstance(error, ValueError) else 'failed',
                    engine.state().get('phase','analysis'), str(error))


STAGED_RULE = 'staged-v1'


def staged_decision(round_number, qualified_count, used, *, version=None,
                    remaining_count=None, untried_layers=(), has_combination=False):
    """规则总表五.6，纯函数，方便单测。返回 'next_round' / 'composite' / 'finish_winner' / 'agent_failed'。"""
    if layered({'verdict_version': version}):
        if remaining_count == 0 and qualified_count and 'performance' not in untried_layers:
            return 'finish_winner'
        at_limit = round_number >= rules.AGENT['max_rounds'] or used >= MAX_EVALS - 1
        if not at_limit and (round_number == 0 or untried_layers):
            return 'next_round'
        if qualified_count:
            return 'composite' if has_combination and used < MAX_EVALS else 'finish_winner'
        return 'agent_failed'
    if round_number > 0 and qualified_count >= rules.AGENT['min_qualified_for_fusion']:
        return 'composite' if used < MAX_EVALS else 'finish_winner'
    if round_number >= rules.AGENT['single_winner_after_round'] and qualified_count:
        return 'composite' if used < MAX_EVALS else 'finish_winner'
    if round_number < rules.AGENT['single_winner_after_round']:
        return 'next_round' if used < MAX_EVALS else ('finish_winner' if qualified_count else 'agent_failed')
    if round_number < rules.AGENT['max_rounds']:
        return 'next_round' if used < MAX_EVALS else 'agent_failed'
    return 'agent_failed'   # 已到最后一轮且没有合格方案


def _qualified_abc(experiment):
    return [c for c in experiment['candidates'] if c['reasoning'].get('candidate_label') in {'A','B','C'}
            and c['status']=='evaluated' and c['result'].get('qualification',{}).get('qualified') is True]


def layered_stage_facts(store, experiment, baseline, winner, number):
    from . import verdict
    from .agent_inputs import baseline_bad_case_rows, is_optimization_target
    from .agent_mechanism import faults_for_cases, preview_rejection
    from .agent_planning import enabled
    from .agent_round_contract import fault_layer, round_base, round_opportunities, saved_final_map
    from .composite import parameter_diff, pipeline_config
    from .optimization import gate_harming_changes, load_retrieval_preview, require_retrieval_preview
    from .policy import failed_performance_gates, validate_candidate_config

    abc_exhausted = bool(experiment['result'].get('decision_stop'))
    run_id = winner['result']['evaluation_run_id'] if winner else baseline['id']
    final = saved_final_map(store, run_id)
    remaining = {q for q, passed in final.items() if not passed}
    decision_version = experiment['result'].get('bad_case_decision_version')
    fill_round = decision_version == rules.BAD_CASE_DECISION_VERSION
    limit = rules.agent_change_limit(decision_version)
    reference = winner or baseline
    performance_gates = (failed_performance_gates((reference['result'].get('gates') or {}).get('gates'))
                         if rules.uses_bad_case_layers(decision_version) else [])
    if not remaining and not performance_gates:
        return {'remaining_count': 0, 'untried_layers': [], 'has_combination': False}
    candidates = experiment['candidates']
    baseline_config = pipeline_config(baseline['config'])
    base = round_base(baseline_config, candidates, number + 1, winner=winner, use_layered=True)
    failures = [row for row in baseline_bad_case_rows(store, baseline, use_final=True)
                if row['question_id'] in remaining]
    cases = verdict.final_cases(store, run_id)
    present = {row['question_id'] for row in failures}
    references = failures + [{'id': q, 'question_id': q} for q in sorted(remaining - present)]
    faults = faults_for_cases(baseline, cases, references, decision_version=decision_version)
    targets = [{**row, 'mechanism_fault': faults[row['question_id']]} for row in failures
               if row['question_id'] in faults and is_optimization_target(row)]
    current = experiment['result']['parameter_effect_ledger']['current']
    directed = enabled(experiment['result'])
    preview = None
    if not directed:
        foundation = json.loads(baseline['dataset_snapshot_json']).get('corpus_fingerprint')
        preview = load_retrieval_preview(store, baseline['id'], foundation=foundation)
    gates = (baseline['result'].get('gates') or {}).get('gates')
    blocked = [row['config_diff'] for row in gate_harming_changes(candidates, gates)]
    checked = [group for plan in experiment['result'].get('round_planning', {}).values()
               if plan['base_id'] == base['id'] for group in plan['directed_checks']] if directed else []
    if fill_round and directed:
        preview = {'directed_checks': checked}
        blocked.extend(parameter_diff(row['config'], baseline_config)
                       for plan in experiment['result'].get('round_planning', {}).values()
                       for row in plan.get('no_effect', []))
    options = round_opportunities(targets, base, baseline_config, candidates, preview, current, [],
                                 blocked=blocked, use_layered=True, performance_gates=performance_gates,
                                 before_directed_checks=directed, decision_version=decision_version)
    untried = {fault_layer(row['fault']['code']) for row in options.values() if row['available']}
    if not fill_round and not directed and len(base['changes']) < limit:
        remaining_layers = {fault_layer(row['code']) for row in faults.values()}
        if 'generation' in remaining_layers and not any(
                row['source'] == '生成诊断' and row['base_id'] == base['id'] for row in current):
            untried.add('generation')
        if 'retrieval' in remaining_layers:
            try:
                require_retrieval_preview(preview, base['changes'])
            except ValueError:
                untried.add('retrieval')

    combined = False
    if winner:
        winner_config = pipeline_config(winner['config'])
        tried = [pipeline_config(c['config']) for c in candidates]
        for source in _qualified_abc(experiment):
            if source['id'] == winner['id'] or source['result'].get('evaluation_identity') != winner['result']['evaluation_identity']:
                continue
            source_diff = parameter_diff(source['config'], baseline_config)
            if any(source_diff[key] != base['changes'][key] for key in source_diff.keys() & base['changes'].keys()):
                continue
            config = {**winner_config, **source_diff}
            delta = parameter_diff(config, winner_config)
            if (not delta or config in tried or len(delta) > rules.AGENT['max_changed_parameters']
                    or len(parameter_diff(config, baseline_config)) > limit
                    or not validate_candidate_config(config)['valid']):
                continue
            if fill_round and (parameter_diff(config, baseline_config) in blocked
                               or preview_rejection(preview or {}, current, base['id'], delta, base['changes'])):
                continue
            other = saved_final_map(store, source['result'].get('evaluation_run_id'))
            if other.keys() == final.keys() and any(other[q] for q in remaining):
                combined = True
                break
        if abc_exhausted or number >= rules.AGENT['max_rounds'] or experiment['evaluation_budget']['used'] >= MAX_EVALS - 1:
            if directed and not fill_round:
                options = round_opportunities(targets, base, baseline_config, candidates,
                    {'directed_checks': checked}, current, [], blocked=blocked, use_layered=True,
                    performance_gates=performance_gates)
            combined = combined or any(not fill_round or action['decision'] == '有证据'
                                       for row in options.values() for action in row['available'])
    return {'remaining_count': len(remaining), 'untried_layers': [] if abc_exhausted else sorted(untried),
            'has_combination': combined}


def _run_staged(store, runtime, experiment_id, state, save, advance_qualified, runner, agent):
    """按规则总表六.6/六.7 执行分阶段试跑。"""
    from .workflow_engine import WorkflowEngine
    engine = WorkflowEngine(store, runtime, experiment_id)
    from .agent_strategy import conclude_round
    from .providers import permanent_provider_error

    def execute(candidate):
        state['active_candidate'] = candidate['id']
        save('running', 'sandbox')
        finished = candidate
        while True:
            if finished['status']=='running':
                runner.recover_run(finished['result']['evaluation_run_id'])
                finished = store.candidate(candidate['id'])
            elif finished['status']=='generated':
                finished = runner.run_candidate(candidate['id'], automatic=True)
            check_cycle_stop(store,experiment_id)
            if finished['status']=='evaluated':
                return finished, None
            run = store.evaluation_run(finished['result'].get('evaluation_run_id'))
            if not run:
                return None, save('failed','sandbox','试跑没有可用断点，不能安全续跑')
            result = run['result']
            if result.get('stop_request') and run['id'] not in state.get('resume_stopped_runs',[]):
                return None, save('stopped','sandbox','用户已停止试跑，保留断点')
            if blocked := _candidate_block_error(run):
                if run['id'] in state.get('resume_blocked_runs', []):
                    finished = runner.run_candidate(candidate['id'], automatic=True, manual_resume=True)
                    continue
                return None, save('blocked','sandbox',blocked)
            error = run.get('error_message') or str(result.get('technical_errors') or '试跑未完整结束')
            recovery = state.setdefault('sandbox_recovery', {}).setdefault(candidate['id'], {'resumes':0, 'error':error})
            if recovery['error'] != error:
                recovery.update(error=error, resumes=0)
            if recovery['resumes'] >= 2:
                return None, save('failed','sandbox',f'同一故障连续2次续跑仍未恢复：{error}')
            plan = runner.candidate_resume_plan(candidate['id'])
            if not plan['can_resume']:
                return None, save('failed','sandbox',plan.get('reason') or '冻结身份或费用账本不允许续跑')
            recovery['resumes'] += 1
            save('running','sandbox',f"断点续跑第{recovery['resumes']}次：{error}")
            finished = runner.run_candidate(candidate['id'], automatic=True)

    def finish(experiment, qualified, decision):
        if decision == 'agent_failed':
            store.refresh_recommendation(experiment_id)
            return save('agent_failed', 'review', '全部方案都不合格，本次 Agent 优化失败（规则总表五.6）')
        if decision == 'finish_winner' and layered(experiment['result']):
            save('running', 'review')
            return advance_qualified(experiment, qualified, do_composite=False)
        def find_d():
            current = store.experiment(experiment_id, light=True)
            return next((c for c in current['candidates'] if c['reasoning'].get('candidate_label')=='D'), None)
        d = find_d()
        if not (d and d['status'] == 'evaluated'):
            terminal = advance_qualified(experiment, qualified)
            if terminal and terminal.get('status') != 'recommended':
                return terminal
            d = find_d()
        if d is None:
            store.refresh_recommendation(experiment_id)
            return save('recommended', 'before_release')
        if d['status'] != 'evaluated':
            finished, stopped = execute(d)
            if stopped:
                return stopped
        if 'D' not in (store.experiment(experiment_id, light=True)['result'].get('round_conclusions') or {}) or \
                (store.experiment(experiment_id, light=True)['result']['round_conclusions']['D'].get('status') != 'saved'):
            save('running', 'composite_review')
            try:
                conclude_round(store, runtime, experiment_id, final_d=True)
            except ValueError as error:
                return save('blocked', 'composite_review', str(error))
        store.refresh_recommendation(experiment_id)
        return save('recommended', 'before_release')

    try:
        while True:
            check_cycle_stop(store,experiment_id)
            experiment = store.experiment(experiment_id, light=True)
            baseline = store.require_current_baseline(experiment['baseline_run_id'])
            use_layered = layered(experiment['result'])
            if stop := experiment['result'].get('decision_stop'):
                qualified = _qualified_abc(experiment)
                winner = layered_winner(store, baseline, qualified) if use_layered else None
                if not winner:
                    return save('stopped', 'review', stop['reason'])
                used = experiment['evaluation_budget']['used']
                facts = layered_stage_facts(store, experiment, baseline, winner, stop['round'])
                decision = staged_decision(stop['round'], 1, used,
                                           version=experiment['result']['verdict_version'], **facts)
                state['staged_decision'] = {'round': stop['round'], 'qualified': [c['id'] for c in qualified],
                                            'used': used, 'decision': decision, 'winner_id': winner['id'], **facts}
                return finish(experiment, [winner], decision)
            if experiment['result'].get('report_confirmation'):
                terminal = state.get('staged_decision', {}).get('decision')
                return finish(experiment, _qualified_abc(experiment),
                              'finish_winner' if use_layered and terminal == 'finish_winner' else 'composite')
            abc = [c for c in experiment['candidates'] if c['reasoning'].get('candidate_label') in {'A','B','C'}]
            number = max((c['reasoning'].get('round', 1) for c in abc), default=0)
            if use_layered and experiment['result'].get('seed_round_planned') is False:
                number = 0
            current = [c for c in abc if c['reasoning'].get('round', 1) == number]
            if experiment['result'].get('bad_case_decision_version') == rules.BAD_CASE_DECISION_VERSION:
                current.sort(key=lambda c: (c['status'] == 'generated',
                                            c['reasoning'].get('evidence_status') != '有证据'))
            for candidate in current:
                candidate = store.candidate(candidate['id'])
                runnable = candidate['status'] in {'generated','running'} or candidate['status']=='failed' and candidate['result'].get('evaluation_run_id')
                if not runnable:
                    continue
                experiment = store.experiment(experiment_id, light=True)
                budget_limit = MAX_EVALS - int(use_layered)
                if (not use_layered and number >= rules.AGENT['max_rounds'] and _qualified_abc(experiment)
                        or experiment['evaluation_budget']['used'] >= budget_limit and candidate['status']=='generated'):
                    store.skip_candidate(candidate['id'], '自动循环', '最后一轮已出现合格方案或预算用完，未运行', automatic=True)
                    continue
                check_cycle_stop(store,experiment_id)
                finished, stopped = execute(candidate)
                if stopped:
                    return stopped
            if current:
                conclude_round(store, runtime, experiment_id)
            experiment = store.experiment(experiment_id, light=True)
            qualified = _qualified_abc(experiment)
            used = experiment['evaluation_budget']['used']
            if use_layered:
                winner = layered_winner(store, baseline, qualified)
                facts = layered_stage_facts(store, experiment, baseline, winner, number) if number else {}
                decision = staged_decision(number, int(winner is not None), used,
                                           version=experiment['result']['verdict_version'], **facts)
            else:
                decision = staged_decision(number, len(qualified), used)
            state['staged_decision'] = {'round': number, 'qualified': [c['id'] for c in qualified], 'used': used, 'decision': decision,
                                        **({'winner_id': winner['id'] if winner else None, **facts} if use_layered else {})}
            # 用户指定"先跑到第 N 轮"（2026-11-18 17:52：先跑第二轮，不做 D）：N 轮之前一律进下一轮，跑完第 N 轮就停。
            run_to = experiment['result'].get('round_policy', {}).get('user_run_to_round')
            if isinstance(run_to, int) and number:
                if number < run_to and used < MAX_EVALS and decision != 'next_round':
                    state['staged_decision']['rule_decision'] = decision
                    state['staged_decision']['user_override'] = f'用户要求先跑到第 {run_to} 轮，本轮不按规则转入 {decision}'
                    decision = state['staged_decision']['decision'] = 'next_round'
                elif number >= run_to:
                    return save('round_completed', 'review', f'已跑到用户指定的第 {run_to} 轮，按要求停下；规则判定的下一步：{decision}')
            if number and state.get('current_round_only'):
                # 只跑本轮（用户 2026-11-18：终点是第一轮 3 个 Candidate 跑完）：本轮统计和复盘做完就停，
                # 规则给出的下一步（下一轮 / D）只记录在 staged_decision，不自动执行。
                return save('round_completed', 'review', f'第 {number} 轮已跑完，按要求停下；规则判定的下一步：{decision}')
            if decision != 'next_round':
                return finish(experiment, [winner] if use_layered and winner else qualified, decision)
            max_rounds = experiment['result'].get('round_policy', {}).get('max_rounds')
            if isinstance(max_rounds, int) and number >= max_rounds:
                # 用户可指定本次只跑到第 N 轮（2026-11-17：只跑第 2、3 轮）；到点停下汇报，不自动开下一轮。
                return save('round_limit', 'review', f'已跑满 {max_rounds} 轮且未达到转入 D 的条件，按用户要求停下汇报')
            save('running', 'analysis')
            try:
                def price_state(pause):
                    state['price_pause']=pause
                    save('running','analysis')
                if experiment['result'].get('mechanism_contract') != MECHANISM_CONTRACT:
                    wait_for_off_peak(store,'cycle:'+experiment_id,price_state,lambda:check_cycle_stop(store,experiment_id))
                engine.generate_next(agent)
            except ProposalValidationExhausted as error:
                from .paid_policy import e7_accounting
                from .paid_run import current_paid_run

                failures = state.setdefault('proposal_generation_failures', [])
                failures.append({'round':number+1, 'reason':str(error), 'sandbox_budget_used':0,
                                 'at':datetime.now(timezone.utc).isoformat()})
                if e7_accounting(current_paid_run()):
                    return save('analysis_exhausted', 'analysis', str(error))
                if sum(f['round'] == number+1 for f in failures) < 3:
                    save('running','analysis',str(error))
                    continue
                if qualified:
                    if use_layered:
                        if winner:
                            state['staged_decision']['decision'] = 'finish_winner'
                            return finish(experiment, [winner], 'finish_winner')
                        return save('analysis_exhausted', 'analysis', str(error))
                    return finish(experiment, qualified, 'composite')
                return save('analysis_exhausted','analysis',str(error))
    except task_leases.LeaseLost:
        raise
    except InterruptedError as error:
        return save('stopped',engine.state().get('phase','sandbox'),str(error))
    except Exception as error:
        return save('blocked' if permanent_provider_error(error) or isinstance(error, ValueError) else 'failed',
                    engine.state().get('phase','analysis'), str(error))


def recover_optimization_cycles(store, runtime):
    from .workflow_engine import recover_pending

    return recover_pending(store, runtime)


def recover_agent_generations(store, runtime):
    """Keep standalone generation separate from generations owned by a cycle."""
    with store.connection() as connection:
        rows = connection.execute("SELECT id,baseline_run_id,result_json FROM experiments WHERE status='generating'").fetchall()
        pending = []
        for row in rows:
            result = json.loads(row['result_json'])
            cycle = result.get('optimization_cycle') or {}
            if (cycle.get('stop_request') or cycle.get('status') in task_leases.ACTIVE_STATES
                    or task_leases.cycle_active(connection, row['id'], cycle)
                    or task_leases.agent_active(connection, row['id'], result, legacy_generating=True)):
                continue
            pending.append((row['id'], row['baseline_run_id']))

    def recover(experiment_id, baseline_id):
        try:
            OptimizationAgent(store, runtime.provider, runtime=runtime).generate(baseline_id, experiment_id=experiment_id, recovering=True)
        except Exception:
            logging.exception('Agent generation recovery failed: %s', experiment_id)

    for args in pending:
        threading.Thread(target=recover, args=args, daemon=True).start()
