"""Run the 126c Agent, Sandbox and convergence decisions under the cycle lease."""
import json
from datetime import datetime, timezone
from pathlib import Path

from . import agent126c as policy, evidence_roles, rules, task_leases, verdict
from .composite import pipeline_config
from .evaluation import EvaluationRunner
from .evaluation_stage import reopen_blocked_requests, request_checkpoint_scope
from .optimization import load_retrieval_preview, parse_agent_json, performance_facts
from .paid_run import provider_task
from .policy import PERFORMANCE_METRICS, search_space_contract
from .providers import DeepSeekProvider, ProviderUnavailable, _retry_sleep, provider_error_details

SYSTEM = """你是 126c 优化 Agent。只使用本实验的经验账本。
程序计算事实、信号与硬约束。逐条情况自行选择合法动作并解释，然后提交对应阶段的 JSON。
动作格式 actions=[{signal,action,reason}]，每条信号至少一个动作。同义改写也不能当成新机制。
默认按优先级分配名额，优先验证推荐工具。探索菜单或跨层须讲清机制。
三个方案用 proposals=[{label,parent_id,changes,hypothesis,reason,expected_fixed,possible_broken,
layer,signals}]。layer 只能是 safety/retrieval/generation/performance。题号用冻结题号。
可按需要追加 exploration_reason、cross_layer_reason、investigate_questions、performance_targets、
combination_type（dependency、mitigation、cross_layer）、mitigation。双参数不能声称已验证单项贡献。
保住父方案已答对的题。累计已到 4 项时只能改已有项的取值或撤销。禁止重配置、假设重复。
review 阶段提交 winner_id、branch_id（无则 null）、selection_reason、next、next_reason。若收敛且没有可组合项，也提交 no_d_reason。
如有 S2/S6/S7，动作应和选定的主线/支线相符。只在程序材料符合时结束。
d 阶段提交 proposal，label=D，另附 sources、combination_type 和需要时的 mitigation。
S14 的 reason 需逐题列证据和工程建议。S19 的动作要带 revisions 对象，键为高偏差的方案 ID，值为错在何处及如何改假设。
已有安全回退参数若还要使用，必须选择缓解并写 mitigation。从 S8 的处置继续提出可检验的机制。
resume 阶段只提交 actions。拒绝后仍按原校验逐项填写。"""


def dump(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def balance_exhausted(error):
    if isinstance(error, dict):
        return (any(balance_exhausted(v) for v in error.values())
                or error.get('http_status') == 402)
    if isinstance(error, list):
        return any(balance_exhausted(v) for v in error)
    if isinstance(error, BaseException):
        return provider_error_details(error, '126c').get('http_status') == 402 or balance_exhausted(str(error))
    return isinstance(error, str) and any(mark in error.lower() for mark in (
        '余额不足', 'insufficient_balance', 'insufficient balance', 'http 402'))


def sandbox_facts(store, run, question_ids, safety_questions):
    saved = verdict.records(store, run['id'])
    if set(saved) != set(question_ids) or any(type(row.get('final_passed')) is not bool for row in saved.values()):
        raise ValueError('Sandbox 须先保存完整的冻结题目判定')
    if any(row.get('final_failure_reason') == verdict.JUDGE_TECHNICAL_FAILURE for row in saved.values()):
        raise ValueError('Sandbox 仍有 Judge 技术失败，需要继续核验')
    cases = verdict.final_cases(store, run['id'])
    timing = performance_facts(run['result'], cases)
    timing['stage_shares'].sort(key=lambda row: row['duration_ms'], reverse=True)
    timing['failed_gates'] = sorted(key for key, row in policy.gate_rows(run['result'], PERFORMANCE_METRICS).items()
                                   if row['passed'] is not True)
    timing['tools'] = policy.performance_tools(timing['stage_shares'])
    return {'id': run['id'], 'passed': sorted(qid for qid, row in saved.items() if row['final_passed']),
            'safety': verdict.safety_violation_question_ids(saved),
            'safety_failed': sorted(qid for qid in safety_questions if not saved[qid]['final_passed']),
            'gates': run['result']['gates'], 'performance': timing,
            'judge_disagreements': {qid: {'votes': [sample['passed'] for sample in row['samples']],
                                          'final_passed': row['final_passed'], 'rechecked': len(row['samples']) == 3}
                for qid, row in saved.items() if len({sample['passed'] for sample in row['samples']}) > 1}}


def prediction(draft, fixed, broken):
    expected, risk = set(draft['predicted_fixed_question_ids']), set(draft['predicted_regression_question_ids'])
    fixed, broken = set(fixed), set(broken)
    return {'hit': sorted(expected & fixed), 'missed': sorted(expected - fixed),
            'unexpected_fixed': sorted(fixed - expected), 'risk_hit': sorted(risk & broken),
            'unexpected_broken': sorted(broken - risk),
            'large_deviation': bool(broken - risk or expected and len(expected & fixed) * 2 < len(expected)
                                    or fixed and len(expected & fixed) * 2 < len(fixed))}


class StrategyCycle:
    def __init__(self, engine):
        self.engine = engine
        self.store, self.runtime, self.id = engine.store, engine.runtime, engine.id
        self.runner = EvaluationRunner(self.store, self.runtime)
        experiment = engine.experiment()
        self.version = experiment['result']['decision_contract_version']
        self.final_only = self.version == policy.FINAL_ONLY_VERSION
        verdict.require_empty_history(experiment['result'].get('parameter_effect_ledger'))
        self.baseline = self.store.require_current_baseline(experiment['baseline_run_id'])
        if isinstance(self.runtime.provider, DeepSeekProvider):
            if not getattr(self.runtime, 'live_enabled', False):
                raise ValueError('126c 需要可用的 Agent Provider')
            self.runner._require_generation_contract(self.baseline['judge'])
        snapshot = json.loads(self.baseline['dataset_snapshot_json'])
        self.question_ids = snapshot['question_ids']
        self.safety_questions = {q['id'] for q in snapshot['questions']
                                 if q.get('negative_subtype') in {'safety_critical', 'prompt_injection'}}
        self.base_facts = sandbox_facts(self.store, self.baseline, self.question_ids, self.safety_questions)
        self.base_config = pipeline_config(self.baseline['config'])
        self.preview = load_retrieval_preview(self.store, self.baseline['id'], foundation=snapshot.get('corpus_fingerprint'))

    def state(self):
        return self.engine.experiment()['result'].get('strategy126c') or {
            'rounds': {}, 'ledger': [], 'winner_id': None, 'branch_id': None, 'streak': 0, 'd_attempts': [],
        }

    def persist(self, state, drafts=(), *, outcomes=()):
        with self.store.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            key = 'cycle:' + self.id
            task_leases.require(db, key, task_leases.current(self.store, key))
            row = db.execute('SELECT result_json FROM experiments WHERE id=?', (self.id,)).fetchone()
            result = json.loads(row['result_json'])
            result['strategy126c'] = state
            if state.get('final') and not result.get('report_confirmation'):
                final = state['final']
                now = datetime.now(timezone.utc).isoformat()
                result['report_confirmation'] = {'winner_id': final['winner_id'], 'confirmed_at': now,
                                                 'actor': 'Agent', 'audit_note': final['reason']}
                db.execute('INSERT INTO approvals(gate,target_id,decision,actor,created_at) VALUES (?,?,?,?,?)',
                           ('experiment_report', self.id, 'approved', 'Agent', now))
            for draft in drafts:
                reasoning = draft['reasoning']
                cid = f"{self.id}-R{reasoning['round']:06d}-{reasoning['candidate_label']}"
                db.execute('INSERT INTO candidate_configs VALUES (?,?,?,?,?,?,?)',
                           (cid, self.id, 'generated', dump(draft['config']), dump(reasoning), '{}',
                            datetime.now(timezone.utc).isoformat()))
            for outcome in outcomes:
                db.execute("UPDATE candidate_configs SET result_json=json_set(result_json,'$.strategy126c_labels',json(?)) WHERE id=?",
                           (dump(outcome['labels']), outcome['id']))
            number = max(map(int, state['rounds']))
            trace = {'round': number, 'decision_contract_version': self.version, **state['rounds'][str(number)]}
            db.execute("INSERT INTO agent_traces(experiment_id,status,result_json,created_at) VALUES (?, 'completed', ?, ?)",
                       (self.id, dump(trace), datetime.now(timezone.utc).isoformat()))
            db.execute("UPDATE experiments SET status='generated', result_json=? WHERE id=?", (dump(result), self.id))

    def target_rows(self, facts):
        failed = set(self.question_ids) - set(facts['passed'])
        cases = verdict.final_cases(self.store, facts['id'])
        faults = evidence_roles.faults(self.baseline, cases, failed)
        targets = {}
        for qid in sorted(failed):
            fault = faults.get(qid) or {'subtype': '待确认', 'layer': None, 'reason': '缺少可确认的保存证据'}
            if fault['subtype'] == '慢':
                fault['stage_shares'] = facts['performance']['stage_shares']
            recommended, exploratory = policy.menu(fault)
            targets[qid] = {**fault, 'recommended': recommended, 'exploratory': exploratory}
        return targets

    def parent(self, candidate_id):
        if candidate_id == self.baseline['id']:
            return {**self.base_facts, 'config': self.base_config}
        candidate = self.store.candidate(candidate_id)
        if not candidate or candidate['experiment_id'] != self.id:
            raise ValueError('父方案必须属于同一实验')
        run = self.store.evaluation_run(candidate['result']['evaluation_run_id'])
        return {**sandbox_facts(self.store, run, self.question_ids, self.safety_questions),
                'config': pipeline_config(candidate['config'])}

    def context(self, number, state, *, winner=None, use_passed_winner=False):
        baseline_id = self.baseline['id']
        winner = winner if use_passed_winner else state['winner_id']
        branch = state['branch_id']
        parents = {cid: self.parent(cid) for cid in dict.fromkeys((baseline_id, winner, branch)) if cid}
        actual = parents[winner or baseline_id]
        by_parent = {cid: self.target_rows(facts) for cid, facts in parents.items()}
        targets = by_parent[winner or baseline_id]
        priorities = self.priorities(targets, actual)
        previous = self.engine.experiment()['candidates']
        pending, boundaries = policy.coverage(targets, state['ledger'])
        preview_risks = []
        for row in (self.preview or {}).get('configs', []):
            risk = sorted(set(row.get('evidence_lost_from_final', []))
                          & {q for facts in parents.values() for q in facts['passed']})
            if risk:
                config = pipeline_config({**self.base_config, **row['change']})
                preview_risks.append({'config': {key: config[key] for key in policy.RETRIEVAL}, 'questions': risk})
        previous_series = state['rounds'].get(str(number - 1), {})
        previous_review = previous_series.get('review', {})
        d_review = previous_series.get('d_review', {})
        previous_round = {**previous_review,
                          **({'plateau': d_review['plateau'],
                              'outcomes': [*previous_review['outcomes'], *d_review['outcomes']]} if d_review else {})}
        return {'round': number, 'question_ids': self.question_ids, 'baseline_id': baseline_id,
                'baseline_config': self.base_config, 'winner_id': winner, 'branch_id': branch,
                'targets': targets, 'targets_by_parent': by_parent, 'parents': parents, 'priorities': priorities,
                'default_slots': [priorities[0], priorities[0], priorities[1]] if len(priorities) > 1 else priorities * 3,
                'performance': actual['performance'], 'preview_risks': preview_risks, 'boundaries': boundaries,
                'pending_tools': pending, 'ledger': state['ledger'], 'previous_configs': [row['config'] for row in previous],
                'hypotheses': [row['reasoning']['hypothesis_key'] for row in previous],
                'previous_round': previous_round,
                'search_space': search_space_contract()}

    @staticmethod
    def priorities(targets, actual):
        from collections import Counter

        counts = Counter(row['layer'] for row in targets.values() if row['layer'] in policy.LAYERS)
        severe = Counter(row['layer'] for row in targets.values() if row.get('severity') in {'致命', '严重'})
        failed_gates = {row['metric'] for row in actual['gates'].get('gates', []) if row['passed'] is not True}
        if actual['performance']['failed_gates']:
            counts['performance'] += 1
        gated = ({'performance'} if failed_gates & set(PERFORMANCE_METRICS) else set())
        if failed_gates & set(policy.SAFETY_METRICS):
            gated.add('safety')
        if failed_gates - set(PERFORMANCE_METRICS) - set(policy.SAFETY_METRICS):
            gated.update(row['layer'] for row in targets.values() if row['layer'] in ('retrieval', 'generation'))
        return sorted(counts, key=lambda layer: (layer != 'safety', layer not in gated, -severe[layer], -counts[layer],
                                                    policy.LAYERS.index(layer)))

    @provider_task('agent')
    def ask(self, key, context, signals, validate):
        saved = self.store.job_checkpoint(self.id, key) or {'attempts': [], 'transport_failures': []}
        if 'accepted' in saved:
            return saved['accepted']

        def persist():
            self.store.save_job_checkpoint(self.id, key, saved)

        while True:
            self.engine.check_stop()
            self.store.require_current_baseline(self.baseline['id'])
            if self.store.current_baseline_identity()['current_experiment_id'] != self.id:
                raise ValueError('126c 只能在当前实验内继续')
            attempts = saved['attempts']
            if not attempts or 'rejected' in attempts[-1]:
                attempts.append({'request_checkpoint': {'attempts': []}})
            attempt = attempts[-1]
            rejected = [row['rejected'] for row in attempts[:-1]]
            current_signals = list(signals)
            if rejected:
                current_signals.append(policy.signal('S17', rejection=rejected[-1], consecutive=len(rejected)))
            request = {'context': context, 'signals': current_signals}
            if context['phase'] == 'plan':
                request['plan_instructions'] = (
                    '每案用完整冻结题号。当前有错题的层须预测父方案至少一题尚未答对的题，'
                    'possible_broken 只填同一父方案已答对的题，无明确风险则填空列表。'
                    '使用推荐菜单外的工具或试撤销继承参数时，必填 exploration_reason。'
                    'performance 只用于父方案确实没过的性能门槛，performance_targets 填对应门槛 ID 列表。'
                    'S20 按三个方案实际改动选择：把任一继承参数改回 Baseline 须选 withdraw，'
                    '只替换继承值须选 replace；两类方案都有时分别填写两个动作。')
                if self.final_only and rejected:
                    request['plan_retry'] = {
                        'a_parent_id': context['winner_id'] or context['baseline_id'],
                        'untried_mainline_changes': policy.retry_menu(context),
                        'recent_rejections': list(dict.fromkeys(rejected[-5:])),
                        'instructions': ('A 的 parent_id 须等于 a_parent_id。优先从单项备选中选未试过的配置，'
                                         'expected_fixed 从同一条的题号中选择，并说明机制。'
                                         '备选通过配置检查，仍须满足本轮信号、风险和机理校验。'
                                         '同一轮三个最终配置也须互不重复。B、C 可按本轮合法动作选择父方案。'),
                    }
                if context.get('remaining_configurations'):
                    request['plan_instructions'] += (
                        '诊断菜单内未试配置不足。可从 remaining_configurations 补齐三案，'
                        '每案用对应父方案、改动与撤销或替换动作，并说明探索机制。')
            elif context['phase'] == 'd':
                request['d_instructions'] = (
                    'actions 只逐条回应本请求顶层 signals，action 填一个合法字符串，'
                    'proposal.signals 只能引用这些已回应的 ID。'
                    '从 context.combinations 选一条，原样使用 changes，sources 填该条 source 的 ID。'
                    '父方案 ID 用 context.winner_id。expected_fixed 填父方案尚未答对的完整冻结题号，'
                    'possible_broken 填父方案已答对的完整冻结题号，无明确风险题时填空列表。')
            if len(rejected) >= 3:
                request['structured_fields'] = self.field_form(context['phase'], current_signals, rejected[-1])
                request['fill_instructions'] = ('按 structured_fields 的字段分组逐项填写。回复 {actions, field_values}。'
                    'field_values 的每个分组值为对象，键为字段名，值为所填内容。原校验不变。')
            if 'response' not in attempt:
                self.engine.wait_for_price()
                checkpoint = attempt['request_checkpoint']

                def on_state(status, **details):
                    persist()
                    self.engine.retry_state(status, **details)

                try:
                    system = SYSTEM
                    if self.final_only:
                        system = SYSTEM.replace('126c', self.version) + (
                            '\n每轮必须提交完整 A/B/C。轮次复盘 next 只按 legal 选择。'
                            'final 表示三案已经复盘且进入最终阶段。'
                            'final 请求只选一个 FINAL_D 动作并给理由。'
                            'd_retry 或 d_merge 从 options 对应项原样填写 changes 和 sources，再提交 proposal。'
                            'd_retry 必填 mitigation 和 combination_type=mitigation。d_skip 不提交方案。')
                    with request_checkpoint_scope(checkpoint, 'agent', self.id, on_state, self.engine.check_stop):
                        attempt['response'] = self.runtime.provider.complete(system, dump(request), json_mode=True)
                except (ProviderUnavailable, OSError) as error:
                    if balance_exhausted(error):
                        raise
                    saved['transport_failures'].append(str(error))
                    reopen_blocked_requests(checkpoint)
                    persist()
                    _retry_sleep(3, self.engine.check_stop)
                    continue
                persist()
            try:
                if not isinstance(attempt['response'], str):
                    raise ValueError('回复必须是 JSON 文本')
                response = parse_agent_json(attempt['response'], {})
                if not isinstance(response, dict):
                    raise ValueError('回复必须是 JSON 对象')
                if 'structured_fields' in request:
                    response = self.field_response(response, context['phase'])
                policy.validate_actions(response, current_signals)
                data = validate(response, current_signals)
            except ValueError as error:
                attempt['rejected'] = str(error)
                persist()
                continue
            saved['accepted'] = {'signals': current_signals, 'actions': response['actions'],
                                 'data': data, 'agent_response': response}
            persist()
            return saved['accepted']

    @staticmethod
    def field_form(phase, signals, rejected):
        actions = [{'signal': row['id'], 'action': list(row['legal_actions']), 'reason': '逐条说明'} for row in signals]
        for action, row in zip(actions, signals):
            if row['id'] == 'S19':
                action['revisions'] = {candidate['id']: '说明偏差和修订后的假设'
                                       for candidate in row['evidence']['candidates']}
        fields = ['label', 'parent_id', 'changes', 'hypothesis', 'reason', 'expected_fixed', 'possible_broken',
                  'layer', 'signals', 'exploration_reason', 'cross_layer_reason', 'investigate_questions',
                  'performance_targets', 'combination_type', 'mitigation']
        forms = {
            'plan': {label: fields[1:] for label in policy.LABELS},
            'review': {'decision': ['winner_id', 'branch_id', 'selection_reason', 'next', 'next_reason', 'no_d_reason']},
            'd': {'D': [*fields[1:], 'sources']},
            'final': {'decision': ['proposal']},  # Leave empty for d_skip.
            'resume': {},
        }
        return {'rejected': rejected, 'actions': actions, 'field_values': forms[phase]}

    @staticmethod
    def field_response(response, phase):
        form = response.get('field_values')
        expected = {'plan': set(policy.LABELS), 'review': {'decision'}, 'd': {'D'}, 'final': {'decision'}, 'resume': set()}
        if not isinstance(form, dict) or set(form) != expected[phase] or any(not isinstance(row, dict) for row in form.values()):
            raise ValueError('field_values 必须按程序提供的分组逐项填写')
        actions = response.get('actions')
        if isinstance(actions, list):
            normalized = []
            for row in actions:
                choice = row.get('action') if isinstance(row, dict) else None
                if isinstance(choice, list) and choice:
                    normalized.extend({**row, 'action': item} for item in choice)
                else:
                    normalized.append(row)
            actions = normalized
        result = {'actions': actions}
        if phase == 'plan':
            result['proposals'] = [{**form[label], 'label': label} for label in policy.LABELS]
        elif phase == 'd':
            result['proposal'] = {**form['D'], 'label': 'D'}
        elif phase in ('review', 'final'):
            result = {**form['decision'], **result}
        return result

    def generate(self, number, state):
        context = self.context(number, state)
        context['phase'] = 'plan'
        context['d_available'] = False
        signals = policy.planning_signals(context)
        if self.final_only:
            context['decision_contract_version'] = self.version
            context['remaining_configurations'] = policy.remaining_configurations(context)
            policy.round_actions(signals)
        self.engine.save(status='running', phase='analysis', round=number)
        plan = self.ask(f'{self.version}:{number}:plan', context, signals,
                        lambda response, sent: policy.validate_plan(response, context, sent))
        state['rounds'][str(number)] = {'plan': {k: plan[k] for k in ('signals', 'actions')}}
        self.persist(state, plan['data'])

    def sandbox(self, number, candidate_id, state):
        while True:
            self.engine.check_stop()
            candidate = self.store.candidate(candidate_id)
            if candidate['status'] == 'evaluated':
                return candidate
            self.engine.save(status='running', phase='sandbox', active_candidate=candidate_id,
                             used=self.engine.experiment()['evaluation_budget']['used'])
            if candidate['status'] in ('queued', 'running', 'recovering'):
                run_id = candidate['result']['evaluation_run_id']
                self.recovery(number, candidate_id, state, run_id, {'error': '发现已有 Sandbox 断点'})
                self.runner.recover_run(run_id)
            else:
                if candidate['status'] == 'failed':
                    result = candidate['result']
                    resuming_balance = self.engine.state().get('resume_blocked_runs', [])
                    if balance_exhausted({key: result.get(key) for key in ('error', 'provider_retry', 'technical_errors')}) and (
                            result.get('evaluation_run_id') not in resuming_balance):
                        self.engine.save(status='budget_exhausted', last_error='DeepSeek 余额不足，Sandbox 断点已保存',
                                         phase='sandbox')
                        return None
                    self.recovery(number, candidate_id, state, result.get('evaluation_run_id'), result)
                    _retry_sleep(1, self.engine.check_stop)
                self.runner.run_candidate(candidate_id, automatic=True, manual_resume=candidate['status'] == 'failed')

    def recovery(self, number, candidate_id, state, run_id, result):
        series = state['rounds'][str(number)].setdefault('recoveries', [])
        if any(item['event']['source_run_id'] == run_id and item['event']['candidate_id'] == candidate_id for item in series):
            return
        event = {'candidate_id': candidate_id, 'source_run_id': run_id,
                 'reason': result.get('error'), 'technical_errors': result.get('technical_errors', [])}
        response = self.ask(f'{self.version}:{number}:resume:{run_id or candidate_id}', {'phase': 'resume', **event},
                            [policy.signal('S18', **event)], lambda response, sent: None)
        series.append({'event': event, 'signals': response['signals'], 'actions': response['actions']})
        self.persist(state)

    def outcome(self, candidate, state):
        draft = candidate['reasoning']
        after = self.parent(candidate['id'])
        parent = self.parent(draft['parent_id'])
        winner = self.parent(state['winner_id'] or self.baseline['id'])
        labels = policy.qualifications(after, self.base_facts, parent, winner)
        slow = any(row['actual'] is not None and old['actual'] is not None and row['actual'] > old['actual']
                   for key, row in policy.gate_rows(after, PERFORMANCE_METRICS).items()
                   if (old := policy.gate_rows(parent, PERFORMANCE_METRICS).get(key)))
        outcome = {**after, 'id': candidate['id'], 'parent_id': draft['parent_id'],
                   'from_branch': bool(state['branch_id'] and (draft['parent_id'] == state['branch_id']
                                                               or candidate['id'] == state['branch_id'])),
                   'higher_score': len(after['passed']) > len(winner['passed']),
                   'changes': draft['changes'], 'hypothesis': draft['hypothesis'], 'labels': labels,
                   'layer': draft['layer'], 'round': draft['round'], 'planned_tools': draft['planned_tools'],
                   'side_effect': bool(labels['vs_parent']['broken'] or labels['safety_regression']
                                       or after['performance']['failed_gates']),
                   'slower_and_better': slow and bool(labels['vs_parent']['fixed']),
                   'prediction': prediction(draft, **labels['vs_parent'])}
        return outcome

    def conditions(self, context, state, *, plateau):
        winner = context['winner_id']
        parent = context['parents'][winner or context['baseline_id']]
        active = set(context['priorities']) | set(state.get('layers_with_faults', []))
        tried = {entry['layer'] for entry in state['ledger']}
        combos = [] if self.final_only else policy.complementary_combinations(context, state['ledger'])
        d_handled = any(entry['winner_id'] == winner for entry in state['d_attempts'])
        full = bool(winner and len(parent['passed']) == len(self.question_ids) and policy.all_gates_pass(parent['gates']))
        return {'qualified': bool(winner), 'questions': not context['pending_tools'], 'layers': active <= tried,
                'd': not combos or d_handled, 'plateau': plateau}, full, combos

    @staticmethod
    def final_steps(conditions, *, full):
        if full:
            return ['finish']
        ready = all(conditions.get(key) is True for key in ('qualified', 'questions', 'layers', 'plateau'))
        return ['final'] if ready else ['continue']

    def review(self, number, state, candidates, *, after_d=False):
        if self.final_only and (
                [c['reasoning']['candidate_label'] for c in candidates] != list(policy.LABELS)
                or any(c['status'] != 'evaluated' or c['result'].get('evaluation_complete') is not True
                       for c in candidates)):
            raise ValueError('127a 须收到 A/B/C 全部 Sandbox 最终判定才能复盘')
        series = state['rounds'][str(number)]
        old_winner = state['winner_id']
        outcomes = [self.outcome(candidate, state) for candidate in candidates]
        new_ledger = [*state['ledger'], *outcomes]
        promotions = [row['id'] for row in outcomes if row['labels']['promoted']]
        next_winners = promotions or [old_winner]
        older = self.context(number, state)
        state['layers_with_faults'] = sorted(set(state.get('layers_with_faults', [])) | set(older['priorities']))
        forecast = {**state, 'ledger': new_ledger}
        check = {}
        for winner in next_winners:
            ctx = self.context(number, forecast, winner=winner, use_passed_winner=True)
            prior_plateau = not promotions and (not after_d or series['review']['plateau'])
            conditions, full, combos = self.conditions(ctx, forecast, plateau=prior_plateau)
            d_possible = bool(combos and not after_d and (conditions['questions'] or state['streak']
                                                            or not promotions and conditions['layers']
                                                            or any(len(policy.config_diff(p['config'], self.base_config)) == 4
                                                                   for p in ctx['parents'].values())))
            if self.final_only:
                conditions.pop('d')
                legal = self.final_steps(conditions, full=full)
            else:
                legal = (['finish'] if full else ['continue'] + (['d'] if d_possible else [])
                         + (['finish'] if policy.may_finish(conditions, full=False) else []))
            check[winner or older['baseline_id']] = {
                'conditions': conditions, 'branches': policy.branch_options(new_ledger, winner,
                                                                           ctx['parents'][winner or older['baseline_id']]),
                'remaining_tools': ctx['pending_tools'], 'boundaries': ctx['boundaries'], 'full': full,
                'd_available': d_possible, 'd_source_ids': sorted({row['source'] for row in combos}),
                'legal': legal,
            }
        overall_full = any(row['full'] for row in check.values())
        plateau = not promotions and (not after_d or series['review']['plateau'])
        streak = (state['streak'] + 1 if not after_d else state['streak']) if plateau else 0
        allowed_conditions = {k: any(row['conditions'].get(k, False) for row in check.values())
                              for k in ('qualified', 'questions', 'layers', 'd', 'plateau')}
        # Offer finish only when one single prospective Winner satisfies the conditions.
        if not any('finish' in row['legal'] for row in check.values()):
            allowed_conditions['questions'] = False
        signals = policy.review_signals(outcomes, old_winner, state['branch_id'], streak, allowed_conditions,
                                        full=overall_full, d_available=any(row['d_available'] for row in check.values()))
        if self.final_only:
            policy.round_actions(signals, closing=all(row['legal'] == ['final'] for row in check.values()))
        if any(row['boundaries'] for row in check.values()):
            signals.append(policy.signal('S14', questions={key: row['boundaries'] for key, row in check.items()}))
        if overall_full:
            signals = [row for row in signals if row['id'] not in {'S4', 'S5'}]
            if not any(row['from_branch'] and check.get(row['id'], {}).get('full') for row in outcomes):
                signals = [row for row in signals if row['id'] != 'S6']
            promotions = [cid for cid in promotions if check[cid]['full']]
        branches = {key: row['branches'] for key, row in check.items()}
        branch_promotions = [row['id'] for row in outcomes if row['from_branch'] and row['id'] in promotions]
        sidelined = [row['id'] for row in outcomes if row['from_branch'] and row['higher_score']
                     and row['labels']['vs_winner']['broken']]
        faster = [row['id'] for row in outcomes if any(other['passed'] == row['passed']
                  and policy.faster(other, row, ratio=1) for other in outcomes if other['id'] in promotions)]
        request = {'phase': 'review', 'round': number, 'previous_winner': old_winner, 'previous_branch': state['branch_id'],
                   'choices_by_winner': check, 'promotions': promotions, 'outcomes': outcomes, 'ledger': new_ledger}

        def validate(review, sent):
            selected = review.get('winner_id')
            selected = selected if isinstance(selected, str) else older['baseline_id']
            selected_check = check.get(selected, {})
            if (review.get('next') == 'finish' and not selected_check.get('full')
                    and not selected_check.get('d_source_ids') and not state['d_attempts']):
                policy.text_field(review, 'no_d_reason')
            return policy.select_review(review, {
                'winner_id': old_winner, 'baseline_id': older['baseline_id'], 'promotions': promotions,
                'branch_promotions': branch_promotions, 'branches_by_winner': branches,
                'sidelined': sidelined, 'same_quality_faster': faster, 'legal_next': selected_check.get('legal', []),
            }, sent)

        self.engine.save(status='running', phase='composite_review' if after_d else 'review', active_candidate=None)
        response = self.ask(f'{self.version}:{number}:' + ('d-review' if after_d else 'review'), request, signals, validate)
        winner, branch, step = response['data']
        selected = check[winner or older['baseline_id']]
        for outcome in outcomes:
            outcome['labels']['promoted'] = outcome['id'] == winner and winner != old_winner
        state.update(ledger=new_ledger, winner_id=winner, branch_id=branch, streak=streak)
        if after_d:
            state['d_attempts'][-1]['outcome'] = 'promoted' if winner != old_winner else 'not_promoted'
        trace = {'signals': response['signals'], 'actions': response['actions'], 'outcomes': outcomes,
                 'all_unqualified': all(not row['labels']['qualified'] for row in outcomes), 'plateau': plateau,
                 'winner_id': winner, 'branch_id': branch, 'next': step, 'conditions': selected['conditions'],
                 'remaining_tools': selected['remaining_tools'], 'boundaries': selected['boundaries'],
                 'selection_reason': response['agent_response'].get('selection_reason'),
                 'reason': response['agent_response']['next_reason']}
        series['d_review' if after_d else 'review'] = trace
        if step == 'finish':
            state['final'] = {'winner_id': winner, 'full': selected['full'], 'conditions': selected['conditions'],
                              'reason': trace['reason'], 'd_outcome': state['d_attempts'][-1]['outcome']
                              if state['d_attempts'] else 'not_generated',
                              'd_reason': '满分，无剩余错题' if selected['full'] else
                              response['agent_response'].get('no_d_reason') or '账本已核对，无待组合项'
                              if not selected['d_source_ids'] else '本主线已评测 D'}
        self.persist(state, outcomes=outcomes)
        if step == 'finish':
            self.store.refresh_recommendation(self.id)

    def generate_d(self, state, number):
        context = self.context(number, state)
        context['phase'] = 'd'
        options = policy.complementary_combinations(context, state['ledger'])
        context['combinations'] = options
        review_signals = state['rounds'][str(number)]['review']['signals']
        signals = [row for row in review_signals if row['id'] in {'S8', 'S13'}]
        signals.extend(row for row in policy.planning_signals(context) if row['id'] in {'S20', 'S21'})

        def validate(response, sent):
            selected = policy.validate_actions(response, sent)
            draft = policy.validate_draft(response.get('proposal'), 'D', context, selected, context['previous_configs'])
            reasoning = draft['reasoning']
            sources = policy.question_ids(reasoning, 'sources', {row['source'] for row in options})
            if not sources:
                raise ValueError('D 需要本实验的互补机制来源')
            applied = [row for row in options if row['source'] in sources and row['changes'] == reasoning['changes']]
            if not applied or set(sources) - {row['source'] for row in applied}:
                raise ValueError('D 须为未试过的合法互补组合')
            if any(row['requires_mitigation'] for row in applied):
                policy.text_field(reasoning, 'mitigation')
                if reasoning.get('combination_type') != 'mitigation':
                    raise ValueError('D 使用局部有效项时须用组合缓解副作用')
            reasoning['winner_id'] = context['winner_id']
            return draft

        self.engine.save(status='running', phase='composite')
        reply = self.ask(f'126c:{number}:d', context, signals, validate)
        state['rounds'][str(number)]['d'] = {key: reply[key] for key in ('signals', 'actions')}
        state['d_attempts'].append({'round': number, 'winner_id': context['winner_id'],
                                    'candidate_id': f'{self.id}-R{number:06d}-D', 'outcome': 'pending'})
        self.persist(state, [reply['data']])

    def choose_final(self, number, state):
        series = state['rounds'][str(number)]
        conditions = series['review']['conditions']
        if self.final_steps(conditions, full=False) != ['final']:
            raise ValueError('须满足 Winner、逐题工具、跨层和平台期条件')
        context = self.context(number, state)
        context.update(phase='final', decision_contract_version=self.version)
        context['options'] = options = policy.final_combinations(context)
        signals = [{'id': 'FINAL_D', 'title': '最终阶段',
                    'legal_actions': {'d_retry': '补跑有收益也有副作用的改动',
                                      'd_merge': '合并互补改动', 'd_skip': '没有合适的组合，保留主线'},
                    'evidence': conditions}]

        def validate(response, sent):
            decisions = [row for row in response['actions'] if row['signal'] == 'FINAL_D']
            if len(decisions) != 1:
                raise ValueError('只选一个最终动作')
            action = decisions[0]['action']
            proposal = response.get('proposal')
            if action == 'd_skip':
                if proposal is not None:
                    raise ValueError('d_skip 不提交 D 方案')
                return None
            if not isinstance(proposal, dict):
                raise ValueError('所选动作需要完整 D 方案')
            option = next((row for row in options[action]
                           if proposal.get('changes') == row['changes'] and proposal.get('sources') == row['sources']), None)
            if option is None:
                raise ValueError('须从所选动作的未试组合中填写改动和账本来源')
            if action == 'd_retry':
                policy.text_field(proposal, 'mitigation')
                if proposal.get('combination_type') != 'mitigation':
                    raise ValueError('d_retry 须说明如何缓解副作用')
            # Final choices have a single action. The shared validator still enforces
            # the four-change cap and requires a mitigation for preview risks.
            if proposal.get('signals') != ['FINAL_D']:
                raise ValueError('D 方案须引用 FINAL_D')
            choices = {**policy.validate_actions(response, sent), 'S20': {'replace', 'withdraw'}, 'S21': {'mitigate'}}
            draft = policy.validate_draft(proposal, 'D', context, choices, context['previous_configs'])
            if not set(draft['reasoning']['predicted_fixed_question_ids']).intersection(option['questions']):
                raise ValueError('D 须指明至少一题账本证据支持的预期修复')
            draft['reasoning'].update(winner_id=state['winner_id'], d_action=action)
            return draft

        self.engine.save(status='running', phase='composite')
        reply = self.ask(f'{self.version}:{number}:final', context, signals, validate)
        decision = next(row for row in reply['actions'] if row['signal'] == 'FINAL_D')
        draft = reply['data']
        series['d'] = {key: reply[key] for key in ('signals', 'actions')}
        if draft:
            cid = f'{self.id}-R{number:06d}-D'
            state['d_attempts'].append({'round': number, 'winner_id': state['winner_id'],
                                        'candidate_id': cid, 'outcome': 'pending'})
            self.persist(state, [draft])
        else:
            state['final'] = {'winner_id': state['winner_id'], 'full': False, 'conditions': conditions,
                              'reason': decision['reason'], 'd_reason': decision['reason'],
                              'd_action': 'd_skip', 'd_outcome': 'not_generated'}
            self.persist(state)

    def complete_final_d(self, number, state, candidate):
        outcome = self.outcome(candidate, state)
        series = state['rounds'][str(number)]
        promoted = outcome['labels']['promoted']
        d_outcome = 'promoted' if promoted else 'not_promoted'
        if promoted:
            state['winner_id'] = outcome['id']
            if state['branch_id'] == outcome['id']:
                state['branch_id'] = None
        state['ledger'].append(outcome)
        state['d_attempts'][-1]['outcome'] = d_outcome
        reason = ('D 保住主线成果且有严格增量，推荐 D' if promoted
                  else 'D 未达到主线晋升条件，保留 Winner')
        decision = next(row for row in series['d']['actions'] if row['signal'] == 'FINAL_D')
        series['d_review'] = {'winner_id': state['winner_id'], 'branch_id': state['branch_id'],
                              'outcomes': [outcome], 'reason': reason, 'next': 'finish'}
        state['final'] = {'winner_id': state['winner_id'], 'full': len(outcome['passed']) == len(self.question_ids) and promoted,
                          'conditions': series['review']['conditions'], 'reason': reason,
                          'd_reason': decision['reason'], 'd_action': decision['action'], 'd_outcome': d_outcome}
        self.persist(state, outcomes=[outcome])

    def finish(self, state, target):
        self.store.refresh_recommendation(self.id)
        winner = state['final']['winner_id']
        if target != 'release':
            self.engine.save(status='recommended', phase='before_release', active_candidate=None)
            return
        self.engine.check_stop()
        published = next((item for item in self.store.production_versions()
                          if item['snapshot'].get('candidate_id') == winner), None)
        if not published:
            from .release_view import release_review_view

            checks = release_review_view(self.store, winner)['checks']
            if not all(check['ok'] is True for check in checks):
                raise ValueError('发布检查缺失：' + '、'.join(row['label'] for row in checks if row['ok'] is not True))
            self.engine.save(status='running', phase='publish126c', active_candidate=None)
            from .task127b_release import AUTHORIZED_AT, TASK, prepare_release

            identity = (self.engine.experiment()['result'].get('paid_run') or {}).get('ledger_identity') or {}
            if identity.get('task') == TASK:
                candidate = self.store.candidate(winner)
                if error := self.store.release_gate_error(candidate):
                    raise ValueError(error)
                result = self.parent(winner)
                base_passed, winner_passed = set(self.base_facts['passed']), set(result['passed'])
                if not (policy.all_gates_pass(result['gates']) and base_passed < winner_passed):
                    raise ValueError('127b 推荐须全部门槛通过、零新增错题且至少修好 1 题')
                receipt = prepare_release(self.engine, candidate, Path(identity['pre_release_backup']))
                published = self.store.publish_candidate(winner, '用户', workflow_release=(
                    receipt['active_version'], candidate['result']['evaluation_run_id'], AUTHORIZED_AT))
            else:
                published = self.store.publish_candidate(winner, '用户')
        self.engine.save(status='completed', phase='published', production_version_id=published['id'],
                         active_candidate=None, used=self.engine.experiment()['evaluation_budget']['used'], last_error=None)

    def run(self, target):
        while True:
            self.engine.check_stop()
            state = self.state()
            if state.get('final'):
                self.finish(state, target)
                return self.engine.state()
            number = max(map(int, state['rounds']), default=1)
            series = state['rounds'].get(str(number))
            if self.final_only and series and series.get('inherited_from') and state['winner_id']:
                winner = self.parent(state['winner_id'])
                if len(winner['passed']) == len(self.question_ids) and policy.all_gates_pass(winner['gates']):
                    reason = '沿用的 Winner 已全部答对并通过门槛'
                    state['final'] = {'winner_id': state['winner_id'], 'full': True, 'reason': reason,
                                      'd_reason': reason, 'd_outcome': 'not_generated'}
                    self.persist(state)
                    continue
            if (series and ('d_review' in series or series.get('review', {}).get('next') == 'continue')):
                if target == 'current_round':
                    self.engine.save(status='round_completed', phase='review')
                    return self.engine.state()
                series = None
                number += 1
            if series is None:
                self.generate(number, state)
                if target == 'next_round':
                    self.engine.save(status='completed', phase='analysis')
                    return self.engine.state()
                continue
            if target == 'next_round':
                self.engine.save(status='completed', phase='analysis')
                return self.engine.state()
            if 'review' not in series:
                candidates = []
                for label in policy.LABELS:
                    candidate = self.sandbox(number, f'{self.id}-R{number:06d}-{label}', state)
                    if not candidate:
                        return self.engine.state()
                    candidates.append(candidate)
                self.review(number, state, candidates)
            elif self.final_only:
                if 'd' not in series:
                    self.choose_final(number, state)
                    continue
                candidate = self.sandbox(number, state['d_attempts'][-1]['candidate_id'], state)
                if not candidate:
                    return self.engine.state()
                self.complete_final_d(number, state, candidate)
            else:
                if 'd' not in series:
                    self.generate_d(state, number)
                candidate = self.sandbox(number, state['d_attempts'][-1]['candidate_id'], state)
                if not candidate:
                    return self.engine.state()
                self.review(number, state, [candidate], after_d=True)
