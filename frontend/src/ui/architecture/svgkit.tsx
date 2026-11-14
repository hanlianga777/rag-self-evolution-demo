import type { ReactNode } from "react";
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
  gate?: string; gateRole?: string; focus?: boolean; value?: string; dot?: boolean;
  titleSize?: number;
};

/** 一个节点：白底细边圆角卡；Gate 节点蓝框；focus 节点浅蓝底。 */
export function Node({ x, y, w, h, icon, title, lines = [], gate, gateRole, focus, value, dot, titleSize = 12.5 }: NodeProps) {
  const Glyph = icon ? ICONS[icon] : null;
  const stroke = gate ? C.accent : focus ? "rgba(0,113,227,0.35)" : C.rule;
  const top = y + 20;
  return <g>
    {gate && <rect x={x - 3} y={y - 3} width={w + 6} height={h + 6} rx={13} fill="rgba(0,113,227,0.07)" />}
    <rect x={x} y={y} width={w} height={h} rx={10} fill={focus ? C.tint : C.surface} stroke={stroke} strokeWidth={gate ? 1.5 : 1} />
    {gate
      ? <text x={x + 11} y={top - 2} fontSize={10.5} fontWeight={700} fill={C.accent}>{gate}<tspan fontWeight={400} fill={C.muted} dx={4}>{gateRole}</tspan></text>
      : Glyph && <Glyph x={x + 10} y={y + 9} width={13} height={13} color={focus ? C.accent : C.muted} strokeWidth={1.8} />}
    <text x={gate ? x + 11 : x + 29} y={gate ? top + 16 : top} fontSize={titleSize} fontWeight={600} fill={C.ink}>{title}</text>
    {dot && <circle cx={x + w - 11} cy={y + 15} r={3} fill={C.accent} />}
    {value && <text x={x + 11} y={(gate ? top + 16 : top) + 19} fontSize={14} fontWeight={600} fill={C.ink}>{value}</text>}
    {lines.map((line, index) => <text key={index} x={x + 11} y={(gate ? top + 16 : top) + (value ? 36 : 18) + index * 15} fontSize={11} fill={C.muted}>{line}</text>)}
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

export function Figure({ label, viewBox, children, legend }: { label: string; viewBox: string; children: ReactNode; legend?: ReactNode }) {
  return <figure className="ui-arch-figure" aria-label={label}>
    <svg viewBox={viewBox} role="img" aria-label={label} className="ui-arch-svg">{children}</svg>
    {legend && <figcaption className="ui-arch-legend">{legend}</figcaption>}
  </figure>;
}
