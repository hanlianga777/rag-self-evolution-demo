import { ICONS, type IconName } from "../icons";
import { Band, C, Defs, Figure, Node, Tag, Wire } from "./svgkit";
import "./architecture.css";

/**
 * 概览 →「技术架构」（11-14 第三版，总指挥编写）。
 *
 * 六层自上而下，左侧一列层名严格对齐：
 * 01 交互层 → 02 治理服务层 → 03 RAG Pipeline（被优化对象，四段与 Pipeline 配置页一致，蓝点 = Agent 可调参数）
 * → 04 评测层（规则计算 + LLM-as-Judge + Hard Gate）→ 05 知识处理层（离线建库）→ 06 模型与存储（按用途分组，标出厂商，悬停看选型理由）。
 * 通用版：不写本项目的数字。
 */

type P = { title: string; icon: IconName; params: string[]; tip: string };
const STEPS: P[] = [
  { title: "查询理解", icon: "search", params: ["Query Rewrite", "Multi-Query", "HyDE"], tip: "把用户的口语问题变成更好检索的说法：改写成规范问法、生成几个互补问法，或先写一段假设答案再拿去检索。" },
  { title: "检索召回", icon: "network", params: ["Candidate K", "Hybrid Search", "Embedding 权重"], tip: "先从知识库里多捞一些候选段落：向量检索看语义，BM25 看原词，两者按权重融合。" },
  { title: "筛选排序", icon: "rerank", params: ["Rerank", "Top-K", "MinScore", "上下文容量"], tip: "用重排模型给候选段落重新打分排序，按最低分过滤，再把命中的小块换成所在的完整段落（Parent），取前 Top-K 段交给模型。" },
  { title: "回答生成", icon: "cite", params: ["Prompt 策略", "Thinking 档位"], tip: "按回答策略组织答案：先结论、再步骤、安全警告在前，句末用角标标出处；Thinking 档位决定模型想多深。" },
];

type M = { title: string; vendor: string; line: string; tip: string; icon: IconName };
const MODEL_GROUPS: { name: string; items: M[] }[] = [
  { name: "知识处理模型", items: [
    { title: "MinerU", vendor: "OpenDataLab", icon: "parse", line: "PDF 版面解析", tip: "上海人工智能实验室（OpenDataLab）开源的文档解析模型。能识别 PDF 里的标题层级、表格和图片说明，并保留页码。说明书里有大量操作表格和警告框，普通的文字抽取会把表格打散，所以选它。" },
    { title: "Embedding", vendor: "阿里云百炼", icon: "boxes", line: "text-embedding-v4", tip: "阿里云百炼（通义）的通用文本向量模型。中文语义效果好，支持多种向量维度，按调用量计费，适合中文说明书的语义检索。" },
  ] },
  { name: "检索排序模型", items: [
    { title: "qwen3-rerank", vendor: "阿里云百炼", icon: "rerank", line: "候选段落重排", tip: "通义千问的重排模型：把问题和每个候选段落成对打分再排序，比只看向量相似度更准，能把真正相关的段落排到前面。" },
  ] },
  { name: "生成模型", items: [
    { title: "DeepSeek", vendor: "深度求索", icon: "model", line: "改写、HyDE、回答", tip: "深度求索（DeepSeek）的对话模型，负责查询改写、HyDE、多路查询和最终回答。中文表达好，可以调节思考档位，价格低，适合需要反复评测的场景。" },
  ] },
  { name: "评测模型", items: [
    { title: "DeepSeek", vendor: "深度求索", icon: "correct", line: "LLM-as-Judge 判分", tip: "LLM-as-Judge：拿每道题的必答要点和证据原文，对照回答打分（答对程度、要点覆盖、是否忠于证据、有无安全问题）。演示阶段和生成模型同一家族；生产环境建议换成独立模型，并加人工抽检。" },
  ] },
  { name: "存储", items: [
    { title: "FAISS", vendor: "Meta 开源", icon: "data", line: "向量索引", tip: "Meta 开源的向量检索库，用内积做精确检索；数据量不大时速度快，不需要单独部署服务。" },
    { title: "BM25", vendor: "经典算法", icon: "search", line: "关键词索引", tip: "经典的关键词检索算法，弥补向量检索对型号、按键名这类原词不敏感的问题。" },
    { title: "SQLite", vendor: "开源", icon: "server", line: "记录与快照", tip: "单文件数据库，保存题卷、评测、实验、发布快照和审计记录，便于整体备份和回滚。" },
  ] },
];

const VW = 1200, LABEL = 120, X0 = 8 + LABEL, RIGHT = VW - 8;
const AW = RIGHT - X0 - 10;            // 内容区宽度
const ID = "tech3";
const L1 = { top: 0, h: 74 }, L2 = { top: 104, h: 104 }, L3 = { top: 238, h: 142 }, L4 = { top: 410, h: 104 }, L5 = { top: 544, h: 104 }, L6 = { top: 678, h: 150 };

function ParamNode({ x, y, w, h, step }: { x: number; y: number; w: number; h: number; step: P }) {
  const Glyph = ICONS[step.icon];
  return <g>
    <Node x={x} y={y} w={w} h={h} title="" tip={step.tip} />
    <Glyph x={x + 10} y={y + 9} width={13} height={13} color={C.accent} strokeWidth={1.8} />
    <text x={x + 29} y={y + 20} fontSize={12.5} fontWeight={600} fill={C.ink}>{step.title}</text>
    {step.params.map((p, i) => <text key={p} x={x + 12 + (i % 2) * (w / 2 - 4)} y={y + 44 + Math.floor(i / 2) * 19} fontSize={11.5} fill={C.ink2}><tspan fill={C.accent}>● </tspan>{p}</text>)}
  </g>;
}

export function TechArchitecture(_: { layers?: unknown } = {}) {
  const pages = ["概览", "知识库", "Golden Dataset", "Pipeline 配置", "Baseline", "Agent 工作台", "发布", "问答验证"];
  const pw = (AW - 7 * 10) / 8;
  const svc = [
    { title: "评测治理", icon: "golden" as IconName, lines: ["考卷生命周期 · 判分", "Hard Gate · Bad Case 归因"] },
    { title: "Agent 优化", icon: "agent" as IconName, lines: ["策略 · Candidate", "Sandbox · Regression Check"] },
    { title: "发布治理", icon: "release" as IconName, lines: ["发布资格 · 三道 Gate", "快照 · 回滚 · 审计"] },
    { title: "线上监控", icon: "status" as IconName, lines: ["问答记录 · 人工标注", "优化线索回流"] },
  ];
  const sw = (AW - 3 * 14) / 4, sx = (i: number) => X0 + i * (sw + 14);
  const kn = [
    { title: "版面解析", icon: "parse" as IconName, lines: ["标题、表格、页码"] },
    { title: "去噪", icon: "split" as IconName, lines: ["去页眉页脚和目录"] },
    { title: "Parent-Child 分块", icon: "chunk" as IconName, lines: ["小块检索、大块回答"] },
    { title: "向量化", icon: "boxes" as IconName, lines: ["章节路径 + 正文"] },
    { title: "建立索引", icon: "data" as IconName, lines: ["FAISS + BM25"] },
    { title: "主题聚类", icon: "coverage" as IconName, lines: ["K-means 主题簇"] },
  ];
  const kw = (AW - 5 * 26) / 6, kx = (i: number) => X0 + i * (kw + 26);
  const ev = [
    { title: "规则计算", icon: "checks" as IconName, lines: ["Recall@K · Precision@K · MRR", "耗时 · Token 成本"], tip: "不用模型、由程序直接算的客观指标：标准证据有没有被检索到、排第几，以及回答耗时和花费。" },
    { title: "LLM-as-Judge 判分", icon: "correct" as IconName, lines: ["答对程度 · 要点覆盖", "忠于证据 · 安全"], tip: "让判分模型拿着必答要点和证据原文逐题对照回答打分。这些分数汇总后就是 Hard Gate 里的质量指标。" },
    { title: "Hard Gate", icon: "gate" as IconName, lines: ["质量 · 安全 · 速度", "每一项单独过线"], tip: "上线门槛：每一项都要单独达标，综合分再高也不能抵消某一项没过。" },
  ];
  const ew = (AW - 2 * 14) / 3, ex = (i: number) => X0 + i * (ew + 14);
  // 模型与存储：五组按宽度比例排开
  const units = MODEL_GROUPS.map(g => g.items.length);
  const total = units.reduce((a, b) => a + b, 0);
  const gap = 12, inner = 8;
  const unitW = (AW - gap * (MODEL_GROUPS.length - 1) - MODEL_GROUPS.length * inner * 2 - (total - MODEL_GROUPS.length) * inner) / total;
  let cursor = X0;
  const groups = MODEL_GROUPS.map(g => { const w = g.items.length * unitW + (g.items.length - 1) * inner + inner * 2; const r = { ...g, x: cursor, w }; cursor += w + gap; return r; });
  const cw = (AW - 3 * 14) / 4, cx = (i: number) => X0 + i * (cw + 14);
  const mid = (a: number, b: number) => (a + b) / 2;
  return <Figure label="技术架构：交互层、治理服务层、RAG Pipeline、评测层、知识处理层、模型与存储" viewBox={`0 0 ${VW} ${L6.top + L6.h + 4}`}
    legend={<><span><i className="ln" />调用关系</span><span><i className="ln dash" />离线建库 / 读取同一份数据</span><span><i className="dot" />Agent 可调参数</span><span><i className="tint" />被优化的 RAG Pipeline</span><span>悬停卡片可看说明</span></>}>
    <Defs id={ID} />
    <Band x={8} y={L1.top} w={RIGHT - 8} h={L1.h} labelWidth={LABEL} index="01" name="交互层" note={["React 页面"]} />
    <Band x={8} y={L2.top} w={RIGHT - 8} h={L2.h} labelWidth={LABEL} index="02" name="治理服务层" note={["FastAPI 后端"]} />
    <Band x={8} y={L3.top} w={RIGHT - 8} h={L3.h} labelWidth={LABEL} index="03" name="RAG Pipeline" note={["被优化的对象，", "四段流水线"]} accent />
    <Band x={8} y={L4.top} w={RIGHT - 8} h={L4.h} labelWidth={LABEL} index="04" name="评测层" note={["给每次回答打分"]} />
    <Band x={8} y={L5.top} w={RIGHT - 8} h={L5.h} labelWidth={LABEL} index="05" name="知识处理层" note={["离线建库，", "回答时只读索引"]} />
    <Band x={8} y={L6.top} w={RIGHT - 8} h={L6.h} labelWidth={LABEL} index="06" name="模型与存储" note={["按用途分组，", "悬停看选型理由"]} />

    {/* 01 交互层 */}
    {pages.map((p, i) => <g key={p}>
      <rect x={X0 + i * (pw + 10)} y={L1.top + 20} width={pw} height={34} rx={8} fill={C.surface} stroke={C.rule} />
      <text x={X0 + i * (pw + 10) + pw / 2} y={L1.top + 41} fontSize={12} fontWeight={500} textAnchor="middle" fill={C.ink}>{p}</text>
    </g>)}
    <Wire id={ID} d={`M${X0 + AW / 2} ${L1.top + 58} V${L2.top + 20}`} />
    <Tag x={X0 + AW / 2 + 8} y={L2.top - 7} text="HTTP / JSON" anchor="start" bg="transparent" />

    {/* 02 治理服务层 */}
    {svc.map((n, i) => <Node key={n.title} x={sx(i)} y={L2.top + 22} w={sw} h={62} {...n} />)}

    {/* 02 → 03 */}
    <Wire id={ID} d={`M${mid(sx(0), sx(1) + sw)} ${L2.top + 88} V${L3.top + 20}`} />
    <Tag x={mid(sx(0), sx(1) + sw) + 8} y={L3.top - 7} text="下发配置、逐题提问" anchor="start" bg="transparent" />

    {/* 03 RAG Pipeline */}
    {STEPS.map((step, i) => <g key={step.title}>
      <ParamNode x={cx(i)} y={L3.top + 22} w={cw} h={100} step={step} />
      {i < STEPS.length - 1 && <Wire id={ID} accent d={`M${cx(i) + cw + 2} ${L3.top + 72} H${cx(i + 1) - 3}`} />}
    </g>)}

    {/* 03 → 04 */}
    <Wire id={ID} d={`M${mid(cx(2), cx(3) + cw)} ${L3.top + 126} V${L4.top + 20}`} />
    <Tag x={mid(cx(2), cx(3) + cw) + 8} y={L4.top - 7} text="回答、证据、耗时" anchor="start" bg="transparent" />

    {/* 04 评测层 */}
    {ev.map((n, i) => <g key={n.title}>
      <Node x={ex(i)} y={L4.top + 22} w={ew} h={62} {...n} />
      {i < ev.length - 1 && <Wire id={ID} d={`M${ex(i) + ew + 2} ${L4.top + 53} H${ex(i + 1) - 3}`} />}
    </g>)}

    {/* 05 知识处理层 */}
    {kn.map((n, i) => <g key={n.title}>
      <Node x={kx(i)} y={L5.top + 22} w={kw} h={52} {...n} />
      {i < kn.length - 1 && <Wire id={ID} d={`M${kx(i) + kw + 2} ${L5.top + 48} H${kx(i + 1) - 3}`} />}
    </g>)}
    {/* 05 索引 → 03 检索召回（读取同一份索引），走左侧空隙 */}
    <Wire id={ID} dashed accent d={`M${kx(4) + kw / 2} ${L5.top + 20} V${L4.top + L4.h + 14} Q${kx(4) + kw / 2} ${L4.top + L4.h + 4} ${kx(4) + kw / 2 - 10} ${L4.top + L4.h + 4} H${X0 - 2} Q${X0 - 12} ${L4.top + L4.h + 4} ${X0 - 12} ${L4.top + L4.h - 6} V${L3.top + 82} Q${X0 - 12} ${L3.top + 72} ${X0 - 2} ${L3.top + 72} H${cx(0) - 4}`} />
    <Tag x={X0 + 200} y={L4.top + L4.h + 8} text="回答时读取同一份索引" accent bg="#fafafb" />

    {/* 06 模型与存储 */}
    {groups.map(g => <g key={g.name}>
      <rect x={g.x} y={L6.top + 14} width={g.w} height={L6.h - 26} rx={12} fill="none" stroke={C.rule} strokeDasharray="4 3" />
      <text x={g.x + inner + 2} y={L6.top + 32} fontSize={11.5} fontWeight={600} fill={C.ink2}>{g.name}</text>
      {g.items.map((m, j) => <Node key={g.name + m.title} x={g.x + inner + j * (unitW + inner)} y={L6.top + 42} w={unitW} h={70} icon={m.icon} title={m.title} lines={[m.line, m.vendor]} tip={m.tip} titleSize={12} />)}
    </g>)}
  </Figure>;
}

/** 兼容旧引用。 */
export type TechTag = { label: string; tunable?: boolean };
export type TechGroup = { title: string; tags: TechTag[] };
export type TechLayer = { key: string; groups: TechGroup[] };
export const TECH_LAYERS: TechLayer[] = [{ key: "pipeline", groups: STEPS.map(step => ({ title: step.title, tags: step.params.map(label => ({ label, tunable: true })) })) }];
