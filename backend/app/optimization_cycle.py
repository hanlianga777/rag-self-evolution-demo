"""Authorized optimization loop; unattended work always stops before release."""
import json
import logging
import os
import threading
from datetime import datetime, timezone

from . import rules
from .agent_mechanism import CONTRACT as MECHANISM_CONTRACT
from .agent_round_contract import layered, layered_winner
from .evaluation import EvaluationRunner
from .full_text import CORPUS_LOCK
from .optimization import OptimizationAgent, ProposalValidationExhausted
from .paid_schedule import wait_for_off_peak, unattended_authorization
from .policy import MAX_EVALS, candidate_rank, gate2_self_check_authorized


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
        confirmation = experiment['result'].get('report_confirmation')
        if confirmation:
            winner = next((c for c in experiment['candidates'] if c['id'] == confirmation['winner_id']), None)
            if not winner or winner['status'] != 'evaluated' or not winner['result'].get('qualification', {}).get('qualified'):
                raise ValueError('Winner资格失效，不能续跑D')
            if current_round_only:
                raise ValueError('报告已确认，只能续跑D')
        if current_round_only and not any(c['reasoning'].get('candidate_label') in {'A','B','C'} for c in experiment['candidates']):
            raise ValueError('当前没有可续跑的 A/B/C 方案')
        state = {'status':'running', 'phase':'composite' if confirmation else 'analysis', 'owner_pid':os.getpid(), 'current_round_only':current_round_only,
                 'resume_stopped_runs':[c['result']['evaluation_run_id'] for c in experiment['candidates']
                     if c['status']=='failed' and c['result'].get('stop_request') and c['result'].get('evaluation_run_id')],
                 'used':experiment['evaluation_budget']['used'],
                 'remaining':max(0, MAX_EVALS-experiment['evaluation_budget']['used']),
                 'reserved_for_d':experiment['evaluation_budget']['reserved_for_d'], 'last_error':None}
        prior_cycle = experiment['result'].get('optimization_cycle', {})
        if prior_cycle.get('status') in {'blocked', 'stopped'}:
            state['reopen_paid_ledger'] = True
        blocked = [c['result']['evaluation_run_id'] for c in experiment['candidates']
                   if c['status']=='failed' and c['result'].get('evaluation_run_id')
                   and c['result'].get('auto_recovery', {}).get('state') == 'blocked']
        if blocked:
            state.update(resume_blocked_runs=blocked, reopen_paid_ledger=True)
        if layered(experiment['result']):
            previous_decision = experiment['result'].get('optimization_cycle', {}).get('staged_decision')
            if previous_decision:
                state['staged_decision'] = previous_decision
        result = {**experiment['result'], 'optimization_cycle':state}
        from .paid_policy import current_binding
        if binding := current_binding():
            if result.get('paid_run') not in (None, binding):
                raise ValueError('实验已绑定另一份费用授权')
            result['paid_run'] = binding
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
    from contextlib import nullcontext
    from .paid_policy import experiment_binding, restore_paid_context
    from .providers import permanent_provider_error, provider_error_details, provider_retry_scope
    if not claimed:
        claim_cycle(store, experiment_id)
    provider = runtime.provider if getattr(runtime, 'live_enabled', True) else None
    def on_state(status, **details):
        _save_state(store, experiment_id, provider_retry={'state':status, **details})
    try:
        binding = experiment_binding(store, experiment_id, provider)
        result = store.experiment(experiment_id, light=True)['result']
        reopen = result.get('optimization_cycle', {}).get('reopen_paid_ledger', False)
        with provider_retry_scope(lambda:check_cycle_stop(store, experiment_id), on_state), (
                restore_paid_context(store,binding,reopen=reopen) if binding else nullcontext()):
            if reopen:
                _save_state(store, experiment_id, reopen_paid_ledger=False)
            return _run_until_qualified(store, runtime, experiment_id)
    except (ValueError, OSError) as error:
        _save_state(store, experiment_id, status='blocked', last_error=str(error),
                    provider_retry={'state':'blocked', **provider_error_details(error,'authorization')})
    except Exception as error:
        if not permanent_provider_error(error):
            raise
        _save_state(store, experiment_id, status='blocked', last_error=str(error),
                    provider_retry={'state':'blocked', **provider_error_details(error,'provider')})
    return store.experiment(experiment_id, light=True)['result']['optimization_cycle']


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
    runner, agent = EvaluationRunner(store, runtime), OptimizationAgent(store, runtime.provider)
    empty_rounds = 0
    state = dict(store.experiment(experiment_id, light=True)['result'].get('optimization_cycle', {}))
    state.pop('provider_retry', None)
    state.update(owner_pid=os.getpid(), worker_thread=threading.get_ident())

    def save(status, phase, error=None):
        experiment = store.experiment(experiment_id, light=True)
        used = experiment['evaluation_budget']['used']
        legacy_staged = (experiment['result'].get('round_policy', {}).get('stop_rule') == STAGED_RULE
                         and not layered(experiment['result']))
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
        authorization = unattended_authorization(store)
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
        composite = store.create_composite(experiment_id, runtime.provider)
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
                conclude_round(store, runtime, experiment_id, final_d=True)
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
            finishing = not full_rounds or bool(experiment['result'].get('report_confirmation')) or bool(state.get('proposal_round_end'))
            if qualified and finishing:
                if terminal := advance_qualified(experiment, qualified):
                    return terminal
                experiment = store.experiment(experiment_id, light=True)
            labels = {'D'} if qualified and finishing else {'A','B','C'}
            pending = [c for c in experiment['candidates'] if c['reasoning'].get('candidate_label') in labels
                       and (c['status'] in {'generated','running'} or c['status']=='failed' and c['result'].get('evaluation_run_id'))]
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
                if not full_rounds and finished['result'].get('qualification',{}).get('qualified') is True:
                    break
            experiment = store.experiment(experiment_id, light=True)
            if not full_rounds and any(c['status']=='evaluated' and c['result'].get('qualification',{}).get('qualified') is True for c in experiment['candidates']):
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
                generated = agent.generate(experiment['baseline_run_id'], experiment_id=experiment_id)
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
    except InterruptedError as error:
        return save('stopped',state.get('phase','sandbox'),str(error))
    except Exception as error:
        return save('blocked' if permanent_provider_error(error) else 'failed', state.get('phase','analysis'), str(error))


STAGED_RULE = 'staged-v1'


def staged_decision(round_number, qualified_count, used, *, version=None,
                    remaining_count=None, untried_layers=(), has_combination=False):
    """规则总表五.6，纯函数，方便单测。返回 'next_round' / 'composite' / 'finish_winner' / 'agent_failed'。"""
    if layered({'verdict_version': version}):
        if remaining_count == 0 and qualified_count:
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
    from .agent_mechanism import faults_for_cases
    from .agent_round_contract import fault_layer, round_base, round_opportunities, saved_final_map
    from .composite import parameter_diff, pipeline_config
    from .optimization import gate_harming_changes, load_retrieval_preview, require_retrieval_preview
    from .policy import validate_candidate_config

    run_id = winner['result']['evaluation_run_id'] if winner else baseline['id']
    final = saved_final_map(store, run_id)
    remaining = {q for q, passed in final.items() if not passed}
    if not remaining:
        return {'remaining_count': 0, 'untried_layers': [], 'has_combination': False}
    candidates = experiment['candidates']
    baseline_config = pipeline_config(baseline['config'])
    base = round_base(baseline_config, candidates, number + 1, winner=winner, use_layered=True)
    failures = [row for row in baseline_bad_case_rows(store, baseline, use_final=True)
                if row['question_id'] in remaining]
    cases = verdict.final_cases(store, run_id)
    present = {row['question_id'] for row in failures}
    references = failures + [{'id': q, 'question_id': q} for q in sorted(remaining - present)]
    faults = faults_for_cases(baseline, cases, references)
    targets = [{**row, 'mechanism_fault': faults[row['question_id']]} for row in failures
               if row['question_id'] in faults and is_optimization_target(row)]
    current = experiment['result']['parameter_effect_ledger']['current']
    foundation = json.loads(baseline['dataset_snapshot_json']).get('corpus_fingerprint')
    preview = load_retrieval_preview(store, baseline['id'], foundation=foundation)
    gates = (baseline['result'].get('gates') or {}).get('gates')
    blocked = [row['config_diff'] for row in gate_harming_changes(candidates, gates)]
    options = round_opportunities(targets, base, baseline_config, candidates, preview, current, [],
                                 blocked=blocked, use_layered=True)
    untried = {fault_layer(row['fault']['code']) for row in options.values() if row['available']}
    if len(base['changes']) < rules.AGENT['d_max_changed_parameters']:
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
                    or len(parameter_diff(config, baseline_config)) > rules.AGENT['d_max_changed_parameters']
                    or not validate_candidate_config(config)['valid']):
                continue
            other = saved_final_map(store, source['result'].get('evaluation_run_id'))
            if other.keys() == final.keys() and any(other[q] for q in remaining):
                combined = True
                break
        if number >= rules.AGENT['max_rounds'] or experiment['evaluation_budget']['used'] >= MAX_EVALS - 1:
            combined = combined or any(row['available'] for row in options.values())
    return {'remaining_count': len(remaining), 'untried_layers': sorted(untried), 'has_combination': combined}


def _run_staged(store, runtime, experiment_id, state, save, advance_qualified, runner, agent):
    """按规则总表六.6/六.7 执行分阶段试跑。"""
    from .agent_strategy import conclude_round
    from .providers import permanent_provider_error

    def execute(candidate):
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
            if state.get('external_runner'):
                return None, save('failed', 'sandbox', result.get('auto_recovery', {}).get('error') or error)
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
                if state.get('external_runner'):
                    raise
                state['d_review_error'] = str(error)
        store.refresh_recommendation(experiment_id)
        return save('recommended', 'before_release')

    try:
        while True:
            check_cycle_stop(store,experiment_id)
            experiment = store.experiment(experiment_id, light=True)
            baseline = store.require_current_baseline(experiment['baseline_run_id'])
            use_layered = layered(experiment['result'])
            if stop := experiment['result'].get('decision_stop'):
                return save('stopped', 'review', stop['reason'])
            if experiment['result'].get('report_confirmation'):
                terminal = state.get('staged_decision', {}).get('decision')
                return finish(experiment, _qualified_abc(experiment),
                              'finish_winner' if use_layered and terminal == 'finish_winner' else 'composite')
            abc = [c for c in experiment['candidates'] if c['reasoning'].get('candidate_label') in {'A','B','C'}]
            number = max((c['reasoning'].get('round', 1) for c in abc), default=0)
            if use_layered and experiment['result'].get('seed_round_planned') is False:
                number = 0
            current = [c for c in abc if c['reasoning'].get('round', 1) == number]
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
                generated = agent.generate(experiment['baseline_run_id'], experiment_id=experiment_id)
                if stop := (generated or {}).get('result', {}).get('decision_stop'):
                    if use_layered and winner:
                        state['staged_decision']['decision'] = 'finish_winner'
                        return finish(experiment, [winner], 'finish_winner')
                    return save('stopped', 'review', stop['reason'])
            except ProposalValidationExhausted as error:
                if state.get('external_runner'):
                    raise
                failures = state.setdefault('proposal_generation_failures', [])
                failures.append({'round':number+1, 'reason':str(error), 'sandbox_budget_used':0,
                                 'at':datetime.now(timezone.utc).isoformat()})
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
    except InterruptedError as error:
        return save('stopped',state.get('phase','sandbox'),str(error))
    except Exception as error:
        return save('blocked' if permanent_provider_error(error) else 'failed', state.get('phase','analysis'), str(error))


def recover_optimization_cycles(store, runtime):
    """Restart only persisted authorized cycles whose worker has exited."""
    with store.connection() as connection:
        rows = connection.execute("SELECT id,json_extract(result_json,'$.optimization_cycle') cycle FROM experiments WHERE json_extract(result_json,'$.optimization_cycle.status')='running'").fetchall()
    for row in rows:
        state = json.loads(row['cycle'])
        if state.get('external_runner'):
            continue
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
        rows=connection.execute("SELECT id,baseline_run_id,json_extract(result_json,'$.agent_generation.owner_pid') owner_pid FROM experiments WHERE status='generating' AND coalesce(json_extract(result_json,'$.optimization_cycle.status'),'')!='running' AND NOT coalesce(json_extract(result_json,'$.optimization_cycle.external_runner'),0)").fetchall()
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
