import type { ReactNode } from "react";
import { HoverCard } from "./HoverCard";
import { Icon } from "./icons";

/* ------------------------------------------------------------------
 * StatTransition：前后对比数值，例如 44 → 48、42.2 → 36.7 秒
 * ------------------------------------------------------------------ */
export type Direction = "higher" | "lower";

export function StatTransition({ from, to, unit, better = "higher", digits, delta = false, deltaUnit, className = "" }: {
  from: number | null | undefined; to: number | null | undefined; unit?: string; better?: Direction; digits?: number; delta?: boolean; deltaUnit?: string; className?: string;
}) {
  const fmt = (value: number | null | undefined) => value == null || Number.isNaN(value) ? "未知" : digits == null ? String(value) : value.toFixed(digits);
  const known = from != null && to != null;
  const diff = known ? (to as number) - (from as number) : 0;
  const improved = known && diff !== 0 && (better === "higher" ? diff > 0 : diff < 0);
  const worse = known && diff !== 0 && !improved;
  return <span className={`ui-transition ${className}`.trim()}>
    <span className="from">{fmt(from)}</span>
    <span className="arrow" aria-hidden="true">→</span>
    <span className={`to${improved ? " better" : ""}`}>{fmt(to)}{unit && <span className="unit">{unit}</span>}</span>
    {delta && known && <DeltaChip value={diff} digits={digits} unit={deltaUnit ?? unit} tone={improved ? "good" : worse ? "bad" : "flat"} />}
  </span>;
}

export function DeltaChip({ value, digits, unit = "", tone }: { value: number; digits?: number; unit?: string; tone: "good" | "bad" | "flat" }) {
  const abs = digits == null ? Math.abs(value) : Math.abs(value).toFixed(digits);
  const sign = value > 0 ? "+" : value < 0 ? "−" : "±";
  return <span className={`ui-delta ${tone}`}>{sign}{abs}{unit ? ` ${unit}` : ""}</span>;
}

/* ------------------------------------------------------------------
 * StatusBadge：已评测 / 合格 / 未通过 / 推荐 / 待发布 / 已发布 / 运行中 …
 * 规则：只有"合格""已发布"用绿色；"推荐""待发布"用藏青；失败用红色。
 * ------------------------------------------------------------------ */
export type StatusKind = "evaluated" | "qualified" | "failed" | "recommended" | "pending_release" | "released" | "running" | "waiting" | "paused" | "stopped" | "completed" | "winner";

const STATUS: Record<StatusKind, { label: string; tone: string; live?: boolean }> = {
  evaluated: { label: "已评测", tone: "neutral" },
  qualified: { label: "合格", tone: "good" },
  failed: { label: "未通过", tone: "bad" },
  recommended: { label: "推荐", tone: "navy" },
  pending_release: { label: "待发布", tone: "navy" },
  released: { label: "已发布", tone: "good" },
  running: { label: "运行中", tone: "neutral", live: true },
  waiting: { label: "等待中", tone: "amber" },
  paused: { label: "已暂停", tone: "neutral" },
  stopped: { label: "已停止", tone: "neutral" },
  completed: { label: "已完成", tone: "neutral" },
  winner: { label: "Winner", tone: "solid" },
};

export function StatusBadge({ kind, label }: { kind: StatusKind; label?: string }) {
  const item = STATUS[kind];
  const glyph = kind === "winner" ? "winner" : kind === "recommended" ? "recommend" : kind === "released" ? "release" : null;
  return <span className={`ui-status ${item.tone}${item.live ? " live" : ""}${glyph ? " has-icon" : ""}`}>{glyph && <Icon name={glyph} size={13} />}{label ?? item.label}</span>;
}

/* ------------------------------------------------------------------
 * QuestionBadge：Q04 题号徽章（修好 / 弄坏 / 仍未修好 / 无变化），悬停看题目
 * ------------------------------------------------------------------ */
export type QuestionTone = "fixed" | "broken" | "open" | "neutral";
const TONE_TEXT: Record<QuestionTone, string> = { fixed: "修好", broken: "新增 Bad Case", open: "仍未修好", neutral: "无变化" };

export function QuestionBadge({ id, tone = "neutral", question, detail }: { id: string; tone?: QuestionTone; question?: string; detail?: ReactNode }) {
  const badge = <span className={`ui-q is-${tone}`} tabIndex={question || detail ? 0 : undefined} aria-label={`${id} ${TONE_TEXT[tone]}`}>{id}</span>;
  if (!question && !detail) return badge;
  return <HoverCard content={<div style={{ maxWidth: 360 }}>
    <div><b>{id}</b> · {TONE_TEXT[tone]}</div>
    {question && <div style={{ marginTop: 4 }}>{question}</div>}
    {detail && <div style={{ marginTop: 6, color: "#b9c5d6" }}>{detail}</div>}
  </div>}>{badge}</HoverCard>;
}

export function QuestionList({ items }: { items: { id: string; tone?: QuestionTone; question?: string; detail?: ReactNode }[] }) {
  if (!items.length) return <span className="ui-q neutral" aria-label="无">无</span>;
  return <span className="ui-q-list">{items.map(item => <QuestionBadge key={item.id} {...item} />)}</span>;
}

/* ------------------------------------------------------------------
 * ParamChip：参数变化胶囊，例如 Candidate K 12 → 24
 * ------------------------------------------------------------------ */
export function ParamChip({ label, from, to, keyParam = false, keyLabel = "本题关键" }: { label: string; from?: ReactNode; to: ReactNode; keyParam?: boolean; keyLabel?: string }) {
  return <span className={`ui-param${keyParam ? " key" : ""}`}>
    {label} <b>{from != null ? <>{from} → {to}</> : to}</b>
    {keyParam && <small>{keyLabel}</small>}
  </span>;
}
