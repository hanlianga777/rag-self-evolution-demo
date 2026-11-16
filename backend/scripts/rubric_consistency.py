"""新 Rubric Judge 一致率测试（规则总表二.6）：同一批已保存回答判 N 遍，看结论是否一致。

只读数据库；不写正式成绩、不写复用表；每次判分后立即存断点，中断后续跑不重复付费。
默认 dry-run 只打印计划；加 --apply 才真正调用 DeepSeek。

PYTHONPATH=backend python backend/scripts/rubric_consistency.py \
    --runs EVAL-20261115170609095674 EVAL-20261115174123118797 \
    --answers 指挥/报告/040-参考答案定稿.csv --effort low --passes 2 \
    --output /tmp/rubric-low [--apply]
"""
import argparse
import csv
import json
import sqlite3
import time
from collections import Counter
from contextlib import closing
from pathlib import Path


def load_answers(path):
    with open(path, encoding='utf-8-sig') as f:
        return {row['题号']: row['参考答案定稿'] for row in csv.DictReader(f)}


def read_run(database, run_id):
    from app.sqlite_support import open_database
    with closing(open_database(database, read_only=True)) as db:
        db.row_factory = sqlite3.Row
        run = db.execute('SELECT id,dataset_snapshot_json FROM evaluation_runs WHERE id=?', (run_id,)).fetchone()
        if run is None:
            raise ValueError('Run 不存在：' + run_id)
        snapshot = json.loads(run['dataset_snapshot_json'])
        cases = {row['question_id']: json.loads(row['result_json']) for row in
                 db.execute('SELECT question_id,result_json FROM evaluation_case_results WHERE run_id=?', (run_id,))}
    items = []
    for index, question in enumerate(snapshot['questions'], 1):
        case = cases.get(question['id'])
        if case is None:
            raise ValueError(f'{run_id} 缺少 {question["id"]}')
        trace = (case.get('programmatic_metrics') or {}).get('retrieval_trace') or {}
        items.append({'run_id': run_id, 'slot': question.get('coverage_slot') or f'Q{index:02d}', 'question_id': question['id'],
                      'question': question['question'], 'category': question.get('test_category') or case.get('test_category'),
                      'negative_subtype': question.get('negative_subtype'), 'answer': case['model_answer'],
                      'final': trace.get('final') or case.get('retrieved_chunks') or [], 'old_passed': case.get('passed')})
    return items


def judge_once(provider, item, reference, effort):
    from app.providers import judge_thinking, ProviderInvalidResponse
    from app.rubric_judge import RUBRIC_VERSION, final_texts, rubric_verdict
    from app.telemetry import collect_usage, cost_fields
    context = {'contract_version': RUBRIC_VERSION, 'category': item['category'], 'negative_subtype': item['negative_subtype'],
               'final_texts': final_texts(item['final'])}
    last = None
    for attempt in range(3):
        try:
            with judge_thinking(effort), collect_usage() as usage:
                judged = provider.judge(item['question'], reference, item['answer'], context=context)
            verdict = rubric_verdict(item['category'], judged)
            cost = cost_fields(provider.settings.model, usage)
            return {k: v for k, v in judged.items() if k not in {'raw_provider_response', 'response_metadata'}} | {
                'passed': verdict['passed'], 'failed_dimensions': verdict['failed_dimensions'], 'attempts': attempt + 1,
                'estimated_cost': (cost.get('estimated_cost') or {}).get('amount') if isinstance(cost.get('estimated_cost'), dict) else cost.get('estimated_cost')}
        except ProviderInvalidResponse as error:
            last = str(error)
            time.sleep(2)
    return {'technical_failure': last}


def summarize(results, passes):
    keys = sorted({k for p in results.values() for k in p})
    rows, flips, score_same, verdict_same, total = [], [], 0, 0, 0
    for key in keys:
        runs = [results[str(p)].get(key) for p in range(1, passes + 1)]
        if any(r is None or 'technical_failure' in r for r in runs):
            continue
        total += 1
        verdicts = {r['passed'] for r in runs}
        dims = [tuple(r.get(d) for d in ('correctness', 'faithfulness', 'completeness', 'behavior_correct', 'safety_violation')) for r in runs]
        verdict_same += len(verdicts) == 1
        score_same += len(set(dims)) == 1
        if len(verdicts) > 1:
            flips.append(key)
    return {'judged_items': total, 'verdict_agreement': round(verdict_same / total, 4) if total else None,
            'exact_score_agreement': round(score_same / total, 4) if total else None, 'verdict_flips': flips}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--database', default='backend/data/demo.db')
    parser.add_argument('--runs', nargs='+', required=True)
    parser.add_argument('--answers', required=True)
    parser.add_argument('--effort', default='low', choices=['off', 'low', 'high', 'max'])
    parser.add_argument('--passes', type=int, default=2)
    parser.add_argument('--output', required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    answers = load_answers(args.answers)
    items = [item for run in args.runs for item in read_run(args.database, run)]
    missing = sorted({i['slot'] for i in items} - set(answers))
    if missing:
        raise SystemExit('参考答案缺题号：' + ','.join(missing))
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    state_path = out / 'state.json'
    state = json.loads(state_path.read_text()) if state_path.exists() else {'effort': args.effort, 'results': {}}
    if state['effort'] != args.effort:
        raise SystemExit('断点档位与本次不同，请换 --output 目录')
    plan = {'items': len(items), 'passes': args.passes, 'planned_calls': len(items) * args.passes, 'effort': args.effort}
    print(json.dumps(plan, ensure_ascii=False))
    if not args.apply:
        from app.rubric_judge import rubric_input, final_texts
        sample = items[0]
        print(rubric_input(sample['question'], answers[sample['slot']], sample['answer'], sample['category'], sample['negative_subtype'], final_texts(sample['final']))[:1500])
        return
    from app.config import load_settings
    from app.providers import DeepSeekProvider
    provider = DeepSeekProvider(load_settings())
    for p in range(1, args.passes + 1):
        bucket = state['results'].setdefault(str(p), {})
        for item in items:
            key = item['run_id'] + '|' + item['slot']
            if key in bucket and 'technical_failure' not in bucket[key]:
                continue
            bucket[key] = {**judge_once(provider, item, answers[item['slot']], args.effort), 'old_passed': item['old_passed'],
                           'category': item['category'], 'negative_subtype': item['negative_subtype']}
            state_path.write_text(json.dumps(state, ensure_ascii=False, indent=1))
    summary = summarize(state['results'], args.passes)
    first = state['results']['1']
    summary['pass_counts_by_run'] = {run: Counter('PASS' if v.get('passed') else 'FAIL' for k, v in first.items() if k.startswith(run + '|')) for run in args.runs}
    summary['technical_failures'] = sum('technical_failure' in v for p in state['results'].values() for v in p.values())
    summary['estimated_cost_usd'] = round(sum(v.get('estimated_cost') or 0 for p in state['results'].values() for v in p.values()), 6)
    (out / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=1))
    with open(out / 'per_question.csv', 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['run', '题号', '题型', '旧判定', *[f'第{p}遍{c}' for p in range(1, args.passes + 1) for c in ('对错', '分数/行为', '理由')]])
        for key in sorted(first):
            row = [key.split('|')[0], key.split('|')[1], first[key].get('category'), 'PASS' if first[key].get('old_passed') else 'FAIL']
            for p in range(1, args.passes + 1):
                r = state['results'][str(p)].get(key, {})
                scores = '/'.join(str(r.get(d)) for d in ('correctness', 'faithfulness', 'completeness')) if r.get('category') != 'negative' else f"行为{r.get('behavior_correct')} 安全违规{r.get('safety_violation')}"
                reason = '；'.join(str(r.get(k)) for k in ('correctness_reason', 'faithfulness_reason', 'completeness_reason', 'behavior_reason', 'safety_reason') if r.get(k))
                row += ['PASS' if r.get('passed') else 'FAIL' if 'passed' in r else '技术失败', scores, reason]
            writer.writerow(row)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
