#!/usr/bin/env python3
"""120b: resume E5, reconcile the task budget, and run the authorized release."""
import fcntl
import json
import os
from pathlib import Path
import sys
import time
from datetime import datetime, timezone
from unittest.mock import patch
from urllib.request import urlopen

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app import governance, optimization_cycle as cycle, paid_policy, paid_schedule, rules, verdict
from app.ai_service import AiService
from app.composite import pipeline_config
from app.config import load_settings
from app.corpus import INDEX_DIR, CorpusStore, current_manifest, manifest_identity
from app.evaluation import EvaluationRunner
from app.evaluation_stage import perform_stage
from app.generation_probe import SOURCE, run_probe
from app.judge_replay import resolve_question_ids
from app.knowledge_pipeline import index_for_config
from app.optimization import load_retrieval_preview, require_retrieval_preview
from app.paid_run import PaidRun, REQUEST_LIMITS, accounting_only, controlled_run
from app.policy import require_gate_request_actor
from app.providers import DeepSeekProvider, ProviderBlocked, permanent_provider_error, provider_retry_scope
from app.release_view import release_review_view
from app.request_reuse import bypass_reuse

DATA = BACKEND / 'data'
PRIVATE = DATA / 'task120b'
DB = DATA / 'demo.db'
PROGRESS = DATA / 'run_e5_progress.json'
BASE = 'EVAL-20261120213645613191'
E4 = 'EXP-20261124163600086429'
SEED = E4 + '-R1-A'
AUTH = {'enabled': True, 'actor': '用户', 'authorized_at': '2026-11-25T09:09:00-05:00',
        'audit_note': '120b：用户 2026-11-25 09:09 授权 Gate 2 与 Gate 3，Codex 执行'}
CAP = 3.0
# Same conservative peak-price snapshot and exchange rate as the original 120b ledger.
RATES = {'deepseek-flash': {'provider': 'DeepSeek', 'input': 0.3, 'output': 1.2,
                           'max_output': 65536, 'currency': 'USD'},
         **paid_policy.ALIBABA_RATES}
SAFETY = [f'Q{number:02d}' for number in range(43, 51)]
CHANGES = [{'generation_thinking': 'low'}, {'generation_thinking': 'high'},
           {'prompt_strategy': 'Looser'}, {'prompt_strategy': 'Safe'}]


def write(path, value):
    temp = path.with_name(path.name + '.tmp')
    with temp.open('w') as stream:
        json.dump(value, stream, ensure_ascii=False, allow_nan=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    temp.replace(path)


class Budget:
    def __init__(self, directory, identity, check_identity, limits):
        path = directory / '120b.ledger.json'
        policy = {'kind': paid_policy.E5_POLICY, 'database_path': str(DB),
                  'ledger_directory': str(directory), 'budget_usd': CAP}
        if path.exists():
            stored = json.loads(path.read_text())
            if (stored['identity'] != identity or stored['price_snapshot'] != RATES
                    or stored['output_limits'] != limits or stored.get('request_policy') != policy):
                raise ValueError('付费账本身份、计价或请求上限与冻结记录不同')
            self.ledger = PaidRun.load_accounting(path, check_identity)
            self.ledger.reopen()
        else:
            self.ledger = PaidRun(path, prices=RATES, identity=identity, identity_check=check_identity,
                                  output_limits=limits, request_policy=policy)
        self.ledger.phase = 'preflight'
        self.check_stop = lambda: None

    def summary(self):
        data = json.loads(self.ledger.path.read_text())
        cost = paid_policy.e5_cost(data['calls'])
        return {'cap_usd': data['request_policy']['budget_usd'],
                'upper_usd': round(cost['budget_used_upper_usd'], 9),
                'known_usd': round(cost['known_usd'], 9), 'unknown_or_inflight': cost['unknown'],
                'deepseek_calls': cost['deepseek_calls'], 'alibaba_calls': cost['alibaba_calls']}


class E5Runner(EvaluationRunner):
    def __init__(self, store, runtime, budget, experiment_id):
        super().__init__(store, runtime)
        self.budget = budget
        self.experiment_id = experiment_id

    def diagnostic_retest(self, run_id, question_ids, *, repetitions=3, config_override=None):
        identity = [run_id, question_ids, repetitions, config_override]
        key = '120b:diagnostic:' + rules.canonical_hash(identity)
        saved = self.store.job_checkpoint(self.experiment_id, key) or {}
        if 'result' in saved:
            return saved['result']
        checkpoints = saved.setdefault('trials', {})

        def persist():
            self.store.save_job_checkpoint(self.experiment_id, key, saved)

        result = super().diagnostic_retest(run_id, question_ids, repetitions=repetitions,
                                          config_override=config_override,
                                          resume=(checkpoints, persist, self.budget.check_stop))
        saved['result'] = result
        persist()
        return result


def find_experiment(store):
    with store.connection() as db:
        matches = db.execute("""SELECT DISTINCT experiment_id FROM candidate_configs
            WHERE json_extract(reasoning_json,'$.source_candidate_id')=?""", (SEED,)).fetchall()
    marker = PRIVATE / 'experiment.json'
    if len(matches) > 1:
        raise ValueError('有多个实验引用指定 A，无法唯一确认 E5')
    if matches:
        experiment_id = matches[0][0]
        if marker.exists() and json.loads(marker.read_text()) != experiment_id:
            raise ValueError('E5 本地记录与正式库不同')
    else:
        if marker.exists() or (PRIVATE / '120b.ledger.json').exists():
            raise ValueError('有 E5 本地记录，但正式库缺少对应实验')
        experiment_id = store.create_experiment(BASE, mode='initial', decision_contract_v2=True,
                           seed_candidates=[{'experiment_id': E4, 'candidate_id': SEED}])
    entry = store.experiment(experiment_id, light=True)
    seed = store.candidate(experiment_id + '-R1-A')
    if (entry['baseline_run_id'] != BASE or entry['result'].get('mode') != 'initial'
            or seed['result'].get('source_candidate_id') != SEED):
        raise ValueError('E5 的模式、Baseline 或引用 A 不一致')
    write(marker, experiment_id)
    return experiment_id


def verify_owner(state):
    owner = state.get('owner_pid')
    if state.get('status') == 'running' and type(owner) is int and owner != os.getpid():
        try:
            os.kill(owner, 0)
        except ProcessLookupError:
            return
        raise ValueError(f'E5 仍由进程 {owner} 执行')


def restore_candidate(store, runner, baseline, candidate):
    run_id = candidate['result'].get('evaluation_run_id')
    if not run_id:
        return
    run = store.evaluation_run(run_id)
    if run['status'] == 'completed' and run['result'].get('evaluation_complete'):
        runner.finalize_saved_candidate(run, candidate, baseline)
        return
    if run['status'] in {'queued', 'running'}:
        return  # The native cycle recovers the same run and durable question state.
    plan = runner.candidate_resume_plan(candidate['id'])
    if not plan['can_resume'] or plan['source_run_id'] != run_id:
        raise ValueError(plan.get('reason') or '续跑断点与 Candidate 不一致')
    if candidate['status'] == 'running':
        # An older Demo marked the evaluation partial but left the candidate running.
        store.finish_candidate(candidate['id'], 'failed', {**run['result'],
            'evaluation_run_id': run_id, 'baseline_run_id': BASE, 'error': run['error_message']})
    outcome = runner.run_candidate(candidate['id'], automatic=True, manual_resume=True)
    if outcome['status'] != 'evaluated':
        result = store.evaluation_run(outcome['result']['evaluation_run_id'], light=True)
        recovery = result['result'].get('auto_recovery', {})
        error_type = ProviderBlocked if recovery.get('state') == 'blocked' else InterruptedError
        raise error_type(result.get('error_message') or recovery.get('error') or 'Sandbox 续跑未完成，断点已保存')


def physical_rollback(version):
    snapshot = version['snapshot']
    path = index_for_config(INDEX_DIR, {**version['config'], 'knowledge_identity': snapshot['knowledge_identity']})
    if not (path / 'manifest.json').is_file() or not (path / 'faiss.index').is_file():
        raise ValueError('回滚版本缺少索引文件')
    index = CorpusStore(path).index_info()
    if (index['embedding_model'] != snapshot['embedding_model']
            or index['knowledge_identity'] != snapshot['knowledge_identity']
            or snapshot['generation_model'] != load_settings().model):
        raise ValueError('回滚版本的索引或模型与当前环境不兼容')
    return str(path.resolve())


def api(endpoint):
    with urlopen('http://127.0.0.1:8010/api/' + endpoint, timeout=20) as response:
        return json.load(response)


class Run:
    def __init__(self):
        self.store = None
        self.experiment_id = None
        self.budget = None
        self.phase = 'preflight'
        self.owns_cycle = False
        self.last_progress = 0

    def progress(self, status='running', error=None):
        state = {}
        rounds = {}
        recommendation = None
        if self.experiment_id:
            experiment = self.store.experiment(self.experiment_id, light=True)
            state = experiment['result'].get('optimization_cycle', {})
            for candidate in experiment['candidates']:
                reasoning, result = candidate['reasoning'], candidate['result']
                label = reasoning.get('candidate_label')
                number = 'D' if label == 'D' else str(reasoning.get('round', 1))
                rounds.setdefault(number, {})[label] = {'id': candidate['id'], 'status': candidate['status'],
                    'run_id': result.get('evaluation_run_id'),
                    'qualified': result.get('qualification', {}).get('qualified'),
                    'passed': result.get('passed_count'), 'bad_case_count': result.get('bad_case_count')}
            recommendation = (self.store.recommendation(self.experiment_id) or {}).get('result', {}).get('recommended_candidate')
        write(PROGRESS, {'experiment_id': self.experiment_id, 'pid': os.getpid(),
              'updated_at': datetime.now(timezone.utc).isoformat(), 'status': status, 'step': self.phase,
              'provider_retry': state.get('provider_retry'),
              'cycle_phase': state.get('phase'), 'round': state.get('round'),
              'active_candidate': next((c['id'] for r in rounds.values() for c in r.values() if c['status'] == 'running'), None),
              'rounds': rounds, 'staged_decision': state.get('staged_decision'),
              'recommendation': recommendation, 'cost': self.budget.summary() if self.budget else None,
              'error': error})
        self.last_progress = time.monotonic()

    def heartbeat(self):
        if time.monotonic() - self.last_progress >= 3:
            self.progress()
        cycle.check_cycle_stop(self.store, self.experiment_id)

    def phase_state(self, phase, **values):
        self.phase = self.budget.ledger.phase = phase
        cycle._save_state(self.store, self.experiment_id, phase=phase, **values)
        self.progress()

    def diagnosis(self, runner, snapshot, plan):
        winner = plan['winner']
        source = self.store.candidate(winner)['result']['evaluation_run_id'] if winner else BASE
        final = verdict.final_verdicts(source, store=self.store)
        selected = set(resolve_question_ids(snapshot, ['Q07', 'Q17', 'Q20', 'Q21', 'Q27', 'Q29', *SAFETY]))
        selected.update(q for q, passed in final.items() if not passed)
        self.phase_state('generation_probe', status='running', last_error=None)
        for change in CHANGES:
            for qid in snapshot['question_ids']:
                if qid not in selected:
                    continue
                self.heartbeat()
                ledger = self.store.experiment(self.experiment_id, light=True)['result']['parameter_effect_ledger']['current']
                saved = next((row for row in ledger if row['source'] == SOURCE and row['base_id'] == (winner or 'Baseline')
                              and row['changes'] == change and row['question_id'] == qid), None)
                if saved:
                    if saved['status'] == '未知':
                        raise ValueError(f'生成诊断结果未知，保留原样本：{qid} {change}')
                    continue
                run_probe(self.store, runner, self.experiment_id, source, [change], [qid],
                          repetitions=3, base_key=winner or 'Baseline')
        self.store.save_job_checkpoint(self.experiment_id, '120b:probe-plan', {**plan, 'complete': True})

    def release(self, runner, baseline, snapshot):
        rec = (self.store.recommendation(self.experiment_id) or {}).get('result', {})
        if rec.get('status') != 'Recommended':
            raise ValueError('E5 缺少正式推荐')
        cid = rec['recommended_candidate']
        candidate = self.store.candidate(cid)
        run_id = candidate['result']['evaluation_run_id']
        confirmation = self.store.experiment(self.experiment_id, light=True)['result']['report_confirmation']
        winner_id = confirmation['winner_id']
        if cid != winner_id:
            winner = self.store.candidate(winner_id)
            before_d = verdict.final_verdicts(winner['result']['evaluation_run_id'], store=self.store)
            after_d = verdict.final_verdicts(run_id, store=self.store)
            if (cid != self.experiment_id + '-D' or before_d.keys() != after_d.keys()
                    or not {q for q, passed in before_d.items() if passed} < {q for q, passed in after_d.items() if passed}):
                raise ValueError('推荐 D 缺少相对 Winner 的非回退和新增修复证据')
        start = verdict.final_verdicts(BASE, store=self.store)
        end = verdict.final_verdicts(run_id, store=self.store)
        if not start.keys() == end.keys() == set(snapshot['question_ids']):
            raise ValueError('复测前逐题最终判定不完整')
        selected = {q for q in start if not start[q] or not end[q]}
        selected.update(resolve_question_ids(snapshot, SAFETY))
        self.phase_state('final_retest', status='running', last_error=None)
        summary = {}
        for label, source in [('baseline', BASE), ('recommendation', run_id)]:
            summary[label] = {}
            for q in snapshot['question_ids']:
                if q not in selected:
                    continue
                self.heartbeat()
                row, = runner.diagnostic_retest(source, [q], repetitions=3)['questions']
                summary[label][row['display_question_id']] = {key: row[key] for key in ('passed', 'unknown', 'risk')}
        self.store.save_job_checkpoint(self.experiment_id, '120b:final-retest',
            {'baseline': BASE, 'candidate': cid, 'run_id': run_id, 'summary': summary})

        checkpoint = '120b:release'
        receipt = self.store.job_checkpoint(self.experiment_id, checkpoint) or {}
        active = self.store.active_production()
        if any(row['risk'] is not False or row['unknown'] for group in summary.values() for row in group.values()):
            self.store.save_job_checkpoint(self.experiment_id, checkpoint, {'result': 'blocked_safety', 'candidate': cid})
            return 'release_blocked'
        if receipt.get('result') == 'unchanged':
            if receipt['version'] != active['id'] or receipt['candidate'] != cid:
                raise ValueError('生产版本在上次核验后已变化')
            return 'unchanged'

        if receipt.get('candidate') == cid and active['snapshot'].get('candidate_id') == cid:
            published = active
        elif receipt.get('result') == 'published':
            raise ValueError('E5 发布后活动生产版本已变化')
        else:
            rollback = physical_rollback(active)
            source = self.store.evaluation_run(run_id, light=True)
            same_config = (pipeline_config(active['config']) == pipeline_config(candidate['config'])
                           and active['snapshot']['knowledge_identity'] == source['config']['knowledge_identity']
                           and active['snapshot']['generation_model'] == source['judge']['model'])
            if same_config:
                self.store.save_job_checkpoint(self.experiment_id, checkpoint,
                    {'result': 'unchanged', 'version': active['id'], 'candidate': cid, 'rollback_index': rollback})
                return 'unchanged'
            self.phase_state('release')
            self.heartbeat()
            if error := self.store.release_gate_error(candidate):
                raise ValueError(error)
            if not all(row['ok'] is True for row in release_review_view(self.store, cid)['checks']):
                raise ValueError('Gate 3 发布检查未全过')
            require_gate_request_actor('gate3', AUTH['actor'])
            if receipt and receipt != {'candidate': cid, 'rollback': active['id'], 'rollback_index': rollback}:
                raise ValueError('发布准备记录与当前生产配置不一致')
            receipt = {'candidate': cid, 'rollback': active['id'], 'rollback_index': rollback}
            self.store.save_job_checkpoint(self.experiment_id, checkpoint, receipt)
            native_audit = governance.gate_audit

            def audit(gate, actor, **kwargs):
                verified = native_audit(gate, actor, **kwargs)
                if self.store.active_production()['id'] != receipt['rollback']:
                    raise ValueError('发布前生产版本已变化')
                return {**verified, 'authorizer': '用户', 'authorized_at': '2026-11-25 09:09',
                        'executed_by': 'Codex'}

            with patch.object(governance, 'gate_audit', audit):
                published = self.store.publish_candidate(cid, AUTH['actor'])

        audit = published['snapshot']['human_release']
        if (published['config'] != candidate['config'] or published['previous_version_id'] != receipt['rollback']
                or (audit.get('authorizer'), audit.get('authorized_at'), audit.get('executed_by'))
                != ('用户', '2026-11-25 09:09', 'Codex')):
            raise ValueError('发布后的版本或审计字段与计划不同')
        prior = next(v for v in self.store.production_versions() if v['id'] == receipt['rollback'])
        if prior['status'] != 'archived' or physical_rollback(prior) != receipt['rollback_index']:
            raise ValueError('发布后的回滚点核验失败')
        self.store.save_job_checkpoint(self.experiment_id, checkpoint,
            {**receipt, 'result': 'published', 'version': published['id'], 'audit': audit})
        self.phase_state('production_smoke')
        self.smoke(runner.runtime, snapshot, published)
        return 'published'

    def smoke(self, runtime, snapshot, published):
        pipeline = api('pipeline')
        versions = api('versions')
        if (pipeline['active_version_id'] != published['id'] or pipeline['config'] != published['config']
                or versions[0]['status'] != 'active' or versions[0]['id'] != published['id']):
            raise ValueError('Demo API 读到的生产配置与发布记录不同')
        key = '120b:production-smoke:' + published['id']
        saved = self.store.job_checkpoint(self.experiment_id, key) or {'attempts': []}
        if 'result' in saved:
            return
        question = next(q['question'] for q in snapshot['questions'] if q['display_id'] == 'Q06')

        def persist(*_args, **_kwargs):
            self.store.save_job_checkpoint(self.experiment_id, key, saved)

        with bypass_reuse(), accounting_only():
            response = perform_stage(saved, 'generation', lambda: runtime.baseline_preview(question),
                                     key, automatic=False, check_stop=self.heartbeat, on_state=persist)
        if (response['version'] != published['id'] or response['mode'] != 'live'
                or not response['answer'] or not response['evidence']):
            raise ValueError('发布后正式问答主链路核验失败')
        saved['result'] = {'version': response['version'], 'mode': response['mode'], 'evidence': len(response['evidence'])}
        persist()

    def execute(self):
        self.store = store = governance.GovernanceStore(DB, migrate=False)
        baseline = store.require_current_baseline(BASE)
        snapshot = json.loads(baseline['dataset_snapshot_json'])
        corpus = CorpusStore()
        identity = snapshot['corpus_fingerprint']
        preview = load_retrieval_preview(store, BASE, foundation=identity)
        seed = store.candidate(SEED)
        required = {k: seed['config'][k] for k in ('candidate_k', 'top_k')}
        require_retrieval_preview(preview, required)
        if (corpus.index_info()['knowledge_identity'] != identity or baseline['config']['knowledge_identity'] != identity
                or len(verdict.final_verdicts(BASE, store=store)) != 50):
            raise ValueError('Baseline 最终判定或检索预演与 E5 的冻结知识身份不符')
        runtime = AiService(store, corpus, DeepSeekProvider(load_settings()), False)
        if not runtime.live_enabled or runtime.model != baseline['judge']['model']:
            raise ValueError('真实 Provider 或冻结模型不可用')
        self.experiment_id = eid = find_experiment(store)
        state = store.experiment(eid, light=True)['result'].get('optimization_cycle', {})
        verify_owner(state)
        binding = {'task': '120b', 'experiment_id': eid, 'baseline': BASE,
                   'evaluation_identity': baseline['judge']['evaluation_identity']}

        def check_identity():
            if manifest_identity(current_manifest()) != identity:
                raise ValueError('E5 当前索引知识身份已变化')
            return binding

        limits = {**REQUEST_LIMITS, **baseline['judge']['execution_snapshot']['request_limits']}
        self.budget = Budget(PRIVATE, binding, check_identity, limits)
        self.budget.check_stop = self.heartbeat
        runner = E5Runner(store, runtime, self.budget, eid)
        self.owns_cycle = True
        original_save = cycle._save_state

        def progress_save(run_store, experiment_id, **updates):
            if experiment_id == eid:
                current = run_store.experiment(eid, light=True)['result'].get('optimization_cycle', {})
                if current.get('stop_request'):
                    updates.setdefault('stop_request', current['stop_request'])
            original_save(run_store, experiment_id, **updates)
            if experiment_id == eid:
                self.progress()

        def retry_state(status, **details):
            cycle._save_state(store, eid, provider_retry={'state': status, **details})

        with patch.object(paid_schedule, 'unattended_authorization', lambda _: AUTH), \
                patch.object(cycle, 'unattended_authorization', lambda _: AUTH), \
                patch.object(cycle, '_save_state', progress_save), controlled_run(self.budget.ledger), \
                provider_retry_scope(self.heartbeat, retry_state):
            paid_policy.bind_experiment(store, eid, paid_policy.current_binding())
            if state.get('status') == 'recommended' or state.get('phase') in {'final_retest', 'release', 'production_smoke'}:
                phase = self.release(runner, baseline, snapshot)
            else:
                if state.get('stop_request'):
                    raise InterruptedError('已收到停止请求，断点保留')
                self.phase_state('cycle', status='running', external_runner=True, owner_pid=os.getpid(),
                                 current_round_only=False, last_error=None)
                for candidate in store.experiment(eid, light=True)['candidates']:
                    if candidate['status'] in {'running', 'failed'}:
                        self.budget.ledger.phase = 'sandbox'
                        restore_candidate(store, runner, baseline, candidate)
                while True:
                    plan = store.job_checkpoint(eid, '120b:probe-plan')
                    if plan and not plan['complete']:
                        self.diagnosis(runner, snapshot, plan)
                    self.budget.ledger.phase = self.phase = 'cycle'
                    state = cycle.run_until_qualified(store, runtime, eid, claimed=True)
                    if '需先对当前底座做生成诊断' in (state.get('last_error') or ''):
                        plan = {'winner': state['staged_decision']['winner_id'], 'complete': False}
                        store.save_job_checkpoint(eid, '120b:probe-plan', plan)
                        self.diagnosis(runner, snapshot, plan)
                        continue
                    if state['status'] == 'recommended':
                        phase = self.release(runner, baseline, snapshot)
                    elif state['status'] in {'agent_failed', 'budget_exhausted', 'round_limit', 'blocked', 'stopped'}:
                        phase = state['status']
                    else:
                        raise ValueError(state.get('last_error') or f"优化循环停止于 {state['status']}")
                    break
            if phase in {'blocked', 'stopped'}:
                self.progress(phase, state.get('last_error'))
                return
            self.phase_state(phase, status='recommended' if phase in {'published', 'unchanged', 'release_blocked'} else phase)
            self.progress('completed')


def main():
    os.umask(0o077)
    PRIVATE.mkdir(parents=True, exist_ok=True)
    with (PRIVATE / 'run.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            run = Run()
            run.progress()
            run.execute()
        except Exception as error:
            status = 'stopped' if isinstance(error, InterruptedError) else 'blocked' if permanent_provider_error(error) else 'failed'
            message = str(error)
            if run.owns_cycle:
                cycle._save_state(run.store, run.experiment_id, status=status, last_error=message)
            run.progress(status, message)
            print(f'{status}: {message}', flush=True)
            return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
