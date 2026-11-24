import { useEffect, useId, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { computeFloatPosition, type FloatPosition } from "./floating";

/**
 * 深色悬停提示卡：给题号徽章、流程节点、图表数据点补充 3–5 行细节。
 * 内容只是"补充"，主画面上的关键数字不能只藏在这里。
 * 键盘聚焦触发元素时同样显示。
 */
export function HoverCard({ content, children, delay = 120, className = "" }: { content: ReactNode; children: ReactNode; delay?: number; className?: string }) {
  const ref = useRef<HTMLSpanElement | null>(null);
  const floatRef = useRef<HTMLDivElement | null>(null);
  const timer = useRef<number | undefined>(undefined);
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState<FloatPosition | null>(null);
  const id = useId();

  const clear = () => { if (timer.current !== undefined) window.clearTimeout(timer.current); timer.current = undefined; };
  const show = () => { clear(); timer.current = window.setTimeout(() => setOpen(true), delay); };
  const hide = () => { clear(); setOpen(false); };

  useLayoutEffect(() => {
    if (!open || !ref.current) return;
    const size = floatRef.current ? { width: floatRef.current.offsetWidth, height: floatRef.current.offsetHeight } : { width: 320, height: 120 };
    setPosition(computeFloatPosition(ref.current.getBoundingClientRect(), size));
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") hide(); };
    document.addEventListener("keydown", onKey);
    window.addEventListener("scroll", hide, true);
    return () => { document.removeEventListener("keydown", onKey); window.removeEventListener("scroll", hide, true); };
  }, [open]);

  useEffect(() => () => clear(), []);

  return <>
    <span ref={ref} className={`ui-hover-trigger ${className}`.trim()} onMouseEnter={show} onMouseLeave={hide} onFocus={show} onBlur={hide} aria-describedby={open ? id : undefined}>{children}</span>
    {open && createPortal(<div ref={floatRef} id={id} role="tooltip" className="ui-float dark" style={{ top: position?.top ?? -9999, left: position?.left ?? -9999 }}>{content}</div>, document.body)}
  </>;
}
