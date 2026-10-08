import { useEffect, useId, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { createPortal } from "react-dom";
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

export function TruncatedText({ children, lines = 3 }: { children: ReactNode; lines?: 2 | 3 }) {
  const id = useId(), ref = useRef<HTMLSpanElement>(null);
  const [position, setPosition] = useState<{ left: number; top: number } | null>(null);
  const show = () => { const box = ref.current?.getBoundingClientRect(); if (box) setPosition({ left: Math.max(8, Math.min(box.left, window.innerWidth - 368)), top: Math.max(8, Math.min(box.bottom + 6, window.innerHeight - 210)) }); };
  return <><span ref={ref} tabIndex={0} className={`truncated-text line-clamp-${lines}`} aria-describedby={position ? id : undefined} onMouseEnter={show} onMouseLeave={() => setPosition(null)} onFocus={show} onBlur={() => setPosition(null)} onKeyDown={event => { if (event.key === "Escape") setPosition(null); }}>{children}</span>{position && createPortal(<div id={id} role="tooltip" className="text-tooltip" style={position}>{children}</div>, document.body)}</>;
}

export function TagList({ tags }: { tags: string[] }) {
  const id = useId(), button = useRef<HTMLButtonElement>(null), popup = useRef<HTMLDivElement>(null);
  const [position, setPosition] = useState<{ left: number; top: number } | null>(null);
  useEffect(() => { if (!position) return; const close = (event: PointerEvent) => { if (!button.current?.contains(event.target as Node) && !popup.current?.contains(event.target as Node)) setPosition(null); }; const escape = (event: globalThis.KeyboardEvent) => { if (event.key === "Escape") setPosition(null); }; document.addEventListener("pointerdown", close); document.addEventListener("keydown", escape); return () => { document.removeEventListener("pointerdown", close); document.removeEventListener("keydown", escape); }; }, [position]);
  return <div className="tag-list">{tags.slice(0, 2).map(tag => <Badge key={tag} tone="warning">{tag}</Badge>)}{tags.length > 2 && <button ref={button} className="badge neutral" aria-expanded={!!position} aria-controls={position ? id : undefined} aria-label={`${tags.length - 2} 个其他标签`} onClick={event => { event.stopPropagation(); const box = button.current?.getBoundingClientRect(); setPosition(position || !box ? null : { left: Math.max(8, Math.min(box.left, window.innerWidth - 368)), top: Math.min(box.bottom + 6, window.innerHeight - 160) }); }}>+{tags.length - 2}</button>}{position && createPortal(<div id={id} ref={popup} role="group" aria-label="其他标签" className="text-tooltip tag-popover" style={position}>{tags.slice(2).map(tag => <p key={tag}>{tag}</p>)}</div>, document.body)}</div>;
}

export function FixedTableCard({ children }: { children: ReactNode }) { return <div className="table-scroll fixed-table">{children}</div>; }

export function Disclosure({ label, children }: { label: string; children: ReactNode }) { return <details className="disclosure"><summary><ChevronDown size={14} aria-hidden="true" />{label}</summary>{children}</details>; }

export type SelectOption = { value: string; label: string; description?: string; title?: string };

export function CustomSelect({ ariaLabel, value, options, onChange, disabled = false, placeholder }: { ariaLabel: string; value: string; options: SelectOption[]; onChange: (value: string) => void; disabled?: boolean; placeholder?: string }) {
  const id = useId();
  const host = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(Math.max(0, options.findIndex(option => option.value === value)));
  useEffect(() => {
    if (!open) return;
    const outside = (event: PointerEvent) => { if (!host.current?.contains(event.target as Node)) setOpen(false); };
    const close = (event: globalThis.KeyboardEvent) => { if (event.key === "Escape") { setOpen(false); trigger.current?.focus(); } };
    const another = (event: Event) => { if ((event as CustomEvent).detail !== id) setOpen(false); };
    document.dispatchEvent(new CustomEvent("custom-select-open", { detail: id }));
    document.addEventListener("custom-select-open", another);
    document.addEventListener("pointerdown", outside); document.addEventListener("keydown", close);
    return () => { document.removeEventListener("pointerdown", outside); document.removeEventListener("keydown", close); document.removeEventListener("custom-select-open", another); };
  }, [open, id]);
  const selected = options.find(option => option.value === value);
  const move = (index: number) => setActive(Math.max(0, Math.min(options.length - 1, index)));
  const choose = (option: SelectOption) => { setOpen(false); trigger.current?.focus(); onChange(option.value); };
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
  return <div ref={host} className={`custom-select${open ? " open" : ""}`} onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setOpen(false); }}>
    <button ref={trigger} type="button" role="combobox" aria-label={ariaLabel} aria-haspopup="listbox" aria-expanded={open} aria-controls={`${id}-listbox`} aria-activedescendant={open ? `${id}-option-${active}` : undefined} disabled={disabled} className="custom-select-trigger" onClick={() => { setActive(Math.max(0, options.findIndex(option => option.value === value))); setOpen(current => !current); }} onKeyDown={onKeyDown}>
      <span title={selected?.title || selected?.label}>{selected?.label || placeholder || "请选择"}</span><ChevronDown size={15} aria-hidden="true" />
    </button>
    {open && <div role="listbox" id={`${id}-listbox`} aria-label={ariaLabel} className="custom-select-listbox">{options.map((option, index) => <div id={`${id}-option-${index}`} key={option.value} role="option" aria-selected={option.value === value} data-value={option.value} className={index === active ? "active" : ""} title={option.title || option.label} onMouseEnter={() => move(index)} onMouseDown={event => event.preventDefault()} onClick={event => { event.preventDefault(); event.stopPropagation(); choose(option); }}><span>{option.label}</span>{option.description && <small>{option.description}</small>}</div>)}</div>}
  </div>;
}

export type Stage = { label: string; state: "completed" | "current" | "pending" | "blocked"; detail?: string; href?: string };

export function StageStepper({ ariaLabel, steps, compact = false }: { ariaLabel: string; steps: Stage[]; compact?: boolean }) {
  return <ol className={`stage-stepper${compact ? " compact" : ""}`} aria-label={ariaLabel}>{steps.map(step => <li key={step.label} className={step.state} aria-current={step.state === "current" ? "step" : undefined}>
    {step.href ? <a href={step.href}><strong>{step.label}</strong>{step.detail && <span>{step.detail}</span>}</a> : <div><strong>{step.label}</strong>{step.detail && <span>{step.detail}</span>}</div>}
    <small>{step.state === "completed" ? "已完成" : step.state === "current" ? "当前阶段" : step.state === "blocked" ? "待处理" : "待开始"}</small>
  </li>)}</ol>;
}

export function ConclusionCard({ title, children, status, tone = "good" }: { title: string; children?: ReactNode; status?: ReactNode; tone?: "good" | "warning" | "bad" | "neutral" }) {
  return <section className={`conclusion-card ${tone}`}><div><h2>{title}</h2>{children && <p>{children}</p>}</div>{status}</section>;
}

export function ExpandableText({ children }: { label: string; children?: ReactNode }) {
  if (!children) return <span className="muted">未记录</span>;
  return <TruncatedText>{children}</TruncatedText>;
}

export function ShortId({ value }: { value?: string | null }) {
  if (!value) return <span className="muted">未记录</span>;
  return <button type="button" className="short-id" title={`${value} · 点击复制`} aria-label={`复制 ID ${value}`} onClick={() => void navigator.clipboard?.writeText(value)}>{value.length > 24 ? `${value.slice(0, 7)}…${value.slice(-7)}` : value}</button>;
}

export function ActionMenu({ label, children }: { label:string; children:ReactNode }) {
  const id=useId(), trigger=useRef<HTMLButtonElement>(null), menu=useRef<HTMLDivElement>(null), [open,setOpen]=useState(false);
  useEffect(()=>{
    const node=menu.current;
    const position=()=>{
      const button=trigger.current;
      if (!node || !button) return;
      const visible=node.matches(":popover-open"); setOpen(visible);
      if (!visible) return;
      const box=button.getBoundingClientRect();
      node.style.left=`${Math.max(8,Math.min(box.right-node.offsetWidth,innerWidth-node.offsetWidth-8))}px`;
      node.style.top=`${Math.max(8,Math.min(box.bottom+4,innerHeight-node.offsetHeight-8))}px`;
    };
    node?.addEventListener("toggle",position);
    return ()=>node?.removeEventListener("toggle",position);
  },[]);
  return <><button ref={trigger} type="button" className="secondary" aria-label={label} aria-haspopup="menu" aria-expanded={open} aria-controls={id} {...{popovertarget:id}}>⋯</button><div ref={menu} id={id} {...{popover:"auto"}} role="menu" aria-label={label} className="action-menu-content" onClick={event=>{if ((event.target as HTMLElement).closest("button,a")) menu.current?.hidePopover?.();}}>{children}</div></>;
}
