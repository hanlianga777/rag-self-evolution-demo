import {RoundNarrative} from '../../components/RoundStrategy';
import { Fragment, useEffect, useState } from "react";
import { storyText } from "../../components/EvolutionStory";
import { agentDisplayText } from "../../display";
import type { ReactNode } from "react";
import { HoverCard } from "../HoverCard";
import { ClampText } from "../ClampText";
import { ParamChip, QuestionList, StatusBadge, type QuestionTone } from "../Primitives";
import type { CandidateView, EvolutionModel } from "./model";

/**
 * Agent 工作台 →「进化路线」主视图。
 * 结构：轮次按钮切换单轮策略与三张等高卡；D 按钮展示现有 DStory。
 * - 卡片字段顺序固定：方向 → 参数变化 → 修好 → 新增 Bad Case → Hard Gate → 答对与耗时。
 * - Winner 卡用深色描边；效率方向标注小标签；每轮最快的 Candidate 的 P50 加粗。
 * - 点击卡片打开现有的方案详情抽屉（onOpen）。
 */
export type BaselineView = { correct: number | null; total: number; badCases: { id: string; layer: string; question?: string }[] };

export function EvolutionTimeline({ model, experiment, sandbox, renderCandidate, onRoundChange, questionText, onOpen, children, roundHeader }: {
  model: EvolutionModel; experiment?:any; renderCandidate?:(id:string)=>ReactNode; onRoundChange?:(round:number)=>void; sandbox?:(round:number)=>ReactNode; baseline?: BaselineView; questionText?: (id: string) => string | undefined;
  onOpen?: (candidateId: string) => void; onOpenDiagnosis?: () => void; children?: ReactNode; roundHeader?: (round: number) => ReactNode;
}) {
  const [selection, setSelection] = useState<number | "D">(1);
  const selected = model.rounds.some(round => round.round === selection) ? selection : selection === "D" ? "D" : model.rounds[0]?.round;
  useEffect(()=>{if(typeof selected==='number')onRoundChange?.(selected);},[selected,onRoundChange]);
  return <section className="ui-evo" aria-label="进化路线">
    <div className="story-round-switch route-round-switch" role="group" aria-label="进化轮次">
      {model.rounds.map(round => <button type="button" className="secondary" key={round.round} aria-pressed={selected === round.round} onClick={event => {setSelection(round.round);onRoundChange?.(round.round);const scroll=event.currentTarget.closest<HTMLElement>(".page-content");if(scroll)scroll.scrollTop=0;}}>Round {round.round}</button>)}
      <button type="button" className="secondary" aria-pressed={selected === "D"} onClick={event => {setSelection("D");const scroll=event.currentTarget.closest<HTMLElement>(".page-content");if(scroll)scroll.scrollTop=0;}}>Candidate D</button>
    </div>

    {!model.rounds.length && <div><RoundNarrative experiment={experiment} round={1} onOpen={onOpen}/>{sandbox?.(1)}</div>}
    {model.rounds.filter(round => round.round === selected).map(round => <div className="ui-evo-round" key={round.round}>
      <div className="ui-evo-rail" aria-hidden="true"><span className={`ui-evo-dot${round.candidates.some(item => item.winner) ? " win" : ""}`} /></div>
      <div className="ui-evo-body">
        {roundHeader?.(round.round)}
        <RoundNarrative experiment={experiment} round={round.round} onOpen={onOpen}/>
        <div className="ui-evo-cards candidate-cards">{round.candidates.map(item => renderCandidate?<Fragment key={item.id}>{renderCandidate(item.id)}</Fragment>:<CandidateCard key={item.id} item={item} fastest={item.id === round.fastestId} questionText={questionText} onOpen={onOpen}/>)}</div>{sandbox?.(round.round)}
      </div>
    </div>)}

    {selected === "D" && children && <div className="ui-evo-round ui-evo-final">
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
    <div className="agent-design-intent"><strong>设计用意</strong><p>{item.intent ? storyText(item.intent) : "—"}</p></div>
    <div className="ui-evo-params plain-parameter-diff">{item.params.length ? item.params.map(param => <div key={param.key}>{param.label}：{param.from} → {param.to}</div>) : <span className="ui-evo-none">参数变化未保存</span>}</div>
    <dl className="ui-evo-facts">
      <dt>修好</dt><dd><QuestionList items={item.fixed.map(id => ({ id, tone: "fixed" as QuestionTone, question: questionText?.(id) }))} /></dd>
      <dt>新增 Bad Case</dt><dd>{item.complete && item.newFailures === 0 ? "0" : <QuestionList items={item.broken.map(id => ({ id, tone: "broken" as QuestionTone, question: questionText?.(id), detail: "Baseline 答对 → 本 Candidate 答错" }))} />}</dd>
      <dt>Hard Gate</dt><dd>{item.gateFailures.length ? <span className="ui-evo-fail">{item.gateFailures.join("；")}</span> : item.complete ? <span className="ui-evo-pass">{item.gates ? `${item.gates.passed} / ${item.gates.total}` : '全部通过'}</span> : "评测中"}</dd>
    </dl>
    <footer className="ui-evo-card-foot ui-num">
      <span>答对 <b>{item.correct ?? "未知"}</b> / {item.total ?? "未知"}</span>
      <span>P50 {fastest ? <b>{fmt(item.p50)}</b> : fmt(item.p50)}　P99 {fmt(item.p99)}</span>
    </footer>
  </article>;
}

const fmt = (value: number | null) => value === null ? "未知" : `${value.toFixed(1)} 秒`;
