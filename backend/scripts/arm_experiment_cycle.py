"""给已跑完第 1 轮的手动实验接上 staged-v1 自动循环（用户 2026-11-17 07:07 授权：接着跑第 2、3 轮）。

只改实验的 result_json 三项，不调用任何模型：
- round_policy 使用规则总表的分阶段停止规则；可通过 --max-rounds 执行已授权的轮次上限；
- causal_evidence = True（下一轮 Agent 拿到逐题对比 case_comparisons，并按逐题证据写本轮结论）；
- 无人值守授权记为"用户"（凑够合格方案时可按规则确认 Winner、生成并跑 D；发布仍需用户）。
默认 dry-run；加 --apply 才写入。写入后由 POST /api/experiments/{id}/run-cycle 启动。

PYTHONPATH=backend python3 backend/scripts/arm_experiment_cycle.py --experiment-id EXP-... [--max-rounds 3] [--apply]
"""
import argparse
import json
import os
from pathlib import Path

AUDIT_NOTE = '用户 2026-11-18 17:52 授权：先查清证据疑点，再跑第 2 轮 A/B/C，跑完即停；不做 D，不发布'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path)
    parser.add_argument('--experiment-id', required=True)
    from app import rules
    parser.add_argument('--max-rounds', type=int, default=rules.AGENT['max_rounds'])
    parser.add_argument('--run-to-round', type=int, help='用户指定先跑到第 N 轮：之前各轮不转入 D，跑完第 N 轮停下')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args(argv)
    from app.config import load_values
    database = args.database or Path(load_values().get('RAG_DEMO_DB_PATH') or Path(__file__).resolve().parents[1] / 'data/demo.db')
    os.environ['RAG_DEMO_DB_PATH'] = str(database.resolve())
    os.environ['RAG_SAFE_START'] = '1'
    from app.main import store
    from app.optimization_cycle import STAGED_RULE
    from app.paid_schedule import set_unattended_authorization, unattended_authorization
    experiment = store.experiment(args.experiment_id, light=True)
    if not experiment:
        raise ValueError('实验不存在')
    store.require_current_baseline(experiment['baseline_run_id'])
    if experiment['result'].get('optimization_cycle', {}).get('status') == 'running':
        raise ValueError('优化批次正在运行')
    if experiment['status'] == 'generating' or any(c['status'] in {'queued', 'running'} for c in experiment['candidates']):
        raise ValueError('还有正在生成或正在跑的方案，等它结束再接循环')  # 已生成未运行（generated）的方案由循环接着跑
    policy = {'mode': 'full_rounds', 'max_rounds': args.max_rounds, 'stop_rule': STAGED_RULE}
    if args.run_to_round:
        policy.update(max_rounds=max(args.max_rounds, args.run_to_round), user_run_to_round=args.run_to_round)
    plan = {'experiment_id': args.experiment_id, 'baseline_run_id': experiment['baseline_run_id'],
            'round_policy': {'old': experiment['result'].get('round_policy'), 'new': policy},
            'causal_evidence': {'old': experiment['result'].get('causal_evidence'), 'new': True},
            'strategy_contract': {'old': experiment['result'].get('strategy_contract'), 'new': experiment['result'].get('strategy_contract') or 'agent-strategy-4'},
            'unattended_authorization': unattended_authorization(store),
            'candidates': [{'id': c['id'], 'status': c['status'], 'qualified': c['result'].get('qualification', {}).get('qualified')} for c in experiment['candidates']],
            'budget': experiment.get('evaluation_budget')}
    if not args.apply:
        return {'dry_run': True, **plan}
    with store.connection() as connection:
        connection.execute('BEGIN IMMEDIATE')
        row = connection.execute('SELECT result_json FROM experiments WHERE id=?', (args.experiment_id,)).fetchone()
        result = json.loads(row['result_json'])
        # 2026-11-18：手动 POST /api/experiments/run 生成的实验没有 strategy_contract，本轮复盘与 D 的组合规则都会被跳过；分轮循环一律补上
        result.setdefault('strategy_contract', 'agent-strategy-4')
        result.update(round_policy=policy, causal_evidence=True,
                      cycle_arming={'audit_note': AUDIT_NOTE, 'max_rounds': args.max_rounds})
        connection.execute('UPDATE experiments SET result_json=? WHERE id=?', (json.dumps(result, ensure_ascii=False), args.experiment_id))
    if not unattended_authorization(store).get('enabled'):
        set_unattended_authorization(store, True, '用户', audit_note=AUDIT_NOTE)
    after = store.experiment(args.experiment_id, light=True)['result']
    return {'armed': {'round_policy': after.get('round_policy'), 'causal_evidence': after.get('causal_evidence'), 'strategy_contract': after.get('strategy_contract')},
            'unattended_authorization': unattended_authorization(store)}


if __name__ == '__main__':
    print(json.dumps(main(), ensure_ascii=False, indent=2, default=str), flush=True)
