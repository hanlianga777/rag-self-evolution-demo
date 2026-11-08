import { Icon, IconLabel } from "../icons";
import { QuestionList, StatusBadge, type QuestionTone } from "../Primitives";
import type { CandidateView } from "./model";

/**
 * Agent 工作台 →「最终推荐」。
 * 重点只比较"同为合格"的两个方案：Winner（Round 3 · Candidate C）与 Candidate D。
 * - C 不是失败方案：它更快；D 多修好 Q04，P99 更高但仍在 Hard Gate 内。按"质量优先、Regression 与 Hard Gate 满足"推荐 D。
 * - 其余 Candidate 的落选理由放在下方一张表里（与进化路线同一套数据），不再是九段长文。
 * reason 用现有 recommendationReason() 的输出，不另写结论。
 */
export function FinalRecommendation({ chosen, runnerUp, baselineCorrect, reason, others, questionText, onRelease, releaseLabel = "去发布", onOpen }: {
  chosen: CandidateView; runnerUp: CandidateView | null; baselineCorrect: number | null; reason: string; others: CandidateView[];
  questionText?: (id: string) => string | undefined; onRelease?: () => void; releaseLabel?: string; onOpen?: (id: string) => void;
}) {
  const rows: { label: string; a: string; b: string; better: "a" | "b" | null }[] = runnerUp ? [
    { label: "答对", a: cnt(runnerUp), b: cnt(chosen), better: cmp(runnerUp.correct, chosen.correct, "higher") },
    { label: "新增 Bad Case", a: String(runnerUp.broken.length), b: String(chosen.broken.length), better: cmp(runnerUp.broken.length, chosen.broken.length, "lower") },
    { label: "Hard Gate", a: gateCount(runnerUp), b: gateCount(chosen), better: null },
    { label: "P50", a: sec(runnerUp.p50), b: sec(chosen.p50), better: cmp(runnerUp.p50, chosen.p50, "lower") },
    { label: "P99", a: sec(runnerUp.p99), b: sec(chosen.p99), better: cmp(runnerUp.p99, chosen.p99, "lower") },
  ] : [];
  const extra = runnerUp ? chosen.fixed.filter(id => !runnerUp.fixed.includes(id)) : [];
  return <section className="ui-fin" aria-label="最终推荐">
    <div className="ui-fin-top">
      <div>
        <span className="ui-rel-k"><IconLabel name="recommend">最终推荐</IconLabel></span>
        <h2>{chosen.name} <StatusBadge kind="recommended" /></h2>
        <p className="ui-fin-reason">{reason}</p>
      </div>
      {onRelease && <button type="button" className="primary" onClick={onRelease}><Icon name="release" size={15} />{releaseLabel}</button>}
    </div>

    {runnerUp && <div className="ui-fin-compare">
      <table>
        <thead><tr><th>合格方案对比</th><th>{runnerUp.name}<small>Winner · 合格</small></th><th className="pick">{chosen.name}<small>推荐</small></th></tr></thead>
        <tbody>
          {baselineCorrect != null && <tr className="muted"><td>Baseline 答对</td><td colSpan={2} className="ui-num">{baselineCorrect} / {chosen.total ?? 50}</td></tr>}
          {rows.map(row => <tr key={row.label}><td>{row.label}</td><td className={`ui-num${row.better === "a" ? " better" : ""}`}>{row.a}</td><td className={`ui-num pick${row.better === "b" ? " better" : ""}`}>{row.b}</td></tr>)}
          <tr><td>比 Winner 多修好</td><td>—</td><td className="pick"><QuestionList items={extra.map(id => ({ id, tone: "fixed" as QuestionTone, question: questionText?.(id) }))} /></td></tr>
        </tbody>
      </table>
    </div>}

    {others.length > 0 && <div className="ui-fin-others">
      <h3><IconLabel name="rejected">其他 Candidate 为什么没选</IconLabel></h3>
      <table>
        <thead><tr><th>Candidate</th><th>修好</th><th>新增 Bad Case</th><th>未通过的 Hard Gate</th></tr></thead>
        <tbody>{others.map(item => <tr key={item.id} onClick={onOpen ? () => onOpen(item.id) : undefined} className={onOpen ? "clickable" : ""}>
          <td><strong>{item.name}</strong></td>
          <td><QuestionList items={item.fixed.map(id => ({ id, tone: "fixed" as QuestionTone, question: questionText?.(id) }))} /></td>
          <td><QuestionList items={item.broken.map(id => ({ id, tone: "broken" as QuestionTone, question: questionText?.(id) }))} /></td>
          <td className={item.gateFailures.length ? "ui-fin-gates" : "ui-fin-ok"}>{item.gateFailures.length ? item.gateFailures.join("；") : "全部通过"}</td>
        </tr>)}</tbody>
      </table>
    </div>}
  </section>;
}

const cnt = (item: CandidateView) => item.correct == null ? "未知" : `${item.correct} / ${item.total ?? 50}`;
const sec = (value: number | null) => value == null ? "未知" : `${value.toFixed(1)} 秒`;
const gateCount = (item: CandidateView) => item.gates ? `${item.gates.passed} / ${item.gates.total}` : item.gateFailures.length ? "未全过" : "全部通过";
function cmp(a: number | null, b: number | null, better: "higher" | "lower"): "a" | "b" | null {
  if (a == null || b == null || a === b) return null;
  return (better === "higher" ? a > b : a < b) ? "a" : "b";
}
