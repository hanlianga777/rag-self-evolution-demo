#!/usr/bin/env python3
"""021c/021c2: private checkpointed rechecks/trials; never writes or serves the demo database.

start/status are operational commands. compare reads saved data and makes no RPC.
The demo does not import this module or open its database.
"""
import argparse
import fcntl
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from contextlib import contextmanager, closing
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from app.governance import GovernanceStore
from app.evaluation import EvaluationRunner, candidate_comparison, protected_question, sandbox_cost
from app.evaluation_contract import evaluation_identity, policy_current
from app.policy import (ALLOWED_SEARCH_SPACE, GATE_DEFINITIONS, evaluate_gates, validate_candidate_config,
                        evaluate_regression, qualify_release, d_improves_winner)

DEFAULT_SOURCE = ROOT / 'backend/data/demo.db'
DEFAULT_OUT = ROOT / 'output/task021c'
DEFAULT_EXPERIMENT = 'EXP-20261105143048349606'
PROTECTED = ('evaluation_runs', 'evaluation_case_results', 'evaluation_checkpoints', 'job_checkpoints',
             'dataset_versions', 'questions', 'candidate_configs', 'experiments', 'recommendations',
             'production_versions', 'bad_cases')
PRIVATE_TABLES = ('evaluation_runs', 'evaluation_case_results', 'evaluation_checkpoints', 'job_checkpoints',
                  'questions', 'candidate_configs', 'experiments', 'bad_cases', 'alias_mappings',
                  'recommendations', 'approvals')


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def save(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2))
    temporary.replace(path)


class ReadOnlyStore(GovernanceStore):
    @contextmanager
    def connection(self):
        with closing(sqlite3.connect(self.database_path.resolve().as_uri() + '?mode=ro', uri=True)) as db:
            db.row_factory = sqlite3.Row
            db.execute('PRAGMA query_only=ON')
            yield db


class InternalStore(GovernanceStore):
    def update_evaluation_progress(self, run_id, result, *, checkpoint_id=None):
        return super().update_evaluation_progress(run_id, {**result, 'internal_recheck': True,
            'purpose': '内部复核'}, checkpoint_id=checkpoint_id)

    def finish_evaluation_run(self, run_id, status, result, error_message=None):
        return super().finish_evaluation_run(run_id, status, {**result, 'internal_recheck': True,
            'purpose': '内部复核'}, error_message)


def protected_state(source):
    store = ReadOnlyStore(source, migrate=False)
    result = {}
    with store.connection() as db:
        db.execute('BEGIN')
        for table in PROTECTED:
            h = hashlib.sha256()
            count = 0
            for row in db.execute('SELECT * FROM ' + table + ' ORDER BY rowid'):
                raw = json.dumps(tuple(row), ensure_ascii=False).encode()
                h.update(len(raw).to_bytes(8, 'big'))
                h.update(raw)
                count += 1
            result[table] = {'rows': count, 'sha256': h.hexdigest()}
    return result


def complete_run(store, run_id):
    run = store.evaluation_run(run_id)
    if not run or run['status'] != 'completed' or run['result'].get('evaluation_complete') is not True:
        raise ValueError('需要已完成的50题原评测：' + str(run_id))
    snapshot = json.loads(run['dataset_snapshot_json'])
    cases = store.evaluation_case_results(run_id)
    ids = snapshot.get('question_ids', [])
    if (len(ids) != 50 or len(set(ids)) != 50 or len(cases) != 50
            or {c['question_id'] for c in cases} != set(ids)
            or any(type(c.get('passed')) is not bool for c in cases)):
        raise ValueError('需要完整50题且无重复、无未知判定：' + run_id)
    if run['judge'].get('evaluation_identity') != evaluation_identity(snapshot, run['judge']):
        raise ValueError('原评测评分身份不一致')
    return run


def selected_candidates(source, experiment_id):
    experiment = source.experiment(experiment_id)
    recommendation = source.recommendation(experiment_id)
    if not experiment or not recommendation or recommendation['status'] != 'Recommended' or not recommendation['candidate_id']:
        raise ValueError('等推荐确定后由总指挥另行安排启动')
    cycle = experiment['result'].get('optimization_cycle', {})
    schedule = experiment['result'].get('composite_schedule', {})
    if cycle.get('status') == 'running' or schedule.get('status') in {'waiting', 'running'}:
        raise ValueError('D尚未结束；等推荐确定后由总指挥另行安排启动')
    selected = source.candidate(recommendation['candidate_id'])
    if not selected or selected['status'] != 'evaluated' or not selected['result'].get('qualification', {}).get('qualified'):
        raise ValueError('最终推荐没有完整合格记录')
    candidates = [selected]
    if selected['reasoning'].get('candidate_label') == 'D':
        first = next((c for c in experiment['candidates'] if c['reasoning'].get('round') == 3
                      and c['reasoning'].get('candidate_label') == 'C'), None)
        if not first:
            raise ValueError('D胜出但首个合格方案R3-C记录缺失')
        candidates.append(first)
    elif not (selected['reasoning'].get('round') == 3 and selected['reasoning'].get('candidate_label') == 'C'):
        raise ValueError('推荐不是任务约定的R3-C或D')
    return experiment, candidates


def prepare(source_path, out, experiment_id, *, trials=False, dependency=DEFAULT_OUT):
    source_path, out = Path(source_path).resolve(), Path(out).resolve()
    private_path = out / 'internal.db'
    if private_path.resolve() == source_path:
        raise ValueError('内部库必须与demo库隔离')
    if (out / 'state.json').exists():
        state = json.loads((out / 'state.json').read_text())
        if (state['source_path'] != str(source_path) or state['experiment_id'] != experiment_id
                or bool(state.get('trials')) != trials
                or trials and state.get('dependency') != str(Path(dependency).resolve())):
            raise ValueError('已有断点属于其他来源，拒绝覆盖')
        return state
    source = ReadOnlyStore(source_path, migrate=False)
    experiment, candidates = selected_candidates(source, experiment_id)
    if trials:
        candidates = [c for c in experiment['candidates'] if c['reasoning'].get('round') == 3
                      and c['reasoning'].get('candidate_label') == 'C']
        if len(candidates) != 1:
            raise ValueError('缺少唯一R3-C，不能建立内部试跑')
    baseline = complete_run(source, experiment['baseline_run_id'])
    originals = [complete_run(source, c['result']['evaluation_run_id']) for c in candidates]
    if any(r['dataset_snapshot_json'] != baseline['dataset_snapshot_json'] or r['judge'] != baseline['judge'] for r in originals):
        raise ValueError('Golden或评分身份与Baseline不一致')
    trial_configs = []
    if trials:
        dependency = Path(dependency).resolve()
        dep = json.loads((dependency / 'state.json').read_text())
        matches = [j for j in dep['jobs'] if j['source_run_id'] == originals[0]['id']]
        if (dep['source_path'] != str(source_path) or dep['experiment_id'] != experiment_id
                or dependency == out or len(matches) != 1):
            raise ValueError('内部复核断点与R3-C来源不一致')
        for changes in ({'top_k': 6}, {'top_k': 6, 'prompt_strategy': 'Tiered'}):
            config = {**originals[0]['config'], **changes}
            check = validate_candidate_config({k: v for k, v in config.items() if k in ALLOWED_SEARCH_SPACE})
            if not check['valid']:
                raise ValueError('内部试跑配置非法：' + str(check['errors']))
            trial_configs.append((changes, config))
    before = protected_state(source_path)
    out.mkdir(parents=True, exist_ok=True)
    if private_path.exists():
        raise ValueError('发现未登记的内部库；保留断点，禁止覆盖或重新付费')
    # Only schemas and this experiment's frozen inputs are copied. No full DB
    # backup, migration, active-production write, recommendation or budget update.
    with source.connection() as src, closing(sqlite3.connect(private_path)) as dst:
        for table in PRIVATE_TABLES:
            dst.execute(src.execute('SELECT sql FROM sqlite_master WHERE type=\'table\' AND name=?', (table,)).fetchone()[0])
        def copy_rows(table, where, args):
            rows = src.execute('SELECT * FROM ' + table + ' WHERE ' + where, args).fetchall()
            for row in rows:
                dst.execute('INSERT INTO ' + table + ' VALUES (' + ','.join('?' for _ in row) + ')', tuple(row))
        copy_rows('experiments', 'id=?', (experiment_id,))
        for candidate in candidates:
            copy_rows('candidate_configs', 'id=?', (candidate['id'],))
        for run_id in dict.fromkeys([baseline['id'], *[r['id'] for r in originals]]):
            copy_rows('evaluation_runs', 'id=?', (run_id,))
            copy_rows('evaluation_case_results', 'run_id=?', (run_id,))
        copy_rows('alias_mappings', "status='approved'", ())
        dst.commit()
    private = InternalStore(private_path, migrate=False)
    jobs = []
    inputs = ([(candidates[0], originals[0], changes, config) for changes, config in trial_configs] if trials else
              [(c, r, {}, r['config']) for c, r in zip(candidates, originals)])
    for candidate, original, changes, config in inputs:
        run_id = private.create_evaluation_run(json.loads(original['dataset_snapshot_json']), config, original['judge'])
        private.update_evaluation_progress(run_id, {'internal_recheck': True, 'purpose': '内部复核'})
        jobs.append({'candidate_id': candidate['id'], 'source_run_id': original['id'], 'run_id': run_id,
                     'source_config_sha256': digest(original['config'])})
        if trials:
            jobs[-1].update(label='内部-' + str(len(jobs)), changes=changes, config_sha256=digest(config))
            with private.connection() as db:
                db.execute("UPDATE evaluation_runs SET status='queued' WHERE id=?", (run_id,))
    state = {'internal_recheck': True, 'purpose': '内部复核', 'created_at': now(), 'source_path': str(source_path),
             'experiment_id': experiment_id, 'baseline_id': baseline['id'], 'jobs': jobs,
             'protected_before': before, 'protected_after_prepare': protected_state(source_path)}
    if trials:
        state.update(trials=True, purpose='内部试跑D候选', dependency=str(dependency),
                     dependency_run_id=matches[0]['run_id'], queue_status='waiting_for_recheck')
    if state['protected_before'] != state['protected_after_prepare']:
        raise ValueError('正式记录哈希变化，禁止启动；请检查并发写入')
    save(out / 'state.json', state)
    return state


def index_state(config):
    from app.corpus import INDEX_DIR, current_manifest, manifest_identity
    from app.knowledge_pipeline import index_for_config
    path = index_for_config(INDEX_DIR, config).resolve()
    identity = manifest_identity(json.loads((path / 'manifest.json').read_text()))
    if config.get('knowledge_identity') != identity or manifest_identity(current_manifest()) != identity:
        raise ValueError('索引或源文件身份与原评测不一致')
    files = {}
    for p in sorted(path.rglob('*')):
        if p.is_file():
            h = hashlib.sha256()
            with p.open('rb') as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                    h.update(chunk)
            files[str(p.relative_to(path))] = h.hexdigest()
    return {'path': str(path), 'identity': identity, 'files': files}


def runtime_for(store, job):
    from app.ai_service import AiService
    from app.config import load_settings
    from app.corpus import CorpusStore
    from app.providers import DeepSeekProvider, judge_thinking
    original = store.evaluation_run(job['source_run_id'])
    settings = load_settings()
    if not settings.configured:
        raise ValueError('未配置模型，禁止用Mock代替内部复核')
    index = index_state(original['config'])
    runtime = AiService(store, CorpusStore(Path(index['path'])), DeepSeekProvider(settings), False,
                        generation_prompt_version=original['judge']['generation_prompt_version'])
    info = runtime.corpus.index_info()
    execution = original['judge']['execution_snapshot']
    if any(info.get(k) != execution.get(k) for k in ('embedding_model', 'vector_index')):
        raise ValueError('Embedding模型或向量索引与原评测不一致')
    with judge_thinking(original['judge'].get('judge_thinking', {}).get('reasoning_effort')):
        EvaluationRunner(store, runtime)._require_generation_contract(original['judge'])
    if not policy_current(original['judge']) or runtime.model != original['judge']['model']:
        raise ValueError('模型或评分合同已改变，禁止跨身份内部复核')
    return runtime, index


def execute_job(store, job, runtime):
    run = store.evaluation_run(job['run_id'])
    if run['status'] == 'completed':
        if run['result'].get('evaluation_complete'):
            return run
        raise ValueError('技术失败已结束但成绩不完整；保留已付费断点，不自动另建或重复运行')
    original = store.evaluation_run(job['source_run_id'])
    if (run['config'] != {**original['config'], **job.get('changes', {})} or run['judge'] != original['judge']
            or run['dataset_snapshot_json'] != original['dataset_snapshot_json']):
        raise ValueError('内部记录配置、题卷或评分身份改变')
    if run['status'] in {'queued', 'partial', 'failed'}:
        # Resume the same run with all saved cases/RPCs intact. The runner only
        # accepts progress writes while running; no new candidate is reserved.
        with store.connection() as db:
            db.execute("UPDATE evaluation_runs SET status='running',error_message=NULL,completed_at=NULL WHERE id=?",
                       (job['run_id'],))
    runner = EvaluationRunner(store, runtime)
    return runner.execute_baseline(job['run_id'], runner.snapshot_items(json.loads(run['dataset_snapshot_json'])), run['config'])


def wait_for_official(state, out):
    """Yield new internal RPCs to any official evaluation; never touch its rows."""
    official = ReadOnlyStore(state['source_path'], migrate=False)
    waited = False
    while True:
        with official.connection() as db:
            active = db.execute("SELECT 1 FROM evaluation_runs WHERE status IN ('queued','running') LIMIT 1").fetchone()
        status = 'waiting_for_official' if active else 'running'
        if state.get('queue_status') != status:
            state['queue_status'] = status
            save(out / 'state.json', state)
        if not active:
            return waited
        waited = True
        time.sleep(1)


def worker(out):
    from app.paid_run import PaidRun, controlled_run
    from app.paid_schedule import wait_for_off_peak
    # Lock out concurrent starts/resumes. Completed cases and durable RPCs stay
    # in the same run, so restarting this worker never redoes completed questions.
    with (out / 'worker.lock').open('w') as lock:
        # The parent briefly holds this lock while saving the child's PID.
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = json.loads((out / 'state.json').read_text())
        store = InternalStore(out / 'internal.db', migrate=False)
        dependency_lock = None
        try:
            if state.get('trials'):
                state['queue_status'] = 'waiting_for_recheck'
                save(out / 'state.json', state)
                # The existing 021c worker owns this lock for its entire run.
                # Wait in the background without touching its state or results.
                dependency_lock = (Path(state['dependency']) / 'worker.lock').open('a')
                fcntl.flock(dependency_lock, fcntl.LOCK_EX)
                dep = ReadOnlyStore(Path(state['dependency']) / 'internal.db', migrate=False)
                with dep.connection() as db:
                    row = db.execute("SELECT status,json_extract(result_json,'$.evaluation_complete') done FROM evaluation_runs WHERE id=?",
                                     (state['dependency_run_id'],)).fetchone()
                if not row or row['status'] != 'completed' or row['done'] != 1:
                    raise ValueError('内部复核中断或不完整；保留队列，不重跑已付费题')
            for job in state['jobs']:
                saved_run = store.evaluation_run(job['run_id'], light=True)
                if saved_run['status'] == 'completed' and saved_run['result'].get('evaluation_complete'):
                    continue
                if state.get('trials'):
                    wait_for_official(state, out)
                runtime, index = runtime_for(store, job)
                if index != job['index']:
                    raise ValueError('冻结索引文件哈希改变')
                def pause(value):
                    # Keep checkpoints; status() reads only this scalar state.
                    run = store.evaluation_run(job['run_id'])
                    store.update_evaluation_progress(job['run_id'], {**run['result'], 'price_pause': value})
                def identity_check():
                    # Reuse the existing price-window policy before every RPC,
                    # including Judge/format/transport retries, with no override.
                    while True:
                        wait_for_off_peak(store, 'internal:' + job['run_id'], pause)
                        if not state.get('trials') or not wait_for_official(state, out):
                            break
                        # Waiting for an official run may have crossed into peak.
                    from app.corpus import current_manifest, manifest_identity
                    if manifest_identity(current_manifest()) != index['identity']:
                        raise ValueError('运行期间源文件或索引身份改变')
                    return job.get('config_sha256', job['source_config_sha256'])
                path = out / (job['run_id'] + '-calls.json')
                ledger = (PaidRun.load_accounting(path, identity_check) if path.exists() else
                          PaidRun(path, identity=job.get('config_sha256', job['source_config_sha256']), identity_check=identity_check,
                                  output_limits=store.evaluation_run(job['source_run_id'])['judge']['execution_snapshot']['request_limits']))
                with controlled_run(ledger):
                    result = execute_job(store, job, runtime)
                if result['status'] != 'completed' or not result['result'].get('evaluation_complete'):
                    raise RuntimeError('内部评测未形成完整成绩，保留断点；不另建运行')
            state['worker_finished_at'] = now()
            if state.get('trials'):
                state['queue_status'] = 'completed'
        except Exception as error:
            state['worker_error'] = str(error)
            state['worker_ended_at'] = now()
            if state.get('trials'):
                state['queue_status'] = 'blocked'
        finally:
            if dependency_lock:
                dependency_lock.close()
            state['protected_after_worker'] = protected_state(state['source_path'])
            state['official_unchanged'] = state['protected_before'] == state['protected_after_worker']
            save(out / 'state.json', state)


def start(source, out, experiment, *, trials=False, dependency=DEFAULT_OUT):
    out.mkdir(parents=True, exist_ok=True)
    with (out / 'start.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        state = prepare(source, out, experiment, trials=trials, dependency=dependency)
        with (out / 'worker.lock').open('a') as worker_lock:
            try:
                fcntl.flock(worker_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return {'already_started': True, 'started_at': state.get('started_at')}
            store = InternalStore(out / 'internal.db', migrate=False)
            runs = [store.evaluation_run(j['run_id'], light=True) for j in state['jobs']]
            if all(r['status'] == 'completed' and r['result'].get('evaluation_complete') for r in runs):
                return {'already_completed': True, 'started_at': state.get('started_at')}
            for job in state['jobs']:
                _, index = runtime_for(store, job)
                if job.get('index') and job['index'] != index:
                    raise ValueError('断点索引改变，禁止付费')
                job['index'] = index
            state.pop('worker_error', None)
            state['started_at'] = now()
            save(out / 'state.json', state)
            with (out / 'worker.log').open('ab') as log:
                child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), 'worker', '--out', str(out)],
                                         cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
            state['worker_pid'] = child.pid
            save(out / 'state.json', state)
            return {'started_at': state['started_at'], 'worker_pid': child.pid,
                    'jobs': [{k: j[k] for k in ('candidate_id', 'source_run_id', 'run_id')} for j in state['jobs']]}


def status(out):
    """One allowed confirmation: no cases, counters, accounting or checkpoints."""
    state = json.loads((out / 'state.json').read_text())
    source = ReadOnlyStore(out / 'internal.db', migrate=False)
    jobs = []
    with source.connection() as db:
        for job in state['jobs']:
            row = db.execute("SELECT status,json_extract(result_json,'$.price_pause') pause FROM evaluation_runs WHERE id=?",
                             (job['run_id'],)).fetchone()
            pause = json.loads(row['pause']) if row['pause'] else {}
            jobs.append({'run_id': job['run_id'], 'status': row['status'], 'price_pause': pause})
    try:
        os.kill(state['worker_pid'], 0)
        alive = True
    except (KeyError, ProcessLookupError):
        alive = False
    return {**({'queue_status': state.get('queue_status')} if state.get('trials') else {}),
            'checked_at': now(), 'started_at': state.get('started_at'), 'jobs': jobs, 'worker_alive': alive,
            'worker_error': state.get('worker_error'), 'official_unchanged':
            protected_state(state['source_path']) == state['protected_before']}


def category(baseline, original, recheck):
    if not baseline:
        return '稳定修好' if original and recheck else '只一次修好' if original or recheck else '稳定仍错'
    return '稳定新坏' if not original and not recheck else '只一次新坏' if not original or not recheck else '稳定答对'


def attribute(original, recheck):
    traces = [c.get('programmatic_metrics', {}).get('retrieval_trace', {}) for c in (original, recheck)]
    if any(any(not isinstance(t.get(s), list) for s in ('candidates', 'reranked', 'final')) for t in traces):
        return '不确定', '保存的候选、重排或最终证据列表缺失，无法比较证据位置。'
    signatures = [{stage: [(e.get('chunk_id'), e.get('matched_child_ids'), e.get('page')) for e in t[stage]]
                   for stage in ('candidates', 'reranked', 'final')} for t in traces]
    changed = [stage for stage in signatures[0] if signatures[0][stage] != signatures[1][stage]]
    if changed:
        return '检索不同', '保存证据位置不同：' + '、'.join(changed) + '（含列表顺序）；只说明伴随差异。'
    answers = [c.get('model_answer') for c in (original, recheck)]
    if any(not isinstance(a, str) or not a.strip() for a in answers):
        return '不确定', '两次保存证据位置相同，但完整回答缺失。'
    normalized = [re.sub(r'\s+', ' ', a).strip() for a in answers]
    if normalized[0] != normalized[1]:
        return '生成不同', '保存证据位置相同，完整回答文字不同；未调用模型判断改写是否语义等价。'
    reasons = [c.get('judge_result', {}).get('reason', '') for c in (original, recheck)]
    if any(re.search('要点|覆盖|明确|必须|遗漏|完整|表达|满足|缺少|未提', str(reason)) for reason in reasons):
        return '判分边界', '保存回答仅折叠空白后相同而判定相反；评分理由涉及要点或表达边界：' + ' / '.join(str(r)[:180] for r in reasons)
    return '不确定', '保存证据和回答相同而判定不同，但理由不足以定位评分要点歧义。'


def qualification(baseline, cases, metrics, golden):
    gates = evaluate_gates(metrics)
    comparison = candidate_comparison(baseline, cases, list(baseline), golden)
    # Saved structural findings on a continued failing question can also add a
    # critical issue; do not miss them by examining PASS->FAIL alone.
    continued = comparison.get('continued_failure_new_critical_question_ids', [])
    checks = {'完整50题': len(cases) == 50 and len(baseline) == 50 and comparison['comparison_complete'],
              '11/11': gates['passed'] and gates['passed_count'] == 11,
              '无新增关键错题': comparison['new_critical_failures'] == 0 and not continued,
              '比Baseline至少少1错题': sum(c.get('passed') is False for c in cases.values()) <= sum(c.get('passed') is False for c in baseline.values()) - 1,
              '至少修好1题': len(comparison['all_fixed_question_ids']) >= 1}
    return {'qualified': all(checks.values()), 'checks': checks, 'gates': gates,
            'fixed': comparison['all_fixed_question_ids'],
            'new_critical': [q for q in comparison['new_regression_question_ids'] if protected_question(baseline[q], golden.get(q))] + continued}


def trial_outcome(baseline, original, trial, original_metrics, trial_metrics):
    """Use the existing D release (vs Baseline) and winner improvement rules."""
    comparison = candidate_comparison(baseline, trial, list(baseline))
    gates = evaluate_gates(trial_metrics)
    regression = evaluate_regression(new_critical_failures=comparison['new_critical_failures'],
                                    new_ordinary_failures=comparison['new_ordinary_failures'])
    release = qualify_release(gates, regression, len(comparison['all_fixed_question_ids']))
    def result(cases, metrics):
        return {'result': {'bad_case_count': sum(c.get('passed') is False for c in cases.values()),
                           'metrics': metrics, 'estimated_cost': sandbox_cost(list(cases.values()))}}
    checks = {'完整50题': len(baseline) == len(original) == len(trial) == 50
                            and comparison['comparison_complete'] and set(original) == set(trial),
              '11/11门槛': gates['passed'] and gates['passed_count'] == 11,
              '相对Baseline零新增错题': release['checks']['zero_new_failures'],
              '相对Baseline至少修好1道': release['checks']['at_least_one_fixed'],
              '错题更少或错题相同且P99及费用均更低': d_improves_winner(result(trial, trial_metrics), result(original, original_metrics))}
    return {'wins': all(checks.values()), 'checks': checks}


def compare_trials(out, report, state):
    """Commander-only, offline comparison of the five saved complete runs."""
    store = ReadOnlyStore(out / 'internal.db', migrate=False)
    dep = ReadOnlyStore(Path(state['dependency']) / 'internal.db', migrate=False)
    jobs = state['jobs']
    runs = [complete_run(store, state['baseline_id']), complete_run(store, jobs[0]['source_run_id']),
            complete_run(dep, state['dependency_run_id']), *[complete_run(store, j['run_id']) for j in jobs]]
    original = runs[1]
    expected = [runs[0]['config'], original['config'], original['config'],
                *[{**original['config'], **j['changes']} for j in jobs]]
    for run, config in zip(runs, expected):
        if (run['config'] != config or run['judge'] != original['judge']
                or run['dataset_snapshot_json'] != original['dataset_snapshot_json']):
            raise ValueError('五列配置、Golden或评分身份不一致，不能比较')
    names = ['Baseline', 'R3-C 原评测', 'R3-C 内部复核', *[j['label'] for j in jobs]]
    cases = [{c['question_id']: c for c in s.evaluation_case_results(r['id'])}
             for s, r in zip((store, store, dep, store, store), runs)]
    metrics = [r['result'].get('metrics', {}) for r in runs]
    snapshot = json.loads(original['dataset_snapshot_json'])
    golden = {q['id']: q for q in snapshot['questions']}
    lines = ['# 内部试跑D候选逐题对比', '', '仅使用保存数据，没有模型调用；结果只供内部判断，不写正式候选、D结论或推荐。', '',
             '判定沿用现有D规则：零新增错题和至少修好1道相对Baseline；优劣相对R3-C原评测。另列相对R3-C及内部复核的新坏题，不混淆两种比较。', '',
             '| 门槛/指标 | ' + ' | '.join(names) + ' |', '| --- | ' + ' | '.join(['---'] * 5) + ' |',
             '| 运行编号 | ' + ' | '.join(r['id'] for r in runs) + ' |',
             '| 错题数 | ' + ' | '.join(str(sum(c['passed'] is False for c in group.values())) for group in cases) + ' |']
    for i, gate in enumerate(GATE_DEFINITIONS):
        lines.append('| ' + gate['metric'] + ' | ' + ' | '.join(
            f"{m.get(gate['metric']) if m.get(gate['metric']) is not None else '未知'}（{evaluate_gates(m)['gates'][i]['status']}）" for m in metrics) + ' |')
    costs = [sandbox_cost(list(group.values())) for group in cases]
    lines += ['| 费用（保存用量估算USD；非账单扣款） | ' + ' | '.join(
        str(c['amount']) if c['amount'] is not None else '未知' for c in costs) + ' |', '',
        '| 题目 | ' + ' | '.join(names) + ' |', '| --- | ' + ' | '.join(['---'] * 5) + ' |']
    for q in snapshot['question_ids']:
        question = str(golden[q].get('question', q)).replace('|', '／').replace('\n', ' ')
        lines.append('| ' + q + ' ' + question + ' | ' + ' | '.join('对' if c[q]['passed'] else '错' for c in cases) + ' |')
    for i in (3, 4):
        lines += ['', '## ' + names[i], '']
        # Every internal trial is compared with all three references and its peer.
        for j in range(5):
            if i == j:
                continue
            change = candidate_comparison(cases[j], cases[i], list(cases[j]), golden)
            lines += [f"相对{names[j]}：修好：" + ('、'.join(change['all_fixed_question_ids']) or '无') +
                      '；弄坏：' + ('、'.join(change['new_regression_question_ids']) or '无') + '。']
        outcome = trial_outcome(cases[0], cases[1], cases[i], metrics[1], metrics[i])
        lines += ['', '| D规则检查 | 是否满足 |', '| --- | --- |']
        lines += [f"| {k} | {'是' if v else '否'} |" for k, v in outcome['checks'].items()]
        lines += ['', '是否胜过 R3-C：' + ('是' if outcome['wins'] else '否') + '。']
        ledger = out / (jobs[i - 3]['run_id'] + '-calls.json')
        if ledger.exists():
            calls = json.loads(ledger.read_text())['calls']
            lines += [f"保存账本：DeepSeek {sum(c['provider']=='DeepSeek' for c in calls)} 次，其他Provider {sum(c['provider']!='DeepSeek' for c in calls)} 次；账单扣费未知。"]
    unchanged = protected_state(state['source_path']) == state['protected_before']
    lines += ['', f'正式记录与排队前哈希一致：{unchanged}。来源：state.json与正式库只读哈希。', '']
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text('\n'.join(lines))
    return {'report': str(report), 'official_unchanged': unchanged}


def compare(out, report):
    """Saved results only; imports no runtime and performs no model call."""
    state = json.loads((out / 'state.json').read_text())
    if state.get('trials'):
        return compare_trials(out, report, state)
    store = ReadOnlyStore(out / 'internal.db', migrate=False)
    baseline = complete_run(store, state['baseline_id'])
    base = {c['question_id']: c for c in store.evaluation_case_results(baseline['id'])}
    snapshot = json.loads(baseline['dataset_snapshot_json'])
    golden = {q['id']: q for q in snapshot['questions']}
    lines = ['# 内部复核逐题对比', '', '仅使用保存数据；没有重新检索、生成或判分。本报告不进入demo，不是发布条件。', '']
    for job in state['jobs']:
        original, rerun = [complete_run(store, job[key]) for key in ('source_run_id', 'run_id')]
        if (original['config'] != rerun['config'] or original['judge'] != rerun['judge']
                or original['dataset_snapshot_json'] != rerun['dataset_snapshot_json']):
            raise ValueError('三列身份不一致，不能比较')
        old, new = [{c['question_id']: c for c in store.evaluation_case_results(r['id'])} for r in (original, rerun)]
        metrics = [r['result'].get('metrics', {}) for r in (baseline, original, rerun)]
        outcomes = [qualification(base, cases, m, golden) for cases, m in zip((old, new), metrics[1:])]
        lines += ['## ' + job['candidate_id'], '', f"原评测：{original['id']}；内部复核：{rerun['id']}。", '',
                  '| 门槛/指标 | Baseline | 原评测 | 内部复核 |', '| --- | --- | --- | --- |']
        for gate in GATE_DEFINITIONS:
            key = gate['metric']
            lines.append('| ' + key + ' | ' + ' | '.join(f"{m.get(key, '未知')}（{evaluate_gates(m)['gates'][list(GATE_DEFINITIONS).index(gate)]['status']}）" for m in metrics) + ' |')
        lines += ['', '| 题目 | Baseline | 原评测 | 内部复核 | 分类 | 归因 | 一句依据 |', '| --- | --- | --- | --- | --- | --- | --- |']
        groups = {}
        for q in snapshot['question_ids']:
            values = [cases[q]['passed'] for cases in (base, old, new)]
            label = category(*values)
            groups.setdefault(label, []).append(q)
            attribution, reason = attribute(old[q], new[q]) if values[1] != values[2] else ('一致', '两次保存判定均为' + ('通过。' if values[1] else '失败。'))
            question = str(golden[q].get('question', q)).replace('|', '／').replace('\n', ' ')
            reason = reason.replace('|', '／').replace('\n', ' ')
            lines.append('| ' + q + ' ' + question + ' | ' + ' | '.join('对' if v else '错' for v in values) + f' | {label} | {attribution} | {reason} |')
        lines += ['', '### 候选合格条件（仅内部结论）', '', '| 条件 | 原评测 | 内部复核 |', '| --- | --- | --- |']
        for check in outcomes[0]['checks']:
            lines.append('| ' + check + ' | ' + ' | '.join('满足' if o['checks'][check] else '不满足' for o in outcomes) + ' |')
        lines += ['', '复核后仍满足候选合格条件：' + ('是' if outcomes[1]['qualified'] else '否') + '。',
                  '稳定修好：' + '、'.join(groups.get('稳定修好', [])) + '。',
                  '只一次修好（不稳定）：' + '、'.join(groups.get('只一次修好', [])) + '。',
                  '新增关键错题：' + ('、'.join(outcomes[1]['new_critical']) or '无') + '。', '']
        ledger_path = out / (job['run_id'] + '-calls.json')
        if ledger_path.exists():
            calls = json.loads(ledger_path.read_text())['calls']
            lines += [f"保存账本：DeepSeek {sum(c['provider']=='DeepSeek' for c in calls)} 次，其他Provider {sum(c['provider']!='DeepSeek' for c in calls)} 次；账单扣费未知。", '']
    unchanged = protected_state(state['source_path']) == state['protected_before']
    lines += [f'正式记录与启动前哈希一致：{unchanged}。来源：state.json protected_before 与当前只读哈希。', '']
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text('\n'.join(lines))
    return {'report': str(report), 'official_unchanged': unchanged}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('start', 'worker', 'status', 'compare'))
    parser.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--trials', action='store_true', help='021c2: R3-C TopK6 / TopK6+Tiered sequential trials')
    parser.add_argument('--dependency', type=Path, default=DEFAULT_OUT)
    parser.add_argument('--experiment', default=DEFAULT_EXPERIMENT)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    args.out = (args.out or (ROOT / 'output/task021c2' if args.trials else DEFAULT_OUT)).resolve()
    args.report = args.report or ROOT / ('指挥/报告/021c2-内部试跑D候选-逐题对比.md' if args.trials else '指挥/报告/021c-内部复核-逐题对比.md')
    if args.command == 'start':
        result = start(args.source, args.out, args.experiment, trials=args.trials, dependency=args.dependency)
    elif args.command == 'worker':
        worker(args.out)
        return
    elif args.command == 'status':
        result = status(args.out)
    else:
        result = compare(args.out, args.report)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
