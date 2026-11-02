"""Review any saved Baseline; attach analysis without changing formal scores.

PYTHONPATH=backend python backend/scripts/task007_review.py --baseline RUN \
    --questions Q37 Q46 [--apply]
Default is a read-only preview. --apply runs the existing two-run majority review,
which generates fresh answers and judges them using the original frozen settings.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path

from app.config import load_values
from app.judge_replay import resolve_question_ids
from scripts.judge_calibration import read_baseline


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', required=True)
    parser.add_argument('--questions', nargs='+', help='Q37 Q46 或完整题号；省略时复核全部错题')
    parser.add_argument('--database', type=Path)
    parser.add_argument('--apply', action='store_true', help='开始复核，会重新生成回答并判分；默认仅预览')
    args = parser.parse_args(argv)
    database = args.database or Path(load_values().get('RAG_DEMO_DB_PATH') or Path(__file__).resolve().parents[1] / 'data/demo.db')
    source, cases = read_baseline(database, args.baseline)
    snapshot = json.loads(source['dataset_snapshot_json'])
    selected = resolve_question_ids(snapshot, args.questions) if args.questions else [c['question_id'] for c in cases if c['passed'] is False]
    if not args.apply:
        return {'dry_run': True, 'source_run_id': source['id'], 'question_ids': selected,
                'provider_calls': 0, 'planned_generation_calls': len(selected) * 2,
                'planned_judge_calls': len(selected) * 2, 'formal_scores_changed': False}
    os.environ['RAG_DEMO_DB_PATH'] = str(database.resolve())
    os.environ['RAG_SAFE_START'] = '1'
    from app.main import store, ai_service
    from app.evaluation import EvaluationRunner
    if Path(store.database_path).resolve() != database.resolve():
        raise ValueError('已加载的数据库与指定数据库不一致')
    with (Path(store.database_path).parent / 'baseline-review.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        runner = EvaluationRunner(store, ai_service)
        result = runner.review_baseline_errors(args.baseline, question_ids=selected)
    return {'source_run_id': source['id'], 'complete': result['complete'], 'formal_scores_changed': False,
            'cases': {key: {k: v for k, v in cp.get('regression_review', {}).items() if k != 'runs'}
                      for key, cp in result['cases'].items() if key in selected}}


if __name__ == '__main__':
    print(json.dumps(main(), ensure_ascii=False, indent=2), flush=True)
