"""Round decisions for experiments using the v2 evidence ledger."""
from itertools import combinations

from . import rules, verdict
from .agent_mechanism import fault_stage, validate_mechanism
from .composite import parameter_diff, pipeline_config
from .policy import GATE_DEFINITIONS, candidate_rank, validate_candidate_config

STOP_REASON = '证据不足以继续'
COMBINATION = '组合探索，不可归因'
LAYERED_VERSION = '2026-11-25'
LAYERS = ('safety', 'retrieval', 'generation')
GENERATION_REQUIRED = '前置条件未满足：需先对当前底座做生成诊断'


def layered(context):
    return (context.get('verdict_version') or '') >= LAYERED_VERSION


def fault_layer(code):
    return 'retrieval' if code in ('recall', 'ranking', 'final') else code


def target_layer(remaining_failures, gate_failures, severe_safety):
    failures = [fault_layer(code) for code in remaining_failures]
    counts = {layer: failures.count(layer) for layer in LAYERS}
    gates = [fault_layer(code) for code in gate_failures]
    priority = max((layer for layer in LAYERS if layer in gates), key=counts.get, default=None)
    if severe_safety:
        layer, reason = 'safety', '存在严重安全违规'
    elif priority:
        layer, reason = priority, '优先修复未过门槛的根因层'
    else:
        layer = max((layer for layer in LAYERS if counts[layer]), key=counts.get, default=None)
        reason = '剩余错题最多，同数时按上游顺序' if layer else '剩余错题无已知根因层'
    return {'layer': layer, 'reason': reason, 'counts': counts}


def all_gates_pass(gates):
    rows = gates.get('gates') or []
    return (gates.get('passed') is True and len(rows) == len(GATE_DEFINITIONS)
            and {row.get('metric') for row in rows} == {gate['metric'] for gate in GATE_DEFINITIONS}
            and all(row.get('passed') is True for row in rows))


def saved_final_map(store, run_id, *, connection=None, saved=None):
    records = verdict.records(store, run_id, connection=connection) if saved is None else saved
    return {qid: row['final_passed'] for qid, row in records.items()
            if type(row.get('final_passed')) is bool}


def layered_winner(store, baseline, candidates, *, connection=None):
    current = saved_final_map(store, baseline['id'], connection=connection)
    identity = baseline['judge'].get('evaluation_identity')
    winner = None
    eligible = [c for c in candidates if c['status'] == 'evaluated'
                and c['reasoning'].get('candidate_label') in rules.AGENT['candidate_labels']
                and type(c['reasoning'].get('round')) is int
                and c['result'].get('evaluation_complete') is True
                and c['result'].get('qualification', {}).get('qualified') is True
                and identity and c['result'].get('evaluation_identity') == identity
                and all_gates_pass(c['result'].get('gates') or {})]
    for number in sorted({c['reasoning']['round'] for c in eligible}):
        group = [c for c in eligible if c['reasoning']['round'] == number]
        seeds = [c for c in group if c['reasoning'].get('reuse') == '用户授权沿用']
        for peers in (seeds, [c for c in group if c not in seeds]):
            improvements = []
            for candidate in peers:
                result = saved_final_map(store, candidate['result'].get('evaluation_run_id'), connection=connection)
                if result.keys() == current.keys() and (
                        {q for q, passed in current.items() if passed} < {q for q, passed in result.items() if passed}):
                    improvements.append((candidate, result))
            if improvements:
                winner, current = min(improvements, key=lambda pair: (
                    sum(not passed for passed in pair[1].values()), candidate_rank(pair[0])))
    return winner


def validate_layered_limits(config, current, baseline):
    cumulative_limit = rules.AGENT['d_max_changed_parameters']
    round_limit = rules.AGENT['max_changed_parameters']
    if len(parameter_diff(config, pipeline_config(baseline))) > cumulative_limit:
        raise ValueError(f'相对 Baseline 最多改 {cumulative_limit} 个参数（含继承）')
    if len(parameter_diff(config, pipeline_config(current))) > round_limit:
        raise ValueError(f'相对当前底座最多改 {round_limit} 个参数')


def validate_target_layer(proposal, selected, opportunities, target):
    if any(fault_layer(opportunities[row['question_id']]['fault']['code']) == target['layer'] for row in selected):
        return
    if target['capacity'] >= target['proposal_count']:
        raise ValueError('目标层机会足够，每个方案须包含至少一道目标层题')
    reason = proposal.get('layer_reason')
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError('转向其他层须填写 layer_reason')


def round_base(baseline, prior, number, *, identity=None, winner=None, use_layered=False):
    if not use_layered:
        winner = min((c for c in prior if c['status'] == 'evaluated'
                      and c['reasoning'].get('candidate_label') in rules.AGENT['candidate_labels']
                      and c['reasoning'].get('round', number) < number
                      and c['result'].get('evaluation_complete') is not False
                      and c['result'].get('qualification', {}).get('qualified') is True
                      and (identity is None or c['result'].get('evaluation_identity') == identity)),
                     key=candidate_rank, default=None)
    if winner is None:
        return {'id': 'Baseline', 'changes': {}}
    return {'id': winner['id'], 'changes': parameter_diff(winner['config'], pipeline_config(baseline))}


def validate_base(proposal, base):
    expected = None if base['id'] == 'Baseline' else base['id']
    inherited = proposal.get('inherited_parameters', {})
    if proposal.get('inherited_from') != expected or not isinstance(inherited, dict) or inherited != base['changes'] or any(
            type(value) is not type(base['changes'][key]) for key, value in inherited.items()):
        raise ValueError('每个方案须使用完整的当前合格 Winner 底座；无 Winner 时使用 Baseline')
    diff = proposal.get('config_diff')
    if isinstance(diff, dict) and (base['changes'].keys() & diff.keys() or
            'hybrid_alpha' in base['changes'] and diff.get('hybrid_search') is False):
        raise ValueError('新增改动须保留 Winner 底座已有参数')


def validate_combinations(candidates):
    combined = [c for c in candidates if len(c['config_diff']) > 1]
    if len(combined) > 1:
        raise ValueError('每轮最多一个组合方案')
    if any(c.get('attribution') != COMBINATION for c in combined):
        raise ValueError('组合方案须标注“组合探索，不可归因”')


def round_opportunities(targets, base, baseline, prior, preview, current, historical, *, blocked=(),
                        use_layered=False, reserved_keys=(), combination_used=False):
    """Check every supported single change and each potentially evidenced combination."""
    preview = preview or {}
    effective = {**baseline, **base['changes']}
    trial_changes = [{key: value} for key in rules.AGENT['tunable']
                     for value in (rules.AGENT['thinking_values'] if key == 'generation_thinking' else rules.PIPELINE_VALUES[key])
                     if not (type(value) is type(effective.get(key)) and value == effective.get(key))]
    for variant in preview.get('configs', []):
        trial = {**effective, **variant.get('change', {})}
        changes = parameter_diff(trial, effective)
        if 1 < len(changes) <= rules.AGENT['max_changed_parameters']:
            trial_changes.append(changes)
    ledger = [*current, *historical]
    trial_changes.extend(r['changes'] for r in ledger if r['base_id'] == base['id'] and
                         1 < len(r['changes']) <= rules.AGENT['max_changed_parameters'])
    saved_configs = [baseline, *[{k: v for k, v in c['config'].items() if k in rules.PIPELINE_VALUES}
                                 for c in prior]]
    valid = []
    for changes in trial_changes:
        if (changes in valid or base['changes'].keys() & changes.keys()
                or 'generation_thinking' in changes and changes['generation_thinking'] not in rules.AGENT['thinking_values']
                or not set(changes).issubset(rules.AGENT['tunable']) or any(
                type(value) is type(effective.get(key)) and value == effective.get(key) for key, value in changes.items())):
            continue
        config = {**effective, **changes}
        if config.get('hybrid_search') is False and 'hybrid_alpha' not in changes:
            config.pop('hybrid_alpha', None)
        if any(config.get(key) != value for key, value in base['changes'].items()):
            continue
        if use_layered and (changes.keys() & set(reserved_keys) or combination_used and len(changes) > 1
                            or len(parameter_diff(config, pipeline_config(baseline))) > rules.AGENT['d_max_changed_parameters']):
            continue
        if parameter_diff(config, pipeline_config(baseline)) in blocked:
            continue
        # Previously generated but skipped configurations are still reserved by the existing
        # unique-configuration guard. Historical observations remain evidence for a first v2 trial.
        if validate_candidate_config(config, prior_configs=saved_configs)['valid']:
            valid.append(changes)
    next_actions = {
        'recall': '检查索引、分块和召回所需的原始资料',
        'ranking': '核对交付片段，补做同底座检索预演',
        'final': '核对交付片段，补做同底座检索预演',
        'generation': '在独立诊断中复测回答和 Judge，检查推理档位',
        'safety': '用安全专项复核危险操作和拒答规则',
        'unknown': '补齐逐题证据、检索 Trace 或判分依据',
    }
    rows = {}
    for target in targets:
        question = target['question_id']
        view = target['diagnostic_view']
        fault = target.get('mechanism_fault') or fault_stage(target)
        available = []
        for changes in valid:
            # This probes whether real preview evidence exists for a possible cross-layer
            # explanation. The actual proposal must still supply its own explanation.
            [check] = validate_mechanism({'config_diff': changes, 'cross_layer_mechanisms': {question: '待方案逐题说明'}},
                                         [{**target, 'mechanism_fault': fault}], base['id'], preview, ledger,
                                         base_changes=base['changes'])
            if check['decision'] != '拒绝':
                available.append({'changes': changes, 'decision': check['decision']})
        action = ('表格结构化或数据处理，再独立复测' if fault['subtype'] == '表格归类' else next_actions[fault['code']])
        rows[question] = {'display_question_id': view.get('display_question_id') or question, 'fault': fault,
                          'available': available, 'next_action': action,
                          'reason': None if available else '无仍可提交且通过机制校验的未试配置'}
    return rows


def available_labels(rows, labels):
    changes = {frozenset(action['changes']) for row in rows.values() for action in row['available']}
    for count in range(len(labels), 0, -1):
        for group in combinations(changes, count):
            if sum(len(keys) > 1 for keys in group) <= 1 and len(set().union(*group)) == sum(map(len, group)):
                return labels[:count]
    return labels[:0]


def layer_capacity(rows, layer, count):
    changes = {frozenset(action['changes']) for row in rows.values() for action in row['available']}
    preferred = {frozenset(action['changes']) for row in rows.values()
                 if fault_layer(row['fault']['code']) == layer for action in row['available']}
    return max(((sum(keys in preferred for keys in group), size)
                for size in range(1, count + 1) for group in combinations(changes, size)
                if sum(len(keys) > 1 for keys in group) <= 1
                and len(set().union(*group)) == sum(map(len, group))), default=(0, 0))


def layer_plan(rows, gate_faults, severe, ledger, base_id, labels):
    codes = [row['fault']['code'] for row in rows.values()]
    target = target_layer(codes, gate_faults, severe)
    selected = target
    skipped = []
    generation_checked = any(row['source'] == '生成诊断' and row['base_id'] == base_id for row in ledger)
    while layer := selected['layer']:
        relevant = {qid: row for qid, row in rows.items() if fault_layer(row['fault']['code']) == layer}
        capacity, count = layer_capacity(rows, layer, len(labels))
        if capacity or layer == 'generation' and relevant and not generation_checked:
            return {**target, 'layer': layer, 'reason': selected['reason'], 'fallbacks': skipped,
                    'capacity': capacity, 'proposal_count': count,
                    'generation_precondition': layer == 'generation' and not generation_checked}
        skipped.append({'layer': layer, 'reason': '当前底座无可用机会'})
        excluded = {item['layer'] for item in skipped}
        selected = target_layer([code for code in codes if fault_layer(code) not in excluded],
                                [code for code in gate_faults if fault_layer(code) not in excluded], False)
    return {**target, 'layer': None, 'reason': '没有仍可验证的目标层机会',
            'fallbacks': skipped, 'capacity': 0, 'proposal_count': 0}


def layer_signals(store, run_id, gates, faults):
    from .evaluation import gate_details

    cases = verdict.gate_cases(store, run_id)
    failed = [gate for gate in gates if gate.get('status') == 'FAIL' and not gate['metric'].startswith('latency_')]
    gate_faults = [faults[item['question_id']]['code'] for gate in gate_details(cases, failed)
                   for item in gate['failed_cases'] if item['question_id'] in faults]
    saved = verdict.records(store, run_id)
    severe = any(any(s['risk'] for s in saved.get(qid, {}).get('samples', [])) for qid in faults)
    return gate_faults, severe


def inherited_repairs(base, prior, ledger, passed):
    by_id = {candidate['id']: candidate for candidate in prior}
    lineage = set()
    source = base['id']
    while source in by_id and source not in lineage:
        lineage.add(source)
        source = by_id[source]['reasoning'].get('inherited_from')
    return [row for row in ledger if row['candidate_id'] in lineage and row['status'] == '修好'
            and row['question_id'] in passed and len(row['changes']) == 1
            and all(key in base['changes'] and base['changes'][key] == value
                    for key, value in row['changes'].items())]


def previous_commitment(context, number):
    previous = context.get('hypothesis_chain', {}).get(str(number - 1))
    if previous is None:
        return None
    outcomes = {row['question_id']: row['status'] for row in context['parameter_effect_ledger']['current']
                if row['candidate_id'] == previous['candidate_id']}
    statuses = [outcomes.get(q, '未知') for q in previous['question_ids']]
    outcome = ('false' if any(s in {'无效', '弄坏'} for s in statuses) else
               'true' if statuses and all(s == '修好' for s in statuses) else 'unknown')
    return {'round': number - 1, 'outcome': outcome, 'expected': previous.get(f'if_{outcome}'),
            'question_outcomes': dict(zip(previous['question_ids'], statuses))}


def check_commitment(previous, action, *, changes=(), reason=None):
    if previous is None:
        return None
    expected = previous['expected'] or {}
    fulfilled = expected.get('action') == action and (action != 'try' or expected.get('changes') in changes)
    if not fulfilled and (not isinstance(reason, str) or not reason.strip()):
        raise ValueError('没有兑现上一轮分支承诺，须写明偏离理由')
    return {**previous, 'actual_action': action, 'fulfilled': fulfilled,
            'reason': None if fulfilled else reason.strip()}


def validate_hypothesis(plan, candidates, inherited, excluded, previous):
    if not isinstance(plan, dict) or not isinstance(plan.get('hypothesis'), str) or not plan['hypothesis'].strip():
        raise ValueError('须写本轮 hypothesis_plan.hypothesis')
    test = next((c for c in candidates if c['id'] == plan.get('test_candidate')), None)
    if test is None:
        raise ValueError('本轮假设须绑定一个实际方案 test_candidate')
    for key in ('if_true', 'if_false'):
        branch = plan.get(key)
        if not isinstance(branch, dict) or branch.get('action') not in ('try', 'stop', 'D'):
            raise ValueError(f'须写明 {key} 的下一步（try/stop/D）')
        if branch['action'] == 'try':
            changes = branch.get('changes')
            if (not isinstance(changes, dict) or not 0 < len(changes) <= rules.AGENT['max_changed_parameters']
                    or not set(changes).issubset(rules.AGENT['tunable'])
                    or any(not any(type(value) is type(item) and value == item for item in rules.PIPELINE_VALUES[key])
                           for key, value in changes.items())):
                raise ValueError(f'{key} 须写明合法的下一步参数和值')
    check = check_commitment(previous, 'try', changes=[c['config_diff'] for c in candidates],
                             reason=plan.get('deviation_reason'))
    return {**{key: plan[key] for key in ('hypothesis', 'test_candidate', 'if_true', 'if_false')},
            'inherit': inherited, 'exclude': excluded, 'question_ids': test['predicted_fixed_question_ids'],
            'previous_check': check}
