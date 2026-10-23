import { StoryDisclosure } from "../components/Storytelling";
import { FilterButtons } from "../components/Storytelling";
import './evaluation-workspaces.css';
import {DiagnosisTable, questionLabel, optimizationDirection, savedDirections, coreEvidence, caseData, currentRoot, rootName, symptoms, agentDiagnosisRows} from '../components/EvaluationDiagnosis';
import { CandidateCaseComparison } from "../components/CandidateCaseComparison";
import { ProviderAuthorization, type PaidRequest } from "../components/ProviderAuthorization";
import { PageShell } from "../components/PageShell";
import { RetrievalEvidence } from "../components/RetrievalEvidence";
import { useEffect, useRef, useState } from "react";
import { Play } from "lucide-react";
import { errorMessage, getJson, identityKey, postJson } from "../api";
import { ConclusionCard, Section, ShortId, StageStepper, Status, TruncatedText } from "../components/Primitives";
import { ExecutionMetrics, ParameterDiff, SearchSpaceTable, parameterNames, formatValue, billedCostText } from "../components/PipelineFields";
import { Drawer } from "../components/Dialog";
import { useOperation } from "../operation";
import { displayText } from "../display";
import { CaseAnswer } from "../components/CaseAnswer";
import { CaseDetails, gateNames } from "./EvaluationPage";

const rootCause = currentRoot;

export function EvolutionPage({ data }: { data: any }) {
  const operation = useOperation();
  const [paid, setPaid] = useState<PaidRequest | null>(null);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [stage, setStage] = useState<"bad" | "agent" | "candidates" | "sandbox" | "regression" | "recommendation">("bad");
  const [experiment, setExperiment] = useState<any>(data.optimization?.id ? data.optimization : null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const errorRef = useRef<HTMLParagraphElement | null>(null);
  useEffect(() => { if (error) errorRef.current?.focus(); }, [error]);
  const [searchOpen, setSearchOpen] = useState(false);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [searchSpace, setSearchSpace] = useState<any>(null);
  const [diagnosticPlan, setDiagnosticPlan] = useState<any>(null);
  const [selectedCandidate, setSelectedCandidate] = useState<any>(null), [candidateReport, setCandidateReport] = useState<any>(null);
  const [reportPage,setReportPage]=useState(1);
  useEffect(() => { setReportPage(1); setCandidateReport(null); const id = selectedCandidate?.result?.evaluation_run_id; if (!id) return; let cancelled = false; void getJson<any>(`/api/evaluations/${id}`).then(value => { if (!cancelled) setCandidateReport(value); }).catch(reason => { if (!cancelled) setError(errorMessage(reason)); }); return () => { cancelled = true; }; }, [selectedCandidate]);
  const [selectedBadCase, setSelectedBadCase] = useState<any>(null);
  const [comparisonCase,setComparisonCase]=useState<any>(null);
  const [comparisonKind,setComparisonKind]=useState<"fixed"|"regression">("regression");
  const refreshed = useRef(new Set<string>());
  const [winnerId, setWinnerId] = useState("");
  const evaluation = data.evaluation || {};
  const identity = identityKey(data.workspace || data.evaluation);
  const currentIdentity = useRef(identity); currentIdentity.current = identity;
  useEffect(() => { setExperiment(data.optimization?.id ? data.optimization : null); setSelectedCandidate(null); setCandidateReport(null); setSelectedBadCase(null); setComparisonCase(null); setWinnerId(""); setSearchOpen(false); setAdvancedOpen(false); setSearchSpace(null); setError(""); setBusy(false); }, [identity]);
  const [targetCandidate, setTargetCandidate] = useState<any>(null);
  useEffect(() => { setTargetCandidate(null); }, [identity]);
  const badCases = (data.badCases || []).filter((item: any) => item.run_id === evaluation.id);
  const candidates: any[] = experiment?.candidates || [];
  const abc = candidates.filter(candidate => ["A", "B", "C"].includes(candidate.reasoning?.candidate_label)).sort((a, b) => (a.reasoning?.round || 1) - (b.reasoning?.round || 1) || String(a.reasoning?.candidate_label).localeCompare(String(b.reasoning?.candidate_label)));
  const d = candidates.find(candidate => candidate.reasoning?.candidate_label === "D");
  const roundNumber = Math.max(1, ...(experiment?.rounds || []).map((item: any) => item.round), ...abc.map(item => item.reasoning?.round || 1));
  const currentRound = abc.filter(item => (item.reasoning?.round || 1) === roundNumber);
  const orderedCandidates = d ? [...currentRound, d] : currentRound;
  const recommendation = experiment?.recommendation?.result || experiment?.recommendation || {};
  const savedRecommended=candidates.find(item=>item.id===recommendation.recommended_candidate);
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
  const canContinue = latestRound?.complete && !confirmation && budget.used < budget.max - (budget.reserved_for_d ?? budget.reserved_for_d1 ?? 1);
  const qualified = candidates.filter(item => ["A", "B", "C"].includes(item.reasoning?.candidate_label) && item.status === "evaluated" && item.result?.qualification?.qualified);
  const selectedWinner = qualified.some(item => item.id === winnerId) ? winnerId : recommendation.suggested_winner || qualified[0]?.id || "";
  const batchId = `sandbox-round:${experiment?.id}:${roundNumber}`;
  const batchRunning = operation.operations.some(item => item.id === batchId && item.status === "running");
  const hasRunning = candidates.some(item => ["running", "queued"].includes(item.status)) || operation.operations.some(item => item.candidateId && item.status === "running") || batchRunning;
  const pending = currentRound.filter(item => item.status === "generated");
  const policyBlocked = !!evaluation.requires_policy_upgrade || !!data.workspace?.requires_policy_upgrade;
  const coverage = experiment?.coverage_plan;
  const planningIncomplete = !!coverage && coverage.status === "incomplete";
  const completePlan = () => void action("零调用补齐本轮规划", () => postJson(`/api/experiments/${experiment.id}/complete-plan`, { binding: coverage.binding }));
  const canBatch = !planningIncomplete && !policyBlocked && !!pending.length && !confirmation && !hasRunning && budget.used < budget.max - (budget.reserved_for_d ?? 1);
  const executeBatch = async () => {
    const captured = identity; setError("");
    try { await operation.runCandidateBatch({ experimentId: experiment.id, baselineId: evaluation.id, round: roundNumber, candidateIds: pending.map(item => item.id), identity: data.workspace ? identity : undefined }); await refresh(); }
    catch (reason) { if (currentIdentity.current === captured) { setError(errorMessage(reason)); await refresh(); } }
  };
  const requestPaid = (title: string, description: string, execute: () => void) => setPaid({ title, description, execute });
  const runBatch = () => requestPaid('运行本轮 A/B/C Sandbox', `Golden ${evaluation.dataset_snapshot?.question_ids?.length ?? evaluation.cases?.length ?? '未采集'} 题，待运行 ${pending.length} 个Candidate；每题回答+Judge；评测次数 ${budget.used}/${budget.max}，D预留1次。Rewrite/MultiQuery/HyDE启用时有额外模型调用。`, () => void executeBatch());
  const activeOperation = (candidateId: string) => operation.operations.find(item => item.candidateId === candidateId && item.status === "running");
  const processingCases=agentDiagnosisRows(badCases);

  const failedGates = (evaluation.result?.gates?.gates || []).filter((gate: any) => gate.status === "FAIL");
  const gateDetails = evaluation.gate_details || [];
  const snapshot = evaluation.dataset_snapshot || (() => { try { return JSON.parse(evaluation.dataset_snapshot_json || "{}"); } catch { return {}; } })();
  useEffect(() => { setDiagnosticPlan(null); }, [identity]);
  const loadDiagnosticPlan = async () => { const captured=identity; try { const plan=await getJson<any>(`/api/evaluations/${evaluation.id}/diagnostic-plan`); if(currentIdentity.current===captured)setDiagnosticPlan(plan); } catch(reason) { if(currentIdentity.current===captured)setError(errorMessage(reason)); } };
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
  const executeGenerate = async () => {
    const captured = identity;
    setBusy(true); setError("");
    try { await operation.run("生成 A/B/C 候选", () => postJson("/api/experiments/run")); await refresh(); }
    catch (reason) { if (currentIdentity.current === captured) setError(errorMessage(reason)); }
    finally { if (currentIdentity.current === captured) setBusy(false); }
  };
  const generate = () => requestPaid('生成A/B/C优化建议', '一次Agent策略分析调用；不自动执行Sandbox。', () => void executeGenerate());
  const continueRound = () => requestPaid('生成下一轮建议', '读取已保存历史实验反馈，一次Agent分析；不自动评测。', () => void action('生成下一轮A/B/C', () => postJson(`/api/experiments/${experiment.id}/continue`)));
  const run = (candidate: any) => candidate.resume_plan?.can_resume === false ? setError(candidate.resume_plan.reason || '当前断点不可续跑，请查看预检原因') : requestPaid(`${candidateName(candidate)} · Sandbox`, `Golden ${evaluation.cases?.length ?? '未采集'}题；${candidate.status === 'failed' ? '同身份续跑，仅补未完成题目或Judge；本次启动计入既有评测次数。' : '每题生成回答+Judge，可能有额外改写/检索调用。'}评测次数${budget.used}/${budget.max}，D预留1次。`, () => void executeCandidate(candidate));
  const executeCandidate = async (candidate: any) => {
    if (!["generated", "failed"].includes(candidate.status) || activeOperation(candidate.id)) return;
    const captured = identity;
    setBusy(true); setError("");
    try { await operation.startEvaluation(`Candidate ${candidate.reasoning?.candidate_label} · Sandbox`, () => postJson(`/api/candidates/${candidate.id}/run`, { authorize_provider: true }), candidate.id); await refresh(); }
    catch (reason) { if (currentIdentity.current === captured) setError(errorMessage(reason)); }
    finally { if (currentIdentity.current === captured) setBusy(false); }
  };

  const evaluatedCount = currentRound.filter(item => item.status === "evaluated").length;
  const roundComplete = !!currentRound.length && currentRound.every(item => item.status === "evaluated" && item.result?.evaluation_complete !== false);
  const recommendationTitle=!roundComplete ? currentRound.some(c=>c.status === "failed") ? "本轮实验尚未完成 · 有运行失败" : "本轮实验尚未完成" : recommendation.status==="No Qualified Candidate" ? "保存结论：本轮暂无合格候选方案" : recommendation.recommended_candidate ? savedRecommended ? `保存推荐：${candidateName(savedRecommended)}` : "已有保存推荐，候选详情未采集" : currentRound.some(item=>typeof item.result?.qualification?.qualified!=="boolean") ? "资格或推荐结论未采集" : qualified.length ? "已有合格方案，等待保存的最终决策" : "推荐结论未采集";
  const steps = [
    { label: "诊断", state: evaluation.status === "completed" ? "completed" : "blocked", detail: evaluation.status === "completed" ? `${evaluation.result?.bad_case_count ?? (badCases.length || "未采集")} 道 Bad Case 进入分析` : "等待有效 Baseline" },
    { label: "生成 A/B/C", state: planningIncomplete ? "current" : experiment?.status === "generating" ? "current" : experiment?.status === "failed" ? "blocked" : currentRound.length ? "completed" : "pending", detail: coverage ? `实际覆盖 ${coverage.covered_count}/${coverage.total} · ${planningIncomplete ? "规划未完成" : coverage.status === "complete_with_gaps" ? "存在能力缺口" : "规划已完成"}` : experiment?.status === "failed" ? "本轮方案生成失败 · 已有结果保留" : currentRound.length ? `第 ${roundNumber} 轮 · ${currentRound.length} 个候选已生成（最多3个）` : "用户启动方案生成" },
    { label: "Sandbox", state: hasRunning ? "current" : roundComplete ? "completed" : "pending", detail: `${evaluatedCount}/${currentRound.length || 3} 已评测${currentRound.some(item => item.status === "failed") ? " · 有运行失败" : ""}` },
    { label: "Gate 2", state: confirmation ? "completed" : roundComplete && qualified.length ? "current" : "pending", detail: confirmation ? "人工已确认" : "等待完整报告与合格方案" },
    { label: "Composite D（条件）", state: composite?.status === "no_effective_composite" || d?.status === "evaluated" ? "completed" : d?.status === "running" ? "current" : d?.status === "failed" ? "blocked" : "pending", detail: composite?.status === "no_effective_composite" ? "合法跳过 · 无有效组合" : d?.status === "evaluated" ? metricText(d.result, "qualification") : "等待组合判断" },
    { label: "最终推荐", state: recommendation.recommended_candidate && confirmation ? "completed" : "pending", detail: recommendation.recommended_candidate && confirmation ? candidateName(candidates.find(item => item.id === recommendation.recommended_candidate)) : "不自动发布" },
  ] as const;
  return <PageShell className="page evolution-page" header={<><div className="page-title"><div><h1>Agent 工作台</h1><p>读取问题证据，提出 A/B/C 假设，用 Sandbox 验证改善与副作用。</p></div>{planningIncomplete ? <button className="primary" disabled={busy || policyBlocked || hasRunning || !!confirmation} onClick={completePlan}>补齐本轮规划（不收费）</button> : pending.length ? <button className="primary" disabled={busy || !canBatch} onClick={() => void runBatch()}><Play size={15} />{batchRunning ? "本轮 Sandbox 运行中" : "运行本轮 A/B/C Sandbox"}</button> : <button className="primary" disabled={policyBlocked || busy || hasRunning || evaluation.status !== "completed" || (!!abc.length && !canContinue) || (!badCases.length && !experiment?.result?.monitoring_context)} onClick={() => void (canContinue ? continueRound() : generate())}><Play size={15} />{busy ? "处理中…" : canContinue ? "继续优化下一轮" : abc.length ? "本轮方案已生成" : "生成 A / B / C"}</button>}</div><StoryDisclosure label={<>实验与人工Gate进度</>}><StageStepper compact ariaLabel="Agent 实验阶段" steps={[...steps]} /></StoryDisclosure></>} tabs={<div className="tabs"><button aria-pressed={stage === "bad"} className={stage === "bad" ? "active" : ""} onClick={() => setStage("bad")}>问题诊断</button><button aria-pressed={stage === "agent"} className={stage === "agent" ? "active" : ""} onClick={() => setStage("agent")}>优化 Agent</button><button aria-pressed={stage === "candidates"} className={stage === "candidates" ? "active" : ""} onClick={() => setStage("candidates")}>A/B/C/D</button><button aria-pressed={stage === "sandbox"} className={stage === "sandbox" ? "active" : ""} onClick={() => setStage("sandbox")}>Sandbox</button><button aria-pressed={stage === "regression"} className={stage === "regression" ? "active" : ""} onClick={()=>setStage("regression")}>Regression</button><button aria-pressed={stage === "recommendation"} className={stage === "recommendation" ? "active" : ""} onClick={()=>setStage("recommendation")}>Recommendation</button></div>} resetKey={stage}>


    <ProviderAuthorization request={paid} onClose={() => setPaid(null)} />
    {policyBlocked && <p className="error-notice">当前 Baseline 评测版本身份与运行代码不兼容，真实 Agent 启动已阻断，旧实验只读。全部 Bad Case 保留在优化规划中；请先到 Baseline 查看身份预检，按原 Q18 复核与独立授权流程处理，不自动重评。</p>}
    {abc.some(item => (item.reasoning?.round || 1) < roundNumber) && <button className="text-button" onClick={() => setHistoryOpen(true)}>历史实验 · {new Set(abc.filter(item => (item.reasoning?.round || 1) < roundNumber).map(item => item.reasoning?.round || 1)).size}轮</button>}
    <Drawer className="workbench-drawer" open={historyOpen} onOpenChange={setHistoryOpen} title="历史实验 · 原方案与结果只读"><div className="drawer-body">{abc.filter(item => (item.reasoning?.round || 1) < roundNumber).map(candidate => <section key={candidate.id}><h3>第{candidate.reasoning?.round || 1}轮 · {candidateName(candidate)}</h3><p>{candidate.reasoning?.hypothesis}</p><ConfigDiff base={evaluation.config || {}} candidate={candidate} /><p>{metricText(candidate.result, 'qualification')} · {candidate.result?.regression?.status || '未运行'}</p><button className="text-button" onClick={() => { setHistoryOpen(false); setSelectedCandidate(candidate); }}>查看当时完整报告</button></section>)}</div></Drawer>
    {error && <p ref={errorRef} tabIndex={-1} className="error-notice" role="alert">{error}</p>}
    {experiment?.result?.diagnostic_tasks?.length>0 && <StoryDisclosure label="高级详情 · 逐题实验约束与补证预检"><button className="secondary" onClick={() => void loadDiagnosticPlan()}>批量补证预检（不收费）</button>{diagnosticPlan && <p>本次范围 {diagnosticPlan.results?.length} 题 · Provider 调用 {diagnosticPlan.provider_calls}。真实执行另行统一授权。</p>}<pre className="technical-record">{JSON.stringify(experiment.result.diagnostic_tasks,null,2)}</pre></StoryDisclosure>}
    {experiment?.result?.generation_status==='no_candidates' && <p className="workbench-status" role="status">本轮没有合法候选，不能运行 Sandbox；未生成不代表优化成功。</p>}
    {experiment?.result?.rejected_candidates?.length>0 && <><p className="workbench-status">本轮保留 {currentRound.length} 个合法候选，拒绝 {experiment.result.rejected_candidates.length} 个候选；拒绝项不会进入 Sandbox。</p><StoryDisclosure label="被拒绝候选与校验依据"><pre className="technical-record">{JSON.stringify(experiment.result.rejected_candidates,null,2)}</pre></StoryDisclosure></>}
    {experiment?.result?.generation_status==='insufficient_evidence' && <p className="workbench-status" role="status">候选依据不足：{experiment.result.insufficient_evidence || '暂无足够依据生成合格优化假设；待核实原始证据，不补造A/B/C。'}</p>}
    {data.workspace?.baseline_unavailable_reason && <p className="error-notice">{data.workspace.baseline_unavailable_reason}</p>}
    <p className="agent-identity">{evaluation.id ? <>当前 Baseline：<ShortId value={evaluation.id} /> · {evaluation.result?.gates?.passed === true ? `群组Gate通过（${evaluation.result.gates.passed_count}/${evaluation.result.gates.total}）` : `${failedGates.length} 项 Gate 待改善`} · Bad Case {processingCases.length} 题 · 全部进入 Agent 诊断与优化规划</> : "当前有效 Baseline 尚未就绪。"}</p>
    {experiment?.result?.processing_progress && <p className="workbench-status">已验证配置 {experiment.result.processing_progress.verified_configuration_id || "尚无"} · 修复 {experiment.result.processing_progress.fixed_question_ids.length} 题 · 待处理 {experiment.result.processing_progress.remaining_question_ids.length} 题。不同候选的修复不相加，组合须重新完整评测。</p>}
    {stage === "bad" && <Section title="本轮 Bad Case"><p>本轮 {processingCases.length} 道 Bad Case。全部业务失败由 Agent 接手，逐题分析原因、提出优化假设，再用真实 Sandbox 验证；根因未知不会排除问题。</p><DiagnosisTable business evidence rows={processingCases} onSelect={setSelectedBadCase} strategy={row=><><TruncatedText lines={2}>{savedDirections(row)}</TruncatedText><button className="text-button" onClick={()=>{setStage('agent');}}>进入优化规划</button>{currentRound.filter(c=>targetRows(c,[row]).length).map(c=><button className="text-button" key={c.id} onClick={()=>setTargetCandidate(c)}>{candidateName(c)} · 查看目标</button>)}</>} /></Section>}

    {stage === "agent" && <>
      <ConclusionCard title={currentRound.length ? `${coverage?.covered_count ?? processingCases.filter((row:any)=>currentRound.some(c=>targetRows(c,[row]).length)).length}/${processingCases.length} 道有实际方案，${currentRound.length} 个候选` : `${processingCases.length} 道 Bad Case，等待生成优化假设`} tone="neutral">同一问题可以对应不同干预假设。下方从实际问题证据连接到候选方案的参数变化；预期收益须由 Sandbox 验证，不能代替结果。</ConclusionCard>
      <Section title="问题与策略关联" action={<button className="text-button" onClick={() => setSearchOpen(true)}>Search Space{searchSpace?.search_space && ` · ${Object.keys(searchSpace.search_space).length}`}</button>}>
        <div className="strategy-relations strategy-map">{processingCases.map(row=>{
          const linked=currentRound.filter(candidate=>targetRows(candidate,[row]).length);
          return <article className="strategy-branch" key={row.id || row.question_id}><div className="strategy-source"><span className="field-label">{questionLabel(row.question_id)} · {rootName(rootCause(row))}</span><TruncatedText lines={2}>{caseData(row).question}</TruncatedText><TruncatedText lines={2}>{coreEvidence(row)}</TruncatedText><p>{savedDirections(row)}</p><button className="text-button" onClick={()=>setSelectedBadCase(row)}>查看问题证据</button></div><div className="strategy-hypotheses">{linked.map(candidate=><section key={candidate.id}><div className="section-head"><h3>{candidateName(candidate)}</h3><button className="text-button" onClick={()=>setSelectedCandidate(candidate)}>{candidateName(candidate)} · 详情</button></div><TruncatedText lines={3}>{businessSummary(candidate.reasoning?.hypothesis || "历史未保存假设")}</TruncatedText><CompactDiff base={evaluation.config || {}} candidate={candidate}/><div className="strategy-expectations"><TruncatedText lines={2}>预期：{businessSummary(candidate.reasoning?.expected_improvement || candidate.reasoning?.expected || "未采集")}</TruncatedText><TruncatedText lines={2}>风险：{businessSummary(candidate.reasoning?.risk || "未采集")}</TruncatedText></div></section>)}{!linked.length && <p className="muted">{coverage?.matrix?.find((m:any)=>m.question_id===row.question_id)?.gap || "尚无实际候选；点击补齐本轮规划（不收费），通过严格校验后保存。"}</p>}</div></article>;
        })}{!processingCases.length && <p>当前没有已完成的业务失败目标。</p>}{currentRound.filter(candidate=>!targetRows(candidate,badCases).length).map(candidate=><p key={candidate.id}>{candidateName(candidate)}：未匹配当前技术目标，暂不建立策略连线。<button className="text-button" onClick={()=>setSelectedCandidate(candidate)}>查看保存方案</button></p>)}</div>
        <StoryDisclosure label={<>实验运行摘要</>}><dl className="report-grid"><div><dt>当前轮次</dt><dd>第 {latestRound?.round ?? roundNumber} 轮 · {latestRound?.evaluated ?? evaluatedCount}/{latestRound?.total ?? currentRound.length}</dd></div><div><dt>完整 Sandbox</dt><dd>{evaluatedCount} / {currentRound.length || "尚无候选"}</dd></div><div><dt>评测次数</dt><dd>{budget.used} / {budget.max} · D 预留 {budget.reserved_for_d ?? 1}</dd></div></dl></StoryDisclosure>
      </Section>
    </>}
    {stage === "agent" && coverage && <Section title={`逐题实际覆盖 ${coverage.covered_count}/${coverage.total}`} action={planningIncomplete ? <button className="secondary" disabled={busy || policyBlocked || hasRunning || !!confirmation} onClick={completePlan}>补齐本轮规划（不收费）</button> : undefined}><p>{planningIncomplete ? "规划未完成；输入问题列表不代表已有方案。" : coverage.status === "complete_with_gaps" ? "已记录能力缺口，未覆盖问题仍未优化。" : "全部目标已有通过离线准入的实际候选；效果等待真实Sandbox。"}规则方案明确标注来源，原模型A及费用审计保留。</p><div className="table-scroll"><table><thead><tr><th>问题</th><th>实际候选 / 来源</th><th>实际参数与假设</th><th>验证要求 / 缺口</th></tr></thead><tbody>{coverage.matrix.map((m:any)=><tr key={m.question_id}><td>{questionLabel(m.question_id)}</td><td>{m.candidates.map((c:any)=>`${c.label} · ${c.origin === "deterministic_coverage_planner" ? "规则规划" : "已保存模型方案"}`).join("、") || "未覆盖"}</td><td>{m.candidates.map((c:any)=><div key={c.id}>{Object.entries(c.config_diff).map(([k,v])=>`${k}=${String(v)}`).join("、")}<p>{businessSummary(c.hypothesis)}</p></div>)}</td><td>{m.gap || m.validation_requirements}</td></tr>)}</tbody></table></div></Section>}

    {stage === "candidates" && <><ConclusionCard title={currentRound.length ? `第 ${roundNumber} 轮：${currentRound.length} 个候选，${evaluatedCount} 个完成评测` : "尚未生成本轮候选"} tone="neutral">每张方案卡保留目标、策略、参数变化及预期风险。已生成、运行失败与完成但不合格分别展示；完整依据进入详情。</ConclusionCard><Section title="Candidate A / B / C" action={canContinue ? <button className="secondary" disabled={busy} onClick={() => void continueRound()}>继续优化下一轮</button> : undefined}>{[roundNumber].map(round => <div key={round}><h3 className="round-heading">第 {round} 轮</h3><div className="candidate-cards">{abc.filter(item => (item.reasoning?.round || 1) === round).map(candidate => <CandidateCard key={candidate.id} candidate={candidate} baseline={evaluation.config || {}} onDetail={() => setSelectedCandidate(candidate)} running={activeOperation(candidate.id)} busy={busy || planningIncomplete || policyBlocked || hasRunning || !!confirmation} targets={targetRows(candidate, badCases)} onTargets={() => setTargetCandidate(candidate)} onRun={() => void run(candidate)} />)}</div></div>)}{!experiment && <p className="muted">需先完成真实 Baseline Evaluation 并识别 Bad Case。</p>}</Section>{(confirmation || d || composite) && <Section title="Composite D · 有效能力组合验证">{composite?.status === "no_effective_composite" ? <ConclusionCard title="保留 Gate 2 Winner" tone="warning">没有有效的 Composite D，继续采用已确认的 Candidate。</ConclusionCard> : d ? <div className="composite-decision"><section><h3>组合决策</h3><dl><div><dt>基础 Winner</dt><dd>{candidateName(candidates.find((item: any) => item.id === (d.reasoning?.winner_id || confirmation?.winner_id)))}</dd></div><div><dt>合并来源</dt><dd>{(d.reasoning?.sources || []).map((source: any) => candidateName(candidates.find((item: any) => item.id === source.candidate_id))).join("、") || "未记录"}</dd></div><div><dt>冲突检查</dt><dd>{Object.keys(d.reasoning?.conflicts || {}).length ? `${Object.keys(d.reasoning.conflicts).length} 项冲突` : "无冲突"}</dd></div></dl><h4>参数差异</h4><ConfigDiff base={evaluation.config || {}} candidate={d} /></section><section><h3>评测结果</h3><div className="d-result-grid"><div><span>Hard Gate</span><strong>{d.result?.gates ? `${d.result.gates.passed_count} / ${d.result.gates.total}` : "未运行"}</strong></div><div><span>修复 Bad Case</span><strong>{d.result?.target_bad_cases_fixed ?? "未运行"}</strong></div><div><span>Regression</span><strong>{d.result?.regression?.status || "未运行"}</strong></div><div><span>发布资格</span><strong>{d.status === "evaluated" ? metricText(d.result, "qualification") : "未判定"}</strong></div></div><ConclusionCard title={dDecision.title} tone={dDecision.tone}>{dDecision.message}</ConclusionCard><button className="text-button" onClick={() => setSelectedCandidate(d)}>查看 D 完整报告与 Decision</button>{d.status === "generated" && <CandidateAction candidate={d} running={activeOperation(d.id)} busy={busy || policyBlocked} onRun={() => void run(d)} />}</section></div> : <p className="muted">等待 Composite D 决策。</p>}</Section>}</>}
    {stage === "sandbox" && <Section title="断点与费用状态">{currentRound.filter(c=>c.result?.evaluation_complete === false).map(c=><section key={c.id}><h3>{candidateName(c)} · 已完成 {c.result?.completed ?? c.resume_plan?.completed ?? 0}/{c.result?.total ?? 50}</h3><p>下一题：{questionLabel(c.resume_plan?.next_question_id || c.result?.auto_recovery?.question_id)} · 已保存结果复用，不重复生成或评分。</p><p>{c.resume_plan?.can_resume === false ? businessSummary(c.resume_plan.reason).replace("Unknown request execution","请求执行结果未知") : "可以同身份继续；须重新确认付费授权。"}</p><p>费用：{accountingText(c.result?.request_accounting)}；未结算请求先对账。</p><button className="text-button" onClick={()=>setSelectedCandidate(c)}>查看断点与续跑预检</button></section>)}</Section>}

    {stage === "sandbox" && <Section title="Sandbox 对比" action={<button className="text-button" onClick={() => setAdvancedOpen(true)}>查看高级指标</button>}><ConclusionCard title={!roundComplete ? "本轮实验未完成，尚无最终 Winner" : "候选收益与副作用已保存，资格以正式结果为准"} tone="neutral">{currentRound.length ? currentRound.map(candidate=>candidate.status === "evaluated" ? `${candidateName(candidate)}：Hard Gate ${metricText(candidate.result,"gates")}，目标修复 ${metricText(candidate.result,"target_bad_cases_fixed")}，新增失败 ${metricText(candidate.result,"new_failures")}，净改善 ${metricText(candidate.result,"net_improvement")}，${metricText(candidate.result,"qualification")}。` : `${candidateName(candidate)}：${candidate.status === "failed" ? "运行失败，未形成完整结论" : displayText(candidate.status)}。`).join(" ") : "尚无已保存候选。方案生成后，在相同评测身份下比较原问题修复与新增失败。"}</ConclusionCard><div className="table-scroll sandbox-core-table"><table><thead><tr><th>指标</th><th>Baseline</th>{orderedCandidates.map(candidate => <th key={candidate.id}>{candidate.reasoning?.candidate_label || candidate.id.slice(-1)}</th>)}</tr></thead><tbody>{[["Hard Gate", "gates"], ["Bad Case", "bad_case_count"], [orderedCandidates.some(item => item.result?.comparison_version) ? "目标问题修复" : "修复原 Bad Case", "target_bad_cases_fixed"], ...(orderedCandidates.some(item => item.result?.comparison_version) ? [["全部原问题修复", "all_fixed_count"], ["其他问题改善", "incidental_fixes"], ["净改善", "net_improvement"]] : []), ["新增失败", "new_failures"], ["Regression", "regression"], ["正式资格", "qualification"]].map(([label, key]) => <tr key={key}><td>{label}</td><td>{["all_fixed_count", "target_bad_cases_fixed", "incidental_fixes", "net_improvement", "new_failures", "regression", "qualification"].includes(key) ? "不适用" : metricText(evaluation.result, key)}</td>{orderedCandidates.map(candidate => <td key={candidate.id}>{metricText(candidate.result, key)}</td>)}</tr>)}</tbody></table></div>{!d && <p className="muted">Composite D：{composite?.status === "no_effective_composite" ? "已跳过 · 无有效组合" : "等待 Gate 2 与组合决策"}</p>}


    </Section>}
    {stage === "regression" && <Section title="Regression · 改善与副作用"><ConclusionCard title={evaluatedCount ? `${evaluatedCount} 个候选已保存回归检查` : "尚无完整候选回归结论"} tone="neutral">{currentRound.map(candidate=>`${candidateName(candidate)}：${candidate.status === "evaluated" ? regressionText(candidate.result) + " 保存判定：" + metricText(candidate.result,"regression") : candidate.status === "failed" ? "运行失败，回归未判定。" : "等待完整实验。"}`).join(" ")} 严重新增上限为 0，普通新增上限为 1；修复目标题不能抵消新增退化。</ConclusionCard><div className="review-filters" aria-label="回归案例类型"><button aria-pressed={comparisonKind==="regression"} onClick={()=>setComparisonKind("regression")}>新增失败</button><button aria-pressed={comparisonKind==="fixed"} onClick={()=>setComparisonKind("fixed")}>原问题修复</button></div><CandidateCaseComparison candidates={currentRound} baselineId={evaluation.id} kind={comparisonKind} onCompare={setComparisonCase} onSelect={row=>setSelectedBadCase({question_id:row.question_id,result:row})} /></Section>}
    {stage === "recommendation" && <Section title="Recommendation"><ConclusionCard title={recommendationTitle} tone={qualified.length ? "good" : "neutral"}>{pending.length ? "仍有候选未运行；已完成方案的真实资格保留，不能预判剩余成绩或制造Winner。" : "候选运行状态、资格和未通过原因见下表；不凭Overall推断推荐。"}</ConclusionCard>    {stage === "recommendation" && recommendation.suggested_winner && <section className="conclusion-card"><h3>已保存的方案建议：{candidateName(candidates.find(item => item.id === recommendation.suggested_winner))}</h3><p>来自第{candidates.find(item => item.id === recommendation.suggested_winner)?.reasoning?.round || 1}轮；{roundComplete?"仍须Gate2人工确认。":"本轮实验未完成，这不是最终Winner。"}</p></section>}
    {stage === "recommendation" && composite?.status === "analyzing" && <p role="status">组合分析已预约；结果尚未确定，刷新或重复点击不会再次调用模型。</p>}
    {stage === "recommendation" && composite?.reason && <p role="status">D决策：{composite.reason}；保留已确认Winner。</p>}
    {stage === "recommendation" && composite?.suggestion && <section><h3>智能组合依据</h3><p>{composite.suggestion.explanation}</p><p>{typeof composite.suggestion.root_cause_alignment === "string" ? composite.suggestion.root_cause_alignment : "根因与组合来源详见方案详情"}</p><p>预期：{composite.suggestion.expected_improvement} · 风险：{typeof composite.suggestion.risks === "string" ? composite.suggestion.risks : "风险详见组合方案"}</p></section>}
<h3>候选方案比较</h3><div className="table-scroll recommendation-comparison"><table><thead><tr><th>方案</th><th>保存资格</th><th>关键改善</th><th>回归风险</th><th>未通过原因 / 决策依据</th></tr></thead><tbody>{orderedCandidates.map(candidate=><tr key={candidate.id}><td><button className="text-button" onClick={()=>setSelectedCandidate(candidate)}>{candidateName(candidate)}</button></td><td>{candidate.status==="evaluated"?metricText(candidate.result,"qualification"):candidate.status==="failed"?"运行失败，资格未判定":displayText(candidate.status)}</td><td>{candidate.status==="evaluated"?`目标修复 ${metricText(candidate.result,"target_bad_cases_fixed")} · 净改善 ${metricText(candidate.result,"net_improvement")}`:"尚无完整实验结果"}</td><td>{candidate.status==="evaluated"?metricText(candidate.result,"new_failures"):"未判定"}</td><td><TruncatedText lines={2}>{qualificationExplanation(candidate)}</TruncatedText><button className="text-button" onClick={()=>setSelectedCandidate(candidate)}>资格详情</button></td></tr>)}{!orderedCandidates.length && <tr><td colSpan={5}>尚无保存方案，无法形成推荐比较。</td></tr>}</tbody></table></div><h3>推荐依据与下一步</h3><p>{recommendation.why || recommendation.reason || "历史未保存最终推荐依据；不能只按Overall选择方案。"}</p><p className="muted">Recommendation 是方案建议。具备资格后仍通过既有 Gate 2 / Gate 3 与「发布」页面决策，不等于 Production 已上线。</p><a className="text-button" href="#versions">进入发布管理</a>      {!confirmation && qualified.length > 0 && abc.every(item => item.status === "evaluated" && item.result?.evaluation_complete !== false) && <div className="review-batch"><label>Gate 2 · 确认 A/B/C 报告并选择合格赢家<FilterButtons label="选择合格赢家" value={selectedWinner} onChange={setWinnerId} options={qualified.map(candidate=>({value:candidate.id,label:candidateName(candidate)}))} /></label><button className="primary" disabled={busy || policyBlocked} onClick={() => void action("确认 A/B/C 报告", () => postJson(`/api/experiments/${experiment.id}/recommendation`, { candidate_id: selectedWinner, actor: "human" }))}>确认报告与赢家</button></div>}
      {confirmation && !composite && <div className="review-batch"><span>Gate 2 已确认赢家 {candidateName(candidates.find(item => item.id === confirmation?.winner_id))}</span><button className="primary" disabled={busy || policyBlocked} onClick={() => requestPaid('生成智能组合建议', '程序先零模型调用初筛；有效来源时最多一次DeepSeek分析，保存复用。D Sandbox须另行授权。', () => void action('生成智能组合建议', () => postJson(`/api/experiments/${experiment.id}/composite`, { authorize_provider: true })))}>生成智能组合建议</button></div>}
      {composite?.status === "no_effective_composite" && <p className="muted">无有效组合，保留 Gate 2 赢家 {candidateName(candidates.find(item => item.id === confirmation?.winner_id))}。</p>}
      {composite?.status === "generated" && <p className="muted">Composite D 已生成；请到候选方案运行完整 Sandbox。若 D 失败或打平，保留 Gate 2 赢家。</p>}
</Section>}
    <Drawer className="workbench-drawer" open={!!comparisonCase} onOpenChange={open=>!open && setComparisonCase(null)} title="Regression · 前后对比"><div className="drawer-body bad-case-details">{comparisonCase && <><section className="candidate-card"><h3>业务问题与回归结论</h3><CaseAnswer text={comparisonCase.question || "历史未保存问题"}/><p>Baseline {comparisonCase.before?.passed===true?"通过":comparisonCase.before?.passed===false?"未通过":"未采集"} → Candidate {comparisonCase.after?.passed===true?"通过":comparisonCase.after?.passed===false?"未通过":"未采集"} · {comparisonCase.after?.severity==="critical"?"严重":comparisonCase.after?.severity==="ordinary"?"普通":"严重程度未采集"}</p></section><section className="candidate-card"><h3>Baseline 回答</h3><CaseAnswer text={comparisonCase.before?.model_answer || "历史未保存回答"}/><p>{coreEvidence(comparisonCase.before || {})}</p></section><section className="candidate-card"><h3>Candidate 回答</h3><CaseAnswer text={comparisonCase.after?.model_answer || "历史未保存回答"}/><p>{coreEvidence(comparisonCase.after || {})}</p></section>{[["Baseline",comparisonCase.before,comparisonCase.baseline],["Candidate",comparisonCase.after,comparisonCase.current]].map(([label,item,run])=><StoryDisclosure className="candidate-card" key={label} label={<>{label} · 证据变化与完整审计</>}><CaseDetails item={item || {}} snapshot={run?.dataset_snapshot || {}} config={run?.config || {}} gates={run?.gate_details || []}/></StoryDisclosure>)}</>}</div></Drawer>
    <Drawer className="workbench-drawer" open={advancedOpen} onOpenChange={setAdvancedOpen} title="Sandbox · 高级指标"><div className="drawer-body"><p>诊断与比较指标不替代 Hard Gate / Regression 资格判定。</p><div className="table-scroll"><table><thead><tr><th>指标</th><th>Baseline</th>{orderedCandidates.map(candidate => <th key={candidate.id}>{candidate.reasoning?.candidate_label || candidate.id}</th>)}</tr></thead><tbody>{[["Fixed Bad Case", "target_bad_cases_fixed"], ["Positive", "positive_correctness"], ["Ablation", "ablation_correctness"], ["Safety", "safe_rejection_rate"], ["Overall", "overall_score"], ["TTFT", "ttft_seconds"], ["Input Tokens", "input_tokens"], ["Output Tokens", "output_tokens"], ["Provider Cost", "token_cost"], ["Recall@K", "recall_at_k"], ["Precision@K", "precision_at_k"], ["MRR", "mrr"]].map(([label, key]) => <tr key={key}><td>{label}</td><td>{["all_fixed_count", "target_bad_cases_fixed", "incidental_fixes", "net_improvement", "new_failures", "regression", "qualification"].includes(key) ? "不适用" : metricText(evaluation.result, key)}</td>{orderedCandidates.map(candidate => <td key={candidate.id}>{metricText(candidate.result, key)}</td>)}</tr>)}</tbody></table></div><p className="muted">历史运行未保存完整计费信息，无法准确回算。</p></div></Drawer>
    <Drawer className="workbench-drawer" open={!!selectedCandidate} onOpenChange={open=>!open && setSelectedCandidate(null)} title={`${candidateName(selectedCandidate)} · 方案详情`}><div className="drawer-body story-details">{selectedCandidate && <>
      {selectedCandidate.resume_plan && <Section title="续跑预检与费用"><p>已完成 {selectedCandidate.resume_plan.completed ?? selectedCandidate.result?.completed}/{selectedCandidate.resume_plan.total ?? selectedCandidate.result?.total} · 可复用 {selectedCandidate.resume_plan.reusable ?? "待核"} 题</p><p>{selectedCandidate.resume_plan.can_resume ? `仅补 ${selectedCandidate.resume_plan.pending_answers} 次回答、${selectedCandidate.resume_plan.pending_judges} 次Judge；另计Embedding/Rerank，启动前须付费确认。` : selectedCandidate.resume_plan.reason}</p><p>费用：{accountingText(selectedCandidate.result?.request_accounting)}</p></Section>}
      <Section title="优化目标"><p>评测执行：{selectedCandidate.status === "evaluated" ? "已完成" : selectedCandidate.status === "failed" ? "运行失败" : ["running","queued"].includes(selectedCandidate.status) ? "运行中" : "未运行"} · 发布资格：{selectedCandidate.status === "evaluated" ? metricText(selectedCandidate.result,"qualification") : "未判定"} · Hard Gate：{selectedCandidate.result?.evaluation_complete === false ? "未完成" : selectedCandidate.result?.gates?.passed === true ? "通过" : selectedCandidate.result?.gates?.passed === false ? "未通过" : "未运行"}</p>{targetRows(selectedCandidate,badCases).map(row=><div key={row.id}><span className="muted">{questionLabel(row.question_id)} · {rootName(rootCause(row))}</span><p>{caseData(row).question}</p></div>)}{!targetRows(selectedCandidate,badCases).length && <p>未匹配当前技术优化目标，原始引用保留在高级审计。</p>}</Section>
      <Section title="优化假设与风险"><CandidateReasoning candidate={selectedCandidate}/></Section>
      <Section title="Config Diff · 参数差异"><ConfigDiff base={evaluation.config || {}} candidate={selectedCandidate}/></Section>
      <Section title="真实实验结果"><p>{qualificationExplanation(selectedCandidate)}</p><p>{selectedCandidate.status === "evaluated" ? regressionText(selectedCandidate.result) : "没有完整 Sandbox，回归结论未判定。"}</p><p>Regression：{metricText(selectedCandidate.result,"regression")} · 目标修复 {metricText(selectedCandidate.result,"target_bad_cases_fixed")} · 净改善 {metricText(selectedCandidate.result,"net_improvement")}</p>{selectedCandidate.result?.evaluation_complete !== false && selectedCandidate.result?.regression_interpretation && <p>{selectedCandidate.result.regression_interpretation}</p>}{selectedCandidate.result?.evaluation_complete === false ? <p>完整50题后判定修复与退化；历史部分比较保留在高级审计。</p> : <p>已修复：{(selectedCandidate.result?.all_fixed_question_ids || []).map(questionLabel).join("、") || "未采集"} · 新增失败：{(selectedCandidate.result?.new_regression_question_ids || []).map(questionLabel).join("、") || "未采集"}</p>}</Section>
      {selectedCandidate.reasoning?.candidate_label === "D" && <Section title="组合来源与冲突"><p>基础 Winner：{candidateName(candidates.find(item=>item.id === selectedCandidate.reasoning.winner_id))}</p>{(selectedCandidate.reasoning.sources || []).map((source:any)=><p key={source.candidate_id}>{candidateName(candidates.find(item=>item.id === source.candidate_id))} · {source.why_merge || "未保存合并理由"}</p>)}<p>冲突：{selectedCandidate.reasoning.conflicts ? Object.keys(selectedCandidate.reasoning.conflicts).join("、") || "无冲突" : "未采集"}</p></Section>}
      <StoryDisclosure label="用量、耗时与审计"><ExecutionMetrics metrics={candidateReport?.cases?.find((row:any)=>row.programmatic_metrics?.stages)?.programmatic_metrics || {input_tokens:selectedCandidate.result?.comparison_metrics?.input_tokens,output_tokens:selectedCandidate.result?.comparison_metrics?.output_tokens}}/></StoryDisclosure>
      <StoryDisclosure label="完整逐题报告与原始候选审计">{candidateReport?.cases?.length>50 && <div className="review-batch"><button disabled={reportPage===1} onClick={()=>setReportPage(reportPage-1)}>上一页</button><span>第 {reportPage} / {Math.ceil(candidateReport.cases.length/50)} 页</span><button disabled={reportPage*50>=candidateReport.cases.length} onClick={()=>setReportPage(reportPage+1)}>下一页</button></div>}{candidateReport?.cases?.length>0 && <div className="table-scroll"><table><thead><tr><th>问题</th><th>判定</th><th>根因</th></tr></thead><tbody>{candidateReport.cases.slice((reportPage-1)*50,reportPage*50).map((row:any)=><tr key={row.question_id}><td><TruncatedText lines={2}>{row.question}</TruncatedText></td><td>{row.passed === true ? "通过" : row.passed === false ? "未通过" : "未采集"}</td><td>{rootName(rootCause(row))}</td></tr>)}</tbody></table></div>}<pre className="technical-record">{JSON.stringify(selectedCandidate,null,2)}</pre></StoryDisclosure>
    </>}</div></Drawer>
    <Drawer className="workbench-drawer" open={!!targetCandidate} onOpenChange={open => !open && setTargetCandidate(null)} title={`${candidateName(targetCandidate)} · 目标问题`}><div className="drawer-body"><p className="muted">来自已保存目标引用，只展示当前 Baseline 中可匹配的问题。</p><DiagnosisTable business rows={targetRows(targetCandidate,badCases)} strategy={()=>targetCandidate?.reasoning?.hypothesis || '优化假设未采集'} onSelect={row=>{setTargetCandidate(null);setSelectedBadCase({...row,result:{...row.result,optimization_strategy:targetCandidate?.reasoning?.hypothesis}})}} /></div></Drawer>
    <Drawer className="workbench-drawer search-space-drawer" open={searchOpen} onOpenChange={setSearchOpen} title={`Search Space · ${searchSpace?.search_space ? Object.keys(searchSpace.search_space).length : "—"}`} ><div className="drawer-body"><p>优化 Agent 只能修改以下字段；参数类型、允许值来自后端 Validator 的同一策略。</p>{searchSpace?.search_space ? <SearchSpaceTable contract={searchSpace.search_space} baseline={evaluation.config || {}} /> : <p>{error || "正在读取 Search Space…"}</p>}</div></Drawer>
    <Drawer className="workbench-drawer" open={!!selectedBadCase} onOpenChange={open => !open && setSelectedBadCase(null)} title="Bad Case 诊断"><div className="drawer-body">{selectedBadCase && <CaseDetails item={{ ...caseData(selectedBadCase), question_id: selectedBadCase.question_id || selectedBadCase.result?.question_id, primary_root_cause: rootCause(selectedBadCase) }} snapshot={snapshot} config={evaluation.config || {}} gates={gateDetails} />}</div></Drawer>
  </PageShell>;
}

function businessSummary(value:unknown):string {
  if(typeof value!=="string" || !value)return "历史未保存说明";
  let text=value.replace(/(?:DOC-\d+-)?C-\d{5}/g,"引用证据片段").replace(/V1G-\d+-\d{2}(?:-R\d+)?/g,questionLabel);
  for(const [key,name] of Object.entries({...parameterNames,...gateNames}))text=text.replaceAll(key,name);
  return text;
}

function CandidateCard({ candidate, baseline, onDetail, targets, onTargets, running, busy, onRun }: { candidate: any; baseline: Record<string, any>; onDetail: () => void; targets: any[]; onTargets: () => void; running?: { current?: number; total?: number; stage?: string }; busy: boolean; onRun: () => void }) {
  const reasoning = candidate.reasoning || {};
  const evaluated = candidate.status === "evaluated";
  return <article className="candidate-card"><div className="candidate-card-header"><div><small>第 {reasoning.round || 1} 轮 · {evaluated ? "已完成" : candidate.status === "failed" ? "运行失败" : running || candidate.status === "running" ? "运行中" : "已生成"}</small><h3>Candidate {reasoning.candidate_label || "—"}</h3><small>{reasoning.provenance?.origin === "deterministic_coverage_planner" ? "规则规划 · 非模型原始输出" : "已保存模型方案"}</small></div><Status value={running ? "running" : evaluated && typeof candidate.result?.qualification?.qualified === "boolean" ? candidate.result.qualification.qualified ? "Qualified" : "Not Qualified" : candidate.status || "not_run"} /></div><div className="candidate-card-body">
    <div className="candidate-story-block"><span className="field-label">优化目标</span><TruncatedText lines={2}>{targets.map(row=>caseData(row).question).join("；") || "未记录可匹配的当前目标"}</TruncatedText></div>
    <div className="candidate-story-block"><span className="field-label">{reasoning.experiment_kind === "exploratory" ? "探索实验 · 根因待验证" : "优化策略"}</span><p>{optimizationDirection(reasoning.intervention_direction)}</p><TruncatedText lines={2}>{businessSummary(reasoning.hypothesis || "历史未保存策略假设")}</TruncatedText>{targets.length ? <><small>{questionLabel(targets[0].question_id)} · {symptoms(targets[0].result || {}).slice(0,1).join('、') || '现象未采集'} · {rootName(rootCause(targets[0]))}</small><button className="text-button" onClick={onTargets}>查看目标 {targets.length} 题</button></> : <p>未记录可匹配的当前目标</p>}</div>
    <div className="candidate-story-block"><span className="field-label">参数变化</span><CompactDiff base={baseline} candidate={candidate} /></div>
    <div className="candidate-story-block"><span className="field-label">预期收益</span><TruncatedText lines={2}>{businessSummary(reasoning.expected_improvement || reasoning.expected || "未采集预期改善")}</TruncatedText></div>
    <div className="candidate-story-block"><span className="field-label">潜在风险</span><TruncatedText lines={2}>{businessSummary(reasoning.risk || "尚未记录风险")}</TruncatedText></div>
    {candidate.result?.evaluation_complete === false && <p>已完成 {candidate.result.completed}/{candidate.result.total} · 可复用 {candidate.resume_plan?.reusable ?? candidate.result.completed} 题{candidate.resume_plan?.can_resume === false ? ` · ${candidate.resume_plan.reason}` : " · 继续前须重新付费确认"}</p>}
    <div className="candidate-story-block"><span className="field-label">实验结果</span>{evaluated ? <><dl className="candidate-result"><div><dt>Hard Gate</dt><dd>{metricText(candidate.result, "gates")}</dd></div><div><dt>{candidate.result?.comparison_version ? "指定目标修复" : "修复原问题"}</dt><dd>{metricText(candidate.result, "target_bad_cases_fixed")}</dd></div><div><dt>全部原问题修复</dt><dd>{Array.isArray(candidate.result?.all_fixed_question_ids) ? candidate.result.all_fixed_question_ids.length : "未采集"}</dd></div><div><dt>Regression</dt><dd>{metricText(candidate.result, "regression")}</dd></div><div><dt>正式资格</dt><dd>{metricText(candidate.result, "qualification")}</dd></div></dl><p className="muted">{regressionText(candidate.result)}</p></> : <p className={candidate.status === "failed" ? "error-notice" : "muted"}>{candidate.status === "failed" ? "Sandbox 运行未完成；断点与真实调用记录已保留。" : running || candidate.status === "running" ? "Sandbox 运行中，尚无完整资格结论。" : "Sandbox 尚未运行"}</p>}</div>
    {running && <div className="inline-progress" role="status"><strong>{running.stage || "正在评测"}</strong>{running.current != null && running.total != null && running.total > 1 && <><p>{running.current} / {running.total}</p><progress value={running.current} max={running.total} /></>}</div>}
  </div><button className="text-button" onClick={event => { event.currentTarget.focus(); onDetail(); }}>查看方案与完整报告</button><CandidateAction candidate={candidate} running={running} busy={busy} onRun={onRun} /></article>;
}

function CompactDiff({base,candidate}:{base:Record<string,any>;candidate:any}) {
  const after=candidate.config || (candidate.reasoning?.changed_parameters ? {...base,...candidate.reasoning.changed_parameters} : null);
  if(!after || !Object.keys(base).length)return <p className="muted">Baseline配置快照未采集，无法核对参数变化。</p>;
  const keys=Object.keys(parameterNames).filter(key=>key in after && key in base && after[key]!==base[key]);
  return <dl className="compact-config-diff">{keys.map(key=><div key={key}><dt>{parameterNames[key]}</dt><dd>{formatValue(base[key])} → {formatValue(after[key])}</dd></div>)}{!keys.length && <p className="muted">没有已核对的参数变化。</p>}</dl>;
}

function ConfigDiff({ base, candidate }: { base: Record<string, any>; candidate: any }) {
  const after = candidate.config || (candidate.reasoning?.changed_parameters ? { ...base, ...candidate.reasoning.changed_parameters } : null);
  if(!after || !Object.keys(base).length)return <p className="muted">历史未保存完整Baseline配置，无法核对参数Diff。</p>;
  const keys=Object.keys(parameterNames).filter(key=>key in base && key in after);
  return <div className="candidate-config-diff"><ParameterDiff before={Object.fromEntries(keys.map(key=>[key,base[key]]))} after={Object.fromEntries(keys.map(key=>[key,after[key]]))}/>{keys.length<Object.keys(parameterNames).length && <p className="muted">部分参数缺少前后记录，未纳入Diff；原始配置保留在高级审计。</p>}</div>;
}

function CandidateAction({ candidate, running, busy, onRun }: { candidate: any; running?: { current?: number; total?: number }; busy: boolean; onRun: () => void }) {
  return <div className="candidate-card-action"><button className="secondary" disabled={busy || !!running || !["generated", "failed"].includes(candidate.status)} onClick={onRun}>{running ? "Sandbox 运行中" : candidate.status === "evaluated" ? "已评测" : candidate.status === "failed" ? "继续 Sandbox" : "运行 Sandbox"}</button>{running && running.current != null && running.total != null && <span>{running.current} / {running.total}</span>}</div>;
}

const candidateName = (candidate?: any) => candidate ? `Candidate ${candidate.reasoning?.candidate_label || "—"}` : "Candidate";

function metricText(result: any, key: string) {
  if (result?.evaluation_complete === false && !["token_cost", "input_tokens", "output_tokens"].includes(key)) return key === "bad_case_count" ? "待完成" : key === "gates" ? "未完成" : "未判定";
  if (!result || !Object.keys(result).length) return "待运行";
  if (key === "all_fixed_count") return Array.isArray(result.all_fixed_question_ids) ? String(new Set(result.all_fixed_question_ids).size) : result.comparison_version ? "未采集" : result.target_bad_cases_fixed ?? "未采集";
  if (key === "new_failures") { const r = result.regression; return r && r.new_critical_failures != null && r.new_ordinary_failures != null ? `${Array.isArray(result.formal_blocking_question_ids)?"正式阻断 · ":""}严重 ${r.new_critical_failures} / 普通 ${r.new_ordinary_failures}` : "未采集"; }
  if (key === "gates") return result.gates?.passed_count!=null && result.gates?.total!=null ? `${result.gates.passed_count} / ${result.gates.total}` : "未采集";
  if (key === "regression") return result.regression ? displayText(result.regression.status || "未采集") : "未判定";
  if (key === "qualification") return typeof result.qualification?.qualified === "boolean" ? result.qualification.qualified ? "合格" : "不合格" : "未判定";
  if (key === "token_cost") return billedCostText(result.comparison_metrics);
  const value = result.comparison_metrics?.[key] ?? result.metrics?.[key] ?? result[key];
  if (["bad_case_count", "target_bad_cases_fixed", "incidental_fixes", "net_improvement", "input_tokens", "output_tokens"].includes(key) && typeof value === "number") return String(value);
  return typeof value === "number" ? value.toFixed(2) : value ?? "未采集";
}

function targetRows(candidate: any, rows: any[]): any[] {
  const ids = new Set(candidate?.reasoning?.observed_evidence || candidate?.reasoning?.target_bad_cases || []);
  return agentDiagnosisRows(rows).filter(row => ids.has(row.id) || ids.has(row.question_id));
}
function qualificationExplanation(candidate:any):string {
  if(candidate.status!=="evaluated")return candidate.status==="failed"?"运行失败；部分结果不能代表资格结论。":"实验尚未完成，不预判资格。";
  const names:Record<string,string>={hard_gates:"Hard Gate 未通过",regression:"Regression 未通过",target_bad_case_fixed:"未满足目标修复条件",total_bad_cases_reduced:"未满足失败总数减少条件"};
  const failed=Object.entries(candidate.result?.qualification?.checks || {}).filter(([,passed])=>passed===false).map(([key])=>names[key] || "其他保存的资格条件未通过");
  return failed.join("；") || (candidate.result?.qualification?.qualified===true?"保存的质量、安全与回归资格通过；正式推荐以已保存决策为准。":"历史未保存具体未通过原因。");
}

function regressionText(result: any): string {
  const r = result?.regression;
  if (!r) return "Regression 尚未运行。";
  const fixed = result.target_bad_cases_fixed;
  const counts = r.new_critical_failures != null && r.new_ordinary_failures != null ? `新增严重 ${r.new_critical_failures}、普通 ${r.new_ordinary_failures} 个失败（上限分别为 0、1）` : "新增失败明细未采集";
  const classification = Array.isArray(result.formal_blocking_question_ids) ? `；正式阻断 ${result.formal_blocking_question_ids.length} 题，资格仍按保存的 Regression 结果判定` : '';
  const continued = result.continued_failure_new_critical_question_ids || r.continued_failure_new_critical_question_ids;
  const risk = Array.isArray(continued) && continued.length ? `；持续失败题新增严重风险 ${continued.length} 题，阻断资格` : '';
  const incomplete = result.comparison_complete === false || r.comparison_complete === false ? '；评测执行未完成，比较与资格阻断' : '';
  return `${fixed == null ? "问题修复数未采集" : `修复 ${fixed} 个${result.comparison_version ? "指定目标" : "原问题（历史统计）"}`}；${counts}。${classification}${risk}${incomplete}`;
}

export function CandidateReasoning({candidate}:{candidate:any}) {
  const r=candidate.reasoning || {};
  const saved=(value:any)=>value==null || value==='' || Array.isArray(value)&&!value.length?'未保存依据':typeof value==='string'?value:JSON.stringify(value,null,2);
  return <section><h3>优化假设与提出理由</h3>{r.experiment_kind === "exploratory" && <p>探索实验 · 根因待验证。证伪条件：{r.falsification}</p>}<p>{businessSummary(r.hypothesis || "历史未保存优化假设")}</p><p>技术干预：{optimizationDirection(r.intervention_direction)}</p><TruncatedText lines={3}>预期改善：{businessSummary(r.expected_improvement || r.expected || "未采集")}</TruncatedText><TruncatedText lines={3}>潜在风险：{businessSummary(r.risk || "未采集")}</TruncatedText><StoryDisclosure label={<>完整假设与技术审计</>}><h3>技术假设与证据</h3><dl className="report-grid">{[
    ['Target Bad Case · 目标',r.target_bad_cases || r.observed_evidence],['Root Cause · 主要根因',r.root_cause ? rootName(r.root_cause) : null],['Root Cause Evidence · 根因证据引用',r.root_cause_evidence],['Hypothesis · 假设',r.hypothesis],['Why · 提出理由',r.proposal || r.why],['Intervention · 技术干预',r.intervention_direction],['Expected Improvement · 预期改善',r.expected_improvement || r.expected],['Regression Risk · 回归风险',r.risk],
  ].map(([label,value])=><div key={label}><dt>{label}</dt><dd><p className="technical-record">{label==='Why · 提出理由'?'Why：':''}{saved(value)}</p></dd></div>)}</dl>{(r.evidence_assertions || r.hypothesis_evidence) && <StoryDisclosure label={<>保存的假设证据</>}><pre className="technical-record">{saved(r.evidence_assertions || r.hypothesis_evidence)}</pre></StoryDisclosure>}{r.target_diagnosis && <StoryDisclosure label={<>保存的目标诊断原始审计</>}><pre className="technical-record">{saved(r.target_diagnosis)}</pre></StoryDisclosure>}{r.parameter_dependencies && <StoryDisclosure label={<>参数依赖依据</>}><pre className="technical-record">{saved(r.parameter_dependencies)}</pre></StoryDisclosure>}<p className="muted">以上为已保存的Agent假设与引用，干预方向仍须真实证据支持；效果等待同身份Sandbox验证。</p></StoryDisclosure></section>;
}

function accountingText(value:any):string {
  if (!value) return "历史费用未完整记录，不能按0元计算";
  const cost=value.cost_estimation;
  return `${value.call_events ?? "未采集"} 次调用记录，${value.unknown_usage_events ?? "未采集"} 次Usage未知；${cost?.status === "estimated" ? `${cost.amount} ${cost.currency}（按Usage核算，非账户实扣）` : "完整费用待账单核对"}`;
}
