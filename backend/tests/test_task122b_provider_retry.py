"""Exercise the real retry and ledger paths with a disposable store and fake HTTP."""
import io
import json
import ssl
from pathlib import Path
from urllib.error import HTTPError, URLError

import pytest

from app.config import Settings
from app.evaluation_stage import perform_stage
from app.governance import GovernanceStore
from app.knowledge_pipeline import AlibabaProvider
from app.paid_run import PaidRun, accounting_only, controlled_run
from app.providers import DeepSeekProvider, ProviderUnavailable


MODEL = 'deepseek-flash'
PRICES = {MODEL: {'provider': 'DeepSeek', 'input': 0.3, 'output': 1.2, 'max_output': 65536}}


@pytest.fixture
def work(tmp_path, monkeypatch):
    store = GovernanceStore(tmp_path / 'retry.db')
    states, sleeps = [], []
    monkeypatch.setattr('app.providers.time.sleep', sleeps.append)
    return store, states, sleeps


def provider():
    return DeepSeekProvider(Settings('offline', 'https://fixture.invalid', MODEL))


def reply():
    return io.BytesIO(b'{"choices":[{"message":{"content":"saved result"}}],"usage":{"prompt_tokens":20,"completion_tokens":10}}')


def stage(work, action, *, stop=lambda: None, run_id='run'):
    store, states, _ = work
    checkpoint = store.job_checkpoint('test122b', 'Q01') or {'attempts': []}

    def persist(state, **details):
        states.append((state, details))
        store.save_job_checkpoint('test122b', 'Q01', checkpoint)

    return perform_stage(checkpoint, 'generation', action, run_id,
                         automatic=True, check_stop=stop, on_state=persist)


def test_two_ssl_eofs_retry_same_request_then_succeed(work, monkeypatch):
    sent = []

    def http(request, **_kwargs):
        sent.append(request.data)
        if len(sent) < 3:
            raise URLError(ssl.SSLEOFError('fixture EOF'))
        return reply()

    monkeypatch.setattr('urllib.request.urlopen', http)
    assert provider().complete('system', 'question') == 'saved result'
    assert len(sent) == 3 and len(set(sent)) == 1
    assert work[2] == [5, 15]


def test_429_retry_after_overrides_default_and_is_capped(work, monkeypatch):
    calls = 0

    def http(request, **_kwargs):
        nonlocal calls
        calls += 1
        if calls <= 2:
            raise HTTPError(request.full_url, 429, 'limited',
                            {'Retry-After': ['2', '300'][calls - 1]}, io.BytesIO(b'{}'))
        return io.BytesIO(b'{"usage":{"total_tokens":2}}')

    monkeypatch.setattr('urllib.request.urlopen', http)
    remote = AlibabaProvider({'DASHSCOPE_API_KEY': 'offline', 'DASHSCOPE_BASE_URL': 'https://fixture.invalid'})
    assert remote._post('/embeddings', {'model': 'text-embedding-v4'})['usage']['total_tokens'] == 2
    assert work[2] == [2, 120]


def test_waiting_worker_resumes_saved_rpc_without_resending_completed_rpc(work, monkeypatch):
    sent = []
    interrupted = False

    def http(request, **_kwargs):
        question = json.loads(request.data)['messages'][1]['content']
        sent.append(question)
        if question == 'second' and sent.count('second') <= 4:
            raise TimeoutError('fixture timeout')
        return reply()

    def sleep(_seconds):
        nonlocal interrupted
        if work[1][-1][0] == 'retry_wait' and not interrupted:
            interrupted = True
            raise KeyboardInterrupt('fixture worker exit')

    monkeypatch.setattr('urllib.request.urlopen', http)
    monkeypatch.setattr('app.providers.time.sleep', sleep)

    def action():
        remote = provider()
        remote.complete('system', 'first')
        return remote.complete('system', 'second')

    with pytest.raises(KeyboardInterrupt):
        stage(work, action)
    assert sent == ['first'] + ['second'] * 4
    assert stage(work, action) == 'saved result'
    assert sent == ['first'] + ['second'] * 5
    assert [details['retry_delay_seconds'] for state, details in work[1] if state == 'retry_wait'][0] == 60


def test_401_is_blocked_before_any_wait(work, monkeypatch):
    sent = []

    def http(request, **_kwargs):
        sent.append(request.data)
        raise HTTPError(request.full_url, 401, 'unauthorized', {}, io.BytesIO(b'{}'))

    monkeypatch.setattr('urllib.request.urlopen', http)
    with pytest.raises(ProviderUnavailable):
        stage(work, lambda: provider().complete('system', 'question'))
    assert len(sent) == 1
    assert work[2] == []
    assert any(state == 'blocked' and details.get('resume_hint') for state, details in work[1])


def test_unknown_attempt_occupies_upper_budget_and_success_saves_before_settling(work, monkeypatch):
    directory = work[0].database_path.parent
    ledger = PaidRun(directory/'test.ledger.json', prices=PRICES, identity='fixture', identity_check=lambda: 'fixture')
    by_request = []

    def http(_request, **_kwargs):
        saved = json.loads(ledger.path.read_text())['calls'][-1]
        assert saved['reserved_at'] and saved['sent_at']
        assert 'settled_at' not in saved
        by_request.append(saved)
        if len(by_request) == 1:
            raise TimeoutError('reply lost')
        return reply()

    monkeypatch.setattr('urllib.request.urlopen', http)
    with controlled_run(ledger), accounting_only():
        assert provider().complete('system', 'question') == 'saved result'
    data = json.loads(ledger.path.read_text())
    unknown, known = data['calls']
    assert unknown['status'] == 'unknown' and unknown['reserved_yuan'] > 0
    assert data['budget_used_upper_yuan'] == pytest.approx(unknown['reserved_yuan'] + known['upper_estimate_yuan'])
    assert known['reserved_at'] <= known['sent_at'] <= known['response_saved_at'] <= known['settled_at']
    assert json.loads((directory / 'test.ledger-response-0002.json').read_text())['choices']


def test_outer_stage_and_reentry_share_the_same_bounded_attempts(work, monkeypatch):
    calls = []

    def http(request, **_kwargs):
        calls.append(request.data)
        raise TimeoutError('still unavailable')

    monkeypatch.setattr('urllib.request.urlopen', http)
    action = lambda: provider().complete('system', 'question')
    for run_id in ('run', 'run:final-retry', 'orchestrator-resume'):
        with pytest.raises(ProviderUnavailable):
            stage(work, action, run_id=run_id)
    assert len(calls) == 13 and len(set(calls)) == 1
    assert sum(work[2]) == 3650
    assert any(state == 'blocked' for state, _ in work[1])


def test_stop_during_task_wait_prevents_further_sends(work, monkeypatch):
    calls = []

    def http(request, **_kwargs):
        calls.append(request.data)
        raise TimeoutError('offline')

    def stop():
        if work[1] and work[1][-1][0] == 'retry_wait':
            raise InterruptedError('user stopped')

    monkeypatch.setattr('urllib.request.urlopen', http)
    with pytest.raises(InterruptedError, match='user stopped'):
        stage(work, lambda: provider().complete('system', 'question'), stop=stop)
    assert len(calls) == 4
    assert sum(work[2]) == 50


def test_script_and_recovered_entry_share_e5_reservation_and_cannot_spend_it_twice(work, monkeypatch):
    from app.paid_policy import E5_POLICY, current_binding, e5_cost, restore_paid_context

    store = work[0]
    path = store.database_path.parent/'120b.ledger.json'
    policy = {'kind':E5_POLICY, 'database_path':str(store.database_path), 'budget_usd':0.0005}
    prices = {MODEL:{**PRICES[MODEL], 'currency':'USD'}}
    ledger = PaidRun(path, prices=prices, identity='same-authorization', identity_check=lambda:'same-authorization',
                     output_limits={'answer':10},request_policy=policy)
    network = []

    def http(_request, **_kwargs):
        network.append(True)
        raise TimeoutError('result unknown')

    monkeypatch.setattr('urllib.request.urlopen', http)
    from app.paid_run import provider_task
    with provider_task('answer'):
        with controlled_run(ledger), accounting_only():
            binding = current_binding()
            with pytest.raises(ProviderUnavailable, match='授权余额不足'):
                provider().complete('system', 'question')
        with restore_paid_context(store, binding, reopen=True):
            with pytest.raises(ProviderUnavailable, match='授权余额不足'):
                provider().complete('system', 'question')
    data = json.loads(path.read_text())
    assert len(network) == 1
    assert data['calls'][0]['status'] == 'unknown'
    assert 0 < e5_cost(data['calls'])['budget_used_upper_usd'] < policy['budget_usd']


def test_non_transient_http_status_never_reaches_second_send(work, monkeypatch):
    network = []

    def http(request, **_kwargs):
        network.append(request.data)
        raise HTTPError(request.full_url, 501, 'not implemented', {}, io.BytesIO(b'{}'))

    monkeypatch.setattr('urllib.request.urlopen', http)
    with pytest.raises(ProviderUnavailable):
        stage(work, lambda: provider().complete('system', 'question'))
    assert len(network) == 1 and not work[2]


def test_cycle_keeps_blocked_sandbox_and_charges_each_send_to_the_bound_ledger(
        legacy_launch, monkeypatch, tmp_path):
    from test_candidate_resume import CandidateResumeTests
    from app.optimization_cycle import claim_cycle, run_until_qualified
    from app.paid_policy import experiment_binding
    from app.paid_run import provider_task

    monkeypatch.setattr('app.corpus.INDEX_DIR', tmp_path/'index')
    case = CandidateResumeTests()
    case.setUp()
    try:
        ledger = experiment_binding(case.store, case.exp, provider())
        assert experiment_binding(case.store, case.exp) == ledger
        case.runtime.provider = object()
        payloads = []

        def http(request, **_kwargs):
            payloads.append(request.data)
            raise TimeoutError('fixture connection lost')

        def answer(question, _config):
            with provider_task('answer'):
                return provider().complete('system', question)

        monkeypatch.setattr('urllib.request.urlopen', http)
        monkeypatch.setattr('app.providers._retry_sleep', lambda *_: None)
        case.runtime.answer = answer
        claim_cycle(case.store, case.exp, current_round_only=True)
        cycle = run_until_qualified(case.store, case.runtime, case.exp, claimed=True)
        candidate = case.store.candidate(case.cid)
        run = case.store.evaluation_run(candidate['result']['evaluation_run_id'])
        assert cycle['status'] == run['result']['auto_recovery']['state'] == 'blocked'
        assert run['result']['auto_recovery']['ledger_path'] == ledger['ledger_path']
        assert len(payloads) == 13 and len(set(payloads)) == 1
        assert len(candidate['reasoning']['sandbox_attempts']) == 1
        calls = json.loads(Path(ledger['ledger_path']).read_text())['calls']
        assert len(calls) == 13 and all(c['status'] == 'unknown' for c in calls)
        assert all(c['reservation_estimate']['amount'] > 0 for c in calls)
    finally:
        case.tearDown()


def test_configured_standalone_adapters_account_for_each_real_send(work, monkeypatch):
    from app.config import load_settings

    database = work[0].database_path
    values = {'RAG_DEMO_DB_PATH': str(database), 'DEEPSEEK_API_KEY': 'offline',
              'DEEPSEEK_BASE_URL': 'https://fixture.invalid', 'DEEPSEEK_MODEL': MODEL,
              'DASHSCOPE_API_KEY': 'offline', 'DASHSCOPE_BASE_URL': 'https://fixture.invalid'}
    remote = DeepSeekProvider(load_settings(values, database.parent/'absent.env'))
    monkeypatch.setattr('app.knowledge_pipeline.settings', lambda: values)

    def http(request, **_kwargs):
        if request.full_url.endswith('/embeddings'):
            return io.BytesIO(b'{"usage":{"total_tokens":20}}')
        return reply()

    monkeypatch.setattr('urllib.request.urlopen', http)
    assert remote.complete('system', 'question') == 'saved result'
    assert AlibabaProvider()._post('/embeddings', {'model':'text-embedding-v4'})['usage']['total_tokens'] == 20
    ledger = database.with_name(database.name + '.provider-ledgers')/'standalone.ledger.json'
    calls = json.loads(ledger.read_text())['calls']
    assert [row['provider'] for row in calls] == ['DeepSeek', 'Alibaba']
    assert all(row['response_saved_at'] <= row['settled_at'] for row in calls)
