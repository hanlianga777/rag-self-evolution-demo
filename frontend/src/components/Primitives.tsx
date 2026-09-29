import { useId, useState, type KeyboardEvent, type ReactNode } from "react";
import { ChevronDown } from "lucide-react";
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

export function TechnicalDetails({ children, label = "技术详情" }: { children: ReactNode; label?: string }) {
  return <details className="technical-details"><summary>{label}</summary><pre>{children}</pre></details>;
}

export type SelectOption = { value: string; label: string; description?: string; title?: string };

export function CustomSelect({ ariaLabel, value, options, onChange, disabled = false, placeholder }: { ariaLabel: string; value: string; options: SelectOption[]; onChange: (value: string) => void; disabled?: boolean; placeholder?: string }) {
  const id = useId();
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(Math.max(0, options.findIndex(option => option.value === value)));
  const selected = options.find(option => option.value === value);
  const move = (index: number) => setActive(Math.max(0, Math.min(options.length - 1, index)));
  const choose = (option: SelectOption) => { onChange(option.value); setOpen(false); };
  const onKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      if (!open) { const selectedIndex = options.findIndex(option => option.value === value); setActive(Math.max(0, Math.min(options.length - 1, selectedIndex + (event.key === "ArrowDown" ? 1 : -1)))); setOpen(true); }
      else move(active + (event.key === "ArrowDown" ? 1 : -1));
    } else if (event.key === "Home" && open) { event.preventDefault(); move(0); }
    else if (event.key === "End" && open) { event.preventDefault(); move(options.length - 1); }
    else if ((event.key === "Enter" || event.key === " ") && open) { event.preventDefault(); if (options[active]) choose(options[active]); }
    else if (event.key === "Escape" && open) { event.preventDefault(); setOpen(false); }
  };
  return <div className={`custom-select${open ? " open" : ""}`} onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setOpen(false); }}>
    <button type="button" role="combobox" aria-label={ariaLabel} aria-haspopup="listbox" aria-expanded={open} aria-controls={`${id}-listbox`} aria-activedescendant={open ? `${id}-option-${active}` : undefined} disabled={disabled} className="custom-select-trigger" onClick={() => setOpen(current => !current)} onKeyDown={onKeyDown}>
      <span title={selected?.title || selected?.label}>{selected?.label || placeholder || "请选择"}</span><ChevronDown size={15} aria-hidden="true" />
    </button>
    {open && <div role="listbox" id={`${id}-listbox`} aria-label={ariaLabel} className="custom-select-listbox">{options.map((option, index) => <div id={`${id}-option-${index}`} key={option.value} role="option" aria-selected={option.value === value} data-value={option.value} className={index === active ? "active" : ""} title={option.title || option.label} onMouseEnter={() => move(index)} onMouseDown={event => event.preventDefault()} onClick={() => choose(option)}><span>{option.label}</span>{option.description && <small>{option.description}</small>}</div>)}</div>}
  </div>;
}

export type Stage = { label: string; state: "completed" | "current" | "pending"; detail?: string; href?: string };

export function StageStepper({ ariaLabel, steps, compact = false }: { ariaLabel: string; steps: Stage[]; compact?: boolean }) {
  return <ol className={`stage-stepper${compact ? " compact" : ""}`} aria-label={ariaLabel}>{steps.map(step => <li key={step.label} className={step.state} aria-current={step.state === "current" ? "step" : undefined}>
    {step.href ? <a href={step.href}><strong>{step.label}</strong>{step.detail && <span>{step.detail}</span>}</a> : <div><strong>{step.label}</strong>{step.detail && <span>{step.detail}</span>}</div>}
    <small>{step.state === "completed" ? "已完成" : step.state === "current" ? "当前阶段" : "待开始"}</small>
  </li>)}</ol>;
}

export function ConclusionCard({ title, children, status, tone = "good" }: { title: string; children?: ReactNode; status?: ReactNode; tone?: "good" | "warning" | "bad" | "neutral" }) {
  return <section className={`conclusion-card ${tone}`}><div><h2>{title}</h2>{children && <p>{children}</p>}</div>{status}</section>;
}

export function ExpandableText({ label, children }: { label: string; children?: ReactNode }) {
  if (!children) return <span className="muted">未记录</span>;
  return <div className="expandable-text"><p className="line-clamp-3">{children}</p><details><summary>查看完整{label}</summary><p>{children}</p></details></div>;
}

export function ShortId({ value }: { value?: string | null }) {
  if (!value) return <span className="muted">未记录</span>;
  return <button type="button" className="short-id" title={`${value} · 点击复制`} aria-label={`复制 ID ${value}`} onClick={() => void navigator.clipboard?.writeText(value)}>{value.length > 24 ? `${value.slice(0, 7)}…${value.slice(-7)}` : value}</button>;
}
