"""补写本轮 Agent 复盘（总指挥 2026-11-18，067 发现）。

067 的实验由手动 POST /api/experiments/run 生成，结果里没有 strategy_contract；
conclude_round 只对 agent-strategy-3/4 实验写复盘，于是 A/B/C 跑完后本轮复盘被静默跳过。
arm_experiment_cycle.py 已改为补上该字段；本脚本给已跑完的实验补字段并补写当前轮复盘
（1 次 DeepSeek 调用，校验不过系统最多重试 4 次）。不改任何 Candidate、成绩或资格判定。默认 dry-run；加 --apply 才写入并调用模型。

PYTHONPATH=backend python3 backend/scripts/conclude_round_now.py --experiment-id EXP-... [--apply]
"""
import argparse
import json
import os
from pathlib import Path
from types import SimpleNamespace


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
    from app.agent_strategy import conclude_round, predicted_ids
    experiment = store.experiment(args.experiment_id, light=True)
    if not experiment:
        raise ValueError('实验不存在')
    if experiment['result'].get('optimization_cycle', {}).get('status') == 'running':
        raise ValueError('优化批次正在运行')
    abc = [c for c in experiment['candidates'] if c['reasoning'].get('candidate_label') in {'A', 'B', 'C'}]
    number = max((c['reasoning'].get('round', 1) for c in abc), default=0)
    current = [c for c in abc if c['reasoning'].get('round', 1) == number]
    if not current or any(c['status'] not in {'evaluated', 'skipped'} for c in current):
        raise ValueError('本轮还有方案没跑完')
    saved = (experiment['result'].get('round_conclusions') or {}).get(str(number))
    print(json.dumps({'dry_run': not args.apply, 'round': number,
                      'strategy_contract': experiment['result'].get('strategy_contract'),
                      'existing_review_status': (saved or {}).get('status'),
                      'candidates': {c['id']: {'status': c['status'], 'predictions': predicted_ids(c)} for c in current}},
                     ensure_ascii=False, indent=2))
    if not args.apply or (saved or {}).get('status') == 'saved':
        return
    with store.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        state = json.loads(db.execute('SELECT result_json FROM experiments WHERE id=?', (args.experiment_id,)).fetchone()[0])
        if not state.get('strategy_contract'):
            state['strategy_contract'] = 'agent-strategy-4'
            state['strategy_contract_note'] = '总指挥 2026-11-18：实验由手动接口生成、缺少分轮合同，导致本轮复盘被跳过；按分轮循环补上'
        db.execute('UPDATE experiments SET result_json=? WHERE id=?', (json.dumps(state, ensure_ascii=False), args.experiment_id))
    from app.config import load_settings
    from app.providers import DeepSeekProvider
    result = conclude_round(store, SimpleNamespace(provider=DeepSeekProvider(load_settings())), args.experiment_id)
    print(json.dumps({'status': (result or {}).get('status'), 'attempts': len((result or {}).get('attempts', [])),
                      'review': (result or {}).get('review')}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
