"""把已完成的 Baseline 绑定到 Agent 串联（staged-v1，规则总表）。

只做三件事：核对 Baseline 完整、确保无人值守授权为用户、用 round_policy staged-v1 和 causal_evidence 绑定串联。
真正启动 Agent 的是后端已有的 5 秒监控（baseline_chain.advance_chain），本脚本不调用任何模型。
默认 dry-run；加 --apply 才写入。

PYTHONPATH=backend python backend/scripts/arm_agent_chain.py --baseline-id EVAL-... [--apply]
"""
import argparse
import json
import os
from pathlib import Path

ROUND_POLICY = {'mode': 'full_rounds', 'max_rounds': 4, 'stop_rule': 'staged-v1'}
AUDIT_NOTE = '用户 2026-11-16 预先授权'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path)
    parser.add_argument('--baseline-id', required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args(argv)
    from app.config import load_values
    database = args.database or Path(load_values().get('RAG_DEMO_DB_PATH') or Path(__file__).resolve().parents[1] / 'data/demo.db')
    os.environ['RAG_DEMO_DB_PATH'] = str(database.resolve())
    os.environ['RAG_SAFE_START'] = '1'
    from app.main import store
    from app.baseline_chain import arm_chain, chain_status
    from app.paid_schedule import set_unattended_authorization, unattended_authorization
    run = store.evaluation_run(args.baseline_id, light=True)
    if not run or run['config'].get('run_target') != 'baseline':
        raise ValueError('不是 Baseline 评测')
    result = run.get('result') or {}
    if run['status'] != 'completed' or result.get('evaluation_complete') is not True or result.get('technical_failed') != 0:
        raise ValueError(f"Baseline 未完整结束：status={run['status']} complete={result.get('evaluation_complete')} technical_failed={result.get('technical_failed')}")
    latest = store.dataset_snapshots()[0]
    snapshot_id = latest.get('id') or latest.get('snapshot_id')
    if run['dataset_version_id'] != snapshot_id:
        raise ValueError(f"Baseline 题卷 {run['dataset_version_id']} 不是最新冻结快照 {snapshot_id}")
    plan = {'baseline_id': args.baseline_id, 'snapshot_id': snapshot_id, 'round_policy': ROUND_POLICY, 'causal_evidence': True,
            'audit_note': AUDIT_NOTE, 'previous_chain': chain_status(store), 'unattended_authorization': unattended_authorization(store)}
    if not args.apply:
        return {'dry_run': True, **plan}
    if not unattended_authorization(store).get('enabled'):
        set_unattended_authorization(store, True, '用户', audit_note=AUDIT_NOTE)
    state = arm_chain(store, args.baseline_id, round_policy=ROUND_POLICY, causal_evidence=True, audit_note=AUDIT_NOTE)
    return {'armed': state, 'unattended_authorization': unattended_authorization(store)}


if __name__ == '__main__':
    print(json.dumps(main(), ensure_ascii=False, indent=2, default=str), flush=True)
