import { useState } from "react";
import { HoverCard } from "./HoverCard";
import { StatusBadge, type StatusKind } from "./Primitives";

/* ==================================================================
 * Golden Dataset：一条"出题流水线"摘要，替换六张同样的"✓ 已完成"大卡
 * ================================================================== */
export function GoldenPipeline({ total, split, steps, frozen }: {
  total: number; split: { label: string; count: number }[];
  steps: { label: string; value: string; done: boolean }[]; frozen: { ok: boolean; text: string };
}) {
  return <section className="ui-gp" aria-label="Golden Dataset 摘要">
    <div className="ui-gp-left">
      <strong className="ui-num">{total} 题</strong>
      <div className="ui-gp-split">{split.map(item => <span key={item.label}>{item.label} <b className="ui-num">{item.count}</b></span>)}</div>
    </div>
    <ol className="ui-gp-steps">{steps.map(step => <li key={step.label} className={step.done ? "done" : ""}><i aria-hidden="true" /><strong>{step.label}</strong><small className="ui-num">{step.value}</small></li>)}</ol>
    <StatusBadge kind={frozen.ok ? "qualified" : "waiting"} label={frozen.text} />
  </section>;
}

/* ==================================================================
 * 知识库：主题覆盖总览（替换 9 张同质大卡）
 * - 每行一个主题：知识片段数（条形）+ 三类题位；
 * - "小主题保底"：题位数高于按片段比例应得的主题，标"保底"。
 * ================================================================== */
export type Topic = { name: string; chunks: number; positive: number; ablation: number; negative: number; protectedSlot?: boolean };

export function KnowledgeCoverage({ topics, onOpen }: { topics: Topic[]; onOpen?: (name: string) => void }) {
  const maxChunks = Math.max(1, ...topics.map(t => t.chunks));
  const totals = topics.reduce((acc, t) => ({ chunks: acc.chunks + t.chunks, positive: acc.positive + t.positive, ablation: acc.ablation + t.ablation, negative: acc.negative + t.negative }), { chunks: 0, positive: 0, ablation: 0, negative: 0 });
  return <section className="ui-kc" aria-label="知识主题覆盖">
    <header className="ui-kc-head">
      <h3>知识主题覆盖</h3>
      <span className="ui-num">{topics.length} 个主题 · {totals.chunks} 个知识片段 · 题位 Positive {totals.positive} / Ablation {totals.ablation} / Negative {totals.negative}</span>
    </header>
    <div className="ui-kc-table" role="table">
      <div className="ui-kc-row head" role="row"><span role="columnheader">主题</span><span role="columnheader">知识片段</span><span role="columnheader">Positive</span><span role="columnheader">Ablation</span><span role="columnheader">Negative</span></div>
      {topics.map(topic => <div key={topic.name} role="row" className={`ui-kc-row${onOpen ? " clickable" : ""}`} onClick={onOpen ? () => onOpen(topic.name) : undefined} tabIndex={onOpen ? 0 : undefined} onKeyDown={event => { if (onOpen && event.key === "Enter") onOpen(topic.name); }}>
        <span role="cell" className="ui-kc-name">{topic.name}{topic.protectedSlot && <HoverCard content="片段较少的主题也保留题位，避免冷门知识没有题考"><span className="ui-kc-tag">保底</span></HoverCard>}</span>
        <span role="cell" className="ui-kc-bar"><i style={{ width: `${topic.chunks / maxChunks * 100}%` }} /><b className="ui-num">{topic.chunks}</b></span>
        <span role="cell" className="ui-num">{topic.positive}</span>
        <span role="cell" className="ui-num">{topic.ablation}</span>
        <span role="cell" className="ui-num">{topic.negative}</span>
      </div>)}
    </div>
  </section>;
}

/* ==================================================================
 * Sandbox：同一份 Golden 上的并排对比表
 * - 主行默认显示：答对、新增 Bad Case、Hard Gate、P99、安全拒答率；其余行收进"更多指标"；
 * - 每行较好的值加粗（better 指明方向）；Winner / 推荐列加浅底。
 * ================================================================== */
export type CompareRow = { label: string; values: (number | string | null)[]; better?: "higher" | "lower"; unit?: string; digits?: number; primary?: boolean };

export function CompareTable({ columns, rows, highlight = [] }: { columns: { name: string; status?: StatusKind; statusLabel?: string }[]; rows: CompareRow[]; highlight?: number[] }) {
  const [more, setMore] = useState(false);
  const primary = rows.filter(row => row.primary !== false);
  const secondary = rows.filter(row => row.primary === false);
  const render = (row: CompareRow) => {
    const nums = row.values.map(v => typeof v === "number" ? v : null);
    const known = nums.filter((v): v is number => v !== null);
    const best = row.better && known.length > 1 ? (row.better === "higher" ? Math.max(...known) : Math.min(...known)) : null;
    return <tr key={row.label}>
      <th scope="row">{row.label}</th>
      {row.values.map((value, index) => {
        const text = value === null || value === undefined ? "未知" : typeof value === "number" ? `${row.digits != null ? value.toFixed(row.digits) : value}${row.unit ?? ""}` : value;
        const isBest = best !== null && nums[index] === best && known.filter(v => v === best).length < known.length;
        return <td key={index} className={`ui-num${highlight.includes(index) ? " hl" : ""}${isBest ? " best" : ""}`}>{text}</td>;
      })}
    </tr>;
  };
  return <div className="ui-ct">
    <table>
      <thead><tr><th />{columns.map((column, index) => <th key={column.name} className={highlight.includes(index) ? "hl" : ""}><span className="ui-ct-name">{column.name}</span>{column.status && <StatusBadge kind={column.status} label={column.statusLabel} />}</th>)}</tr></thead>
      <tbody>{primary.map(render)}{more && secondary.map(render)}</tbody>
    </table>
    {secondary.length > 0 && <button type="button" className="text-button ui-ct-more" aria-expanded={more} onClick={() => setMore(value => !value)}>{more ? "收起更多指标" : `更多指标（${secondary.length}）`}</button>}
  </div>;
}
