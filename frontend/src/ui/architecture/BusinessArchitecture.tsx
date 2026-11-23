import { Icon, type IconName } from "../icons";
import { Band, C, Defs, Figure, Node, Tag, Wire } from "./svgkit";
import "./architecture.css";

/**
 * 概览 →「业务架构」（11-14 第三版，总指挥编写）。
 *
 * 通用版：不出现任何本项目的数字，换一个客户、换一批文档也成立。
 * 五段自上而下，每段从左往右读；左侧一列是段名，严格对齐：
 * 01 知识准备 → 02 考卷生产（三类题型并排后汇聚）→ 03 评测诊断（四层 Bad Case 并排后汇聚）
 * → 04 Agent 优化（Candidate A/B/C 并排、每轮结论回到下一轮策略、最后合成 Candidate D）
 * → 05 发布与监控（从右往左回流，线上 Bad Case 经人工确认回到考卷候选池）。
 * 三道人工关口用卡片右上角的蓝色徽标表示，不挤占标题位置。
 */

type N = { icon: IconName; title: string; lines: string[]; badge?: string; focus?: boolean; dashed?: boolean };

const VW = 1200;
const LABEL = 120;            // 左侧段名列宽
const X0 = 8 + LABEL;         // 第一列节点的左边
const W = 136, STEP = 154;    // 七列网格
const col = (i: number) => X0 + i * STEP;
const mid = (i: number) => col(i) + W / 2;
const H = 62;                 // 普通节点高
const ID = "biz3";

/** 五段的纵向位置：top 为底带顶部，a0/a1 为节点区上下沿。 */
const B1 = { top: 0, a0: 22, a1: 84, h: 106 };
const B2 = { top: 146, a0: 168, a1: 326, h: 180 };
const B3 = { top: 366, a0: 388, a1: 578, h: 212 };
const B4 = { top: 618, a0: 640, a1: 790, h: 200 };
const B5 = { top: 866, a0: 882, a1: 944, h: 106 };
const centerY = (b: { a0: number; a1: number }) => (b.a0 + b.a1) / 2 - H / 2;

const KNOWLEDGE: N[] = [
  { icon: "doc", title: "文档接入", lines: ["说明书、FAQ 等资料", "按产品和类别归档"] },
  { icon: "parse", title: "版面解析", lines: ["MinerU 识别标题、表格", "和图片说明，保留页码"] },
  { icon: "chunk", title: "Parent-Child 分块", lines: ["Child 小块用来检索", "Parent 大块给回答用"] },
  { icon: "search", title: "向量化与索引", lines: ["Embedding 向量索引", "加 BM25 关键词检索"] },
  { icon: "coverage", title: "主题聚类", lines: ["K-means 分出主题簇", "按主题厚薄分配题位"] },
];
const K_STEP = (VW - 8 - X0 - W) / (KNOWLEDGE.length - 1);

const QTYPES = [
  { title: "正向题", line: "资料里有答案，测能不能答对" },
  { title: "消融题", line: "同一知识点换个问法" },
  { title: "负向题", line: "证据不足、安全、提示注入" },
];
const LAYERS = [
  { title: "检索层", line: "没找回来 · 排名靠后被截掉 · 找回的不相关" },
  { title: "生成层", line: "证据给到却漏了要点 · 编造内容 · 过度拒答" },
  { title: "安全层", line: "该拒没拒 · 被提示词注入绕过 · 答了库外内容" },
  { title: "性能层", line: "整体太慢 · 首字太慢 · 成本太高" },
];
const CANDIDATES = ["Candidate A", "Candidate B", "Candidate C"];

/** 竖直分叉：从 (x1,y1) 出发，水平走到 x2 前转弯落到 y2。 */
const fan = (x1: number, y1: number, x2: number, y2: number) => {
  const m = (x1 + x2) / 2;
  return `M${x1} ${y1} C${m} ${y1}, ${m} ${y2}, ${x2} ${y2}`;
};
/** 段与段之间的换行连线：从上一段某列底部下行，在段间空隙里水平走到目标列，再落到目标顶部。 */
const drop = (x1: number, y1: number, gapY: number, x2: number, y2: number) => {
  const r = 10, dir = x2 < x1 ? -1 : 1;
  return `M${x1} ${y1} V${gapY - r} Q${x1} ${gapY} ${x1 + dir * r} ${gapY} H${x2 - dir * r} Q${x2} ${gapY} ${x2} ${gapY + r} V${y2}`;
};

export function BusinessArchitecture() {
  const right = VW - 8;
  const fullW = right - 8;
  // 02 考卷生产
  const qY = (i: number) => B2.a0 + i * 54;           // 三类题型，高 46，间距 8
  const g0 = centerY(B2);
  // 03 评测诊断
  const lY = (i: number) => B3.a0 + i * 48;            // 四层，高 42，间距 6
  const e0 = centerY(B3);
  const LW = W * 2 + (STEP - W);                       // 四层节点横跨两列
  // 04 Agent 优化
  const cY = (i: number) => B4.a0 + 4 + i * 48;
  const o0 = centerY(B4);
  return <Figure label="业务架构：知识准备、考卷生产、评测诊断、Agent 优化、发布与监控五段闭环" viewBox={`0 0 ${VW} ${B5.top + B5.h + 4}`}
    legend={<><span><i className="ln" />主流程</span><span><i className="ln dash" />回流与下一轮</span><span><i className="fork" />并排分支后汇聚</span><span><i className="badge" />Gate：必须由人确认</span><span><i className="tint" />Agent 自动试错区</span></>}>
    <Defs id={ID} />
    <Band x={8} y={B1.top} w={fullW} h={B1.h} labelWidth={LABEL} index="01" name="知识准备" note={["把说明书变成", "可检索、可回溯", "原页的知识"]} />
    <Band x={8} y={B2.top} w={fullW} h={B2.h} labelWidth={LABEL} index="02" name="考卷生产" note={["先有一套每轮", "都不变的考卷"]} />
    <Band x={8} y={B3.top} w={fullW} h={B3.h} labelWidth={LABEL} index="03" name="评测诊断" note={["同一套考卷和", "判分标准体检，", "找到问题在哪层"]} />
    <Band x={8} y={B4.top} w={fullW} h={B4.h} labelWidth={LABEL} index="04" name="Agent 优化" note={["在白名单参数里", "试错，每轮带着", "上一轮的经验"]} accent />
    <Band x={8} y={B5.top} w={fullW} h={B5.h} labelWidth={LABEL} index="05" name="发布与监控" note={["机器提议，", "人来拍板；线上", "问题回到下一轮"]} />

    {/* 01 知识准备 */}
    {KNOWLEDGE.map((n, i) => i < KNOWLEDGE.length - 1 && <Wire key={i} id={ID} d={`M${X0 + i * K_STEP + W + 4} ${B1.a0 + H / 2} H${X0 + (i + 1) * K_STEP - 5}`} />)}
    {KNOWLEDGE.map((n, i) => <Node key={n.title} x={X0 + i * K_STEP} y={B1.a0} w={W} h={H} {...n} />)}
    <Wire id={ID} accent d={drop(X0 + 4 * K_STEP + W / 2, B1.a1, B1.top + B1.h + 20, mid(0), B2.a0 + 4)} />
    <Tag x={(mid(0) + X0 + 4 * K_STEP) / 2 + 60} y={B1.top + B1.h + 24} text="主题簇和题位" accent />

    {/* 02 考卷生产 */}
    <Node x={col(0)} y={B2.a0 + 4} w={W} h={H} icon="golden" title="AI 按主题出题" lines={["每道题指定素材", "出坏了就换一道"]} />
    <Node x={col(0)} y={B2.a1 - H} w={W} h={H} icon="data" title="考卷候选池" lines={["客户 FAQ、线上回流", "的问题先放这里"]} dashed />
    {QTYPES.map((q, i) => <g key={q.title}>
      <Wire id={ID} d={fan(col(0) + W + 3, i === 2 ? B2.a1 - H / 2 : B2.a0 + 4 + H / 2, col(1) - 4, qY(i) + 23)} />
      <rect x={col(1)} y={qY(i)} width={W + 40} height={46} rx={10} fill={C.surface} stroke={C.rule} />
      <text x={col(1) + 11} y={qY(i) + 19} fontSize={12.5} fontWeight={600} fill={C.ink}>{q.title}</text>
      <text x={col(1) + 11} y={qY(i) + 36} fontSize={11} fill={C.muted}>{q.line}</text>
      <Wire id={ID} d={fan(col(1) + W + 43, qY(i) + 23, col(2) + 36, g0 + H / 2)} />
    </g>)}
    <Wire id={ID} d={fan(col(0) + W + 3, B2.a0 + 4 + H / 2, col(1) - 4, qY(1) + 23)} />
    <Node x={col(2) + 40} y={g0} w={W} h={H} icon="checks" title="硬校验与探针" lines={["证据须在原文逐字找到", "探针拿题去检索验真伪"]} />
    <Wire id={ID} d={`M${col(2) + 40 + W + 4} ${g0 + H / 2} H${col(3) + 36}`} />
    <Node x={col(3) + 40} y={g0} w={W} h={H} icon="report" title="质检 QC" lines={["模型检查题目质量", "问题按轻重分级"]} />
    <Wire id={ID} d={`M${col(3) + 40 + W + 4} ${g0 + H / 2} H${col(4) + 36}`} />
    <Node x={col(4) + 40} y={g0} w={W} h={H} icon="approval" title="题卷确认" lines={["人只看红线问题清单", "冻结后每轮都用它"]} badge="Gate 1" />
    <Wire id={ID} accent d={drop(col(4) + 40 + W / 2, g0 + H, B2.top + B2.h + 20, mid(0), e0)} />
    <Tag x={(mid(0) + col(4)) / 2 + 40} y={B2.top + B2.h + 24} text="冻结的考卷" accent />

    {/* 03 评测诊断 */}
    <Node x={col(0)} y={e0} w={W} h={H} icon="baseline" title="Baseline 评测" lines={["当前配置逐题作答", "记录检索、回答和耗时"]} />
    <Wire id={ID} d={`M${col(0) + W + 4} ${e0 + H / 2} H${col(1) - 5}`} />
    <Node x={col(1)} y={e0} w={W} h={H} icon="correct" title="判分" lines={["规则算检索和耗时", "LLM-as-Judge 判对错"]} />
    <Wire id={ID} d={`M${col(1) + W + 4} ${e0 + H / 2} H${col(2) - 5}`} />
    <Node x={col(2)} y={e0} w={W} h={H} icon="gate" title="Hard Gate" lines={["质量、安全、速度", "每一项单独过线"]} />
    {LAYERS.map((l, i) => <g key={l.title}>
      <Wire id={ID} d={fan(col(2) + W + 3, e0 + H / 2, col(3) - 4, lY(i) + 21)} />
      <rect x={col(3)} y={lY(i)} width={LW} height={42} rx={10} fill={C.surface} stroke={C.rule} />
      <text x={col(3) + 11} y={lY(i) + 17} fontSize={12.5} fontWeight={600} fill={C.ink}>{l.title}</text>
      <text x={col(3) + 11} y={lY(i) + 33} fontSize={11} fill={C.muted}>{l.line}</text>
      <Wire id={ID} d={fan(col(3) + LW + 3, lY(i) + 21, col(5) - 4, e0 + H / 2)} />
    </g>)}
    <Node x={col(5)} y={e0} w={W} h={H} icon="bad" title="Bad Case 诊断" lines={["每题定位到层和原因", "标出严重或一般"]} />
    <Wire id={ID} accent d={drop(mid(5), e0 + H, B3.top + B3.h + 20, mid(0), o0)} />
    <Tag x={(mid(0) + mid(5)) / 2} y={B3.top + B3.h + 24} text="Bad Case 和归因" accent />

    {/* 04 Agent 优化 */}
    <Node x={col(0)} y={o0} w={W} h={H} icon="thinking" title="Agent 策略" lines={["读诊断和上一轮经验", "定参数、预期和风险"]} focus />
    {CANDIDATES.map((name, i) => <g key={name}>
      <Wire id={ID} accent d={fan(col(0) + W + 3, o0 + H / 2, col(1) - 4, cY(i) + 20)} />
      <rect x={col(1)} y={cY(i)} width={W} height={40} rx={10} fill={C.tint} stroke="rgba(0,113,227,0.35)" />
      <text x={col(1) + 11} y={cY(i) + 17} fontSize={12.5} fontWeight={600} fill={C.ink}>{name}</text>
      <text x={col(1) + 11} y={cY(i) + 32} fontSize={11} fill={C.muted}>方向互不相同</text>
      <Wire id={ID} accent d={fan(col(1) + W + 3, cY(i) + 20, col(2) - 4, o0 + H / 2)} />
    </g>)}
    <Node x={col(2)} y={o0} w={W} h={H} icon="compare" title="Sandbox 评测" lines={["同一套考卷", "同一套判分标准"]} focus />
    <Wire id={ID} accent d={`M${col(2) + W + 4} ${o0 + H / 2} H${col(3) - 5}`} />
    <Node x={col(3)} y={o0} w={W} h={H} icon="gate" title="Regression Check" lines={["修好的题不能抵消", "新弄坏的题"]} focus />
    <Wire id={ID} accent d={`M${col(3) + W + 4} ${o0 + H / 2} H${col(4) - 5}`} />
    <Node x={col(4)} y={o0} w={W} h={H} icon="report" title="本轮结论" lines={["修好、弄坏了什么", "可能是哪个参数"]} focus />
    <Wire id={ID} accent dashed d={`M${mid(4)} ${o0 + H} V${B4.a1 + 2} Q${mid(4)} ${B4.a1 + 12} ${mid(4) - 10} ${B4.a1 + 12} H${mid(0) + 10} Q${mid(0)} ${B4.a1 + 12} ${mid(0)} ${B4.a1 + 2} V${o0 + H + 4}`} />
    <Tag x={(mid(0) + mid(4)) / 2} y={B4.a1 + 16} text="未达标：经验写入下一轮策略，在评测预算内继续" accent bg="#f5f9fe" />
    <Wire id={ID} accent d={`M${col(4) + W + 4} ${o0 + H / 2} H${col(5) - 5}`} />
    <Node x={col(5)} y={o0} w={W} h={H} icon="merge" title="Candidate D" lines={["合并合格方案的有效参数", "事先预测、事后对账"]} focus />
    <Wire id={ID} d={`M${col(5) + W + 4} ${o0 + H / 2} H${col(6) - 5}`} />
    <Node x={col(6)} y={o0} w={W} h={H} icon="report" title="报告确认" lines={["人看各方案报告", "和推荐理由"]} badge="Gate 2" />
    <Wire id={ID} d={`M${mid(6)} ${o0 + H + 4} V${B5.a0 - 5}`} />

    {/* 05 发布与监控（从右往左） */}
    <Node x={col(6)} y={B5.a0} w={W} h={H} icon="checks" title="发布资格" lines={["程序校验门槛、回归、", "白名单和快照"]} />
    <Wire id={ID} d={`M${col(6) - 4} ${B5.a0 + H / 2} H${col(5) + W + 5}`} />
    <Node x={col(5)} y={B5.a0} w={W} h={H} icon="release" title="发布确认" lines={["看红线和抽样回归", "保存快照，可回滚"]} badge="Gate 3" />
    <Wire id={ID} d={`M${col(5) - 4} ${B5.a0 + H / 2} H${col(4) + W + 5}`} />
    <Node x={col(4)} y={B5.a0} w={W} h={H} icon="verify" title="线上问答" lines={["回答附引用出处", "记录检索和耗时"]} />
    <Wire id={ID} d={`M${col(4) - 4} ${B5.a0 + H / 2} H${col(3) + W + 5}`} />
    <Node x={col(3)} y={B5.a0} w={W} h={H} icon="status" title="线上反馈" lines={["人工标注 Bad Case", "盯耗时和引用"]} />
    <Wire id={ID} d={`M${col(3) - 4} ${B5.a0 + H / 2} H${col(2) + W + 5}`} />
    <Node x={col(2)} y={B5.a0} w={W} h={H} icon="loop" title="提交优化线索" lines={["人工确认后", "回到考卷候选池"]} />
    <rect x={col(0)} y={B5.a0} width={W * 2 + STEP - W - 18} height={H} rx={10} fill="none" stroke={C.rule} strokeDasharray="4 3" />
    <text x={col(0) + 12} y={B5.a0 + 20} fontSize={11.5} fontWeight={600} fill={C.ink2}>下一轮的考卷</text>
    <text x={col(0) + 12} y={B5.a0 + 37} fontSize={11} fill={C.muted}>原有题目（含仍未修好的题）</text>
    <text x={col(0) + 12} y={B5.a0 + 52} fontSize={11} fill={C.muted}>＋ 人工确认的新增题</text>
    <Wire id={ID} accent dashed d={`M${col(2) - 4} ${B5.a0 + H / 2} H${col(1) + W - 6} Q${col(1) + W - 16} ${B5.a0 + H / 2} ${col(1) + W - 16} ${B5.a0 + H / 2 - 10} V${B5.top - 10} Q${col(1) + W - 16} ${B5.top - 20} ${col(1) + W - 26} ${B5.top - 20} H${13} Q${3} ${B5.top - 20} ${3} ${B5.top - 30} V${B2.a1 - H / 2 + 10} Q${3} ${B2.a1 - H / 2} ${13} ${B2.a1 - H / 2} H${col(0) - 5}`} />
  </Figure>;
}

export type Problem = { icon: IconName; title: string; text: string };

export const PROJECT_PROBLEMS: Problem[] = [
  { icon: "target", title: "效果说不清", text: "智能客服上线以后，答得好不好往往要等到客户投诉才知道，团队手里缺少一把稳定的尺子，每次讨论效果都只能凭印象。" },
  { icon: "pipeline", title: "调参靠经验", text: "检索条数、排序方式、模型思考深度这些参数彼此牵连，靠人一个个去试既慢又贵，试出来的结果也很难说清是哪一处改动起了作用。" },
  { icon: "release", title: "改了不敢上线", text: "修好一道题的同时，常常会悄悄弄坏另一道原本答对的题，没有回归检查和人工把关，谁也不敢在这样的改动上签字发布。" },
];

export function ProjectProblems({ items = PROJECT_PROBLEMS, title = "这个项目要解决的问题" }: { items?: Problem[]; title?: string }) {
  return <section className="ui-problems" aria-label={title}>
    <h3>{title}</h3>
    <div className="ui-problems-grid">
      {items.map(item => <div key={item.title} className="ui-problem">
        <span className="ui-problem-title"><Icon name={item.icon} size={14} />{item.title}</span>
        <p>{item.text}</p>
      </div>)}
    </div>
  </section>;
}

/** 兼容旧引用：BUSINESS_LANES / ArchLane / ArchNode 已不再使用，保留类型导出避免外部引用报错。 */
export type ArchNode = N;
export type ArchLane = { key: string; nodes: N[] };
export const BUSINESS_LANES: ArchLane[] = [];
