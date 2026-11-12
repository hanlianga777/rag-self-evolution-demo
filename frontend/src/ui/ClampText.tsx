import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState, type ReactNode, type CSSProperties } from "react";
import { createPortal } from "react-dom";
import { computeFloatPosition, type FloatPosition } from "./floating";

const OPEN_DELAY = 250;
const CLOSE_GRACE = 150;

/**
 * 长文本默认收起到 N 行；只有真的被截断时，悬停（或键盘聚焦）才浮出全文。
 * - 鼠标移开后有 150ms 缓冲，可以移进浮窗里滚动或选中文字；
 * - 点击"钉住"，再点外面或按 Esc 关闭；
 * - 关键数字和判定不要只放在这里——它们必须始终显示在主画面。
 */
export function ClampText({ text, children, hoverOnly = false, lines = 2, className = "", style }: { text: string; children?: ReactNode; hoverOnly?: boolean; lines?: number; className?: string; style?: CSSProperties }) {
  const ref = useRef<HTMLDivElement | null>(null);
  const floatRef = useRef<HTMLDivElement | null>(null);
  const timer = useRef<number | undefined>(undefined);
  const [truncated, setTruncated] = useState(false);
  const [open, setOpen] = useState(false);
  const [pinned, setPinned] = useState(false);
  const [position, setPosition] = useState<FloatPosition | null>(null);
  const floatId = useId();

  const measure = useCallback(() => {
    const node = ref.current;
    if (!node) return;
    const clipped = node.scrollHeight - node.clientHeight > 1 || node.scrollWidth - node.clientWidth > 1;
    setTruncated(clipped);
    if (!clipped) { setOpen(false); setPinned(false); }
  }, []);

  useLayoutEffect(() => { measure(); }, [measure, text, children, lines]);
  useEffect(() => {
    const node = ref.current;
    if (!node || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(measure);
    observer.observe(node);
    return () => observer.disconnect();
  }, [measure]);

  const clear = () => { if (timer.current !== undefined) window.clearTimeout(timer.current); timer.current = undefined; };
  const show = (delay = OPEN_DELAY) => { if (!truncated) return; clear(); timer.current = window.setTimeout(() => setOpen(true), delay); };
  const hide = () => { if (pinned) return; clear(); timer.current = window.setTimeout(() => setOpen(false), CLOSE_GRACE); };
  const close = useCallback(() => { clear(); setPinned(false); setOpen(false); }, []);

  useLayoutEffect(() => {
    if (!open || !ref.current) return;
    const size = floatRef.current ? { width: floatRef.current.offsetWidth, height: floatRef.current.offsetHeight } : { width: 440, height: 200 };
    setPosition(computeFloatPosition(ref.current.getBoundingClientRect(), size));
  }, [open, pinned]);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") close(); };
    const onDown = (event: MouseEvent) => {
      const target = event.target as Node;
      if (pinned && !ref.current?.contains(target) && !floatRef.current?.contains(target)) close();
    };
    const onScroll = () => { if (!pinned) close(); };
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onDown);
    window.addEventListener("scroll", onScroll, true);
    return () => { document.removeEventListener("keydown", onKey); document.removeEventListener("mousedown", onDown); window.removeEventListener("scroll", onScroll, true); };
  }, [open, pinned, close]);

  useEffect(() => () => clear(), []);

  return <>
    <div
      ref={ref}
      className={`ui-clamp ${className}`.trim()}
      style={{ WebkitLineClamp: lines, ...style }}
      data-truncated={truncated ? "true" : "false"}
      tabIndex={truncated ? 0 : undefined}
      aria-describedby={open ? floatId : undefined}
      onMouseEnter={() => show()}
      onMouseLeave={hide}
      onFocus={() => show(0)}
      onBlur={() => { if (!pinned) close(); }}
      onClick={() => { if (!truncated || hoverOnly) return; if (pinned) { close(); return; } clear(); setOpen(true); setPinned(true); }}
    >{children ?? text}</div>
    {open && truncated && createPortal(
      <div
        ref={floatRef}
        id={floatId}
        role="tooltip"
        className={`ui-float dark ui-clamp-float${pinned ? " pinned" : ""}`}
        style={{ top: position?.top ?? -9999, left: position?.left ?? -9999 }}
        onMouseEnter={clear}
        onMouseLeave={hide}
      >{children ?? text}</div>,
      document.body)}
  </>;
}
