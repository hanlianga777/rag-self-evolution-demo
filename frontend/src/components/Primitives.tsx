import type { ReactNode } from "react";
import { displayText } from "../display";

export function Badge({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "good" | "bad" | "warning" | "accent" }) {
  return <span className={`badge ${tone}`}>{children}</span>;
}

export function Metric({ label, value, note }: { label: string; value: ReactNode; note?: string }) {
  return <div className="metric"><span>{label}</span><strong>{value}</strong>{note && <small>{note}</small>}</div>;
}

export function Section({ title, action, children }: { title: string; action?: ReactNode; children: ReactNode }) {
  return <section className="panel"><div className="section-head"><h2>{title}</h2>{action}</div>{children}</section>;
}

export function Status({ value }: { value: string }) {
  const tone = /fail|rejected|not[\s_-]*qualified|needs_revision/i.test(value) ? "bad" : /pass|completed|indexed|active|recommended|released|reviewed|qualified|evaluated/i.test(value) ? "good" : /running|evaluating|queued/i.test(value) ? "accent" : /pending|human_review|not_run|not_evaluable|legacy/i.test(value) ? "warning" : "neutral";
  return <Badge tone={tone}>{displayText(value)}</Badge>;
}

export function TechnicalDetails({ children, label = "Technical Details" }: { children: ReactNode; label?: string }) {
  return <details className="technical-details"><summary>{label}</summary><pre>{children}</pre></details>;
}

export function ShortId({ value }: { value?: string | null }) {
  if (!value) return <span className="muted">未记录</span>;
  return <button type="button" className="short-id" title={`${value} · 点击复制`} aria-label={`复制 ID ${value}`} onClick={() => void navigator.clipboard?.writeText(value)}>{value.length > 24 ? `${value.slice(0, 7)}…${value.slice(-7)}` : value}</button>;
}
