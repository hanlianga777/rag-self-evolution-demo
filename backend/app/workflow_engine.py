"""Run the authorized portion of an optimization workflow under its saved lease."""
import json
import os
import threading
from contextlib import nullcontext
from contextvars import copy_context
from datetime import datetime, timezone

from . import optimization_cycle as cycle, rules, task_leases, verdict
from .agent_round_contract import GenerationDiagnosisRequired, layered
from .corpus import require_knowledge_binding, require_retrieval_identity
from .evaluation import EvaluationRunner
from .evaluation_stage import perform_stage, reopen_blocked_requests
from .generation_probe import SOURCE, run_probe
from .optimization import OptimizationAgent
from .paid_policy import ALIBABA_RATES, E5_POLICY, E6_BASELINE, e6_accounting, experiment_binding, restore_paid_context
from .paid_run import REQUEST_LIMITS, current_paid_run
from .paid_schedule import wait_for_off_peak
from .policy import protected_question, require_gate_request_actor
from .providers import permanent_provider_error, provider_retry_scope

E5_BASELINE = 'EVAL-20261120213645613191'
E5_SEED = 'EXP-20261124163600086429-R1-A'
E5_AUTHORIZATION = {'enabled': True, 'actor': '用户', 'authorized_at': '2026-11-25T09:09:00-05:00',
                    'audit_note': '120b：用户 2026-11-25 09:09 授权 Gate 2 与 Gate 3，Codex 执行'}
E5_PRICES = {'deepseek-flash': {'provider': 'DeepSeek', 'input': 0.3, 'output': 1.2,
                               'max_output': 65536, 'currency': 'USD'}, **ALIBABA_RATES}
E6_AUTHORIZATION = {'enabled': True, 'actor': '用户', 'confirmed_by': '总指挥',
                    'authorized_at': '2026-11-26 09:32',
                    'audit_note': '124c：用户 11-26 09:32 全权授权，所有 Gate 由总指挥代用户确认'}
PROBE_CHANGES = [{'generation_thinking': 'low'}, {'generation_thinking': 'high'},
                 {'prompt_strategy': rules.LOOSER}, {'prompt_strategy': rules.SAFE}]
E5_SAFETY = [f'Q{number:02d}' for number in range(43, 51)]
RELEASE_PHASES = {'final_retest', 'release', 'production_smoke'}


def recover_pending(store, runtime):
    """Claim an interrupted cycle in place, retaining its saved phase and authorization."""
    with store.connection() as connection:
        ids = [row['id'] for row in connection.execute("""SELECT id FROM experiments
            WHERE json_extract(result_json,'$.optimization_cycle.status') IN ('queued','running','recovering')""")]
    for experiment_id in ids:
        with store.connection() as connection:
            connection.execute('BEGIN IMMEDIATE')
            saved = connection.execute('SELECT status,result_json FROM experiments WHERE id=?',(experiment_id,)).fetchone()
            if not saved:
                continue
            context = json.loads(saved['result_json'])
            state = context.get('optimization_cycle', {})
            if state.get('status') not in task_leases.ACTIVE_STATES or task_leases.cycle_active(connection, experiment_id, state):
                continue
            if state.get('stop_request'):
                task_leases.mark_paused(connection, 'cycle:' + experiment_id)
                state['status'] = 'stopped'
                token = None
            else:
                candidates = store.candidates(experiment_id, light=True)
                if (task_leases.agent_active(connection, experiment_id, context, legacy_generating=saved['status'] == 'generating')
                        or task_leases.active(connection, 'composite:' + experiment_id)
                        or any(cycle.candidate_occupied(connection, candidate) for candidate in candidates)):
                    continue
                token = task_leases.claim(connection, 'cycle:' + experiment_id, recovering=True)
                if state.get('external_runner') and not state.get('workflow_scope'):
                    state['legacy_external_runner'] = True
                state.update(status='recovering', external_runner=False, owner_pid=os.getpid())
                if state.get('workflow_scope'):
                    state.setdefault('workflow_audit', []).append({
                        'at': datetime.now(timezone.utc).isoformat(), 'status': 'recovering', 'phase': state.get('phase'),
                    })
                state.pop('worker_thread', None)
            connection.execute('UPDATE experiments SET result_json=? WHERE id=?', (json.dumps(context, ensure_ascii=False), experiment_id))
        if token:
            threading.Thread(target=cycle.run_until_qualified, args=(store,runtime,experiment_id),
                             kwargs={'claimed':True, 'lease_token':token}, daemon=True).start()


class WorkflowEngine:
    def __init__(self, store, runtime, experiment_id):
        self.store, self.runtime, self.id = store, runtime, experiment_id

    def experiment(self):
        return self.store.experiment(self.id, light=True)

    def state(self):
        return cycle.read_cycle_state(self.store, self.id)

    def save(self, **updates):
        cycle._save_state(self.store, self.id, **updates)

    def check_stop(self):
        cycle.check_cycle_stop(self.store, self.id)

    def start(self, target='cycle', *, candidate_id=None, background=True):
        scope = {'target': target, 'entry': 'api'}
        if candidate_id:
            scope['candidate_id'] = candidate_id
        state = cycle.claim_cycle(self.store, self.id, current_round_only=target == 'current_round',
                                  workflow_scope=scope)
        token = cycle.take_cycle_claim(self.store, self.id)

        def execute():
            return cycle.run_until_qualified(self.store, self.runtime, self.id, lease_token=token)

        if background:
            threading.Thread(target=copy_context().run, args=(execute,), daemon=True).start()
            return state
        return execute()

    def is_e5(self, experiment):
        return (experiment['baseline_run_id'] == E5_BASELINE and experiment['result'].get('mode') == 'initial'
                and any(c['id'] == self.id + '-R1-A' and c['reasoning'].get('source_candidate_id') == E5_SEED
                        for c in experiment['candidates']))

    def release_authorization(self):
        ledger = current_paid_run()
        if not ledger or (ledger.request_policy or {}).get('kind') != E5_POLICY:
            return None
        experiment = self.experiment()
        identity = ledger.identity
        if not isinstance(identity, dict):
            return None
        if e6_accounting(ledger):
            if (experiment['baseline_run_id'] == identity.get('baseline') == E6_BASELINE
                    and identity.get('experiment_id') == self.id and experiment['result'].get('mode') == 'initial'
                    and identity.get('release_authorization') == E6_AUTHORIZATION
                    and ledger.request_policy.get('budget_usd') == 5.0
                    and not any(c['reasoning'].get('source_candidate_id') for c in experiment['candidates'])
                    and not experiment['result']['parameter_effect_ledger'].get('historical')):
                return E6_AUTHORIZATION.copy()
            return None
        if not (self.is_e5(experiment) and identity.get('task') == '120b'
                and identity.get('experiment_id') == self.id and identity.get('baseline') == E5_BASELINE
                and ledger.request_policy.get('budget_usd') == 3.0):
            return None
        return E5_AUTHORIZATION.copy()

    def require_e5_contract(self):
        if not self.release_authorization():
            raise ValueError('E5 的冻结预算、实验或种子身份不匹配')
        baseline = self.store.require_current_baseline(E5_BASELINE)
        frozen = json.loads(baseline['dataset_snapshot_json'])
        ledger = current_paid_run()
        limits = {**REQUEST_LIMITS, **baseline['judge']['execution_snapshot']['request_limits']}
        if (ledger.prices != E5_PRICES or ledger.output_limits != limits
                or ledger.request_policy.get('ledger_directory') != str(ledger.path.parent)
                or not self.runtime.live_enabled or self.runtime.model != baseline['judge']['model']
                or len(verdict.final_verdicts(baseline['id'], store=self.store)) != 50
                or baseline['config'].get('knowledge_identity') != frozen['corpus_fingerprint']
                or self.runtime.corpus.index_info()['knowledge_identity'] != frozen['corpus_fingerprint']):
            raise ValueError('E5 的冻结题卷、模型、计价或请求上限不匹配')
        from .optimization import load_retrieval_preview, require_retrieval_preview

        seed = self.store.candidate(E5_SEED)
        if not seed:
            raise ValueError('E5 缺少原引用方案，请核对源 Candidate')
        preview = load_retrieval_preview(self.store, baseline['id'], foundation=frozen['corpus_fingerprint'])
        require_retrieval_preview(preview, {key: seed['config'][key] for key in ('candidate_k', 'top_k')})

    def retry_state(self, status, **details):
        if status in {'retry_wait', 'recovering', 'recovered', 'blocked'}:
            self.save(provider_retry={'state': status, **details})

    def wait_for_price(self):
        wait_for_off_peak(self.store, 'cycle:' + self.id,
                          lambda pause: self.save(price_pause=pause), self.check_stop)

    def run(self):
        """Dispatch from persisted scope. Both start and lease recovery use this method."""
        experiment = self.experiment()
        state = experiment['result'].get('optimization_cycle') or {}
        scope = state.get('workflow_scope') or {}
        reopen = state.get('reopen_paid_ledger', False)
        try:
            self.check_stop()
            provider = self.runtime.provider if getattr(self.runtime, 'live_enabled', True) else None
            if self.is_e5(experiment) and not experiment['result'].get('paid_run'):
                legacy = self.store.database_path.parent / 'task120b' / '120b.ledger.json'
                if not legacy.is_file() or json.loads(legacy.read_text()).get('identity', {}).get('experiment_id') != self.id:
                    raise ValueError('E5 缺少原 120b 费用授权，请核对冻结账本')
            binding = experiment_binding(self.store, self.id, provider)
            with provider_retry_scope(self.check_stop, self.retry_state), (
                    restore_paid_context(self.store, binding, reopen=reopen) if binding else nullcontext()):
                if self.is_e5(experiment):
                    self.require_e5_contract()
                if e6_accounting(current_paid_run()):
                    self.require_e6_contract()
                if reopen:
                    self.save(reopen_paid_ledger=False, resume_probe_requests=True)
                if not scope and state.get('legacy_external_runner') and self.release_authorization():
                    scope = {'target': 'release', 'entry': 'legacy_recovery'}
                    self.save(workflow_scope=scope)
                target = scope.get('target', 'cycle')
                if target == 'next_round':
                    # A worker can die after saving the proposals but before marking the workflow complete.
                    if not any(c['reasoning'].get('round') == scope['round'] and c['status'] == 'generated'
                               for c in experiment['candidates']) and (
                            experiment['result'].get('decision_stop') or {}).get('round') != scope['round']:
                        self.generate_next(resume_blocked=reopen)
                    self.save(status='completed', phase='analysis', last_error=None, provider_retry=None)
                elif target == 'candidate':
                    self.run_candidate(scope['candidate_id'])
                elif target == 'release' and state.get('phase') in RELEASE_PHASES:
                    self.release(resume_blocked=reopen)
                else:
                    result = cycle._run_until_qualified(self.store, self.runtime, self.id)
                    if target == 'release' and result['status'] == 'recommended':
                        self.release(resume_blocked=reopen)
                    else:
                        return result
        except task_leases.LeaseLost:
            raise
        except InterruptedError as error:
            self.save(status='stopped', last_error=str(error))
        except Exception as error:
            if not isinstance(error, (ValueError, OSError)) and not permanent_provider_error(error):
                self.save(status='failed', last_error=str(error))
                return self.state()
            self.save(status='blocked', last_error=str(error),
                      provider_retry={'state': 'blocked', 'error': str(error),
                                      'resume_hint': '核对所列原因后，从原实验断点继续'})
        return self.state()

    def require_e6_contract(self):
        from .evaluation_contract import evaluation_identity, policy_current

        if not self.release_authorization():
            raise ValueError('E6 的实验、Baseline 或授权账本身份不匹配')
        baseline = self.store.require_current_baseline(E6_BASELINE)
        frozen = json.loads(baseline['dataset_snapshot_json'])
        judge = baseline['judge']
        ledger = current_paid_run()
        if (frozen['id'] != ledger.identity.get('snapshot_id') or len(frozen['question_ids']) != 50
                or not policy_current(judge) or judge['evaluation_identity'] != evaluation_identity(frozen, judge)
                or not self.runtime.live_enabled or self.runtime.model != judge['model']
                or not baseline['config'].get('knowledge_identity')
                or baseline['config'].get('knowledge_identity') != frozen['corpus_fingerprint']
                or self.runtime.corpus.index_info()['knowledge_identity'] != frozen['corpus_fingerprint']
                or ledger.prices != E5_PRICES or ledger.output_limits != {**REQUEST_LIMITS, **judge['execution_snapshot']['request_limits']}
                or ledger.request_policy.get('ledger_directory') != str(ledger.path.parent)):
            raise ValueError('E6 的冻结题卷、Judge、知识库、模型或计价不匹配')
        verdict.require_baseline(self.store, baseline)

    def run_candidate(self, candidate_id):
        runner = EvaluationRunner(self.store, self.runtime)
        candidate = self.store.candidate(candidate_id)
        self.save(status='running', phase='sandbox', active_candidate=candidate_id)
        if candidate['status'] == 'running':
            runner.recover_run(candidate['result']['evaluation_run_id'])
        elif candidate['status'] != 'evaluated':
            runner.run_candidate(candidate_id, automatic=True, manual_resume=True)
        self.check_stop()
        candidate = self.store.candidate(candidate_id)
        if candidate['status'] != 'evaluated':
            raise ValueError(candidate['result'].get('error') or 'Sandbox 未完成，请核对续跑断点')
        self.save(status='completed', phase='sandbox', active_candidate=None, last_error=None)

    def generate_composite(self):
        from .agent_planning import enabled

        experiment = self.experiment()
        if experiment and enabled(experiment['result']):
            return self.store.create_composite(self.id, self.runtime.provider, workflow=self)
        return self.store.create_composite(self.id, self.runtime.provider)

    def directed_planning(self, number, base_id, base_run_id):
        from .agent_planning import DirectedPlanning

        return DirectedPlanning(self, number, base_id, base_run_id)

    def generate_next(self, agent=None, *, resume_blocked=False):
        experiment = self.experiment()
        baseline_id = experiment['baseline_run_id']
        agent = agent or OptimizationAgent(self.store, self.runtime.provider, runtime=self.runtime)
        from .agent_planning import enabled

        if enabled(experiment['result']) or not layered(experiment['result']):
            return agent.generate(baseline_id, experiment_id=self.id)
        e5 = self.is_e5(experiment)
        key = '120b:probe-plan' if e5 else 'workflow:probe-plan'
        pending = self.store.job_checkpoint(self.id, key)
        if pending and not pending.get('complete'):
            self.diagnose(pending, key, resume_blocked=resume_blocked or self.state().get('resume_probe_requests'))
        self.save(status='running', phase='analysis', provider_retry=None)
        try:
            return agent.generate(baseline_id, experiment_id=self.id)
        except GenerationDiagnosisRequired as required:
            plan = {'base_id': required.base_id, 'base_run_id': required.run_id,
                    'question_ids': required.question_ids, 'complete': False}
            self.store.save_job_checkpoint(self.id, key, plan)
            self.diagnose(plan, key, resume_blocked=resume_blocked)
            self.save(status='running', phase='analysis', provider_retry=None)
            return agent.generate(baseline_id, experiment_id=self.id)

    def diagnose(self, plan, key, *, resume_blocked=False):
        e5 = self.is_e5(self.experiment())
        base_id = plan.get('base_id', plan.get('winner') or 'Baseline')
        candidate = self.store.candidate(base_id) if base_id != 'Baseline' else None
        run_id = (candidate['result']['evaluation_run_id'] if candidate else self.experiment()['baseline_run_id'])
        if plan.get('base_run_id', run_id) != run_id:
            raise ValueError('生成诊断底座身份已变化，请核对已保存断点')
        run = self.store.evaluation_run(run_id)
        snapshot = json.loads(run['dataset_snapshot_json'])
        selected = set(plan.get('question_ids', []))
        if e5:
            from .judge_replay import resolve_question_ids

            selected.update(resolve_question_ids(snapshot, ['Q07', 'Q17', 'Q20', 'Q21', 'Q27', 'Q29', *E5_SAFETY]))
            selected.update(q for q, passed in verdict.final_verdicts(run_id, store=self.store).items() if not passed)
        if not selected or not selected.issubset(snapshot['question_ids']):
            raise ValueError('生成诊断题号和冻结题卷不一致')
        self.save(status='running', phase='generation_probe',
                  next_action='系统将自动先做生成诊断，完成后继续生成本轮方案')
        runner = CheckpointedRetest(self, '120b:' if e5 else 'workflow:', resume_blocked=resume_blocked)
        entries = self.experiment()['result']['parameter_effect_ledger']['current']
        existing = {(row['question_id'], rules.canonical_hash(row['changes'])): row['status']
                    for row in entries if row['source'] == SOURCE and row['base_id'] == base_id}
        for changes in PROBE_CHANGES:
            for question in snapshot['question_ids']:
                if question not in selected:
                    continue
                self.check_stop()
                saved = existing.get((question, rules.canonical_hash(changes)))
                if saved == '未知':
                    raise ValueError(f'生成诊断结果未知，请核对原样本：{question} {changes}')
                if saved is None:
                    run_probe(self.store, runner, self.id, run_id, [changes], [question], base_key=base_id)
        self.store.save_job_checkpoint(self.id, key, {**plan, 'complete': True})
        self.save(next_action=None, resume_probe_requests=False)

    def release(self, *, resume_blocked=False):
        from .composite import pipeline_config
        from .release_view import release_review_view

        self.check_stop()
        experiment = self.experiment()
        baseline = self.store.require_current_baseline(experiment['baseline_run_id'])
        snapshot = json.loads(baseline['dataset_snapshot_json'])
        rec = (self.store.recommendation(self.id) or {}).get('result', {})
        if rec.get('status') != 'Recommended':
            raise ValueError('最终复测缺少正式推荐，请先完成 Gate 2 和 D 决策')
        cid = rec.get('recommended_candidate')
        if not cid:
            self.save(status='completed', phase='unchanged', last_error='暂无有增量收益的推荐，保留当前线上版本')
            return
        candidate = self.store.candidate(cid)
        if not candidate or candidate['experiment_id'] != self.id:
            raise ValueError('正式推荐与本实验的 Candidate 不一致')
        run_id = candidate['result']['evaluation_run_id']
        e5 = self.is_e5(experiment)
        prefix = '120b:' if e5 else 'workflow:'
        receipt_key = prefix + 'release'
        receipt = self.store.job_checkpoint(self.id, receipt_key) or {}
        active = self.store.active_production()
        if not active:
            raise ValueError('发布前需要可核对的当前线上版本和回滚点')
        if receipt.get('result') == 'unchanged':
            if receipt['version'] != active['id'] or receipt['candidate'] != cid:
                raise ValueError('线上版本或推荐已经变化，请重新核对发布依据')
            self.save(status='completed', phase='unchanged', last_error=receipt.get('reason'))
            return
        if receipt.get('candidate') == cid and active['snapshot'].get('candidate_id') == cid:
            self.verify_production(active, candidate, snapshot, receipt, prefix, resume_blocked=resume_blocked)
            return
        if receipt.get('result') == 'published' or receipt and receipt.get('candidate') != cid:
            raise ValueError('发布记录与当前线上版本或推荐不一致，请核对原记录')
        if error := self.store.release_gate_error(candidate):
            raise ValueError(error)
        failed_checks = [row['label'] for row in release_review_view(self.store, cid)['checks'] if row['ok'] is not True]
        if failed_checks:
            raise ValueError('Gate 3 发布检查未通过：' + '、'.join(failed_checks))
        before, after, summary = self.final_retest(experiment, baseline, candidate, snapshot, prefix,
                                                   resume_blocked=resume_blocked)
        if any(row['risk'] is not False or row['unknown'] for group in summary.values() for row in group.values()):
            self.save(status='blocked', phase='final_retest', last_error='最终复测有风险或未知结果，请核对保存样本')
            return
        # Saved qualification and the independent comparison must still show an improvement.
        if not before < after:
            reason = '最终独立复测未确认新增修复且无回退，保留当前线上版本'
        else:
            source = self.store.evaluation_run(run_id, light=True)
            same_config = (pipeline_config(active['config']) == pipeline_config(candidate['config'])
                           and active['snapshot'].get('knowledge_identity') == source['config'].get('knowledge_identity')
                           and active['snapshot'].get('generation_model') == source['judge']['model'])
            reason = '推荐配置与当前线上版本一致' if same_config else None
        if reason:
            self.store.save_job_checkpoint(self.id, receipt_key,
                {'result': 'unchanged', 'version': active['id'], 'candidate': cid, 'reason': reason})
            self.save(status='completed', phase='unchanged', last_error=reason)
            return
        authorization = self.release_authorization()
        if not authorization:
            self.save(status='awaiting_release_approval', phase='before_release',
                      last_error='最终复测完成，请用户核对 Gate 3 后确认发布')
            return

        self.save(status='running', phase='release')
        self.check_stop()
        require_gate_request_actor('gate3', authorization['actor'])
        prepared = {'candidate': cid, 'rollback': active['id'], 'rollback_index': self.rollback_index(active)}
        if e6_accounting(current_paid_run()):
            prepared['rollback_rehearsal'] = self.rehearse_rollback(active, candidate)
            prepared['authorization'] = authorization
        if receipt and receipt != prepared:
            raise ValueError('发布准备记录与当前线上版本不同，请核对回滚点')
        self.store.save_job_checkpoint(self.id, receipt_key, prepared)
        published = self.store.publish_candidate(cid, authorization['actor'], workflow_release=(
            prepared['rollback'], run_id, authorization['authorized_at']))
        self.verify_production(published, candidate, snapshot, prepared, prefix, resume_blocked=resume_blocked)

    def rehearse_rollback(self, active, candidate):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from .governance import GovernanceStore

        simulation = 'rollback-rehearsal'
        with TemporaryDirectory(prefix='rag-rollback-rehearsal-') as directory:
            database = Path(directory) / 'rehearsal.db'
            if database.resolve() == self.store.database_path.resolve():
                raise ValueError('回滚演练必须使用独立临时库')
            isolated = GovernanceStore(database)
            with isolated.connection() as db:
                db.execute('DELETE FROM production_versions')  # Discard disposable bootstrap row.
                db.executemany('INSERT INTO production_versions(id,status,config_json,created_at,snapshot_json) '
                               'VALUES (?,?,?,?,?)', [
                    (active['id'], 'archived', json.dumps(active['config']), active['created_at'], json.dumps(active['snapshot'])),
                    (simulation, 'active', json.dumps(candidate['config']), active['created_at'], '{}'),
                ])
            restored = isolated.rollback_to(active['id'], 'Codex')
            with isolated.connection() as db:
                recorded = db.execute('SELECT 1 FROM rollback_history WHERE from_version_id=? AND to_version_id=?',
                                      (simulation, active['id'])).fetchone()
            if not restored or restored['id'] != active['id'] or restored['config'] != active['config'] or not recorded:
                raise ValueError('临时数据库回滚演练未恢复原配置或缺少回滚记录')
        return {'database': 'explicit_temporary_database', 'restored_version': active['id'], 'status': 'passed'}

    def final_retest(self, experiment, baseline, candidate, snapshot, prefix, *, resume_blocked):
        from .judge_replay import resolve_question_ids

        run_id = candidate['result']['evaluation_run_id']
        before, after = (verdict.final_verdicts(source, store=self.store) for source in (baseline['id'], run_id))
        if not before.keys() == after.keys() == set(snapshot['question_ids']):
            raise ValueError('最终复测前的逐题最终判定不完整')
        if candidate['reasoning'].get('candidate_label') == 'D':
            winner_id = (experiment['result'].get('report_confirmation') or {}).get('winner_id')
            winner = self.store.candidate(winner_id) if winner_id else None
            winner_final = verdict.final_verdicts(winner['result']['evaluation_run_id'], store=self.store) if winner else {}
            if winner_final.keys() != after.keys() or not (
                    {q for q, passed in winner_final.items() if passed} < {q for q, passed in after.items() if passed}):
                raise ValueError('推荐 D 缺少相对 Winner 的非回退和新增修复证据')

        selected = {q for q in before if not before[q] or not after[q]}
        selected.update(q['id'] for q in snapshot['questions'] if protected_question(q, q))
        if prefix == '120b:':
            selected.update(resolve_question_ids(snapshot, E5_SAFETY))
        self.save(status='running', phase='final_retest')
        runner = CheckpointedRetest(self, prefix, resume_blocked=resume_blocked)
        summary = {}
        for label, source in [('baseline', baseline['id']), ('recommendation', run_id)]:
            summary[label] = {}
            for question in snapshot['question_ids']:
                if question in selected:
                    self.check_stop()
                    row, = runner.diagnostic_retest(source, [question])['questions']
                    summary[label][row['display_question_id']] = {key: row[key] for key in ('passed', 'unknown', 'risk')}
        self.store.save_job_checkpoint(self.id, prefix + 'final-retest',
            {'baseline': baseline['id'], 'candidate': candidate['id'], 'run_id': run_id, 'summary': summary})
        votes = [{q for q, row in summary[label].items() if row['passed'] >= 2}
                 for label in ('baseline', 'recommendation')]
        return votes[0], votes[1], summary

    def rollback_index(self, version):
        from .corpus import INDEX_DIR, CorpusStore
        from .knowledge_pipeline import index_for_config

        snapshot = version['snapshot']
        path = index_for_config(INDEX_DIR, {**version['config'], 'knowledge_identity': snapshot.get('knowledge_identity')})
        if not (path / 'manifest.json').is_file() or not (path / 'faiss.index').is_file():
            raise ValueError('回滚版本缺少索引文件，请恢复原索引')
        index = CorpusStore(path).index_info()
        if (index['embedding_model'] != snapshot.get('embedding_model')
                or index['knowledge_identity'] != snapshot.get('knowledge_identity')
                or snapshot.get('generation_model') != self.runtime.model):
            raise ValueError('回滚版本的索引或模型与当前环境不兼容')
        return str(path.resolve())

    def verify_production(self, published, candidate, snapshot, receipt, prefix, *, resume_blocked):
        bound = require_knowledge_binding(published['snapshot'], snapshot.get('corpus_fingerprint'))
        authorization = self.release_authorization()
        audit = published['snapshot'].get('human_release', {})
        at = (authorization or {}).get('authorized_at')
        if (not authorization or published['config'] != candidate['config']
                or published['previous_version_id'] != receipt.get('rollback')
                or audit.get('authorizer') != authorization['actor'] or audit.get('executed_by') != 'Codex'
                or audit.get('authorized_at') not in {at, '2026-11-25 09:09'}):
            raise ValueError('已发布版本或审计字段与准备记录不同，请核对线上版本')
        prior = next((v for v in self.store.production_versions() if v['id'] == receipt['rollback']), None)
        if not prior or prior['status'] != 'archived' or self.rollback_index(prior) != receipt['rollback_index']:
            raise ValueError('发布后回滚点核验失败，请检查归档版本和索引')
        self.store.save_job_checkpoint(self.id, prefix + 'release',
            {**receipt, 'result': 'published', 'version': published['id'], 'audit': audit})
        self.save(status='running', phase='production_smoke')
        key = prefix + 'production-smoke:' + published['id']
        saved = self.store.job_checkpoint(self.id, key) or {'attempts': []}
        if 'result' not in saved:
            self.wait_for_price()
            if resume_blocked:
                reopen_blocked_requests(saved)
            from .request_reuse import bypass_reuse

            question = next((q['question'] for q in snapshot['questions'] if
                             (q.get('coverage_slot') or q.get('display_id')) == 'Q06'), snapshot['questions'][0]['question'])

            def persist(state, **details):
                self.store.save_job_checkpoint(self.id, key, saved)
                self.retry_state(state, **details)

            with bypass_reuse():
                response = perform_stage(saved, 'generation', lambda: self.runtime.baseline_preview(question),
                    key, automatic=False, check_stop=self.check_stop, on_state=persist)
            require_retrieval_identity(response.get('retrieval_trace'), bound)
            if (response['version'] != published['id'] or response['mode'] != 'live'
                    or not response['answer'] or not response['evidence']
                    or self.store.active_production()['id'] != published['id']):
                raise ValueError('版本已发布，正式问答主链路核验失败，请检查线上版本或回滚')
            saved['result'] = {'version': response['version'], 'mode': response['mode'], 'evidence': len(response['evidence'])}
            self.store.save_job_checkpoint(self.id, key, saved)
        self.save(status='completed', phase='published', last_error=None, provider_retry=None)


class CheckpointedRetest(EvaluationRunner):
    """Reuse completed samples (including the original 120b checkpoints)."""
    def __init__(self, engine, prefix, *, resume_blocked=False):
        super().__init__(engine.store, engine.runtime)
        self.engine = engine
        self.prefix = prefix
        self.resume_blocked = resume_blocked

    def diagnostic_retest(self, run_id, question_ids, *, repetitions=3, config_override=None):
        identity = [run_id, question_ids, repetitions, config_override]
        key = self.prefix + 'diagnostic:' + rules.canonical_hash(identity)
        saved = self.store.job_checkpoint(self.engine.id, key) or {}
        if 'result' in saved:
            return saved['result']
        self.engine.wait_for_price()
        checkpoints = saved.setdefault('trials', {})
        if self.resume_blocked:
            for checkpoint in checkpoints.values():
                if isinstance(checkpoint, dict):
                    reopen_blocked_requests(checkpoint)

        def persist():
            self.store.save_job_checkpoint(self.engine.id, key, saved)

        result = super().diagnostic_retest(run_id, question_ids, repetitions=repetitions,
                                          config_override=config_override,
                                          resume=(checkpoints, persist, self.engine.check_stop))
        saved['result'] = result
        persist()
        return result
