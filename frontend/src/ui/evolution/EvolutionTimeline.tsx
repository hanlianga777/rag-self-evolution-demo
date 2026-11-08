import { agentDisplayText } from "../../display";
import type { ReactNode } from "react";
import { HoverCard } from "../HoverCard";
import { ClampText } from "../ClampText";
import { ParamChip, QuestionList, StatusBadge, type QuestionTone } from "../Primitives";
import type { CandidateView, EvolutionModel } from "./model";

/**
 * Agent 工作台 →「进化路线」主视图。
 * 结构：Baseline 起点一行 → 每轮一段（轮次结论一行 + 三张等高 Candidate 卡）→ children（Candidate D 区块，沿用现有 DStory）。
 * - 卡片字段顺序固定：方向 → 参数变化 → 修好 → 新增 Bad Case → Hard Gate → 答对与耗时。
 * - Winner 卡用深色描边；效率方向标注小标签；每轮最快的 Candidate 的 P50 加粗。
 * - 点击卡片打开现有的方案详情抽屉（onOpen）。
 */
export type BaselineView = { correct: number | null; total: number; badCases: { id: string; layer: string; question?: string }[] };

export function EvolutionTimeline({ model, baseline, questionText, onOpen, onOpenDiagnosis, children }: {
  model: EvolutionModel; baseline: BaselineView; questionText?: (id: string) => string | undefined;
  onOpen?: (candidateId: string) => void; onOpenDiagnosis?: () => void; children?: ReactNode;
}) {
  const layers = Array.from(new Set(baseline.badCases.map(item => item.layer)));
  return <section className="ui-evo" aria-label="进化路线">
    <div className="ui-evo-start">
      <div className="ui-evo-start-main">
        <span className="ui-evo-step">Baseline</span>
        <strong className="ui-num">{baseline.correct ?? "未知"} / {baseline.total}</strong>
        <span className="ui-evo-sep" aria-hidden="true" />
        <span>{baseline.badCases.length} 个 Bad Case</span>
        {layers.map(layer => {
          const items = baseline.badCases.filter(item => item.layer === layer);
          return <span key={layer} className="ui-evo-layer">{layer} {items.length}<QuestionList items={items.map(item => ({ id: item.id, tone: "open" as QuestionTone, question: item.question ?? questionText?.(item.id) }))} /></span>;
        })}
      </div>
      {onOpenDiagnosis && <button type="button" className="text-button ui-evo-link" onClick={onOpenDiagnosis}>查看 Bad Case 诊断</button>}
    </div>

    {model.rounds.map(round => <div className="ui-evo-round" key={round.round}>
      <div className="ui-evo-rail" aria-hidden="true"><span className={`ui-evo-dot${round.candidates.some(item => item.winner) ? " win" : ""}`} /></div>
      <div className="ui-evo-body">
        <header className="ui-evo-round-head"><h3>Round {round.round}</h3><p>{round.summary}</p></header>
        {round.lesson && <HoverCard content={<div style={{ whiteSpace: "pre-line", maxWidth: 520 }}>{round.lesson.source}</div>}><p className="ui-body-muted" tabIndex={0}>本轮经验：{round.lesson.text}</p></HoverCard>}
        <div className="ui-evo-cards">{round.candidates.map(item => <CandidateCard key={item.id} item={item} fastest={item.id === round.fastestId} questionText={questionText} onOpen={onOpen} />)}</div>
      </div>
    </div>)}

    {children && <div className="ui-evo-round ui-evo-final">
      <div className="ui-evo-rail" aria-hidden="true"><span className="ui-evo-dot win" /></div>
      <div className="ui-evo-body">{children}</div>
    </div>}
  </section>;
}

function CandidateCard({ item, fastest, questionText, onOpen }: { item: CandidateView; fastest: boolean; questionText?: (id: string) => string | undefined; onOpen?: (id: string) => void }) {
  const status = !item.complete ? <StatusBadge kind="running" label="评测中" /> : item.winner ? <StatusBadge kind="winner" /> : item.qualified ? <StatusBadge kind="qualified" /> : <StatusBadge kind="failed" />;
  const open = onOpen ? () => onOpen(item.id) : undefined;
  return <article className={`ui-evo-card${item.winner ? " winner" : ""}`} tabIndex={open ? 0 : undefined} role={open ? "button" : undefined} aria-label={open ? `查看 ${item.name} 详情` : undefined}
    onClick={open} onKeyDown={event => { if (open && (event.key === "Enter" || event.key === " ")) { event.preventDefault(); open(); } }}>
    <header className="ui-evo-card-head"><strong>Candidate {item.label}</strong>{status}</header>
    <div className="ui-evo-dir">
      <ClampText text={agentDisplayText(item.direction || "方向未保存")} lines={1} />
      {item.efficiency && <span className="ui-evo-tag">效率方向</span>}
    </div>
    <div className="ui-evo-params">{item.params.length ? item.params.map(param => <ParamChip key={param.key} label={param.label} from={param.from} to={param.to} />) : <span className="ui-evo-none">参数变化未保存</span>}</div>
    <dl className="ui-evo-facts">
      <dt>修好</dt><dd><QuestionList items={item.fixed.map(id => ({ id, tone: "fixed" as QuestionTone, question: questionText?.(id) }))} /></dd>
      <dt>新增 Bad Case</dt><dd>{item.complete && item.newFailures === 0 ? "0" : <QuestionList items={item.broken.map(id => ({ id, tone: "broken" as QuestionTone, question: questionText?.(id), detail: "Baseline 答对 → 本 Candidate 答错" }))} />}</dd>
      <dt>Hard Gate</dt><dd>{item.gateFailures.length ? <span className="ui-evo-fail">{item.gateFailures.join("；")}</span> : item.complete ? <span className="ui-evo-pass">{item.gates ? `${item.gates.passed} / ${item.gates.total}` : '全部通过'}</span> : "评测中"}</dd>
    </dl>
    <footer className="ui-evo-card-foot ui-num">
      <span>答对 <b>{item.correct ?? "未知"}</b> / {item.total ?? 50}</span>
      <span>P50 {fastest ? <b>{fmt(item.p50)}</b> : fmt(item.p50)}　P99 {fmt(item.p99)}</span>
    </footer>
  </article>;
}

const fmt = (value: number | null) => value === null ? "未知" : `${value.toFixed(1)} 秒`;
