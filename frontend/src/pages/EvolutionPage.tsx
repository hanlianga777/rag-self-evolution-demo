import { useEffect, useRef, useState } from "react";
import { Play } from "lucide-react";
import { errorMessage, getJson, postJson } from "../api";
import { Badge, ConclusionCard, CustomSelect, ExpandableText, Section, ShortId, StageStepper, Status, TechnicalDetails } from "../components/Primitives";
import { SearchSpaceTable, parameterNames, formatValue } from "../components/PipelineFields";
import { Drawer } from "../components/Dialog";
import { useOperation } from "../operation";

const gateNames: Record<string, string> = { ablation_correctness: "Ablation Correctness（消融题正确性）", safe_rejection_rate: "Safe Rejection Rate（安全拒答率）" };
const rootCause = (item: any) => {
  const value = item.primary_root_cause || item.result?.primary_root_cause || item.category || "未记录";
  return /retrieval/i.test(value) ? "Retrieval" : /generation/i.test(value) ? "Generation" : /safety/i.test(value) ? "Safety" : value;
};
const humanizeField = (value: string) => value.split("_").map(word => word[0]?.toUpperCase() + word.slice(1)).join(" ");

export function EvolutionPage({ data }: { data: any }) {
  const operation = useOperation();
  const [stage, setStage] = useState<"bad" | "agent" | "candidates" | "sandbox">("bad");
  const [experiment, setExperiment] = useState<any>(data.optimization?.id ? data.optimization : null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchSpace, setSearchSpace] = useState<any>(null);
  const [selectedBadCase, setSelectedBadCase] = useState<any>(null);
  const refreshed = useRef(new Set<string>());
  const [winnerId, setWinnerId] = useState("");
  const evaluation = data.evaluation || {};
  const badCases = (data.badCases || []).filter((item: any) => item.run_id === evaluation.id);
  const candidates: any[] = experiment?.candidates || [];
  const abc = candidates.filter(candidate => candidate.reasoning?.candidate_label !== "D").sort((a, b) => (a.reasoning?.round || 1) - (b.reasoning?.round || 1) || String(a.reasoning?.candidate_label).localeCompare(String(b.reasoning?.candidate_label)));
  const d = candidates.find(candidate => candidate.reasoning?.candidate_label === "D");
  const orderedCandidates = d ? [...abc, d] : abc;
  const recommendation = experiment?.recommendation?.result || experiment?.recommendation || {};
  const confirmation = experiment?.result?.report_confirmation || recommendation.report_confirmation;
  const composite = experiment?.result?.composite || recommendation.composite;
  const budget = experiment?.evaluation_budget || { used: candidates.filter(item => ["evaluated", "failed", "running"].includes(item.status)).length, max: 12, reserved_for_d: 1 };
  const latestRound = experiment?.rounds?.at(-1);
  const canContinue = latestRound?.complete && recommendation.status === "No Qualified Candidate" && budget.used < budget.max - (budget.reserved_for_d ?? budget.reserved_for_d1 ?? 1);
  const qualified = candidates.filter(item => ["A", "B", "C"].includes(item.reasoning?.candidate_label) && item.status === "evaluated" && item.result?.qualification?.qualified);
  const selectedWinner = qualified.some(item => item.id === winnerId) ? winnerId : qualified[0]?.id || "";
  const activeOperation = (candidateId: string) => operation.operations.find(item => item.candidateId === candidateId && item.status === "running");
  const tuningStages: [string, boolean][] = [["诊断", !!evaluation.id], ["生成 A/B/C", abc.length > 0], ["Sandbox", abc.some(item => item.status === "evaluated")], ["Gate 2", !!confirmation], ["Composite D", !!composite], ["最终推荐", recommendation.status === "Recommended"]];
  const currentTuningStage = tuningStages.findIndex(([, complete]) => !complete);
  const refresh = async () => setExperiment(await getJson("/api/optimization"));

  useEffect(() => { if (searchOpen && !searchSpace) void getJson("/api/pipeline").then(setSearchSpace).catch(reason => setError(errorMessage(reason))); }, [searchOpen, searchSpace]);
  useEffect(() => {
    for (const item of operation.operations) if (item.candidateId && item.status !== "running" && !refreshed.current.has(item.id)) {
      refreshed.current.add(item.id); void refresh();
    }
  }, [operation.operations]);

  const action = async (title: string, work: () => Promise<unknown>) => {
    setBusy(true); setError("");
    try { await operation.run(title, work); await refresh(); }
    catch (reason) { setError(errorMessage(reason)); }
    finally { setBusy(false); }
  };
  const generate = async () => {
    setBusy(true); setError("");
    try { await operation.run("生成 A/B/C 候选", () => postJson("/api/experiments/run")); await refresh(); }
    catch (reason) { setError(errorMessage(reason)); }
    finally { setBusy(false); }
  };
  const run = async (candidate: any) => {
    if (candidate.status !== "generated" || activeOperation(candidate.id)) return;
    setBusy(true); setError("");
    try { await operation.startEvaluation(`Candidate ${candidate.reasoning?.candidate_label} · Sandbox`, () => postJson(`/api/candidates/${candidate.id}/run`), candidate.id); await refresh(); }
    catch (reason) { setError(errorMessage(reason)); }
    finally { setBusy(false); }
  };

  return <div className="page evolution-page">
    <div className="page-title"><div><h1>Tuning · 实验工作台</h1><p>依据 Baseline 诊断提出候选方案，经 Sandbox 与人工 Gate 确认推荐结果。</p></div><button className="primary" disabled={busy || evaluation.status !== "completed" || !badCases.length} onClick={() => void generate()}><Play size={15} />{busy ? "处理中…" : "生成 A / B / C"}</button></div>
    <StageStepper ariaLabel="Tuning Lifecycle" steps={tuningStages.map(([label, done], index) => ({ label, state: done ? "completed" : index === currentTuningStage ? "current" : "pending" }))} />
    <div className="tabs"><button aria-pressed={stage === "bad"} className={stage === "bad" ? "active" : ""} onClick={() => setStage("bad")}>诊断</button><button aria-pressed={stage === "agent"} className={stage === "agent" ? "active" : ""} onClick={() => setStage("agent")}>Optimization Agent</button><button aria-pressed={stage === "candidates"} className={stage === "candidates" ? "active" : ""} onClick={() => setStage("candidates")}>A / B / C / D</button><button aria-pressed={stage === "sandbox"} className={stage === "sandbox" ? "active" : ""} onClick={() => setStage("sandbox")}>Sandbox</button></div>
    {error && <p className="error-notice" role="alert">{error}</p>}
    {stage === "bad" && <><div className="metrics-grid four"><div className="metric"><span>Baseline</span><strong><ShortId value={evaluation.id} /></strong></div><div className="metric"><span>Overall</span><strong>{evaluation.result?.overall_score ?? "未采集"}</strong></div><div className="metric"><span>Hard Gate</span><strong>{evaluation.result?.gates ? `${evaluation.result.gates.passed_count} / ${evaluation.result.gates.total}` : "未运行"}</strong></div><div className="metric"><span>Bad Case</span><strong>{badCases.length}</strong></div></div><Section title="未通过 Gate"><div className="failed-gate-grid">{(evaluation.result?.gates?.gates || []).filter((gate: any) => gate.status === "FAIL").map((gate: any) => <div key={gate.metric}><strong>{gateNames[gate.metric] || humanizeField(gate.metric)}</strong><span>{gate.actual?.toFixed?.(2) ?? "未采集"} / {gate.operator} {gate.threshold?.toFixed?.(2) ?? "未采集"}</span><Status value="FAIL" /></div>)}</div></Section><Section title="根因摘要"><p>{Object.entries(badCases.reduce((counts: Record<string, number>, item: any) => ({ ...counts, [rootCause(item)]: (counts[rootCause(item)] || 0) + 1 }), {} as Record<string, number>)).map(([key, count]) => `${key} ${count}`).join(" · ") || "无真实 Bad Case"}</p></Section><Section title="Bad Case 诊断"><div className="table-scroll"><table><thead><tr><th>Case</th><th>Question</th><th>Root Cause</th><th>Affected Gate</th><th>Evidence</th></tr></thead><tbody>{badCases.map((item: any, index: number) => { const relatedGates = (evaluation.gate_details || []).filter((gate: any) => gate.contributing_cases?.some((row: any) => row.question_id === item.question_id)).map((gate: any) => gateNames[gate.metric] || humanizeField(gate.metric)); const tags: string[] = item.result?.failure_tags || []; return <tr key={item.id || item.question_id || index} onClick={() => setSelectedBadCase(item)} tabIndex={0} onKeyDown={event => event.key === "Enter" && setSelectedBadCase(item)}><td><ShortId value={item.question_id} /></td><td className="question-cell">{item.result?.question || "未记录"}</td><td><Badge tone="neutral">{rootCause(item)}</Badge></td><td>{relatedGates.join("、") || "未关联"}</td><td>{tags.slice(0, 2).map(tag => <Badge key={tag} tone="warning">{tag}</Badge>)}{tags.length > 2 && <details><summary>+{tags.length - 2}</summary>{tags.slice(2).join("、")}</details>}{!tags.length && (item.result?.programmatic_metrics?.retrieval_hit === false ? "Retrieval Miss" : "已记录")}</td></tr>; })}</tbody></table></div></Section></>}
    {stage === "agent" && <><Section title="实验概览" action={<button className="secondary" onClick={() => setSearchOpen(true)}>查看 Search Space</button>}><div className="report-grid"><div><dt>Experiment</dt><dd><ShortId value={experiment?.id} /></dd></div><div><dt>轮次</dt><dd>{latestRound ? `Round ${latestRound.round} · ${latestRound.evaluated}/${latestRound.total ?? 3}` : "未运行"}</dd></div><div><dt>评测预算</dt><dd>{budget.used} / {budget.max} · D 预留 {budget.reserved_for_d ?? budget.reserved_for_d1 ?? 1}</dd></div><div><dt>Bad Case</dt><dd>{badCases.length}</dd></div><div><dt>状态</dt><dd><Status value={experiment?.status || "not_run"} /></dd></div></div></Section><Section title="Agent 诊断"><p className="summary-text">{experiment?.result?.root_cause_cluster || "尚未生成诊断"}</p><div className="diagnosis-cards">{[["Retrieval", "检索问题"], ["Generation", "生成问题"], ["Safety", "安全问题"]].map(([name, label]) => { const rows = badCases.filter((item: any) => rootCause(item) === label || item.category === name); const retrievalSignals = rows.length || badCases.some((item: any) => item.result?.programmatic_metrics?.retrieval_hit === false); return <article key={name}><h3>{label}</h3><p>主要根因案例：{rows.length}</p>{name === "Retrieval" && retrievalSignals && !rows.length && <p>存在检索异常信号</p>}<p>Evidence：{rows[0]?.result?.failure_tags?.slice(0, 2).join("、") || "未记录"}</p><p>Relevant Config：{name === "Retrieval" ? `CandidateK ${evaluation.config?.candidate_k ?? "—"} · TopK ${evaluation.config?.top_k ?? "—"}` : `Prompt ${evaluation.config?.prompt_strategy || "—"}`}</p></article>; })}</div><details><summary>查看诊断证据</summary><div className="evidence-list">{(experiment?.result?.observed_evidence || []).map((value: string, index: number) => <p key={index}>{value}</p>)}</div></details></Section><Section title="优化假设"><div className="table-scroll"><table><thead><tr><th>Candidate</th><th>假设</th><th>目标案例</th><th>原因</th><th>调整参数</th></tr></thead><tbody>{abc.map(candidate => <tr key={candidate.id}><td>Candidate {candidate.reasoning?.candidate_label}</td><td><ExpandableText label="假设">{candidate.reasoning?.hypothesis || "未记录"}</ExpandableText></td><td><details><summary>{candidate.reasoning?.observed_evidence?.length || 0} 个 Case · 查看</summary>{(candidate.reasoning?.observed_evidence || []).map((id: string) => <p key={id}><ShortId value={id} /></p>)}</details></td><td><ExpandableText label="原因">{candidate.reasoning?.proposal || "未记录"}</ExpandableText></td><td>{Object.keys(candidate.reasoning?.changed_parameters || {}).map(key => parameterNames[key] || key).join("、") || "无"}</td></tr>)}</tbody></table></div></Section></>}
    {stage === "candidates" && <><Section title="Candidate A / B / C" action={canContinue ? <button className="secondary" disabled={busy} onClick={() => void action("生成下一轮 A/B/C", () => postJson(`/api/experiments/${experiment.id}/continue`))}>继续优化下一轮</button> : undefined}>{[...new Set(abc.map(item => item.reasoning?.round || 1))].map(round => <div key={round}><h3 className="round-heading">Round {round}</h3><div className="candidate-cards">{abc.filter(item => (item.reasoning?.round || 1) === round).map(candidate => <CandidateCard key={candidate.id} candidate={candidate} baseline={evaluation.config || {}} running={activeOperation(candidate.id)} busy={busy} onRun={() => void run(candidate)} />)}</div></div>)}{!experiment && <p className="muted">需先完成真实 Baseline Evaluation 并识别 Bad Case。</p>}</Section>{confirmation && <Section title="Composite D">{composite?.status === "no_effective_composite" ? <ConclusionCard title="保留 Gate 2 Winner" tone="warning">没有有效的 Composite D，继续采用已确认的 Candidate。</ConclusionCard> : d ? <div className="composite-decision"><section><h3>组合决策</h3><dl><div><dt>基础 Winner</dt><dd>{candidateName(candidates.find((item: any) => item.id === (d.reasoning?.winner_id || confirmation.winner_id)))}</dd></div><div><dt>合并来源</dt><dd>{(d.reasoning?.sources || []).map((source: any) => candidateName(candidates.find((item: any) => item.id === source.candidate_id))).join("、") || "未记录"}</dd></div><div><dt>冲突检查</dt><dd>{d.reasoning?.conflicts?.length ? `${d.reasoning.conflicts.length} 项冲突` : "无冲突"}</dd></div></dl><h4>参数差异</h4><ConfigDiff base={evaluation.config || {}} candidate={d} /><details><summary>查看合并来源与冲突明细</summary>{(d.reasoning?.sources || []).map((source: any) => <p key={source.candidate_id}>{candidateName(candidates.find((item: any) => item.id === source.candidate_id))} · {Object.entries(source.parameter_diff || {}).map(([key, value]) => `${parameterNames[key] || key} → ${formatValue(value)}`).join("；")} · {source.why_merge || "未保存合并理由"}</p>)}</details></section><section><h3>评测结果</h3><div className="d-result-grid"><div><span>Hard Gate</span><strong>{d.result?.gates ? `${d.result.gates.passed_count} / ${d.result.gates.total}` : "未运行"}</strong></div><div><span>修复 Bad Case</span><strong>{d.result?.target_bad_cases_fixed ?? "未运行"}</strong></div><div><span>Regression</span><strong>{d.result?.regression?.status || "未运行"}</strong></div><div><span>Qualification</span><strong>{d.result?.qualification?.qualified ? "Qualified" : d.status === "evaluated" ? "Not Qualified" : "未运行"}</strong></div></div><ConclusionCard title={d.result?.qualification?.qualified ? "Composite D 满足资格" : `保留 ${candidateName(candidates.find((item: any) => item.id === confirmation.winner_id))}`} tone={d.result?.qualification?.qualified ? "good" : "warning"}>{d.result?.qualification?.qualified ? "Composite D 已达到资格要求。" : "Composite D 未通过全部 Hard Gate，因此不能替代 Gate 2 Winner。"}</ConclusionCard>{d.status === "generated" && <CandidateAction candidate={d} running={activeOperation(d.id)} busy={busy} onRun={() => void run(d)} />}</section></div> : <p className="muted">等待 Composite D 决策。</p>}</Section>}</>}
    {stage === "sandbox" && <Section title="Sandbox 对比"><ConclusionCard title={recommendation.recommended_candidate ? `推荐 ${candidateName(candidates.find((item: any) => item.id === recommendation.recommended_candidate))}` : "等待资格与 Gate 2 结论"} status={recommendation.status && <Status value={recommendation.status} />} tone={recommendation.recommended_candidate ? "good" : "neutral"}>{recommendation.recommended_candidate ? "推荐依据来自已保存的资格与推荐审计。Overall 仅供比较，不能覆盖失败 Gate。" : "Overall 仅供比较，不能覆盖失败 Gate。"}</ConclusionCard><div className="table-scroll"><table><thead><tr><th>指标</th><th>Baseline</th>{orderedCandidates.map(candidate => <th key={candidate.id}>{candidate.reasoning?.candidate_label || candidate.id.slice(-1)}</th>)}</tr></thead><tbody>{[["Overall", "overall_score"], ["Hard Gate", "gates"], ["Bad Case", "bad_case_count"], ["Fixed Bad Case", "target_bad_cases_fixed"], ["Regression", "regression"], ["Positive", "positive_correctness"], ["Ablation", "ablation_correctness"], ["Safety", "safe_rejection_rate"], ["TTFT", "ttft_seconds"], ["Token Cost", "token_cost"], ["Recall@K", "recall_at_k"], ["Precision@K", "precision_at_k"], ["MRR", "mrr"]].map(([label, key]) => <tr key={key}><td>{label}</td><td>{metricText(evaluation.result, key)}</td>{orderedCandidates.map(candidate => <td key={candidate.id}>{metricText(candidate.result, key)}</td>)}</tr>)}</tbody></table></div>
      <div className="run-list">{orderedCandidates.map(candidate => <div key={candidate.id}><strong>{candidateName(candidate)}</strong><Status value={candidate.result?.qualification?.qualified ? "Qualified" : candidate.status === "evaluated" ? "Not Qualified" : candidate.status} /></div>)}</div>
      {recommendation.status && <Badge tone="neutral">{recommendation.status}</Badge>}
      {!confirmation && qualified.length > 0 && candidates.every(item => !["running", "queued"].includes(item.status)) && <div className="review-batch"><label>Gate 2 · 确认 A/B/C 报告并选择合格赢家<CustomSelect ariaLabel="选择合格赢家" value={selectedWinner} onChange={setWinnerId} options={qualified.map(candidate => ({ value: candidate.id, label: candidateName(candidate), description: "Qualified" }))} /></label><button className="primary" disabled={busy} onClick={() => void action("确认 A/B/C 报告", () => postJson(`/api/experiments/${experiment.id}/recommendation`, { candidate_id: selectedWinner, actor: "human" }))}>确认报告与赢家</button></div>}
      {confirmation && !composite && <div className="review-batch"><span>Gate 2 已确认赢家 {confirmation.winner_id}</span><button className="primary" disabled={busy} onClick={() => void action("构建 Composite D", () => postJson(`/api/experiments/${experiment.id}/composite`))}>构建 Composite D</button></div>}
      {composite?.status === "no_effective_composite" && <p className="muted">无有效组合，保留 Gate 2 赢家 {confirmation?.winner_id}。</p>}
      {composite && <details><summary>Composite D 决策详情</summary><p>Base Winner：{composite.winner_id || "未记录"}</p><p>Merged Changes：{(composite.sources || []).map((item: any) => `${item.candidate_id}: ${JSON.stringify(item.parameters || item.changes || item.diff || {})}`).join("；") || "无"}</p><p>Conflicts：{(composite.conflicts || []).map((item: any) => `${item.candidate_id} ${item.parameters?.join("、")}`).join("；") || "无"}</p></details>}
      {composite?.status === "generated" && <p className="muted">Composite D 已生成；请到候选方案运行完整 Sandbox。若 D 失败或打平，保留 Gate 2 赢家。</p>}
      {recommendation.status === "Recommended" && <ConclusionCard title={`推荐 ${candidateName(candidates.find((item: any) => item.id === recommendation.recommended_candidate))}`} tone="good">Gate 3 可在 Release 页面由人确认发布。</ConclusionCard>}
    </Section>}
    <Drawer open={searchOpen} onOpenChange={setSearchOpen} title="Search Space · Frozen by SPEC V1.3" className="search-space-drawer"><div className="drawer-body"><p>Optimization Agent 只能修改以下字段；参数类型、允许值来自后端 Validator 的同一策略。</p>{searchSpace?.search_space ? <SearchSpaceTable contract={searchSpace.search_space} baseline={searchSpace.baseline_config || evaluation.config || {}} /> : <p>{error || "正在读取 Search Space…"}</p>}</div></Drawer>
    <Drawer open={!!selectedBadCase} onOpenChange={open => !open && setSelectedBadCase(null)} title="Bad Case Diagnosis"><div className="drawer-body">{selectedBadCase && <><h3>Question</h3><p>{selectedBadCase.result?.question}</p><h3>Root Cause</h3><p>{selectedBadCase.category} · {selectedBadCase.result?.failure_tags?.join("、") || "未记录"}</p><h3>Model Answer</h3><p>{selectedBadCase.result?.model_answer || "未记录"}</p><TechnicalDetails label="Raw Trace">{JSON.stringify(selectedBadCase.result, null, 2)}</TechnicalDetails></>}</div></Drawer>
  </div>;
}

function CandidateCard({ candidate, baseline, running, busy, onRun }: { candidate: any; baseline: Record<string, any>; running?: { current?: number; total?: number; stage?: string }; busy: boolean; onRun: () => void }) {
  const reasoning = candidate.reasoning || {};
  return <article className="candidate-card"><div className="candidate-card-header"><div><small>Round {reasoning.round || 1}</small><h3>Candidate {reasoning.candidate_label || "—"}</h3></div><Status value={running ? "running" : candidate.result?.qualification?.qualified ? "Qualified" : candidate.status === "evaluated" ? "Not Qualified" : candidate.status || "not_run"} /></div><div className="candidate-card-body"><div className="candidate-card-field"><span className="field-label">优化假设</span><ExpandableText label="假设">{reasoning.hypothesis}</ExpandableText></div><div className="candidate-card-field"><span className="field-label">目标 Bad Case</span><details><summary>{reasoning.observed_evidence?.length || 0} 个 Case · 查看详情</summary>{(reasoning.observed_evidence || []).map((id: string) => <p key={id}><ShortId value={id} /></p>)}</details></div><div className="candidate-card-field"><span className="field-label">调整原因</span><ExpandableText label="原因">{reasoning.proposal || reasoning.why}</ExpandableText></div><div className="candidate-card-field"><span className="field-label">参数差异</span><ConfigDiff base={baseline} candidate={candidate} /></div><div className="candidate-result"><span>Hard Gate <strong>{candidate.result?.gates ? `${candidate.result.gates.passed_count}/${candidate.result.gates.total}` : "未运行"}</strong></span><span>修复案例 <strong>{candidate.result?.target_bad_cases_fixed ?? "未运行"}</strong></span><span>Regression <strong>{candidate.result?.regression?.status || "未运行"}</strong></span></div><div className="candidate-card-field"><span className="field-label">风险</span><ExpandableText label="风险">{reasoning.risk}</ExpandableText></div>{running && <div className="inline-progress" role="status"><strong>Sandbox 运行中 · {running.stage || "等待评测"}</strong>{running.current != null && running.total != null && running.total > 1 && <><p>{running.current} / {running.total} · {Math.round(running.current / running.total * 100)}%</p><progress value={running.current} max={running.total} /></>}</div>}</div><CandidateAction candidate={candidate} running={running} busy={busy} onRun={onRun} /></article>;
}

function ConfigDiff({ base, candidate }: { base: Record<string, any>; candidate: any }) {
  const changes = Object.entries(candidate.reasoning?.changed_parameters || {});
  const rows = (items: [string, any][]) => items.map(([key, value]) => <tr key={key}><td title={parameterNames[key] || key}>{parameterNames[key] || key}</td><td title={formatValue(base[key])}>{formatValue(base[key])}</td><td title={formatValue(value)}>{formatValue(value)}</td></tr>);
  if (!changes.length) return <p>无参数变化记录。</p>;
  return <div className="candidate-config-diff"><table><thead><tr><th>Parameter</th><th>Baseline</th><th>Candidate</th></tr></thead><tbody>{rows(changes.slice(0, 3))}</tbody></table>{changes.length > 3 && <details><summary>查看全部 {changes.length} 项参数</summary><table><tbody>{rows(changes.slice(3))}</tbody></table></details>}</div>;
}

function CandidateAction({ candidate, running, busy, onRun }: { candidate: any; running?: { current?: number; total?: number }; busy: boolean; onRun: () => void }) {
  return <div className="candidate-card-action"><button className="secondary" disabled={busy || !!running || candidate.status !== "generated"} onClick={onRun}>{running ? "Sandbox 运行中" : candidate.status === "evaluated" ? "已评测" : "运行 Sandbox"}</button>{running && running.current != null && running.total != null && <span>{running.current} / {running.total}</span>}</div>;
}

const candidateName = (candidate?: any) => candidate ? `Candidate ${candidate.reasoning?.candidate_label || "—"}` : "Candidate";

function metricText(result: any, key: string) {
  if (!result) return "未运行";
  if (key === "gates") return result.gates ? `${result.gates.passed_count} / ${result.gates.total}` : "未运行";
  if (key === "regression") return result.regression?.status || "N/A";
  const value = result.comparison_metrics?.[key] ?? result.metrics?.[key] ?? result[key];
  return typeof value === "number" ? value.toFixed(2) : value ?? "未采集";
}
