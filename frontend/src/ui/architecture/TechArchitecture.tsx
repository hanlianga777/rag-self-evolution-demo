import { ICONS, type IconName } from "../icons";
import { C, Defs, Figure, Node, Tag, Wire } from "./svgkit";
import "./architecture.css";

/**
 * 概览 →「技术架构」（11-13 第二版，总指挥编写）。
 *
 * 五个层次自上而下：交互层 → 治理服务层（FastAPI）→ RAG Pipeline（被优化对象，浅蓝底）
 * → 底部并排的知识处理层（离线）、检索模型、大模型、存储。
 * 连线只画讲解时会被问到的调用关系：下发候选配置、逐题提问与回收证据、检索读索引、
 * 向量化与重排、生成、Embedding 建库、发布快照落库。
 * 蓝点 = Agent 可调参数（共 12 项），名称与 Pipeline 配置页完全一致。
 */

type P = { title: string; icon: IconName; params: string[][] };
const STEPS: P[] = [
  { title: "查询理解", icon: "search", params: [["Query Rewrite", "Multi-Query"], ["HyDE"]] },
  { title: "检索召回", icon: "network", params: [["Hybrid Search", "Candidate K"], ["Embedding 权重"]] },
  { title: "筛选排序", icon: "rerank", params: [["Rerank", "Top-K", "MinScore"], ["上下文容量"]] },
  { title: "回答生成", icon: "cite", params: [["Prompt 策略"], ["Thinking 档位"]] },
];

const ID = "tech";

function ParamNode({ x, y, w, h, step }: { x: number; y: number; w: number; h: number; step: P }) {
  const Glyph = ICONS[step.icon];
  return <g>
    <rect x={x} y={y} width={w} height={h} rx={10} fill={C.surface} stroke="rgba(0,113,227,0.35)" />
    <Glyph x={x + 10} y={y + 9} width={13} height={13} color={C.accent} strokeWidth={1.8} />
    <text x={x + 29} y={y + 20} fontSize={12.5} fontWeight={600} fill={C.ink}>{step.title}</text>
    {step.params.map((row, r) => <text key={r} x={x + 11} y={y + 42 + r * 18} fontSize={11.5} fill={C.ink2}>
      {row.map((p, i) => <tspan key={p} dx={i ? 10 : 0}><tspan fill={C.accent}>● </tspan>{p}</tspan>)}
    </text>)}
  </g>;
}

export function TechArchitecture(_: { layers?: unknown } = {}) {
  const bx = [30, 401, 772], bw = 347;
  const cx = [30, 312.5, 595, 877.5], cw = 242;
  const k = [14, 154, 294, 434], kw = 118;
  return <Figure label="技术架构：交互层、治理服务层、RAG Pipeline、知识处理与模型服务" viewBox="0 0 1150 600"
    legend={<><span><i className="ln" />调用</span><span><i className="ln dash" />回收结果</span><span><i className="dot" />Agent 可调参数（共 12 项）</span><span><i className="tint" />被优化的对象</span></>}>
    <Defs id={ID} />
    {/* 01 交互层 */}
    <rect x={14} y={14} width={1122} height={56} rx={12} fill={C.surface} stroke={C.rule} />
    <text x={30} y={38} fontSize={12} fontWeight={600} fill={C.faint}>01<tspan dx={6} fill={C.ink} fontSize={13}>交互层</tspan></text>
    <text x={30} y={56} fontSize={11} fill={C.muted}>React 18 · TypeScript · Vite</text>
    {["知识库", "Golden Dataset", "Baseline", "Agent 工作台", "发布", "问答验证"].map((name, i) => <g key={name}>
      <rect x={300 + i * 136} y={28} width={124} height={28} rx={8} fill={C.rule2} />
      <text x={362 + i * 136} y={46} fontSize={11.5} textAnchor="middle" fill={C.ink2}>{name}</text>
    </g>)}
    <Wire id={ID} d="M575 72 V106" />
    <Tag x={583} y={93} text="HTTP / JSON" anchor="start" bg="transparent" />

    {/* 02 治理服务层 */}
    <rect x={14} y={110} width={1122} height={118} rx={14} fill="#fbfbfd" stroke={C.rule2} />
    <text x={30} y={130} fontSize={12} fontWeight={600} fill={C.faint}>02<tspan dx={6} fill={C.ink} fontSize={13}>治理服务层</tspan><tspan dx={8} fill={C.muted} fontWeight={400} fontSize={11.5}>FastAPI · 评测、优化、发布的规则都在这一层</tspan></text>
    <Node x={bx[0]} y={140} w={bw} h={74} icon="golden" title="评测治理" lines={["Golden 生命周期 · LLM-as-Judge 逐条判分", "11 项 Hard Gate · Bad Case 归因到层"]} />
    <Node x={bx[1]} y={140} w={bw} h={74} icon="candidate" title="Agent 优化" lines={["Candidate 生成 · Sandbox 执行", "Regression Check · 评测预算 12 次"]} />
    <Node x={bx[2]} y={140} w={bw} h={74} icon="release" title="发布治理" lines={["推荐报告 · 发布快照", "版本回滚 · 线上反馈"]} />

    {/* 治理层 → RAG */}
    <Wire id={ID} d={`M${bx[0] + 120} 216 V286`} />
    <Tag x={bx[0] + 112} y={254} text="逐题提问" anchor="end" bg="transparent" />
    <Wire id={ID} dashed accent d={`M${bx[0] + 220} 288 V218`} />
    <Tag x={bx[0] + 228} y={254} text="回答 + 证据 + 耗时" anchor="start" accent bg="transparent" />
    <Wire id={ID} accent d={`M${bx[1] + bw / 2} 216 V286`} />
    <Tag x={bx[1] + bw / 2 + 8} y={254} text="下发 Candidate 配置" anchor="start" accent bg="transparent" />

    {/* 03 RAG Pipeline */}
    <rect x={14} y={272} width={1122} height={130} rx={14} fill={C.tint} opacity={0.6} />
    <rect x={14} y={272} width={1122} height={130} rx={14} fill="none" stroke="rgba(0,113,227,0.28)" />
    <text x={30} y={292} fontSize={12} fontWeight={600} fill={C.accent}>03<tspan dx={6} fill={C.ink} fontSize={13}>RAG Pipeline</tspan><tspan dx={8} fill={C.accent} fontWeight={400} fontSize={11.5}>被优化的对象 · 一次问答依次经过四个环节</tspan></text>
    {STEPS.map((step, i) => <ParamNode key={step.title} x={cx[i]} y={302} w={cw} h={86} step={step} />)}
    {cx.slice(0, 3).map((x, i) => <Wire key={i} id={ID} accent d={`M${x + cw + 3} 345 H${cx[i + 1] - 4}`} />)}

    {/* 04 底部：知识处理 · 检索模型 · 大模型 · 存储 */}
    <text x={14} y={452} fontSize={12} fontWeight={600} fill={C.faint}>04<tspan dx={6} fill={C.ink} fontSize={13}>知识处理层</tspan><tspan dx={8} fill={C.muted} fontWeight={400} fontSize={11.5}>离线</tspan></text>
    <Node x={k[0]} y={464} w={kw} h={70} icon="parse" title="MinerU 解析" lines={["VLM · 保留表格", "与页码"]} />
    <Node x={k[1]} y={464} w={kw} h={70} icon="chunk" title="Parent-Child" lines={["1400 / 400 Tokens", "重叠 80"]} />
    <Node x={k[2]} y={464} w={kw} h={70} icon="model" title="向量化" lines={["text-embedding-v4", "1024 维"]} />
    <Node x={k[3]} y={464} w={kw} h={70} icon="data" title="检索索引" lines={["FAISS 内积索引", "BM25 查询时打分"]} />
    {k.slice(0, 3).map((x, i) => <Wire key={i} id={ID} d={`M${x + kw + 3} 499 H${k[i + 1] - 4}`} />)}
    <Node x={586} y={464} w={128} h={70} icon="network" title="通义 Qwen" lines={["Embedding", "qwen3-rerank"]} />
    <Node x={728} y={464} w={128} h={70} icon="model" title="DeepSeek" lines={["回答生成 · Judge", "Agent 提案"]} />
    <Node x={890} y={464} w={246} h={70} icon="data" title="SQLite" lines={["题卷 · 评测记录 · Candidate", "发布快照 · 审批与审计"]} />

    {/* RAG → 底部 */}
    <Wire id={ID} d={`M${cx[1] + 70} 390 C${cx[1] + 70} 430, ${k[3] + 59} 420, ${k[3] + 59} 461`} />
    <Tag x={cx[1] + 40} y={428} text="读取索引" anchor="end" bg="transparent" />
    <Wire id={ID} d={`M${cx[1] + 190} 390 C${cx[1] + 190} 436, 620 424, 630 461`} />
    <Tag x={cx[1] + 238} y={428} text="问题向量化" anchor="start" bg="transparent" />
    <Wire id={ID} d={`M${cx[2] + 90} 390 C${cx[2] + 90} 430, 680 430, 680 461`} />
    <Tag x={cx[2] + 98} y={426} text="Rerank" anchor="start" bg="transparent" />
    <Wire id={ID} d={`M${cx[3] + 100} 390 C${cx[3] + 100} 436, 800 424, 800 461`} />
    <Tag x={cx[3] + 108} y={428} text="流式生成" anchor="start" bg="transparent" />
    {/* 建库时向量化调用 Qwen Embedding */}
    <Wire id={ID} dashed d={`M${k[2] + 59} 536 C${k[2] + 59} 580, 650 580, 650 537`} />
    <Tag x={(k[2] + 59 + 650) / 2} y={584} text="建库时批量向量化" />
    {/* 发布治理 → SQLite */}
    <Wire id={ID} d={`M${bx[2] + bw + 2} 177 C1150 177, 1148 440, 1110 461`} />
    <Tag x={1128} y={258} text="快照 · 版本 · 审计" anchor="end" bg="transparent" />
  </Figure>;
}

/** 兼容旧引用。 */
export type TechTag = { label: string; tunable?: boolean };
export type TechGroup = { title: string; tags: TechTag[] };
export type TechLayer = { key: string; groups: TechGroup[] };
export const TECH_LAYERS: TechLayer[] = [{ key: "pipeline", groups: STEPS.map(step => ({ title: step.title, tags: step.params.flat().map(label => ({ label, tunable: true })) })) }];
