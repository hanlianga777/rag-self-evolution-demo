import {
  Activity, Award, Ban, BarChart3, BookOpen, Brain, Bug, ChevronRight, CircleCheck, Info, ClipboardCheck, Clock3, Database, FileCheck, FileText,
  FlaskConical, Gauge, GitBranch, Hourglass, Layers, Library, ListChecks, ListX, Lock, MessageCircle, Play, Repeat, Rocket,
  ShieldCheck, SlidersHorizontal, Square, Target, Timer, Trophy, Waypoints, Wrench,
  ScanText, Scissors, Search, ArrowDownUp, Merge, Quote, Server, Monitor, Cpu, Network, Boxes, GitCompare, RefreshCw, Split, type LucideIcon,
} from "lucide-react";
import type { ReactNode } from "react";
import "./icons.css";

/**
 * 全站统一的线性图标（lucide-react，项目已有依赖）。
 * 规则：
 * - 只用这里登记过的语义名，页面不直接挑图标，保证同一个概念在每一页都是同一个图标；
 * - 统一 1.75 线宽、灰色；只有页面标题的图标块和主按钮里的图标用深色 / 白色；
 * - 图标只做"导读"，不替代文字：一律 aria-hidden，旁边必须有文字标签；
 * - 不用 emoji。
 */
export const ICONS = {
  // 页面（与左侧导航一致）
  overview: BarChart3, knowledge: BookOpen, pipeline: SlidersHorizontal, golden: ClipboardCheck,
  baseline: Waypoints, agent: FlaskConical, release: Rocket, verify: MessageCircle,
  // 指标
  correct: CircleCheck, fixed: Wrench, bad: Bug, gate: ShieldCheck, p99: Timer, p50: Clock3, refusal: Ban,
  budget: Gauge, layers: Layers, thinking: Brain, time: Hourglass, target: Target, data: Database, coverage: Library,
  // Agent 与发布
  rounds: Repeat, candidate: GitBranch, status: Activity, winner: Trophy, recommend: Award, rejected: ListX,
  report: FileCheck, checks: ListChecks, approval: Lock, doc: FileText,
  // 运行控制
  play: Play, stop: Square,
  // 导航与说明
  go: ChevronRight, info: Info,
  // 架构图与知识流程（11-12 新增）
  parse: ScanText, chunk: Scissors, search: Search, rerank: ArrowDownUp, merge: Merge, cite: Quote,
  server: Server, screen: Monitor, model: Cpu, network: Network, boxes: Boxes, compare: GitCompare, loop: RefreshCw, split: Split,
} satisfies Record<string, LucideIcon>;

export type IconName = keyof typeof ICONS;

export function Icon({ name, size = 16, className = "" }: { name: IconName; size?: number; className?: string }) {
  const Glyph = ICONS[name];
  return <Glyph size={size} strokeWidth={1.75} aria-hidden="true" focusable="false" className={`ui-icon ${className}`.trim()} />;
}

/** 页面标题、流程步骤前的图标块：白底细边圆角方块。 */
export function IconTile({ name, size = 18, small = false }: { name: IconName; size?: number; small?: boolean }) {
  return <span className={`ui-icon-tile${small ? " sm" : ""}`} aria-hidden="true"><Icon name={name} size={size} /></span>;
}

/** 图标 + 文字标签（指标名、小标题用）。 */
export function IconLabel({ name, children, className = "" }: { name?: IconName; children: ReactNode; className?: string }) {
  return <span className={`ui-icon-label ${className}`.trim()}>{name && <Icon name={name} size={14} />}{children}</span>;
}

/** 按文字猜流程步骤对应的页面图标（概览流程条、Golden 流水线用）；猜不到返回 undefined，调用方退回显示序号。 */
export function iconForStep(label: string): IconName | undefined {
  const rules: [RegExp, IconName][] = [
    [/知识/, "knowledge"], [/Golden|题卷|出题/, "golden"], [/Baseline|基线/, "baseline"], [/Agent|优化|Candidate/, "agent"],
    [/发布|上线/, "release"], [/问答|验证|反馈/, "verify"], [/Pipeline|配置/, "pipeline"],
  ];
  return rules.find(([pattern]) => pattern.test(label))?.[1];
}
