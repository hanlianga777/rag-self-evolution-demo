"""检索可修空间扫描：开跑前判断"Agent 手里的检索参数，到底能不能把题修好"。只检索、不生成、不判分。

为什么要有它（2026-11-16 复盘）：
  如果 Baseline 配置下标准证据本来就都进了最终资料，Agent 调检索参数修不了题，只能靠其他方向；
  如果连其他方向也没有空间，剩下的成绩差只是回答和判分的随机波动。花钱前先把检索这一层的空间量清楚。
  这一步只调用 embedding、rerank 和（开了改写/多问法/HyDE 时）关闭思考的小模型，几分钱，结果可重复，
  所以必须放在付费 Baseline 和 Agent 之前。

做法：
  1. 对每道正向题、消融题，用 Baseline 配置走一遍正式回答前的全部检索步骤（AiService.retrieve_context，与正式回答同一条代码），
     看标准证据切块是否全部进了最终交给模型的资料（all_hit）以及第一段标准证据排第几（rank）。
  2. 再对 Agent 搜索空间里每个检索参数的每个可选值，各改一个参数扫一遍；最后把单参数里收益最大的几个两两组合再扫一遍
     （Agent 每个方案最多改 2 个参数）。
  3. 汇总：Baseline 没拿到证据的题 = 检索缺口；其中某个配置能补回来的 = 可修空间。

结论只作参考（用户 2026-11-16 21:26 定）：
  Bad Case 有生成层、检索层、安全边界层、性能层四类，Agent 会按实际情况选方向（例如调思考档位），不只修检索。
  本扫描只量得出"检索层"的可修空间，所以输出的 GO / NO-GO 只是检索层的参考信号，不作为启动 Baseline 或 Agent 的硬条件。
  参考口径：可修空间 ≥ --min-fixable（默认 5）道，且至少有一个 ≤2 参数的配置能补回 ≥3 道、同时弄丢的题 ≤1 道 → GO。

PYTHONPATH=backend python3 backend/scripts/retrieval_headroom.py --csv 指挥/报告/049-新题卷定稿.csv --output 指挥/报告/050-检索可修空间.csv
  --smoke：只扫 3 道题 × 2 个配置，先确认能跑通（几乎不花钱）。
"""
import argparse
import csv
import io
import json
import os
from itertools import combinations
from pathlib import Path

RETRIEVAL_KEYS = ('candidate_k', 'top_k', 'min_score', 'hybrid_search', 'hybrid_alpha', 'rerank',
                  'query_rewrite', 'multi_query', 'hyde', 'retrieval_max_tokens')


def golden_questions(csv_bytes):
    """从题卷 CSV 取正向题和消融题：题号、问题、标准证据切块。"""
    rows = list(csv.DictReader(io.StringIO(csv_bytes.decode('utf-8-sig'), newline='')))
    items = []
    for row in rows:
        if row['题型'].strip() not in {'positive', 'ablation'}:
            continue
        ids = []
        for line in (row.get('证据') or '').splitlines():
            chunk_id, sep, _ = line.partition('｜')
            if sep and chunk_id.strip() and chunk_id.strip() not in ids:
                ids.append(chunk_id.strip())
        if not ids:
            raise ValueError(f"{row['题号']} 没有标准证据切块，无法扫描")
        items.append({'qid': row['题号'].strip(), 'group': row['题型'].strip(), 'method': row.get('出题方式', '').strip(),
                      'question': row['问题'].strip(), 'golden': ids})
    return items


def single_variants(baseline, space):
    """每个检索参数的每个可选值各改一次（相对 Baseline 只改 1 个参数）。"""
    variants = []
    for key in RETRIEVAL_KEYS:
        for value in space.get(key, ()):
            if value != baseline.get(key):
                variants.append({key: value})
    return variants


def hit_of(evidence, golden):
    got = [e.get('chunk_id') for e in evidence]
    ranks = [got.index(g) + 1 for g in golden if g in got]
    return {'all_hit': len(ranks) == len(golden), 'rank': min(ranks) if ranks else None, 'n_context': len(got)}


def scan(items, baseline, variants, retrieve):
    """retrieve(question, config) -> 最终交给模型的资料列表。返回 {配置名: {题号: hit}}。"""
    def label(change):
        return 'baseline' if not change else ' + '.join(f'{k}={json.dumps(v)}' for k, v in sorted(change.items()))
    results = {}
    for change in [{}, *variants]:
        config = {**baseline, **change}
        results[label(change)] = {'change': change, 'hits': {item['qid']: hit_of(retrieve(item['question'], config), item['golden']) for item in items}}
    return results


def summarize(results, *, min_fixable=5, min_single=3, max_lost=1):
    base = results['baseline']['hits']
    gap = sorted(q for q, h in base.items() if not h['all_hit'])
    rows = []
    for name, data in results.items():
        if name == 'baseline':
            continue
        hits = data['hits']
        fixed = sorted(q for q in gap if hits[q]['all_hit'])
        lost = sorted(q for q, h in base.items() if h['all_hit'] and not hits[q]['all_hit'])
        rows.append({'config': name, 'n_params': len(data['change']), 'fixed': fixed, 'lost': lost, 'net': len(fixed) - len(lost)})
    rows.sort(key=lambda r: (-r['net'], r['n_params'], r['config']))
    fixable = sorted({q for r in rows for q in r['fixed']})
    strong = [r for r in rows if r['n_params'] <= 2 and len(r['fixed']) >= min_single and len(r['lost']) <= max_lost]
    verdict = 'GO' if len(fixable) >= min_fixable and strong else 'NO-GO'
    return {'verdict': verdict, 'note': '仅检索层参考信号，不作为启动条件', 'rule': f'可修空间≥{min_fixable} 且存在 ≤2 参数配置补回≥{min_single}、弄丢≤{max_lost}',
            'baseline_gap': gap, 'fixable': fixable, 'unfixable_gap': sorted(set(gap) - set(fixable)),
            'best_configs': rows[:8], 'strong_configs': [r['config'] for r in strong]}


def write_table(path, items, results):
    names = list(results)
    with open(path, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['题号', '题型', '出题方式', '标准证据', *names])
        for item in items:
            cells = []
            for n in names:
                h = results[n]['hits'][item['qid']]
                cells.append(('✓' if h['all_hit'] else '✗') + (f" #{h['rank']}" if h['rank'] else ''))
            w.writerow([item['qid'], item['group'], item['method'], ' '.join(item['golden']), *cells])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--csv', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--database', type=Path)
    parser.add_argument('--smoke', action='store_true')
    parser.add_argument('--pairs', type=int, default=4, help='单参数收益最大的前 N 个两两组合再扫')
    parser.add_argument('--min-fixable', type=int, default=5)
    args = parser.parse_args(argv)
    from app.config import load_values
    database = args.database or Path(load_values().get('RAG_DEMO_DB_PATH') or Path(__file__).resolve().parents[1] / 'data/demo.db')
    os.environ['RAG_DEMO_DB_PATH'] = str(database.resolve())
    os.environ['RAG_SAFE_START'] = '1'
    from app.main import ai_service
    from app.policy import ALLOWED_SEARCH_SPACE, DEFAULT_PIPELINE_CONFIG
    if not ai_service.live_enabled:
        raise SystemExit('需要真实的 embedding / rerank / DeepSeek 配置；当前是 Mock，扫描结果没有意义')
    baseline = dict(DEFAULT_PIPELINE_CONFIG)
    items = golden_questions(args.csv.read_bytes())

    def retrieve(question, config):
        return ai_service.retrieve_context(question, config)[0]

    if args.smoke:
        items, variants = items[:3], [{'candidate_k': 24}]
        return {'smoke': True, 'baseline_config': baseline, 'results': scan(items, baseline, variants, retrieve)}
    singles = single_variants(baseline, ALLOWED_SEARCH_SPACE)
    results = scan(items, baseline, singles, retrieve)
    best = [r for r in summarize(results)['best_configs'] if r['net'] > 0][:args.pairs]
    pairs = []
    for a, b in combinations(best, 2):
        change = {**results[a['config']]['change'], **results[b['config']]['change']}
        if len(change) == 2:
            pairs.append(change)
    if pairs:
        results.update({k: v for k, v in scan(items, baseline, pairs, retrieve).items() if k != 'baseline'})
    summary = summarize(results, min_fixable=args.min_fixable)
    if args.output:
        write_table(args.output, items, results)
    return {'baseline_config': {k: baseline[k] for k in RETRIEVAL_KEYS}, 'questions': len(items), 'configs': len(results), **summary}


if __name__ == '__main__':
    print(json.dumps(main(), ensure_ascii=False, indent=1, default=str), flush=True)
