import { createContext, useContext, useRef, useState, type MouseEvent, type ReactNode } from "react";
import { ICONS, type IconName } from "../icons";

/**
 * 架构图共用的 SVG 小部件（11-13，总指挥编写）。
 * 所有图都画在固定坐标的 viewBox 里，宽度 100% 自适应；文字用页面字体。
 * 颜色与 ui.css 的设计变量取值一致（SVG 属性里不用 CSS 变量，避免个别浏览器不解析）。
 */

export const C = {
  ink: "#1d1d1f",
  ink2: "#424245",
  muted: "#6e6e73",
  faint: "#aeaeb2",
  rule: "#e5e5ea",
  rule2: "#f0f0f3",
  accent: "#0071e3",
  tint: "#eaf3fe",
  surface: "#ffffff",
};

/** 粗略估算文字宽度（中文按 1 em，西文按 0.58 em），用来给连线标签垫白底。 */
export function textWidth(text: string, size: number) {
  let width = 0;
  for (const ch of text) width += ch.charCodeAt(0) > 255 ? size : size * 0.58;
  return width;
}

export function Defs({ id }: { id: string }) {
  return <defs>
    <marker id={`${id}-a`} viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0 L8 4 L0 8 z" fill={C.faint} /></marker>
    <marker id={`${id}-b`} viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0 L8 4 L0 8 z" fill={C.accent} /></marker>
  </defs>;
}

export type NodeProps = {
  x: number; y: number; w: number; h: number;
  icon?: IconName; title: string; lines?: string[];
  /** 人工关口徽标，例如 "Gate 1"：画在卡片右上角，不挤占标题位置。 */
  badge?: string;
  /** 兼容旧写法：gate 等同 badge，gateRole 不再显示。 */
  gate?: string; gateRole?: string;
  focus?: boolean; value?: string; dot?: boolean; dashed?: boolean;
  titleSize?: number;
  /** 右上角的小号灰字，例如厂商名。 */
  corner?: string;
  /** 悬停提示（显示问号光标与深色说明卡）。 */
  tip?: string;
};

type TipState = { text: string; x: number; y: number } | null;
const TipContext = createContext<((tip: TipState) => void) | null>(null);

/** 一个节点：白底细边圆角卡；Gate 节点蓝框 + 右上角徽标；focus 浅蓝底；dashed 虚线框。 */
export function Node({ x, y, w, h, icon, title, lines = [], badge, gate, focus, value, dot, dashed, titleSize = 12.5, corner, tip }: NodeProps) {
  const setTip = useContext(TipContext);
  const Glyph = icon ? ICONS[icon] : null;
  const mark = badge ?? gate;
  const stroke = mark ? C.accent : focus ? "rgba(0,113,227,0.35)" : dashed ? C.faint : C.rule;
  const top = y + 20;
  const badgeWidth = mark ? textWidth(mark, 10) + 14 : 0;
  const show = (event: MouseEvent<SVGGElement>) => {
    if (!tip || !setTip) return;
    const host = event.currentTarget.ownerSVGElement?.parentElement?.getBoundingClientRect();
    if (host) setTip({ text: tip, x: event.clientX - host.left, y: event.clientY - host.top });
  };
  return <g className={tip ? "ui-arch-tip" : undefined} onMouseMove={show} onMouseLeave={() => tip && setTip?.(null)}>
    {tip && <title>{tip}</title>}
    {mark && <rect x={x - 3} y={y - 3} width={w + 6} height={h + 6} rx={13} fill="rgba(0,113,227,0.07)" />}
    <rect x={x} y={y} width={w} height={h} rx={10} fill={focus ? C.tint : C.surface} stroke={stroke} strokeWidth={mark ? 1.5 : 1} strokeDasharray={dashed ? "4 3" : undefined} />
    {mark && <g>
      <rect x={x + w - badgeWidth - 8} y={y - 8} width={badgeWidth} height={16} rx={8} fill={C.accent} />
      <text x={x + w - badgeWidth / 2 - 8} y={y + 3.5} fontSize={10} fontWeight={600} textAnchor="middle" fill="#fff">{mark}</text>
    </g>}
    {Glyph && <Glyph x={x + 10} y={y + 9} width={13} height={13} color={focus || mark ? C.accent : C.muted} strokeWidth={1.8} />}
    <text x={Glyph ? x + 29 : x + 11} y={top} fontSize={titleSize} fontWeight={600} fill={C.ink}>{title}</text>
    {corner && <text x={x + w - 10} y={top} fontSize={10} textAnchor="end" fill={C.faint}>{corner}</text>}
    {tip && <text x={x + w - 9} y={y + h - 8} fontSize={10.5} textAnchor="end" fill={C.faint}>ⓘ</text>}
    {dot && <circle cx={x + w - 11} cy={y + 15} r={3} fill={C.accent} />}
    {value && <text x={x + 11} y={top + 19} fontSize={14} fontWeight={600} fill={C.ink}>{value}</text>}
    {lines.map((line, index) => <text key={index} x={x + 11} y={top + (value ? 36 : 18) + index * 15} fontSize={11} fill={C.muted}>{line}</text>)}
  </g>;
}

/** 连线标签：浅灰小字，垫白底避免压线。 */
export function Tag({ x, y, text, accent, anchor = "middle", bg = C.surface }: { x: number; y: number; text: string; accent?: boolean; anchor?: "start" | "middle" | "end"; bg?: string }) {
  const width = textWidth(text, 11) + 12;
  const left = anchor === "middle" ? x - width / 2 : anchor === "end" ? x - width : x;
  return <g>
    <rect x={left} y={y - 12} width={width} height={17} rx={8.5} fill={bg} />
    <text x={left + width / 2} y={y} fontSize={11} textAnchor="middle" fill={accent ? C.accent : C.muted}>{text}</text>
  </g>;
}

/** 连线：d 为 SVG path；accent 用蓝色；dashed 表示回流或"同一份数据"。 */
export function Wire({ d, id, accent, dashed, width = 1.4 }: { d: string; id: string; accent?: boolean; dashed?: boolean; width?: number }) {
  return <path d={d} fill="none" stroke={accent ? C.accent : C.faint} strokeWidth={width} strokeDasharray={dashed ? "5 4" : undefined} markerEnd={`url(#${id}-${accent ? "b" : "a"})`} strokeLinecap="round" strokeLinejoin="round" />;
}

export function Lane({ x, y, index, name, note, accent }: { x: number; y: number; index: string; name: string; note?: string; accent?: boolean }) {
  return <text x={x} y={y} fontSize={12} fill={accent ? C.accent : C.faint} fontWeight={600}>{index}
    <tspan dx={6} fill={C.ink} fontSize={13}>{name}</tspan>
    {note && <tspan dx={8} fill={C.muted} fontWeight={400} fontSize={11.5}>{note}</tspan>}
  </text>;
}

/** 左侧泳道标签列 + 浅灰底带：标题在同一列严格对齐，不受连线影响。 */
export function Band({ x, y, w, h, labelWidth, index, name, note, accent }: { x: number; y: number; w: number; h: number; labelWidth: number; index: string; name: string; note?: string[]; accent?: boolean }) {
  return <g>
    <rect x={x} y={y} width={w} height={h} rx={14} fill={accent ? "rgba(0,113,227,0.04)" : "#fafafb"} />
    <text x={x + 14} y={y + 24} fontSize={11.5} fontWeight={600} fill={accent ? C.accent : C.faint}>{index}</text>
    <text x={x + 14} y={y + 44} fontSize={14} fontWeight={600} fill={C.ink}>{name}</text>
    {(note ?? []).map((line, i) => <text key={i} x={x + 14} y={y + 64 + i * 15} fontSize={11} fill={C.muted}>{line}</text>)}
    <line x1={x + labelWidth - 8} x2={x + labelWidth - 8} y1={y + 14} y2={y + h - 14} stroke={C.rule} />
  </g>;
}

export function Figure({ label, viewBox, children, legend }: { label: string; viewBox: string; children: ReactNode; legend?: ReactNode }) {
  const [tip, setTip] = useState<TipState>(null);
  const host = useRef<HTMLDivElement>(null);
  const width = host.current?.clientWidth ?? 0;
  return <figure className="ui-arch-figure" aria-label={label}>
    <div className="ui-arch-host" ref={host}>
      <TipContext.Provider value={setTip}>
        <svg viewBox={viewBox} role="img" aria-label={label} className="ui-arch-svg">{children}</svg>
      </TipContext.Provider>
      {tip && <div className="ui-arch-tipcard" role="tooltip" style={{ left: Math.min(tip.x + 14, Math.max(0, width - 300)), top: tip.y + 16 }}>{tip.text}</div>}
    </div>
    {legend && <figcaption className="ui-arch-legend">{legend}</figcaption>}
  </figure>;
}
