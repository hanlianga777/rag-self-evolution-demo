"""Print the exact saved Baseline Agent input and an in-memory coverage replay."""
import argparse
import json
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.agent_inputs import prepare_baseline_rows
from app.agent_coverage import plan_coverage
from app.evaluation_contract import business_verdict
from app.optimization import build_agent_prompt
from app.policy import DEFAULT_PIPELINE_CONFIG


def preview(database, baseline_id):
    connection = sqlite3.connect(Path(database).resolve().as_uri() + '?mode=ro', uri=True)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute('PRAGMA query_only=ON')
        raw = connection.execute('SELECT * FROM evaluation_runs WHERE id=?', (baseline_id,)).fetchone()
        if raw is None:
            raise ValueError('找不到指定 Baseline')
        baseline = {**dict(raw), 'result': json.loads(raw['result_json']), 'config': json.loads(raw['config_json'])}
        rows = [{**dict(row), 'result': {**json.loads(row['result_json']), 'run_id': row['run_id'], 'question_id': row['question_id']}}
                for row in connection.execute('SELECT * FROM bad_cases WHERE run_id=? ORDER BY created_at DESC', (baseline_id,))]
    finally:
        connection.close()
    rows = prepare_baseline_rows(baseline, rows)
    rows = [row for row in rows if business_verdict(row['result']) == 'FAIL' or
            (row['result'].get('evaluation_outcome') or {}).get('contract_version') != 'business-vnext-1' and row['result'].get('passed') is False]
    base = {**DEFAULT_PIPELINE_CONFIG, **baseline['config']}
    for key in ('run_target', 'knowledge_identity'):
        base.pop(key, None)
    gates = (baseline['result'].get('gates') or {}).get('gates')
    failed = [gate for gate in gates if gate.get('passed') is False] if isinstance(gates, list) else None
    system, prompt = build_agent_prompt(rows, base, [], failed, list('ABC'))
    return {'baseline_id': baseline_id, 'golden_id': raw['dataset_version_id'],
            'scope': '首次生成A/B/C的完整提示词；上一轮方案为空，仅内存构建，不创建实验',
            'system': system, 'prompt': prompt, 'coverage': plan_coverage(rows, base, []), 'provider_calls': 0}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, default=Path(__file__).resolve().parents[1] / 'data/demo.db')
    parser.add_argument('--baseline-id', required=True)
    parser.add_argument('--full', action='store_true', help='同时打印完整提示词和规划回放；默认仅打印错题输入')
    args = parser.parse_args()
    value = preview(args.database, args.baseline_id)
    print(json.dumps(value if args.full else value['prompt']['bad_cases'], ensure_ascii=False, indent=2))
