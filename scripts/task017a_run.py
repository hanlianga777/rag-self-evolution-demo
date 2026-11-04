#!/usr/bin/env python3
"""017a authorized workflow; durable RPCs, $5 cap, every DeepSeek RPC off peak."""
import argparse
import csv
import fcntl
import hashlib
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from app.diagnostic_evidence import digest
from app.paid_run import PaidRun, REQUEST_LIMITS, controlled_run, accounting_only
from app.paid_policy import policy_cost
from task016b_trials import revised, save

OUT = ROOT / 'output/task017a'
PARENT = 'GD-20261101151940'
SOURCES = {'max': 'EVAL-20261103151339324195', 'A': 'EVAL-20261103225716098518',
           'B': 'EVAL-20261103234322134342', 'C': 'EVAL-20261104003045193515'}
STORE = None


def money():
    return policy_cost(OUT)


def ledger(name):
    path = OUT / (name + '.ledger.json')
    policy = {'kind': 'off_peak_usd_cap_v1', 'budget_usd': 5, 'ledger_directory': str(OUT),
        'database_path': str(STORE.database_path if STORE else OUT / 'isolated.db')}
    run = (PaidRun.load_accounting(path, lambda: name) if path.exists() else
           PaidRun(path, identity=name, identity_check=lambda: name, output_limits=REQUEST_LIMITS, request_policy=policy))
    if not run.request_policy:
        run.request_policy=policy;run.save()
    return run


def draft(store):
    parent = next(s['snapshot'] for s in store.dataset_snapshots() if s['id'] == PARENT)
    questions = [revised(q)[0] for q in parent['questions']]
    with (ROOT / '指挥/报告/016b-评分要点修订草案.csv').open(encoding='utf-8-sig') as stream:
        rows = {r['题号']:r for r in csv.DictReader(stream)}
    for before, after in zip(parent['questions'], questions):
        row = rows[before['coverage_slot']]
        assert json.loads(row['原必答']) == before['business_requirements']['required_checks']
        assert json.loads(row['改后必答']) == after['business_requirements']['required_checks']
    changed = [q['id'] for old,q in zip(parent['questions'], questions) if old != q]
    assert len(changed) == 20
    value = {'parent': parent, 'questions': questions, 'changed': changed,
        'draft_sha256': hashlib.sha256((ROOT / '指挥/报告/016b-评分要点修订草案.csv').read_bytes()).hexdigest()}
    save(OUT / 'draft.json', value)
    return value


def qc(main):
    from app.evaluation import EvaluationRunner
    from app.evaluation_stage import _request_checkpoint
    data = draft(main.store)
    items = EvaluationRunner(main.store, main.ai_service).snapshot_items({
        'questions': data['questions'], 'question_ids': data['parent']['question_ids']})
    def work(item):
        if item['id'] not in data['changed']: return
        name = 'qc-' + item['raw']['coverage_slot']
        path = OUT / (name + '.json')
        state = json.loads(path.read_text()) if path.exists() else {'attempts': []}
        if 'result' in state:
            assert state['question_sha256'] == digest(item['raw'])
            return
        if state.get('error'): return
        token = _request_checkpoint.set((state, 'qc', name, lambda *_a, **_k: save(path, state), lambda: None))
        try:
            with controlled_run(ledger(name)), accounting_only():
                result = main.ai_service.quality_check(item)
                state.update(result=result, question_sha256=digest(item['raw']))
        except Exception as error:
            state.update(error=type(error).__name__ + ': ' + str(error),
                raw_response=getattr(error, 'raw_provider_response', None))
        finally:
            _request_checkpoint.reset(token); save(path, state)
        print(name, 'saved' if 'result' in state else state.get('error'), flush=True)
    with ThreadPoolExecutor(max_workers=3) as pool: list(pool.map(work, items))
    print(json.dumps(money()), flush=True)


def freeze(main):
    from app.scoring_revision import freeze_scoring_revision
    data = json.loads((OUT / 'draft.json').read_text())
    results = {}
    for q in data['questions']:
        if q['id'] in data['changed']:
            value = json.loads((OUT / ('qc-' + q['coverage_slot'] + '.json')).read_text())
            results[q['id']] = {k: value[k] for k in ('question_sha256', 'result')}
    snapshot = freeze_scoring_revision(main.store, PARENT, data['questions'], results,
        actor='task017a_auto_authorized', reason='017a明确授权正式采用016b评分要点，20题补QC后冻结；确认默认同意',
        draft_sha256=data['draft_sha256'])
    save(OUT / 'frozen.json', snapshot)
    print('FROZEN', snapshot['id'], flush=True)


def replays(main):
    from app.evaluation import EvaluationRunner
    runner = EvaluationRunner(main.store, main.ai_service)
    target = json.loads((OUT / 'frozen.json').read_text())
    assert main.store.dataset_snapshots()[0]['id'] == target['id']
    def work(entry):
        label, source_id = entry
        path = OUT / ('replay-' + label + '.json')
        state = json.loads(path.read_text()) if path.exists() else {}
        with controlled_run(ledger('replay-' + label)), accounting_only():
            if not state.get('id'):
                # Recover the DB record if a process ended between insertion and marker.
                with main.store.connection() as db:
                    prior = db.execute("SELECT id FROM evaluation_runs WHERE dataset_version_id=? AND json_extract(result_json,'$.judge_replay.source_run_id')=? ORDER BY created_at DESC", (target['id'], source_id)).fetchall()
                if prior: state['id'] = prior[0]['id']
                else:
                    plan = runner.judge_replay_preflight(source_id, judge_thinking='low')
                    save(OUT / ('preflight-' + label + '.json'), plan)
                    if not plan['can_replay']: raise RuntimeError(json.dumps(plan, ensure_ascii=False))
                    state['id'], _, _ = runner.start_judge_replay(source_id, judge_thinking='low')
                state.update(source_id=source_id, dataset_id=target['id']); save(path, state)
                print('REPLAY_STARTED', label, state['id'], flush=True)
            run = main.store.evaluation_run(state['id'])
            if run['status'] != 'completed':
                if run['status'] in {'partial', 'failed'}:
                    assert run['result'].get('judge_replay', {}).get('source_run_id') == source_id
                    state.setdefault('previous_run_ids', []).append(run['id'])
                    # Formal resume copies completed cases and saved generation checkpoints.
                    state['id'], _, _ = runner.start_baseline(run['id'], automatic=True)
                    save(path, state)
                    run = main.store.evaluation_run(state['id'])
                run = runner.execute_baseline(run['id'], runner.snapshot_items(target), run['config'])
            state.update(status=run['status'], result={k:v for k,v in run['result'].items() if k != 'checkpoints'})
            save(path, state)
            if run['status'] != 'completed' or run['result'].get('technical_failed', 0):
                raise RuntimeError('Replay incomplete: ' + run['id'])
            source = {c['question_id']:c for c in main.store.evaluation_case_results(source_id)}
            saved = main.store.evaluation_case_results(run['id'])
            assert len(saved) == 50
            for c in saved:
                before = source[c['question_id']]
                assert c['model_answer'] == before['model_answer']
                for field in ('latency_ms', 'ttft_ms', 'retrieval_trace'):
                    assert c['programmatic_metrics'].get(field) == before['programmatic_metrics'].get(field)
            print('REPLAY_DONE', label, run['id'], 50 - run['result']['bad_case_count'], flush=True)
    # The formal start guard permits one active evaluation; preserve that rule.
    for entry in SOURCES.items(): work(entry)
    print(json.dumps(money()), flush=True)


def agent(main):
    from app.optimization import OptimizationAgent
    from app.optimization_cycle import claim_cycle, run_until_qualified
    replay = {label:json.loads((OUT / ('replay-' + label + '.json')).read_text()) for label in SOURCES}
    baseline = main.store.evaluation_run(replay['max']['id'])
    assert all(v['status'] == 'completed' for v in replay.values())
    path = OUT / 'agent.json'
    state = json.loads(path.read_text()) if path.exists() else {}
    if not state.get('baseline_designated'):
        value = main.store.designate_baseline(baseline['id'], replay['A']['id'], 'task017a_auto_authorized',
            '017a正式采用新评分要点：今天max的low重判设Baseline；同新题卷的历史方案A回放仅作对照')
        state.update(baseline_designated=value); save(path, state)
    if not state.get('experiment_id'):
        existing = main.store.current_baseline_identity().get('current_experiment_id')
        state['experiment_id'] = existing or main.store.create_experiment(baseline['id'])
        refs = [{'candidate_id': 'EXP-20261103225621615671-R1-' + label, 'replay_run_id': replay[label]['id']}
                for label in 'ABC']
        with main.store.connection() as db:
            row = db.execute('SELECT result_json FROM experiments WHERE id=?', (state['experiment_id'],)).fetchone()
            result = json.loads(row['result_json']); result['historical_sandbox_replays'] = refs
            db.execute('UPDATE experiments SET result_json=? WHERE id=?', (json.dumps(result, ensure_ascii=False), state['experiment_id']))
        save(path, state)
    experiment_id = state['experiment_id']
    with controlled_run(ledger('agent-cycle')), accounting_only():
        experiment = main.store.experiment(experiment_id)
        if not experiment['candidates']:
            experiment = OptimizationAgent(main.store, main.ai_service.provider).generate(baseline['id'], experiment_id=experiment_id)
        save(OUT / 'proposals.json', experiment)
        if len(experiment['candidates']) != 3: raise RuntimeError('ABC proposals not ready')
        cycle = experiment['result'].get('optimization_cycle', {})
        if cycle.get('status') != 'running':
            if cycle.get('phase') == 'review': return
            claim_cycle(main.store, experiment_id, current_round_only=True)
        state.update(cycle_started_at=datetime.now(timezone.utc).isoformat(), owner_pid=os.getpid())
        save(path, state)
        print('CYCLE_STARTED', experiment_id, flush=True)
        result = run_until_qualified(main.store, main.ai_service, experiment_id, claimed=True)
        save(OUT / 'cycle-finished.json', result)
        print('CYCLE_STOPPED', result, flush=True)


def main():
    global STORE
    parser = argparse.ArgumentParser(); parser.add_argument('phase', choices=['qc', 'freeze', 'replays', 'agent', 'money'])
    args = parser.parse_args(); OUT.mkdir(parents=True, exist_ok=True)
    if args.phase == 'money': print(json.dumps(money())); return
    with (OUT / 'worker.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        from app import main as application
        STORE = application.store
        assert application.ai_service.live_enabled
        globals()[args.phase](application)


if __name__ == '__main__': main()
