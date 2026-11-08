import {EvolutionRoute, DStory, QualityComparison, alternativeReason, questionText, schemeName, storyText, StoryText, recommendationReason, dProgressLabel, ChangedParameters} from "../components/EvolutionStory";
import { savedSnapshot } from "../evaluationProgress";
import { DataTable } from "../components/DataTable";
import { PricePauseNotice, UnattendedAuthorization } from "../components/RuntimeSettings";
import { StoryDisclosure } from "../components/Storytelling";
import { FilterButtons } from "../components/Storytelling";
import './evaluation-workspaces.css';
import {DiagnosisTable, questionLabel, optimizationDirection, savedDirections, coreEvidence, caseData, currentRoot, rootName, symptoms, agentDiagnosisRows} from '../components/EvaluationDiagnosis';
import { BadCaseOverview, StrategyPresentation } from "../components/ProductDiagnostics";
import { CandidateCaseComparison } from "../components/CandidateCaseComparison";
import { PageShell } from "../components/PageShell";
import { RetrievalEvidence } from "../components/RetrievalEvidence";
import { useEffect, useRef, useState } from "react";
import { Play } from "lucide-react";
import { cachedJson, errorMessage, getJson, identityKey, postJson } from "../api";
import { Badge, ConclusionCard, MoreMenu, Section, ShortId, StageStepper, Status, TruncatedText } from "../components/Primitives";
import { ExecutionMetrics, ParameterDiff, SearchSpaceTable, parameterNames, formatValue, billedCostText } from "../components/PipelineFields";
import { Drawer } from "../components/Dialog";
import { useOperation } from "../operation";
import { displayText, narrativeText, baselineName } from "../display";
import { CaseAnswer } from "../components/CaseAnswer";
import { CaseDetails, gateNames } from "./EvaluationPage";

const rootCause = currentRoot;

export function EvolutionPage({ data }: { data: any }) {
  const operation = useOperation();
  const [historyOpen, setHistoryOpen] = useState(false);
  const [stage, setStage] = useState<"bad" | "route" | "candidates" | "sandbox" | "regression" | "recommendation">("route");
  const [experiment, setExperiment] = useState<any>(data.optimization?.id ? data.optimization : null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const errorRef = useRef<HTMLParagraphElement | null>(null);
  useEffect(() => { if (error) errorRef.current?.focus(); }, [error]);
  const [searchOpen, setSearchOpen] = useState(false);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [searchSpace, setSearchSpace] = useState<any>(null);
  const [selectedCandidate, setSelectedCandidate] = useState<any>(null), [candidateReport, setCandidateReport] = useState<any>(null);
  const [reportPage,setReportPage]=useState(1);
  const [candidateAudit, setCandidateAudit] = useState<any>(null);
  const [candidateAuditOpen, setCandidateAuditOpen] = useState(false), [candidateMetricsOpen, setCandidateMetricsOpen] = useState(false);
  useEffect(() => { setCandidateAuditOpen(false); setCandidateMetricsOpen(false); }, [selectedCandidate?.id]);
  useEffect(() => {
    setCandidateAudit(null);
    if (!selectedCandidate?.experiment_id || !candidateAuditOpen) return;
    setCandidateAudit(cachedJson<any>(`/api/experiments/${selectedCandidate.experiment_id}`)?.candidates?.find((item:any) => item.id === selectedCandidate.id) || null);
    let cancelled = false;
    void getJson<any>(`/api/experiments/${selectedCandidate.experiment_id}`).then(value => {
      if (!cancelled) setCandidateAudit(value.candidates?.find((item:any) => item.id === selectedCandidate.id));
    }).catch(reason => { if (!cancelled) setError(errorMessage(reason)); });
    return () => { cancelled = true; };
  }, [selectedCandidate?.id, candidateAuditOpen]);
  useEffect(() => { setReportPage(1); const id = selectedCandidate?.result?.evaluation_run_id; setCandidateReport(id && selectedCandidate.status==="evaluated" && (candidateAuditOpen || candidateMetricsOpen) ? cachedJson<any>(`/api/evaluations/${id}`) || null : null); if (!id || selectedCandidate.status!=="evaluated" || !candidateAuditOpen && !candidateMetricsOpen) return; let cancelled = false; void getJson<any>(`/api/evaluations/${id}`).then(value => { if (!cancelled) setCandidateReport(value); }).catch(reason => { if (!cancelled) setError(errorMessage(reason)); }); return () => { cancelled = true; }; }, [selectedCandidate, candidateAuditOpen, candidateMetricsOpen]);
  const [selectedBadCase, setSelectedBadCase] = useState<any>(null);
  useEffect(() => {
    if (!selectedBadCase?.id || selectedBadCase.details_loaded !== false) return;
    let cancelled = false;
    void getJson<any>(`/api/bad-cases/${encodeURIComponent(selectedBadCase.id)}`).then(value => {
      if (!cancelled) setSelectedBadCase({...value,result:{...value.result,optimization_strategy:selectedBadCase.result?.optimization_strategy}});
    }).catch(reason => { if (!cancelled) setError(errorMessage(reason)); });
    return () => { cancelled = true; };
  }, [selectedBadCase?.id]);
  const [comparisonCase,setComparisonCase]=useState<any>(null);
  const [comparisonKind,setComparisonKind]=useState<"fixed"|"regression">("regression");
  const refreshed = useRef(new Set<string>());
  const [winnerId, setWinnerId] = useState("");
  const evaluation = data.evaluation || {};
  const identity = identityKey(data.workspace || data.evaluation);
  const currentIdentity = useRef(identity); currentIdentity.current = identity;
  useEffect(() => { setExperiment(data.optimization?.id ? data.optimization : null); setSelectedCandidate(null); setCandidateReport(null); setSelectedBadCase(null); setComparisonCase(null); setWinnerId(""); setSearchOpen(false); setAdvancedOpen(false); setSearchSpace(null); setError(""); setBusy(false); }, [identity]);
  useEffect(() => { setExperiment(data.optimization?.id ? data.optimization : null); }, [data.optimization]);
  const [targetCandidate, setTargetCandidate] = useState<any>(null);
  useEffect(() => { setTargetCandidate(null); }, [identity]);
  const badCases = (data.badCases || []).filter((item: any) => item.run_id === evaluation.id);
  const candidates: any[] = experiment?.candidates || [];
  const abc = candidates.filter(candidate => ["A", "B", "C"].includes(candidate.reasoning?.candidate_label)).sort((a, b) => (a.reasoning?.round || 1) - (b.reasoning?.round || 1) || String(a.reasoning?.candidate_label).localeCompare(String(b.reasoning?.candidate_label)));
  const d = candidates.find(candidate => candidate.reasoning?.candidate_label === "D");
  const roundNumber = Math.max(1, ...(experiment?.rounds || []).map((item: any) => item.round), ...abc.map(item => item.reasoning?.round || 1));
  const currentRound = abc.filter(item => (item.reasoning?.round || 1) === roundNumber);
  const [roundSelection,setRoundSelection]=useState<number|null>(null);
  useEffect(()=>setRoundSelection(null),[identity]);
  const displayRound=roundSelection ?? roundNumber;
  const roundChoices=[...new Set<number>(abc.map(item=>item.reasoning?.round || 1))].sort((a,b)=>a-b);
  const displayedCandidates=abc.filter(item=>(item.reasoning?.round || 1)===displayRound);
  const recommendation = experiment?.recommendation?.result || experiment?.recommendation || {};
  const savedRecommended=candidates.find(item=>item.id===recommendation.recommended_candidate);
  const confirmation = experiment?.result?.report_confirmation || recommendation.report_confirmation;
  const composite = experiment?.result?.composite || recommendation.composite;
  const compositeSchedule = experiment?.result?.composite_schedule;
  const compositeWaiting = ["scheduled", "waiting", "queued", "running"].includes(compositeSchedule?.status) || !!compositeSchedule?.price_pause?.paused;
  const cycle = experiment?.result?.optimization_cycle;
  const pricePause = [cycle?.price_pause, experiment?.result?.price_pause, compositeSchedule?.price_pause].find(pause => pause?.paused);
  const sandboxPause = pricePause || currentRound.find(candidate => candidate.result?.price_pause?.paused)?.result.price_pause;
  const dWinner = candidates.find(item => item.id === (d?.reasoning?.winner_id || confirmation?.winner_id));
  const orderedCandidates = [...displayedCandidates,...(dWinner && !displayedCandidates.some(c=>c.id===dWinner.id) && (d || compositeWaiting) ? [dWinner] : []),...(d ? [d] : [])];
  const budget = experiment?.evaluation_budget || data.optimization?.evaluation_budget || {};
  const budgetKnown = Number.isFinite(budget.used) && Number.isFinite(budget.max);
  const diagnosisSummary = experiment?.result?.baseline_diagnosis_summary || evaluation.product_diagnostics?.baseline_diagnosis_summary || [];
  const latestRound = experiment?.rounds?.at(-1);
  const canContinue = latestRound?.complete && !confirmation && budgetKnown && budget.used <= budget.max - (budget.reserved_for_d ?? budget.reserved_for_d1 ?? 1) - 3;
  const qualified = candidates.filter(item => ["A", "B", "C"].includes(item.reasoning?.candidate_label) && item.status === "evaluated" && item.result?.qualification?.qualified);
  const selectedWinner = qualified.some(item => item.id === winnerId) ? winnerId : recommendation.suggested_winner || qualified[0]?.id || "";
  const batchId = `sandbox-round:${experiment?.id}:${roundNumber}`;
  const batchRunning = operation.operations.some(item => item.id === batchId && item.status === "running");
  const hasRunning = cycle?.status === "running" || compositeWaiting || candidates.some(item => ["running", "queued"].includes(item.status)) || operation.operations.some(item => item.candidateId && item.status === "running") || batchRunning;
  const pending = currentRound.filter(item => ["generated", "failed"].includes(item.status));
  const policyBlocked = !!evaluation.requires_policy_upgrade || !!data.workspace?.requires_policy_upgrade;
  const coverage = experiment?.coverage_plan;
  const planningIncomplete = !!coverage && coverage.status === "incomplete";
  const planningBlocked = planningIncomplete && currentRound.length < 3;
  const triedSandbox = abc.some(candidate => ["running","queued","evaluated","failed"].includes(candidate.status) || candidate.result?.evaluation_run_id);
  const uncovered = coverage?.matrix?.filter((row:any) => !row.candidates?.length) || [];
  const coverageSummary = uncovered.length ? uncovered.map((row:any) => `${questionLabel(row.question_id)} 暂时没有方案覆盖：${coverageReason(row.gap)}`).join("；") : coverage ? `全部 ${coverage.total} 道真 Bad Case 已有方案覆盖，等待评测验证` : "";
  const completePlan = () => void action("零调用补齐本轮规划", () => postJson(`/api/experiments/${experiment.id}/complete-plan`, { binding: coverage.binding }));
  const canBatch = budgetKnown && !planningBlocked && !policyBlocked && !!pending.length && !confirmation && !hasRunning && budget.used < budget.max - (budget.reserved_for_d ?? 1);
  const executeBatch = async () => {
    const captured = identity; setError("");
    try { await operation.runCandidateBatch({ experimentId: experiment.id, baselineId: evaluation.id, round: roundNumber, candidateIds: pending.map(item => item.id), identity: data.workspace ? identity : undefined }); await refresh(); }
    catch (reason) { if (currentIdentity.current === captured) { setError(errorMessage(reason)); await refresh(); } }
  };
  const requestPaid = (_title: string, _description: string, execute: () => void) => execute();
  const runBatch = () => requestPaid('运行本轮 A/B/C Sandbox', `Golden ${evaluation.dataset_snapshot?.question_ids?.length ?? evaluation.cases?.length ?? '未采集'} 题，待运行 ${pending.length} 个 Candidate；每题回答+Judge；评测次数 ${budget.used}/${budget.max}，D预留1次。Rewrite/MultiQuery/HyDE 启用时有额外模型调用。`, () => void executeBatch());
  const activeOperation = (candidateId: string) => operation.operations.find(item => item.candidateId === candidateId && item.status === "running");
  const processingCases=agentDiagnosisRows(badCases);
  const targetCases=processingCases;

  const failedGates = (evaluation.result?.gates?.gates || []).filter((gate: any) => gate.status === "FAIL");
  const gateDetails = evaluation.gate_details || [];
  const snapshot = savedSnapshot(evaluation);
  const refresh = async () => { const captured = identity; const value: any = await getJson("/api/optimization?light=true&planning=true"); if (currentIdentity.current === captured && (!value.current_baseline_id || value.current_baseline_id === evaluation.id)) setExperiment(value.id ? value : null); };
  const polling = hasRunning || experiment?.result?.optimization_cycle?.status === "running";
  useEffect(() => {
    if (!experiment?.id || !polling) return;
    let cancelled = false;
    let timer: number;
    const poll = async () => {
      try {
        const value = await getJson<any>(`/api/experiments/${experiment.id}?light=true`);
        if (cancelled) return;
        setExperiment((previous: any) => ({...previous, ...value, result:{...previous?.result,...value.result}, candidates:(value.candidates || []).map((candidate:any) => ({...previous?.candidates?.find((saved:any) => saved.id === candidate.id), ...candidate}))}));
        if (value.result?.optimization_cycle?.status === "running" || ["scheduled", "waiting", "queued", "running"].includes(value.result?.composite_schedule?.status) || value.result?.composite_schedule?.price_pause?.paused || value.candidates?.some((candidate:any) => ["running","queued"].includes(candidate.status))) timer = window.setTimeout(poll, 1000);
        else await refresh();
      } catch (reason) { if (!cancelled) { setError(errorMessage(reason)); timer = window.setTimeout(poll, 2000); } }
    };
    void poll();
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [experiment?.id, polling, identity]);

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
  const run = (candidate: any) => candidate.resume_plan?.can_resume === false ? setError(candidate.resume_plan.reason || '当前断点不可续跑，请查看预检原因') : void executeCandidate(candidate);
  const executeCandidate = async (candidate: any) => {
    if (!["generated", "failed"].includes(candidate.status) || activeOperation(candidate.id)) return;
    const captured = identity;
    setBusy(true); setError("");
    try { await operation.startEvaluation(`${candidateName(candidate)} · Sandbox 评测`, () => postJson(`/api/candidates/${candidate.id}/run`, { authorize_provider: true }), candidate.id); await refresh(); }
    catch (reason) { if (currentIdentity.current === captured) setError(errorMessage(reason)); }
    finally { if (currentIdentity.current === captured) setBusy(false); }
  };

  const evaluatedCount = currentRound.filter(item => item.status === "evaluated").length;
  const roundComplete = !!currentRound.length && currentRound.every(item => item.status === "skipped" || item.status === "evaluated" && item.result?.evaluation_complete !== false);
  const recommendationTitle=recommendation.status === "Recommended" && !recommendation.recommended_candidate ? "保存推荐：保持 Baseline" : !roundComplete ? currentRound.some(c=>c.status === "failed") ? "本轮实验尚未完成 · 有运行失败" : "本轮实验尚未完成" : recommendation.status==="No Qualified Candidate" ? "保存结论：本轮暂无合格 Candidate" : recommendation.recommended_candidate ? savedRecommended ? `保存推荐：${candidateName(savedRecommended)}` : "已有保存推荐，候选详情未采集" : currentRound.some(item=>typeof item.result?.qualification?.qualified!=="boolean") ? "资格或推荐结论未采集" : qualified.length ? "已有合格方案，等待保存的最终决策" : "推荐结论未采集";
  const activeCandidate = currentRound.find(candidate => ["running", "queued"].includes(candidate.status) || candidate.result?.price_pause?.paused);
  const steps = [
    { label: "诊断", state: evaluation.status === "completed" ? "completed" : "blocked", detail: evaluation.status === "completed" ? `${evaluation.result?.bad_case_count ?? badCases.length} 个 Bad Case 已读取` : "等待有效 Baseline", onSelect: () => setStage("bad") },
    { label: "生成 A/B/C", state: planningIncomplete && (!roundComplete || currentRound.length<3) || experiment?.status === "generating" ? "current" : experiment?.status === "failed" ? "blocked" : currentRound.length ? "completed" : "pending", detail: experiment?.status === "failed" ? "本轮方案生成失败" : planningIncomplete && (!roundComplete || currentRound.length<3) ? `${currentRound.length} 个方案 · 有覆盖缺口` : `${currentRound.length} 个 Candidate`, onSelect: () => setStage("route") },
    { label: "Candidate A/B/C/D", state: planningIncomplete && (!roundComplete || currentRound.length<3) ? "current" : currentRound.length ? "completed" : "pending", detail: `${currentRound.length} 个方案 · ${dProgressLabel(experiment)}`, onSelect: () => setStage("candidates") },
    { label: "Sandbox", state: sandboxPause || hasRunning ? "current" : currentRound.some(candidate => candidate.status === "failed") ? "blocked" : roundComplete ? "completed" : "pending", detail: activeCandidate ? `${activeCandidate.reasoning?.candidate_label} ${candidateProgress(activeCandidate, activeOperation(activeCandidate.id), sandboxPause)}` : sandboxPause ? "高峰时段暂停" : currentRound.length ? `${evaluatedCount}/${currentRound.length} 已评测` : "尚无待评测方案", onSelect: () => setStage("sandbox") },
    { label: "Regression Check", state: roundComplete ? "completed" : "pending", detail: roundComplete ? `${evaluatedCount} 个方案已保存判定` : "等待完整评测", onSelect: () => setStage("regression") },
    { label: "最终推荐", state: recommendation.recommended_candidate && confirmation ? "completed" : roundComplete ? "current" : "pending", detail: recommendation.recommended_candidate && confirmation ? schemeName(savedRecommended,recommendation.recommended_candidate) : confirmation ? "等待组合 Candidate D" : "等待完整报告与人工确认", onSelect: () => setStage("recommendation") },
  ] as const;
  return <PageShell className="page evolution-page" header={<><div className="page-title"><div><h1>Agent 工作台</h1><p>读取 Bad Case 诊断，多轮提出 A/B/C 方案并在 Sandbox 验证；出现合格 Winner 后，由 Candidate D 判断能否在 Winner 基础上融合精修。</p></div><div className="header-actions">{triedSandbox ? <button className="primary" onClick={() => setStage("sandbox")}>查看 Sandbox 进度</button> : planningBlocked ? <button className="primary" disabled={busy || policyBlocked || hasRunning || !!confirmation} onClick={completePlan}>补齐本轮规划（不收费）</button> : pending.length ? <button className="primary" disabled={busy || !canBatch} onClick={() => void runBatch()}><Play size={15} />{batchRunning ? "本轮 Sandbox 运行中" : "运行本轮 A/B/C Sandbox"}</button> : <button className="primary" disabled={policyBlocked || busy || hasRunning || evaluation.status !== "completed" || (!!abc.length && !canContinue) || (!badCases.length && !experiment?.result?.monitoring_context)} onClick={() => void (canContinue ? continueRound() : generate())}><Play size={15} />{busy ? "处理中…" : canContinue ? "继续优化下一轮" : abc.length ? "本轮方案已生成" : "生成 A / B / C"}</button>}<MoreMenu>{planningIncomplete && triedSandbox && <button role="menuitem" disabled={busy || policyBlocked || hasRunning || !!confirmation} onClick={completePlan}>补齐本轮规划（不收费）</button>}<button role="menuitem" onClick={() => setSearchOpen(true)}>查看可调参数</button><button role="menuitem" onClick={() => setHistoryOpen(true)}>查看历史实验</button>{canBatch && triedSandbox && <button role="menuitem" disabled={busy} onClick={() => void runBatch()}>运行本轮 A/B/C Sandbox</button>}</MoreMenu></div></div><section className="experiment-progress" aria-label="实验进度"><StageStepper compact ariaLabel="Agent 实验阶段" steps={[...steps]} /><p className="experiment-budget">{latestRound && <>Round {latestRound.round} · {latestRound.evaluated ?? "暂无"}/{latestRound.total ?? "暂无"} · </>}{budgetKnown ? `已评测 ${budget.used} / ${budget.max} 次（含 Candidate D）` : experiment ? "预算尚未同步，正在等待后台已用次数。" : "尚未评测；创建实验后显示预算。"}</p></section></>} tabs={<div className="tabs"><button aria-pressed={stage === "bad"} className={stage === "bad" ? "active" : ""} onClick={() => setStage("bad")}>问题诊断</button><button aria-pressed={stage === "route"} className={stage === "route" ? "active" : ""} onClick={() => setStage("route")}>进化路线</button><button aria-pressed={stage === "candidates"} className={stage === "candidates" ? "active" : ""} onClick={() => setStage("candidates")}>A/B/C/D</button><button aria-pressed={stage === "sandbox"} className={stage === "sandbox" ? "active" : ""} onClick={() => setStage("sandbox")}>Sandbox</button><button aria-pressed={stage === "regression"} className={stage === "regression" ? "active" : ""} onClick={()=>setStage("regression")}>{displayText("Regression")}</button><button aria-pressed={stage === "recommendation"} className={stage === "recommendation" ? "active" : ""} onClick={()=>setStage("recommendation")}>最终推荐</button></div>} resetKey={stage}>


    <PricePauseNotice pause={pricePause} experimentId={experiment?.id} onChanged={refresh} />
    {candidates.filter(candidate => !pricePause && candidate.result?.price_pause?.paused).map(candidate => <PricePauseNotice key={candidate.id} pause={candidate.result.price_pause} evaluationId={candidate.result.evaluation_run_id} onChanged={refresh} />)}
    {cycle?.status === "qualified" && !confirmation && <p className="workbench-status" role="status">本轮 A/B/C 已完成，等待人工确认报告与 Winner；确认后才能生成组合 Candidate D。</p>}
    {cycle?.status === "budget_exhausted" && <p className="workbench-status" role="status">优化循环已停止：已评测 {budget.used} / {budget.max} 次，剩余 {Math.max(0, budget.max - budget.used)} 次（其中 1 次留给 D）。剩余次数不足以运行完整 A/B/C；只有合格 Winner 经人工确认后才能进入 D。</p>}
    {policyBlocked && <p className="error-notice">当前 Baseline 评测版本身份与运行代码不兼容，真实 Agent 启动已阻断，旧实验只读。全部 Bad Case 保留在优化规划中；请先到 Baseline 查看身份预检，核对历史评测与当前规则的兼容性；需要新版评分时使用保存回答判分，不自动重新生成。</p>}
    <Drawer className="workbench-drawer" open={historyOpen} onOpenChange={setHistoryOpen} title="历史实验 · 原方案与结果只读"><div className="drawer-body"><div className="candidate-cards">{abc.filter(item => (item.reasoning?.round || 1) < roundNumber).map(candidate => <CandidateCard key={candidate.id} candidate={candidate} baseline={evaluation.config || {}} busy={true} onDetail={()=>{setHistoryOpen(false);setSelectedCandidate(candidate);}} targets={targetRows(candidate,badCases)} onTargets={()=>{setHistoryOpen(false);setTargetCandidate(candidate);}} onRun={()=>void run(candidate)} />)}</div></div></Drawer>
    {error && <p ref={errorRef} tabIndex={-1} className="error-notice" role="alert">{error}</p>}

    {experiment?.result?.generation_status==='no_candidates' && <p className="workbench-status" role="status">本轮没有合法候选，不能运行 Sandbox；未生成不代表优化成功。</p>}
    {experiment?.result?.rejected_candidates?.length>0 && <><p className="workbench-status">本轮保留 {currentRound.length} 个合法候选，拒绝 {experiment.result.rejected_candidates.length} 个候选；拒绝项不会进入 Sandbox。</p></>}
    {experiment?.result?.generation_status==='insufficient_evidence' && <p className="workbench-status" role="status">候选依据不足：{experiment.result.insufficient_evidence || '暂无足够依据生成合格优化假设；待核实原始证据，不补造A/B/C。'}</p>}
    {data.workspace?.baseline_unavailable_reason && <p className="error-notice">{data.workspace.baseline_unavailable_reason}</p>}
    <p className={`agent-identity ${stage!=="bad" ? "sr-only" : ""}`}>{evaluation.id ? <>当前 Baseline：{baselineName(evaluation)} · {evaluation.result?.gates?.passed === true ? `Hard Gate 通过（${evaluation.result.gates.passed_count}/${evaluation.result.gates.total}）` : `${failedGates.length} 项 Hard Gate 待改善`} · Bad Case {processingCases.length} 题 · Bad Case 进入 Agent 优化</> : "当前有效 Baseline 尚未就绪。"}</p>

    {stage === "bad" && !savedRecommended && experiment?.result?.processing_progress && <p className="workbench-status">{experiment.result.processing_progress.verified_configuration_id ? "已有经完整评测验证的方案" : "尚无经完整评测验证的方案"} · 修复 {experiment.result.processing_progress.fixed_question_ids.length} 题 · 待处理 {experiment.result.processing_progress.remaining_question_ids.length} 题。不同候选的修复不相加，组合须重新完整评测。</p>}
    {stage === "bad" && <Section title="本轮 Bad Case"><p>本轮 {processingCases.length} 个 Bad Case，{evaluation.product_diagnostics?.review_summary?.target_count ?? targetCases.length} 道作为优化目标。</p><BadCaseOverview rows={processingCases} categories={evaluation.diagnostic_categories} priorities={evaluation.product_diagnostics?.optimization_priorities} latencyGates={evaluation.result?.gates?.gates} onSelect={setSelectedBadCase} /></Section>}

    {stage === "route" && <EvolutionRoute evaluation={evaluation} experiment={experiment} badCases={badCases} onDetail={setSelectedCandidate}>
    <>
      <Section title="无人值守设置"><UnattendedAuthorization /></Section>
      <Section title="Agent 读到了什么事实"><p>{targetCases.length} 个 Bad Case · {coverage ? `${coverage.covered_count}/${coverage.total} 道已有方案覆盖` : "覆盖明细暂无"}。{planningIncomplete && "规划未完成，需补齐覆盖缺口。"}</p>
        <div className="agent-facts">{targetCases.map(row => <article className="agent-fact" key={row.id || row.question_id}><h3>{questionLabel(row.question_id)} · {caseData(row).diagnostic_view?.diagnosis_category || "分类暂无"}</h3><TruncatedText>{caseData(row).question}</TruncatedText><TruncatedText lines={4}>{coreEvidence(row)}</TruncatedText><TruncatedText lines={3}>{savedDirections(row)}</TruncatedText><button className="text-button" onClick={() => setSelectedBadCase(row)}>查看问题证据</button></article>)}</div>
        <StoryDisclosure label="基线诊断摘要">{diagnosisSummary.length ? <div className="table-scroll product-table"><DataTable><thead><tr><th>维度</th><th>基线值</th><th>目标值</th><th>差距</th><th>相关问题</th></tr></thead><tbody>{diagnosisSummary.map((item:any,index:number)=><tr key={index}><td>{item.dimension_label || "暂无"}</td><td>{String(item.baseline_value ?? "暂无")}</td><td>{String(item.target_value ?? "暂无")}</td><td>{String(item.gap ?? "暂无")}</td><td>{item.root_causes?.map((cause:any)=>`${cause.diagnosis_category}：${(cause.question_ids || []).map(questionLabel).join("、")}`).join("；") || "暂无"}{item.root_cause_note && <p>{businessSummary(item.root_cause_note)}</p>}</td></tr>)}</tbody></DataTable></div> : <p className="muted">暂无基线诊断摘要。</p>}</StoryDisclosure>
      </Section>
      <Section title="Agent 提出了什么假设" action={<button className="text-button" onClick={() => setSearchOpen(true)}>可调参数{searchSpace?.search_space && ` · ${Object.keys(searchSpace.search_space).length}`}</button>}>
        <div className="strategy-hypotheses agent-hypotheses">{currentRound.map(candidate => <section key={candidate.id}><h3>{candidateName(candidate)}</h3><TruncatedText lines={3}>{candidate.reasoning?.hypothesis || candidate.reasoning?.core_idea || "暂无"}</TruncatedText><p className="muted">问题与策略关联：{targetRows(candidate,badCases).map(row => questionLabel(row.question_id)).join("、") || "暂无"}</p><button className="text-button" onClick={() => setSelectedCandidate(candidate)}>{candidateName(candidate)} · 详情</button></section>)}</div>{!currentRound.length && <p>暂无优化假设，生成方案后显示。</p>}
      </Section>
      <Section title="Agent 得出了哪些方案"><div className="candidate-cards">{currentRound.map(candidate => <CandidateCard key={candidate.id} candidate={candidate} baseline={evaluation.config || {}} onDetail={() => setSelectedCandidate(candidate)} onSkip={() => void action("跳过未运行方案",()=>postJson(`/api/candidates/${candidate.id}/skip`,{actor:"当前用户"}))} running={activeOperation(candidate.id)} busy={busy || planningBlocked || policyBlocked || hasRunning || !!confirmation} targets={targetRows(candidate,badCases)} onTargets={() => setTargetCandidate(candidate)} onRun={() => void run(candidate)} />)}</div>{!currentRound.length && <p>暂无已保存方案。</p>}</Section>
    </>
    {coverage && <Section title={`逐题实际覆盖 ${coverage.covered_count}/${coverage.total}`} ><p>{coverageSummary}。</p><div className="table-scroll"><DataTable><thead><tr><th>问题</th><th>实际候选 / 来源</th><th>实际参数与假设</th><th>验证要求 / 缺口</th></tr></thead><tbody>{coverage.matrix.map((m:any)=><tr key={m.question_id}><td>{questionLabel(m.question_id)}</td><td>{m.candidates.map((c:any)=>`${c.label} · ${c.origin === "deterministic_coverage_planner" ? "规则规划" : "已保存模型方案"}`).join("、") || "未覆盖"}</td><td>{m.candidates.map((c:any)=><div key={c.id}>{Object.entries(c.config_diff).map(([k,v])=>`${parameterNames[k] || displayText(k)}：${formatValue(v)}`).join("、")}<p>{c.hypothesis}</p></div>)}</td><td>{m.gap ? coverageReason(m.gap) : m.validation_requirements}</td></tr>)}</tbody></DataTable></div></Section>}

    </EvolutionRoute>}

    {["candidates","sandbox","regression"].includes(stage) && <div className="story-round-switch" role="group" aria-label="查看轮次"><span>查看轮次</span>{roundChoices.map(round=><button className="secondary" key={round} aria-pressed={displayRound===round} onClick={()=>setRoundSelection(round)}>Round {round}</button>)}</div>}
    {stage === "candidates" && <><Section title="Candidate A / B / C" action={canContinue ? <button className="secondary" disabled={busy} onClick={() => void continueRound()}>继续优化下一轮</button> : undefined}>{[displayRound].map(round => <div key={round}><p className="round-heading">Round {round} · {displayedCandidates.length} 个候选 · {displayedCandidates.filter(c=>c.status==="evaluated").length} 个完成评测</p><div className="candidate-cards">{abc.filter(item => (item.reasoning?.round || 1) === round).map(candidate => <CandidateCard key={candidate.id} candidate={candidate} baseline={evaluation.config || {}} onDetail={() => setSelectedCandidate(candidate)} onSkip={() => void action("跳过未运行方案",()=>postJson(`/api/candidates/${candidate.id}/skip`,{actor:"当前用户"}))} running={activeOperation(candidate.id)} busy={busy || planningBlocked || policyBlocked || hasRunning || !!confirmation} targets={targetRows(candidate, badCases)} onTargets={() => setTargetCandidate(candidate)} onRun={() => void run(candidate)} />)}</div></div>)}{!experiment && <p className="muted">需先完成真实 Baseline Evaluation 并识别 Bad Case。</p>}</Section>{(confirmation || d || composite || compositeWaiting) && <Section title="Candidate D · 融合决策"><DStory experiment={experiment} evaluation={evaluation} badCases={badCases}/>{d && <><button className="text-button" onClick={()=>setSelectedCandidate(d)}>查看 D 完整报告</button><CandidateAction candidate={d} running={activeOperation(d.id)} busy={busy || policyBlocked || hasRunning} onRun={()=>void run(d)}/></>}</Section>}</>}

    {stage === "sandbox" && <Section title="Sandbox 对比" action={<button className="text-button" onClick={() => setAdvancedOpen(true)}>查看高级指标</button>}><ConclusionCard title={!roundComplete ? "本轮实验未完成，尚无最终 Winner" : "候选收益与副作用已保存，资格以正式结果为准"} tone="neutral">比较同一题卷的修复、退化和 Hard Gate；完整评测后显示正式资格。</ConclusionCard><div className="table-scroll sandbox-core-table"><DataTable><thead><tr><th>指标</th><th>Baseline</th>{orderedCandidates.map(candidate => <th key={candidate.id}>{schemeName(candidate)}{candidate.id===dWinner?.id && d ? " · Winner" : ""}</th>)}</tr></thead><tbody><tr><td>运行状态</td><td>{displayText(evaluation.status || "暂无")}</td>{orderedCandidates.map(candidate => <td key={candidate.id}>{candidateProgress(candidate, activeOperation(candidate.id), sandboxPause)}</td>)}</tr>{[["Hard Gate", "gates"], ["Bad Case", "bad_case_count"], [orderedCandidates.some(item => item.result?.comparison_version) ? "目标问题修复" : "修复原 Bad Case", "target_bad_cases_fixed"], ...(orderedCandidates.some(item => item.result?.comparison_version) ? [["全部原问题修复", "all_fixed_count"], ["其他问题改善", "incidental_fixes"], ["净改善", "net_improvement"]] : []), ["新增失败", "new_failures"], [displayText("Regression"), "regression"], ["候选合格", "qualification"], ["可发布", "release_qualification"]].map(([label, key]) => <tr key={key}><td>{label}</td><td>{["all_fixed_count", "target_bad_cases_fixed", "incidental_fixes", "net_improvement", "new_failures", "regression", "qualification", "release_qualification"].includes(key) ? "不适用" : metricText(evaluation.result, key)}</td>{orderedCandidates.map(candidate => <td key={candidate.id}>{candidate.result?.price_pause?.paused || sandboxPause && ["running","queued"].includes(candidate.status) || ["running","queued"].includes(candidate.status) ? candidateProgress(candidate, activeOperation(candidate.id), sandboxPause) : metricText(candidate.result, key)}</td>)}</tr>)}</tbody></DataTable></div>{!d && <p className="muted">组合 Candidate D：{compositeWaiting ? "已排队，等待平价时段" : composite?.status === "no_effective_composite" ? "已跳过 · 无有效组合" : "等待 人工确认 与组合决策"}</p>}


    </Section>}
    {stage === "regression" && <Section title={`${displayText("Regression")} · 改善与副作用`}>{(d || compositeWaiting) && dWinner && <><h3>Winner 与 Candidate D</h3><QualityComparison baseline={dWinner} baselineLabel={`Winner · ${schemeName(dWinner)}`} candidate={d} candidateLabel="Candidate D"/></>}<h3>方案 Regression Check</h3><div className="table-scroll regression-summary-table"><DataTable><thead><tr>{["方案","修好","新增严重","新增普通","上限","Regression 判定","最终资格"].map(label=><th key={label}>{label}</th>)}</tr></thead><tbody>{orderedCandidates.map(candidate=>{const review=candidate.result?.regression_review;return <tr key={candidate.id}><td>Round {candidate.reasoning?.round || dWinner?.reasoning?.round || displayRound} · Candidate {candidate.reasoning?.candidate_label || "—"}</td><td>{review?.fixed_count ?? "未采集"}</td><td>{review?.new_critical_failures ?? "未采集"}</td><td>{review?.new_ordinary_failures ?? "未采集"}</td><td>严重 0 / 普通 1</td><td>{candidate.status==="evaluated" ? displayText(review?.status || "NOT_EVALUABLE") : "未判定"}</td><td>{candidate.result?.release_qualification?.qualified===true ? "合格" : candidate.result?.release_qualification?.qualified===false ? "不合格" : "未判定"}</td></tr>})}{!orderedCandidates.length && <tr><td colSpan={7}>尚无候选 Regression 结论</td></tr>}</tbody></DataTable></div><p>严重新增上限 0、普通新增上限 1；修好的题不能抵消新增的 Bad Case</p><div className="review-filters" aria-label="Regression 案例类型"><button aria-pressed={comparisonKind==="regression"} onClick={()=>setComparisonKind("regression")}>新增失败</button><button aria-pressed={comparisonKind==="fixed"} onClick={()=>setComparisonKind("fixed")}>原问题修复</button></div><CandidateCaseComparison candidates={orderedCandidates} baselineId={evaluation.id} kind={comparisonKind} onCompare={setComparisonCase} onSelect={row=>setSelectedBadCase({question_id:row.question_id,result:row})} /></Section>}
    {stage === "recommendation" && <Section title="最终推荐"><h3>{savedRecommended ? schemeName(savedRecommended) : recommendationTitle}</h3><QualityComparison baseline={evaluation} candidate={savedRecommended}/><h3>为什么选它</h3><p><StoryText value={recommendationReason(experiment)} evaluation={evaluation} badCases={badCases}/></p><h3>其他方案为什么没选</h3><div className="story-alternatives">{candidates.filter(c=>c.id!==savedRecommended?.id).map(candidate=><div key={candidate.id}><button className="text-button" onClick={()=>setSelectedCandidate(candidate)}>{schemeName(candidate)}</button><TruncatedText lines={3}>{alternativeReason(candidate,savedRecommended)}</TruncatedText>{[...new Set<string>([...(candidate.result?.all_fixed_question_ids || []), ...(candidate.result?.new_regression_question_ids || [])])].map(id => <TruncatedText key={id} lines={2}>{questionText(id,evaluation,badCases)}</TruncatedText>)}</div>)}</div>{confirmation && <p>人工报告确认已完成。</p>}{confirmation && !composite && !compositeWaiting && <button className="secondary" disabled={busy || policyBlocked} onClick={()=>requestPaid("生成智能组合建议","在 Winner 基础上融合",()=>void action("生成智能组合建议",()=>postJson(`/api/experiments/${experiment.id}/composite`,{authorize_provider:true})))}>生成智能组合建议</button>}<a className="primary" href="#versions">{savedRecommended?.release_state?.human_release ? "查看发布记录" : "去发布"}</a>
{!confirmation && qualified.length > 0 && abc.every(item => item.status === "skipped" || item.status === "evaluated" && item.result?.evaluation_complete !== false) && <div className="review-batch"><label>人工确认 · 确认 A/B/C 报告并选择合格 Winner<FilterButtons label="选择合格 Winner" value={selectedWinner} onChange={setWinnerId} options={qualified.map(candidate=>({value:candidate.id,label:candidateName(candidate)}))} /></label><button className="primary" disabled={busy || policyBlocked} onClick={() => void action("确认 A/B/C 报告", () => postJson(`/api/experiments/${experiment.id}/recommendation`, { candidate_id: selectedWinner, actor: "human" }))}>确认报告与 Winner</button></div>}
</Section>}
    <Drawer className="workbench-drawer" open={!!comparisonCase} onOpenChange={open=>!open && setComparisonCase(null)} title="Regression Check · 前后对比"><div className="drawer-body bad-case-details">{comparisonCase && <><section className="candidate-card"><h3>业务问题与 Regression 结论</h3><CaseAnswer text={comparisonCase.question || "历史未保存问题"}/><p>Baseline {comparisonCase.before?.passed===true?"通过":comparisonCase.before?.passed===false?"未通过":"未采集"} → Candidate {comparisonCase.after?.passed===true?"通过":comparisonCase.after?.passed===false?"未通过":"未采集"} · {comparisonCase.after?.severity==="critical"?"严重":comparisonCase.after?.severity==="ordinary"?"普通":"严重程度未采集"}</p></section><section className="candidate-card"><h3>Baseline 回答</h3><CaseAnswer text={comparisonCase.before?.model_answer || "历史未保存回答"} final={comparisonCase.before?.programmatic_metrics?.retrieval_trace?.final ?? comparisonCase.before?.retrieved_chunks ?? []}/><p>{coreEvidence(comparisonCase.before || {})}</p></section><section className="candidate-card"><h3>Candidate 回答</h3><CaseAnswer text={comparisonCase.after?.model_answer || "历史未保存回答"} final={comparisonCase.after?.programmatic_metrics?.retrieval_trace?.final ?? comparisonCase.after?.retrieved_chunks ?? []}/><p>{coreEvidence(comparisonCase.after || {})}</p></section>{[["Baseline",comparisonCase.before,comparisonCase.baseline],["Candidate",comparisonCase.after,comparisonCase.current]].map(([label,item,run])=><StoryDisclosure className="candidate-card" key={label} label={<>{label} · 证据变化与完整审计</>}><CaseDetails item={item || {}} snapshot={run?.dataset_snapshot || {}} config={run?.config || {}} gates={run?.gate_details || []}/></StoryDisclosure>)}</>}</div></Drawer>
    <Drawer className="workbench-drawer" open={advancedOpen} onOpenChange={setAdvancedOpen} title="Sandbox · 高级指标"><div className="drawer-body"><p>诊断与比较指标不替代 Hard Gate / Regression Check 资格判定。</p><div className="table-scroll"><DataTable><thead><tr><th>指标</th><th>Baseline</th>{orderedCandidates.map(candidate => <th key={candidate.id}>{candidate.reasoning?.candidate_label || candidate.id}</th>)}</tr></thead><tbody>{[["Fixed Bad Case", "target_bad_cases_fixed"], ["Positive", "positive_correctness"], ["Ablation", "ablation_correctness"], ["Safety", "safe_rejection_rate"], ["综合分", "overall_score"], ["TTFT", "ttft_seconds"], ["Input Tokens", "input_tokens"], ["Output Tokens", "output_tokens"], ["Provider Cost", "token_cost"], ["Recall@K", "recall_at_k"], ["Precision@K", "precision_at_k"], ["MRR", "mrr"]].map(([label, key]) => <tr key={key}><td>{label}</td><td>{["all_fixed_count", "target_bad_cases_fixed", "incidental_fixes", "net_improvement", "new_failures", "regression", "qualification", "release_qualification"].includes(key) ? "不适用" : metricText(evaluation.result, key)}</td>{orderedCandidates.map(candidate => <td key={candidate.id}>{metricText(candidate.result, key)}</td>)}</tr>)}</tbody></DataTable></div><p className="muted">历史运行未保存完整计费信息，无法准确回算。</p></div></Drawer>
    <Drawer className="workbench-drawer" open={!!selectedCandidate} onOpenChange={open=>!open && setSelectedCandidate(null)} title={`${candidateName(selectedCandidate)} · 方案详情`}><div className="drawer-body story-details">{selectedCandidate && <>
      {selectedCandidate.resume_plan && <Section title="续跑预检与费用"><p>已完成 {selectedCandidate.resume_plan.completed ?? selectedCandidate.result?.completed}/{selectedCandidate.resume_plan.total ?? selectedCandidate.result?.total} · 可复用 {selectedCandidate.resume_plan.reusable ?? "待核"} 题</p><p>{selectedCandidate.resume_plan.can_resume ? `仅补 ${selectedCandidate.resume_plan.pending_answers} 次回答、${selectedCandidate.resume_plan.pending_judges} 次Judge；另计Embedding/Rerank，启动前须付费确认。` : selectedCandidate.resume_plan.reason}</p><p>费用：{accountingText(selectedCandidate.result?.request_accounting)}</p></Section>}
      <Section title="优化目标"><p>评测执行：{selectedCandidate.status === "evaluated" ? "已完成" : selectedCandidate.status === "failed" ? "运行失败" : ["running","queued"].includes(selectedCandidate.status) ? "运行中" : "未运行"} · 候选资格：{selectedCandidate.status === "evaluated" ? metricText(selectedCandidate.result,"qualification") : "未判定"} · 发布资格：{selectedCandidate.status === "evaluated" ? metricText(selectedCandidate.result,"release_qualification") : "未判定"} · Hard Gate：{selectedCandidate.result?.evaluation_complete === false ? "未完成" : selectedCandidate.result?.gates?.passed === true ? "通过" : selectedCandidate.result?.gates?.passed === false ? "未通过" : "未运行"}</p>{targetRows(selectedCandidate,badCases).map(row=><div key={row.id}><span className="muted">{questionLabel(row.question_id)} · {caseData(row).diagnostic_view?.diagnosis_category || "分类未知"}</span><p>{caseData(row).question}</p></div>)}{!targetRows(selectedCandidate,badCases).length && <p>未匹配当前技术优化目标，原始引用保留在高级审计。</p>}</Section>
      <Section title="方案内容"><StrategyPresentation reasoning={selectedCandidate.reasoning}/></Section>
      <Section title="Config Diff · 参数差异"><ConfigDiff base={evaluation.config || {}} candidate={selectedCandidate}/></Section>
      <Section title="真实实验结果"><p>{qualificationExplanation(selectedCandidate)}</p><p>{selectedCandidate.status === "evaluated" ? regressionText(selectedCandidate.result) : "没有完整 Sandbox，Regression 结论未判定。"}</p><p>Regression Check：{metricText(selectedCandidate.result,"regression")} · 目标修复 {metricText(selectedCandidate.result,"target_bad_cases_fixed")} · 净改善 {metricText(selectedCandidate.result,"net_improvement")}</p>{selectedCandidate.result?.evaluation_complete !== false && selectedCandidate.result?.regression_interpretation && <p>{selectedCandidate.result.regression_review ? "严重新增上限 0、普通新增上限 1；修好的题不能抵消新增的 Bad Case" : selectedCandidate.result.regression_interpretation}</p>}{selectedCandidate.result?.evaluation_complete === false ? <p>完整50题后判定修复与退化；历史部分比较保留在高级审计。</p> : <p>已修复：{(selectedCandidate.result?.all_fixed_question_ids || []).map(questionLabel).join("、") || "未采集"} · 新增失败：{(selectedCandidate.result?.new_regression_question_ids || []).map(questionLabel).join("、") || "未采集"}</p>}</Section>
      {selectedCandidate.reasoning?.candidate_label === "D" && <Section title="组合来源与冲突"><p>基础 Winner：{candidateName(candidates.find(item=>item.id === selectedCandidate.reasoning.winner_id))}</p>{(selectedCandidate.reasoning.sources || []).map((source:any)=><p key={source.candidate_id}>{candidateName(candidates.find(item=>item.id === source.candidate_id))} · {source.why_merge || "未保存合并理由"}</p>)}<p>冲突：{selectedCandidate.reasoning.conflicts ? Object.keys(selectedCandidate.reasoning.conflicts).join("、") || "无冲突" : "未采集"}</p></Section>}
      <StoryDisclosure key={`metrics:${selectedCandidate.id}`} label="用量、耗时与审计" onToggle={event=>setCandidateMetricsOpen(event.currentTarget.open)}><ExecutionMetrics metrics={candidateReport?.cases?.find((row:any)=>row.programmatic_metrics?.stages)?.programmatic_metrics || {input_tokens:selectedCandidate.result?.comparison_metrics?.input_tokens,output_tokens:selectedCandidate.result?.comparison_metrics?.output_tokens}}/></StoryDisclosure>
      <StoryDisclosure key={`audit:${selectedCandidate.id}`} label="完整逐题报告与原始候选审计" onToggle={event=>setCandidateAuditOpen(event.currentTarget.open)}>{candidateReport?.cases?.length>50 && <div className="review-batch"><button disabled={reportPage===1} onClick={()=>setReportPage(reportPage-1)}>上一页</button><span>第 {reportPage} / {Math.ceil(candidateReport.cases.length/50)} 页</span><button disabled={reportPage*50>=candidateReport.cases.length} onClick={()=>setReportPage(reportPage+1)}>下一页</button></div>}{candidateReport?.cases?.length>0 && <div className="table-scroll"><DataTable><thead><tr><th>问题</th><th>判定</th><th>根因</th></tr></thead><tbody>{candidateReport.cases.slice((reportPage-1)*50,reportPage*50).map((row:any)=><tr key={row.question_id}><td><TruncatedText lines={2}>{row.question}</TruncatedText></td><td>{row.passed === true ? "通过" : row.passed === false ? "未通过" : "未采集"}</td><td>{rootName(rootCause(row))}</td></tr>)}</tbody></DataTable></div>}<pre className="technical-record">{candidateAuditOpen ? JSON.stringify(candidateAudit || selectedCandidate,null,2) : null}</pre></StoryDisclosure>
    </>}</div></Drawer>
    <Drawer className="workbench-drawer" open={!!targetCandidate} onOpenChange={open => !open && setTargetCandidate(null)} title={`${candidateName(targetCandidate)} · 目标问题`}><div className="drawer-body"><p className="muted">来自已保存目标引用，只展示当前 Baseline 中可匹配的问题。</p><DiagnosisTable business rows={targetRows(targetCandidate,badCases)} strategy={()=>targetCandidate?.reasoning?.hypothesis || '优化假设未采集'} onSelect={row=>{setTargetCandidate(null);setSelectedBadCase({...row,result:{...row.result,optimization_strategy:targetCandidate?.reasoning?.hypothesis}})}} /></div></Drawer>
    <Drawer className="workbench-drawer search-space-drawer" open={searchOpen} onOpenChange={setSearchOpen} title={`可调参数 · ${searchSpace?.search_space ? Object.keys(searchSpace.search_space).length : "—"}`} ><div className="drawer-body"><p>优化 Agent 只能修改以下字段；参数类型、允许值来自后端 Validator 的同一策略。</p>{searchSpace?.search_space ? <SearchSpaceTable contract={searchSpace.search_space} baseline={evaluation.config || {}} /> : <p>{error || "正在读取 可调参数…"}</p>}</div></Drawer>
    <Drawer className="workbench-drawer" open={!!selectedBadCase} onOpenChange={open => !open && setSelectedBadCase(null)} title="Bad Case 诊断"><div className="drawer-body">{selectedBadCase?.details_loaded === false && <p role="status">正在读取完整案例证据…</p>}{selectedBadCase && <CaseDetails item={{ ...caseData(selectedBadCase), question_id: selectedBadCase.question_id || selectedBadCase.result?.question_id, primary_root_cause: rootCause(selectedBadCase) }} snapshot={selectedBadCase.dataset_snapshot || snapshot} config={evaluation.config || {}} gates={gateDetails} />}</div></Drawer>

  </PageShell>;
}

function coverageReason(value:unknown):string {
  if (typeof value !== 'string' || !value.trim()) return '具体原因暂未记录';
  if (value === '本轮剩余A/B/C容量不足，需明确调整规划，不能宣称完成') return '本轮三套方案的名额已用完，需要调整规划';
  return businessSummary(value).replace('当前规则模板未找到通过严格验证的干预；', '当前可用的调整方法暂时不能覆盖这道题；');
}

function candidateState(candidate:any, running=false):{label:string;tone:'neutral'|'accent'|'warning'|'good'|'bad'} {
  if (candidate.result?.price_pause?.paused) return {label:'高峰时段暂停',tone:'warning'};
  if (running || ['running','queued'].includes(candidate.status)) return {label:'运行中',tone:'accent'};
  if (candidate.status === 'skipped') return {label:'已跳过（未运行）',tone:'neutral'};
  if (candidate.status === 'failed') return candidate.product_interruption === true ? {label:'评测中断',tone:'warning'} : {label:'评测停止',tone:'warning'};
  if (candidate.status === 'evaluated' && candidate.result?.evaluation_complete === false) return {label:'评测未完成',tone:'warning'};
  if (candidate.status === 'evaluated') return candidate.result?.qualification?.qualified === true ? {label:'合格',tone:'good'} : candidate.result?.qualification?.qualified === false ? {label:'已评测未通过',tone:'bad'} : {label:'已评测，资格未知',tone:'neutral'};
  return {label:'待评测',tone:'neutral'};
}

function businessSummary(value:unknown):string { return storyText(value); }

function candidateProgress(candidate:any, running?:{current?:number;total?:number}, pause?:any):string {
  if (candidate.status === "skipped") return "已跳过（未运行）";
  const completed = candidate.result?.completed ?? running?.current ?? candidate.resume_plan?.completed;
  const total = candidate.result?.total ?? running?.total ?? candidate.resume_plan?.total;
  const count = completed != null && total != null ? ` ${completed}/${total}` : " · 进度暂无";
  if (candidate.result?.price_pause?.paused || pause?.paused && ["running","queued"].includes(candidate.status)) return `高峰时段暂停${count}`;
  if (running || ["running","queued"].includes(candidate.status)) return `运行中${count}`;
  return candidateState(candidate).label;
}

function CandidateCard({ candidate, baseline, onDetail, targets, onTargets, running, busy, onRun, onSkip }: { candidate: any; baseline: Record<string, any>; onDetail: () => void; targets: any[]; onTargets: () => void; running?: { current?: number; total?: number; stage?: string }; busy: boolean; onRun: () => void; onSkip?: () => void }) {
  const reasoning = candidate.reasoning || {}, result = candidate.result;
  const evaluated = candidate.status === "evaluated" && result?.evaluation_complete !== false;
  const interrupted = candidate.status === "failed" && candidate.product_interruption === true;
  const state = candidateState(candidate, !!running);
  const questions = (value:any) => Array.isArray(value) ? value.length ? value.map(id=>targets.find(row=>row.question_id===id)).every(Boolean) ? value.map(id=>caseData(targets.find(row=>row.question_id===id)).question).join("；") : `${value.length} 道，完整内容见方案报告` : "无" : "暂无";
  return <article className="candidate-card"><div className="candidate-card-header"><div><small>Round {reasoning.round || 1}</small><h3>Candidate {reasoning.candidate_label || "—"}</h3></div><Badge tone={candidate.result?.price_pause?.paused ? "warning" : state.tone}>{candidate.result?.price_pause?.paused ? "高峰时段暂停" : state.label}</Badge></div><div className="candidate-card-body" tabIndex={0} role="region" aria-label={`Candidate ${reasoning.candidate_label} 正文`}>
    <CandidateField label="方向"><TruncatedText lines={3}>{reasoning.direction ? reasoning.direction : reasoning.intervention_direction ? optimizationDirection(reasoning.intervention_direction) : "暂无方向标签"}</TruncatedText>{reasoning.strategy_name && <TruncatedText lines={3}>{reasoning.strategy_name}</TruncatedText>}</CandidateField>
    <CandidateField label="核心思路"><TruncatedText lines={3}>{reasoning.core_idea || reasoning.hypothesis || "暂无"}</TruncatedText></CandidateField>
    <CandidateField label="参数变化"><ChangedParameters before={baseline} after={candidate.config || (candidate.reasoning?.changed_parameters ? {...baseline,...candidate.reasoning.changed_parameters} : null)}/></CandidateField>
    <CandidateField label="针对的题"><TruncatedText lines={2}>{targets.map(row => caseData(row).question).join("；") || "暂无可匹配的题目"}</TruncatedText>{targets.length > 0 && <button className="text-button" onClick={onTargets}>查看目标 {targets.length} 题</button>}</CandidateField>
    <CandidateField label="预期效果"><TruncatedText lines={3}>{reasoning.expected_improvement || reasoning.expected || "暂无"}</TruncatedText></CandidateField>
    <CandidateField label="风险">{Array.isArray(reasoning.risks) && reasoning.risks.length ? <ul>{reasoning.risks.map((risk:any,index:number) => <li key={index}><TruncatedText lines={3}>{questions(risk.question_ids)} · {risk.reason || "暂无"}</TruncatedText></li>)}</ul> : <TruncatedText lines={3}>{reasoning.risk || "暂无"}</TruncatedText>}</CandidateField>
    <CandidateField label="结果">{evaluated ? <><dl className="candidate-result">{[["Hard Gate","gates"],["修复原问题","target_bad_cases_fixed"],["新增失败","new_failures"],["Regression Check","regression"],["P50","latency_p50_seconds"],["P99","latency_p99_seconds"],["候选合格","qualification"],["可发布","release_qualification"]].map(([label,key]) => <div key={key}><dt>{label}</dt><dd>{metricText(result,key)}</dd></div>)}</dl><TruncatedText lines={2}>修好：{questions(result?.all_fixed_question_ids)}</TruncatedText><TruncatedText lines={2}>弄坏：{questions(result?.new_regression_question_ids)}</TruncatedText><TruncatedText lines={3}>{regressionText(result)}</TruncatedText></> : <><p>{candidateProgress(candidate,running)}</p>{result?.evaluation_complete === false && <p>已完成 {result.completed ?? "暂无"}/{result.total ?? "暂无"}{candidate.resume_plan?.can_resume === false ? ` · ${businessSummary(candidate.resume_plan.reason)}` : " · 已保存断点"}</p>}<p className={interrupted ? "candidate-interruption-note" : "muted"}>{interrupted ? "产品故障，会自动续跑；已完成的题不重复调用。" : candidate.status === "failed" ? "Sandbox 运行停止，原因见详情。" : running || ["running","queued"].includes(candidate.status) ? "等待完整资格结论。" : "Sandbox 尚未运行"}</p></>}</CandidateField>
  </div><div className="candidate-card-footer"><button className="text-button" onClick={event => { event.currentTarget.focus(); onDetail(); }}>查看方案与完整报告</button>{candidate.status === "generated" && onSkip && <button className="text-button" disabled={busy || !!running} onClick={onSkip}>跳过此方案</button>}<CandidateAction candidate={candidate} running={running} busy={busy} onRun={onRun} /></div></article>;
}

function CandidateField({label,children}:{label:string;children:React.ReactNode}) {
  return <section className="candidate-story-block"><h4 className="field-label">{label}</h4><div className="candidate-field-content">{children}</div></section>;
}

function ConfigDiff({ base, candidate }: { base: Record<string, any>; candidate: any }) {
  const after = candidate.config || (candidate.reasoning?.changed_parameters ? { ...base, ...candidate.reasoning.changed_parameters } : null);
  if(!after || !Object.keys(base).length)return <p className="muted">历史未保存完整Baseline配置，无法核对参数Diff。</p>;
  const keys=Object.keys(parameterNames).filter(key=>key in base && key in after);
  return <div className="candidate-config-diff"><ParameterDiff before={Object.fromEntries(keys.map(key=>[key,base[key]]))} after={Object.fromEntries(keys.map(key=>[key,after[key]]))}/>{keys.length<Object.keys(parameterNames).length && <p className="muted">部分参数缺少前后记录，未纳入Diff；原始配置保留在高级审计。</p>}</div>;
}

function CandidateAction({ candidate, running, busy, onRun }: { candidate: any; running?: { current?: number; total?: number }; busy: boolean; onRun: () => void; onSkip?: () => void }) {
  return <div className="candidate-card-action"><button className="secondary" disabled={busy || !!running || !["generated", "failed"].includes(candidate.status)} onClick={onRun}>{running ? "Sandbox 运行中" : candidate.status === "skipped" ? "已跳过（未运行）" : candidate.status === "evaluated" ? "已评测" : candidate.status === "failed" ? "继续 Sandbox" : "运行 Sandbox"}</button>{running && running.current != null && running.total != null && <span>{running.current} / {running.total}</span>}</div>;
}

const candidateName = (candidate?: any) => candidate ? schemeName(candidate) : displayText("Candidate");

function metricText(result: any, key: string) {
  if (result?.evaluation_complete === false && !["token_cost", "input_tokens", "output_tokens"].includes(key)) return key === "bad_case_count" ? "待完成" : key === "gates" ? "未完成" : "未判定";
  if (!result || !Object.keys(result).length) return "待运行";
  if (key === "all_fixed_count") return Array.isArray(result.all_fixed_question_ids) ? String(new Set(result.all_fixed_question_ids).size) : result.comparison_version ? "未采集" : result.target_bad_cases_fixed ?? "未采集";
  if (key === "new_failures") { const r = result.regression_review || result.regression; return r && r.new_critical_failures != null && r.new_ordinary_failures != null ? `${!result.regression_review && Array.isArray(result.formal_blocking_question_ids)?"正式阻断 · ":""}严重 ${r.new_critical_failures} / 普通 ${r.new_ordinary_failures}` : "未采集"; }
  if (key === "gates") return result.gates?.passed_count!=null && result.gates?.total!=null ? `${result.gates.passed_count} / ${result.gates.total}` : "未采集";
  if (key === "regression") return result.regression_review || result.regression ? displayText((result.regression_review || result.regression).status || "未采集") : "未判定";
  if (key === "release_qualification") return result.release_qualification?.qualified === true ? "可发布" : result.release_qualification?.qualified === false ? "不可发布" : "未判定";
  if (key === "qualification") return typeof result.qualification?.qualified === "boolean" ? result.qualification.qualified ? "合格" : "不合格" : "未判定";
  if (key === "token_cost") return billedCostText(result.comparison_metrics);
  const value = result.comparison_metrics?.[key] ?? result.metrics?.[key] ?? result[key];
  if (["bad_case_count", "target_bad_cases_fixed", "incidental_fixes", "net_improvement", "input_tokens", "output_tokens"].includes(key) && typeof value === "number") return String(value);
  if (["latency_p50_seconds", "latency_p99_seconds"].includes(key)) return typeof value === "number" ? `${value.toFixed(1)} 秒` : "暂无";
  return typeof value === "number" ? value.toFixed(2) : value ?? "未采集";
}

function targetRows(candidate: any, rows: any[]): any[] {
  const ids = new Set(candidate?.reasoning?.observed_evidence || candidate?.reasoning?.target_bad_cases || []);
  return agentDiagnosisRows(rows).filter(row => ids.has(row.id) || ids.has(row.question_id));
}
function qualificationExplanation(candidate:any):string {
  if(candidate.status!=="evaluated")return candidate.status==="failed"?"运行失败；部分结果不能代表资格结论。":"实验尚未完成，不预判资格。";
  const names:Record<string,string>={hard_gates:"Hard Gate 未通过",regression:"Regression Check 未通过",target_bad_case_fixed:"未满足目标修复条件",total_bad_cases_reduced:"未满足失败总数减少条件"};
  const failed=Object.entries(candidate.result?.qualification?.checks || {}).filter(([,passed])=>passed===false).map(([key])=>names[key] || "其他保存的资格条件未通过");
  return failed.join("；") || (candidate.result?.qualification?.qualified===true?"保存的质量、安全与 Regression 资格通过；正式推荐以已保存决策为准。":"历史未保存具体未通过原因。");
}

function regressionText(result: any): string {
  const r = result?.regression_review || result?.regression;
  if (!r) return "Regression Check 尚未运行。";
  const fixed = result.target_bad_cases_fixed;
  const counts = r.new_critical_failures != null && r.new_ordinary_failures != null ? `新增严重 ${r.new_critical_failures}、普通 ${r.new_ordinary_failures} 个失败（上限分别为 0、1）` : "新增失败明细未采集";
  const classification = result.regression_review ? "；按当前上限核对，最终资格保留保存结论" : "";
  const continued = result.continued_failure_new_critical_question_ids || r.continued_failure_new_critical_question_ids;
  const risk = Array.isArray(continued) && continued.length ? `；持续失败题新增严重风险 ${continued.length} 题，阻断资格` : '';
  const incomplete = result.comparison_complete === false || r.comparison_complete === false ? '；评测执行未完成，比较与资格阻断' : '';
  return `${fixed == null ? "问题修复数未采集" : `修复 ${fixed} 个${result.comparison_version ? "指定目标" : "原问题（历史统计）"}`}；${counts}。${classification}${risk}${incomplete}`;
}

function accountingText(value:any):string {
  if (!value) return "历史费用未完整记录，不能按0元计算";
  const cost=value.cost_estimation;
  return `${value.call_events ?? "未采集"} 次调用记录，${value.unknown_usage_events ?? "未采集"} 次Usage未知；${cost?.status === "estimated" ? `${cost.amount} ${cost.currency}（按Usage核算，非账户实扣）` : "完整费用待账单核对"}`;
}
