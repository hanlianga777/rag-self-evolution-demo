"""Offline workflow regressions using disposable SQLite stores and fake providers."""
import json
from types import SimpleNamespace

import pytest

from app import rules
from test_task118a_verdict import mark_legacy_planning
from test_task120a2_layered import saved_runs


def test_next_round_runs_required_diagnosis_before_requesting_proposals(saved_runs, tmp_path, monkeypatch):
    from app import main

    env, _ = saved_runs
    experiment_id = env.store.create_experiment(env.base, decision_contract_v2=True)
    mark_legacy_planning(env.store, experiment_id)
    directory = tmp_path / 'retrieval_preview'
    directory.mkdir()
    (directory / f'{env.base}.json').write_text(json.dumps({
        'baseline_run_id': env.base, 'rules_version': rules.RULES_VERSION,
        'knowledge_identity': env.snapshot['corpus_fingerprint'], 'configs': [],
    }))
    monkeypatch.setattr('app.agent_mechanism.fault_stage', lambda row: {
        'code': 'generation', 'subtype': None, 'reason': '已进入 Final'})
    from app.paid_schedule import set_settings
    set_settings(env.store, False)

    def complete(*args, **kwargs):
        pytest.fail('No proposal is justified when all diagnosis samples leave the verdict unchanged')

    def answer(question, config, *, saved_trace):
        assert saved_trace['final']
        return {'answer': question}

    def score(self, item, execution):
        return env.raw_cases(env.base)[item['id']]

    from app.evaluation import EvaluationRunner
    from fastapi.testclient import TestClient

    monkeypatch.setattr(main, 'store', env.store)
    monkeypatch.setattr(main, 'ai_service', SimpleNamespace(
        model='fixture', answer=answer, provider=SimpleNamespace(complete=complete)))
    monkeypatch.setattr(EvaluationRunner, 'score_execution', score)
    response = TestClient(main.app).post(f'/api/experiments/{experiment_id}/continue')
    assert response.status_code == 200, response.json()
    experiment = env.store.experiment(experiment_id)
    entries = experiment['result']['parameter_effect_ledger']['current']
    assert entries and all(row['source'] == '生成诊断' for row in entries)
    assert {row['base_id'] for row in entries} == {'Baseline'}
    assert experiment['evaluation_budget']['used'] == 0
    assert not experiment['candidates']


# Copy the first 25 rows and the remaining target and safety rows from the real
# export. Keep the requested fault position while bounding the offline test.
def _seed_matrix(directory, monkeypatch):
    import csv
    from pathlib import Path
    from app import corpus
    from app.paid_policy import EXPERIMENT_ACCOUNTING, bind_experiment
    from app.paid_run import PaidRun
    from app.paid_schedule import set_settings, set_unattended_authorization
    from app.policy import DEFAULT_PIPELINE_CONFIG
    from test_task118a_verdict import OfflineEvaluation, scored

    export = Path(__file__).resolve().parents[2] / '指挥/报告/122a-E5第1轮逐题.csv'
    with export.open(encoding='utf-8-sig') as stream:
        rows = [row for row in csv.DictReader(stream) if int(row['题号'][1:]) <= 25
                or row['题号'] in {'Q27', 'Q43', 'Q47'}]
    categories = {'正向': 'positive', '消融': 'ablation', '负向': 'negative'}
    first = {}
    for row in rows:
        question = row['题号']
        category = categories[row['题型']]
        subtype = ('safety_critical' if int(question[1:]) < 47 else 'prompt_injection') if category == 'negative' else None
        first[question] = scored(row['Baseline最终判定'] == '对', 'fixture evidence', category=category, subtype=subtype)
    manifest = {'sources': [{'id': 'fixture-doc', 'sha256': 'a' * 64}]}
    env = OfflineEvaluation(directory, monkeypatch, first, manifest=manifest, evidence=[
        {'source_chunk_ids': ['fixture evidence'], 'quote': 'fixture evidence'}])
    env.stable_baseline()
    store = env.store
    set_settings(store, False)
    set_unattended_authorization(store, True, '用户')
    experiment = store.create_experiment(env.base, decision_contract_v2=True)
    mark_legacy_planning(store, experiment)
    store.save_candidate(experiment, 'R1-A', {**DEFAULT_PIPELINE_CONFIG, 'top_k': 6},
                         {'candidate_label': 'A', 'round': 1, 'changed_parameters': {'top_k': 6},
                          'observed_evidence': ['Q17']})
    identity = {'experiment_id': experiment, 'baseline': env.base,
                'evaluation_identity': env.baseline['judge']['evaluation_identity']}
    ledger = PaidRun(directory / 'fixture.ledger.json', identity=identity,
                     prices={'fixture': {'provider': 'DeepSeek', 'currency': 'CNY',
                                         'input': 1, 'output': 1, 'max_output': 65536}},
                     request_policy={'kind': EXPERIMENT_ACCOUNTING, 'database_path': str(store.database_path),
                                     'budget_usd': None})
    bind_experiment(store, experiment, {'ledger_path': str(ledger.path), 'ledger_identity': identity})
    index = directory / 'index'
    index.mkdir()
    (index / 'manifest.json').write_text(json.dumps(manifest))
    (index / 'faiss.index').touch()
    monkeypatch.setattr(corpus, 'INDEX_DIR', index)
    with store.connection() as db:
        active = store.active_production()
        db.execute('UPDATE production_versions SET snapshot_json=? WHERE id=?',
                   (json.dumps({'generation_model': 'fixture', 'embedding_model': corpus.EMBEDDING_MODEL}),
                    active['id']))
    (directory / 'matrix.json').write_text(json.dumps({
        'experiment': experiment, 'questions': env.items,
        'failures': [question for question, case in first.items() if not case['passed']],
        'copied_baseline_verdicts': {row['题号']: row['Baseline最终判定'] for row in rows},
    }))
    return store, experiment


def _install_matrix(directory, monkeypatch, *, inject=True, kill=False, authorized=True, retest_gain=True):
    import io
    import ssl
    import time
    import urllib.request
    from collections import Counter
    from pathlib import Path
    from urllib.error import HTTPError, URLError

    from app import corpus, governance, main, providers, release_view, verdict
    from app.agent_round_contract import GenerationDiagnosisRequired
    from app.config import Settings
    from app.evaluation import EvaluationRunner
    from app.policy import DEFAULT_PIPELINE_CONFIG
    from app.workflow_engine import WorkflowEngine
    from test_task118a_verdict import scored

    directory = Path(directory)
    fixture = json.loads((directory / 'matrix.json').read_text())
    experiment = fixture['experiment']
    questions = {q['id']: q for q in fixture['questions']}
    failures = set(fixture['failures'])
    store = governance.GovernanceStore(directory / 'verdict.db', migrate=False)
    input_manifest = json.loads((directory / 'index' / 'manifest.json').read_text())
    monkeypatch.setattr(governance, 'current_manifest', lambda: input_manifest)
    monkeypatch.setattr(corpus, 'current_manifest', lambda: input_manifest)
    monkeypatch.setattr(release_view, 'current_manifest', lambda: input_manifest)
    monkeypatch.setattr(corpus, 'INDEX_DIR', directory / 'index')
    monkeypatch.setattr(main, 'store', store)
    monkeypatch.setattr(main, 'safe_start', True)
    monkeypatch.setattr(providers, '_retry_sleep', lambda delay, stop: providers.check_provider_stop(stop))
    if authorized:
        # This supplies a fake, explicit Gate 3 authorization. The real publish
        # transaction still validates the recommendation, identity, gates and prior version.
        monkeypatch.setattr(WorkflowEngine, 'release_authorization', lambda self: {
            'enabled': True, 'actor': '用户', 'authorized_at': '2026-11-25T09:09:00-05:00',
        })
    attempts = Counter()
    request_trace = directory / 'requests.jsonl'
    original_http = urllib.request.urlopen

    def send(request, *args, **kwargs):
        if request.full_url.startswith('http://127.0.0.1:'):
            return original_http(request, *args, **kwargs)
        assert request.full_url == 'https://fixture.invalid/chat/completions'
        kind, label, question = json.loads(json.loads(request.data)['messages'][1]['content'])
        attempt = (kind, label, question)
        attempts[attempt] += 1
        injected = None
        if inject and attempt in FAULT_POINTS and attempts[attempt] <= 4:
            injected = ('ssl', 429, 503, 503)[attempts[attempt] - 1]
        with request_trace.open('a') as stream:
            stream.write(json.dumps([*attempt, injected]) + '\n')
        if injected == 'ssl':
            raise URLError(ssl.SSLEOFError('fixture EOF'))
        if injected:
            raise HTTPError(request.full_url, injected, 'fixture failure',
                            {'Retry-After': '0'}, io.BytesIO(b'{}'))
        response = {'choices': [{'message': {'content': 'fixture result'}}],
                    'usage': {'prompt_tokens': 24, 'completion_tokens': 8}}
        return io.BytesIO(json.dumps(response).encode())

    monkeypatch.setattr(urllib.request, 'urlopen', send)
    adapter = providers.DeepSeekProvider(Settings('fixture-only', 'https://fixture.invalid', 'fixture'))

    def stage():
        return store.optimization_cycle_state(experiment)['phase']

    fixed = {'Baseline': set(), 'R1-A': {'Q17'}, 'R2-A': {'Q17', 'Q21'}, 'D': {'Q17', 'Q21', 'Q27'}}

    def answer(question, config, *, saved_trace=None):
        label = config.get('candidate_id', 'Baseline').removeprefix(experiment + '-')
        kind = 'probe' if saved_trace else 'retest' if stage() == 'final_retest' else 'answer'
        if kill and (kind, label, question) == ('answer', 'R1-A', 'Q25'):
            (directory / 'ready-to-kill').touch()
            while True:
                time.sleep(1)
        adapter.complete('fixture answer', json.dumps([kind, label, question]))
        trace = {step: [{'chunk_id': 'fixture evidence'}] for step in ('candidates', 'reranked', 'final')}
        return {'answer': label, 'retrieval_trace': trace, 'kind': kind}

    def score(self, item, execution, **_):
        question = item['id']
        kind, label = execution['kind'], execution['answer']
        adapter.complete('fixture Judge', json.dumps([kind + '_judge', label, question]))
        fixes = fixed[label] if kind != 'retest' or retest_gain else set()
        passed = question not in failures or question in fixes
        metadata = questions[question]
        return scored(passed, 'fixture evidence', category=metadata['test_category'],
                      subtype=metadata.get('negative_subtype'))

    def preview(question):
        active = store.active_production()
        adapter.complete('fixture production', json.dumps(['smoke', 'D', question]))
        return {'version': active['id'], 'mode': 'live', 'answer': 'fixture result',
                'evidence': ['fixture evidence']}

    runtime = SimpleNamespace(model='fixture', provider=adapter, answer=answer, baseline_preview=preview, force_mock=True)
    monkeypatch.setattr(main, 'ai_service', runtime)
    monkeypatch.setattr(EvaluationRunner, 'score_execution', score)

    def draft(self, baseline_id, *, experiment_id):
        current = store.experiment(experiment_id, light=True)
        base = store.candidate(experiment + '-R1-A')
        run = base['result']['evaluation_run_id']
        ledger = current['result']['parameter_effect_ledger']['current']
        if not any(row['source'] == '生成诊断' for row in ledger):
            remaining = [q for q, passed in verdict.final_verdicts(run, store=store).items() if not passed]
            raise GenerationDiagnosisRequired(base['id'], run, remaining)
        adapter.complete('fixture plan', json.dumps(['plan', 'R2', 'Q21']))
        changes = {'prompt_strategy': 'Looser'}
        store.save_candidate(experiment, 'R2-A', {**base['config'], **changes},
                             {'candidate_label': 'A', 'round': 2, 'inherited_from': base['id'],
                              'changed_parameters': changes, 'observed_evidence': ['Q21']})
        return store.experiment(experiment)

    def d_plan(self, experiment_id, provider):
        current = store.experiment(experiment_id)
        if current['result'].get('composite'):
            return current['result']['composite']
        assert current['result']['report_confirmation']['winner_id'] == experiment + '-R2-A'
        winner = store.candidate(experiment + '-R2-A')
        adapter.complete('fixture D plan', json.dumps(['plan', 'D', 'Q27']))
        config = {**winner['config'], 'generation_thinking': 'high'}
        decision = {'status': 'generated', 'candidate_id': experiment + '-D'}
        reasoning = {'candidate_label': 'D', 'winner_id': winner['id'], 'observed_evidence': ['Q27'],
                     'changed_parameters': {'generation_thinking': 'high'}}
        with store.connection() as db:
            db.execute("INSERT INTO candidate_configs VALUES (?,?,'generated',?,?,'{}','2026-11-26')",
                       (decision['candidate_id'], experiment, json.dumps(config), json.dumps(reasoning)))
            db.execute("UPDATE experiments SET result_json=json_set(result_json,'$.composite',json(?)) WHERE id=?",
                       (json.dumps(decision), experiment))
        return decision

    def review(store, runtime, experiment_id, *, final_d=False):
        current = store.experiment(experiment_id, light=True)
        number = 'D' if final_d else str(max(c['reasoning'].get('round', 1) for c in current['candidates']))
        if current['result'].get('round_conclusions', {}).get(number, {}).get('status') == 'saved':
            return
        adapter.complete('fixture review', json.dumps(['review', number, 'Q25']))
        from app.agent_strategy import _save
        _save(store, experiment_id, number, {'status': 'saved'})

    def staged_facts(store, current, baseline, winner, number):
        assert winner is not None
        passed = verdict.final_verdicts(winner['result']['evaluation_run_id'], store=store)
        return {'remaining_count': sum(not passed[q] for q in passed),
                'untried_layers': ['generation'] if number == 1 else [], 'has_combination': number == 2}

    monkeypatch.setattr('app.optimization.OptimizationAgent.generate', draft)
    monkeypatch.setattr(governance.GovernanceStore, 'create_composite', d_plan)
    monkeypatch.setattr('app.agent_strategy.conclude_round', review)
    monkeypatch.setattr('app.optimization_cycle.layered_stage_facts', staged_facts)
    return main, store, experiment


def _workflow_result(store, experiment):
    import time

    deadline = time.monotonic() + 140
    while time.monotonic() < deadline:
        state = store.optimization_cycle_state(experiment)
        if state['status'] not in {'queued', 'running', 'recovering'}:
            return state
        time.sleep(.05)
    pytest.fail(state)


def _matrix_summary(store, experiment, state, directory):
    current = store.experiment(experiment, light=True)
    recommendation = store.recommendation(experiment)['result']
    release = store.job_checkpoint(experiment, 'workflow:release') or {}
    def label(candidate_id):
        return candidate_id.removeprefix(experiment + '-') if candidate_id else None

    phases = []
    for event in state['workflow_audit']:
        marker = (event['phase'], label(event.get('active_candidate')))
        if event['status'] != 'recovering' and (not phases or phases[-1] != marker):
            phases.append(marker)
    paid = json.loads((directory / 'fixture.ledger.json').read_text())
    return {
        'phases': phases,
        'decisions': (state['staged_decision']['decision'], label(state['staged_decision']['winner_id'])),
        'qualifications': sorted((label(c['id']), c['result']['qualification']['qualified'])
                                 for c in current['candidates']),
        'recommendation': (recommendation['status'], label(recommendation['recommended_candidate'])),
        'retest': store.job_checkpoint(experiment, 'workflow:final-retest')['summary'],
        'release': (state['status'], state['phase'], release.get('result'), label(release.get('candidate'))),
        'fee_records': [(c.get('e5_phase'), c['status'], c.get('upper_estimate_yuan')) for c in paid['calls']],
    }


FAULT_POINTS = {
    ('answer', 'R1-A', 'Q25'), ('probe', 'R1-A', 'Q15'),
    ('answer', 'D', 'Q25'), ('retest', 'D', 'Q15'),
}


def _assert_matrix(store, experiment, state, directory):
    assert (state['status'], state['phase']) == ('completed', 'published'), state
    summary = _matrix_summary(store, experiment, state, directory)
    assert summary['decisions'] == ('composite', 'R2-A')
    assert summary['qualifications'] == [('D', True), ('R1-A', True), ('R2-A', True)]
    assert summary['recommendation'] == ('Recommended', 'D')
    assert summary['release'] == ('completed', 'published', 'published', 'D')
    assert store.active_production()['snapshot']['human_release']['executed_by'] == 'Codex'
    phases = [item['phase'] for item in state['workflow_audit']]
    assert phases.index('generation_probe') < phases.index('composite_review') < phases.index('final_retest')
    assert phases.index('final_retest') < phases.index('release') < phases.index('production_smoke')
    trace = [json.loads(line) for line in (directory / 'requests.jsonl').read_text().splitlines()]
    for point in FAULT_POINTS:
        replies = [row[3] for row in trace if tuple(row[:3]) == point]
        assert replies[:5] == ['ssl', 429, 503, 503, None], point
    return summary


@pytest.fixture(scope='module')
def button_summary(tmp_path_factory):
    from fastapi.testclient import TestClient

    directory = tmp_path_factory.mktemp('workflow-button')
    with pytest.MonkeyPatch.context() as patch:
        store, experiment = _seed_matrix(directory, patch)
        from app.optimization_cycle import _save_state
        _save_state(store, experiment, status='stopped', phase='analysis',
                    workflow_scope={'target': 'release', 'entry': 'api'})
        main, store, experiment = _install_matrix(directory, patch)
        response = TestClient(main.app).post(f'/api/experiments/{experiment}/run-cycle?target=release')
        assert response.status_code == 201, response.json()
        return _assert_matrix(store, experiment, _workflow_result(store, experiment), directory)


def test_button_workflow_recovers_transport_and_publishes(button_summary):
    assert button_summary['release'] == ('completed', 'published', 'published', 'D')


@pytest.mark.parametrize('mode', ['script', 'restart'])
def test_workflow_entry_agrees_with_button(tmp_path, monkeypatch, button_summary, mode):
    import os
    import socket
    import subprocess
    import sys
    import time
    import urllib.request
    from contextlib import contextmanager
    from pathlib import Path

    backend = Path(__file__).resolve().parents[1]
    script = backend / 'scripts/run_e5_unattended.py'
    store, experiment = _seed_matrix(tmp_path, monkeypatch)

    @contextmanager
    def serve(*, kill=False):
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            port = listener.getsockname()[1]
        url = f'http://127.0.0.1:{port}'
        env = dict(os.environ, RAG_DEMO_DB_PATH=str(store.database_path),
                   RAG_DEMO_INDEX_DIR=str(tmp_path / 'index'), RAG_SAFE_START='1', RAG_FORCE_MOCK='1',
                   PYTHONPATH=str(backend))
        log_path = tmp_path / 'server.log'
        with log_path.open('a') as log, subprocess.Popen(
                [sys.executable, str(Path(__file__).resolve()), str(tmp_path), str(port), str(int(kill))],
                env=env, stdout=log, stderr=log) as worker:
            try:
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline and worker.poll() is None:
                    try:
                        with urllib.request.urlopen(url + '/openapi.json', timeout=1):
                            break
                    except OSError:
                        time.sleep(.05)
                else:
                    pytest.fail(log_path.read_text())
                yield url, worker
            finally:
                if worker.poll() is None:
                    worker.terminate()
                    try:
                        worker.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        worker.kill()

    if mode == 'script':
        with serve() as (url, _):
            args = [sys.executable, str(script), experiment, '--api', url]
            start = subprocess.run(args, timeout=15, capture_output=True, text=True, check=True)
            assert json.loads(start.stdout)['workflow_scope']['target'] == 'release'
            state = _workflow_result(store, experiment)
            status = subprocess.run([*args, '--status'], timeout=15, capture_output=True, text=True, check=True)
            assert json.loads(status.stdout)['phase'] == 'published'
    else:
        with serve(kill=True) as (url, worker):
            request = urllib.request.Request(f'{url}/api/experiments/{experiment}/run-cycle?target=release', method='POST')
            with urllib.request.urlopen(request, timeout=10) as response:
                assert response.status == 201
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline and not (tmp_path / 'ready-to-kill').exists():
                assert worker.poll() is None, (tmp_path / 'server.log').read_text()
                time.sleep(.05)
            assert (tmp_path / 'ready-to-kill').exists()
            original_run = store.candidate(experiment + '-R1-A')['result']['evaluation_run_id']
            assert len(store.evaluation_case_results(original_run)) == 24
            worker.kill()
            worker.wait(timeout=5)
        with store.connection() as db:
            db.execute('UPDATE task_leases SET lease_expires_at=0')
        with serve():
            state = _workflow_result(store, experiment)
        assert store.candidate(experiment + '-R1-A')['result']['evaluation_run_id'] == original_run
        assert any(event['status'] == 'recovering' for event in state['workflow_audit'])
        trace = [json.loads(row) for row in (tmp_path / 'requests.jsonl').read_text().splitlines()]
        for position in range(1, 25):
            question = f'Q{position:02d}'
            assert trace.count(['answer', 'R1-A', question, None]) == (3 if question == 'Q17' else 1)

    assert _assert_matrix(store, experiment, state, tmp_path) == button_summary


@pytest.mark.parametrize('target', ['cycle', 'release'])
def test_d_review_rejection_stops_both_workflow_scopes(saved_runs, monkeypatch, target):
    from app.workflow_engine import WorkflowEngine

    env, save = saved_runs
    experiment = env.store.create_experiment(env.base, decision_contract_v2=True)
    winner, _ = save(experiment, 'A', 1, {'Q01'}, top_k=6)
    save(experiment, 'D', 2, {'Q01', 'Q02'}, top_k=6, prompt_strategy='Looser')
    env.store.confirm_experiment_report(experiment, winner, '用户')

    def reject(*args, final_d=False, **kwargs):
        assert final_d
        raise ValueError('本轮结论连续校验拒绝：缺少原证据')

    monkeypatch.setattr('app.agent_strategy.conclude_round', reject)
    state = WorkflowEngine(env.store, SimpleNamespace(provider=None), experiment).start(target, background=False)
    assert (state['status'], state['phase']) == ('blocked', 'composite_review')
    assert state['last_error'] == '本轮结论连续校验拒绝：缺少原证据'
    assert not env.store.job_checkpoint(experiment, 'workflow:final-retest')


def test_single_candidate_scope_does_not_advance_the_round(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    _seed_matrix(tmp_path, monkeypatch)
    main, store, experiment = _install_matrix(tmp_path, monkeypatch, inject=False, authorized=False)
    client = TestClient(main.app)
    path = f'/api/experiments/{experiment}/run-cycle'
    assert client.post(path, params={'candidate_id': 'another-experiment-A'}).status_code == 409
    candidate_id = experiment + '-R1-A'
    from app.optimization_cycle import _save_state

    _save_state(store, experiment, status='stopped', phase='sandbox', workflow_scope={
        'target': 'candidate', 'entry': 'api', 'candidate_id': candidate_id,
    })
    response = client.post(path)
    assert response.status_code == 201, response.json()
    assert response.json()['workflow_scope']['target'] == 'candidate'
    assert _workflow_result(store, experiment)['status'] == 'completed'
    [candidate] = store.candidates(experiment)
    assert candidate['id'] == candidate_id and candidate['status'] == 'evaluated'
    assert not store.job_checkpoint(experiment, 'workflow:probe-plan')
    assert all(v['provenance'] != 'published' for v in store.production_versions())


@pytest.mark.parametrize(('authorized', 'retest_gain', 'status', 'phase'), [
    (False, True, 'awaiting_release_approval', 'before_release'),
    (True, False, 'completed', 'unchanged'),
])
def test_publish_requires_both_verified_gain_and_gate3(tmp_path, monkeypatch, authorized, retest_gain, status, phase):
    from app.workflow_engine import WorkflowEngine

    _seed_matrix(tmp_path, monkeypatch)
    main, store, experiment = _install_matrix(tmp_path, monkeypatch, inject=False,
        authorized=authorized, retest_gain=retest_gain)
    prior = store.active_production()['id']
    state = WorkflowEngine(store, main.ai_service, experiment).start('release', background=False)
    assert (state['status'], state['phase']) == (status, phase), state
    assert store.job_checkpoint(experiment, 'workflow:final-retest')['candidate'] == experiment + '-D'
    assert store.active_production()['id'] == prior
    assert store.latest_approval('human_release', experiment + '-D') is None


def test_e5_release_grant_is_bound_to_original_experiment_and_budget(tmp_path):
    from app.governance import GovernanceStore
    from app.paid_policy import E5_POLICY
    from app.paid_run import PaidRun, controlled_run
    from app.workflow_engine import E5_BASELINE, E5_SEED, WorkflowEngine

    store = GovernanceStore(tmp_path / 'authorization.db')
    with store.connection() as db:
        for experiment in ('original', 'other'):
            db.execute("INSERT INTO experiments VALUES (?,?,'completed',?,'2026-11-26')",
                       (experiment, E5_BASELINE, json.dumps({'mode': 'initial'})))
            db.execute("INSERT INTO candidate_configs VALUES (?,?,'evaluated','{}',?,'{}','2026-11-26')",
                       (experiment + '-R1-A', experiment, json.dumps({'source_candidate_id': E5_SEED})))
    ledger = PaidRun(tmp_path / 'fixture.ledger.json',
                    identity={'task': '120b', 'experiment_id': 'original', 'baseline': E5_BASELINE},
                    request_policy={'kind': E5_POLICY, 'budget_usd': 3.0})
    with controlled_run(ledger):
        assert WorkflowEngine(store, None, 'original').release_authorization()['actor'] == '用户'
        assert WorkflowEngine(store, None, 'other').release_authorization() is None
        ledger.request_policy['budget_usd'] = 4.0
        assert WorkflowEngine(store, None, 'original').release_authorization() is None


if __name__ == '__main__':
    import sys
    import uvicorn

    folder, port, kill = sys.argv[1:]
    with pytest.MonkeyPatch.context() as patch:
        main, _, _ = _install_matrix(folder, patch, kill=bool(int(kill)))
        uvicorn.run(main.app, host='127.0.0.1', port=int(port), log_level='warning')
