import { HoverCard } from "../HoverCard";
import { StatTransition, StatusBadge, type StatusKind } from "../Primitives";

/**
 * 概览 →「项目概览」首屏。
 * - 主成果：答对 from → to（最大字号），下方三枚事实：修好 N、新增 Bad Case 0、Hard Gate x/y；
 * - 次要指标：P99、P50、安全拒答率、评测预算；
 * - 一条真实状态：Candidate D 推荐待发布 ｜ 当前线上：初始配置（状态由调用方从同一份线上版本数据算出，不写死）；
 * - 流程条：6 步，每步只写一个事实；悬停看补充；点击跳转。
 */
export type FlowStep = { label: string; fact: string; tips?: string[]; onClick?: () => void };
export type Pair = { from: number | null; to: number | null };

export function OverviewSummary({ correct, total, fixedCount, newBadCount, gates, p99, p50, safeRefusal, budget, status, flow, primaryAction }: {
  correct: Pair; total: number; fixedCount: number | null; newBadCount: number | null; gates: { passed: number; total: number } | null;
  p99: Pair; p50: Pair; safeRefusal: Pair; budget: { used: number; max: number } | null;
  status: { kind: StatusKind; candidate: string; online: string };
  flow: FlowStep[];
  primaryAction?: { label: string; onClick: () => void };
}) {
  return <div className="ui-ov">
    <section className="ui-ov-hero" aria-label="优化成果">
      <div className="ui-ov-main">
        <span className="ui-ov-label">答对（Baseline → 最终推荐）</span>
        <div className="ui-ov-big"><StatTransition from={correct.from} to={correct.to} unit={`/ ${total}`} /></div>
        <div className="ui-ov-facts">
          <span className="ui-ov-fact good">修好 <b className="ui-num">{fixedCount ?? "未知"}</b></span>
          <span className="ui-ov-fact">新增 Bad Case <b className="ui-num">{newBadCount ?? "未知"}</b></span>
          <span className="ui-ov-fact">Hard Gate <b className="ui-num">{gates ? `${gates.passed} / ${gates.total}` : "未知"}</b></span>
        </div>
      </div>
      <dl className="ui-ov-side">
        <div><dt>P99</dt><dd><StatTransition from={p99.from} to={p99.to} unit="秒" better="lower" digits={1} /></dd></div>
        <div><dt>P50</dt><dd><StatTransition from={p50.from} to={p50.to} unit="秒" better="lower" digits={1} /></dd></div>
        <div><dt>安全拒答率</dt><dd><StatTransition from={safeRefusal.from} to={safeRefusal.to} unit="%" /></dd></div>
        <div><dt>评测预算</dt><dd className="ui-num"><b>{budget ? budget.used : "未知"}</b>{budget && <span className="ui-ov-of"> / {budget.max} 次</span>}</dd></div>
      </dl>
    </section>

    <div className="ui-ov-status">
      <span className="ui-ov-status-item"><StatusBadge kind={status.kind} /> {status.candidate}</span>
      <span className="ui-ov-divider" aria-hidden="true" />
      <span className="ui-ov-status-item">当前线上：{status.online}</span>
      {primaryAction && <button type="button" className="primary ui-ov-action" onClick={primaryAction.onClick}>{primaryAction.label}</button>}
    </div>

    <nav className="ui-ov-flow" aria-label="从知识到线上改善">
      {flow.map((step, index) => {
        const inner = <button type="button" className="ui-ov-step" onClick={step.onClick}>
          <span className="ui-ov-step-no ui-num">{index + 1}</span>
          <span className="ui-ov-step-text"><strong>{step.label}</strong><small>{step.fact}</small></span>
        </button>;
        return <div className="ui-ov-step-wrap" key={step.label}>
          {step.tips?.length ? <HoverCard content={<div>{step.tips.map(tip => <div key={tip}>{tip}</div>)}</div>}>{inner}</HoverCard> : inner}
          {index < flow.length - 1 && <span className="ui-ov-arrow" aria-hidden="true" />}
        </div>;
      })}
    </nav>
  </div>;
}

/** Agent 工作台顶部的紧凑统计，替换原来六张同样的绿色"已完成"卡。 */
export function AgentStats({ rounds, candidates, budget, status }: { rounds: number; candidates: number; budget: { used: number; max: number } | null; status: { kind: StatusKind; text: string } }) {
  return <dl className="ui-agent-stats">
    <div><dt>轮次</dt><dd className="ui-num">{rounds}</dd></div>
    <div><dt>Candidate</dt><dd className="ui-num">{candidates}</dd></div>
    <div><dt>评测预算</dt><dd className="ui-num">{budget ? <>{budget.used}<span> / {budget.max}</span></> : "未知"}</dd></div>
    <div className="wide"><dt>当前状态</dt><dd><StatusBadge kind={status.kind} /> <span className="ui-agent-status-text">{status.text}</span></dd></div>
  </dl>;
}
