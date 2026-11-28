"""Version 126c decisions over saved Sandbox evidence."""
from collections import defaultdict

from . import rules
from .composite import parameter_diff, pipeline_config
from .policy import (ALLOWED_SEARCH_SPACE, PERFORMANCE_METRICS, SAFETY_METRICS,
                     all_gates_pass, validate_candidate_config)

VERSION = '126c'
FINAL_ONLY_VERSION = '127a'
VERSIONS = (VERSION, FINAL_ONLY_VERSION)
E8_BASELINE = 'EVAL-20261126212249302614'
LABELS = ('A', 'B', 'C')
LAYERS = ('safety', 'retrieval', 'generation', 'performance')
QUERY = ('query_rewrite', 'multi_query', 'hyde', 'query_decompose')
RETRIEVAL = (*QUERY, 'candidate_k', 'top_k', 'min_score', 'rerank',
             'hybrid_alpha', 'hybrid_search', 'retrieval_max_tokens')
TOOLS = {'safety': ('prompt_strategy',), 'retrieval': RETRIEVAL,
         'generation': ('generation_thinking', 'prompt_strategy'),
         'performance': ('generation_thinking', *RETRIEVAL)}
COMBINATION = '组合机制假设，单项贡献尚未单独验证'
SIGNALS = {
    'S1': ('首轮无 Winner', {'different_hypotheses': '以 Baseline 提出三个不同假设'}),
    'S2': ('多个方案合格', {'select_winner': '从严格增量方案中选 Winner', 'select_branch': '选互补支线', 'record_lessons': '把试跑证据留在账本'}),
    'S3': ('本轮全不合格', {'keep_base': '保留原底座', 'mitigate': '在原底座改良局部机制', 'switch_mechanism': '换机制', 'switch_layer': '换层'}),
    'S4': ('有 Winner，本轮无增量', {'branch_base': '用支线作底座', 'switch_mechanism': '换机制', 'withdraw': '撤销可疑改动', 'try_d': '按需试 D'}),
    'S5': ('连续两轮无增量', {'continue': '继续验证可信假设', 'try_d': '验证互补组合', 'finish': '满足收敛条件后结束'}),
    'S6': ('支线保住并超过主线', {'promote_branch': '晋升支线，原主线改作支线'}),
    'S7': ('支线总分更高但丢了主线成果', {'keep_branch': '作为支线保留', 'combine_later': '记录互补机制并研究组合'}),
    'S8': ('单参数有收益也有副作用', {'mitigate': '以双参数组合缓解', 'equivalent': '改试等效参数', 'leave_for_d': '保留证据供 D 综合'}),
    'S9': ('错题涉及多层', {'default_slots': '默认按优先级分配方案', 'adjust_slots': '说明依据后调整名额'}),
    'S10': ('存在没有错题的层', {'leave_layer': '不动该层', 'cross_layer': '说明跨层作用后探索'}),
    'S11': ('质量提升但耗时增加', {'tradeoff': '门槛内接受耗时增加', 'prefer_faster': '同质量优先选更快方案'}),
    'S12': ('未通过性能门槛', {'optimize_stage': '按分阶段耗时选性能目标'}),
    'S13': ('出现安全题回退', {'avoid': '分析参数并避开', 'mitigate': '分析参数并缓解'}),
    'S14': ('工具已试过或属于能力边界', {'engineering': '结束该类题的参数优化并给工程建议'}),
    'S15': ('三样本判定不一致', {'use_recheck': '以变化题的复核结论为准'}),
    'S16': ('全部答对且通过门槛', {'publish': '结束并发布推荐'}),
    'S17': ('提案被拒绝', {'revise': '按拒绝原因修正并重提'}),
    'S18': ('Sandbox 技术中断', {'resume': '从断点续跑并复用保存结果'}),
    'S19': ('上轮预测与实测偏差大', {'retrospect': '先复盘出错的假设，再提新方案'}),
    'S20': ('底座累计改动已到四项', {'replace': '替换已有参数', 'withdraw': '撤销已有参数'}),
    'S21': ('预演显示有回退风险', {'deprioritize': '降低排序', 'mitigate': '提供缓解假设后仍可试跑'}),
}


def enabled(state):
    return state.get('decision_contract_version') in VERSIONS


def menu(fault):
    subtype = fault.get('subtype')
    kind = fault.get('question_type') or ''
    if subtype == '没检索到':
        if any(word in kind for word in ('别名', '口语', '弱关键词')):
            return ('query_rewrite', 'multi_query'), ('hyde', 'hybrid_alpha')
        if any(word in kind for word in ('跨段', '桥接', '复杂子问')):
            return ('query_decompose', 'multi_query'), ('candidate_k', 'hyde')
        return ('candidate_k', 'min_score'), ('multi_query', 'hybrid_alpha')
    return {
        '找到但没交给模型': (('top_k', 'rerank'), ('candidate_k', 'min_score')),
        '表格理解错': (('generation_thinking', 'prompt_strategy'), ('top_k',)),
        '漏要点': (('top_k', 'prompt_strategy'), ('query_decompose', 'generation_thinking')),
        '过度拒答': (('prompt_strategy',), ('generation_thinking',)),
        '该追问没追问': (('prompt_strategy',), ('generation_thinking',)),
        '安全越界': (('prompt_strategy',), ()),
        '慢': (performance_tools(fault.get('stage_shares', [])), ()),
    }.get(subtype, ((), ()))


def performance_tools(stages):
    names = ' '.join(row['stage'].lower() for row in stages[:2])
    keys = []
    for words, tools in (
        (('generation', 'answer', '生成', '回答'), ('generation_thinking', 'top_k', 'retrieval_max_tokens')),
        (('query', 'rewrite', 'hyde', '查询', '改写'), QUERY),
        (('retriev', 'rerank', '检索', '重排'), ('candidate_k', 'top_k', 'rerank', 'hybrid_alpha')),
    ):
        if any(word in names for word in words):
            keys.extend(tools)
    return tuple(dict.fromkeys(keys)) or ('generation_thinking', 'candidate_k', 'top_k', *QUERY)


def gate_rows(facts, metrics):
    return {row['metric']: row for row in facts['gates'].get('gates', []) if row['metric'] in metrics}


def difference(after, before):
    yes, old = set(after['passed']), set(before['passed'])
    return {'fixed': sorted(yes - old), 'broken': sorted(old - yes)}


def faster(after, before, *, ratio=0.9):
    now, old = gate_rows(after, PERFORMANCE_METRICS), gate_rows(before, PERFORMANCE_METRICS)
    if set(now) != set(old) or not now or any(
            row['actual'] is None or old[key]['actual'] is None or row['actual'] > old[key]['actual']
            for key, row in now.items()):
        return False
    return any(row['actual'] < old[key]['actual'] and row['actual'] <= ratio * old[key]['actual']
               for key, row in now.items())


def qualifications(after, baseline, parent, winner):
    vs_base, vs_parent, vs_winner = [difference(after, before) for before in (baseline, parent, winner)]
    def safe_against(before):
        old = gate_rows(before, SAFETY_METRICS)
        return (not after['safety'] and not (set(after.get('safety_failed', ())) - set(before.get('safety_failed', ())))
                and not any(old[key]['passed'] and not row['passed'] for key, row in
                            gate_rows(after, SAFETY_METRICS).items() if key in old))
    current = gate_rows(after, PERFORMANCE_METRICS)
    repair = lambda ref: sorted(k for k, row in gate_rows(ref, PERFORMANCE_METRICS).items()
                                if not row['passed'] and current.get(k, {}).get('passed'))
    gates_kept = all(not row['passed'] or current.get(key, {}).get('passed')
                     for key, row in gate_rows(parent, PERFORMANCE_METRICS).items())
    qualified = bool(all_gates_pass(after['gates']) and safe_against(baseline) and vs_base['fixed'] and not vs_base['broken'])
    effective = bool(safe_against(parent) and gates_kept and not vs_parent['broken'] and (vs_parent['fixed'] or repair(parent)))
    increment = bool(qualified and safe_against(winner) and not vs_winner['broken'] and
                     (vs_winner['fixed'] or repair(winner) or faster(after, winner)))
    return {'qualified': qualified, 'effective': effective, 'promoted': increment,
            'vs_baseline': vs_base, 'vs_parent': vs_parent, 'vs_winner': vs_winner,
            'performance_repaired': repair(parent), 'safe_vs_baseline': safe_against(baseline),
            'safety_regression': not all(map(safe_against, (baseline, parent, winner)))}


def config_diff(config, reference):
    changes = parameter_diff(config, pipeline_config(reference))
    if config.get('hybrid_search') is False:
        changes.pop('hybrid_alpha', None)
    return changes


def changed_config(baseline, parent, changes, *, previous=()):
    baseline, parent = pipeline_config(baseline), pipeline_config(parent)
    if not isinstance(changes, dict) or not changes or set(changes) - set(ALLOWED_SEARCH_SPACE):
        raise ValueError('改动必须来自参数白名单')
    config = {**parent, **changes}
    if config.get('hybrid_search') is False and 'hybrid_alpha' not in changes:
        config.pop('hybrid_alpha', None)
    checked = validate_candidate_config(config)
    if not checked['valid']:
        raise ValueError('参数白名单或取值约束：' + str(checked))
    config = pipeline_config(config)
    actual = config_diff(config, parent)
    if not actual or set(actual) != set(changes):
        raise ValueError('每项改动都必须改变父方案配置')
    if len(actual) > 2:
        raise ValueError('相对父方案最多改 2 项')
    inherited = config_diff(parent, baseline)
    cumulative = config_diff(config, baseline)
    if len(cumulative) > 4 or len(inherited) == 4 and set(cumulative) - set(inherited):
        raise ValueError('累计最多 4 项，已到上限时只能替换取值或撤销已有项')
    if any(config == pipeline_config(other) for other in (baseline, *previous)):
        raise ValueError('配置重复')
    if config.get('hybrid_search') is False:
        config.pop('hybrid_alpha', None)
    return config


def may_finish(conditions, *, full):
    return conditions['qualified'] and (full or all(conditions.values()))


def text_field(row, key):
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{key} 必须填写具体说明')
    return value.strip()


def signal(code, **evidence):
    title, actions = SIGNALS[code]
    return {'id': code, 'title': title, 'legal_actions': actions, 'evidence': evidence}


def validate_actions(response, signals):
    actions = response.get('actions')
    if not isinstance(actions, list) or any(not isinstance(row, dict) for row in actions):
        raise ValueError('actions 必须为对象列表')
    allowed = {row['id']: row['legal_actions'] for row in signals}
    details = {row['id']: row['evidence'] for row in signals}
    selected = defaultdict(set)
    for row in actions:
        sid, action = row.get('signal'), row.get('action')
        if not isinstance(sid, str) or not isinstance(action, str) or action not in allowed.get(sid, {}):
            raise ValueError('actions 包含本次情况不允许的动作')
        if action in selected[sid]:
            raise ValueError('同一个情况动作不可重复')
        text_field(row, 'reason')
        if sid == 'S19':
            revisions = row.get('revisions')
            if not isinstance(revisions, dict) or set(revisions) != {c['id'] for c in details[sid]['candidates']}:
                raise ValueError('S19 revisions 须逐条引用偏差较大的候选')
            for cid in revisions:
                text_field(revisions, cid)
        selected[sid].add(action)
    if set(selected) != set(allowed):
        raise ValueError('actions 需要回应每条情况信号')
    if len(selected.get('S9', ())) > 1:
        raise ValueError('S9 的互斥动作只能选一个')
    return selected


def actions_for(signals, code, permitted):
    for row in signals:
        if row['id'] == code:
            row['legal_actions'] = {key: label for key, label in row['legal_actions'].items() if key in permitted}


def planning_signals(context):
    layers = context['priorities']
    last = context.get('previous_round') or {}
    signals = []
    if context['round'] == 1:
        signals.append(signal('S1'))
    if len(layers) > 1:
        signals.append(signal('S9', priorities=layers, default=context['default_slots']))
    if inactive := sorted(set(LAYERS) - set(layers)):
        signals.append(signal('S10', inactive=inactive))
    if context['performance']['failed_gates']:
        signals.append(signal('S12', **context['performance']))
    if boundaries := context.get('boundaries'):
        signals.append(signal('S14', questions=boundaries))
    if misses := [entry for entry in last.get('outcomes', []) if entry['prediction']['large_deviation']]:
        signals.append(signal('S19', candidates=[{k: row[k] for k in ('id', 'hypothesis', 'prediction')} for row in misses]))
    if capped := [parent for parent, facts in context['parents'].items()
                  if len(config_diff(facts['config'], context['baseline_config'])) == 4]:
        signals.append(signal('S20', parents=capped))
    if risks := context.get('preview_risks'):
        signals.append(signal('S21', risks=risks))
    # The previous review can choose a direction before the next planning request.
    if last.get('all_unqualified'):
        signals.append(signal('S3', local_effects=last['outcomes']))
    if context.get('winner_id') and last.get('plateau'):
        signals.append(signal('S4', winner=context['winner_id'], branch=context.get('branch_id')))
        permitted = {'switch_mechanism', 'withdraw'} if parameter_diff(
            context['parents'][context['winner_id']]['config'], context['baseline_config']) else {'switch_mechanism'}
        if context.get('branch_id') and not last.get('all_unqualified'):
            permitted.add('branch_base')
        if context.get('d_available'):
            permitted.add('try_d')
        actions_for(signals, 'S4', permitted)
    if unsafe := [row for row in last.get('outcomes', []) if row['labels']['safety_regression']]:
        signals.append(signal('S13', candidates={row['id']: {'changes': row['changes'], 'safety': row.get('safety'),
                                                            'safety_failed': row.get('safety_failed')} for row in unsafe}))
    return signals


def review_signals(outcomes, previous_winner, branch, streak, conditions, *, full, d_available):
    signals = []
    if sum(row['labels']['qualified'] for row in outcomes) > 1:
        signals.append(signal('S2', qualified=[row['id'] for row in outcomes if row['labels']['qualified']]))
        if not any(row['labels']['promoted'] for row in outcomes):
            actions_for(signals, 'S2', {'select_branch', 'record_lessons'})
    if outcomes and all(not row['labels']['qualified'] for row in outcomes):
        signals.append(signal('S3'))
    if previous_winner and conditions['plateau']:
        signals.append(signal('S4', winner=previous_winner, branch=branch))
        actions_for(signals, 'S4', {'switch_mechanism', 'withdraw', *({'branch_base'} if branch else ()),
                                     *({'try_d'} if d_available else ())})
    if streak >= 2:
        signals.append(signal('S5', rounds=streak))
        actions_for(signals, 'S5', {'continue', *({'try_d'} if d_available else ()),
                                     *({'finish'} if may_finish(conditions, full=full) else ())})
    if promoted_branch := [row['id'] for row in outcomes if row['from_branch'] and row['labels']['promoted']]:
        signals.append(signal('S6', candidates=promoted_branch))
    if sidelined := [row['id'] for row in outcomes if row['from_branch'] and row['higher_score']
                     and row['labels']['vs_winner']['broken']]:
        signals.append(signal('S7', candidates=sidelined))
    if tradeoffs := [row['id'] for row in outcomes if len(row['changes']) == 1
                     and row['labels']['vs_parent']['fixed'] and row['side_effect']]:
        signals.append(signal('S8', candidates=tradeoffs))
    if slower := [row['id'] for row in outcomes if row['slower_and_better']]:
        signals.append(signal('S11', candidates=slower))
    if slow := {row['id']: row['performance'] for row in outcomes if row['performance']['failed_gates']}:
        signals.append(signal('S12', candidates=slow))
    if unsafe := {row['id']: {'changes': row['changes'], 'safety_failed': row.get('safety_failed'),
                             'safety': row.get('safety')} for row in outcomes if row['labels']['safety_regression']}:
        signals.append(signal('S13', candidates=unsafe))
    if unstable := {row['id']: row['judge_disagreements'] for row in outcomes if row['judge_disagreements']}:
        signals.append(signal('S15', candidates=unstable))
    if full:
        signals.append(signal('S16'))
    return signals


def question_ids(row, field, allowed):
    values = row.get(field)
    if (not isinstance(values, list) or any(not isinstance(q, str) or q not in allowed for q in values)
            or len(set(values)) != len(values)):
        raise ValueError(f'{field} 必须填入不重复且属于比较底座的冻结题号')
    return values


def preview_matches(context, config):
    values = pipeline_config(config)
    coordinates = {key: values[key] for key in RETRIEVAL}
    return [risk for risk in context.get('preview_risks', []) if risk['config'] == coordinates]


def validate_draft(draft, label, context, choices, previous):
    if not isinstance(draft, dict) or draft.get('label') != label:
        raise ValueError(f'{label} 方案须使用指定位置')
    baseline = context['baseline_id']
    parent_id = text_field(draft, 'parent_id')
    if parent_id not in context['parents']:
        raise ValueError('父方案须为本实验的 Baseline、主线或支线')
    winner = context.get('winner_id')
    if (context['round'] == 1 and parent_id != baseline or label in ('A', 'D') and parent_id != (winner or baseline)):
        raise ValueError('首轮均用 Baseline，A 和 D 必须用当前主线')
    parent = context['parents'][parent_id]
    changes = draft.get('changes')
    config = changed_config(context['baseline_config'], parent['config'], changes, previous=previous)
    hypothesis = text_field(draft, 'hypothesis')
    hypothesis_key = ''.join(ch.casefold() for ch in hypothesis if ch.isalnum())
    if not hypothesis_key or hypothesis_key in context.get('hypotheses', ()):
        raise ValueError('机制假设重复或缺少内容')
    text_field(draft, 'reason')
    expected = question_ids(draft, 'expected_fixed', set(context['question_ids']) - set(parent['passed']))
    risk = question_ids(draft, 'possible_broken', set(parent['passed']))
    layer = draft.get('layer')
    if not isinstance(layer, str) or layer not in LAYERS:
        raise ValueError('layer 必须是安全、检索、生成或性能的合法标识')
    referenced = draft.get('signals')
    if (not isinstance(referenced, list) or any(not isinstance(s, str) or s not in choices for s in referenced)
            or not referenced and choices):
        raise ValueError('signals 必须引用当前 Agent 已应对的情况')
    targets = context['targets_by_parent'][parent_id]
    performance = parent['performance']
    if layer == 'performance':
        metrics = draft.get('performance_targets')
        if (not isinstance(metrics, list) or not metrics
                or any(metric not in performance['failed_gates'] for metric in metrics)):
            raise ValueError('performance_targets 必须引用父方案未通过的性能门槛')
    elif not expected and layer in context['priorities']:
        raise ValueError('预计修好题或性能目标至少填一项')
    active_layers = set(context['priorities'])
    tool_layers = set()
    for key, value in changes.items():
        if key == 'prompt_strategy':
            tool_layers.add('safety' if value == rules.SAFE else 'generation')
        else:
            tool_layers.add('retrieval' if key in RETRIEVAL else 'generation')
    if layer != 'performance' and tool_layers - active_layers and label != 'D':
        if 'cross_layer' not in choices.get('S10', ()):
            raise ValueError('S10 没有错题的层，只能说明跨层作用后改动')
        text_field(draft, 'cross_layer_reason')
    if label != 'D':
        target_layers = {targets.get(q, {}).get('layer') for q in expected}
        if layer not in active_layers or expected and layer not in target_layers and layer != 'performance':
            if 'cross_layer' not in choices.get('S10', ()) and layer not in active_layers:
                raise ValueError('没有错题的层，只能按 S10 说明跨层作用')
            text_field(draft, 'cross_layer_reason')
        if not expected and layer != 'performance':
            examined = question_ids(draft, 'investigate_questions', set(context['question_ids']) - set(parent['passed']))
            if not examined:
                raise ValueError('探索方案须列出仍待处理的题')
        else:
            examined = []
        diagnostic_rows = [targets[q] for q in (*expected, *examined) if q in targets]
        recommended = {key for row in diagnostic_rows for key in row['recommended']}
        exploratory = {key for row in diagnostic_rows for key in row['exploratory']}
        if layer == 'performance':
            recommended.update(performance['tools'])
        off_menu = set(changes) - recommended - exploratory
        # S3/S4 allow reverting inherited changes instead of treating a withdrawal as a new tool.
        inherited = config_diff(parent['config'], context['baseline_config'])
        off_menu -= inherited.keys() if set(referenced) & {'S3', 'S4', 'S20'} else set()
        if off_menu and label != 'C' and not any(
                row['parent_id'] == parent_id and row['changes'] == changes
                for row in context.get('remaining_configurations', ())):
            raise ValueError('菜单外的参数只能由 C 作差异化探索')
        if off_menu or set(changes) - recommended:
            text_field(draft, 'exploration_reason')
        if (layer == 'safety' or any(row['layer'] == 'safety' for row in diagnostic_rows)) and (
                changes.get('prompt_strategy') != rules.SAFE and parent['config']['prompt_strategy'] != rules.SAFE):
            raise ValueError('修复安全越界须使用 Safe 提示词')
    else:
        examined = []
    if len(changes) == 2 and draft.get('combination_type') not in ('dependency', 'mitigation', 'cross_layer'):
        raise ValueError('双参数方案须标注依赖、抵消副作用或跨层协同')
    if preview_matches(context, config):
        if 'mitigate' not in choices.get('S21', ()):
            raise ValueError('S21 风险方案仍要试跑时须选择缓解动作')
        text_field(draft, 'mitigation')
    if len(config_diff(parent['config'], context['baseline_config'])) == 4:
        withdrawn = any(key not in config_diff(config, context['baseline_config']) for key in changes)
        if ('withdraw' if withdrawn else 'replace') not in choices.get('S20', ()):
            raise ValueError('S20 动作须对应撤销或替换改动')
    return {'config': config, 'reasoning': {
        **draft, 'hypothesis_key': hypothesis_key, 'candidate_label': label, 'round': context['round'],
        'inherited_from': parent_id if parent_id != baseline else None,
        'changed_parameters': changes, 'changed_parameters_vs_baseline': config_diff(config, context['baseline_config']),
        'predicted_fixed_question_ids': expected, 'predicted_regression_question_ids': risk,
        'observed_evidence': expected + examined, 'core_idea': hypothesis,
        'proposal': draft['reason'], 'combination_note': COMBINATION if len(changes) == 2 else None,
        'decision_contract_version': context.get('decision_contract_version', VERSION), 'planned_tools': {
            qid: sorted(set(changes) & set(targets[qid]['recommended'])) for qid in (*expected, *examined) if qid in targets},
    }}


def validate_plan(response, context, signals):
    choices = validate_actions(response, signals)
    context = {**context, 'hypotheses': list(context['hypotheses'])}
    drafts = response.get('proposals')
    if not isinstance(drafts, list) or len(drafts) != len(LABELS):
        raise ValueError('proposals 必须按 A、B、C 顺序完整填写')
    previous, accepted = list(context['previous_configs']), []
    for label, draft in zip(LABELS, drafts):
        try:
            prepared = validate_draft(draft, label, context, choices, previous)
        except ValueError as error:
            raise ValueError(f'proposals.{label} {error}') from error
        previous.append(prepared['config'])
        context['hypotheses'].append(prepared['reasoning']['hypothesis_key'])
        accepted.append(prepared)
    layers = [row['reasoning']['layer'] for row in accepted]
    if 'default_slots' in choices.get('S9', ()) and (layers[0] != context['default_slots'][0]
            or sorted(layers) != sorted(context['default_slots'])):
        raise ValueError('S9 须采用默认名额或说明调整理由')
    if 'safety' in context['priorities'] and layers[0] != 'safety':
        raise ValueError('安全错因优先，须保留至少一个安全名额')
    if 'S12' in choices and 'performance' not in layers:
        raise ValueError('S12 须指定至少一个性能方案')
    if 'branch_base' in choices.get('S4', ()) and not any(
            row['reasoning']['parent_id'] == context.get('branch_id') for row in accepted):
        raise ValueError('S4 选择支线底座时须有对应方案')
    if 'withdraw' in choices.get('S4', ()) and not any(
            row['reasoning']['parent_id'] == context['winner_id'] and
            set(row['reasoning']['changed_parameters']) - set(row['reasoning']['changed_parameters_vs_baseline'])
            for row in accepted):
        raise ValueError('S4 选择撤销时须在主线方案中撤销改动')
    if 'S13' in choices:
        unsafe = next(row['evidence']['candidates'] for row in signals if row['id'] == 'S13')
        for row in accepted:
            changes = row['reasoning']['changed_parameters']
            if any(all(changes.get(key) == value for key, value in entry['changes'].items())
                   for entry in unsafe.values()):
                if 'mitigate' not in choices['S13']:
                    raise ValueError('S13 已观察到的安全回退参数组合须避开或缓解')
                text_field(row['reasoning'], 'mitigation')
    if context.get('previous_round', {}).get('all_unqualified') and any(
            row['reasoning']['parent_id'] != (context.get('winner_id') or context['baseline_id']) for row in accepted):
        raise ValueError('S3 轮次必须保留原主线底座，可重新组合局部机制')
    return accepted


def coverage(targets, ledger):
    attempted = defaultdict(set)
    for entry in ledger:
        for qid, tools in entry['planned_tools'].items():
            attempted[qid].update(tools)
    pending, closed = {}, {}
    for qid, target in targets.items():
        recommended = set(target['recommended'])
        if missing := recommended - attempted[qid]:
            pending[qid] = sorted(missing)
        else:
            closed[qid] = {'reason': target['reason'], 'tested': sorted(recommended & attempted[qid]),
                           'capability_boundary': not bool(recommended)}
    return pending, closed


def complementary_combinations(context, ledger):
    """Find feasible, untried ways of transferring a measured complementary effect."""
    winner = context.get('winner_id')
    if not winner:
        return []
    parent = context['parents'][winner]
    remaining = set(context['question_ids']) - set(parent['passed'])
    if not remaining:
        return []
    result = []
    for source in ledger:
        gained = remaining & set(source['passed'])
        patch = {key: value for key, value in source['changes'].items() if value != parent['config'][key]}
        if not gained or not patch:
            continue
        mitigation = bool(source['side_effect'] or not source['labels']['qualified'])
        variants = [patch] if not mitigation else []
        if len(patch) == 1:
            for key, values in ALLOWED_SEARCH_SPACE.items():
                if key not in patch:
                    variants.extend({**patch, key: value} for value in values if value != parent['config'][key])
        for changes in variants:
            try:
                changed_config(context['baseline_config'], parent['config'], changes, previous=context['previous_configs'])
            except ValueError:
                continue
            result.append({'source': source['id'], 'questions': sorted(gained), 'changes': changes,
                           'requires_mitigation': mitigation})
    return result


def branch_options(ledger, winner_id, winner):
    usable = []
    for entry in ledger:
        if entry['id'] == winner_id:
            continue
        extra = difference(entry, winner)['fixed']
        quicker = faster(entry, winner)
        if extra or quicker:
            usable.append({'id': entry['id'], 'qualified': entry['labels']['qualified'],
                           'complementary': extra, 'faster': quicker})
    qualified = [row for row in usable if row['qualified']]
    return qualified or usable


def select_review(response, context, signals):
    choices = validate_actions(response, signals)
    winner, branch = response.get('winner_id'), response.get('branch_id')
    if winner is not None and not isinstance(winner, str) or branch is not None and not isinstance(branch, str):
        raise ValueError('winner_id 和 branch_id 必须是保存的 ID 或 null')
    promotions = context['promotions']
    if promotions and winner not in promotions or not promotions and winner != context['winner_id']:
        raise ValueError('Winner 须从保住主线成果且严格增量的合格方案中选')
    if 'select_winner' in choices.get('S2', ()) and winner not in promotions:
        raise ValueError('S2 选择须有对应的新 Winner')
    branches = context['branches_by_winner'][winner or context['baseline_id']]
    if winner in context['branch_promotions']:
        if 'promote_branch' not in choices.get('S6', ()) or branch != context['winner_id']:
            raise ValueError('S6 晋升支线时原主线须转为支线')
    elif branch and branch not in {row['id'] for row in branches}:
        raise ValueError('支线须有互补题或可核实的性能优势，并优先选择合格项')
    if 'select_branch' in choices.get('S2', ()) and not branch:
        raise ValueError('S2 选支线须给出支线 ID')
    if branch or branches or winner != context['winner_id']:
        text_field(response, 'selection_reason')
    if winner in context['same_quality_faster']:
        raise ValueError('S11 选择同质量更快方案时须按实测选择')
    if 'promote_branch' in choices.get('S6', ()) and winner not in context['branch_promotions']:
        raise ValueError('S6 请选择已保住主线且严格增量的支线方案')
    if 'keep_branch' in choices.get('S7', ()) and branch not in context['sidelined']:
        raise ValueError('S7 选择保留时须引用对应支线')
    step = response.get('next')
    if not isinstance(step, str) or step not in context['legal_next']:
        raise ValueError('next 须符合程序提供的继续、D 和结束条件')
    text_field(response, 'next_reason')
    if 'S16' in choices and step != 'finish':
        raise ValueError('满分且有合格 Winner 时必须正常结束')
    if 'finish' in choices.get('S5', ()) and step != 'finish':
        raise ValueError('S5 所选结束动作须与 next 一致')
    if any('try_d' in values for values in choices.values()) and step != 'd':
        raise ValueError('所选综合动作须对应 next=d')
    return winner, branch, step


def round_actions(signals, *, closing=False):
    """Keep 127a round actions focused on A/B/C and recording tradeoffs."""
    for row in signals:
        code = row['id']
        if code in {'S4', 'S5'}:
            if closing:
                row['legal_actions'] = {'record_plateau': '记录本轮无新增晋升'}
            else:
                actions_for([row], code, set(row['legal_actions']) - {'try_d', 'finish'})
        if code == 'S8':
            row['legal_actions'] = {k: v for k, v in row['legal_actions'].items() if not closing and k != 'leave_for_d'}
            row['legal_actions']['record_tradeoff'] = '记录实测收益与副作用'


def remaining_configurations(context):
    """List executable single and paired changes when the diagnosis menu is thin."""
    from itertools import combinations

    result, ordinary = [], set()
    main = context['winner_id'] or context['baseline_id']
    for parent_id, parent in context['parents'].items():
        if context['previous_round'].get('all_unqualified') and parent_id != main:
            continue
        targets = context['targets_by_parent'][parent_id].values()
        menu = {k for row in targets for k in (*row['recommended'], *row['exploratory'])}
        if parent['performance']['failed_gates']:
            menu.update(parent['performance']['tools'])
        prior = config_diff(parent['config'], context['baseline_config'])
        current = pipeline_config(parent['config'])
        values = [(key, value) for key, allowed in ALLOWED_SEARCH_SPACE.items() for value in allowed
                  if value != current[key] and (len(prior) < 4 or key in prior)]
        for patch in (*((item,) for item in values), *combinations(values, 2)):
            changes = dict(patch)
            if len(changes) != len(patch):
                continue
            try:
                config = changed_config(context['baseline_config'], current, changes, previous=context['previous_configs'])
            except ValueError:
                continue
            if changes.keys() <= menu:
                ordinary.add(rules.canonical_hash(pipeline_config(config)))
                if len(ordinary) >= 3:
                    return []
            operations = {key: 'withdraw' if value == context['baseline_config'][key] else 'replace'
                          for key, value in changes.items() if key in prior}
            result.append({'parent_id': parent_id, 'changes': changes, 'operations': operations})
    return result


def final_combinations(context):
    """Offer mitigation retries and transfers of measured complementary gains."""
    winner = context['parents'][context['winner_id']]
    current = pipeline_config(winner['config'])
    remaining = set(context['question_ids']) - set(winner['passed'])
    ledger = context['ledger']
    retry_questions = {row['id']: sorted(remaining & set(row['labels']['vs_parent']['fixed']))
                       for row in ledger if row['side_effect'] and len(row['changes']) == 1}
    retry_sources = [row for row in ledger if retry_questions.get(row['id'])]
    retries = [{'sources': [row['source']], 'questions': retry_questions[row['source']], 'changes': row['changes']}
               for row in complementary_combinations(context, retry_sources) if len(row['changes']) == 2]
    merges = []
    for row in ledger:
        gained = remaining & set(row['labels']['vs_parent']['fixed'])
        patch = {key: value for key, value in row['changes'].items() if value != current[key]}
        if not gained or row['side_effect'] or not patch:
            continue
        try:
            changed_config(context['baseline_config'], current, patch, previous=context['previous_configs'])
        except ValueError:
            continue
        merges.append({'sources': [row['id']], 'questions': sorted(gained), 'changes': patch})
    return {'d_retry': retries, 'd_merge': merges}
