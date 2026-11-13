import { DataTable } from "../../components/DataTable";
import { Icon, IconLabel } from "../icons";
import { QuestionList, type QuestionTone } from "../Primitives";
import type { CandidateView } from "./model";

/**
 * Agent 工作台 →「最终推荐」。
 * 重点只比较"同为合格"的两个方案：Winner（Round 3 · Candidate C）与 Candidate D。
 * - C 不是失败方案：它更快；D 多修好 Q04，P99 更高但仍在 Hard Gate 内。按"质量优先、Regression 与 Hard Gate 满足"推荐 D。
 * - 其余 Candidate 的落选理由放在下方一张表里（与进化路线同一套数据），不再是九段长文。
 * reason 用现有 recommendationReason() 的输出，不另写结论。
 */
export function FinalRecommendation({ chosen, runnerUp, baselineCorrect, reason, others, questionText, onRelease, releaseLabel = "去发布", onOpen, totalCandidates, qualifiedCount }: {
  totalCandidates?: number; qualifiedCount?: number;
  chosen: CandidateView; runnerUp: CandidateView | null; baselineCorrect: number | null; reason: string; others: CandidateView[];
  questionText?: (id: string) => string | undefined; onRelease?: () => void; releaseLabel?: string; onOpen?: (id: string) => void;
}) {
  const rows: { label: string; a: string; b: string; better: "a" | "b" | null }[] = runnerUp ? [
    { label: "答对", a: cnt(runnerUp), b: cnt(chosen), better: cmp(runnerUp.correct, chosen.correct, "higher") },
    { label: "新增 Bad Case", a: String(runnerUp.broken.length), b: String(chosen.broken.length), better: cmp(runnerUp.broken.length, chosen.broken.length, "lower") },
    { label: "P50", a: sec(runnerUp.p50), b: sec(chosen.p50), better: cmp(runnerUp.p50, chosen.p50, "lower") },
    { label: "P99", a: sec(runnerUp.p99), b: sec(chosen.p99), better: cmp(runnerUp.p99, chosen.p99, "lower") },
  ] : [];
  const extra = runnerUp ? chosen.fixed.filter(id => !runnerUp.fixed.includes(id)) : [];
  return <section className="ui-fin" aria-label="最终推荐">
    <div className="ui-fin-top">
      <div>
        <span className="ui-rel-k"><IconLabel name="recommend">最终推荐</IconLabel></span>
        <h2>{totalCandidates != null ? `${totalCandidates} 个 Candidate 中只有 ${qualifiedCount ?? 0} 个通过回归检查，最终推荐 ${chosen.name}` : chosen.name}</h2>
        <p className="ui-fin-reason">{reason}</p>
      </div>
      {onRelease && <button type="button" className="primary" onClick={onRelease}><Icon name="release" size={15} />{releaseLabel}</button>}
    </div>

    {runnerUp && <div className="ui-fin-compare">
      <table>
        <thead><tr><th>合格 Candidate 对比</th><th>{runnerUp.name}<small>Winner · 合格</small></th><th className="pick">{chosen.name}<small>推荐</small></th></tr></thead>
        <tbody>
          {rows.map(row => <tr key={row.label}><td>{row.label}</td><td className={`ui-num${row.better === "a" ? " better" : ""}`}>{row.a}{row.label === "答对" && baselineCorrect != null && runnerUp.correct != null && <small className="ui-body-muted">较 Baseline {delta(runnerUp.correct - baselineCorrect)}</small>}</td><td className={`ui-num pick${row.better === "b" ? " better" : ""}`}>{row.b}{row.label === "答对" && baselineCorrect != null && chosen.correct != null && <small className="ui-body-muted">较 Baseline {delta(chosen.correct - baselineCorrect)}</small>}</td></tr>)}
          <tr><td>比 Winner 多修好</td><td>—</td><td className="pick"><QuestionList items={extra.map(id => ({ id, tone: "fixed" as QuestionTone, question: questionText?.(id) }))} /></td></tr>
        </tbody>
      </table>
      {onOpen && <button type="button" className="secondary" onClick={()=>onOpen(runnerUp.id)}>查看 Winner 详情</button>}
    </div>}

    {others.length > 0 && <div className="ui-fin-others">
      <h3><IconLabel name="rejected">落选原因（{others.length}）</IconLabel></h3>
      <div className="table-scroll"><DataTable><thead><tr><th>Candidate</th><th>落选原因</th></tr></thead><tbody>{others.map(item=><tr key={item.id}><td><button type="button" className="text-button" onClick={()=>onOpen?.(item.id)} disabled={!onOpen}><strong>{item.name}</strong><Icon name="go" size={14}/></button></td><td>{rejectionReason(item)}</td></tr>)}</tbody></DataTable></div>
    </div>}
  </section>;
}

const delta = (value: number) => value > 0 ? `+${value}` : String(value);
const cnt = (item: CandidateView) => item.correct == null ? "未知" : `${item.correct} / ${item.total ?? 50}`;
const sec = (value: number | null) => value == null ? "未知" : `${value.toFixed(1)} 秒`;
function cmp(a: number | null, b: number | null, better: "higher" | "lower"): "a" | "b" | null {
  if (a == null || b == null || a === b) return null;
  return (better === "higher" ? a > b : a < b) ? "a" : "b";
}

function rejectionReason(item: CandidateView): string {
  if (!item.complete) return '评测尚未完成，不能据此确定资格。';
  if (item.qualified===true) return '本次保存的最终推荐未选择该方案，具体取舍见完整报告。';
  const review=item.regression;
  const failures=review?.limits ? (['critical','ordinary'] as const).filter(key=>review[`new_${key}_failures`]>review.limits![key]) : [];
  const regression=failures.length===1 ? `新增 ${item.broken.length} 个 Bad Case，超过${failures[0]==='critical' ? '严重' : '普通'}新增最多 ${review!.limits![failures[0]]} 个的上限。` : failures.length ? `新增 ${item.broken.length} 个 Bad Case；${failures.map(key=>`${key==='critical' ? '严重' : '普通'}新增 ${review![`new_${key}_failures`]} 个，超过最多 ${review!.limits![key]} 个的上限`).join('；')}。` : '';
  const gates=item.gateFailures.length ? `${item.gateFailures.join('；')}，未通过 Hard Gate。` : '';
  return [regression,gates].filter(Boolean).join(' ') || (item.broken.length ? `新增 ${item.broken.length} 个 Bad Case，保存记录未提供超限明细，具体落选原因见完整报告。` : '保存记录未提供具体落选原因，见完整报告。');
}
