import type { ReactNode } from "react";
import { IconLabel, ICONS, type IconName } from "../icons";
import { C, Defs, Tag, Wire, textWidth } from "../architecture/svgkit";
import "../architecture/architecture.css";

/**
 * 知识库 →「知识处理链路」（11-13 第二版，总指挥编写）。
 *
 * 两条泳道各 6 步：离线入库（说明书怎样变成可检索的知识）、在线检索（一个问题怎样找到证据并回答）。
 * 两条跨泳道的连线讲清楚两者的关系：
 * - 建立索引 → 混合检索：检索时读取的就是离线建好的那一份索引；
 * - Parent 分块 → 补齐 Parent：命中的 Child 按 Parent ID 取回整段原文。
 * 字号收小：步骤名 12、关键数值 14、说明 11，避免拥挤。
 * 数值由页面传入（离线来自知识库数据，在线来自当前线上配置）。
 */

export type FlowStep = { icon: IconName; label: string; value?: string; detail: string; tunable?: boolean };
export type FlowLane = { key: string; name: string; purpose: string; steps: FlowStep[] };

const ID = "kf";
const X0 = 128, W = 140, GAP = 26, H = 84;
const xs = Array.from({ length: 6 }, (_, i) => X0 + i * (W + GAP));
const Y1 = 8, Y2 = 168;

/** 按宽度粗略折行（英文单词不拆开），最多 maxLines 行，超出加省略号。 */
function wrap(text: string, width: number, size: number, maxLines = 2) {
  const tokens = text.match(/[A-Za-z0-9.\-_/+]+|\s+|./gu) || [];
  const lines: string[] = []; let line = "";
  for (const token of tokens) {
    const next = line + token;
    if (textWidth(next.trimEnd(), size) > width && line.trim()) {
      lines.push(line.trimEnd()); line = token.trimStart();
      if (lines.length === maxLines) { line = ""; lines[maxLines - 1] = lines[maxLines - 1].replace(/.$/u, "…"); return lines; }
    } else line = next;
  }
  if (line.trim()) lines.push(line.trim());
  return lines;
}

function Step({ x, y, step }: { x: number; y: number; step: FlowStep }) {
  const Glyph = ICONS[step.icon];
  const detail = wrap(step.detail, W - 22, 11, step.value ? 2 : 3);
  return <g>
    <title>{`${step.label}${step.value ? `：${step.value}` : ""}。${step.detail}`}</title>
    <rect x={x} y={y} width={W} height={H} rx={10} fill={C.surface} stroke={C.rule} />
    {Glyph && <Glyph x={x + 10} y={y + 9} width={12} height={12} color={C.muted} strokeWidth={1.8} />}
    <text x={x + 27} y={y + 19} fontSize={12} fontWeight={600} fill={C.ink}>{step.label}</text>
    {step.tunable && <circle cx={x + W - 11} cy={y + 15} r={3} fill={C.accent} />}
    {step.value && <text x={x + 11} y={y + 40} fontSize={14} fontWeight={600} fill={C.ink}>{step.value}</text>}
    {detail.map((line, i) => <text key={i} x={x + 11} y={y + (step.value ? 58 : 38) + i * 14} fontSize={11} fill={C.muted}>{line}</text>)}
  </g>;
}

function LaneHead({ y, lane }: { y: number; lane: FlowLane }) {
  return <g>
    <text x={0} y={y + 22} fontSize={13} fontWeight={600} fill={C.ink}>{lane.name}</text>
    {wrap(lane.purpose, 104, 11, 3).map((line, i) => <text key={i} x={0} y={y + 42 + i * 15} fontSize={11} fill={C.muted}>{line}</text>)}
  </g>;
}

export function KnowledgeFlow({ lanes, title = "知识处理链路", action }: { lanes: FlowLane[]; title?: string; action?: ReactNode }) {
  const [offline, online] = lanes;
  const hasCross = offline?.steps.length >= 5 && online?.steps.length >= 5;
  const mid = (i: number) => xs[i] + W / 2;
  return <section className="ui-kf" aria-label={title}>
    <div className="ui-kf-heading"><h3><IconLabel name="data">{title}</IconLabel></h3>{action}</div>
    <svg viewBox={`0 0 1100 ${Y2 + H + 10}`} role="img" aria-label={`${title}：离线入库与在线检索`} className="ui-arch-svg">
      <Defs id={ID} />
      {offline && <><LaneHead y={Y1} lane={offline} />{offline.steps.slice(0, 6).map((step, i) => <Step key={step.label} x={xs[i]} y={Y1} step={step} />)}
        {offline.steps.slice(0, 5).map((_, i) => i < offline.steps.length - 1 && <Wire key={i} id={ID} d={`M${xs[i] + W + 3} ${Y1 + H / 2} H${xs[i + 1] - 4}`} />)}</>}
      {online && <><LaneHead y={Y2} lane={online} />{online.steps.slice(0, 6).map((step, i) => <Step key={step.label} x={xs[i]} y={Y2} step={step} />)}
        {online.steps.slice(0, 5).map((_, i) => i < online.steps.length - 1 && <Wire key={i} id={ID} accent d={`M${xs[i] + W + 3} ${Y2 + H / 2} H${xs[i + 1] - 4}`} />)}</>}
      {hasCross && <>
        {/* 建立索引（离线第 5 步）→ 混合检索（在线第 3 步） */}
        <Wire id={ID} dashed accent d={`M${mid(4)} ${Y1 + H + 3} C${mid(4)} ${Y1 + H + 44}, ${mid(2)} ${Y2 - 44}, ${mid(2)} ${Y2 - 5}`} />
        <Tag x={mid(4) + 10} y={Y1 + H + 34} text="检索读取同一份索引" anchor="start" accent bg="transparent" />
        {/* Parent 分块（离线第 2 步）→ 补齐 Parent（在线第 5 步） */}
        <Wire id={ID} dashed d={`M${mid(1)} ${Y1 + H + 3} C${mid(1)} ${Y1 + H + 58}, ${mid(4) - 20} ${Y2 - 58}, ${mid(4) - 20} ${Y2 - 5}`} />
        <Tag x={mid(1) - 10} y={Y1 + H + 34} text="按 Parent ID 取回整段原文" anchor="end" bg="transparent" />
      </>}
    </svg>
  </section>;
}

/** 样板数据（Gallery 与测试用）。页面接入时：离线数值来自 knowledge 接口，在线参数来自当前线上配置。 */
export const SAMPLE_KNOWLEDGE_LANES: FlowLane[] = [
  {
    key: "offline", name: "离线入库", purpose: "说明书怎样变成可检索的知识",
    steps: [
      { icon: "parse", label: "文档解析", value: "4 份 · 157 页", detail: "MinerU VLM 解析，保留表格与页码" },
      { icon: "chunk", label: "Parent 分块", value: "349 段", detail: "每段约 1400 Tokens，作为回答上下文" },
      { icon: "split", label: "Child 分块", value: "368 段", detail: "每段 400 Tokens、重叠 80，用于检索" },
      { icon: "model", label: "向量化", value: "1024 维", detail: "text-embedding-v4 为每个 Child 编码" },
      { icon: "data", label: "建立索引", value: "368 已索引", detail: "FAISS 内积索引；BM25 在查询时打分" },
      { icon: "coverage", label: "主题聚类", value: "9 个主题", detail: "K-means 聚类，用来规划考题覆盖" },
    ],
  },
  {
    key: "online", name: "在线检索", purpose: "一个问题怎样找到证据并给出带出处的回答",
    steps: [
      { icon: "verify", label: "用户提问", detail: "客服或客户用口语描述问题" },
      { icon: "search", label: "查询理解", value: "按配置启用", detail: "Query Rewrite / Multi-Query / HyDE", tunable: true },
      { icon: "network", label: "混合检索", value: "召回 24 段", detail: "向量与 BM25 分数按权重融合", tunable: true },
      { icon: "rerank", label: "Rerank 重排", value: "重排 24 段", detail: "qwen3-rerank 重排，再按 MinScore 过滤", tunable: true },
      { icon: "merge", label: "补齐 Parent", value: "取前 6 个", detail: "Child 换成所在 Parent，去重后取 Top-K", tunable: true },
      { icon: "cite", label: "生成并引用", value: "Thinking High", detail: "每句标出处，可回溯到说明书原页", tunable: true },
    ],
  },
];
