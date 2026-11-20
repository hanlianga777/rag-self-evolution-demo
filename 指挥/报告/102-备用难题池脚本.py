"""总指挥出的备用难题池（2026-11-20，在第一次 Baseline 之前写好并提交；规则总表二.7）。

每道备用题与它要替换的"易"题：同一簇、同一题型，只把难度从"易"提到"中/难"（要点更多、要比较或要带条件）。
替换顺序固定：R1→Q01、R2→Q20、R3→Q03、R4→Q02、R5→Q06。由 102-加难脚本.py 执行，不临时出新题。
"""
import csv, re, sys, unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / 'backend'))
from app.golden_v2 import friend_answer_supported

CHUNKS = {r['chunk_id']: r['切块原文'].replace('\\n', '\n') for r in csv.DictReader(open(HERE / '100-切块全量.csv', encoding='utf-8-sig'))}
S, M1, M5 = 'DOC-41ed759faa12', 'DOC-8c302b249b5b', 'DOC-7cf7d0fd4182'
st = lambda v: re.sub(r'\s+', '', unicodedata.normalize('NFKC', v))
FIELDS = ['替换槽位', '备用号', '题型', '出题方式', '问题', '参考答案', '证据', '难度', '簇', '备注']


def loc(doc, quote):
    hits = [c for c in CHUNKS if c.startswith(doc + '-V2-C-') and st(quote) in st(CHUNKS[c])]
    if not hits: raise SystemExit(f'找不到 {doc} {quote}')
    return hits[0]


POOL = [
    ('Q01', 'R1', 'positive', '单段标准', 'IRB 1300 四个型号的标称重量各是多少？这个重量包含安装在机械臂上的工具和其他设备吗？',
     '1. IRB 1300-11/0.9：75 kg。\n2. IRB 1300-10/1.15：77 kg。\n3. IRB 1300-7/1.4：79 kg。\n4. IRB 1300-12/1.4：79 kg。\n该重量不包括安装在机械臂上的额外选项、工具和其他设备。',
     [(M1, 'IRB 1300-11/0.9: 75 kg'), (M1, 'IRB 1300-10/1.15: 77 kg'), (M1, 'IRB 1300-7/1.4: 79 kg'), (M1, 'IRB 1300-12/1.4: 79 kg'), (M1, '该重量不包括安装在机械臂上的额外选项、工具和其他设备。')], '中', 'T007'),
    ('Q20', 'R2', 'positive', '台账事实', 'IRB 1300 机械臂的防护类型 Standard、Foundry Plus 2、Clean Room，以及带电磁阀的机械臂，各自的保护等级或洁净等级是什么？',
     '1. Standard：IP40，可选 IP67（option 3350-670）。\n2. Foundry Plus 2：IP67。\n3. Clean Room：ISO 4。\n4. 带有电磁阀的机械臂（选件）：IP40，可选 IP67（option 3350-670）。',
     [(M1, '防护类型=机械臂,防护类型 Standard；保护等级i/适用性等级ii=IP40IP67 (option 3350-670)'), (M1, '防护类型=机械臂,防护类型 Foundry Plus 2；保护等级i/适用性等级ii=IP67'),
      (M1, '防护类型=机械臂,防护类型 Clean Room；保护等级i/适用性等级ii=ISO 4'), (M1, '防护类型=带有电磁阀的机械臂(选件)；保护等级i/适用性等级ii=IP40IP67 (option 3350-670)')], '中', 'T002'),
    ('Q03', 'R3', 'positive', '单段标准', 'IRB 1300 不是落地安装时，Gravity Beta 和 Gravity Alpha 分别在什么情况下要重新定义、设为多少？安装角度定义错会有什么后果？',
     '1. 采用落地安装以外方式安装时，机器人基座和 Gravity Beta 必须重新定义：倒置安装为 π（+3.141593），墙上安装为 ±π/2（±1.570796）。\n2. 机器人装在墙壁上（绕 X 轴旋转）时，还要重新定义 Gravity Alpha，数值宜为 ±π/2（±1.570796）。\n3. 安装角度定义不正确会导致：机械结构过载；路径性能和路径精确度较低；Load Identification、Collision detection 等功能无法正常工作。',
     [(M1, '采用落地安装（绕y轴旋转）以外方式安装机器人时，机器人基座和系统参数GravityBeta 均必须重新定义。'), (M1, '如果机器人倒置安装（倒置），则 Gravity Beta 应为 π （+3.141593）。'), (M1, '如果机器人安装在墙上，那么 Gravity Beta 应为 ±π/2 (±1.570796)。'),
      (M1, '若机器人装设在墙壁上（绕X轴旋转），就必须重新定义此机器人的基准坐标系和系统参数Gravity Alpha。之后Gravity Alpha的数值宜为±π/2（±1.570796）。'),
      (M1, '• 机械结构过载。'), (M1, '• 路径性能和路径精确度较低。'), (M1, '• 某些功能将无法正常工作，例如 Load Identification 和 Collision detection。')], '难', 'T005'),
    ('Q02', 'R4', 'positive', '单段标准', 'IRB 1200-5/0.9 和 IRB 1200-7/0.7 的位姿可重复性 RP 和线性路径精确度 AT 各是多少？哪一款的线性路径精确度数值更小？',
     '1. IRB 1200 5/0.9：位姿可重复性 RP 0.025 mm，线性路径精确度 AT 0.53 mm。\n2. IRB 1200-7/0.7：位姿可重复性 RP 0.02 mm，线性路径精确度 AT 0.77 mm。\n3. 线性路径精确度 AT：5/0.9 为 0.53 mm，小于 7/0.7 的 0.77 mm。',
     [(S, '位姿可重复性,RP (mm) | 0.025 | 0.02'), (S, '线性路径精确度,AT (mm) | 0.53 | 0.77'), (S, 'IRB 1200 - 5/0.9 | IRB 1200-7/0.7')], '中', 'T001'),
    ('Q06', 'R5', 'positive', '单段标准', 'Axis Calibration 校准工具在使用前和定期检查时分别要检查什么？定期检查的外径和平直度要求是多少？',
     '1. 使用前：确保管套已插入、塑料保护件与钢弹簧环也无缺失；任何部分缺失或损坏，工具必须立即更换。\n2. 定期检查：外径在 Ø12g4 mm、Ø8g4 mm 或 Ø6g5 mm 以内（取决于校准工具大小）。\n3. 平直度在 0.005 mm 以内。',
     [(M5, '在使用校准工具前，确保管套已插入、塑料保护件与钢弹簧环也无缺失。'), (M5, '如果任何部分缺失或损坏，工具必须立即更换。'), (M5, '外径在 Ø12g4 mm、Ø8g4 mm 或 Ø6g5 mm 以内（取决于校准工具大小）。'), (M5, '平直度在 0.005 mm 以内。')], '中', 'T009'),
]

rows, bad = [], []
for slot, rid, group, method, q, a, ev, diff, cl in POOL:
    allhits = [[c for c in CHUNKS if c.startswith(d + '-V2-C-') and st(t) in st(CHUNKS[c])] for d, t in ev]
    if not all(allhits): raise SystemExit(f'找不到 {rid}')
    pairs = [(max(h, key=lambda c: (sum(c in x for x in allhits), -h.index(c))), t) for h, (d, t) in zip(allhits, ev)]
    ids = list(dict.fromkeys(c for c, _ in pairs))
    if not friend_answer_supported(a, [{'chunk_text': CHUNKS[i], 'text': CHUNKS[i]} for i in ids]):
        bad.append(rid)
    rows.append(dict(zip(FIELDS, [slot, rid, group, method, q, a, '\n'.join(f'{c}｜{t}' for c, t in pairs), diff, cl, '102 备用难题池（Baseline 前写定）'])))
print('答案锚点不过：', bad or '无', len(rows))
with open(HERE / '102-备用难题池.csv', 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader(); w.writerows(rows)
