#!/usr/bin/env python3
"""Build 016b comparisons from saved trial outcomes, with no provider calls."""
import csv
import difflib
import json
from datetime import datetime
from pathlib import Path
from statistics import mean, median
from zoneinfo import ZoneInfo
from task016b_trials import OUT, ROOT, RUNS, SELECTED, inputs, money, digest
import sys
sys.path.insert(0, str(ROOT / 'backend'))
from app.evaluation import summarize_evaluation_cases
from app.telemetry import cost_report
from app.paid_schedule import schedule_status
from task016b_trials import ReadOnlyStore

REPORTS = ROOT / '指挥/报告'


def write_csv(name, rows):
    if not rows:
        return
    with (REPORTS / name).open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def result(name):
    path = OUT / 'jobs' / (name + '.json')
    return json.loads(path.read_text()).get('result') if path.exists() else None


def percent(value):
    return '未知' if value is None else str(value)


def summary():
    sources = inputs()
    draft = json.loads((OUT / 'draft.json').read_text())
    changed, questions = draft['changed'], draft['questions']
    a_rows, controls, summaries, flips = [], [], {}, []
    genuine = {3, 4, 6, 7, 8, 13, 16, 17, 20, 23, 24, 27, 29}
    for label, source in sources.items():
        cases = {k: dict(v) for k, v in source['cases'].items()}
        missing = []
        for slot in changed:
            q = questions[slot]
            old = cases[q['id']]
            new = result(f'A-{label}-{slot}')
            if new is None:
                missing.append(slot)
            else:
                assert new['model_answer'] == old['model_answer']
                assert new['programmatic_metrics']['retrieval_trace'] == old['programmatic_metrics']['retrieval_trace']
                assert new['programmatic_metrics']['latency_ms'] == old['programmatic_metrics']['latency_ms']
                cases[q['id']] = {**new, 'question_id': q['id']}
            row = {'来源': label, '评测ID': source['id'], '题号': slot,
                   '旧结论': '对' if old['passed'] else '错',
                   '新结论': ('对' if new['passed'] else '错') if new else '未知',
                   '旧correctness': old['judge_result']['correctness'],
                   '新correctness': new['judge_result']['correctness'] if new else '未知',
                   '旧completeness': old['judge_result']['completeness'],
                   '新completeness': new['judge_result']['completeness'] if new else '未知',
                   '旧faithfulness': old['judge_result']['faithfulness'],
                   '新faithfulness': new['judge_result']['faithfulness'] if new else '未知',
                   '回答SHA256': digest(old['model_answer'])}
            a_rows.append(row)
            if new and not old['passed'] and new['passed']:
                flips.append({'label': label, 'slot': slot, 'known_genuine': int(slot[1:]) in genuine,
                              'answer': old['model_answer'], 'old_issues': old['judge_result'].get('issues'),
                              'new_checks': new['judge_result'].get('atomic_results', new['judge_result'].get('checks'))})
        old_summary = summarize_evaluation_cases(list(source['cases'].values()))
        new_summary = summarize_evaluation_cases(list(cases.values()), complete=not missing)
        summaries[label] = {'run_id': source['id'], 'missing': missing,
                            'old_correct': sum(c['passed'] for c in source['cases'].values()),
                            'new_correct': sum(c['passed'] for c in cases.values()) if not missing else None,
                            'old_summary': old_summary, 'new_summary': new_summary}
        for slot in ['Q35', 'Q37', 'Q46']:
            old = source['cases'][questions[slot]['id']]
            control = result(f'control-{label}-{slot}')
            new = result(f'A-{label}-{slot}')
            controls.append({'来源': label, '题号': slot, '历史原要点': '对' if old['passed'] else '错',
                             '本次原要点': ('对' if control['passed'] else '错') if control else '未知',
                             '本次新要点': ('对' if new['passed'] else '错') if new else '未知'})
    b_rows, stability = [], []
    b_cases = {1: [], 2: []}
    for number in SELECTED:
        slot = f'Q{number:02d}'
        q = questions[slot]
        executions, scored = {}, {}
        for repeat in [1, 2]:
            execution = result(f'B-gen-{slot}-{repeat}')
            score = result(f'B-judge-{slot}-{repeat}')
            executions[repeat], scored[repeat] = execution, score
            if score:
                b_cases[repeat].append(score)
            hist = {l: sources[l]['cases'][q['id']] for l in ['high', '今天 max', '11-01 max']}
            b_rows.append({'题号': slot, '重复': repeat, '结论': ('对' if score['passed'] else '错') if score else '未知',
                           '耗时ms': execution['latency_ms'] if execution else '未知',
                           '输出token': execution.get('output_tokens') if execution else '未知',
                           'high原结论': '对' if hist['high']['passed'] else '错',
                           'high草案结论': ('对' if (result('A-high-' + slot) or hist['high'])['passed'] else '错'),
                           'high耗时ms': hist['high']['programmatic_metrics'].get('latency_ms'),
                           '今天max原结论': '对' if hist['今天 max']['passed'] else '错',
                           '今天max耗时ms': hist['今天 max']['programmatic_metrics'].get('latency_ms'),
                           '11-01max原结论': '对' if hist['11-01 max']['passed'] else '错',
                           '11-01max耗时ms': hist['11-01 max']['programmatic_metrics'].get('latency_ms')})
        first, second = executions[1], executions[2]
        stability.append({'题号': slot, '完全相同': first['answer'] == second['answer'] if first and second else '未知',
                          '文字相似度': round(difflib.SequenceMatcher(None, first['answer'], second['answer'], autojunk=False).ratio(), 6) if first and second else '未知',
                          '判分一致': scored[1]['passed'] == scored[2]['passed'] if all(scored.values()) else '未知',
                          '最终上下文相同': digest(first['retrieval_trace']['final']) == digest(second['retrieval_trace']['final']) if first and second else '未知'})
    comparisons = {}
    for label in ['high', '今天 max', '11-01 max']:
        chosen = [sources[label]['cases'][questions[f'Q{n:02d}']['id']] for n in SELECTED]
        revised_cases = [result(f'A-{label}-Q{n:02d}') or c for n, c in zip(SELECTED, chosen)]
        missing_draft = [f'Q{n:02d}' for n in SELECTED if f'Q{n:02d}' in changed and result(f'A-{label}-Q{n:02d}') is None]
        times = [c['programmatic_metrics']['latency_ms'] for c in chosen]
        comparisons[label] = {'correct_original': sum(c['passed'] for c in chosen),
                              'correct_draft': sum(c['passed'] for c in revised_cases) if not missing_draft else None,
                              'missing_draft': missing_draft,
                              'median_ms': median(times), 'mean_ms': round(mean(times), 2), 'total_ms': sum(times)}
    for repeat in [1, 2]:
        chosen = b_cases[repeat]
        times = [c['programmatic_metrics']['latency_ms'] for c in chosen]
        comparisons[f'off-{repeat}'] = {'completed': len(chosen), 'correct': sum(c['passed'] for c in chosen),
                                        'median_ms': median(times) if times else None,
                                        'mean_ms': round(mean(times), 2) if times else None, 'total_ms': sum(times)}
    calls = []
    for path in (OUT / 'jobs').glob('*.ledger.json'):
        for index, call in enumerate(json.loads(path.read_text())['calls'], 1):
            usage = call.get('usage', {})
            report = cost_report(call['model'], [usage]) if call['provider'] == 'DeepSeek' else {}
            timestamp = datetime.fromisoformat(call['started_at'])
            payload = call.get('request_payload', {})
            calls.append({'任务': path.name.removesuffix('.ledger.json'), '序号': index,
                          'UTC时间': call['started_at'], '多伦多时间': timestamp.astimezone(ZoneInfo('America/Toronto')).isoformat(),
                          'Provider': call['provider'], '模型': call['model'], '用途': call['task'],
                          '思考': payload.get('reasoning_effort', payload.get('thinking', {}).get('type', '不适用')),
                          'temperature': payload.get('temperature', '未传'), '状态': call['status'],
                          '输入token': usage.get('prompt_tokens', usage.get('total_tokens', '未知')),
                          '输出token': usage.get('completion_tokens', '不适用'),
                          '缓存命中token': usage.get('prompt_cache_hit_tokens', '不适用'),
                          '时段': (report.get('calls') or [{}])[0].get('billing_period', '不适用'),
                          '估算USD': report.get('amount') if report.get('amount') is not None else '未知',
                          '未知费用保守上界USD': call.get('reservation_usd', '未知') if call['provider'] == 'DeepSeek' and report.get('amount') is None else '',
                          '请求前平价核验': not schedule_status(ReadOnlyStore(), at=timestamp)['peak_now'] if call['provider'] == 'DeepSeek' else '不适用',
                          '请求SHA256': call['request_sha256']})
    calls.sort(key=lambda r: r['UTC时间'])
    write_csv('016b-试跑A逐题对照.csv', a_rows)
    write_csv('016b-六份重算汇总.csv', [
        {'来源': label, '原答对数': r['old_correct'], '新答对数': r['new_correct'] if not r['missing'] else '未知',
         '安全拒答率': r['new_summary']['safety_metrics']['safe_rejection_rate'] if not any(questions[s]['test_category'] == 'negative' for s in r['missing']) else '未知',
         '安全关键准确率': r['new_summary']['safety_metrics']['safety_critical_accuracy'] if not any(questions[s].get('negative_subtype') == 'safety_critical' for s in r['missing']) else '未知',
         '门槛通过数': r['new_summary']['gates']['passed_count'] if not r['missing'] else '未知',
         '未完成题': '、'.join(r['missing'])} for label, r in summaries.items()])
    write_csv('016b-三题原要点对照.csv', controls)
    write_csv('016b-试跑B逐次结果.csv', b_rows)
    write_csv('016b-试跑B稳定性.csv', stability)
    write_csv('016b-调用明细.csv', calls)
    aggregate = {'A': summaries, 'controls': controls, 'flips': flips,
                 'B': comparisons, 'stability': stability, 'money': money(),
                 'planned_A': len(changed) * 6, 'completed_A': sum(r['新结论'] != '未知' for r in a_rows),
                 'planned_control': 18, 'completed_control': sum(r['本次原要点'] != '未知' for r in controls),
                 'planned_B': 60, 'completed_B': sum(result(f'B-{phase}-Q{n:02d}-{r}') is not None for phase in ['gen', 'judge'] for n in SELECTED for r in [1, 2])}
    (OUT / 'summary.json').write_text(json.dumps(aggregate, ensure_ascii=False, indent=2))
    print(json.dumps({k: v for k, v in aggregate.items() if k not in {'A', 'controls', 'flips', 'stability'}}, ensure_ascii=False))
    return aggregate


if __name__ == '__main__':
    summary()
