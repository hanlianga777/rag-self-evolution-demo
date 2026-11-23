"""检索可修空间扫描：开跑前判断"Agent 手里的检索参数，到底能不能把题修好"。只检索、不生成、不判分。

为什么要有它（2026-11-16 复盘）：
  如果 Baseline 配置下标准证据本来就都进了最终资料，Agent 调检索参数修不了题，只能靠其他方向；
  如果连其他方向也没有空间，剩下的成绩差只是回答和判分的随机波动。花钱前先把检索这一层的空间量清楚。
  这一步只调用 embedding、rerank 和（开了改写/多问法/HyDE 时）关闭思考的小模型，几分钱，结果可重复，
  所以必须放在付费 Baseline 和 Agent 之前。

做法：
  1. 对每道正向题、消融题，用 Baseline 配置走一遍正式回答前的全部检索步骤（AiService.retrieve_context，与正式回答同一条代码），
     看标准证据切块是否全部进了最终交给模型的资料（all_hit）以及第一段标准证据排第几（rank）。
  2. 再对 Agent 搜索空间里每个检索参数的每个可选值，各改一个参数扫一遍；最后再扫收益较好的参数组合；供 Agent 使用的组合按本轮参数上限过滤。
  3. 汇总：Baseline 没拿到证据的题 = 检索缺口；其中某个配置能补回来的 = 可修空间。

结论只作参考（用户 2026-11-16 21:26 定）：
  Bad Case 有生成层、检索层、安全边界层、性能层四类，Agent 会按实际情况选方向（例如调整回答提示词），不只修检索。
  本扫描只量得出"检索层"的可修空间，所以输出的 GO / NO-GO 只是检索层的参考信号，不作为启动 Baseline 或 Agent 的硬条件。
  参考口径：可修空间 ≥ --min-fixable（默认 5）道，且至少有一个符合 Agent 改动上限的配置能补回 ≥3 道、同时弄丢的题 ≤1 道 → GO。

PYTHONPATH=backend python3 backend/scripts/retrieval_headroom.py --csv 指挥/报告/049-新题卷定稿.csv --output 指挥/报告/050-检索可修空间.csv
  --smoke：只扫 3 道题 × 2 个配置，先确认能跑通（几乎不花钱）。
"""
import argparse
import csv
import io
import json
import os
from itertools import combinations
from statistics import median_low

from app import rules
from pathlib import Path

RETRIEVAL_KEYS = ('candidate_k', 'top_k', 'min_score', 'hybrid_search', 'hybrid_alpha', 'rerank',
                  'query_rewrite', 'multi_query', 'hyde', 'query_decompose', 'retrieval_max_tokens')


def golden_questions(csv_bytes):
    """从题卷 CSV 取正向题和消融题：题号、问题、标准证据切块。"""
    rows = list(csv.DictReader(io.StringIO(csv_bytes.decode('utf-8-sig'), newline='')))
    items = []
    for row in rows:
        if row['题型'].strip() not in {'positive', 'ablation'}:
            continue
        ids, quotes = [], {}
        for line in (row.get('证据') or '').splitlines():
            chunk_id, sep, quote = line.partition('｜')
            if sep and chunk_id.strip():
                if chunk_id.strip() not in ids:
                    ids.append(chunk_id.strip())
                if quote.strip():
                    quotes.setdefault(chunk_id.strip(), []).append(quote.strip())
        if not ids:
            raise ValueError(f"{row['题号']} 没有标准证据切块，无法扫描")
        items.append({'qid': row['题号'].strip(), 'group': row['题型'].strip(), 'method': row.get('出题方式', '').strip(),
                      'question': row['问题'].strip(), 'golden': ids, 'quotes': quotes})
    return items


def single_variants(baseline, space):
    """每个检索参数的每个可选值各改一次（相对 Baseline 只改 1 个参数）。"""
    variants = []
    for key in RETRIEVAL_KEYS:
        for value in space.get(key, ()):
            if value != baseline.get(key):
                variants.append({key: value})
    return variants


def _norm(text):
    import re, unicodedata
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', str(text or '')))


def hit_of(evidence, golden, quotes=None):
    """标准子块是否进了最终资料。父子切块交付父块全文，matched_child_ids 只记被命中的子块（069 发现）：
    按 ID 找不到时，标准原文全部出现在某条资料全文里也算进入（与 agent_inputs.evidence_positions 同口径）。"""
    quotes = quotes or {}
    ranks = []
    for g in golden:
        rank = None
        for index, entry in enumerate(evidence, 1):
            if entry.get('chunk_id') == g or g in (entry.get('matched_child_ids') or []):
                rank = index; break
        if rank is None and quotes.get(g):
            wanted = [_norm(q) for q in quotes[g] if _norm(q)]
            for index, entry in enumerate(evidence, 1):
                body = _norm(entry.get('content') or entry.get('chunk_text') or entry.get('text') or '')
                if wanted and body and all(q in body for q in wanted):
                    rank = index; break
        if rank is not None:
            ranks.append(rank)
    final_ids = ['/'.join([e.get('chunk_id') or '?', *(e.get('matched_child_ids') or [])]) for e in evidence]
    return {'all_hit': len(ranks) == len(golden), 'rank': min(ranks) if ranks else None, 'n_context': len(evidence), 'final_ids': final_ids}


def scan(items, baseline, variants, retrieve):
    """retrieve(question, config) -> 最终交给模型的资料列表。返回 {配置名: {题号: hit}}。"""
    from app.ai_service import generation_context

    def label(change):
        return 'baseline' if not change else ' + '.join(f'{k}={json.dumps(v)}' for k, v in sorted(change.items()))
    results = {}
    for change in [{}, *variants]:
        config = {**baseline, **change}
        hits = {}
        for item in items:
            context = retrieve(item['question'], config)
            hit = hit_of(context, item['golden'], item.get('quotes'))
            if all(isinstance(entry.get('content'), str) for entry in context):
                hit['context_fingerprint'] = rules.canonical_hash(generation_context(context))
            hits[item['qid']] = hit
        results[label(change)] = {'change': change, 'hits': hits}
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
    limit = rules.AGENT['max_changed_parameters']
    strong = [r for r in rows if r['n_params'] <= limit and len(r['fixed']) >= min_single and len(r['lost']) <= max_lost]
    verdict = 'GO' if len(fixable) >= min_fixable and strong else 'NO-GO'
    return {'verdict': verdict, 'note': '仅检索层参考信号，不作为启动条件', 'rule': f'可修空间≥{min_fixable} 且存在 ≤{limit} 参数配置补回≥{min_single}、弄丢≤{max_lost}',
            'baseline_gap': gap, 'fixable': fixable, 'unfixable_gap': sorted(set(gap) - set(fixable)),
            'best_configs': rows[:8], 'strong_configs': [r['config'] for r in strong]}


def write_table(path, items, results):
    names = list(results)
    with open(path, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['题号', '题型', '出题方式', '标准证据', *names, 'Baseline最终资料（父块/命中子块）'])
        for item in items:
            cells = []
            for n in names:
                h = results[n]['hits'][item['qid']]
                cells.append(('✓' if h['all_hit'] else '✗') + (f" #{h['rank']}" if h['rank'] else ''))
            w.writerow([item['qid'], item['group'], item['method'], ' '.join(item['golden']), *cells, ' | '.join(results['baseline']['hits'][item['qid']].get('final_ids') or [])])


def build_preview(baseline_run_id, items, results):
    """给 Agent 的检索预演表（2026-11-19 用户确认）：每个配置相对 Baseline，哪些题的标准证据会进入 / 掉出最终资料。
    只检索、不生成、不判分，结果确定；它只说明检索层，生成和判分仍要在 Sandbox 里验证。"""
    base = results['baseline']['hits']
    configs = []
    limit = rules.AGENT['max_changed_parameters']
    for name, data in results.items():
        if name == 'baseline' or len(data['change']) > limit:
            continue
        hits = data['hits']
        enters = sorted(q for q, h in base.items() if not h['all_hit'] and hits[q]['all_hit'])
        lost = sorted(q for q, h in base.items() if h['all_hit'] and not hits[q]['all_hit'])
        context = {q: h['context_fingerprint'] for q, h in hits.items() if h.get('context_fingerprint')}
        changed = sorted(q for q, fingerprint in context.items() if base[q].get('context_fingerprint')
                         and base[q]['context_fingerprint'] != fingerprint)
        configs.append({'change': data['change'], 'evidence_enters_final': enters, 'evidence_lost_from_final': lost,
                        'net': len(enters) - len(lost), 'context_changed_question_ids': changed, 'context_fingerprints': context})
    configs.sort(key=lambda c: (-c['net'], len(c['change']), json.dumps(c['change'], sort_keys=True)))
    return {'baseline_run_id': baseline_run_id, 'kind': 'retrieval_preview',
            'note': '只检索不生成：说明改某个参数后标准证据进不进最终资料。证据进来不等于一定答对，掉出去大概率答错；生成层和负向题不在预演范围。',
            'context_fingerprints': {q: h['context_fingerprint'] for q, h in base.items() if h.get('context_fingerprint')},
            'baseline_evidence': {item['qid']: {'group': item['group'], 'method': item['method'], 'all_hit': base[item['qid']]['all_hit'], 'rank': base[item['qid']]['rank']} for item in items},
            'configs': configs}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--csv', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--database', type=Path)
    parser.add_argument('--smoke', action='store_true')
    parser.add_argument('--preview-for-baseline', help='把逐配置预演结果存成 Agent 输入：data/retrieval_preview/<Baseline run ID>.json')
    parser.add_argument('--pairs', type=int, default=4, help='单参数收益最大的前 N 个两两组合再扫')
    parser.add_argument('--min-fixable', type=int, default=5)
    args = parser.parse_args(argv)
    from app.config import load_values
    database = args.database or Path(load_values().get('RAG_DEMO_DB_PATH') or Path(__file__).resolve().parents[1] / 'data/demo.db')
    os.environ['RAG_DEMO_DB_PATH'] = str(database.resolve())
    os.environ['RAG_SAFE_START'] = '1'
    from app.main import ai_service
    from app.policy import ALLOWED_SEARCH_SPACE, FRIEND_BASELINE_CONFIG
    if not ai_service.live_enabled:
        raise SystemExit('需要真实的 embedding / rerank / DeepSeek 配置；当前是 Mock，扫描结果没有意义')
    baseline = dict(FRIEND_BASELINE_CONFIG)  # 2026-11-18：Baseline 用朋友式朴素默认配置
    # 与正式 Baseline（evaluation._baseline_inputs）一致：绑定当前活动索引的知识身份，否则会退回旧版 legacy 索引
    index_info = ai_service.corpus.index_info() or {}
    identity = index_info.get('knowledge_identity')
    if not identity:
        raise SystemExit('当前活动索引没有知识身份，扫描会落到旧版索引；请先确认 062 的 v3 索引已生效')
    items = golden_questions(args.csv.read_bytes())

    def retrieve(question, config):
        return ai_service.retrieve_context(question, {**config, 'knowledge_identity': identity})[0]

    space = ALLOWED_SEARCH_SPACE
    wide_k = max(space['candidate_k'])
    if args.smoke:
        items, variants = items[:3], [{'candidate_k': wide_k}]
        return {'smoke': True, 'knowledge_identity': identity, 'index_chunks': len(ai_service.corpus.chunks()), 'baseline_config': baseline, 'results': scan(items, baseline, variants, retrieve)}
    singles = single_variants(baseline, ALLOWED_SEARCH_SPACE)
    results = scan(items, baseline, singles, retrieve)
    best = [r for r in summarize(results)['best_configs'] if r['net'] > 0][:args.pairs]
    pairs = []
    for a, b in combinations(best, 2):
        change = {**results[a['config']]['change'], **results[b['config']]['change']}
        if len(change) == 2:
            pairs.append(change)
    # 2026-11-19（081 审核）：父子切块下 Top-K 数的是父块，Top-K=4 会把"候选召回变多"的收益全部挡住，
    # 所以 candidate_k / multi_query / 问题拆解 / HyDE 单独看永远是 0，不会进入上面的两两组合。
    # 固定补扫"Top-K 放到最大 + 一个召回类参数"（Colin A 轮就是 candidate_k 24 + top_k 6），让扫描和给 Agent 的预演都看得到。
    widest = max(ALLOWED_SEARCH_SPACE.get('top_k', (baseline.get('top_k'),)))
    middle_score = median_low(space['min_score'])
    partners = [('candidate_k', wide_k),
                ('multi_query', median_low([v for v in space['multi_query'] if type(v) is int])),
                ('query_decompose', True), ('hyde', True), ('query_rewrite', True), ('min_score', middle_score)]
    if widest != baseline.get('top_k'):
        for key, value in partners:
            if value in ALLOWED_SEARCH_SPACE.get(key, ()) and value != baseline.get(key):
                change = {'top_k': widest, key: value}
                if change not in pairs:
                    pairs.append(change)
    # 2026-11-19（085 审核）：Top-K=6 + 单个召回参数仍补不回"一次问全"题——第 5 个父块的子块要么不在 12 个候选里，要么重排分低于 0.4。
    # 朋友的 A 轮一次改 2～5 个参数（扣子 A/B/C 改 4～5 个），所以再固定补扫几组"整体放宽检索"的三四参数组合。
    widest_config = {'top_k': widest, 'candidate_k': wide_k, 'min_score': middle_score}
    wide_combos = [widest_config, {**widest_config, 'min_score': min(space['min_score'])},
                   *({**widest_config, key: value} for key, value in partners[1:-1])]
    for extra in wide_combos:
        change = {k: v for k, v in extra.items() if v in ALLOWED_SEARCH_SPACE.get(k, ()) and v != baseline.get(k)}
        if len(change) >= 3 and change not in pairs:
            pairs.append(change)
    if pairs:
        results.update({k: v for k, v in scan(items, baseline, pairs, retrieve).items() if k != 'baseline'})
    summary = summarize(results, min_fixable=args.min_fixable)
    if args.output:
        write_table(args.output, items, results)
    if args.preview_for_baseline:
        target = database.resolve().parent / 'retrieval_preview' / f'{args.preview_for_baseline}.json'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(build_preview(args.preview_for_baseline, items, results), ensure_ascii=False, indent=1), encoding='utf-8')
        summary['preview_file'] = str(target)
    return {'knowledge_identity': identity, 'baseline_config': {k: baseline[k] for k in RETRIEVAL_KEYS}, 'questions': len(items), 'configs': len(results), **summary}


if __name__ == '__main__':
    print(json.dumps(main(), ensure_ascii=False, indent=1, default=str), flush=True)
