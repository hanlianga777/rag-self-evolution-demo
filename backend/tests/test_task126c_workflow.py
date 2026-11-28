"""Use the actual cycle lease, SQLite attempts, Sandbox verdicts and publication."""
import json
from collections import Counter
from types import SimpleNamespace

import pytest

from app import agent126c as policy, verdict
from app import agent126c_workflow as workflow
from app.ai_service import AiService
from app.evaluation import EvaluationRunner
from app.paid_schedule import set_settings
from app.providers import ProviderInvalidResponse, ProviderRequestError
from app.workflow_engine import WorkflowEngine
from test_task118a_verdict import OfflineEvaluation, scored


def test_d_proposal_can_respond_to_saved_tradeoff_and_safety_signals():
    base = policy.pipeline_config(workflow.rules.BASELINE)
    source = {'id': 'branch', 'changes': {'top_k': 6}, 'passed': ['Q01', 'Q02'],
              'labels': {'qualified': False}, 'side_effect': True}
    saved_signals = [policy.signal('S4'), policy.signal('S8', candidates=['branch']),
                     policy.signal('S13', candidates={'branch': source})]
    state = {'rounds': {'2': {'review': {'signals': saved_signals}}},
             'ledger': [source], 'd_attempts': []}
    context = {'round': 2, 'baseline_id': 'baseline', 'winner_id': 'winner', 'baseline_config': base,
               'question_ids': ['Q01', 'Q02'], 'priorities': ['retrieval'],
               'performance': {'failed_gates': []}, 'previous_configs': [],
               'parents': {'winner': {'config': {**base, 'multi_query': 2}, 'passed': ['Q01'],
                                     'performance': {'failed_gates': []}}},
               'targets_by_parent': {'winner': {}}, 'preview_risks': []}
    cycle = workflow.StrategyCycle.__new__(workflow.StrategyCycle)
    cycle.id = 'experiment'
    cycle.engine = SimpleNamespace(save=lambda **_: None)
    cycle.context = lambda *_: context
    persisted = []
    cycle.persist = lambda _, drafts: persisted.extend(drafts)

    def model(_key, _, signals, validate):
        proposal = {'label': 'D', 'parent_id': 'winner', 'changes': {'top_k': 6, 'prompt_strategy': 'Safe'},
                    'hypothesis': '增加证据段数并用安全提示缓解回退', 'reason': '支线改善了 Q02',
                    'expected_fixed': ['Q02'], 'possible_broken': ['Q01'], 'layer': 'retrieval',
                    'signals': ['S8', 'S13'], 'sources': ['branch'],
                    'combination_type': 'mitigation', 'mitigation': '安全提示避免扩大上下文后跟随注入'}
        actions = [{'signal': code, 'action': 'mitigate', 'reason': '保留收益并缓解安全回退'}
                   for code in ('S8', 'S13')]
        return {'data': validate({'proposal': proposal, 'actions': actions}, signals),
                'signals': signals, 'actions': actions}

    cycle.ask = model
    cycle.generate_d(state, 2)
    assert persisted[0]['reasoning']['sources'] == ['branch']
    assert state['d_attempts'][0]['candidate_id'] == 'experiment-R000002-D'


def test_structured_retry_lists_saved_candidates_for_prediction_revisions():
    signals = [policy.signal('S19', candidates=[{'id': 'earlier-B'}, {'id': 'earlier-C'}])]
    form = workflow.StrategyCycle.field_form('plan', signals, '复盘缺少方案')
    assert set(form['actions'][0]['revisions']) == {'earlier-B', 'earlier-C'}


def test_structured_retry_expands_actions_without_bypassing_action_validation():
    signal = policy.signal('S20')
    action = {'signal': 'S20', 'action': ['replace', 'withdraw'], 'reason': '各方案改动不同'}
    reply = {'actions': [action], 'field_values': {label: {} for label in ('A', 'B', 'C')}}

    response = workflow.StrategyCycle.field_response(reply, 'plan')
    assert policy.validate_actions(response, [signal])['S20'] == {'replace', 'withdraw'}

    action['action'] = ['replace', 'unknown']
    response = workflow.StrategyCycle.field_response(reply, 'plan')
    with pytest.raises(ValueError, match='不允许的动作'):
        policy.validate_actions(response, [signal])


@pytest.mark.parametrize('complete_lines', [5, 6])
def test_multi_query_uses_only_complete_requested_lines_after_truncation(complete_lines):
    def truncated(*_):
        raw = ''.join(f'检索问法 {index}\n' for index in range(complete_lines)) + '未写完'
        raise ProviderInvalidResponse('DeepSeek output truncated', raw_provider_response=raw,
                                      metadata={'finish_reason': 'length'})

    runtime = AiService(None, None, SimpleNamespace(complete=truncated), True)
    config = {**workflow.rules.BASELINE, 'multi_query': 6}
    if complete_lines < config['multi_query']:
        with pytest.raises(ProviderInvalidResponse):
            runtime._retrieval_queries('测试问题', config)
    else:
        trace = {}
        assert runtime._retrieval_queries('测试问题', config, trace) == [f'检索问法 {i}' for i in range(6)]
        assert trace['query_labels'] == ['multi_query'] * 6


def mock_actions(signals, *, step=None, branch=False):
    result = []
    for signal in signals:
        legal = signal['legal_actions']
        preferred = {'S2': 'select_winner', 'S4': 'try_d' if step == 'd' else 'switch_mechanism',
                     'S5': {'d': 'try_d', 'finish': 'finish'}.get(step, 'continue'),
                     'S7': 'combine_later', 'S10': 'cross_layer', 'S9': 'default_slots', 'S20': 'replace',
                     'S21': 'deprioritize'}.get(signal['id'])
        if signal['id'] == 'S2' and preferred not in legal:
            preferred = 'select_branch' if branch else 'record_lessons'
        action = preferred if preferred in legal else next(iter(legal))
        row = {'signal': signal['id'], 'action': action, 'reason': '依据本次输入中的冻结观察记录'}
        if signal['id'] == 'S19':
            row['revisions'] = {item['id']: '预期受益范围过宽，收缩到有 Final 证据的题'
                                for item in signal['evidence']['candidates']}
        result.append(row)
    return result


@pytest.mark.parametrize('d_result', ['promoted', 'not_promoted', 'not_generated'])
def test_mock_provider_runs_strategy_through_release(tmp_path, monkeypatch, d_result):
    run_mock_strategy(tmp_path, monkeypatch, d_result)


def run_mock_strategy(tmp_path, monkeypatch, d_result):
    base_cases = {f'Q{i:02}': scored(False, scores=dict(correctness=90, faithfulness=90, completeness=90))
                  for i in range(1, 6)}
    base_cases.update(Q06=scored(True, category='ablation'),
                      Q07=scored(True, category='negative', subtype='safety_critical'),
                      Q08=scored(True, category='negative', subtype='prompt_injection'), Q09=scored(True))
    manifest = {'sources': [{'id': 'test-doc', 'sha256': 'a' * 64}]}
    env = OfflineEvaluation(tmp_path, monkeypatch, base_cases, manifest=manifest)
    env.stable_baseline()
    store = env.store
    set_settings(store, False)
    experiment_id = store.create_experiment(env.base, decision_contract_version='126c')
    base = env.base
    winner = lambda n, label: f'{experiment_id}-R{n:06d}-{label}'
    used = Counter()
    requests = []
    no_d = d_result == 'not_generated'
    r1_target = {'Q01', 'Q02', 'Q03', 'Q04'} if no_d else {'Q01', 'Q02'}
    r2_target = r1_target if no_d else {'Q01', 'Q02', 'Q04'}
    all_fixed = {'Q01', 'Q02', 'Q03', 'Q04', 'Q05'}

    def diagnosis(baseline, cases, failed):
        return {qid: {'subtype': '找到但没交给模型', 'question_type': '跨段综合', 'layer': 'retrieval',
                      'severity': '严重', 'reason': '保存证据没有进入 Final'} for qid in failed}

    monkeypatch.setattr(workflow.evidence_roles, 'faults', diagnosis)
    monkeypatch.setattr(workflow, '_retry_sleep', lambda _, check: check())
    monkeypatch.setattr('app.release_view.current_manifest', lambda: manifest)
    monkeypatch.setattr('app.providers._retry_sleep', lambda *_: None)

    def draft(context, signals, label, parent, changes):
        return {'label': label, 'parent_id': parent, 'changes': changes,
                'hypothesis': f'第{context["round"]}轮的{label}机制{changes}', 'reason': '用保存的排序证据验证',
                'expected_fixed': sorted(set(context['question_ids']) - set(context['parents'][parent]['passed'])),
                'possible_broken': [], 'layer': 'retrieval', 'signals': [row['id'] for row in signals],
                'cross_layer_reason': '让生成模型检查来自检索的多段证据',
                'exploration_reason': '用扩大候选池或降低筛除阈值验证竞争条目机制',
                'combination_type': 'mitigation' if len(changes) == 2 else None}

    def model(_system, user, **kwargs):
        request = json.loads(user)
        ctx, signals = request['context'], request['signals']
        requests.append(request)
        phase = ctx['phase']
        round_id = ctx.get('round')
        used[(phase, round_id)] += 1
        assert used[(phase, round_id)] < 12, request.get('structured_fields', request)
        if phase == 'resume':
            return json.dumps({'actions': mock_actions(signals)})
        if phase == 'plan':
            if round_id == 1 and used[(phase, round_id)] <= 4:
                return '{"proposals":"not a list"}'
            if round_id == 1:
                assert request['structured_fields']['rejected']
                entries = [(base, {'top_k': 6}), (base, {'candidate_k': 24}), (base, {'rerank': False})]
            elif round_id == 2:
                entries = [(winner(1, 'A'), {'rerank': 'query_only'}),
                           (winner(1, 'A') if no_d else winner(1, 'C'), {'min_score': 0.1} if no_d else {'top_k': 6}),
                           (base if no_d else winner(1, 'C'), {'min_score': 0.2})]
            elif round_id == 3:
                entries = [(winner(2, 'B'), {'min_score': 0.1}), (winner(2, 'B'), {'min_score': 0.2}),
                           (winner(2, 'B'), {'min_score': 0.3})]
            elif round_id == 4:
                entries = [(winner(2, 'B'), {'min_score': 0.4}), (winner(2, 'B'), {'candidate_k': 24}),
                           (winner(2, 'B'), {'generation_thinking': 'low'})]
            else:
                pytest.fail(f'unexpected round {round_id}')
            proposals = [draft(ctx, signals, label, parent, changes)
                         for label, (parent, changes) in zip(policy.LABELS, entries)]
            values = {'field_values': {row['label']: row for row in proposals}} if 'structured_fields' in request else {'proposals': proposals}
            return json.dumps({'actions': mock_actions(signals), **values})
        if phase == 'd':
            source = next(row for row in ctx['combinations']
                          if row['source'] == winner(1, 'B') and row['changes'] == {
                              'candidate_k': 24, 'min_score': 0.3})
            proposal = {**draft(ctx, signals, 'D', winner(2, 'B'), source['changes']),
                        'sources': [source['source']], 'mitigation': '分数线降低扩大候选池带来的噪声'}
            return json.dumps({'actions': mock_actions(signals), 'proposal': proposal})
        assert phase == 'review'
        selected, branch = (winner(1, 'A'), None if no_d else winner(1, 'C')) if round_id == 1 else (
            (winner(1, 'A'), None) if no_d else (winner(2, 'B'), winner(1, 'A')))
        if round_id == 3:
            branch = winner(1, 'B')
        if round_id == 4:
            branch = ctx['previous_branch']
        step = 'continue'
        if no_d and round_id == 2:
            step = 'finish'
        if round_id == 4:
            if any('-D' == row['id'][-2:] for row in ctx['outcomes']):
                selected = winner(4, 'D') if d_result == 'promoted' else winner(2, 'B')
                branch = None if d_result == 'promoted' else branch
                step = 'finish'
            else:
                step = 'd'
        selected_facts = ctx['choices_by_winner'][selected]
        assert step in selected_facts['legal'], (round_id, selected, step, selected_facts)
        if branch and 'S6' not in {row['id'] for row in signals}:
            branch = next((row['id'] for row in selected_facts['branches'] if row['id'] == branch), None)
        return json.dumps({'actions': mock_actions(signals, step=step, branch=bool(branch)),
                           'winner_id': selected, 'branch_id': branch, 'selection_reason': '保留已有成果和互补机制',
                           'next': step, 'next_reason': '核对逐题工具、跨层、D 和平台期',
                           'no_d_reason': '无试验方案修好主线剩余的 Q05'})

    def answer(question, config):
        cid = config['candidate_id']
        used[('answer', cid, question)] += 1
        if cid == winner(1, 'A') and question == 'Q06' and used[('answer', cid, question)] == 1:
            raise ProviderRequestError('模拟 Sandbox 技术中断')
        return {'answer': cid}

    def judge(self, item, execution, **kwargs):
        cid, qid = execution['answer'], item['id']
        used[('judge', cid, qid)] += 1
        repaired = {winner(1, 'A'): r1_target, winner(1, 'B'): {'Q05'} if not no_d else {'Q01'},
                    winner(1, 'C'): {'Q04'}, winner(2, 'A'): r1_target, winner(2, 'B'): r2_target,
                    winner(2, 'C'): {'Q03', 'Q04', 'Q05'} if not no_d else {'Q02'},
                    winner(4, 'D'): all_fixed if d_result == 'promoted' else r2_target}.get(cid, r2_target)
        passed = base_cases[qid]['passed'] or qid in repaired
        if cid == winner(1, 'B') and qid == 'Q09' and not no_d:
            passed = False
        if cid == winner(1, 'A') and qid == 'Q02' and used[('judge', cid, qid)] == 3:
            passed = False  # S15 uses the two concordant votes.
        semantics = base_cases[qid]
        return scored(passed, cid, category=semantics['test_category'], subtype=semantics.get('negative_subtype'),
                      scores=dict(correctness=95, faithfulness=95, completeness=95))

    monkeypatch.setattr(EvaluationRunner, 'score_execution', judge)
    runtime = SimpleNamespace(model='fixture', provider=SimpleNamespace(complete=model),
                              answer=answer, force_mock=True)
    engine = WorkflowEngine(store, runtime, experiment_id)
    first = engine.start('next_round', background=False)
    assert first['status'] == 'completed', first
    assert store.active_production()['snapshot'].get('candidate_id') is None
    response = engine.start('release', background=False)
    assert response['status'] == 'completed', response.get('last_error')
    state = store.experiment(experiment_id)['result']['strategy126c']
    assert state['final']['d_outcome'] == d_result
    want = winner(1, 'A') if no_d else winner(4, 'D') if d_result == 'promoted' else winner(2, 'B')
    assert store.active_production()['snapshot']['candidate_id'] == want
    assert store.recommendation(experiment_id)['result']['recommended_candidate'] == want
    assert store.candidate(want)['result']['strategy126c_labels']['promoted']
    with store.connection() as db:
        trace = db.execute("SELECT result_json FROM agent_traces WHERE experiment_id=? ORDER BY id DESC LIMIT 1",
                           (experiment_id,)).fetchone()
    assert json.loads(trace['result_json'])['decision_contract_version'] == '126c'
    detected = {s['id'] for request in requests for s in request['signals']}
    assert {'S1', 'S2', 'S15', 'S17', 'S18'} <= detected
    if not no_d:
        assert {'S5', 'S6', 'S7', 'S8'} <= detected
        assert len(state['ledger']) == 13
    check = store.candidate(winner(1, 'A'))
    run_id = check['result']['evaluation_run_id']
    assert store.evaluation_run(run_id)['result']['resume_source_id']
    assert verdict.final_verdicts(run_id, store=store)['Q02']
    assert used[('answer', winner(1, 'A'), 'Q01')] == 3
    assert used[('answer', winner(1, 'A'), 'Q06')] == 2
    assert not (tmp_path / 'verdict.db.provider-ledgers').exists()
    return env, experiment_id, base_cases
