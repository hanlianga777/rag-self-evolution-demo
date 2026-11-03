"""Explicit demo background follow-ups; checkpoints stay local, scores stay frozen."""
import contextvars
import csv
import fcntl
import json
import os
from pathlib import Path
import threading
from datetime import datetime, timezone

from .evaluation import EvaluationRunner
from .evaluation_stage import checkpoint_usage
from .telemetry import cost_report
from .agent_inputs import review_summary
from scripts.judge_calibration import read_baseline, calibration_plan, run_calibration, comparison_rows


def now():
    return datetime.now(timezone.utc).isoformat()


class FollowupJobs:
    def __init__(self, store, service):
        self.store, self.service = store, service
        self.root = Path(store.database_path).parent / 'followups'
        self.lock = threading.Lock()
        self.threads = {}

    def path(self, run_id, group):
        if Path(run_id).name != run_id or group not in {'review', 'max', 'high', 'low'}:
            raise ValueError('非法复核或校准标识')
        return self.root / run_id / (group + '.json')

    def start(self, run_id, group):
        read_baseline(self.store.database_path, run_id)
        path = self.path(run_id, group)
        with self.lock:
            if path.exists() or (run_id, group) in self.threads:
                return self.progress(run_id, group)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({'cases': {}, 'complete': False, '_job': {
                'status': 'starting', 'pid': os.getpid(), 'started_at': now()}}, ensure_ascii=False))
            thread = threading.Thread(target=contextvars.copy_context().run, args=(self._run, run_id, group), daemon=True)
            self.threads[run_id, group] = thread
            thread.start()
        return {'source_run_id': run_id, 'group': group, 'status': 'starting'}

    def _run(self, run_id, group):
        path = self.path(run_id, group)
        path.parent.mkdir(parents=True, exist_ok=True)
        state = json.loads(path.read_text()) if path.exists() else {'cases': {}, 'complete': False, '_job': {}}
        if hasattr(self.store, 'job_checkpoints'):
            state.setdefault('cases', {}).update({key.removeprefix('followup:' + group + ':'): value
                for key, value in self.store.job_checkpoints(run_id).items() if key.startswith('followup:' + group + ':')})
        saved_cases = {}
        state['_job'].update(status='running', started_at=state['_job'].get('started_at', now()), pid=os.getpid(), checkpoint_path=str(path))
        state['_job'].pop('error', None)
        state['_job'].pop('ended_at', None)

        def save(*_args, **_kwargs):
            state['_job']['updated_at'] = now()
            summary = state
            if hasattr(self.store, 'save_job_checkpoint'):
                for key, checkpoint in state.get('cases', {}).items():
                    encoded = json.dumps(checkpoint, ensure_ascii=False, sort_keys=True)
                    if saved_cases.get(key) != encoded:
                        self.store.save_job_checkpoint(run_id, 'followup:' + group + ':' + key, checkpoint)
                        saved_cases[key] = encoded
                summary = {key: value for key, value in state.items() if key != 'cases'}
                summary['_progress'] = self._summarize(state, run_id, group)
            temporary = path.with_suffix('.tmp')
            temporary.write_text(json.dumps(summary, ensure_ascii=False, indent=2))
            temporary.replace(path)

        with path.with_suffix('.lock').open('w') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return
            try:
                source, cases = read_baseline(self.store.database_path, run_id)
                state['_job']['model'] = source['judge'].get('model')
                runner = EvaluationRunner(self.store, self.service)
                save()
                if group == 'review':
                    def progress(review):
                        state.update(review)
                        save()
                    state['planned'] = 2 * sum(c['passed'] is False for c in cases)
                    runner.review_baseline_errors(run_id, on_progress=progress, stop_on_error=False)
                else:
                    plan = calibration_plan(source, cases, group)
                    if state.get('plan', plan) != plan:
                        raise ValueError('校准源数据或目标判分身份发生变化')
                    state['plan'] = plan
                    def progress(*_args, **_kwargs):
                        save()
                        rows = comparison_rows(source, cases, state['cases'], group)
                        with path.with_suffix('.csv').open('w', encoding='utf-8-sig', newline='') as stream:
                            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
                            writer.writeheader()
                            writer.writerows(rows)
                    run_calibration(runner, source, cases, group, state, progress)
                state['_job']['status'] = 'completed' if state['complete'] else 'failed'
            except Exception as error:
                state['_job'].update(status='failed', error=type(error).__name__ + ': ' + str(error))
            finally:
                state['_job']['ended_at'] = now()
                # Preserve the error checkpoint without re-raising the stop signal.
                save()

    def has_active(self):
        if any(thread.is_alive() for thread in self.threads.values()):
            return True
        return self.root.exists() and any(json.loads(path.read_text()).get('_job', {}).get('status') in {'running', 'starting'}
            for path in self.root.glob('*/*.json') if path.stem in {'review', 'max', 'high', 'low'})

    def recover(self):
        """Reclaim only jobs whose persisted owner exited; completed work is reused."""
        if not self.root.exists():
            return
        for path in self.root.glob('*/*.json'):
            if path.stem not in {'review', 'max', 'high', 'low'}:
                continue
            state = json.loads(path.read_text())
            job = state.get('_job', {})
            if job.get('status') not in {'running', 'starting'}:
                continue
            pid = job.get('pid')
            if type(pid) is int and pid > 0 and pid != os.getpid():
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    pass
                except PermissionError:
                    continue
                else:
                    continue
            key = (path.parent.name, path.stem)
            with self.lock:
                thread = self.threads.get(key)
                if thread and thread.is_alive():
                    continue
                thread = threading.Thread(target=self._run, args=key, daemon=True)
                self.threads[key] = thread
                thread.start()

    def progress(self, run_id, group):
        path = self.path(run_id, group)
        if not path.exists():
            return {'source_run_id': run_id, 'group': group, 'status': 'not_started', 'completed': 0}
        state = json.loads(path.read_text())
        state['_job'].setdefault('checkpoint_path', str(path))
        if '_progress' in state:
            return {**state['_progress'], **state['_job']}
        return self._summarize(state, run_id, group)

    @staticmethod
    def _summarize(state, run_id, group):
        checkpoints = list(state.get('cases', {}).values())
        stages = [stage for cp in checkpoints for stage in cp.get('regression_review', {}).get('runs', [])] if group == 'review' else checkpoints
        events = [event for stage in stages for event in checkpoint_usage(stage)]
        completed = [stage for stage in stages if type(stage.get('scored_result', {}).get('passed')) is bool]
        review_errors = [review_summary(cp).get('technical_error') for cp in checkpoints if group == 'review' and review_summary(cp).get('status') == 'technical_failure']
        return {**state['_job'], 'source_run_id': run_id, 'group': group,
                **({'status':'failed', 'error':str(review_errors[0])} if review_errors else {}),
                'planned': state.get('planned', 4) if group == 'review' else state.get('plan', {}).get('planned_questions', 50),
                'completed': len(completed), 'complete': state.get('complete', False) and not review_errors,
                'passed': sum(stage['scored_result']['passed'] for stage in completed),
                'technical_failed': sum(bool(cp.get('technical_error')) or (review_summary(cp).get('status') == 'technical_failure' if group == 'review' else type(cp.get('scored_result', {}).get('passed')) is not bool and any(a.get('status') == 'error' for a in cp.get('attempts', []))) for cp in checkpoints),
                'recorded_provider_calls': len(events), 'cost_estimation': cost_report(state['_job'].get('model'), events),
                'checkpoint_path': state.get('_job', {}).get('checkpoint_path'),
                'results': [{'question_id': key, 'passed': stage['scored_result']['passed']}
                            for key, cp in state.get('cases', {}).items()
                            for stage in (cp.get('regression_review', {}).get('runs', []) if group == 'review' else [cp])
                            if type(stage.get('scored_result', {}).get('passed')) is bool]}
