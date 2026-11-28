"""Run 128a from planning through publication with a simulated Provider."""
import json
from collections import Counter
from types import SimpleNamespace

import pytest

from app import agent126c_workflow as workflow, verdict
from app.evaluation import EvaluationRunner
from app.paid_schedule import set_settings
from app.workflow_engine import WorkflowEngine
from test_task118a_verdict import OfflineEvaluation, scored
from test_task126c_workflow import mock_actions


@pytest.mark.parametrize(
    ('scenario', 'last_round', 'trigger', 'd_result', 'target'),
    [
        ('two_in_round_one', 1, 'two_qualified', 'promoted', 'cycle'),
        ('one_per_round', 2, 'two_qualified', 'not_promoted', 'release'),
        ('converged_with_one', 2, 'converged', 'not_promoted', 'current_round'),
        ('reject_invalid_d', 1, 'two_qualified', 'promoted', 'release'),
        ('full_winner', 1, 'two_qualified', 'not_promoted', 'release'),
        ('no_round_cap', 5, 'two_qualified', 'promoted', 'release'),
    ],
)
def test_128a_runs_all_abc_then_one_terminal_d(tmp_path, monkeypatch, scenario, last_round, trigger, d_result, target):
    scores = dict(correctness=95, faithfulness=95, completeness=95)
    cases = {f'Q{i:02}': scored(i > 5, scores=scores) for i in range(1, 10)}
    cases.update(Q06=scored(True, category='ablation'),
                 Q07=scored(True, category='negative', subtype='safety_critical'),
                 Q08=scored(True, category='negative', subtype='prompt_injection'))
    manifest = {'sources': [{'id': 'test-doc', 'sha256': 'a' * 64}]}
    env = OfflineEvaluation(tmp_path, monkeypatch, cases, manifest=manifest)
    env.stable_baseline()
    store = env.store
    set_settings(store, False)
    experiment = store.create_experiment(env.base, decision_contract_version='128a')

    def cid(number, label):
        return f'{experiment}-R{number:06d}-{label}'

    def diagnosis(_baseline, _cases, failed):
        return {q: {'subtype': '找到但没交给模型', 'layer': 'retrieval', 'severity': '严重',
                    'reason': '证据未进入 Final'} for q in failed}

    monkeypatch.setattr(workflow.evidence_roles, 'faults', diagnosis)
    monkeypatch.setattr('app.release_view.current_manifest', lambda: manifest)
    plans, reviews, d_requests = [], [], []
    answered = Counter()
    initial_a = cid(1, 'A')
    invalid_d = scenario == 'reject_invalid_d'
    want_winner = cid(last_round, 'A') if scenario in {'one_per_round', 'no_round_cap'} else initial_a
    qualified = [initial_a]
    if trigger == 'two_qualified':
        qualified.append(cid(2, 'A') if scenario == 'one_per_round' else cid(1, 'B'))
    if scenario == 'no_round_cap':
        qualified = [cid(5, label) for label in 'AB']

    def model(system, user, **_):
        request = json.loads(user)
        context, signals = request['context'], request['signals']
        phase, number = context['phase'], context['round']
        assert number <= last_round, request
        actions = mock_actions(signals)

        def draft(label, parent, changes):
            return dict(label=label, parent_id=parent, changes=changes,
                        hypothesis=f'{number}{label} 的检索组合', reason='验证送入 Final 的证据',
                        expected_fixed=sorted(set(context['question_ids']) - set(context['parents'][parent]['passed'])),
                        possible_broken=[], layer='retrieval', signals=[row['id'] for row in signals],
                        exploration_reason='检验排序、阈值与候选池的协同', combination_type='dependency')

        if phase == 'plan':
            plans.append(number)
            assert len(plans) <= last_round, request
            first_a = {'top_k': 6, 'min_score': 0.1} if invalid_d else {'top_k': 6}
            patches = [first_a, {'candidate_k': 24}, {'rerank': False}] if number == 1 else [
                {'min_score': 0.1}, {'min_score': 0.2}, {'min_score': 0.3}]
            extra = {3: {'top_k': 6}, 4: {'rerank': False}, 5: {'candidate_k': 24}}
            if scenario == 'no_round_cap' and number in extra:
                patches = [{**patch, **extra[number]} for patch in patches]
            parent = context['winner_id'] or context['baseline_id']
            return json.dumps({'actions': actions,
                               'proposals': [draft(label, parent, patch) for label, patch in zip('ABC', patches)]})
        if phase == 'review':
            reviews.append(number)
            assert len(reviews) <= last_round, request
            for label in 'ABC':
                row = store.candidate(cid(number, label))
                assert row['status'] == 'evaluated'
                assert set(verdict.records(store, row['result']['evaluation_run_id'])) == set(cases)
            winner = initial_a if number == 1 else want_winner
            if scenario == 'no_round_cap' and number < last_round:
                winner = None
            legal = context['choices_by_winner'][winner or env.base]['legal']
            assert legal == (['final'] if number == last_round else ['continue'])
            return json.dumps({'actions': actions, 'winner_id': winner, 'branch_id': None,
                               'selection_reason': '保留已修好的题'})

        assert phase == 'terminal_d'
        assert reviews == list(range(1, last_round + 1))
        assert context['winner_id'] == want_winner
        assert context['trigger'] == {'reason': trigger, 'qualified_ids': qualified}
        assert set(signals[0]['legal_actions']) == {'compose_d'}
        assert 'd_skip' not in system
        d_requests.append(request)
        assert len(d_requests) <= (4 if invalid_d else 1), request
        prior = len(d_requests) - 1
        if prior:
            assert signals[-1]['id'] == 'S17' and signals[-1]['evidence']['consecutive'] == prior

        source = cid(1, 'C')
        changes, sources, mitigations = {}, {}, {}
        if scenario in {'two_in_round_one', 'reject_invalid_d', 'full_winner'}:
            changes['candidate_k'] = 24
            sources['candidate_k'] = cid(1, 'B')
        if scenario == 'two_in_round_one' or invalid_d and prior in {1, 2}:
            changes['rerank'] = False
            sources['rerank'] = source
            if not (invalid_d and prior == 2):
                mitigations[source] = '用阈值和证据范围控制排序回退'
        changes['generation_thinking'] = 'low'
        if invalid_d and prior == 0:
            changes['hyde'] = True
        if invalid_d and prior == 2:
            changes.pop('generation_thinking')
        proposal = draft('D', want_winner, changes)
        proposal.update(signals=['FINAL_D'], expected_fixed=[] if scenario == 'full_winner' else ['Q03'],
                        sources=sources, source_mitigations=mitigations,
                        qualified_ideas={key: '保留候选的已验证检索机制' for key in qualified},
                        tuning={'parameter': 'generation_thinking', 'purpose': '调节证据消化'} if
                        'generation_thinking' in changes else None)
        if 'structured_fields' in request:
            return json.dumps({'actions': actions, 'field_values': {'D': proposal}})
        return json.dumps({'actions': actions, 'proposal': proposal})

    def answer(question, config):
        owner = config['candidate_id']
        answered[owner, question] += 1
        return {'answer': owner}

    def judge(_self, item, execution, **_):
        owner, question = execution['answer'], item['id']
        fixed = {
            initial_a: set(cases) if scenario == 'full_winner' else {'Q01'},
            cid(1, 'B'): {'Q02'}, cid(1, 'C'): {'Q03'},
            cid(2, 'A'): {'Q01', 'Q02'} if scenario == 'one_per_round' else {'Q02'},
            cid(last_round, 'D'): {'Q01', 'Q02', 'Q03'} if d_result == 'promoted' else {'Q01'},
        }.get(owner, set())
        if scenario == 'no_round_cap' and not owner.endswith('-D'):
            fixed = {cid(5, 'A'): {'Q01'}, cid(5, 'B'): {'Q02'}}.get(owner, set())
        passed = cases[question]['passed'] or question in fixed
        if question == 'Q09' and (owner == cid(1, 'C')
                                 or owner == cid(1, 'B') and scenario in {'one_per_round', 'converged_with_one'}
                                 or owner == cid(2, 'A') and scenario == 'converged_with_one'
                                 or owner.endswith('-D') and scenario == 'full_winner'):
            passed = False
        case = cases[question]
        return scored(passed, owner, category=case['test_category'], subtype=case['negative_subtype'], scores=scores)

    monkeypatch.setattr(EvaluationRunner, 'score_execution', judge)
    runtime = SimpleNamespace(model='fixture', provider=SimpleNamespace(complete=model), answer=answer, force_mock=True)
    engine = WorkflowEngine(store, runtime, experiment)
    if scenario == 'two_in_round_one':
        from fastapi.testclient import TestClient
        from api_fixture import main

        monkeypatch.setattr(main, 'store', store)
        monkeypatch.setattr(main, 'ai_service', runtime)
        response = TestClient(main.app).post('/api/experiments/run', json={'decision_contract_version': '128a'})
        assert response.status_code == 201, response.text
        assert response.json()['id'] == experiment and len(response.json()['candidates']) == 3
    else:
        assert engine.start('next_round', background=False)['status'] == 'completed'
    with pytest.raises(ValueError, match='不能跳过'):
        store.skip_candidate(initial_a, 'fixture', 'simulate bypass')
    if target == 'current_round':
        stopped = engine.start(target, background=False)
        assert stopped['status'] == 'round_completed' and not d_requests
        assert engine.start('next_round', background=False)['status'] == 'completed'
        with monkeypatch.context() as failure:
            failure.setattr('app.release_view.release_review_view',
                            lambda *_: {'checks': [{'ok': False, 'label': '模拟发布检查中断'}]})
            stopped = engine.start(target, background=False)
        assert stopped['status'] == 'blocked' and '模拟发布检查中断' in stopped['last_error']
        assert not store.active_production()['snapshot'].get('candidate_id')
        saved = answered.copy()
        response = engine.start(None, background=False)
        assert answered == saved and len(d_requests) == 1
    else:
        response = engine.start(target, background=False)
    assert response['status'] == 'completed', response
    after = store.experiment(experiment)
    state = after['result']['strategy126c']
    d = store.candidate(cid(last_round, 'D'))
    wanted = d['id'] if d_result == 'promoted' else want_winner
    assert plans == reviews == list(range(1, last_round + 1))
    assert set(state['rounds']) == {str(n) for n in plans}
    assert len(after['candidates']) == last_round * 3 + 1
    assert all(row['total'] == row['evaluated'] == 3 and row['complete'] for row in after['rounds'])
    assert after['evaluation_budget'] == {'used': last_round * 3 + 1, 'max': None, 'reserved_for_d': 0}
    assert len(state['d_attempts']) == 1
    assert state['final']['d_outcome'] == d_result
    assert d['reasoning']['parent_id'] == want_winner
    assert d['reasoning']['d_trigger']['qualified_ids'] == qualified
    assert d['reasoning']['tuning']['parameter'] == 'generation_thinking'
    assert {qid for owner, qid in answered if owner == d['id']} == set(cases)
    assert store.recommendation(experiment)['result']['recommended_candidate'] == wanted
    assert store.active_production()['snapshot']['candidate_id'] == wanted
    if invalid_d:
        assert '最多 1 项' in d_requests[1]['signals'][-1]['evidence']['rejection']
        assert '累计最多 4 项' in d_requests[2]['signals'][-1]['evidence']['rejection']
        assert '缓解' in d_requests[3]['signals'][-1]['evidence']['rejection']
        assert set(d_requests[3]['structured_fields']['field_values']) == {'D'}
    request_count = len(d_requests)
    calls = answered.copy()
    assert engine.start('release', background=False)['status'] == 'completed'
    assert len(d_requests) == request_count and answered == calls
    assert not (tmp_path / 'verdict.db.provider-ledgers').exists()
