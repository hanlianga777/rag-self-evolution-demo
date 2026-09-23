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
  const tone = /pass|completed|indexed|active|recommended|reviewed|qualified|evaluated/i.test(value) ? "good" : /fail|rejected|not_qualified|needs_revision/i.test(value) ? "bad" : /running|evaluating|queued/i.test(value) ? "accent" : /pending|human_review|not_run|not_evaluable|legacy/i.test(value) ? "warning" : "neutral";
  return <Badge tone={tone}>{displayText(value)}</Badge>;
}
