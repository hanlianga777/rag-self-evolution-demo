#!/usr/bin/env python3
"""Read persisted progress without starting the app or invoking any Provider."""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sqlite3
import sys
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
# Reuse pure budget functions; do not instantiate GovernanceStore or import main.
sys.path.insert(0, str(ROOT / 'backend'))
from app.governance import MAX_EVALS, sandbox_attempts_used
TORONTO = ZoneInfo('America/Toronto')
ACTIVE = {'queued', 'running', 'generating', 'coverage', 'validation', 'validating', 'probing', 'qc', 'waiting'}


def number(value):
    return value if type(value) in (int, float) else '未知'


def identifier(value):
    return value if isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_-]{1,100}', value) else '未知'


def toronto(value):
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return parsed.astimezone(TORONTO).strftime('%Y-%m-%d %H:%M:%S %Z') if parsed.tzinfo else '未知'
    except (ValueError, TypeError, AttributeError):
        return '未知'


def safe_error(error):
    # Error messages may contain prompts, answers, keys or HTTP bodies. Never echo them.
    text = str(error or '')
    for terms, kind, explanation in [
        (('ProviderTimeout', 'timeout', '超时'), 'ProviderTimeout', '外部请求超时，详见本机记录'),
        (('401', '403', 'auth', '认证'), 'AuthenticationError', '外部服务认证失败'),
        (('429', 'rate_limit'), 'RateLimitError', '外部服务限流'),
        (('locked', 'busy'), 'SQLiteBusy', '本机数据库暂时繁忙'),
        (('identity', '合同', '身份'), 'IdentityMismatch', '冻结身份或合同校验未通过'),
    ]:
        if any(term.lower() in text.lower() for term in terms):
            return f'{kind}：{explanation}'
    return 'UnknownError：任务失败，具体原因请查本机记录' if error else '无'


def build_status(database, data_dir):
    with closing(sqlite3.connect(Path(database).resolve().as_uri() + '?mode=ro', uri=True, timeout=10)) as db:
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA query_only=ON')
        db.execute('BEGIN')
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}

        def rows(table):
            return [dict(row) for row in db.execute(f'SELECT * FROM {table} ORDER BY rowid DESC')] if table in tables else []

        def load(row, field='result_json'):
            return json.loads(row.get(field) or '{}')

        runs = rows('evaluation_runs')
        experiments = rows('experiments')
        candidates = rows('candidate_configs')
        by_candidate = {c['id']: c for c in candidates}
        tasks = []
        for run in runs:
            result, config = load(run), load(run, 'config_json')
            candidate = by_candidate.get(config.get('candidate_id'))
            stage = 'Baseline'
            if candidate:
                reasoning = load(candidate, 'reasoning_json')
                label = reasoning.get('candidate_label')
                match = re.search(r'-R(\d+)-([ABC])$', candidate['id'])
                round_no = reasoning.get('round') or (int(match[1]) if match else None)
                label = label or (match[2] if match else None)
                stage = 'Candidate D' if label == 'D' else f'第{number(round_no)}轮第{dict(A=1,B=2,C=3).get(label,"未知")}个 Candidate（{label if label in {"A","B","C"} else "未知"}）'
            tasks.append({**run, 'result': result, 'stage': stage})
        for exp in experiments:
            result = load(exp)
            cycle = result.get('optimization_cycle', {})
            composite = result.get('composite_schedule', {})
            active = exp['status'] in ACTIVE or cycle.get('status') in ACTIVE or composite.get('status') in ACTIVE
            if active or cycle.get('status') == 'failed':
                tasks.append({**exp, 'status': 'running' if active else 'failed',
                    'created_at': cycle.get('updated_at', exp['created_at']),
                    'result': {**result, 'price_pause': cycle.get('price_pause') or composite.get('price_pause') or result.get('price_pause', {}),
                               'error': cycle.get('last_error') or result.get('error')},
                    'stage': 'Candidate D' if cycle.get('phase') == 'composite' or composite.get('status') in ACTIVE else f'第{number(cycle.get("round", result.get("round")))}轮第未知个 Candidate（Agent分析）'})
        for rev in rows('candidate_revision_runs'):
            tasks.append({**rev, 'created_at': rev.get('updated_at', rev['created_at']),
                          'result': load(rev, 'audit_json'), 'stage': '题卷锚定'})
        for gen in rows('golden_generation_runs'):
            artifact = db.execute('SELECT hard_validation_json FROM golden_generation_artifacts WHERE generation_run_id=?', (gen['id'],)).fetchone() if 'golden_generation_artifacts' in tables else None
            result = json.loads(artifact[0]) if artifact else {}
            progress = result.get('progress') or {}
            profile = load(gen, 'profile_json')
            expected = profile.get('expected_count') or sum(profile.get(k + '_count', profile.get(k, 0)) for k in ('positive', 'ablation', 'negative'))
            phase = result.get('failed_stage') or progress.get('stage', gen['status'])
            if phase == 'probing':
                result.update(completed=progress.get('probe_completed', 0), total=expected)
            elif phase in {'qc', 'completed'}:
                result.update(completed=progress.get('qc_completed', 0) + progress.get('qc_skipped', 0), total=expected)
            else:
                result.update(completed=progress.get('phase_processed', len(json.loads(gen.get('question_ids_json') or '[]'))), total=progress.get('phase_total', expected))
            tasks.append({**gen, 'result': result, 'stage': '题卷锚定'})
        for path in sorted((Path(data_dir) / 'corpus_operations').glob('*.json')):
            operation = json.loads(path.read_text())
            tasks.append({**operation, 'created_at': datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
                          'result': operation, 'stage': '知识库重建'})

        tasks.sort(key=lambda t: t.get('created_at', t.get('started_at', '')), reverse=True)
        active = [t for t in tasks if t.get('status') in ACTIVE]
        # An active Sandbox gives more precise progress than its parent cycle.
        active_runs = [t for t in active if t.get('id') in {r['id'] for r in runs}]
        current = next(iter(active_runs or active or tasks), {})
        result = current.get('result', {})
        failed = current.get('status') in {'failed', 'error', 'interrupted', 'partial', 'failed_quality'}
        stage = '出错' if failed else current.get('stage', '已完成（空闲）') if active else '已完成（空闲）'
        progress = result.get('progress') or {}
        quality = result.get('quality_rerun') or {}
        if quality.get('status') in ACTIVE:
            progress = quality
        done = result.get('completed', progress.get('completed', progress.get('current', progress.get('phase_processed', progress.get('probe_completed')))))
        total = result.get('total', progress.get('total', progress.get('phase_total')))
        technical = result.get('technical_failed', result.get('technical_error_count'))
        pause = result.get('price_pause') or progress.get('price_pause') or {}
        paused = pause.get('paused') is True and bool(active)
        error = current.get('error_message') or result.get('error') or result.get('last_error')
        if not error and result.get('technical_errors'):
            error = result['technical_errors'][-1]
        if not error and failed:
            error = 'unknown'
        if not failed and not (type(technical) in (int,float) and technical > 0):
            error = None
        # Use the real attempt ledger, not the stale result.evaluation_budget.used.
        used = budget = '未知'
        if experiments:
            exp = experiments[0]
            peers = [c for c in candidates if c['experiment_id'] == exp['id']]
            used = 0
            for c in peers:
                used += sandbox_attempts_used({**c, 'reasoning': load(c, 'reasoning_json'), 'result': load(c)})
            budget = MAX_EVALS

        # No reliable whole-chain ledger exists in every historical run; never sum overlapping resume histories.
        accounting = result.get('request_accounting') or {}
        cost = accounting.get('cost_estimation') or result.get('cost_estimation') or {}
        amount = cost.get('amount') if cost.get('status') == 'estimated' else None
        currency = cost.get('currency') or cost.get('price_snapshot', {}).get('currency')
        cost_text = f'{amount:.6f} {currency}（当前任务；整条链路累计：未知）' if type(amount) in (int, float) and currency in {'USD', 'CNY'} else '未知（未取得完整费用依据）'
        lines = [f'当前阶段：{stage}',
                 f'完成题数：{number(done)} / {number(total)}；技术失败数：{number(technical)}',
                 f'非平价时段暂停：{"是" if paused else "否"}；预计恢复时间：{toronto(pause.get("resume_at")) if paused else "无"}',
                 f'预算已用 / 总数：{used} / {budget}（Sandbox次数）',
                 f'费用估算：{cost_text}', f'最近一次错误：{safe_error(error)}', '',
                 '已完成的评测（P50、P99 单位：秒）：', '',
                 '| 编号 | 答对 | Hard Gate通过数 | P50 | P99 |', '| --- | --- | --- | --- | --- |']
        for run in runs:
            if run['status'] != 'completed':
                continue
            r = load(run)
            count, correct = r.get('total'), None
            if 'evaluation_case_results' in tables:
                counts = db.execute("SELECT count(*),sum(CASE WHEN json_extract(result_json,'$.passed')=1 THEN 1 ELSE 0 END) FROM evaluation_case_results WHERE run_id=?", (run['id'],)).fetchone()
                if counts[0] and counts[0] == count:
                    correct = counts[1]
            if correct is None and r.get('evaluation_complete') is True and r.get('technical_failed') == 0 and type(count) is int and type(r.get('bad_case_count')) is int:
                correct = count - r['bad_case_count']
            gates, metrics = r.get('gates') or {}, r.get('metrics') or {}
            lines.append(f'| {identifier(run["id"])} | {number(correct)} / {number(count)} | {number(gates.get("passed_count"))} / {number(gates.get("total"))} | {number(metrics.get("latency_p50_seconds"))} | {number(metrics.get("latency_p99_seconds"))} |')
        return '\n'.join(lines) + '\n'


def export_status(database, data_dir, output):
    body = build_status(database, data_dir)
    output = Path(output)
    previous = output.read_text() if output.exists() else ''
    if previous.partition('\n\n')[2] == body:
        return False
    text = '更新时间（多伦多）：' + datetime.now(TORONTO).strftime('%Y-%m-%d %H:%M:%S %Z') + '\n\n' + body
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_suffix('.md.tmp')
    temp.write_text(text)
    temp.replace(output)
    return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, default=ROOT / 'backend/data/demo.db')
    parser.add_argument('--data-dir', type=Path, default=ROOT / 'backend/data')
    parser.add_argument('--output', type=Path, default=ROOT / '指挥/运行状态.md')
    args = parser.parse_args()
    print('已更新' if export_status(args.database, args.data_dir, args.output) else '状态未变')
