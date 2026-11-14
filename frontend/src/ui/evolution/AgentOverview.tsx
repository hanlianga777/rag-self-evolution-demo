import { DataTable } from "../../components/DataTable";
import { caseData, caseId, savedDirections } from "../../components/EvaluationDiagnosis";
import { completeResult, schemeName, storyText } from "../../components/EvolutionStory";
import { AgentStats } from "../overview/OverviewSummary";
import { QuestionBadge, StatusBadge } from "../Primitives";
import { ClampText } from "../ClampText";
import type { EvolutionModel } from "./model";
import { shortId } from "./model";

const RULES = [
  ["三个方向互斥", "每一轮的三个 Candidate 必须改不同的参数，其中一个固定走“降档 + 检索补偿”的效率方向，这样结果变好或变坏都能说清是哪一处改动造成的。"],
  ["修好不能抵消弄坏", "只要新增了严重 Bad Case，或者普通 Bad Case 超过一个，修好再多题也不算合格，这就是“回归检查”守住的底线。"],
  ["事先预测，事后对账", "Candidate D 在评测之前就写下预计修好哪些题、要盯住哪些题，跑完以后逐条核对，没修好的也要说清原因。"],
];

export function AgentOverview({ experiment, model, evaluation, chosenId, released, status, cases, onCase }: {
  experiment: any; model: EvolutionModel; evaluation: any; chosenId?: string; released: boolean; status: string; cases: any[]; onCase: (row: any) => void;
}) {
  const candidates: any[] = experiment?.candidates || [];
  const chosen = [...model.rounds.flatMap(round => round.candidates), ...(model.d ? [model.d] : [])].find(item => item.id === chosenId);
  const selected = candidates.find(item => item.id === chosenId);
  const d = candidates.find(item => item.reasoning?.candidate_label === "D");
  const finalResult = completeResult(d);
  const fixed: string[] | undefined = Array.isArray(finalResult?.all_fixed_question_ids) ? finalResult.all_fixed_question_ids.map(shortId) : undefined;
  const remaining: string[] | undefined = Array.isArray(finalResult?.continued_failure_question_ids) ? finalResult.continued_failure_question_ids.map(shortId) : undefined;
  const views = model.rounds.flatMap(round => round.candidates);
  const baselineCorrect = typeof evaluation.result?.total === "number" && typeof evaluation.result?.bad_case_count === "number" ? evaluation.result.total - evaluation.result.bad_case_count : "—";
  const sourceFor = (key: string, to: string) => {
    if (!selected) return "—";
    const winner = views.find(item => item.id === selected.reasoning?.winner_id);
    if (winner?.params.some(param => param.key === key && param.to === to)) return `${winner.name} 引入，D 沿用`;
    const change = (selected.reasoning?.changes || selected.reasoning?.sources || []).find((row: any) => row.parameter === key);
    const sources = (change?.source_candidates || []).map((id: string) => views.find(item => item.id === id)).filter((item: any) => item?.params.some((param: any) => param.key === key && param.to === to));
    return sources.length ? `${sources.map((item: any) => item.name).join("、")} 验证过，D 采纳` : "—";
  };
  const assigned = (row: any) => {
    const id = shortId(caseId(row) || "");
    const matches = candidates.filter(candidate => {
      const r = candidate.reasoning || {};
      return [r.observed_evidence, r.target_bad_cases, r.root_cause_evidence].some(ids => Array.isArray(ids) && ids.some((target: string) => target === row.id || shortId(target) === id));
    }).sort((a, b) => (a.reasoning?.candidate_label === "D" ? 100 : a.reasoning?.round || 1) - (b.reasoning?.candidate_label === "D" ? 100 : b.reasoning?.round || 1) || String(a.reasoning?.candidate_label).localeCompare(String(b.reasoning?.candidate_label)));
    if (matches.length) return matches.map(item => schemeName(item)).join("、");
    const view = caseData(row).diagnostic_view;
    return view?.tuning_directions?.length || view?.optimization_directions?.length || view?.experiment_plan?.directions?.length || view?.experiment_plan?.next_action ? savedDirections(row) : "—";
  };
  return <div className="agent-overview">
    <section className={`agent-overview-result ui-card${released ? " released" : ""}`} aria-label="Agent 结果">
      <div><h2>{chosen ? `${released ? "推荐并已发布" : "推荐"} ${chosen.name}` : "尚无最终推荐"}</h2>
        <p>答对 {baselineCorrect} → {chosen?.complete ? chosen.correct ?? "—" : "—"}<span>新增 Bad Case {chosen?.complete ? chosen.newFailures ?? "—" : "—"}</span><span>Hard Gate {chosen?.complete && chosen.gates ? `${chosen.gates.passed}/${chosen.gates.total}` : "—"}</span></p>
      </div>
      <AgentStats rounds={model.rounds.length} candidates={candidates.length} budget={model.budget} status={{ kind: released ? "released" : chosen ? "recommended" : "waiting", text: status }}/>
    </section>
    {!chosen && experiment?.result?.processing_progress && <p className="ui-body-muted">{experiment.result.processing_progress.verified_configuration_id ? "已有经完整评测验证的 Candidate" : "尚无经完整评测验证的 Candidate"} · 修复 {experiment.result.processing_progress.fixed_question_ids?.length ?? "未知"} 题 · 待处理 {experiment.result.processing_progress.remaining_question_ids?.length ?? "未知"} 题</p>}
    {!chosen && experiment?.coverage_plan?.status === "incomplete" && <p className="ui-body-muted">规划未完成：{experiment.coverage_plan.covered_count}/{experiment.coverage_plan.total} 道已有 Candidate 覆盖。</p>}
    <section className="agent-overview-params" aria-label="最终改动的参数">{chosen?.params.map(param => <article className="ui-card" key={param.key}><strong>{param.label}　{param.from ?? "—"} → {param.to}</strong><small>{sourceFor(param.key, param.to)}</small></article>)}{!chosen?.params.length && <p className="ui-body-muted">最终参数变化：—</p>}</section>
    <section className="agent-overview-rules" aria-label="Agent 的三条规则">{RULES.map(([title, text]) => <article className="ui-card" key={title}><h3>{title}</h3><p>{text}</p></article>)}</section>
    <section className="agent-case-destinations ui-card" aria-label="Bad Case 去向表"><h3>Bad Case 去向</h3><DataTable><thead><tr>{["题号", "所在层", "Agent 指派的方向或 Candidate", "第一次被修好的 Candidate", "最终状态"].map(text => <th key={text}>{text}</th>)}</tr></thead><tbody>{[...cases].sort((a,b)=>shortId(caseId(a) || "").localeCompare(shortId(caseId(b) || ""),undefined,{numeric:true})).map(row => {
      const id = shortId(caseId(row) || ""), first = [...views, ...(model.d ? [model.d] : [])].find(item => item.complete && item.fixed.includes(id));
      const finalStatus = fixed?.includes(id) ? "D 已修好" : remaining?.includes(id) || fixed && finalResult?.evaluation_complete !== false ? "仍未修好" : "未知";
      return <tr key={caseId(row)} tabIndex={0} role="button" aria-label={`查看 ${id} 问题证据`} onClick={() => onCase(row)} onKeyDown={event => { if (event.target === event.currentTarget && (event.key === "Enter" || event.key === " ")) { event.preventDefault(); onCase(row); } }}>
        <td><QuestionBadge id={id} question={caseData(row).question}/></td><td>{caseData(row).diagnostic_view?.diagnosis_category?.replace(/问题$/, "") || "分类未知"}</td><td><ClampText text={storyText(assigned(row))} lines={1}/></td><td>{first?.name || "—"}</td><td><StatusBadge kind={finalStatus === "D 已修好" ? "qualified" : "evaluated"} label={finalStatus}/></td>
      </tr>;
    })}{!cases.length && <tr><td colSpan={5}>暂无保存的 Bad Case</td></tr>}</tbody></DataTable></section>
  </div>;
}
