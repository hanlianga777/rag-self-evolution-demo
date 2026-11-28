"""Exercise 127a through an isolated SQLite store and a simulated Provider."""
import json
from collections import Counter
from types import SimpleNamespace

import pytest

from app import agent126c as policy, request_reuse, verdict
from app.agent126c_workflow import StrategyCycle
from app.evaluation import EvaluationRunner, summarize_evaluation_cases
from app.policy import GATE_DEFINITIONS
from app.providers import ProviderRequestError
from app.workflow_engine import WorkflowEngine
from test_task118a_verdict import OfflineEvaluation, scored
from test_task126c_workflow import mock_actions, run_mock_strategy


def candidate(experiment, number, label):
    return f'{experiment}-R{number:06d}-{label}'


@pytest.mark.parametrize('action,d_passes', [('d_retry', True), ('d_retry', False), ('d_merge', True), ('d_skip', False)])
def test_inherited_cycle_runs_abc_then_publishes_from_final_stage(tmp_path, monkeypatch, action, d_passes):
    env, source, cases = run_mock_strategy(tmp_path, monkeypatch, 'promoted')
    store = env.store
    old = store.experiment(source)
    seed = [c for c in old['candidates']
            if c['reasoning']['round'] <= 2 and c['reasoning']['candidate_label'] in 'ABC']
    excluded = [c for c in old['candidates'] if c not in seed]
    for record in [seed[0], *excluded]:
        run = store.evaluation_run(record['result']['evaluation_run_id'])
        with request_reuse.reuse_scope(store, run):
            request_reuse.reuse_result('generation', ['saved', record['id']], lambda: {'content': 'saved answer'})
    with pytest.raises(ValueError, match='轮'):
        store.inherit_strategy_rounds(source, 5)
    assert store.current_baseline_identity()['current_experiment_id'] == source
    inherited = store.inherit_strategy_rounds(source, 2)
    copied = store.experiment(inherited)
    old_winner = candidate(inherited, 2, 'B')
    stage = copied['result']['strategy126c']
    assert copied['result']['decision_contract_version'] == '127a'
    assert stage['winner_id'] == old_winner
    assert stage['d_attempts'] == []
    assert set(stage['rounds']) == {'1', '2'}
    assert [row['id'] for row in stage['ledger']] == [c['id'].replace(source, inherited) for c in seed]
    assert [row['prediction'] for row in stage['ledger']] == [
        row['prediction'] for row in old['result']['strategy126c']['ledger'] if row['round'] <= 2]
    assert store.experiment(source)['result_json'] == old['result_json']
    assert 'paid_run' not in copied['result'] and 'report_confirmation' not in copied['result']
    assert len(copied['candidates']) == 6
    first_run = store.evaluation_run(copied['candidates'][0]['result']['evaluation_run_id'])
    assert first_run['id'] != seed[0]['result']['evaluation_run_id']
    assert len(verdict.final_verdicts(first_run['id'], store=store)) == len(cases)
    assert stage['rounds']['1']['inherited_from']['round'] == 1
    second_run = store.evaluation_run(copied['candidates'][1]['result']['evaluation_run_id'])
    assert first_run['judge']['run_snapshot'] != second_run['judge']['run_snapshot']
    with request_reuse.reuse_scope(store, second_run):
        reused = request_reuse.reuse_result('generation', ['saved', seed[0]['id']], lambda: pytest.fail('missing cache'))
        assert reused['reused_from']['run_id'] == first_run['id']
        for row in excluded:
            assert request_reuse.reuse_result('generation', ['saved', row['id']], lambda: {'content': 'fresh'}) == {
                'content': 'fresh'}

    # Prove the new experiment reads its own rows, including its cloned verdicts and cache.
    with store.connection() as db:
        db.execute('DELETE FROM experiments WHERE id=?', (source,))
        db.execute('DELETE FROM candidate_configs WHERE experiment_id=?', (source,))
        for c in old['candidates']:
            run_id = c['result']['evaluation_run_id']
            db.execute('DELETE FROM evaluation_runs WHERE id=?', (run_id,))
            db.execute('DELETE FROM job_checkpoints WHERE run_id=?', (run_id,))
            db.execute('DELETE FROM model_request_reuse WHERE origin=?', (run_id,))

    requested, answered = Counter(), Counter()
    reviews = []

    def actions(signals, chosen=None):
        return [dict(row, action=chosen) if row['signal'] == 'FINAL_D' else row
                for row in mock_actions(signals)]

    def model(_system, user, **_):
        request = json.loads(user)
        ctx, signals = request['context'], request['signals']
        phase, number = ctx['phase'], ctx.get('round')
        assert not any(set(row['legal_actions']) & {'try_d', 'leave_for_d'} for row in signals)
        assert not any(row['id'] in user or row['result']['evaluation_run_id'] in user for row in excluded)
        requested[phase, number] += 1
        assert requested[phase, number] <= 4, request
        if phase == 'resume':
            assert ctx['candidate_id'] == candidate(inherited, 3, 'B')
            return json.dumps({'actions': actions(signals)})
        if phase == 'plan':
            assert number in {3, 4}
            if number == 3:
                assert ctx['winner_id'] == old_winner
                assert len(ctx['ledger']) == 6
                if requested[phase, number] > 1:
                    retry = next(row for row in signals if row['id'] == 'S17')
                    assert retry['evidence']['consecutive'] == requested[phase, number] - 1
                    assert 'A、B、C' in retry['evidence']['rejection']
                if requested[phase, number] <= 3:
                    return json.dumps({'actions': actions(signals), 'proposals': [{}, {}]})
                assert request['structured_fields']['rejected']
            changes = ([{'min_score': 0.1}, {'min_score': 0.2}, {'min_score': 0.3}] if number == 3 else
                       [{'min_score': 0.4}, {'candidate_k': 24, 'min_score': 0.2}, {'rerank': 'query_only'}])
            parent = ctx['winner_id']
            proposals = [dict(label=label, parent_id=parent, changes=patch, hypothesis=f'新假设{number}{label}',
                              reason='验证检索门槛和候选池', expected_fixed=['Q05'], possible_broken=[],
                              layer='retrieval', signals=[row['id'] for row in signals],
                              exploration_reason='替换检索取值测试未解决的证据问题', combination_type='dependency')
                         for label, patch in zip('ABC', changes)]
            if number == 3:
                proposals[1]['parent_id'] = ctx['baseline_id']
            response = {'actions': actions(signals)}
            response.update({'field_values': {row['label']: row for row in proposals}} if number == 3
                            else {'proposals': proposals})
            return json.dumps(response)
        if phase == 'review':
            reviews.append(number)
            for label in 'ABC':
                row = store.candidate(candidate(inherited, number, label))
                assert row['status'] == 'evaluated'
                assert set(verdict.records(store, row['result']['evaluation_run_id'])) == set(cases)
            winner = candidate(inherited, 3, 'A')
            step = 'continue' if number == 3 else 'final'
            assert ctx['choices_by_winner'][winner]['legal'] == [step]
            assert not any('d_retry' in row['legal_actions'] for row in signals)
            return json.dumps({'actions': actions(signals), 'winner_id': winner, 'branch_id': None,
                               'selection_reason': '保住主线修复并核对增量', 'next': step,
                               'next_reason': '按本轮三案结果继续或收尾'})
        assert phase == 'final'
        assert number == 4 and reviews == [3, 4]
        assert list(signals[0]['legal_actions']) == ['d_retry', 'd_merge', 'd_skip']
        reply = {'actions': actions(signals, action)}
        if action != 'd_skip':
            patch = {'candidate_k': 24, 'min_score': 0.3} if action == 'd_retry' else {'min_score': 0.2}
            option = next(row for row in ctx['options'][action] if row['changes'] == patch)
            reply['proposal'] = dict(label='D', parent_id=ctx['winner_id'], changes=option['changes'],
                                     sources=option['sources'], hypothesis='扩大池并调阈值缓解副作用',
                                     reason='账本显示扩大候选池可修 Q05', expected_fixed=['Q05'],
                                     possible_broken=['Q09'], layer='retrieval', signals=['FINAL_D'],
                                     combination_type='mitigation', mitigation='用门槛阻挡额外噪声')
        return json.dumps(reply)

    def answer(question, config):
        owner = config['candidate_id']
        assert owner.startswith(inherited)
        answered[owner, question] += 1
        if (action == 'd_skip' and owner == candidate(inherited, 3, 'B') and question == 'Q06'
                and answered[owner, question] == 1):
            raise ProviderRequestError('模拟 Sandbox 中断')
        return {'answer': owner}

    def judge(self, item, execution, **_):
        qid, owner = item['id'], execution['answer']
        fixed = {'Q01', 'Q02', 'Q04'}
        if owner == candidate(inherited, 3, 'B'):
            fixed = {'Q05'}
        if owner == candidate(inherited, 3, 'A') or '-R000004-' in owner:
            fixed.add('Q03')
        if owner.endswith('-D') and d_passes:
            fixed.add('Q05')
        return scored(cases[qid]['passed'] or qid in fixed, owner, category=cases[qid]['test_category'],
                      subtype=cases[qid].get('negative_subtype'),
                      scores=dict(correctness=95, faithfulness=95, completeness=95))

    monkeypatch.setattr(EvaluationRunner, 'score_execution', judge)
    runtime = SimpleNamespace(model='fixture', provider=SimpleNamespace(complete=model), answer=answer, force_mock=True)
    engine = WorkflowEngine(store, runtime, inherited)
    planned = engine.start('next_round', background=False)
    assert planned['status'] == 'completed' and not answered
    with pytest.raises(ValueError, match='不能跳过'):
        store.skip_candidate(candidate(inherited, 3, 'A'), 'fixture', 'simulate bypass')
    result = engine.start('release', background=False)
    assert result['status'] == 'completed', result
    after = store.experiment(inherited)
    assert len(after['candidates']) == (12 if action == 'd_skip' else 13)
    stage = after['result']['strategy126c']
    assert set(stage['rounds']) == {'1', '2', '3', '4'}
    assert requested['plan', 3] == 4 and reviews == [3, 4]
    wanted = candidate(inherited, 4, 'D') if d_passes else candidate(inherited, 3, 'A')
    assert store.active_production()['snapshot']['candidate_id'] == wanted
    assert stage['final']['d_action'] == action
    assert all(answered[candidate(inherited, n, label), 'Q09'] for n in (3, 4) for label in 'ABC')
    if action == 'd_skip':
        assert requested['resume', None] == 1
        run_id = store.candidate(candidate(inherited, 3, 'B'))['result']['evaluation_run_id']
        assert store.evaluation_run(run_id)['result']['resume_source_id']
    assert not (tmp_path / 'verdict.db.provider-ledgers').exists()


def test_127a_final_stage_requires_each_convergence_condition():
    complete = dict(qualified=True, questions=True, layers=True, plateau=True)
    for missing in complete:
        assert StrategyCycle.final_steps({**complete, missing: False}, full=False) == ['continue']
    assert StrategyCycle.final_steps({}, full=False) == ['continue']
    assert StrategyCycle.final_steps(complete, full=False) == ['final']
    assert StrategyCycle.final_steps({**complete, 'plateau': False}, full=True) == ['finish']


def test_127a_fallback_lists_and_accepts_untried_replacements_within_four_changes():
    base = policy.pipeline_config(policy.rules.BASELINE)
    parent = {**base, 'candidate_k': 24, 'multi_query': 2, 'query_rewrite': True, 'hyde': True}
    assert len(policy.config_diff(parent, base)) == 4
    context = {'round': 3, 'baseline_id': 'baseline', 'baseline_config': base, 'winner_id': 'winner',
               'decision_contract_version': '127a', 'previous_round': {'all_unqualified': True},
               'parents': {'winner': {'config': parent, 'passed': ['Q02'], 'performance': {'failed_gates': []}}},
               'hypotheses': [], 'previous_configs': [{**parent, 'multi_query': 6}], 'question_ids': ['Q01', 'Q02'],
               'targets_by_parent': {'winner': {'Q01': {'layer': 'retrieval', 'recommended': ['top_k'], 'exploratory': []}}},
               'priorities': ['retrieval'], 'preview_risks': []}
    context['remaining_configurations'] = menu = policy.remaining_configurations(context)
    assert any(row['changes'] == {'query_rewrite': False} and row['operations'] == {'query_rewrite': 'withdraw'}
               for row in menu)
    assert any(row['changes'] == {'multi_query': 4} and row['operations'] == {'multi_query': 'replace'} for row in menu)
    assert all(row['changes'] != {'multi_query': 6} and 'top_k' not in row['changes'] for row in menu)
    signals = [policy.signal('S20')]
    actions = [{'signal': 'S20', 'action': action, 'reason': '按实际参数变动选择'} for action in ['withdraw', 'replace']]
    drafts = [dict(label=label, parent_id='winner', changes=change, layer='retrieval', hypothesis=f'试验{label}',
                   reason='验证剩余错题的检索路径', expected_fixed=['Q01'], possible_broken=[],
                   exploration_reason='常用工具组合已评测，尝试调整当前配置', signals=['S20'])
              for label, change in zip('ABC', [{'query_rewrite': False}, {'multi_query': 4}, {'hyde': False}])]
    accepted = policy.validate_plan({'proposals': drafts, 'actions': actions}, context, signals)
    assert len(accepted) == 3
    assert all(len(row['reasoning']['changed_parameters_vs_baseline']) <= 4 for row in accepted)


def test_127a_retry_menu_shows_untried_mainline_changes_for_their_own_questions():
    base = policy.pipeline_config(policy.rules.BASELINE)
    winner = {**base, 'query_rewrite': True, 'multi_query': 2}
    context = {'baseline_id': 'baseline', 'baseline_config': base, 'winner_id': 'winner',
               'parents': {'winner': {'config': winner}},
               'previous_configs': [{**winner, 'top_k': 6}],
               'targets_by_parent': {'winner': {
                   'Q06': {'recommended': ['top_k'], 'exploratory': ['min_score']},
                   'Q21': {'recommended': ['query_rewrite'], 'exploratory': ['hyde']},
               }}}
    menu = policy.retry_menu(context)
    assert any(row == {'changes': {'hyde': True}, 'expected_fixed_options': ['Q21']} for row in menu)
    assert all(row['changes'] != {'top_k': 6} for row in menu)
    assert all(row['expected_fixed_options'] == ['Q06'] for row in menu if 'min_score' in row['changes'])


def make_e8_fixture(tmp_path, monkeypatch, manifest=None):
    """A 42/50 source with R1-B at 45/50, a plateau in R2 and an old D."""
    from app.agent127a_inheritance import E8_ID

    scores = dict(correctness=95, faithfulness=95, completeness=95)
    cases = {f'Q{n:02}': scored(n > 8, scores=scores) for n in range(1, 48)}
    cases.update(Q48=scored(True, category='ablation', scores=scores),
                 Q49=scored(True, category='negative', subtype='safety_critical'),
                 Q50=scored(True, category='negative', subtype='prompt_injection'))
    env = OfflineEvaluation(tmp_path, monkeypatch, cases, manifest=manifest)
    env.stable_baseline()
    store = env.store
    source = store.create_experiment(env.base, decision_contract_version='126c')
    with store.connection() as db:
        db.execute('UPDATE experiments SET id=? WHERE id=?', (E8_ID, source))
    source = E8_ID
    cycle = StrategyCycle(WorkflowEngine(store, SimpleNamespace(provider=None), source))
    state = cycle.state()
    baseline_run = store.evaluation_run(env.base)
    winner = candidate(source, 1, 'B')
    entries = [
        (1, 'A', env.base, {'top_k': 6}, ['Q01', 'Q02'], ['Q50']),
        (1, 'B', env.base, {'multi_query': 2, 'query_rewrite': True}, ['Q01', 'Q02', 'Q03'], []),
        (1, 'C', env.base, {'rerank': 'query_only'}, ['Q02'], ['Q49']),
        (2, 'A', winner, {'top_k': 6}, ['Q04'], ['Q50']),
        (2, 'B', winner, {'min_score': 0.2}, ['Q04'], ['Q49']),
        (2, 'C', winner, {'generation_thinking': 'low'}, [], []),
    ]
    for number in (1, 2):
        outcomes = []
        for _, label, parent, changes, fixed, broken in (row for row in entries if row[0] == number):
            cid = candidate(source, number, label)
            parent_config = cycle.parent(parent)['config']
            config = policy.changed_config(cycle.base_config, parent_config, changes)
            run_id = store.create_evaluation_run(env.snapshot, {**config, 'candidate_id': cid, 'run_target': 'sandbox_candidate'},
                                                baseline_run['judge'])
            saved, evaluated = {}, []
            for qid, original in cases.items():
                passed = (original['passed'] or qid in fixed or number == 2 and qid in {'Q01', 'Q02', 'Q03'}) and qid not in broken
                case = scored(passed, category=original['test_category'], subtype=original.get('negative_subtype'),
                              scores=scores)
                store.record_evaluation_case(run_id, qid, case, with_bad_case=True)
                sample = verdict.make_sample(case, env.questions[qid], 1, 'sandbox', f'{run_id}:{qid}:1')
                saved[qid] = verdict.record(run_id, qid, [sample])
                evaluated.append(case)
            verdict.save_records(store, run_id, saved)
            accounting = {'enabled': True, 'state': 'completed',
                          'ledger_identity': {'experiment_id': source}, 'ledger_path': 'old-fixture'}
            saved_result = {**summarize_evaluation_cases(evaluated), 'evaluation_complete': True,
                            'technical_failed': 0, 'auto_recovery': accounting, 'verdict_version': policy.rules.RULES_VERSION}
            store.finish_evaluation_run(run_id, 'completed', saved_result)
            reasoning = {'candidate_label': label, 'round': number, 'parent_id': parent, 'changes': changes,
                         'hypothesis': cid, 'hypothesis_key': cid, 'layer': 'retrieval',
                         'planned_tools': {'Q04': list(changes)}, 'predicted_fixed_question_ids': ['Q04'],
                         'predicted_regression_question_ids': []}
            result = {**saved_result, 'evaluation_run_id': run_id, 'baseline_run_id': env.base,
                      'evaluation_identity': baseline_run['judge']['evaluation_identity']}
            with store.connection() as db:
                db.execute('INSERT INTO candidate_configs VALUES (?,?,?,?,?,?,?)',
                           (cid, source, 'evaluated', json.dumps(config), json.dumps(reasoning),
                            json.dumps(result), '2026-11-27'))
            outcomes.append(cycle.outcome(store.candidate(cid), state))
        state.update(winner_id=winner, streak=number - 1)
        state['ledger'].extend(outcomes)
        state['rounds'][str(number)] = {
            'plan': {'signals': [policy.signal('S10', inactive=['safety', 'generation', 'performance'])], 'actions': []},
            'review': {'outcomes': outcomes, 'winner_id': winner, 'branch_id': None, 'plateau': number == 2,
                       'next': 'd' if number == 2 else 'continue',
                       'signals': [policy.signal('S4')] if number == 2 else [],
                       'actions': [{'signal': 'S4', 'action': 'try_d', 'reason': '旧版在本轮后尝试综合'}] if number == 2 else []}}
    d_id = candidate(source, 2, 'D')
    state['rounds']['2'].update(d={'proposal': 'EXCLUDED D PROPOSAL'}, d_review={'winner_id': d_id})
    state['d_attempts'] = [{'candidate_id': d_id, 'outcome': 'promoted'}]
    state['final'] = {'winner_id': d_id}
    with store.connection() as db:
        db.execute("UPDATE experiments SET status='generated',result_json=json_set(result_json,'$.strategy126c',json(?)) WHERE id=?",
                   (json.dumps(state), source))
    return store, source


def test_127a_inherit_api_restores_45_of_50_winner_and_strips_old_d(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from api_fixture import main

    store, source = make_e8_fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(main, 'store', store)
    client = TestClient(main.app)
    route = f'/api/experiments/{source}/inherit'
    assert client.post(route, json={'rounds': '2'}).status_code == 422
    response = client.post(route, json={'rounds': 2})
    assert response.status_code == 201, response.text
    new = response.json()
    stage = new['result']['strategy126c']
    assert stage['winner_id'] == candidate(new['id'], 1, 'B') and stage['streak'] == 1
    assert stage['rounds']['2']['review']['next'] == 'continue'
    assert stage['rounds']['2']['inherited_from']['label'] == 'E8'
    assert 'EXCLUDED D PROPOSAL' not in response.text and 'try_d' not in response.text
    assert not stage['d_attempts'] and 'final' not in stage
    winner = store.candidate(stage['winner_id'])
    run_id = winner['result']['evaluation_run_id']
    passed = verdict.final_verdicts(run_id, store=store)
    assert len(passed) == 50 and sum(passed.values()) == 45
    assert store.evaluation_run(run_id)['result']['auto_recovery'] == {'enabled': False, 'state': 'completed'}


def test_127a_inherited_perfect_winner_goes_directly_to_release():
    state = {'winner_id': 'winner', 'rounds': {'2': {'inherited_from': {'round': 2}, 'review': {'next': 'continue'}}}}
    cycle = StrategyCycle.__new__(StrategyCycle)
    cycle.final_only = True
    cycle.question_ids = ['Q01']
    cycle.state = lambda: state
    cycle.engine = SimpleNamespace(check_stop=lambda: None, state=lambda: {'status': 'completed'})
    cycle.parent = lambda _: {'passed': ['Q01'], 'gates': {'passed': True, 'gates': [
        {**gate, 'passed': True} for gate in GATE_DEFINITIONS]}}
    cycle.persist = lambda saved: None
    cycle.generate = lambda *_: pytest.fail('Perfect inherited Winner must not start another round')

    def finish(saved, target):
        assert target == 'release'
        assert saved['final']['full']
        assert saved['final']['winner_id'] == 'winner'
        assert saved['final']['d_outcome'] == 'not_generated'

    cycle.finish = finish
    assert cycle.run('release') == {'status': 'completed'}
