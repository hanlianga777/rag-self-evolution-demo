"""总指挥出题候选池（2026-11-19 092）：081/085/089 三次扫描说明，v2 大父块下"答案要 5 个父块"的题任何检索配置都补不回，
"答案在 1～2 个父块"的题 Baseline 几乎全中。唯一被调参补回的是 Q20 这类：答案只有一行、独一份，但同一批关键词（防护类型、IP67、型号、
货号）在维修手册里出现几十次，标准父块被挤到第 5、6 名。候选池按这个规律出 16 道正向、12 道消融，扫描后按预先写好的规则选入正式题卷：
只选"Baseline 检索缺、且同一个配置能补回"的题，选法和理由写进 092 报告。不进正式题卷的候选不用于任何评测。"""
import csv, re, sys, unicodedata
sys.path.insert(0, '/home/claude/rag-self-evolution-demo/backend')
from app.golden_v2 import friend_answer_supported
from app.reviewed_import import validate_friend_content
REPO = '/home/claude/rag-self-evolution-demo/指挥/报告/'
chunks = {r['chunk_id']: r['切块原文'].replace('\\n', '\n') for r in csv.DictReader(open(REPO + '080-切块全量.csv', encoding='utf-8-sig'))}
S, M1, A4 = 'DOC-41ed759faa12', 'DOC-8c302b249b5b', 'DOC-aa04015f71fb'
st = lambda v: re.sub(r'\s+', '', unicodedata.normalize('NFKC', v))
def loc(doc, quote):
    hits = [c for c in chunks if c.startswith(doc + '-V2-C-') and st(quote) in st(chunks[c])]
    if not hits: raise SystemExit(f'找不到：{doc} {quote}')
    return hits[0]
P = []
ALIAS = {'A01': ('IRB 1300-7/1.4 Type A', '1.4 米臂展的新款 A 型 1300'), 'A05': ('IRB 1300-11/0.9', '1300 里臂展最短的那款')}
def add(qid, group, method, attr, pair, q, a, ev, note):
    P.append((qid, group, method, attr, pair, q, a, [(loc(d, t), t) for d, t in ev], note))

E01 = [(M1, '备件=主电缆线束,L,基础,适用于 Type A；货号=3HAC099153-001；注释=与 IRB 1300-7/1.4 和 IRB 1300-12/1.4一起使用。')]
add('P01','positive','台账事实','','','IRB 1300-7/1.4 的 Type A 机型，基础款主电缆线束的备件号是多少？',
    '基础款主电缆线束（L，适用于 Type A）的备件号是 3HAC099153-001，与 IRB 1300-7/1.4 和 IRB 1300-12/1.4 一起使用。', E01, '备件清单里同名线束有 S/M/L、标准/Type A 共 18 行')
E02 = [(M1, 'i For robots installed with solenoid valves (option 3303-3), the minimum allowed ambient temperature is -10°C (14°F).'),
       (M1, 'ii For robots installed with solenoid valves (option 3303-3), the maximum allowed ambient temperature is +50°C (+122°F).'),
       (M1, 'iii 对于安装有电磁阀（选件 3303-3）的机器人，允许的最大环境湿度为 20% 至 80%，在恒定温度下不允许有露水凝结。')]
add('P02','positive','单段标准','','','安装了电磁阀（选件 3303-3）的 IRB 1300，储存时允许的最低、最高环境温度和环境湿度是多少？',
    '1. 最低环境温度：-10°C（14°F）。\n2. 最高环境温度：+50°C（+122°F）。\n3. 最大环境湿度：20% 至 80%，在恒定温度下不允许有露水凝结。', E02, '脚注藏在储存条件表下，和操作条件表、标准机型数值并排')
E03 = [(S, '数据=空气传播的噪音水平；描述=外界声压水平；注释=< 70 dB (A) Leq(根据工作空间机器指令 2006/42/EG)')]
add('P03','positive','单段标准','','','IRB 1200 的空气传播噪音水平是多少？',
    '空气传播的噪音水平：外界声压水平 < 70 dB (A) Leq（根据工作空间机器指令 2006/42/EG）。', E03, '一行数据')
E04 = [(S, '防护类型=机械臂,防护类型 Hygienic；保护等级i/适用性等级ii=IP67IP69K(最大30巴),在轴6法兰上'),
       (S, '防护类型=机械臂,防护类型 Clean Room；保护等级i/适用性等级ii=ISO Class 3(选项287-1,配备IRC5控制器)')]
add('P04','positive','单段标准','','','IRB 1200 防护类型 Hygienic 的保护等级是什么？防护类型 Clean Room 呢？',
    '1. Hygienic：IP67、IP69K（最大30巴），在轴6法兰上。\n2. Clean Room：ISO Class 3（选项287-1，配备IRC5控制器）。', E04, '与 Q20 同类：防护类型在两本手册几十处出现')
E05 = [(M1, '轴=轴2；工作范围=IRB 1300-10/1.15, IRB 1300-7/1.4 and IRB 1300-12/1.4 -95°/+155° IRB 1300-11/0.9 -100°/+130°'),
       (M1, '轴=轴3；工作范围=IRB 1300-7/1.4 and IRB 1300-12/1.4 -210°/+69° IRB 1300-10/1.15 and IRB 1300-11/0.9 -210°/+65°')]
add('P05','positive','单段标准','','','IRB 1300-11/0.9 的轴 2 和轴 3 工作范围各是多少？',
    '1. 轴 2：-100°/+130°。\n2. 轴 3：-210°/+65°。', E05, '同格多个型号数值并排')
E06 = [(S, '动作位置=轴2；动作类型=手臂动作；IRB 1200-7/0.7=+135°至-100°；IRB 1200-5/0.9=+130° to -100°'),
       (S, '动作位置=轴5；动作类型=弯曲动作；IRB 1200-7/0.7=±130°(非 Hygienic 机器人)±128°(Hygienic 机器人)；IRB 1200-5/0.9=±130° (not Hygienic robots)±128° (Hygienic robots)')]
add('P06','positive','单段标准','','','IRB 1200-5/0.9 的轴 2 和轴 5 工作范围各是多少？',
    '1. 轴 2：+130° 到 -100°。\n2. 轴 5：±130°（Hygienic 机器人为 ±128°）。', E06, '同表另一列是 7/0.7')
E07 = [(M1, '请勿将电池短接、充电、刺穿、焚烧、粉碎、浸泡、强行放电或置于超过产品的规定工作温度范围的温度下。这些可能造成火灾或爆炸危险。'),
       (M1, '有关电池的说明请参见Material/product safety data sheet - Battery pack（3HAC043118-001）。')]
add('P07','positive','单段标准','','','IRB 1300 的电池组在使用上有哪些禁忌？电池安全数据表的文件号是多少？',
    '1. 请勿将电池短接、充电、刺穿、焚烧、粉碎、浸泡、强行放电或置于超过产品的规定工作温度范围的温度下，这些可能造成火灾或爆炸危险。\n2. 电池说明请参见 Material/product safety data sheet - Battery pack（3HAC043118-001）。', E07, '电池在维护、维修、更换章节反复出现')
E09 = [(M1, '机型=IRB 1300-11/0.9；最大机械臂负载 (kg)=1'), (M1, '机型=IRB 1300-12/1.4；最大机械臂负载 (kg)=1')]
add('P09','positive','台账事实','','','IRB 1300 各型号机械臂上允许的最大负载是多少？',
    'IRB 1300-11/0.9、IRB 1300-10/1.15、IRB 1300-7/1.4、IRB 1300-12/1.4 的最大机械臂负载都是 1 kg。',
    E09 + [(M1, '机型=IRB 1300-10/1.15；最大机械臂负载 (kg)=1'), (M1, '机型=IRB 1300-7/1.4；最大机械臂负载 (kg)=1')], '"负载"一词遍布载荷图、有效载荷章节')
E10 = [(S, '机器人型号=IRB 1200-7/0.7；轴4和轴5的最大肘节转矩=12.5 Nm；轴6的最大肘节转矩=6.2 Nm；载荷时的最大有效转矩=7 kg')]
add('P10','positive','台账事实','','','IRB 1200-7/0.7 轴 4、轴 5 和轴 6 的最大肘节转矩各是多少？',
    '1. 轴 4 和轴 5：12.5 Nm。\n2. 轴 6：6.2 Nm。', E10, '同表 5/0.9 为 8.9 / 4.4 Nm')
E11 = [(M1, 'IP67(选件) | 是 | 是。使用温和的清洁剂。 | 是。强烈推荐在水中加入防锈剂溶液,并且在清洁后对机械臂进行干燥。 | 否')]
add('P11','positive','单段标准','','','防护等级 IP67（选件）的 IRB 1300 可以用水冲洗吗？能用高压水吗？',
    '1. 可以用水冲洗，强烈推荐在水中加入防锈剂溶液，并且在清洁后对机械臂进行干燥。\n2. 不能使用高压水、蒸汽或喷剂。\n3. 也可以用真空吸尘器，或用布蘸温和的清洁剂擦拭。', E11, '清洁方法表一行，Clean Room 行规定相反')
E12 = [(S, '机器人具有食品级润滑(NSFH1)供选用。配食品级润滑的机器人的保护类型是CleanRoom 和 IP67。'),
       (S, '参数=最高环境温度用于采用食品级润滑的机器人用于防护类型 Hygienic 的机器人；值=+35°C ii')]
add('P12','positive','跨段综合','','','IRB 1200 选食品级润滑（NSFH1）时，机器人是什么保护类型？允许的最高运行环境温度是多少？',
    '1. 配食品级润滑的机器人保护类型是 CleanRoom 和 IP67。\n2. 采用食品级润滑的机器人最高环境温度为 +35°C。', E12, '选项说明与操作条件表分在两章')
E14 = [(A4, '备件=电机装置,轴2 (IRB 1300-12/1.4),适用于 Type A；货号=3HAC099134-001；注释=用于 IRB 1300-12/1.4。')]
add('P14','positive','台账事实','','','IRB 1300-12/1.4 的 Type A 机型，轴 2 电机装置的备件号是多少？',
    '轴 2 电机装置（IRB 1300-12/1.4，适用于 Type A）的备件号是 3HAC099134-001。', E14, '同表 4 行轴 2 电机，标准/Type A、12/1.4/其他型号交叉')
E15 = [(A4, '备件=电机装置,轴3 (IRB 1300-12/1.4)；货号=3HAC082079-001；注释=用于 IRB 1300-12/1.4。')]
add('P15','positive','台账事实','','','IRB 1300-12/1.4（标准型，非 Type A）轴 3 电机装置的备件号是多少？',
    '轴 3 电机装置（IRB 1300-12/1.4）的备件号是 3HAC082079-001。', E15, '同上')
E16 = [(A4, '备件=电机装置,轴6,适用于 Type A；货号=3HAC099139-001')]
add('P16','positive','台账事实','','','IRB 1300 Type A 机型轴 6 电机装置的备件号是多少？',
    '轴 6 电机装置（适用于 Type A）的备件号是 3HAC099139-001。', E16, '标准型轴 5、轴 6 共用 3HAC073088-001，易混')

# ---- 消融候选（口语 / 别名 / 弱关键词），证据同配对正向题 ----
add('A01','ablation','别名变体','alias_entity','P01','1.4 米臂展的新款 A 型 1300，最基础那根主电缆总成订哪个料号？',
    '基础款主电缆线束（L，适用于 Type A）的备件号是 3HAC099153-001，与 IRB 1300-7/1.4 和 IRB 1300-12/1.4 一起使用。', E01, '')
add('A02','ablation','口语变体','colloquial','P02','1300 装了电磁阀选件，放仓库里存放的时候，温度和湿度有什么讲究？',
    '1. 最低环境温度：-10°C（14°F）。\n2. 最高环境温度：+50°C（+122°F）。\n3. 最大环境湿度：20% 至 80%，在恒定温度下不允许有露水凝结。', E02, '')
add('A03','ablation','口语变体','colloquial','P03','1200 干起活来吵不吵？大概多少分贝？',
    '空气传播的噪音水平：外界声压水平 < 70 dB (A) Leq（根据工作空间机器指令 2006/42/EG）。', E03, '')
add('A04','ablation','弱关键词变体','weak_keywords','P04','做食品的那种卫生型 1200，防水能做到几级？无尘车间版的洁净等级又是多少？',
    '1. Hygienic：IP67、IP69K（最大30巴），在轴6法兰上。\n2. Clean Room：ISO Class 3（选项287-1，配备IRC5控制器）。', E04, '')
add('A05','ablation','别名变体','alias_entity','P05','1300 里臂展最短的那款，大臂和小臂各能转多大角度？',
    '臂展最短的是 IRB 1300-11/0.9：\n1. 轴 2：-100°/+130°。\n2. 轴 3：-210°/+65°。', E05, '')
add('A06','ablation','弱关键词变体','weak_keywords','P10','1200 那款 7 公斤、0.7 米的，手腕那几个关节最多能扛多大扭矩？',
    '这是 IRB 1200-7/0.7：\n1. 轴 4 和轴 5：12.5 Nm。\n2. 轴 6：6.2 Nm。', E10, '')
add('A07','ablation','口语变体','colloquial','P11','加了 IP67 防水选件的 1300 脏了，能直接拿水冲吗？高压水枪行不行？',
    '1. 可以用水冲洗，强烈推荐在水中加入防锈剂溶液，并且在清洁后对机械臂进行干燥。\n2. 不能使用高压水、蒸汽或喷剂。', E11, '')
add('A08','ablation','口语变体','colloquial','P14','12 公斤那款 1300 是 A 型的，大臂那个关节的电机坏了，订哪个料号？',
    '这是 IRB 1300-12/1.4（Type A）轴 2 电机装置，备件号是 3HAC099134-001。', E14, '')
add('A09','ablation','弱关键词变体','weak_keywords','P09','1300 胳膊上还能额外挂多重的东西？',
    'IRB 1300 各型号的最大机械臂负载都是 1 kg。', E09, '')
add('A10','ablation','口语变体','colloquial','P07','1300 里那块电池平时有什么不能干的？对应的安全资料编号是多少？',
    '1. 请勿将电池短接、充电、刺穿、焚烧、粉碎、浸泡、强行放电或置于超过产品的规定工作温度范围的温度下，这些可能造成火灾或爆炸危险。\n2. 电池说明请参见 Material/product safety data sheet - Battery pack（3HAC043118-001）。', E07, '')
add('A11','ablation','弱关键词变体','weak_keywords','P16','新款 A 型 1300 最末端那个关节的电机，料号是多少？',
    '轴 6 电机装置（适用于 Type A）的备件号是 3HAC099139-001。', E16, '')
add('A12','ablation','口语变体','colloquial','P12','做食品用的 1200 换成食品级润滑油以后，算什么防护类型？车间最热能到多少度？',
    '1. 配食品级润滑的机器人保护类型是 CleanRoom 和 IP67。\n2. 采用食品级润滑的机器人最高环境温度为 +35°C。', E12, '')

FIELDS = ['题号','题型','出题方式','消融类型','原实体','别名','配对题号','负向子类型','预期行为','criticality','问题','参考答案','证据','考查节点','考查参数','难度','关键词','备注','统计条目']
chunk_list = [{'chunk_id': k, 'chunk_text': v} for k, v in chunks.items()]
rows, problems = [], []
for qid, group, method, attr, pair, q, a, ev, note in P:
    cand = {'question': q, 'reference_answer': a, 'test_category': group, 'generation_method': method, 'ablation_attribute': attr or None,
            'evidence': [{'source_chunk_ids': [c], 'evidence_key_points': [t]} for c, t in ev]}
    try: validate_friend_content(cand, chunk_list)
    except ValueError as e: problems.append(f'{qid} {e}')
    if not friend_answer_supported(a, [{'chunk_text': chunks[c], 'text': chunks[c]} for c in dict.fromkeys(c for c, _ in ev)]):
        problems.append(f'{qid} 答案锚点不过')
    rows.append(dict(zip(FIELDS, [qid, group, method, attr, *ALIAS.get(qid, ('', '')), pair, '', '', '', q, a, '\n'.join(f'{c}｜{t}' for c, t in ev),
                                  'retrieval' if group == 'positive' else 'query', 'top_k,hybrid_alpha,hyde', 'hard', '', '092 候选：' + note, ''])))
print('\n'.join(problems) or 'ALL OK', len(rows))
with open(REPO + '092-候选池.csv', 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader(); w.writerows(rows)

# ---- 扫描用整卷：081 版正向/消融 30 题（Q01、Q21 用 085 修过证据的版本）+ 上面 26 道候选，一次扫完、同一套配置列 ----
base81 = {r['题号']: r for r in csv.DictReader(open(REPO + '081-题卷v4.csv', encoding='utf-8-sig'))}
base85 = {r['题号']: r for r in csv.DictReader(open(REPO + '085-题卷v4.csv', encoding='utf-8-sig'))}
base = [base85[q] if q in ('Q01', 'Q21') else base81[q] for q in [f'Q{i:02d}' for i in range(1, 31)]]
with open(REPO + '092-候选池.csv', 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader(); w.writerows(base + rows)
print('scan sheet rows', len(base) + len(rows))
