"""Resume the task 007b Baseline reviews; all checkpoints live on the original Run."""
import fcntl
import json
from pathlib import Path

from app.main import store, ai_service
from app.evaluation import EvaluationRunner


if __name__ == '__main__':
    # One local worker prevents two invocations spending on the same checkpoint.
    with (Path(store.database_path).parent / 'task007b-review.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = EvaluationRunner(store, ai_service).review_baseline_errors('EVAL-20261101155246923769')
        print(json.dumps({'complete': result['complete'], 'cases': {
            key: {k: v for k, v in cp.get('regression_review', {}).items() if k != 'runs'}
            for key, cp in result['cases'].items()}}, ensure_ascii=False), flush=True)
