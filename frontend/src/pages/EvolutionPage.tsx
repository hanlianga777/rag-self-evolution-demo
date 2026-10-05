import { PageShell } from "../components/PageShell";
import { RetrievalEvidence } from "../components/RetrievalEvidence";
import { useEffect, useRef, useState } from "react";
import { Play } from "lucide-react";
import { errorMessage, getJson, identityKey, postJson } from "../api";
import { ConclusionCard, CustomSelect, Section, ShortId, Status, TruncatedText } from "../components/Primitives";
import { ExecutionMetrics, ParameterDiff, SearchSpaceTable, parameterNames, formatValue, billedCostText } from "../components/PipelineFields";
import { Drawer } from "../components/Dialog";
import { useOperation } from "../operation";
import { displayText } from "../display";
import { CaseDetails } from "./EvaluationPage";

const gateNames: Record<string, string> = { ablation_correctness: "Ablation Correctness（消融题正确性）", safe_rejection_rate: "Safe Rejection Rate（安全拒答率）" };
const rootCause = (item: any) => item.primary_root_cause || item.result?.primary_root_cause || item.result?.root_cause?.primary || item.category || "未记录";
const changedKeys = (baseline: Record<string, any>, candidate: any) => Object.keys(candidate.config || candidate.reasoning?.changed_parameters || {}).filter(key => (candidate.config || candidate.reasoning.changed_parameters)[key] !== baseline[key]);
const humanizeField = (value: string) => value.split("_").map(word => word[0]?.toUpperCase() + word.slice(1)).join(" ");

export function EvolutionPage({ data }: { data: any }) {
  const operation = useOperation();
  const [stage, setStage] = useState<"bad" | "agent" | "candidates" | "sandbox">("bad");
  const [experiment, setExperiment] = useState<any>(data.optimization?.id ? data.optimization : null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [searchSpace, setSearchSpace] = useState<any>(null);
  const [selectedCandidate, setSelectedCandidate] = useState<any>(null), [candidateReport, setCandidateReport] = useState<any>(null);
  useEffect(() => { setCandidateReport(null); const id = selectedCandidate?.result?.evaluation_run_id; if (!id) return; let cancelled = false; void getJson<any>(`/api/evaluations/${id}`).then(value => { if (!cancelled) setCandidateReport(value); }).catch(() => {}); return () => { cancelled = true; }; }, [selectedCandidate]);
  const [selectedBadCase, setSelectedBadCase] = useState<any>(null);
  const refreshed = useRef(new Set<string>());
  const [winnerId, setWinnerId] = useState("");
  const evaluation = data.evaluation || {};
  const identity = identityKey(data.workspace || data.evaluation);
  const currentIdentity = useRef(identity); currentIdentity.current = identity;
  useEffect(() => { setExperiment(data.optimization?.id ? data.optimization : null); setSelectedCandidate(null); setCandidateReport(null); setSelectedBadCase(null); setWinnerId(""); setSearchOpen(false); setAdvancedOpen(false); setSearchSpace(null); setError(""); setBusy(false); }, [identity]);
  const [causeFilter, setCauseFilter] = useState<string | null>(null);
  useEffect(() => { setCauseFilter(null); }, [identity]);
  const badCases = (data.badCases || []).filter((item: any) => item.run_id === evaluation.id);
  const candidates: any[] = experiment?.candidates || [];
  const abc = candidates.filter(candidate => candidate.reasoning?.candidate_label !== "D").sort((a, b) => (a.reasoning?.round || 1) - (b.reasoning?.round || 1) || String(a.reasoning?.candidate_label).localeCompare(String(b.reasoning?.candidate_label)));
  const d = candidates.find(candidate => candidate.reasoning?.candidate_label === "D");
  const orderedCandidates = d ? [...abc, d] : abc;
  const recommendation = experiment?.recommendation?.result || experiment?.recommendation || {};
  const confirmation = experiment?.result?.report_confirmation || recommendation.report_confirmation;
  const composite = experiment?.result?.composite || recommendation.composite;
  const dWinner = candidates.find(item => item.id === (d?.reasoning?.winner_id || confirmation?.winner_id));
  const retainedWinner = d && recommendation.recommended_candidate && recommendation.recommended_candidate !== d.id;
  const dDecision = !d || d.status !== "evaluated" ? { title: d?.status === "failed" ? "Composite D 运行失败" : "等待完整 Sandbox", message: d?.status === "failed" ? "运行未完成，继续保留 Gate 2 Winner。" : "Composite D 尚无完整评测与资格结论。", tone: "neutral" as const }
    : retainedWinner ? { title: `保留 ${candidateName(dWinner)}`, message: d.result?.qualification?.qualified === true ? "Composite D 已满足资格；保存的推荐决策仍保留 Gate 2 Winner。" : d.result?.qualification?.qualified === false ? "Composite D 未满足发布资格，保存的推荐决策保留 Gate 2 Winner。" : "保存的推荐决策保留 Gate 2 Winner。", tone: "warning" as const }
    : d.result?.qualification?.qualified === true ? { title: recommendation.recommended_candidate === d.id ? "采用 Composite D" : "Composite D 满足资格", message: recommendation.recommended_candidate === d.id ? "保存的推荐决策采用 Composite D。" : "Composite D 已达到资格要求，等待推荐结论。", tone: "good" as const }
    : { title: d.result?.qualification?.qualified === false ? `保留 ${candidateName(dWinner)}` : "等待资格与推荐结论", message: d.result?.regression?.passed === false ? "Composite D 未通过 Regression，保留 Gate 2 Winner。" : d.result?.qualification?.qualified === false ? "Composite D 未满足发布资格，保留 Gate 2 Winner。" : "历史结果未保存完整资格结论。", tone: "warning" as const };
  const budget = experiment?.evaluation_budget || { used: candidates.filter(item => ["evaluated", "failed", "running"].includes(item.status)).length, max: 12, reserved_for_d: 1 };
  const latestRound = experiment?.rounds?.at(-1);
  const canContinue = latestRound?.complete && recommendation.status === "No Qualified Candidate" && budget.used < budget.max - (budget.reserved_for_d ?? budget.reserved_for_d1 ?? 1);
  const qualified = candidates.filter(item => ["A", "B", "C"].includes(item.reasoning?.candidate_label) && item.status === "evaluated" && item.result?.qualification?.qualified);
  const selectedWinner = qualified.some(item => item.id === winnerId) ? winnerId : qualified[0]?.id || "";
  const activeOperation = (candidateId: string) => operation.operations.find(item => item.candidateId === candidateId && item.status === "running");
  const causes = badCases.reduce((counts: Record<string, number>, item: any) => ({ ...counts, [rootCause(item)]: (counts[rootCause(item)] || 0) + 1 }), {} as Record<string, number>);
  const failedGates = (evaluation.result?.gates?.gates || []).filter((gate: any) => gate.status === "FAIL");
  const gateDetails = evaluation.gate_details || [];
  const snapshot = evaluation.dataset_snapshot || (() => { try { return JSON.parse(evaluation.dataset_snapshot_json || "{}"); } catch { return {}; } })();
  const refresh = async () => { const captured = identity; const value: any = await getJson("/api/optimization"); if (currentIdentity.current === captured && (!value.current_baseline_id || value.current_baseline_id === evaluation.id)) setExperiment(value.id ? value : null); };

  useEffect(() => { let cancelled = false; void getJson("/api/pipeline").then(value => { if (!cancelled) setSearchSpace(value); }).catch(reason => { if (!cancelled) setError(errorMessage(reason)); }); return () => { cancelled = true; }; }, [identity]);
  useEffect(() => {
    for (const item of operation.operations) if (item.candidateId && item.status !== "running" && !refreshed.current.has(item.id)) {
      refreshed.current.add(item.id); void refresh();
    }
  }, [operation.operations]);

  const action = async (title: string, work: () => Promise<unknown>) => {
    const captured = identity;
    setBusy(true); setError("");
    try { await operation.run(title, work); await refresh(); }
    catch (reason) { if (currentIdentity.current === captured) setError(errorMessage(reason)); }
    finally { if (currentIdentity.current === captured) setBusy(false); }
  };
  const generate = async () => {
    const captured = identity;
    setBusy(true); setError("");
    try { await operation.run("生成 A/B/C 候选", () => postJson("/api/experiments/run")); await refresh(); }
    catch (reason) { if (currentIdentity.current === captured) setError(errorMessage(reason)); }
    finally { if (currentIdentity.current === captured) setBusy(false); }
  };
  const run = async (candidate: any) => {
    if (candidate.status !== "generated" || activeOperation(candidate.id)) return;
    const captured = identity;
    setBusy(true); setError("");
    try { await operation.startEvaluation(`Candidate ${candidate.reasoning?.candidate_label} · Sandbox`, () => postJson(`/api/candidates/${candidate.id}/run`), candidate.id); await refresh(); }
    catch (reason) { if (currentIdentity.current === captured) setError(errorMessage(reason)); }
    finally { if (currentIdentity.current === captured) setBusy(false); }
  };

  return <PageShell className="page evolution-page" header={<div className="page-title"><div><h1>Agent 工作台</h1><p>基于 Baseline 根因提出受控优化方案，并通过 Sandbox / Regression 验证。</p></div><button className="primary" disabled={busy || evaluation.status !== "completed" || (!badCases.length && !experiment?.result?.monitoring_context && !experiment?.result?.monitoring_event)} onClick={() => void generate()}><Play size={15} />{busy ? "处理中…" : "生成 A / B / C"}</button></div>} tabs={<div className="tabs"><button aria-pressed={stage === "bad"} className={stage === "bad" ? "active" : ""} onClick={() => setStage("bad")}>诊断</button><button aria-pressed={stage === "agent"} className={stage === "agent" ? "active" : ""} onClick={() => setStage("agent")}>优化 Agent</button><button aria-pressed={stage === "candidates"} className={stage === "candidates" ? "active" : ""} onClick={() => setStage("candidates")}>A / B / C / D</button><button aria-pressed={stage === "sandbox"} className={stage === "sandbox" ? "active" : ""} onClick={() => setStage("sandbox")}>Sandbox</button></div>} resetKey={stage}>


    {error && <p className="error-notice" role="alert">{error}</p>}
    {data.workspace?.baseline_unavailable_reason && <p className="error-notice">{data.workspace.baseline_unavailable_reason}</p>}
    <p className="muted">{evaluation.id ? <>当前 Baseline：<ShortId value={evaluation.id} /> · Failed Gate {failedGates.map((gate: any) => gateNames[gate.metric] || humanizeField(gate.metric)).join("、") || "无已记录失败"}</> : "当前有效 Baseline 尚未就绪。"}</p>
    {stage === "bad" && <Section title="根因诊断"><p className="muted">来自当前 Baseline 保存的 Primary Root Cause 与案例证据。</p><div className="diagnosis-cards">{Object.entries(causes).filter(([, count]) => Number(count) > 0).map(([name, count]) => {
      const rows = badCases.filter((row: any) => rootCause(row) === name);
      const questionIds = new Set(rows.map((row: any) => row.question_id || row.result?.question_id));
      const caseIds = new Set(rows.flatMap((row: any) => [row.id, row.question_id, row.result?.question_id]));
      const evidence = [...new Set(rows.flatMap((row: any) => [row.result?.programmatic_metrics?.evidence_coverage?.diagnostic_basis, ...(row.result?.failure_tags || [])]).filter(Boolean))];
      const relatedGates = gateDetails.filter((gate: any) => gate.status === "FAIL" && gate.contributing_cases?.some((row: any) => questionIds.has(row.question_id)));
      const capabilities = [...new Set(abc.filter(candidate => (candidate.reasoning?.observed_evidence || candidate.reasoning?.target_bad_cases || []).some((id: string) => caseIds.has(id))).flatMap(candidate => changedKeys(evaluation.config || {}, candidate)).filter(key => searchSpace?.search_space?.[key]))];
      return <article className="diagnosis-card" key={name} role="button" tabIndex={0} onClick={() => setCauseFilter(name)} onKeyDown={event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); setCauseFilter(name); } }}><h3>{displayText(name)}</h3><dl><div><dt>Evidence</dt><dd>{String(count)} 个 Bad Case</dd></div><div><dt>现象</dt><dd>{evidence.join("、") || "保存的判断依据见案例"}</dd></div>{relatedGates.length > 0 && <div><dt>影响</dt><dd>{relatedGates.map((gate: any) => gateNames[gate.metric] || humanizeField(gate.metric)).join("、")}</dd></div>}{capabilities.length > 0 && <div><dt>Agent 可用能力</dt><dd>{capabilities.map(key => parameterNames[key] || key).join(" / ")}</dd></div>}</dl><span className="diagnosis-card-link">查看 {String(count)} 个相关案例 →</span></article>;
    })}</div>{!badCases.length && <p>当前 Baseline 无已记录 Bad Case。</p>}</Section>}
    {stage === "agent" && <>
      <Section title="Agent 收到了什么"><dl className="report-grid"><div><dt>Failed Gate</dt><dd>{failedGates.map((gate: any) => gateNames[gate.metric] || humanizeField(gate.metric)).join("、") || "无已记录失败 Gate"}</dd></div><div><dt>Bad Cases</dt><dd>{badCases.length} 个</dd></div><div><dt>Primary Root Cause</dt><dd>{Object.entries(causes).map(([name, count]) => `${displayText(name)} ${count}`).join(" · ") || "无已记录根因"}</dd></div></dl>{experiment?.result?.monitoring_context && <p>已确认 Monitoring 上下文 · {experiment.result.monitoring_context.event?.question} · 明确点击生成后启动 Round 1。</p>}</Section>
      <Section title="Agent 能改什么" action={<button className="text-button" onClick={() => setSearchOpen(true)}>Search Space{searchSpace?.search_space && ` · ${Object.keys(searchSpace.search_space).length}`}</button>}><p>只在冻结 Search Space 内提出参数变化。</p><p>评测预算 {budget.used} / {budget.max} · D 预留 {budget.reserved_for_d ?? budget.reserved_for_d1 ?? 1}{latestRound && ` · 第 ${latestRound.round} 轮${latestRound.evaluated != null && latestRound.total != null ? ` · ${latestRound.evaluated}/${latestRound.total}` : ""}`}</p></Section>
      <Section title="Agent 决定验证什么">{experiment?.result?.root_cause_cluster && <p>{experiment.result.root_cause_cluster}</p>}<ul className="agent-hypotheses">{abc.filter(candidate => (candidate.reasoning?.round || 1) === (latestRound?.round || 1) && candidate.reasoning?.hypothesis).map(candidate => <li key={candidate.id}><p>{candidate.reasoning.hypothesis}</p></li>)}</ul>{!abc.length && <p>{experiment?.status === "failed" ? "Agent 运行失败，修正后可重试；没有可用候选。" : "尚未生成 Agent 假设；机器诊断见诊断页。"}</p>}null</Section>
    </>}
    {stage === "candidates" && <><Section title="Candidate A / B / C" action={canContinue ? <button className="secondary" disabled={busy} onClick={() => void action("生成下一轮 A/B/C", () => postJson(`/api/experiments/${experiment.id}/continue`))}>继续优化下一轮</button> : undefined}>{[...new Set(abc.map(item => item.reasoning?.round || 1))].map(round => <div key={round}><h3 className="round-heading">第 {round} 轮</h3><div className="candidate-cards">{abc.filter(item => (item.reasoning?.round || 1) === round).map(candidate => <CandidateCard key={candidate.id} candidate={candidate} baseline={evaluation.config || {}} onDetail={() => setSelectedCandidate(candidate)} running={activeOperation(candidate.id)} busy={busy} onRun={() => void run(candidate)} />)}</div></div>)}{!experiment && <p className="muted">需先完成真实 Baseline Evaluation 并识别 Bad Case。</p>}</Section>{(confirmation || d || composite) && <Section title="Composite D · 有效能力组合验证">{composite?.status === "no_effective_composite" ? <ConclusionCard title="保留 Gate 2 Winner" tone="warning">没有有效的 Composite D，继续采用已确认的 Candidate。</ConclusionCard> : d ? <div className="composite-decision"><section><h3>组合决策</h3><dl><div><dt>基础 Winner</dt><dd>{candidateName(candidates.find((item: any) => item.id === (d.reasoning?.winner_id || confirmation?.winner_id)))}</dd></div><div><dt>合并来源</dt><dd>{(d.reasoning?.sources || []).map((source: any) => candidateName(candidates.find((item: any) => item.id === source.candidate_id))).join("、") || "未记录"}</dd></div><div><dt>冲突检查</dt><dd>{d.reasoning?.conflicts?.length ? `${d.reasoning.conflicts.length} 项冲突` : "无冲突"}</dd></div></dl><h4>参数差异</h4><ConfigDiff base={evaluation.config || {}} candidate={d} /></section><section><h3>评测结果</h3><div className="d-result-grid"><div><span>Hard Gate</span><strong>{d.result?.gates ? `${d.result.gates.passed_count} / ${d.result.gates.total}` : "未运行"}</strong></div><div><span>修复 Bad Case</span><strong>{d.result?.target_bad_cases_fixed ?? "未运行"}</strong></div><div><span>Regression</span><strong>{d.result?.regression?.status || "未运行"}</strong></div><div><span>发布资格</span><strong>{d.status === "evaluated" ? metricText(d.result, "qualification") : "未判定"}</strong></div></div><ConclusionCard title={dDecision.title} tone={dDecision.tone}>{dDecision.message}</ConclusionCard><button className="text-button" onClick={() => setSelectedCandidate(d)}>查看 D 完整报告与 Decision</button>{d.status === "generated" && <CandidateAction candidate={d} running={activeOperation(d.id)} busy={busy} onRun={() => void run(d)} />}</section></div> : <p className="muted">等待 Composite D 决策。</p>}</Section>}</>}
    {stage === "sandbox" && <Section title="Sandbox 对比" action={<button className="text-button" onClick={() => setAdvancedOpen(true)}>查看高级指标</button>}><ConclusionCard title={recommendation.recommended_candidate ? `推荐 ${candidateName(candidates.find((item: any) => item.id === recommendation.recommended_candidate))}` : "等待资格与 Gate 2 结论"} status={recommendation.status && <Status value={recommendation.status} />} tone={recommendation.recommended_candidate ? "good" : "neutral"}>{recommendation.recommended_candidate ? "推荐依据来自已保存的资格与推荐审计。Overall 仅供比较，不能覆盖失败 Gate。" : "Hard Gate 与 Regression 共同决定资格。"}</ConclusionCard><div className="table-scroll sandbox-core-table"><table><thead><tr><th>指标</th><th>Baseline</th>{orderedCandidates.map(candidate => <th key={candidate.id}>{candidate.reasoning?.candidate_label || candidate.id.slice(-1)}</th>)}</tr></thead><tbody>{[["Hard Gate", "gates"], ["Bad Case", "bad_case_count"], ["Regression", "regression"], ["Qualification", "qualification"]].map(([label, key]) => <tr key={key}><td>{label}</td><td>{metricText(evaluation.result, key)}</td>{orderedCandidates.map(candidate => <td key={candidate.id}>{metricText(candidate.result, key)}</td>)}</tr>)}</tbody></table></div>{!d && <p className="muted">Composite D：{composite?.status === "no_effective_composite" ? "已跳过 · 无有效组合" : "等待 Gate 2 与组合决策"}</p>}
      {!confirmation && qualified.length > 0 && candidates.every(item => !["running", "queued"].includes(item.status)) && <div className="review-batch"><label>Gate 2 · 确认 A/B/C 报告并选择合格赢家<CustomSelect ariaLabel="选择合格赢家" value={selectedWinner} onChange={setWinnerId} options={qualified.map(candidate => ({ value: candidate.id, label: candidateName(candidate), description: "Gate 通过" }))} /></label><button className="primary" disabled={busy} onClick={() => void action("确认 A/B/C 报告", () => postJson(`/api/experiments/${experiment.id}/recommendation`, { candidate_id: selectedWinner, actor: "human" }))}>确认报告与赢家</button></div>}
      {confirmation && !composite && <div className="review-batch"><span>Gate 2 已确认赢家 {candidateName(candidates.find(item => item.id === confirmation?.winner_id))}</span><button className="primary" disabled={busy} onClick={() => void action("构建 Composite D", () => postJson(`/api/experiments/${experiment.id}/composite`))}>构建 Composite D</button></div>}
      {composite?.status === "no_effective_composite" && <p className="muted">无有效组合，保留 Gate 2 赢家 {candidateName(candidates.find(item => item.id === confirmation?.winner_id))}。</p>}
      {composite?.status === "generated" && <p className="muted">Composite D 已生成；请到候选方案运行完整 Sandbox。若 D 失败或打平，保留 Gate 2 赢家。</p>}

    </Section>}
    <Drawer open={advancedOpen} onOpenChange={setAdvancedOpen} title="Sandbox · 高级指标"><div className="drawer-body"><p>诊断与比较指标不替代 Hard Gate / Regression 资格判定。</p><div className="table-scroll"><table><thead><tr><th>指标</th><th>Baseline</th>{orderedCandidates.map(candidate => <th key={candidate.id}>{candidate.reasoning?.candidate_label || candidate.id}</th>)}</tr></thead><tbody>{[["Fixed Bad Case", "target_bad_cases_fixed"], ["Positive", "positive_correctness"], ["Ablation", "ablation_correctness"], ["Safety", "safe_rejection_rate"], ["Overall", "overall_score"], ["TTFT", "ttft_seconds"], ["Input Tokens", "input_tokens"], ["Output Tokens", "output_tokens"], ["Provider Cost", "token_cost"], ["Recall@K", "recall_at_k"], ["Precision@K", "precision_at_k"], ["MRR", "mrr"]].map(([label, key]) => <tr key={key}><td>{label}</td><td>{metricText(evaluation.result, key)}</td>{orderedCandidates.map(candidate => <td key={candidate.id}>{metricText(candidate.result, key)}</td>)}</tr>)}</tbody></table></div><p className="muted">历史运行未保存完整计费信息，无法准确回算。</p></div></Drawer>
    <Drawer open={!!selectedCandidate} onOpenChange={open => !open && setSelectedCandidate(null)} title={`${candidateName(selectedCandidate)} · 方案详情`}><div className="drawer-body">{selectedCandidate && <><h3>假设 / Why / Risk</h3><p>{selectedCandidate.reasoning?.hypothesis || "未记录"}</p><p>Why：{selectedCandidate.reasoning?.proposal || selectedCandidate.reasoning?.why || "未记录"}</p><p>Risk：{selectedCandidate.reasoning?.risk || "未记录"}</p><h3>组合来源与冲突</h3>{selectedCandidate.reasoning?.winner_id && <p>基础 Winner：{candidateName(candidates.find(item => item.id === selectedCandidate.reasoning.winner_id))}</p>}{(selectedCandidate.reasoning?.sources || []).map((source: any) => <p key={source.candidate_id}>{candidateName(candidates.find(item => item.id === source.candidate_id))} · {Object.entries(source.parameter_diff || {}).map(([key, value]) => `${parameterNames[key] || key} → ${formatValue(value)}`).join("；")} · {source.why_merge || "未保存合并理由"}</p>)}{selectedCandidate.reasoning?.conflicts && <p>冲突：{Object.keys(selectedCandidate.reasoning.conflicts).join("、")}</p>}<h3>目标案例</h3>{(selectedCandidate.reasoning?.observed_evidence || selectedCandidate.reasoning?.target_bad_cases || []).map((id: string) => <p key={id}>{badCases.find((row: any) => row.id === id || row.question_id === id)?.result?.question || id}</p>)}<ParameterDiff before={evaluation.config} after={selectedCandidate.config} /><p>评测执行：{selectedCandidate.status === "evaluated" ? "已完成" : selectedCandidate.status === "failed" ? "运行失败" : ["running", "queued"].includes(selectedCandidate.status) ? "运行中" : "未运行"} · 发布资格：{selectedCandidate.status === "evaluated" ? selectedCandidate.result?.qualification?.qualified ? "合格" : "不合格" : "未判定"} · Hard Gate：{selectedCandidate.result?.gates?.passed === true ? "通过" : selectedCandidate.result?.gates?.passed === false ? "未通过" : "未运行"}</p><ExecutionMetrics metrics={candidateReport?.cases?.find((row: any) => row.programmatic_metrics?.stages)?.programmatic_metrics || { input_tokens: selectedCandidate.result?.comparison_metrics?.input_tokens, output_tokens: selectedCandidate.result?.comparison_metrics?.output_tokens }} /><h3>Sandbox / Regression</h3><p>Regression：{selectedCandidate.result?.regression?.status || "未运行"} · 修复 {selectedCandidate.result?.target_bad_cases_fixed ?? "未采集"} 个目标案例</p>{candidateReport?.cases?.length > 0 && <div className="table-scroll"><table><thead><tr><th>Question</th><th>判定</th><th>根因 / 依据</th></tr></thead><tbody>{candidateReport.cases.map((row: any) => <tr key={row.question_id}><td><TruncatedText lines={2}>{row.question}</TruncatedText></td><td>{row.passed ? "通过" : "未通过"}</td><td>{row.primary_root_cause || row.judge_result?.reason || "未采集"}</td></tr>)}</tbody></table></div>}null</>}</div></Drawer>
    <Drawer open={searchOpen} onOpenChange={setSearchOpen} title={`Search Space · ${searchSpace?.search_space ? Object.keys(searchSpace.search_space).length : "—"}`} className="search-space-drawer"><div className="drawer-body"><p>优化 Agent 只能修改以下字段；参数类型、允许值来自后端 Validator 的同一策略。</p>{searchSpace?.search_space ? <SearchSpaceTable contract={searchSpace.search_space} baseline={evaluation.config || {}} /> : <p>{error || "正在读取 Search Space…"}</p>}</div></Drawer>
    <Drawer open={!!causeFilter} onOpenChange={open => !open && setCauseFilter(null)} title={`${causeFilter || ""} · Cases & Evidence`}><div className="drawer-body">{badCases.filter((row: any) => rootCause(row) === causeFilter).map((row: any) => <section key={row.id}><h3>{row.result?.question || "未记录"}</h3><p>{row.result?.failure_tags?.join("、") || "依据未采集"}</p><RetrievalEvidence metrics={row.result?.programmatic_metrics} /><button className="text-button" onClick={() => { setCauseFilter(null); setSelectedBadCase(row); }}>查看完整案例</button></section>)}</div></Drawer>
    <Drawer open={!!selectedBadCase} onOpenChange={open => !open && setSelectedBadCase(null)} title="Bad Case 诊断"><div className="drawer-body">{selectedBadCase && <CaseDetails item={{ ...selectedBadCase.result, question_id: selectedBadCase.question_id || selectedBadCase.result?.question_id, primary_root_cause: rootCause(selectedBadCase) }} snapshot={snapshot} config={evaluation.config || {}} gates={gateDetails} />}</div></Drawer>
  </PageShell>;
}

function CandidateCard({ candidate, baseline, onDetail, running, busy, onRun }: { candidate: any; baseline: Record<string, any>; onDetail: () => void; running?: { current?: number; total?: number; stage?: string }; busy: boolean; onRun: () => void }) {
  const reasoning = candidate.reasoning || {};
  return <article className="candidate-card"><div className="candidate-card-header"><div><small>第 {reasoning.round || 1} 轮</small><h3>Candidate {reasoning.candidate_label || "—"}</h3></div><Status value={running ? "running" : candidate.result?.qualification?.qualified ? "Qualified" : candidate.status === "evaluated" ? "Not Qualified" : candidate.status || "not_run"} /></div><div className="candidate-card-body">
    <div className="candidate-story-block"><span className="field-label">WHY</span><TruncatedText lines={3}>{reasoning.proposal || reasoning.why || reasoning.hypothesis || "历史未保存提出理由"}</TruncatedText></div>
    <div className="candidate-story-block"><span className="field-label">CHANGE</span><ConfigDiff base={baseline} candidate={candidate} /></div>
    <div className="candidate-story-block"><span className="field-label">RESULT</span><dl className="candidate-result"><div><dt>Hard Gate</dt><dd>{metricText(candidate.result, "gates")}</dd></div><div><dt>Regression</dt><dd>{metricText(candidate.result, "regression")}</dd></div><div><dt>Qualification</dt><dd>{candidate.status === "evaluated" ? metricText(candidate.result, "qualification") : "未判定"}</dd></div></dl></div>
    {running && <div className="inline-progress" role="status"><strong>Sandbox 运行中 · {running.stage || "等待评测"}</strong>{running.current != null && running.total != null && running.total > 1 && <><p>{running.current} / {running.total} · {Math.round(running.current / running.total * 100)}%</p><progress value={running.current} max={running.total} /></>}</div>}
  </div><button className="text-button" onClick={event => { event.currentTarget.focus(); onDetail(); }}>查看方案与完整报告</button><CandidateAction candidate={candidate} running={running} busy={busy} onRun={onRun} /></article>;
}

function ConfigDiff({ base, candidate }: { base: Record<string, any>; candidate: any }) {
  const after = candidate.config || (candidate.reasoning?.changed_parameters ? { ...base, ...candidate.reasoning.changed_parameters } : null);
  return <div className="candidate-config-diff">{after ? <ParameterDiff before={base} after={after} /> : <p className="muted">历史未保存可比较配置。</p>}</div>;
}

function CandidateAction({ candidate, running, busy, onRun }: { candidate: any; running?: { current?: number; total?: number }; busy: boolean; onRun: () => void }) {
  return <div className="candidate-card-action"><button className="secondary" disabled={busy || !!running || candidate.status !== "generated"} onClick={onRun}>{running ? "Sandbox 运行中" : candidate.status === "evaluated" ? "已评测" : "运行 Sandbox"}</button>{running && running.current != null && running.total != null && <span>{running.current} / {running.total}</span>}</div>;
}

const candidateName = (candidate?: any) => candidate ? `Candidate ${candidate.reasoning?.candidate_label || "—"}` : "Candidate";

function metricText(result: any, key: string) {
  if (!result) return "未运行";
  if (key === "gates") return result.gates ? `${result.gates.passed_count} / ${result.gates.total}` : "未运行";
  if (key === "regression") return result.regression?.status || "N/A";
  if (key === "qualification") return typeof result.qualification?.qualified === "boolean" ? result.qualification.qualified ? "PASS" : "FAIL" : "N/A";
  if (key === "token_cost") return billedCostText(result.comparison_metrics);
  const value = result.comparison_metrics?.[key] ?? result.metrics?.[key] ?? result[key];
  if (["bad_case_count", "target_bad_cases_fixed", "input_tokens", "output_tokens"].includes(key) && typeof value === "number") return String(value);
  return typeof value === "number" ? value.toFixed(2) : value ?? "未采集";
}
