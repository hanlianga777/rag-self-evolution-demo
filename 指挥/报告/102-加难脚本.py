"""按规则总表二.7 执行受控加难（总指挥 2026-11-20 在第一次 Baseline 之前写定；关卡 2 反审后加了防错检查）。

用法：python3 102-加难脚本.py <轮次 1|2> <本轮 Baseline 错题数>
（只在关卡 4 审核确认错题数口径无误后才运行；每轮生成的新题卷同样要过关卡 2 的双审。）

- 只读取：错题总数、轮次、备用难题池（固定顺序 R1→R5）。不读取任何单题回答、单题分数或 Candidate 结果。
- 第 1 轮：从 M1 生成 M2，替换前 k 道，k = max(1, 5 - 错题数)。
- 第 2 轮：从 M2 生成 M3，接着替换后面的 k 道（同一公式；备用题用完为止）。
- 每道替换前强制检查：同簇、同题型、同出题方式、难度更高；不满足就整轮报错、不输出。
- 替换时同步更新：问题、参考答案、证据、难度、关键词、考查节点、考查参数、统计条目，并在备注写明来源。
"""
import csv, os, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
RANK = {'易': 0, '中': 1, '难': 2}
rnd, errors = int(sys.argv[1]), int(sys.argv[2])
if rnd not in (1, 2):
    raise SystemExit('轮次只能是 1 或 2（规则总表二.7：最多 2 轮）')
if errors >= 5:
    raise SystemExit('错题已 ≥5，不需要加难')
src = HERE / ('102-题卷M1.csv' if rnd == 1 else '102-题卷M2.csv')
dst = HERE / ('102-题卷M2.csv' if rnd == 1 else '102-题卷M3.csv')
rows = list(csv.DictReader(open(src, encoding='utf-8-sig')))
pool = list(csv.DictReader(open(HERE / '102-备用难题池.csv', encoding='utf-8-sig')))
used = {r['题号'] for r in rows if '受控加难' in r['备注']}
pending = [p for p in pool if p['替换槽位'] not in used]
k = max(1, 5 - errors)
take = pending[:k]
if not take:
    raise SystemExit('备用难题池已用完')
by = {r['题号']: r for r in rows}
for p in take:
    r = by[p['替换槽位']]
    checks = {
        '同簇': r['簇'] == p['簇'],
        '同题型': r['题型'] == p['题型'],
        '同出题方式': r['出题方式'] == p['出题方式'],
        '难度更高': RANK[p['难度']] > RANK[r['难度']],
    }
    if not all(checks.values()):
        raise SystemExit(f"{p['备用号']} 替换 {r['题号']} 不满足：{[name for name, ok in checks.items() if not ok]}，本轮不输出")
for p in take:
    r = by[p['替换槽位']]
    old_q = r['问题']
    r.update({'问题': p['问题'], '参考答案': p['参考答案'], '证据': p['证据'], '难度': p['难度'], '统计条目': '',
              '关键词': p['关键词'], '考查节点': p['考查节点'], '考查参数': p['考查参数']})
    r['备注'] = f"受控加难第 {rnd} 轮：由备用题 {p['备用号']} 替换（{p['难度依据']}；原题：{old_q}）。" + r['备注']
fd, tmp = tempfile.mkstemp(dir=HERE, suffix='.csv')
with os.fdopen(fd, 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
os.replace(tmp, dst)
print(f'第 {rnd} 轮：替换 {[p["替换槽位"] for p in take]}，写出 {dst.name}')
