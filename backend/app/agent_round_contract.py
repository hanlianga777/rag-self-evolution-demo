"""Round decisions for experiments using the v2 evidence ledger."""
from itertools import combinations

from . import rules
from .agent_mechanism import fault_stage, validate_mechanism
from .composite import parameter_diff, pipeline_config
from .policy import candidate_rank, validate_candidate_config

STOP_REASON = '证据不足以继续'
COMBINATION = '组合探索，不可归因'


def round_base(baseline, prior, number, *, identity=None):
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


def round_opportunities(targets, base, baseline, prior, preview, current, historical, *, blocked=()):
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
        if parameter_diff(config, pipeline_config(baseline)) in blocked:
            continue
        # Previously generated but skipped configurations are still reserved by the existing
        # unique-configuration guard. Historical observations remain evidence for a first v2 trial.
        if validate_candidate_config(config, prior_configs=saved_configs)['valid']:
            valid.append(changes)
    next_actions = {
        'recall': '检查索引、分块和召回所需的原始资料',
        'ranking': '核对交付片段，补做同底座检索预演',
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
