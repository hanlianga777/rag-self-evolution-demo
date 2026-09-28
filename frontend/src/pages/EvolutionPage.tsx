import { useEffect, useRef, useState } from "react";
import { Play } from "lucide-react";
import { errorMessage, getJson, postJson } from "../api";
import { Badge, Section, ShortId, Status, TechnicalDetails } from "../components/Primitives";
import { SearchSpaceTable, parameterNames, formatValue } from "../components/PipelineFields";
import { Drawer } from "../components/Dialog";
import { useOperation } from "../operation";

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
    <div className="page-title"><div><h1>Tuning · 实验工作台</h1><p>Baseline Diagnosis → Optimization Agent → A/B/C Sandbox → Human Gate → Recommendation。</p></div><button className="primary" disabled={busy || evaluation.status !== "completed" || !badCases.length} onClick={() => void generate()}><Play size={15} />{busy ? "处理中…" : "生成 A / B / C"}</button></div>
    <div className="tuning-stepper" aria-label="Tuning Lifecycle">{[["Diagnosis", !!evaluation.id], ["Generate A/B/C", abc.length > 0], ["Sandbox", abc.some(item => item.status === "evaluated")], ["Gate 2", !!confirmation], ["Composite D", !!composite], ["Final Recommendation", recommendation.status === "Recommended"]].map(([name, done], index) => <div key={String(name)} className={done ? "done" : "pending"}><small>{String(index + 1).padStart(2, "0")}</small><span>{name}</span>{done ? " ✓" : ""}</div>)}</div>
    <div className="tabs"><button aria-pressed={stage === "bad"} className={stage === "bad" ? "active" : ""} onClick={() => setStage("bad")}>诊断</button><button aria-pressed={stage === "agent"} className={stage === "agent" ? "active" : ""} onClick={() => setStage("agent")}>Optimization Agent</button><button aria-pressed={stage === "candidates"} className={stage === "candidates" ? "active" : ""} onClick={() => setStage("candidates")}>A / B / C / D</button><button aria-pressed={stage === "sandbox"} className={stage === "sandbox" ? "active" : ""} onClick={() => setStage("sandbox")}>Sandbox</button></div>
    {error && <p className="error-notice" role="alert">{error}</p>}
    {stage === "bad" && <><div className="metrics-grid four"><div className="metric"><span>Baseline</span><strong><ShortId value={evaluation.id} /></strong></div><div className="metric"><span>Overall</span><strong>{evaluation.result?.overall_score ?? "未采集"}</strong></div><div className="metric"><span>Hard Gate</span><strong>{evaluation.result?.gates ? `${evaluation.result.gates.passed_count} / ${evaluation.result.gates.total}` : "未运行"}</strong></div><div className="metric"><span>Bad Cases</span><strong>{badCases.length}</strong></div></div><Section title="Failed Gates"><div className="failed-gate-grid">{(evaluation.result?.gates?.gates || []).filter((gate: any) => gate.status === "FAIL").map((gate: any) => <div key={gate.metric}><strong>{gate.metric}</strong><span>{gate.actual?.toFixed?.(2) ?? "未采集"} / {gate.operator} {gate.threshold?.toFixed?.(2) ?? "未采集"}</span><Status value="FAIL" /></div>)}</div></Section><Section title="Root Cause Summary"><p>{Object.entries(badCases.reduce((counts: Record<string, number>, item: any) => ({ ...counts, [item.category || "未记录"]: (counts[item.category || "未记录"] || 0) + 1 }), {} as Record<string, number>)).map(([key, count]) => `${key} ${count}`).join(" · ") || "无真实 Bad Case"}</p></Section><Section title="Bad Case Table"><div className="table-scroll"><table><thead><tr><th>Case</th><th>Question</th><th>Root Cause</th><th>Affected Gate</th><th>Evidence Status</th></tr></thead><tbody>{badCases.map((item: any) => <tr key={item.id} onClick={() => setSelectedBadCase(item)} tabIndex={0} onKeyDown={event => event.key === "Enter" && setSelectedBadCase(item)}><td><ShortId value={item.question_id} /></td><td className="question-cell">{item.result?.question || "未记录"}</td><td>{item.category || "未记录"}</td><td>{item.result?.failure_tags?.join("、") || "未记录"}</td><td>{item.result?.programmatic_metrics?.retrieval_hit === false ? "Retrieval Miss" : "已记录"}</td></tr>)}</tbody></table></div></Section></>}
    {stage === "agent" && <><Section title="Experiment Summary" action={<button className="secondary" onClick={() => setSearchOpen(true)}>查看 Search Space</button>}><div className="report-grid"><div><dt>Experiment</dt><dd><ShortId value={experiment?.id} /></dd></div><div><dt>Round</dt><dd>{latestRound ? `Round ${latestRound.round} · ${latestRound.evaluated}/${latestRound.total ?? 3}` : "未运行"}</dd></div><div><dt>Budget</dt><dd>{budget.used} / {budget.max} · D 预留 {budget.reserved_for_d ?? budget.reserved_for_d1 ?? 1}</dd></div><div><dt>Cases</dt><dd>{badCases.length}</dd></div><div><dt>Status</dt><dd><Status value={experiment?.status || "not_run"} /></dd></div></div></Section><Section title="Agent Diagnosis"><p className="summary-text">{experiment?.result?.root_cause_cluster || "尚未生成诊断"}</p><div className="diagnosis-cards">{["Retrieval", "Generation", "Safety"].map(name => { const rows = badCases.filter((item: any) => item.category === name); return <article key={name}><h3>{name} Problem</h3><p>{rows.length} affected cases</p><p>Evidence：{rows[0]?.result?.failure_tags?.join("、") || "未记录"}</p><p>Relevant Config：{name === "Retrieval" ? `CandidateK ${evaluation.config?.candidate_k ?? "—"} · TopK ${evaluation.config?.top_k ?? "—"}` : `Prompt ${evaluation.config?.prompt_strategy || "—"}`}</p></article>; })}</div><details><summary>查看诊断证据</summary><div className="evidence-list">{(experiment?.result?.observed_evidence || []).map((value: string, index: number) => <p key={index}>{value}</p>)}</div></details></Section><Section title="Optimization Hypotheses"><div className="table-scroll"><table><thead><tr><th>Candidate</th><th>Hypothesis</th><th>Target</th><th>Why</th><th>Parameters</th></tr></thead><tbody>{abc.map(candidate => <tr key={candidate.id}><td>{candidate.reasoning?.candidate_label}</td><td className="question-cell">{candidate.reasoning?.hypothesis || "未记录"}</td><td>{candidate.reasoning?.observed_evidence?.length || 0} Cases</td><td className="question-cell">{candidate.reasoning?.proposal || "未记录"}</td><td>{Object.keys(candidate.reasoning?.changed_parameters || {}).map(key => parameterNames[key] || key).join("、") || "无"}</td></tr>)}</tbody></table></div></Section></>}
    {stage === "candidates" && <><Section title="Candidate A / B / C" action={canContinue ? <button className="secondary" disabled={busy} onClick={() => void action("生成下一轮 A/B/C", () => postJson(`/api/experiments/${experiment.id}/continue`))}>继续优化下一轮</button> : undefined}>{[...new Set(abc.map(item => item.reasoning?.round || 1))].map(round => <div key={round}><h3 className="round-heading">Round {round}</h3><div className="candidate-cards">{abc.filter(item => (item.reasoning?.round || 1) === round).map(candidate => <CandidateCard key={candidate.id} candidate={candidate} baseline={evaluation.config || {}} running={activeOperation(candidate.id)} busy={busy} onRun={() => void run(candidate)} />)}</div></div>)}{!experiment && <p className="muted">需先完成真实 Baseline Evaluation 并识别 Bad Case。</p>}</Section>{confirmation && <Section title="Composite D"><p>Gate 2 Winner：<ShortId value={confirmation.winner_id} /></p>{composite?.status === "no_effective_composite" ? <p className="muted">No Effective Composite · 保留 Gate 2 Winner。</p> : d ? <><div className="report-grid"><div><dt>Base Winner</dt><dd><ShortId value={d.reasoning?.winner_id} /></dd></div><div><dt>Merge Source</dt><dd>{d.reasoning?.sources?.map((source: any) => source.candidate_id).join("、") || "无"}</dd></div><div><dt>Conflict Check</dt><dd>{d.reasoning?.conflicts?.length ? `${d.reasoning.conflicts.length} 冲突` : "无冲突"}</dd></div><div><dt>Recommendation</dt><dd>{recommendation.recommended_candidate === d.id ? "Recommended" : "保留 Gate 2 Winner"}</dd></div></div><div className="candidate-cards composite-card"><CandidateCard candidate={d} baseline={evaluation.config || {}} running={activeOperation(d.id)} busy={busy} onRun={() => void run(d)} /></div><details><summary>Merge Reason / Source Parameter Bundle</summary>{(d.reasoning?.sources || []).map((source: any) => <p key={source.candidate_id}><ShortId value={source.candidate_id} /> · {Object.entries(source.parameter_diff || {}).map(([key, value]) => `${key} → ${String(value)}`).join("；")} · {source.why_merge}</p>)}</details></> : <p className="muted">等待 Composite D 决策。</p>}</Section>}</>}
    {stage === "sandbox" && <Section title="Sandbox Compare"><div className="recommendation-summary"><strong>{recommendation.recommended_candidate ? orderedCandidates.find(item => item.id === recommendation.recommended_candidate)?.reasoning?.candidate_label || "Recommended" : qualified[0]?.reasoning?.candidate_label || "尚无推荐"}</strong><span>{recommendation.recommended_candidate ? "Final Recommendation" : "Gate 2 候选"}</span><p>{recommendation.recommended_candidate ? "推荐依据见已保存的资格与推荐审计。Overall 仅供比较，不能覆盖失败 Gate。" : "等待 Sandbox 资格与 Gate 2 结论；Overall 仅供比较。"}</p></div><div className="table-scroll"><table><thead><tr><th>指标</th><th>Baseline</th>{orderedCandidates.map(candidate => <th key={candidate.id}>{candidate.reasoning?.candidate_label || candidate.id.slice(-1)}</th>)}</tr></thead><tbody>{[["Overall", "overall_score"], ["Hard Gate", "gates"], ["Bad Case", "bad_case_count"], ["Fixed Bad Case", "target_bad_cases_fixed"], ["Regression", "regression"], ["Positive", "positive_correctness"], ["Ablation", "ablation_correctness"], ["Safety", "safe_rejection_rate"], ["TTFT", "ttft_seconds"], ["Token Cost", "token_cost"], ["Recall@K", "recall_at_k"], ["Precision@K", "precision_at_k"], ["MRR", "mrr"]].map(([label, key]) => <tr key={key}><td>{label}</td><td>{metricText(evaluation.result, key)}</td>{orderedCandidates.map(candidate => <td key={candidate.id}>{metricText(candidate.result, key)}</td>)}</tr>)}</tbody></table></div>
      <div className="run-list">{orderedCandidates.map(candidate => <div key={candidate.id}><strong>{candidate.reasoning?.candidate_label || candidate.id}</strong><span>{candidate.id} · {candidate.status} · {candidate.result?.qualification?.qualified ? "Qualified" : "Not Qualified"}</span></div>)}</div>
      {recommendation.status && <Badge tone="neutral">{recommendation.status}</Badge>}
      {!confirmation && qualified.length > 0 && candidates.every(item => !["running", "queued"].includes(item.status)) && <div className="review-batch"><label>Gate 2 · 确认 A/B/C 报告并选择合格赢家<select aria-label="选择合格赢家" value={selectedWinner} onChange={event => setWinnerId(event.target.value)}>{qualified.map(candidate => <option key={candidate.id} value={candidate.id}>{candidate.reasoning?.candidate_label} · {candidate.id}</option>)}</select></label><button className="primary" disabled={busy} onClick={() => void action("确认 A/B/C 报告", () => postJson(`/api/experiments/${experiment.id}/recommendation`, { candidate_id: selectedWinner, actor: "human" }))}>确认报告与赢家</button></div>}
      {confirmation && !composite && <div className="review-batch"><span>Gate 2 已确认赢家 {confirmation.winner_id}</span><button className="primary" disabled={busy} onClick={() => void action("构建 Composite D", () => postJson(`/api/experiments/${experiment.id}/composite`))}>构建 Composite D</button></div>}
      {composite?.status === "no_effective_composite" && <p className="muted">无有效组合，保留 Gate 2 赢家 {confirmation?.winner_id}。</p>}
      {composite && <details><summary>Composite D 决策详情</summary><p>Base Winner：{composite.winner_id || "未记录"}</p><p>Merged Changes：{(composite.sources || []).map((item: any) => `${item.candidate_id}: ${JSON.stringify(item.parameters || item.changes || item.diff || {})}`).join("；") || "无"}</p><p>Conflicts：{(composite.conflicts || []).map((item: any) => `${item.candidate_id} ${item.parameters?.join("、")}`).join("；") || "无"}</p></details>}
      {composite?.status === "generated" && <p className="muted">Composite D 已生成；请到候选方案运行完整 Sandbox。若 D 失败或打平，保留 Gate 2 赢家。</p>}
      {recommendation.status === "Recommended" && <p className="success-notice">推荐 {recommendation.recommended_candidate || confirmation?.winner_id}；Gate 3 可在版本与发布页人工确认。</p>}
    </Section>}
    <Drawer open={searchOpen} onOpenChange={setSearchOpen} title="Search Space · Frozen by SPEC V1.3" className="search-space-drawer"><div className="drawer-body"><p>Optimization Agent 只能修改以下字段；参数类型、允许值来自后端 Validator 的同一策略。</p>{searchSpace?.search_space ? <SearchSpaceTable contract={searchSpace.search_space} baseline={searchSpace.baseline_config || evaluation.config || {}} /> : <p>{error || "正在读取 Search Space…"}</p>}</div></Drawer>
    <Drawer open={!!selectedBadCase} onOpenChange={open => !open && setSelectedBadCase(null)} title="Bad Case Diagnosis"><div className="drawer-body">{selectedBadCase && <><h3>Question</h3><p>{selectedBadCase.result?.question}</p><h3>Root Cause</h3><p>{selectedBadCase.category} · {selectedBadCase.result?.failure_tags?.join("、") || "未记录"}</p><h3>Model Answer</h3><p>{selectedBadCase.result?.model_answer || "未记录"}</p><TechnicalDetails label="Raw Trace">{JSON.stringify(selectedBadCase.result, null, 2)}</TechnicalDetails></>}</div></Drawer>
  </div>;
}

function CandidateCard({ candidate, baseline, running, busy, onRun }: { candidate: any; baseline: Record<string, any>; running?: { current?: number; total?: number; stage?: string }; busy: boolean; onRun: () => void }) {
  const reasoning = candidate.reasoning || {};
  return <article className="candidate-card"><div className="candidate-card-header"><div><small>Round {reasoning.round || 1}</small><h3>{reasoning.candidate_label === "D" ? "Composite D" : `Candidate ${reasoning.candidate_label || "—"}`}</h3></div><Status value={running ? "running" : candidate.result?.qualification?.qualified ? "Qualified" : candidate.status === "evaluated" ? "Not Qualified" : candidate.status || "not_run"} /></div><div className="candidate-card-body"><div><span className="field-label">Hypothesis</span><p className="line-clamp-3">{reasoning.hypothesis || "未记录"}</p></div><div><span className="field-label">Target Bad Cases</span><details><summary>{reasoning.observed_evidence?.length || 0} Cases · 查看详情</summary>{(reasoning.observed_evidence || []).map((id: string) => <p key={id}><ShortId value={id} /></p>)}</details></div><div><span className="field-label">Why</span><p className="line-clamp-3">{reasoning.proposal || "未记录"}</p></div><div><span className="field-label">Config Diff</span><ConfigDiff base={baseline} candidate={candidate} /></div><div className="candidate-result"><span>Hard Gate <strong>{candidate.result?.gates ? `${candidate.result.gates.passed_count}/${candidate.result.gates.total}` : "未运行"}</strong></span><span>Fixed <strong>{candidate.result?.target_bad_cases_fixed ?? "未运行"}</strong></span><span>Regression <strong>{candidate.result?.regression?.status || "未运行"}</strong></span></div><div><span className="field-label">Risk</span><p className="line-clamp-2">{reasoning.risk || "未记录"}</p></div>{running && <div className="inline-progress" role="status"><strong>Sandbox Running · {running.stage || "等待评测"}</strong>{running.current != null && running.total != null && running.total > 1 && <><p>{running.current} / {running.total} · {Math.round(running.current / running.total * 100)}%</p><progress value={running.current} max={running.total} /></>}</div>}</div><div className="candidate-card-action"><button className="secondary" disabled={busy || !!running || candidate.status !== "generated"} onClick={onRun}>{running ? "Sandbox Running" : candidate.status === "evaluated" ? "Evaluated" : "Run Sandbox"}</button></div></article>;
}

function ConfigDiff({ base, candidate }: { base: Record<string, any>; candidate: any }) {
  const changes = Object.entries(candidate.reasoning?.changed_parameters || {});
  return changes.length ? <div className="table-scroll"><table><thead><tr><th>Parameter</th><th>Baseline</th><th>Candidate</th></tr></thead><tbody>{changes.map(([key, value]) => <tr key={key}><td>{parameterNames[key] || key}</td><td>{formatValue(base[key])}</td><td>{formatValue(value)}</td></tr>)}</tbody></table></div> : <p>无参数变化记录。</p>;
}

function metricText(result: any, key: string) {
  if (!result) return "未运行";
  if (key === "gates") return result.gates ? `${result.gates.passed_count} / ${result.gates.total}` : "未运行";
  if (key === "regression") return result.regression?.status || "N/A";
  const value = result.comparison_metrics?.[key] ?? result.metrics?.[key] ?? result[key];
  return typeof value === "number" ? value.toFixed(2) : value ?? "未采集";
}
