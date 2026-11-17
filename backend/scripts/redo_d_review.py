"""重做 Candidate D 的事后复盘（总指挥 2026-11-17，058 审核发现的输入缺陷）。

旧的 D 复盘有两处输入错误：
1. D 的预测写在 changes[].target_question_ids，复盘只读 predicted_fixed_question_ids，误写成"预测为空、命中 0"；
2. 复盘只拿 D 和 Baseline 比，把 Winner 原有的 candidate_k、generation_thinking 也当成 D 的改动，写成"多参数混改无法归因"。

本脚本不删旧复盘：把它原样移到 result_json.round_conclusions_history，再用修好的程序重新复盘 D（1 次 DeepSeek 调用，校验不过最多 4 次）。
不改任何 Candidate、成绩、Winner 或推荐。默认 dry-run；加 --apply 才写入并调用模型。

PYTHONPATH=backend python3 backend/scripts/redo_d_review.py --experiment-id EXP-... [--apply]
"""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

REASON = '总指挥 2026-11-17：旧 D 复盘未读到 D 的目标题预测，且把 Winner 原有改动算作 D 的改动；保留原文，重新复盘'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path)
    parser.add_argument('--experiment-id', required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args(argv)
    from app.config import load_values
    database = args.database or Path(load_values().get('RAG_DEMO_DB_PATH') or Path(__file__).resolve().parents[1] / 'data/demo.db')
    os.environ['RAG_DEMO_DB_PATH'] = str(database.resolve())
    os.environ['RAG_SAFE_START'] = '1'
    from app.main import store
    from app.agent_strategy import conclude_round, predicted_ids, winner_comparison
    experiment = store.experiment(args.experiment_id, light=True)
    if not experiment:
        raise ValueError('实验不存在')
    if experiment['result'].get('optimization_cycle', {}).get('status') == 'running':
        raise ValueError('优化批次正在运行')
    d = next((c for c in experiment['candidates'] if c['reasoning'].get('candidate_label') == 'D'), None)
    if not d or d['status'] != 'evaluated':
        raise ValueError('D 不存在或还没跑完')
    winner = next(c for c in experiment['candidates'] if c['id'] == d['reasoning'].get('winner_id'))
    old = (experiment['result'].get('round_conclusions') or {}).get('D')
    print(json.dumps({'dry_run': not args.apply, 'd': d['id'], 'winner': winner['id'],
                      'd_predictions': predicted_ids(d), 'winner_comparison': winner_comparison(store, d, winner),
                      'old_review_status': (old or {}).get('status'),
                      'old_review_plan': ((old or {}).get('review') or {}).get('plans', [None])[0]}, ensure_ascii=False, indent=2))
    if not args.apply:
        return
    with store.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        state = json.loads(db.execute('SELECT result_json FROM experiments WHERE id=?', (args.experiment_id,)).fetchone()[0])
        if (state.get('round_conclusions') or {}).get('D') is not None:
            state.setdefault('round_conclusions_history', []).append(
                {'round': 'D', 'archived_at': datetime.now(timezone.utc).isoformat(), 'reason': REASON, 'saved': state['round_conclusions'].pop('D')})
        db.execute('UPDATE experiments SET result_json=? WHERE id=?', (json.dumps(state, ensure_ascii=False), args.experiment_id))
    from app.config import load_settings
    from app.providers import DeepSeekProvider
    saved = conclude_round(store, SimpleNamespace(provider=DeepSeekProvider(load_settings())), args.experiment_id, final_d=True)
    print(json.dumps({'status': saved.get('status'), 'attempts': len(saved.get('attempts', [])),
                      'review': saved.get('review')}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
