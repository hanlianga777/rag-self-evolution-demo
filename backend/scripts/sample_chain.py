"""10 题小样全链路（规则总表：正式 Baseline 前的通路检查）。

用与正式 Baseline 完全相同的输入（最新 approved Golden Snapshot、Strict、BASELINE_THINKING、冻结的输出上限）
对固定挑选的 10 题各跑一次"检索 → 生成 → 新 Judge 判分"，只把结果写到 --output 目录：
- 不创建 evaluation run，不写正式成绩，不写复用表（不进入 reuse_scope）；
- 每题完成即存断点，中断后续跑不会重复付费；
- 挑题规则固定（按题卷顺序取前 4 道正向、前 2 道消融、第 1 道安全关键、第 1 道提示注入、其余负向前 2 道），
  不是"多跑几次挑好结果"。

默认 dry-run 只打印计划；加 --apply 才真正调用 DeepSeek / 阿里云。

PYTHONPATH=backend python backend/scripts/sample_chain.py --output /tmp/sample-chain [--apply]
"""
import argparse
import csv
import json
import os
import statistics
import time
from pathlib import Path


def pick(items, question_ids=None):
    if question_ids:
        wanted = set(question_ids)
        chosen = [item for item in items if item['id'] in wanted or item.get('coverage_slot') in wanted]
        if len(chosen) != len(wanted):
            raise ValueError('有题号不在当前题卷里')
        return chosen
    positive = [i for i in items if i['test_category'] == 'positive'][:4]
    ablation = [i for i in items if i['test_category'] == 'ablation'][:2]
    negative = [i for i in items if i['test_category'] == 'negative']
    safety = [i for i in negative if i.get('negative_subtype') == 'safety_critical'][:1]
    injection = [i for i in negative if i.get('negative_subtype') == 'prompt_injection'][:1]
    other = [i for i in negative if i.get('negative_subtype') not in {'safety_critical', 'prompt_injection'}][:2]
    return positive + ablation + safety + injection + other


def slot(item, items):
    return item.get('coverage_slot') or f"Q{[i['id'] for i in items].index(item['id']) + 1:02d}"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path)
    parser.add_argument('--questions', nargs='+', help='可选：指定题号（Q01 或原始题号）；省略时用固定挑题规则')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args(argv)
    from app.config import load_values
    database = args.database or Path(load_values().get('RAG_DEMO_DB_PATH') or Path(__file__).resolve().parents[1] / 'data/demo.db')
    os.environ['RAG_DEMO_DB_PATH'] = str(database.resolve())
    os.environ['RAG_SAFE_START'] = '1'
    from app.main import store, ai_service
    from app.evaluation import EvaluationRunner
    from app.providers import thinking_config
    if Path(store.database_path).resolve() != database.resolve():
        raise ValueError('已加载的数据库与指定数据库不一致')
    runner = EvaluationRunner(store, ai_service)
    snapshot, approved, config, judge_meta = runner.baseline_inputs()
    chosen = pick(approved, args.questions)
    limits = judge_meta['execution_snapshot'].get('request_limits')
    plan = {'snapshot_id': snapshot.get('id') or snapshot.get('snapshot_id'), 'snapshot_question_count': len(approved),
            'questions': [{'slot': slot(i, approved), 'id': i['id'], 'category': i['test_category'],
                           'negative_subtype': i.get('negative_subtype')} for i in chosen],
            'config': {k: config.get(k) for k in sorted(config)}, 'judge_thinking': thinking_config('judge'),
            'judge_versions': {k: judge_meta.get(k) for k in ('prompt_version', 'scoring_policy', 'judge_input_version', 'judge_prompt_sha256')},
            'request_limits': limits, 'planned_generation_calls': len(chosen), 'planned_judge_calls': len(chosen),
            'formal_records_written': False}
    if not args.apply:
        return {'dry_run': True, **plan}
    args.output.mkdir(parents=True, exist_ok=True)
    state_path = args.output / 'state.json'
    state = json.loads(state_path.read_text()) if state_path.exists() else {'plan': plan, 'cases': {}}
    if state['plan'] != plan:
        raise ValueError('题卷、配置或判分合同已变化，请换一个 --output 目录')

    def save():
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=1))

    from app.paid_run import accounting_only, execution_limits
    from app.paid_schedule import wait_for_off_peak
    from app.telemetry import collect_usage, cost_fields
    with accounting_only(), execution_limits(limits):
        for item in chosen:
            key = slot(item, approved)
            if 'result' in state['cases'].get(key, {}):
                continue
            wait_for_off_peak(store, 'sample-chain:' + key, lambda pause: None)
            started = time.perf_counter()
            try:
                with collect_usage() as usage:
                    execution = ai_service.answer(item['question'], config)
                    answered = time.perf_counter()
                    case = runner.score_execution(item, execution)
                outcome = case.get('evaluation_outcome') or {}
                judged = {k: v for k, v in (case.get('judge_result') or {}).items()
                          if k not in {'token_usage', 'stages', 'estimated_cost', 'cost_estimation'}}
                state['cases'][key] = {'result': {
                    'id': item['id'], 'category': item['test_category'], 'negative_subtype': item.get('negative_subtype'),
                    'passed': case.get('passed'), 'verdict_reason': outcome.get('reason'),
                    'failed_dimensions': outcome.get('failed_dimensions'), 'judge': judged,
                    'answer_chars': len(execution.get('answer') or ''), 'answer': execution.get('answer'),
                    'generation_seconds': round(answered - started, 2), 'total_seconds': round(time.perf_counter() - started, 2),
                    'latency_ms': execution.get('latency_ms'), 'cost': cost_fields(ai_service.model, usage).get('estimated_cost')}}
            except Exception as error:
                state['cases'][key] = {'technical_error': type(error).__name__ + ': ' + str(error)[:500]}
            save()
    rows = [state['cases'][slot(i, approved)] for i in chosen]
    done = [r['result'] for r in rows if 'result' in r]
    seconds = [r['total_seconds'] for r in done]
    summary = {**plan, 'completed': len(done), 'technical_errors': sum('technical_error' in r for r in rows),
               'passed': sum(r['passed'] is True for r in done), 'failed': sum(r['passed'] is False for r in done),
               'answer_chars_median': statistics.median([r['answer_chars'] for r in done]) if done else None,
               'seconds_median': statistics.median(seconds) if seconds else None, 'seconds_max': max(seconds) if seconds else None}
    (args.output / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=1))
    with (args.output / 'per_question.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['题号', '类型', '负向子类型', '判定', '未达标维度', '三维/行为分数与理由', '回答字数', '用时秒', '回答', '技术错误'])
        for item, row in zip(chosen, rows):
            r = row.get('result', {})
            writer.writerow([slot(item, approved), item['test_category'], item.get('negative_subtype') or '',
                             {True: '对', False: '错'}.get(r.get('passed'), '未知'), json.dumps(r.get('failed_dimensions'), ensure_ascii=False),
                             json.dumps(r.get('judge'), ensure_ascii=False), r.get('answer_chars'), r.get('total_seconds'),
                             r.get('answer'), row.get('technical_error', '')])
    return summary


if __name__ == '__main__':
    print(json.dumps(main(), ensure_ascii=False, indent=2), flush=True)
