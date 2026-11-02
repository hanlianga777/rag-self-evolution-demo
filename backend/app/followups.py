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
            thread = threading.Thread(target=contextvars.copy_context().run, args=(self._run, run_id, group), daemon=True)
            self.threads[run_id, group] = thread
            thread.start()
        return {'source_run_id': run_id, 'group': group, 'status': 'starting'}

    def _run(self, run_id, group):
        path = self.path(run_id, group)
        path.parent.mkdir(parents=True, exist_ok=True)
        state = {'cases': {}, 'complete': False, '_job': {'status': 'running', 'started_at': now(), 'pid': os.getpid()}}

        def save(*_args, **_kwargs):
            state['_job']['updated_at'] = now()
            temporary = path.with_suffix('.tmp')
            temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2))
            temporary.replace(path)
            checkpoints = list(state['cases'].values())
            stages = [stage for cp in checkpoints for stage in cp.get('regression_review', {}).get('runs', [])] if group == 'review' else checkpoints
            errors = [cp['technical_error'] for cp in checkpoints if cp.get('technical_error')]
            errors += [attempt.get('error', attempt.get('error_type')) for stage in stages for attempt in stage.get('attempts', []) if attempt.get('status') == 'error']
            if errors:
                raise RuntimeError(str(errors[0]))

        with path.with_suffix('.lock').open('w') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                source, cases = read_baseline(self.store.database_path, run_id)
                state['_job']['model'] = source['judge'].get('model')
                runner = EvaluationRunner(self.store, self.service)
                save()
                if group == 'review':
                    def progress(review):
                        state.update(review)
                        save()
                    state['planned'] = 2 * sum(c['passed'] is False for c in cases)
                    runner.review_baseline_errors(run_id, on_progress=progress, stop_on_error=True)
                else:
                    state['plan'] = calibration_plan(source, cases, group)
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
                temporary = path.with_suffix('.tmp')
                temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2))
                temporary.replace(path)

    def progress(self, run_id, group):
        path = self.path(run_id, group)
        if not path.exists():
            return {'source_run_id': run_id, 'group': group, 'status': 'not_started', 'completed': 0}
        state = json.loads(path.read_text())
        checkpoints = list(state.get('cases', {}).values())
        stages = [stage for cp in checkpoints for stage in cp.get('regression_review', {}).get('runs', [])] if group == 'review' else checkpoints
        events = [event for stage in stages for event in checkpoint_usage(stage)]
        completed = [stage for stage in stages if type(stage.get('scored_result', {}).get('passed')) is bool]
        return {**state['_job'], 'source_run_id': run_id, 'group': group,
                'planned': state.get('planned', 4) if group == 'review' else state.get('plan', {}).get('planned_questions', 50),
                'completed': len(completed), 'complete': state.get('complete', False),
                'passed': sum(stage['scored_result']['passed'] for stage in completed),
                'technical_failed': sum(bool(cp.get('technical_error')) or any(a.get('status') == 'error' for stage in (cp.get('regression_review', {}).get('runs', []) if group == 'review' else [cp]) for a in stage.get('attempts', [])) for cp in checkpoints),
                'recorded_provider_calls': len(events), 'cost_estimation': cost_report(state['_job'].get('model'), events),
                'checkpoint_path': str(path),
                'results': [{'question_id': key, 'passed': stage['scored_result']['passed']}
                            for key, cp in state.get('cases', {}).items()
                            for stage in (cp.get('regression_review', {}).get('runs', []) if group == 'review' else [cp])
                            if type(stage.get('scored_result', {}).get('passed')) is bool]}
