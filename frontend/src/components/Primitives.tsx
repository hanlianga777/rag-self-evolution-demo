import type { ReactNode } from "react";

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
  const tone = /pass|completed|indexed|active|recommended|reviewed/i.test(value) ? "good" : /fail|rejected/i.test(value) ? "bad" : /running|evaluating|queued/i.test(value) ? "accent" : "neutral";
  return <Badge tone={tone}>{value}</Badge>;
}
