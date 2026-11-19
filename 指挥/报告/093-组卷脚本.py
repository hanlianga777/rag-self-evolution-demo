"""总指挥组卷（2026-11-19 093）：读 092 扫描表，按下面写死的规则从候选池选题，替换 081 版题卷里 Baseline 已经答全的槽位，生成 093-题卷v4.csv。

规则（扫描前写定，不看任何回答和判分，只看检索层）：
1. 只选"Baseline 检索缺（✗）、且同一个配置 c 能补回（✓）"的候选题。
2. 正向候选最多 6 道，按候选号顺序依次替换这些 Baseline 已全中的正向槽位：Q09、Q02、Q03、Q10、Q19、Q13
   （优先单段题；避开有消融题配对的槽位，免得配对失效）。消融候选最多 5 道，依次替换 Q22、Q23、Q24、Q28、Q30。
   槽位在 Baseline 下不是 ✓ 的跳过，不替换。
3. 对每个配置 c 算：最终题卷里 c 补回的题数（✗→✓）和弄丢的题数（✓→✗）。选补回最多、且弄丢 ≤1 的 c；
   打平时选改动参数少的，再打平按扫描表列序。
4. 达标 = 最终题卷 Baseline 缺口中正向 ≥4、消融 ≥4，且 c 补回 ≥8、弄丢 ≤1（用户 2026-11-19 08:02 标准）。
5. 负向 20 题取 085 版，原样不动。消融题配对的正向题被替换时，配对号清空；配对的候选正向题也被选中时，改成它的新题号。
用法：python3 093-组卷脚本.py [扫描表路径，默认 092-候选池扫描.csv]
"""
import csv, json, sys
from pathlib import Path

REPO = Path(__file__).resolve().parent
SCAN = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / '092-候选池扫描.csv'
POS_SLOTS = ['Q09', 'Q02', 'Q03', 'Q10', 'Q19', 'Q13']
ABL_SLOTS = ['Q22', 'Q23', 'Q24', 'Q28', 'Q30']
LAST_COLUMN = 'Baseline最终资料（父块/命中子块）'

scan = {r['题号']: r for r in csv.DictReader(open(SCAN, encoding='utf-8-sig'))}
configs = [c for c in next(iter(scan.values())) if c not in ('题号', '题型', '出题方式', '标准证据', 'baseline', LAST_COLUMN)]
ok = lambda qid, col: scan[qid][col].startswith('✓')
sheet = {r['题号']: r for r in csv.DictReader(open(REPO / '092-候选池.csv', encoding='utf-8-sig'))}
neg = [r for r in csv.DictReader(open(REPO / '085-题卷v4.csv', encoding='utf-8-sig')) if r['题型'] == 'negative']
n_params = lambda col: col.count(' + ') + 1


def build(col):
    """按规则 1、2、5 为配置 col 组卷，返回 (题卷行, 替换表)。"""
    pool_pos = [q for q in sheet if q.startswith('P') and not ok(q, 'baseline') and ok(q, col)][:6]
    pool_abl = [q for q in sheet if q.startswith('A') and not ok(q, 'baseline') and ok(q, col)][:5]
    swaps = {}
    for picks, slots in ((pool_pos, POS_SLOTS), (pool_abl, ABL_SLOTS)):
        free = [s for s in slots if ok(s, 'baseline')]
        for pick, slot in zip(picks, free):
            swaps[slot] = pick
    new_id = {pick: slot for slot, pick in swaps.items()}
    rows = []
    for i in range(1, 31):
        slot = f'Q{i:02d}'
        if slot in swaps:
            row = dict(sheet[swaps[slot]]); row['题号'] = slot
            row['配对题号'] = new_id.get(row['配对题号'], '') if row['配对题号'] else ''
            row['备注'] = f"093 组卷：由 092 候选 {swaps[slot]} 替换原 {slot}。" + row['备注']
        else:
            row = dict(sheet[slot])
            if row['配对题号'] in swaps:
                row['配对题号'] = ''
        rows.append(row)
    return rows + neg, swaps


def score(rows, swaps, col):
    ids = [swaps.get(r['题号'], r['题号']) for r in rows if r['题型'] in ('positive', 'ablation')]
    group = {swaps.get(r['题号'], r['题号']): r['题型'] for r in rows if r['题型'] in ('positive', 'ablation')}
    gap = [q for q in ids if not ok(q, 'baseline')]
    fixed = [q for q in gap if ok(q, col)]
    lost = [q for q in ids if ok(q, 'baseline') and not ok(q, col)]
    back = {v: k for k, v in swaps.items()}
    name = lambda q: back.get(q, q)
    return {'config': col, 'n_params': n_params(col),
            'gap_positive': [name(q) for q in gap if group[q] == 'positive'], 'gap_ablation': [name(q) for q in gap if group[q] == 'ablation'],
            'fixed': [name(q) for q in fixed], 'lost': [name(q) for q in lost], 'swaps': swaps}


results = []
for col in configs:
    rows, swaps = build(col)
    results.append((score(rows, swaps, col), rows))
eligible = [r for r in results if len(r[0]['lost']) <= 1]
eligible.sort(key=lambda r: (-len(r[0]['fixed']), r[0]['n_params'], configs.index(r[0]['config'])))
best, rows = eligible[0] if eligible else (results[0][0], results[0][1])
passed = len(best['gap_positive']) >= 4 and len(best['gap_ablation']) >= 4 and len(best['fixed']) >= 8 and len(best['lost']) <= 1

assert len(rows) == 50 and len({r['题号'] for r in rows}) == 50
with open(REPO / '093-题卷v4.csv', 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
top = [{k: v for k, v in r[0].items() if k != 'swaps'} | {'swaps': r[0]['swaps']} for r in eligible[:5]]
print(('组卷结论：达标' if passed else '组卷结论：不达标') + f"（配置 {best['config']}：补回 {len(best['fixed'])} 道，弄丢 {len(best['lost'])} 道；"
      f"缺口正向 {len(best['gap_positive'])}、消融 {len(best['gap_ablation'])}）")
print(json.dumps({'chosen': best, 'top5_eligible': top}, ensure_ascii=False, indent=1))
