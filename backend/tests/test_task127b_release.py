"""127b pre-publish operations use a disposable database and no Provider calls."""
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.agent126c import E8_BASELINE
from app.agent127a_inheritance import E8_ID
from app.governance import GovernanceStore


def test_prepare_127b_backs_up_before_removing_only_e8(tmp_path):
    from app.task127b_release import CHECKPOINT, ROLLBACK, prepare_release, retire_e8

    store = GovernanceStore(tmp_path / 'live.sqlite3')
    experiment_id = 'e9'
    winner = 'e9-A'
    candidate = {'id': winner, 'result': {'evaluation_run_id': 'e9-eval'}}
    old_candidate = E8_ID + '-A'
    with store.connection() as db:
        db.execute('DELETE FROM production_versions')
        db.executemany('INSERT INTO experiments VALUES (?,?,?,?,?)',
                       [(owner, E8_BASELINE, 'generated', '{}', 'now') for owner in (E8_ID, experiment_id, 'other')])
        db.executemany('INSERT INTO candidate_configs VALUES (?,?,?,?,?,?,?)',
                       [(cid, owner, 'evaluated', '{}', '{}', '{}', 'now')
                        for cid, owner in ((old_candidate, E8_ID), (winner, experiment_id))])
        db.execute("UPDATE candidate_configs SET result_json=json_object('evaluation_run_id',?) WHERE id=?",
                   ('e9-eval', winner))
        db.execute("INSERT INTO evaluation_runs VALUES ('e9-eval','completed','real','real',NULL,"
                   "'{}','{}','{}','{}',NULL,'now','now')")
        db.execute("INSERT INTO production_versions(id,status,config_json,created_at,snapshot_json) "
                   "VALUES (?,'archived','{}','now',json_object('baseline_run_id',?))", (ROLLBACK, E8_BASELINE))
        db.execute("INSERT INTO production_versions(id,status,config_json,created_at,snapshot_json) "
                   "VALUES ('e8-online','active','{}','now',json_object('candidate_id',?))", (old_candidate,))
    event = []

    def rehearse(active, candidate):
        assert active['id'] == ROLLBACK
        assert candidate['id'] == winner
        assert store.active_production()['id'] == 'e8-online'
        event.append(winner)
        return {'status': 'passed'}

    engine = SimpleNamespace(id=experiment_id, store=store, check_stop=lambda: None,
                             rollback_index=lambda row: 'fixture-index', rehearse_rollback=rehearse)
    backup = tmp_path / 'backup.sqlite3'
    receipt = prepare_release(engine, candidate, backup)
    assert event == [winner]
    assert receipt == store.job_checkpoint(experiment_id, CHECKPOINT)
    assert store.active_production()['id'] == 'e8-online'
    with sqlite3.connect(Path(backup).as_uri() + '?mode=ro', uri=True) as db:
        assert db.execute("SELECT id FROM production_versions WHERE status='active'").fetchone() == ('e8-online',)
        assert db.execute('SELECT 1 FROM experiments WHERE id=?', (E8_ID,)).fetchone() == (1,)
    assert prepare_release(engine, candidate, backup) == receipt
    assert event == [winner]
    with pytest.raises(RuntimeError, match='publish failed'):
        with store.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            retire_e8(db, receipt)
            raise RuntimeError('publish failed')
    assert store.active_production()['id'] == 'e8-online'
    with store.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        retire_e8(db, receipt)
        db.execute("UPDATE production_versions SET status='active' WHERE id=?", (ROLLBACK,))
        assert {row[0] for row in db.execute('SELECT id FROM experiments')} == {experiment_id, 'other'}
        assert [row[0] for row in db.execute('SELECT id FROM candidate_configs')] == [winner]


def test_publish_127b_rolls_back_e8_removal_if_version_write_fails(tmp_path, monkeypatch):
    import json

    from app import task127b_release as release
    from app.paid_policy import EXPERIMENT_ACCOUNTING, bind_experiment
    from app.paid_run import PaidRun
    from app.workflow_engine import WorkflowEngine
    from test_task127a import make_e8_fixture

    manifest = {'sources': [{'id': 'test', 'sha256': 'a' * 64}]}
    store, source = make_e8_fixture(tmp_path, monkeypatch, manifest)
    monkeypatch.setattr('app.release_view.current_manifest', lambda: manifest)
    e9 = store.inherit_strategy_rounds(source, 2)
    baseline_id = store.experiment(e9, light=True)['baseline_run_id']
    monkeypatch.setattr(release, 'E8_BASELINE', baseline_id)
    winner = e9 + '-R000001-B'
    with store.connection() as db:
        db.execute('DELETE FROM production_versions')
        db.execute("INSERT INTO production_versions(id,status,config_json,created_at,snapshot_json) "
                   "VALUES (?,'archived','{}','now',json_object('baseline_run_id',?))", (release.ROLLBACK, baseline_id))
        db.execute("INSERT INTO production_versions(id,status,config_json,created_at,snapshot_json) "
                   "VALUES ('e8-online','active','{}','now',json_object('candidate_id',?))",
                   (source + '-R000001-B',))
        db.execute("UPDATE experiments SET result_json=json_set(result_json,'$.strategy126c.final',json(?)) WHERE id=?",
                   (json.dumps({'winner_id': winner, 'conditions': {'fixture': True}}), e9))
        db.execute("UPDATE candidate_configs SET result_json=json_set(result_json,"
                   "'$.release_qualification.qualified',json('true'),'$.regression.passed',json('true'),"
                   "'$.qualification.rule_version','127a','$.qualification.qualified',json('true')) WHERE id=?", (winner,))
        db.execute("""CREATE TRIGGER force_publish_failure BEFORE INSERT ON production_versions
            WHEN new.id GLOB 'production-*' BEGIN SELECT RAISE(ABORT, 'test insert failed'); END""")

    backup = tmp_path / 'backup.sqlite3'
    identity = {'task': '127b', 'experiment_id': e9, 'pre_release_backup': str(backup)}
    ledger = tmp_path / '127b.ledger.json'
    PaidRun(ledger, identity=identity, request_policy={'kind': EXPERIMENT_ACCOUNTING,
            'database_path': str(store.database_path), 'budget_usd': None})
    bind_experiment(store, e9, {'ledger_path': str(ledger), 'ledger_identity': identity})
    monkeypatch.setattr(WorkflowEngine, 'rollback_index', lambda *_: 'fixture-index')
    monkeypatch.setattr(WorkflowEngine, 'rehearse_rollback', lambda *_: {'status': 'passed'})
    engine = WorkflowEngine(store, SimpleNamespace(provider=None), e9)

    failed = engine.start('release', background=False)
    assert failed['last_error'] == 'test insert failed', failed
    assert store.active_production()['id'] == 'e8-online'
    assert store.experiment(source)
    assert backup.is_file()

    with store.connection() as db:
        db.execute('DROP TRIGGER force_publish_failure')
    finished = engine.start('release', background=False)
    assert (finished['status'], finished['phase']) == ('completed', 'published'), finished
    online = store.active_production()
    assert online['previous_version_id'] == release.ROLLBACK
    assert online['snapshot']['human_release']['confirmed_by'] == '总指挥'
    assert not store.experiment(source)
    assert store.candidate(winner)
