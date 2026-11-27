import pytest

from app import agent126c as strategy, rules
from app.policy import GATE_DEFINITIONS, evaluate_gates


GATES = evaluate_gates({row['metric']: row['threshold'] for row in GATE_DEFINITIONS})


def facts(*passed, gates=GATES, safety=()):
    return {'passed': list(passed), 'gates': gates, 'safety': list(safety)}


def test_three_independent_labels():
    base, winner = facts('Q01'), facts('Q01', 'Q02')
    result = strategy.qualifications(facts('Q01', 'Q03'), base, base, winner)
    assert [result[k] for k in ('qualified', 'effective', 'promoted')] == [True, True, False]
    result = strategy.qualifications(winner, base, winner, winner)
    assert [result[k] for k in ('qualified', 'effective', 'promoted')] == [True, False, False]
    assert not strategy.qualifications(facts('Q02'), base, base, base)['qualified']
    assert not strategy.qualifications(facts('Q01', 'Q02', safety=['Q02']), base, base, base)['qualified']


@pytest.mark.parametrize('missing', ['qualified', 'questions', 'layers', 'd', 'plateau', None])
def test_convergence_requires_every_condition(missing):
    conditions = dict.fromkeys(['qualified', 'questions', 'layers', 'd', 'plateau'], True)
    if missing:
        conditions[missing] = False
    assert strategy.may_finish(conditions, full=False) is (missing is None)
    assert strategy.may_finish(conditions, full=True) is (missing != 'qualified')


def test_126b_menus():
    assert strategy.menu({'subtype': '没检索到', 'question_type': '口语与弱关键词'})[0] == ('query_rewrite', 'multi_query')
    assert strategy.menu({'subtype': '没检索到', 'question_type': '复杂子问'})[0] == ('query_decompose', 'multi_query')
    assert strategy.menu({'subtype': '安全越界'}) == (('prompt_strategy',), ())
    assert strategy.menu({'subtype': '待确认'}) == ((), ())


def test_allow_replacing_and_reverting_at_four():
    base = rules.BASELINE
    parent = {**base, 'candidate_k': 24, 'top_k': 6, 'hyde': True, 'generation_thinking': 'low'}
    assert strategy.changed_config(base, parent, {'hyde': False, 'top_k': 4})['top_k'] == 4
    with pytest.raises(ValueError, match='4 项'):
        strategy.changed_config(base, parent, {'multi_query': 2})
    with pytest.raises(ValueError, match='白名单'):
        strategy.changed_config(base, parent, {'chunk_size': 5})
    with pytest.raises(ValueError, match='2 项'):
        strategy.changed_config(base, parent, {'hyde': False, 'top_k': 4, 'candidate_k': 12})


def observed(**updates):
    return {
        'id': 'R1-A', 'from_branch': False, 'higher_score': False, 'changes': {'top_k': 6},
        'labels': {'qualified': True, 'promoted': False, 'vs_parent': {'fixed': ['Q02']},
                   'vs_winner': {'broken': []}, 'safety_regression': False},
        'side_effect': False, 'slower_and_better': False, 'judge_disagreements': {},
        'performance': {'failed_gates': []}, **updates,
    }


def planning(**facts):
    return strategy.planning_signals({
        'round': 2, 'targets': {}, 'priorities': ['retrieval'], 'parents': {},
        'baseline_config': rules.BASELINE, 'performance': {'failed_gates': []}, **facts,
    })


def review(*outcomes, winner='old', streak=0, full=False, plateau=False, d=True):
    return strategy.review_signals(outcomes, winner, 'branch', streak, {
        'qualified': bool(winner), 'questions': False, 'layers': True, 'd': False, 'plateau': plateau,
    }, full=full, d_available=d)


@pytest.mark.parametrize(('code', 'case', 'action'), [
    ('S1', lambda: planning(round=1), 'different_hypotheses'),
    ('S2', lambda: review(observed(), observed(id='R1-B', labels={**observed()['labels'], 'promoted': True})), 'select_winner'),
    ('S3', lambda: review(observed(labels={**observed()['labels'], 'qualified': False}), winner=None), 'switch_layer'),
    ('S4', lambda: review(observed(), plateau=True), 'branch_base'),
    ('S5', lambda: review(observed(), plateau=True, streak=2), 'continue'),
    ('S6', lambda: review(observed(from_branch=True, labels={**observed()['labels'], 'promoted': True})), 'promote_branch'),
    ('S7', lambda: review(observed(from_branch=True, higher_score=True,
                                  labels={**observed()['labels'], 'vs_winner': {'broken': ['Q01']}})), 'keep_branch'),
    ('S8', lambda: review(observed(side_effect=True)), 'mitigate'),
    ('S9', lambda: planning(priorities=['safety', 'retrieval'], default_slots=['safety', 'safety', 'retrieval']), 'default_slots'),
    ('S10', lambda: planning(), 'leave_layer'),
    ('S11', lambda: review(observed(slower_and_better=True)), 'tradeoff'),
    ('S12', lambda: planning(performance={'failed_gates': ['latency_p99_seconds'], 'stage_shares': [{'stage': 'answer'}]}), 'optimize_stage'),
    ('S13', lambda: review(observed(labels={**observed()['labels'], 'safety_regression': True})), 'avoid'),
    ('S14', lambda: planning(boundaries={'Q04': {'capability_boundary': True, 'reason': '冻结证据不足'}}), 'engineering'),
    ('S15', lambda: review(observed(judge_disagreements={'Q02': {'votes': [True, False, False], 'final_passed': False}})), 'use_recheck'),
    ('S16', lambda: review(observed(), full=True), 'publish'),
    ('S17', lambda: [strategy.signal('S17', rejection='proposals.A 参数超出白名单', consecutive=3)], 'revise'),
    ('S18', lambda: [strategy.signal('S18', source_run_id='EVAL-fixture', reason='network timeout')], 'resume'),
    ('S19', lambda: planning(previous_round={'outcomes': [{'id': 'A', 'hypothesis': '预期修复 Q02', 'labels': {'safety_regression': False},
                                                         'prediction': {'large_deviation': True}}]}), 'retrospect'),
    ('S20', lambda: planning(parents={'P': {'config': {**rules.BASELINE, 'candidate_k': 24, 'top_k': 6,
                                                       'hyde': True, 'generation_thinking': 'low'}}}), 'replace'),
    ('S21', lambda: planning(preview_risks=[{'config': {'top_k': 6}, 'questions': ['Q01']}]), 'deprioritize'),
], ids=[f'S{i}' for i in range(1, 22)])
def test_signal_input_and_action_contract(code, case, action):
    signals = case()
    detected = next(row for row in signals if row['id'] == code)
    assert action in detected['legal_actions']
    reply = {'actions': [{'signal': row['id'], 'action': action if row['id'] == code else next(iter(row['legal_actions'])),
                          'reason': '根据冻结题的记录判断'} for row in signals]}
    if code == 'S19':
        next(row for row in reply['actions'] if row['signal'] == code)['revisions'] = {'A': '原假设缺少排序位置证据'}
    assert strategy.validate_actions(reply, signals)[code] == {action}
    draft = next(row for row in reply['actions'] if row['signal'] == code)
    draft['action'] = 'ignore_hard_constraint'
    with pytest.raises(ValueError, match='不允许'):
        strategy.validate_actions(reply, signals)
    draft.update(action=action, reason='')
    with pytest.raises(ValueError, match='reason'):
        strategy.validate_actions(reply, signals)


def test_coverage_reads_completed_per_question_tools_and_capability_evidence():
    targets = {'Q02': {'recommended': ['top_k', 'rerank'], 'reason': '依据未进 Final'},
               'Q03': {'recommended': [], 'reason': '缺少证据标注'}}
    pending, closed = strategy.coverage(targets, [{'planned_tools': {'Q02': ['top_k'], 'Q01': ['rerank']}}])
    assert pending == {'Q02': ['rerank']}
    assert closed == {'Q03': {'reason': '缺少证据标注', 'tested': [], 'capability_boundary': True}}
    pending, closed = strategy.coverage(targets, [{'planned_tools': {'Q02': ['top_k', 'rerank']}}])
    assert not pending and closed['Q02']['tested'] == ['rerank', 'top_k']


def review_context():
    return {'baseline_id': 'BASE', 'winner_id': 'MAIN', 'promotions': ['BRANCH'],
            'branches_by_winner': {'BRANCH': []}, 'branch_promotions': ['BRANCH'],
            'sidelined': ['BRANCH'], 'same_quality_faster': [], 'legal_next': ['continue']}


def test_branch_switch_keeps_former_main_and_rejects_early_finish():
    signals = [strategy.signal('S6')]
    reply = {'actions': [{'signal': 'S6', 'action': 'promote_branch', 'reason': '保留主线的题并多修一道'}],
             'winner_id': 'BRANCH', 'branch_id': 'MAIN', 'selection_reason': '多修一道',
             'next': 'continue', 'next_reason': '下一轮继续验证'}
    assert strategy.select_review(reply, review_context(), signals) == ('BRANCH', 'MAIN', 'continue')
    with pytest.raises(ValueError, match='原主线'):
        strategy.select_review({**reply, 'branch_id': None}, review_context(), signals)
    with pytest.raises(ValueError, match='严格增量'):
        strategy.select_review({**reply, 'winner_id': 'MAIN'}, review_context(), signals)
    with pytest.raises(ValueError, match='结束条件'):
        strategy.select_review({**reply, 'next': 'finish'}, review_context(), signals)


def test_performance_gate_repair_can_be_effective_without_release_qualification():
    before = facts('Q01', gates=evaluate_gates({row['metric']: row['threshold'] + (
        1 if row['metric'] == 'latency_p99_seconds' else 0) for row in GATE_DEFINITIONS}))
    result = strategy.qualifications(facts('Q01'), before, before, before)
    assert result['effective'] and not result['qualified'] and not result['promoted']
    assert result['performance_repaired'] == ['latency_p99_seconds']


def test_safety_label_is_independent_of_parent_and_winner():
    baseline = facts('Q01')
    parent = {**facts('Q01', 'Q02', 'Q03'), 'safety_failed': []}
    next_run = {**facts('Q01', 'Q03'), 'safety_failed': ['Q02']}
    result = strategy.qualifications(next_run, {**baseline, 'safety_failed': ['Q02']}, parent, parent)
    assert result['qualified'] and not result['effective'] and not result['promoted']


def test_126c_plan_rejects_duplicate_hypotheses_configs_and_unsafe_preview():
    base = strategy.pipeline_config(rules.BASELINE)
    fault = {'layer': 'retrieval', 'recommended': ['top_k', 'rerank'], 'exploratory': ['candidate_k']}
    targets = {'Q02': fault}
    parent = {**facts('Q01'), 'config': base, 'performance': {'failed_gates': []}}
    context = {'round': 1, 'baseline_id': 'BASE', 'baseline_config': base, 'parents': {'BASE': parent},
               'targets_by_parent': {'BASE': targets}, 'priorities': ['retrieval'], 'hypotheses': [],
               'previous_configs': [], 'question_ids': ['Q01', 'Q02'],
               'preview_risks': [{'config': {k: 6 if k == 'top_k' else base[k] for k in strategy.RETRIEVAL},
                                  'questions': ['Q01']}]}
    signals = [strategy.signal('S1'), strategy.signal('S21')]
    draft = {'parent_id': 'BASE', 'reason': '测试排序机制', 'expected_fixed': ['Q02'],
             'possible_broken': ['Q01'], 'layer': 'retrieval', 'signals': ['S1'],
             'exploration_reason': '池扩张让长尾切块进入重排'}
    rows = [{**draft, 'label': label, 'changes': changes, 'hypothesis': label + '排序机制'}
            for label, changes in zip(strategy.LABELS, [{'top_k': 6}, {'rerank': False}, {'candidate_k': 24}])]
    actions = [{'signal': 'S1', 'action': 'different_hypotheses', 'reason': '检验三个不同的干预机制'},
               {'signal': 'S21', 'action': 'deprioritize', 'reason': 'Final 可能丢掉证据'}]
    reply = {'actions': actions, 'proposals': rows}
    with pytest.raises(ValueError, match='S21'):
        strategy.validate_plan(reply, context, signals)
    actions[-1]['action'] = 'mitigate'
    rows[0]['mitigation'] = '检查完整上下文并在 Sandbox 核对 Q01'
    assert len(strategy.validate_plan(reply, context, signals)) == 3
    rows[1]['hypothesis'] = rows[0]['hypothesis'] + '。'
    with pytest.raises(ValueError, match='机制假设重复'):
        strategy.validate_plan(reply, context, signals)
    rows[1]['hypothesis'] = '调整不同的参数'
    rows[1]['changes'] = rows[2]['changes']
    with pytest.raises(ValueError, match='配置重复'):
        strategy.validate_plan(reply, context, signals)


def test_43_of_50_with_untested_recommended_tool_cannot_finish():
    questions = {f'Q{i:02}' for i in range(1, 51)}
    winner = facts(*sorted(questions)[:43])
    remaining = {q: {'recommended': ['top_k', 'rerank'], 'reason': '证据未进入 Final'}
                 for q in questions - set(winner['passed'])}
    pending, _ = strategy.coverage(remaining, [{'planned_tools': {q: ['top_k'] for q in remaining}}])
    assert len(pending) == 7
    assert not strategy.may_finish({'qualified': True, 'questions': not pending, 'layers': True, 'd': True,
                                    'plateau': True}, full=False)


def test_hybrid_disable_handles_implicit_alpha_and_keeps_whitelist():
    base = {**rules.BASELINE, 'hybrid_alpha': 0.7}
    config = strategy.changed_config(base, base, {'hybrid_search': False})
    assert 'hybrid_alpha' not in config
    assert strategy.config_diff(config, base) == {'hybrid_search': False}
    with pytest.raises(ValueError, match='白名单'):
        strategy.changed_config(base, base, {'hybrid_search': False, 'hybrid_alpha': 0.3})
