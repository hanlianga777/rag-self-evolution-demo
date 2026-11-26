"""Offline lease races and process loss using disposable SQLite databases."""
import json
import os
import select
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from threading import Barrier

import pytest

from app import task_leases
from app.governance import GovernanceStore


def test_only_one_worker_can_claim(tmp_path):
    store = GovernanceStore(tmp_path / 'demo.db')
    barrier = Barrier(2)

    def claim():
        barrier.wait()
        with store.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            return task_leases.claim(db, 'cycle:exp')

    with ThreadPoolExecutor(2) as pool:
        claims = list(pool.map(lambda _: claim(), range(2)))
    assert sum(token is not None for token in claims) == 1


def test_killed_worker_recovers_checkpoint_and_old_token_cannot_write(tmp_path, monkeypatch):
    store = GovernanceStore(tmp_path / 'demo.db')
    worker = subprocess.Popen([sys.executable, '-c', """
import sys, time
from app import task_leases
from app.governance import GovernanceStore
store = GovernanceStore(sys.argv[1], migrate=False)
with store.connection() as db:
    db.execute('BEGIN IMMEDIATE')
    token = task_leases.claim(db, 'evaluation:run')
with task_leases.work(store, 'evaluation:run', token):
    store.save_job_checkpoint('run', 'Q1', {'answer': 'saved'})
    print(token, flush=True)
    time.sleep(60)
""", str(store.database_path)], stdout=subprocess.PIPE, text=True)
    try:
        assert select.select([worker.stdout], [], [], 8)[0]
        old_token = worker.stdout.readline().strip()
        assert old_token
    finally:
        if worker.poll() is None:
            worker.kill()
        worker.wait(timeout=5)
        worker.stdout.close()

    with store.connection() as db:
        assert task_leases.active(db, 'evaluation:run')
        expires = db.execute('SELECT lease_expires_at FROM task_leases WHERE task_key=?',
                             ('evaluation:run',)).fetchone()[0]
    monkeypatch.setattr(task_leases, 'now', lambda: expires + 1)
    with store.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        token = task_leases.claim(db, 'evaluation:run', recovering=True)
    assert token and token != old_token
    assert store.job_checkpoint('run', 'Q1') == {'answer': 'saved'}
    with task_leases.work(store, 'evaluation:run', token):
        store.save_job_checkpoint('run', 'Q2', {'answer': 'resumed'})
    with pytest.raises(task_leases.LeaseLost):
        with task_leases.work(store, 'evaluation:run', old_token):
            store.save_job_checkpoint('run', 'Q1', {'answer': 'stale'})
    assert store.job_checkpoint('run', 'Q1') == {'answer': 'saved'}
    assert store.job_checkpoint('run', 'Q2') == {'answer': 'resumed'}


def test_evaluation_stop_persists_after_lease_expires(tmp_path, monkeypatch):
    store = GovernanceStore(tmp_path / 'demo.db')
    run_id = store.create_evaluation_run({'id': 'fixture'}, {}, {})
    store.update_evaluation_progress(run_id, {'auto_recovery': {'enabled': True}})
    assert store.claim_evaluation_worker(run_id)
    store.request_evaluation_stop(run_id)
    with store.connection() as db:
        expires = db.execute('SELECT lease_expires_at FROM task_leases WHERE task_key=?',
                             ('evaluation:' + run_id,)).fetchone()[0]
    monkeypatch.setattr(task_leases, 'now', lambda: expires + 1)
    assert not store.claim_evaluation_worker(run_id, recovering=True)
    assert store.request_evaluation_stop(run_id)['result']['stop_request']
    assert not store.evaluation_runs(authorized_only=True)


def test_legacy_external_cycle_is_reclaimed(tmp_path, monkeypatch):
    from app import optimization_cycle

    store = GovernanceStore(tmp_path / 'demo.db')
    state = json.dumps({'optimization_cycle': {'status': 'running', 'owner_pid': 2147483647,
        'external_runner': True, 'phase': 'sandbox', 'updated_at': datetime.now(timezone.utc).isoformat()}})
    with store.connection() as db:
        db.execute("INSERT INTO experiments VALUES ('exp','base','completed',?,'2020-01-01')", (state,))
    calls = []

    class InlineWorker:
        def __init__(self, *, target, args, kwargs, daemon):
            self.call = lambda: target(*args, **kwargs)

        def start(self):
            self.call()

    monkeypatch.setattr(optimization_cycle.threading, 'Thread', InlineWorker)
    monkeypatch.setattr(optimization_cycle, 'run_until_qualified',
                        lambda *args, **kwargs: calls.append(store.experiment('exp', light=True)['result']['optimization_cycle']))
    optimization_cycle.recover_optimization_cycles(store, None)
    assert len(calls) == 1
    assert calls[0]['status'] == 'recovering'
    assert calls[0]['phase'] == 'sandbox'
    assert not calls[0]['external_runner']


def test_evaluation_recovery_skips_saved_case_in_same_run(monkeypatch):
    from test_baseline_resume import ResumeTests, Runtime
    from app.evaluation import EvaluationRunner
    from app.paid_schedule import set_settings

    fixture = ResumeTests()
    fixture.setUp()
    try:
        store = fixture.store
        set_settings(store, False)
        run_id, _, _ = fixture.runner.start_baseline(automatic=True)
        command = """
import sys, time
from app.evaluation import EvaluationRunner
from app.governance import GovernanceStore
from test_baseline_resume import Runtime
runtime = Runtime(fail=None)
original = runtime.judge
def judge(question, *args, **kwargs):
    if question == 'Q2':
        print('waiting for kill', flush=True)
        time.sleep(60)
    return original(question, *args, **kwargs)
runtime.judge = judge
EvaluationRunner(GovernanceStore(sys.argv[1], migrate=False), runtime).recover_run(sys.argv[2])
"""
        env = dict(os.environ)
        env['PYTHONPATH'] = os.pathsep.join((str(Path(__file__).resolve().parents[1]),
                                                         str(Path(__file__).resolve().parent)))
        with subprocess.Popen([sys.executable, '-c', command, str(store.database_path), run_id],
                              env=env, stdout=subprocess.PIPE, text=True) as worker:
            try:
                assert select.select([worker.stdout], [], [], 8)[0]
                assert worker.stdout.readline().strip() == 'waiting for kill'
            finally:
                if worker.poll() is None:
                    worker.kill()
        assert [case['question_id'] for case in store.evaluation_case_results(run_id)] == ['Q1']
        with store.connection() as db:
            lease = task_leases.row(db, 'evaluation:' + run_id)
            old_token = json.loads(lease['lease_owner'])['token']
        monkeypatch.setattr(task_leases, 'now', lambda: lease['lease_expires_at'] + 1)

        runtime = Runtime(fail=None)
        recovered = EvaluationRunner(store, runtime).recover_run(run_id)
        assert recovered['id'] == run_id
        assert recovered['result']['evaluation_complete']
        assert runtime.answers == ['Q3', 'Q4']
        assert runtime.judges == ['Q2', 'Q3', 'Q4']
        with pytest.raises(task_leases.LeaseLost):
            with task_leases.work(store, 'evaluation:' + run_id, old_token):
                store.record_evaluation_case(run_id, 'Q99', {'passed': True})
        assert len(store.evaluation_case_results(run_id)) == 4
    finally:
        fixture.tearDown()


def test_heartbeat_extends_lease_during_worker_wait(tmp_path, monkeypatch):
    from threading import Event

    store = GovernanceStore(tmp_path / 'demo.db')
    renewed = Event()
    monkeypatch.setattr(task_leases, 'HEARTBEAT_SECONDS', 0.01)
    original = task_leases.renew

    def renew(*args, start=False):
        ok = original(*args, start=start)
        if not start and ok:
            renewed.set()
        return ok

    clock = [1000]
    monkeypatch.setattr(task_leases, 'now', lambda: clock[0])
    monkeypatch.setattr(task_leases, 'renew', renew)
    with store.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        token = task_leases.claim(db, 'agent:exp')
    with task_leases.work(store, 'agent:exp', token):
        clock[0] = 1030
        assert renewed.wait(2)
        with store.connection() as db:
            lease = task_leases.row(db, 'agent:exp')
            assert (lease['heartbeat_at'], lease['lease_expires_at']) == (1030, 1210)
            with pytest.raises(task_leases.LeaseLost):
                task_leases.require(db, 'agent:exp', 'wrong-token')


def test_completed_incomplete_is_eligible_for_recovery(tmp_path):
    store = GovernanceStore(tmp_path / 'demo.db')
    run_id = store.create_evaluation_run({'id': 'fixture'}, {}, {})
    store.finish_evaluation_run(run_id, 'completed', {'evaluation_complete': False})
    with store.connection() as db:
        db.execute("""UPDATE evaluation_runs SET result_json=json_set(result_json,
                      '$.auto_recovery.enabled', json('true')) WHERE id=?""", (run_id,))
    assert store.evaluation_history()[0]['status'] == 'partial'
    assert [run['id'] for run in store.evaluation_runs(authorized_only=True)] == [run_id]
    token = store.claim_evaluation_worker(run_id, recovering=True)
    assert token
    with store.connection() as db:
        assert task_leases.row(db, 'evaluation:' + run_id)['business_status'] == 'recovering'
    assert store.evaluation_run(run_id)['status'] == 'running'


def test_inflight_stale_writer_rolls_back_its_transaction(tmp_path, monkeypatch):
    store = GovernanceStore(tmp_path / 'demo.db')
    key = 'evaluation:run'
    clock = [1000]
    monkeypatch.setattr(task_leases, 'now', lambda: clock[0])

    def claim(*, recovering=False):
        with store.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            return task_leases.claim(db, key, recovering=recovering)

    old = claim()
    with task_leases.work(store, key, old):
        store.save_job_checkpoint('run', 'Q1', {'answer': 'original'})
        clock[0] = 1181
        with ThreadPoolExecutor(1) as pool:
            new = pool.submit(claim, recovering=True).result(timeout=5)
        assert new and new != old
        with pytest.raises(task_leases.LeaseLost):
            store.save_job_checkpoint('run', 'Q1', {'answer': 'late result'})
    assert store.job_checkpoint('run', 'Q1') == {'answer': 'original'}
    with store.connection() as db:
        assert task_leases.active(db, key)


def test_d_resumes_saved_response_without_another_provider_call(monkeypatch, legacy_launch):
    from types import SimpleNamespace
    from app import optimization, paid_schedule
    from test_task020b_composite import CompositeRecoveryTests

    fixture = CompositeRecoveryTests()
    fixture.setUp()
    try:
        store = fixture.store
        experiment_id = fixture.experiment
        paid_schedule.set_settings(store, False)
        requests = []

        def complete(*args, **kwargs):
            requests.append(True)
            return '{"fixture": "D reply"}'

        def interrupted(raw, audit):
            assert raw == '{"fixture": "D reply"}'
            raise SystemExit('fixture interruption after response persistence')

        provider = SimpleNamespace(complete=complete)
        monkeypatch.setattr(optimization, 'parse_agent_json', interrupted)
        for _ in range(2):
            with pytest.raises(SystemExit):
                store.create_composite(experiment_id, provider)
        assert len(requests) == 1
        decision = store.experiment(experiment_id, light=True)['result']['composite']
        assert decision['attempts'][0]['provider_raw_text'] == '{"fixture": "D reply"}'
        assert decision['provider_calls'] == 1
    finally:
        fixture.doCleanups()


def test_new_scheduled_d_does_not_keep_a_previous_price_override(tmp_path, monkeypatch):
    from app import paid_schedule

    store = GovernanceStore(tmp_path / 'demo.db')
    experiment_id = 'exp'
    with store.connection() as db:
        result = {'report_confirmation': {'winner_id': 'fixture-winner'}}
        db.execute("INSERT INTO experiments VALUES (?,'base','completed',?,'2026-11-07')",
                   (experiment_id, json.dumps(result)))
    key = 'composite:' + experiment_id
    monkeypatch.setattr(paid_schedule, 'utc_now', lambda: datetime(2026, 11, 4, 1, tzinfo=timezone.utc))
    paid_schedule.set_run_now(store, key)
    assert not paid_schedule.pause_state(store, key)['paused']
    token, state = paid_schedule.claim_composite(store, experiment_id, scheduled=True)
    assert token
    assert state['price_pause']['paused']
    assert paid_schedule.pause_state(store, key)['paused']
