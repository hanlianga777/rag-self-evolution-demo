import { useEffect, useLayoutEffect, useId, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
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
  const tone = /fail|rejected|not[\s_-]*qualified|needs_revision/i.test(value) ? "bad" : /pass|completed|indexed|released|reviewed|qualified|evaluated/i.test(value) ? "good" : /running|evaluating|queued/i.test(value) ? "accent" : /pending|human_review|not_run|not_evaluable|legacy/i.test(value) ? "warning" : "neutral";
  return <Badge tone={tone}>{displayText(value)}</Badge>;
}

export function TruncatedText({ children, lines = 2 }: { children: ReactNode; lines?: 2 | 3 }) {
  const id = useId(), ref = useRef<HTMLSpanElement>(null);
  const [position, setPosition] = useState<{ left: number; top: number } | null>(null);
  const show = () => { const node=ref.current; if (!node || node.scrollHeight<=node.clientHeight && node.scrollWidth<=node.clientWidth) return; const box = node.getBoundingClientRect(); if (box) setPosition({ left: Math.max(8, Math.min(box.left, window.innerWidth - 368)), top: Math.max(8, Math.min(box.bottom + 6, window.innerHeight - 210)) }); };
  useEffect(()=>{ if(!position)return; const close=(event:Event)=>{if(!(event.target instanceof Element && event.target.closest('[role="tooltip"]')))setPosition(null);}; window.addEventListener("resize",close); document.addEventListener("scroll",close,true); return ()=>{window.removeEventListener("resize",close);document.removeEventListener("scroll",close,true);}; },[position]);
  return <><span ref={ref} tabIndex={0} className={`truncated-text line-clamp-${lines}`} aria-describedby={position ? id : undefined} onMouseEnter={show} onMouseLeave={() => setPosition(null)} onFocus={show} onBlur={() => setPosition(null)} onKeyDown={event => { if (event.key === "Escape") setPosition(null); }}>{children}</span>{position && createPortal(<div id={id} role="tooltip" className="text-tooltip" style={position}>{children}</div>, document.body)}</>;
}

export function FixedTableCard({ children }: { children: ReactNode }) { return <div className="table-scroll fixed-table">{children}</div>; }

export function Disclosure({ label, children }: { label: string; children: ReactNode }) { return <details className="disclosure"><summary><ChevronDown size={14} aria-hidden="true" />{label}</summary>{children}</details>; }

export type SelectOption = { value: string; label: string; description?: string; title?: string };

export function CustomSelect({ ariaLabel, value, options, onChange, disabled = false, placeholder }: { ariaLabel: string; value: string; options: SelectOption[]; onChange: (value: string) => void; disabled?: boolean; placeholder?: string }) {
  const id = useId();
  const host = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const list = useRef<HTMLDivElement>(null);
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
  useLayoutEffect(()=>{
    const popup=list.current, button=trigger.current;
    if(!open || !popup || !button)return;
    popup.showPopover?.();
    const box=button.getBoundingClientRect(), below=innerHeight-box.bottom-8, above=box.top-8;
    const upward=below<Math.min(280,popup.scrollHeight) && above>below;
    popup.style.width=`${Math.min(Math.max(box.width,180),innerWidth-16)}px`;
    popup.style.maxHeight=`${Math.min(280,Math.max(40,upward?above:below))}px`;
    popup.style.left=`${Math.max(8,Math.min(box.left,innerWidth-popup.offsetWidth-8))}px`;
    popup.style.top=`${upward?Math.max(8,box.top-popup.offsetHeight-4):box.bottom+4}px`;
    const close=(event:Event)=>{if(!popup.contains(event.target as Node))setOpen(false);};
    document.addEventListener("scroll",close,true);window.addEventListener("resize",close);
    return ()=>{document.removeEventListener("scroll",close,true);window.removeEventListener("resize",close);};
  },[open]);
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
    {open && <div ref={list} {...{popover:"manual"}} role="listbox" id={`${id}-listbox`} aria-label={ariaLabel} className="custom-select-listbox">{options.map((option, index) => <div id={`${id}-option-${index}`} key={option.value} role="option" aria-selected={option.value === value} data-value={option.value} className={index === active ? "active" : ""} title={option.title || option.label} onMouseEnter={() => move(index)} onMouseDown={event => event.preventDefault()} onClick={event => { event.preventDefault(); event.stopPropagation(); choose(option); }}><span>{option.label}</span>{option.description && <small>{option.description}</small>}</div>)}</div>}
  </div>;
}

export type Stage = { label: string; state: "completed" | "current" | "pending" | "blocked"; detail?: string; href?: string; onSelect?: () => void };

export function StageStepper({ ariaLabel, steps, compact = false }: { ariaLabel: string; steps: Stage[]; compact?: boolean }) {
  return <ol className={`stage-stepper${compact ? " compact" : ""}`} aria-label={ariaLabel}>{steps.map(step => <li key={step.label} className={step.state} aria-current={step.state === "current" ? "step" : undefined}>
    {step.onSelect ? <button type="button" onClick={step.onSelect}><strong>{step.label}</strong>{step.detail && <span>{step.detail}</span>}</button> : step.href ? <a href={step.href}><strong>{step.label}</strong>{step.detail && <span>{step.detail}</span>}</a> : <div><strong>{step.label}</strong>{step.detail && <span>{step.detail}</span>}</div>}
    <small>{step.state === "completed" ? "✓ 已完成" : step.state === "current" ? "当前阶段" : step.state === "blocked" ? "待处理" : "待开始"}</small>
  </li>)}</ol>;
}

export function ConclusionCard({ title, children, status, tone = "good" }: { title: string; children?: ReactNode; status?: ReactNode; tone?: "good" | "warning" | "bad" | "neutral" }) {
  return <section className={`conclusion-card ${tone}`}><div><h2>{title}</h2>{children && <p>{children}</p>}</div>{status}</section>;
}

export function ShortId({ value }: { value?: string | null }) {
  if (!value) return <span className="muted">未记录</span>;
  return <button type="button" className="short-id" title={`${value} · 点击复制`} aria-label={`复制 ID ${value}`} onClick={() => void navigator.clipboard?.writeText(value)}>{value.length > 24 ? `${value.slice(0, 7)}…${value.slice(-7)}` : value}</button>;
}

export function ActionMenu({ label, children, triggerText = "⋯" }: { label:string; children:ReactNode; triggerText?: string }) {
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
  return <><button ref={trigger} type="button" className="secondary" aria-label={label} aria-haspopup="menu" aria-expanded={open} aria-controls={id} {...{popovertarget:id}}>{triggerText}</button><div ref={menu} id={id} {...{popover:"auto"}} role="menu" aria-label={label} className="action-menu-content" onClick={event=>{if ((event.target as HTMLElement).closest("button,a")) menu.current?.hidePopover?.();}}>{children}</div></>;
}

/** One track style for both completion and proportions; thresholds are optional. */
export function ProgressBar({ value, max = 100, label, failed = false, threshold }: { value: number; max?: number; label: string; failed?: boolean; threshold?: number }) {
  const percent = max > 0 ? Math.max(0, Math.min(100, value / max * 100)) : 0;
  return <div className={`progress-track${failed ? " failed" : ""}`} role="progressbar" aria-label={label} aria-valuemin={0} aria-valuemax={max} aria-valuenow={value}><span style={{ width: `${percent}%` }} />{threshold != null && max > 0 && <i className="progress-threshold" style={{ left: `${Math.max(0, Math.min(100, threshold / max * 100))}%` }} title={`门槛 ${threshold}`} />}</div>;
}

export function DrawerSection({ title, children }: { title: string; children: ReactNode }) {
  return <section className="drawer-section"><h3>{title}</h3>{children}</section>;
}

export function DrawerFooter({ children }: { children: ReactNode }) { return <div className="detail-footer">{children}</div>; }

export function EmptyState({ title, children, action }: { title: string; children: ReactNode; action?: ReactNode }) {
  return <div className="empty-state"><p>{title}</p><p className="muted">{children}</p>{action}</div>;
}

export function MoreMenu({ children }: { children: ReactNode }) { return <ActionMenu label="页面更多操作" triggerText="更多">{children}</ActionMenu>; }

export function TechnicalDetails({ children }: { children: ReactNode }) { return <Disclosure label="技术详情">{children}</Disclosure>; }
