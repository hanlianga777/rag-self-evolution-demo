import { yuanText } from "../components/PipelineFields";
import { judgePresentation } from "../components/judgePresentation";
import { agentDisplayText } from "../display";
import { Icon, IconLabel, IconTile } from "../ui/icons";
import { CompareTable, type CompareRow } from "../ui/pages3";
import { HoverCard } from "../ui/HoverCard";
import {DStory, DSideEffects, questionText, schemeName, storyText, StoryText, recommendationReason, recommendationTradeoff, dProgressLabel, ChangedParameters, storyParameterNames, storyValue, shortQuestionId} from "../components/EvolutionStory";
import { AgentOverview } from "../ui/evolution/AgentOverview";
import { FinalRecommendation } from "../ui/evolution/FinalRecommendation";
import { EvolutionTimeline } from "../ui/evolution/EvolutionTimeline";
import { QuestionBadge, QuestionList } from "../ui/Primitives";
import { ClampText } from "../ui/ClampText";
import { buildEvolutionModel } from "../ui/evolution/model";
import { usePageTab } from "../usePageTab";
import { savedSnapshot } from "../evaluationProgress";
import { DataTable } from "../components/DataTable";
import { PricePauseNotice } from "../components/RuntimeSettings";
import { StoryDisclosure } from "../components/Storytelling";
import { FilterButtons } from "../components/Storytelling";
import './evaluation-workspaces.css';
import {DiagnosisTable, questionLabel, optimizationDirection, savedDirections, coreEvidence, caseData, currentRoot, rootName, agentDiagnosisRows} from '../components/EvaluationDiagnosis';
import { StrategyPresentation } from "../components/ProductDiagnostics";
import { CandidateCaseComparison } from "../components/CandidateCaseComparison";
import { PageShell } from "../components/PageShell";
import { RetrievalEvidence } from "../components/RetrievalEvidence";
import { useEffect, useRef, useState } from "react";
import { Play } from "lucide-react";
import { detailJson, useDetailPrefetch, useHoverPrefetch } from "../preload";
import { cachedJson, errorMessage, getJson, identityKey, postJson } from "../api";
import { LoadingSkeleton, Badge, ConclusionCard, Section, TableVerdict, ShortId, Status, TruncatedText } from "../components/Primitives";
import { ExecutionMetrics, ParameterDiff, SearchSpaceTable, parameterNames, formatValue, billedCostText } from "../components/PipelineFields";
import { ConfirmDialog, Drawer } from "../components/Dialog";
import { useOperation } from "../operation";
import { displayText, narrativeText, baselineName } from "../display";
import { CaseAnswer } from "../components/CaseAnswer";
import { CaseDetails, gateNames } from "./EvaluationPage";

const rootCause = currentRoot;

export function EvolutionPage({ data }: { data: any }) {
  const operation = useOperation();
  const [historyOpen, setHistoryOpen] = useState(false);
  const [savedStage, setStage] = usePageTab("evolution", ["overview", "route", "comparison", "review", "candidates", "sandbox", "regression", "recommendation"] as const, "overview");
  const stage = savedStage === "candidates" || savedStage === "sandbox" ? "comparison" : savedStage === "regression" || savedStage === "recommendation" ? "review" : savedStage;
  useEffect(() => { if (savedStage !== stage) setStage(stage); }, [savedStage, stage]);
  const openDiagnosis = () => { location.hash = "evaluation?tab=cases"; };
  useEffect(() => {
    const redirect = () => { const params = new URLSearchParams(location.hash.split("?")[1]); if (location.hash.startsWith("#evolution?") && ["bad", "diagnosis"].includes(params.get("tab") || params.get("stage") || "")) openDiagnosis(); };
    redirect(); window.addEventListener("hashchange", redirect);
    return () => window.removeEventListener("hashchange", redirect);
  }, []);
  const [confirmationAction, setConfirmationAction] = useState<{title: string; description: string; execute: () => void} | null>(null);
  const [experiment, setExperiment] = useState<any>(data.optimization?.id ? data.optimization : null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const errorRef = useRef<HTMLParagraphElement | null>(null);
  useEffect(() => { if (error) errorRef.current?.focus(); }, [error]);
  const [searchOpen, setSearchOpen] = useState(false);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [searchSpace, setSearchSpace] = useState<any>(null);
  const [selectedCandidate, setSelectedCandidate] = useState<any>(null), [candidateReport, setCandidateReport] = useState<any>(null);
  const [reportError,setReportError] = useState(''), [auditError,setAuditError] = useState('');
  const [reportPage,setReportPage]=useState(1);
  const [candidateAudit, setCandidateAudit] = useState<any>(null);
  const [candidateAuditOpen, setCandidateAuditOpen] = useState(false), [candidateMetricsOpen, setCandidateMetricsOpen] = useState(false);
  useEffect(() => { setCandidateAuditOpen(false); setCandidateMetricsOpen(false); }, [selectedCandidate?.id]);
  useEffect(() => {
    setCandidateAudit(null); setAuditError('');
    if (!selectedCandidate?.experiment_id || !candidateAuditOpen) return;
    setCandidateAudit(cachedJson<any>(`/api/experiments/${selectedCandidate.experiment_id}`)?.candidates?.find((item:any) => item.id === selectedCandidate.id) || null);
    let cancelled = false;
    void detailJson<any>(`/api/experiments/${selectedCandidate.experiment_id}`).then(value => {
      if (!cancelled) setCandidateAudit(value.candidates?.find((item:any) => item.id === selectedCandidate.id));
    }).catch(reason => { if (!cancelled) setAuditError(errorMessage(reason)); });
    return () => { cancelled = true; };
  }, [selectedCandidate?.id, candidateAuditOpen]);
  useEffect(() => { setReportError(''); setReportPage(1); const id = selectedCandidate?.result?.evaluation_run_id; setCandidateReport(id && selectedCandidate.status==="evaluated" && (candidateAuditOpen || candidateMetricsOpen) ? cachedJson<any>(`/api/evaluations/${id}`) || null : null); if (!id || selectedCandidate.status!=="evaluated" || !candidateAuditOpen && !candidateMetricsOpen) return; let cancelled = false; void detailJson<any>(`/api/evaluations/${id}`).then(value => { if (!cancelled) setCandidateReport(value); }).catch(reason => { if (!cancelled) setReportError(errorMessage(reason)); }); return () => { cancelled = true; }; }, [selectedCandidate, candidateAuditOpen, candidateMetricsOpen]);
  const [selectedBadCase, setSelectedBadCase] = useState<any>(null);
  useEffect(() => {
    if (!selectedBadCase?.id || selectedBadCase.details_loaded !== false) return;
    let cancelled = false;
    void detailJson<any>(`/api/bad-cases/${encodeURIComponent(selectedBadCase.id)}`).then(value => {
      if (!cancelled) setSelectedBadCase({...value,result:{...value.result,optimization_strategy:selectedBadCase.result?.optimization_strategy}});
    }).catch(reason => { if (!cancelled) setSelectedBadCase((current:any) => ({...current,load_error:errorMessage(reason)})); });
    return () => { cancelled = true; };
  }, [selectedBadCase?.id]);
  const [comparisonCase,setComparisonCase]=useState<any>(null);
  const [comparisonKind,setComparisonKind]=useState<"fixed"|"regression">("regression");
  const refreshed = useRef(new Set<string>());
  const [winnerId, setWinnerId] = useState("");
  const evaluation = data.evaluation || {};
  const identity = identityKey(data.workspace || data.evaluation);
  const currentIdentity = useRef(identity); currentIdentity.current = identity;
  useEffect(() => { setExperiment(data.optimization?.id ? data.optimization : null); setSelectedCandidate(null); setCandidateReport(null); setSelectedBadCase(null); setComparisonCase(null); setWinnerId(""); setSearchOpen(false); setAdvancedOpen(false); setSearchSpace(null); setError(""); setBusy(false); setConfirmationAction(null); }, [identity]);
  useEffect(() => { setExperiment(data.optimization?.id ? data.optimization : null); }, [data.optimization]);
  const [targetCandidate, setTargetCandidate] = useState<any>(null);
  useEffect(() => { setTargetCandidate(null); }, [identity]);
  const badCases = (data.badCases || []).filter((item: any) => item.run_id === evaluation.id);
  const candidates: any[] = experiment?.candidates || [];
  const hover = useHoverPrefetch();
  useDetailPrefetch([
    ...(evaluation.id ? [`/api/evaluations/${evaluation.id}`] : []),
    ...candidates.filter(candidate => candidate.status === "evaluated" && candidate.result?.evaluation_run_id).map(candidate => `/api/evaluations/${candidate.result.evaluation_run_id}`),
    ...candidates.filter(candidate => candidate.experiment_id).map(candidate => `/api/experiments/${candidate.experiment_id}`),
    ...badCases.filter((row: any) => row.id && row.details_loaded === false).map((row: any) => `/api/bad-cases/${encodeURIComponent(row.id)}`),
  ]);
  const abc = candidates.filter(candidate => ["A", "B", "C"].includes(candidate.reasoning?.candidate_label)).sort((a, b) => (a.reasoning?.round || 1) - (b.reasoning?.round || 1) || String(a.reasoning?.candidate_label).localeCompare(String(b.reasoning?.candidate_label)));
  const d = candidates.find(candidate => candidate.reasoning?.candidate_label === "D");
  const dReportId = d?.status === "evaluated" && d.result?.evaluation_complete !== false ? d.result?.evaluation_run_id : undefined;
  useEffect(() => { if (dReportId) void detailJson(`/api/evaluations/${encodeURIComponent(dReportId)}`).catch(() => {}); }, [dReportId]);
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
  const reviewCandidates = [...abc, ...(d ? [d] : [])];
  const budget = experiment?.evaluation_budget || data.optimization?.evaluation_budget || {};
  const budgetKnown = Number.isFinite(budget.used) && Number.isFinite(budget.max);
  const latestRound = experiment?.rounds?.at(-1);
  const canContinue = latestRound?.complete && !confirmation && budgetKnown && budget.used <= budget.max - (budget.reserved_for_d ?? budget.reserved_for_d1 ?? 1) - 3;
  const qualified = candidates.filter(item => ["A", "B", "C"].includes(item.reasoning?.candidate_label) && item.status === "evaluated" && item.result?.qualification?.qualified);
  const selectedWinner = qualified.some(item => item.id === winnerId) ? winnerId : recommendation.suggested_winner || qualified[0]?.id || "";
  const batchId = `sandbox-round:${experiment?.id}:${roundNumber}`;
  const batchRunning = operation.operations.some(item => item.id === batchId && item.status === "running");
  const hasRunning = cycle?.status === "running" || compositeWaiting || candidates.some(item => ["running", "queued"].includes(item.status)) || operation.operations.some(item => item.candidateId && item.status === "running") || batchRunning;
  const published = (data.versions || []).some((version:any) => version.status === "active" && version.provenance === "published" && candidates.some(candidate => candidate.id === version.snapshot?.candidate_id));
  const pending = currentRound.filter(item => ["generated", "failed"].includes(item.status));
  const policyBlocked = !!evaluation.requires_policy_upgrade || !!data.workspace?.requires_policy_upgrade;
  const coverage = experiment?.coverage_plan;
  const planningIncomplete = !!coverage && coverage.status === "incomplete";
  const planningBlocked = planningIncomplete && currentRound.length < 3;
  const triedSandbox = candidates.some(candidate => ["running","queued","evaluated","failed"].includes(candidate.status) || candidate.result?.evaluation_run_id);
  const completePlan = () => void action("零调用补齐本轮规划", () => postJson(`/api/experiments/${experiment.id}/complete-plan`, { binding: coverage.binding }));
  const canBatch = budgetKnown && !planningBlocked && !policyBlocked && !!pending.length && !confirmation && !hasRunning && budget.used < budget.max - (budget.reserved_for_d ?? 1);
  const executeBatch = async () => {
    const captured = identity; setError("");
    try { await operation.runCandidateBatch({ experimentId: experiment.id, baselineId: evaluation.id, round: roundNumber, candidateIds: pending.map(item => item.id), identity: data.workspace ? identity : undefined }); await refresh(); }
    catch (reason) { if (currentIdentity.current === captured) { setError(errorMessage(reason)); await refresh(); } }
  };
  const requestPaid = (title: string, description: string, execute: () => void) => setConfirmationAction({title, description, execute});
  const runBatch = () => requestPaid('运行本轮 A/B/C Sandbox', `Golden ${evaluation.dataset_snapshot?.question_ids?.length ?? evaluation.cases?.length ?? '未采集'} 题，待运行 ${pending.length} 个 Candidate；每题回答+Judge；评测次数 ${budget.used}/${budget.max}，D预留1次。Rewrite/MultiQuery/HyDE 启用时有额外模型调用。`, () => void executeBatch());
  const activeOperation = (candidateId: string) => operation.operations.find(item => item.candidateId === candidateId && item.status === "running");
  const processingCases=agentDiagnosisRows(badCases);

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
    try { await operation.run("生成 A/B/C Candidate", () => postJson("/api/experiments/run")); await refresh(); }
    catch (reason) { if (currentIdentity.current === captured) setError(errorMessage(reason)); }
    finally { if (currentIdentity.current === captured) setBusy(false); }
  };
  const generate = () => requestPaid('生成A/B/C优化建议', '一次Agent策略分析调用；不自动执行Sandbox。', () => void executeGenerate());
  const continueRound = () => requestPaid('生成下一轮建议', '读取已保存历史实验反馈，一次Agent分析；不自动评测。', () => void action('生成下一轮A/B/C', () => postJson(`/api/experiments/${experiment.id}/continue`)));
  const run = (candidate: any) => candidate.resume_plan?.can_resume === false ? setError(candidate.resume_plan.reason || '当前无法继续，请查看原因') : requestPaid('运行 Candidate Sandbox', '继续完成尚未结束的评测；会产生模型费用。', () => void executeCandidate(candidate));
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
  const recommendationTitle=recommendation.status === "Recommended" && !recommendation.recommended_candidate ? "保存推荐：保持 Baseline" : !roundComplete ? currentRound.some(c=>c.status === "failed") ? "本轮实验尚未完成 · 有运行失败" : "本轮实验尚未完成" : recommendation.status==="No Qualified Candidate" ? "保存结论：本轮暂无合格 Candidate" : recommendation.recommended_candidate ? savedRecommended ? `保存推荐：${candidateName(savedRecommended)}` : "已有保存推荐，Candidate 详情未采集" : currentRound.some(item=>typeof item.result?.qualification?.qualified!=="boolean") ? "资格或推荐结论未采集" : qualified.length ? "已有合格 Candidate，等待保存的最终决策" : "推荐结论未采集";
  const activeCandidate = currentRound.find(candidate => ["running", "queued"].includes(candidate.status) || candidate.result?.price_pause?.paused);
  const steps = [
    { label: "诊断", state: evaluation.status === "completed" ? "completed" : "blocked", detail: evaluation.status === "completed" ? `${evaluation.result?.bad_case_count ?? badCases.length} 个 Bad Case 已读取` : "等待有效 Baseline", onSelect: openDiagnosis },
    { label: "生成 A/B/C", state: planningIncomplete && (!roundComplete || currentRound.length<3) || experiment?.status === "generating" ? "current" : experiment?.status === "failed" ? "blocked" : currentRound.length ? "completed" : "pending", detail: experiment?.status === "failed" ? "本轮 Candidate 生成失败" : planningIncomplete && (!roundComplete || currentRound.length<3) ? `${currentRound.length} 个 Candidate · 有覆盖缺口` : `${currentRound.length} 个 Candidate`, onSelect: () => setStage("route") },
    { label: "Candidate A/B/C/D", state: planningIncomplete && (!roundComplete || currentRound.length<3) ? "current" : currentRound.length ? "completed" : "pending", detail: `${currentRound.length} 个 Candidate · ${dProgressLabel(experiment)}`, onSelect: () => setStage("comparison") },
    { label: "Sandbox", state: sandboxPause || hasRunning ? "current" : currentRound.some(candidate => candidate.status === "failed") ? "blocked" : roundComplete ? "completed" : "pending", detail: activeCandidate ? `${activeCandidate.reasoning?.candidate_label} ${candidateProgress(activeCandidate, activeOperation(activeCandidate.id), sandboxPause)}` : sandboxPause ? "已暂停" : currentRound.length ? `${evaluatedCount}/${currentRound.length} 已评测` : "尚无待评测 Candidate", onSelect: () => setStage("comparison") },
    { label: "Regression Check", state: roundComplete ? "completed" : "pending", detail: roundComplete ? `${evaluatedCount} 个 Candidate 已保存判定` : "等待完整评测", onSelect: () => setStage("review") },
    { label: "最终推荐", state: recommendation.recommended_candidate && confirmation ? "completed" : roundComplete ? "current" : "pending", detail: recommendation.recommended_candidate && confirmation ? schemeName(savedRecommended,recommendation.recommended_candidate) : confirmation ? "等待组合 Candidate D" : "等待完整报告与人工确认", onSelect: () => setStage("review") },
  ] as const;
  const evolutionModel = buildEvolutionModel(experiment, evaluation.config, metric => gateNames[metric] ?? metric, schemeName);
  const candidateViews = [...evolutionModel.rounds.flatMap(round => round.candidates), ...(evolutionModel.d ? [evolutionModel.d] : [])];
  const qualifiedViews = candidateViews.filter(candidate => candidate.complete && candidate.qualified);
  const chosenView = candidateViews.find(candidate => candidate.id === savedRecommended?.id);
  const runnerUpView = candidateViews.find(candidate => candidate.id === evolutionModel.winnerId && candidate.id !== chosenView?.id) || null;
  const production = data.overview?.production || data.versions?.find((item: any) => item.status === "active");
  const productionReleased = production?.provenance === "published" && !!savedRecommended && production.snapshot?.candidate_id === savedRecommended.id;
  const phaseDetails = [...new Set(steps.filter(step => step.state === "current" || step.state === "blocked").map(step => step.detail))].join(" · ");
  const agentStatus = hasRunning || busy ? `${activeCandidate ? `${schemeName(activeCandidate)} · ${candidateProgress(activeCandidate, activeOperation(activeCandidate.id), sandboxPause)}` : "Agent 评测中"} · ${dProgressLabel(experiment)}${savedRecommended ? ` · 当前保存推荐：${schemeName(savedRecommended)}` : ""}` : productionReleased ? schemeName(savedRecommended).replace(/^Round \d+ · /, "") : savedRecommended ? `推荐 ${schemeName(savedRecommended)}，待人工发布 · ${dProgressLabel(experiment)}` : sandboxPause ? "已暂停，进度已保存" : `${latestRound ? `Round ${latestRound.round} · ${latestRound.evaluated ?? "未知"}/${latestRound.total ?? "未知"} · ` : ""}${phaseDetails || "等待生成优化 Candidate"}${!budgetKnown && experiment ? " · 预算尚未同步" : ""}`;

  const sandboxCandidates = [...displayedCandidates, ...(d ? [d] : [])];
  const comparisonSources = [evaluation, ...sandboxCandidates];
  const compareValue = (source: any, key: string): number | string | null => {
    const result = source.result;
    if (source !== evaluation && (result?.price_pause?.paused || ["running", "queued"].includes(source.status))) return candidateProgress(source, activeOperation(source.id), sandboxPause);
    if (!result || result.evaluation_complete === false || !["completed", "evaluated"].includes(source.status)) return null;
    if (key === "correct") return typeof result.total === "number" && typeof result.bad_case_count === "number" ? result.total - result.bad_case_count : null;
    if (key === "new") return Array.isArray(result.new_regression_question_ids) ? new Set(result.new_regression_question_ids).size : typeof result.new_regressions === "number" ? result.new_regressions : null;
    if (key === "gates") return result.gates?.passed_count ?? null;
    const value = result.comparison_metrics?.[key] ?? result.metrics?.[key] ?? result.safety_metrics?.[key] ?? result.gates?.gates?.find((gate: any) => gate.metric === key)?.actual;
    return typeof value === "number" ? value : null;
  };
  const gateTotals = comparisonSources.map(source => source.result?.gates?.total);
  const sameGateTotal = gateTotals[0] != null && gateTotals.every(total => total === gateTotals[0]);
  const compareRows: CompareRow[] = [
    { label: "答对", values: comparisonSources.map(source => compareValue(source, "correct")), better: "higher", unit: typeof evaluation.result?.total === "number" ? ` / ${evaluation.result.total}` : undefined },
    { label: "新增 Bad Case", values: ["不适用", ...sandboxCandidates.map(source => compareValue(source, "new"))], better: "lower" },
    { label: "Hard Gate", values: comparisonSources.map(source => sameGateTotal ? compareValue(source, "gates") : metricText(source.result, "gates")), better: "higher", unit: sameGateTotal ? ` / ${gateTotals[0]}` : undefined },
    { label: "安全拒答率", values: comparisonSources.map(source => compareValue(source, "safe_rejection_rate")), better: "higher", digits: 1, unit: "%" },
    { label: "P50", values: comparisonSources.map(source => compareValue(source, "latency_p50_seconds")), better: "lower", digits: 1, unit: " 秒" },
    { label: "P99", values: comparisonSources.map(source => compareValue(source, "latency_p99_seconds")), better: "lower", digits: 1, unit: " 秒" },
    ...([["全部原 Bad Case 修好", "all_fixed_count"], ["指定目标修好", "target_bad_cases_fixed"], ["新增 Bad Case 明细", "new_failures"], ["其他问题改善", "incidental_fixes"], ["净改善", "net_improvement"], [displayText("Regression"), "regression"]] as const).map(([label, key]): CompareRow => ({ label, primary: false,
      better: ["all_fixed_count", "incidental_fixes", "net_improvement"].includes(key) ? "higher" : undefined,
      unit: key === "all_fixed_count" ? ` / ${evaluation.result?.bad_case_count ?? "未知"}` : undefined,
      values: comparisonSources.map((source, index) => {
        if (index === 0) return "不适用";
        if (key === "target_bad_cases_fixed") {
          const denominator = Array.isArray(source.reasoning?.observed_evidence || source.reasoning?.target_bad_cases) && badCases.length ? targetRows(source, badCases).length : "未知";
          return `${metricText(source.result, key)} / ${denominator}`;
        }
        const value = metricText(source.result, key);
        return ["all_fixed_count", "incidental_fixes", "net_improvement"].includes(key) && /^-?\d+$/.test(value) ? Number(value) : value;
      }),
    })),
  ];
  const regressionSummary = <section className="panel regression-check"><div className="section-head"><h2>Regression Check · 全部 Candidate</h2></div><div className="table-scroll regression-summary-table"><DataTable><colgroup><col style={{width:'25%'}}/>{[15,15,15,15,15].map((width,index)=><col key={index} style={{width:`${width}%`}}/>)}</colgroup><thead><tr>{["Candidate","修好","新增严重","新增普通","Hard Gate","判定"].map((label,index)=><th key={label} className={index>0 && index<4?"num":undefined}>{label}</th>)}</tr></thead><tbody>{reviewCandidates.map(candidate=>{const review=candidate.result?.regression_review;const view=candidateViews.find(item=>item.id===candidate.id);const complete=view?.complete;return <tr key={candidate.id} className={complete && view.qualified===true ? "qualified" : undefined}><td><button className="regression-candidate" onClick={()=>setSelectedCandidate(candidate)}>{schemeName(candidate)}</button></td><td className="num">{review?.fixed_count ?? "未知"}</td><td className="num">{review?.new_critical_failures ?? "未知"}</td><td className="num">{review?.new_ordinary_failures ?? "未知"}</td><td><TableVerdict value={complete ? candidate.result?.gates?.passed : undefined} pass="通过" fail="未通过"/></td><td><TableVerdict value={complete ? view.qualified : undefined} pass="通过" fail="未通过"/></td></tr>})}{!reviewCandidates.length && <tr><td colSpan={6}>尚无 Candidate Regression 结论</td></tr>}</tbody></DataTable></div><p className="regression-limit-note">新增严重上限 0，普通上限 1；修好的题不能抵消新增 Bad Case。判定沿用保存的最终资格，同时检查 Hard Gate；单独 Regression 结论见 Candidate 详情。</p></section>;
  return <PageShell className="page evolution-page" header={<><div className="page-title"><div><h1><IconTile name="agent" />Agent 工作台</h1><p className="ui-kicker page-purpose">Agent 根据 Bad Case 的成因提出不同方向的 Candidate，在 Sandbox 里用同一套考卷比较，找出既修好问题又不弄坏其他题的方案。</p></div><div className="header-actions">{hasRunning && <button className="secondary" onClick={() => setStage("comparison")}>查看 Sandbox 进度</button>}<button className="secondary" onClick={() => setHistoryOpen(true)}>查看历史实验</button></div></div></>} tabs={<div className="tabs"><button aria-pressed={stage === "overview"} className={stage === "overview" ? "active" : ""} onClick={() => setStage("overview")}>概览</button><button aria-pressed={stage === "route"} className={stage === "route" ? "active" : ""} onClick={() => setStage("route")}>进化路线</button><button aria-pressed={stage === "comparison"} className={stage === "comparison" ? "active" : ""} onClick={() => setStage("comparison")}>Candidate 对比</button><button aria-pressed={stage === "review"} className={stage === "review" ? "active" : ""} onClick={() => setStage("review")}>回归与推荐</button></div>} resetKey={stage}>


    <ConfirmDialog open={!!confirmationAction} onOpenChange={open => !open && setConfirmationAction(null)} title={confirmationAction?.title || "确认操作"} onConfirm={() => { const next = confirmationAction; setConfirmationAction(null); next?.execute(); }}><div className="muted-prose"><TruncatedText lines={3}>{confirmationAction?.description}</TruncatedText></div></ConfirmDialog>
    <PricePauseNotice pause={pricePause} experimentId={experiment?.id} onChanged={refresh} />
    {candidates.filter(candidate => !pricePause && candidate.result?.price_pause?.paused).map(candidate => <PricePauseNotice key={candidate.id} pause={candidate.result.price_pause} evaluationId={candidate.result.evaluation_run_id} onChanged={refresh} />)}
    {cycle?.status === "qualified" && !confirmation && <p className="workbench-status" role="status">本轮 A/B/C 已完成，等待人工确认报告与 Winner；确认后才能生成组合 Candidate D。</p>}
    {cycle?.status === "budget_exhausted" && <p className="workbench-status" role="status">优化循环已停止：已评测 {budget.used} / {budget.max} 次，剩余 {Math.max(0, budget.max - budget.used)} 次（其中 1 次留给 D）。剩余次数不足以运行完整 A/B/C；只有合格 Winner 经人工确认后才能进入 D。</p>}
    {policyBlocked && <p className="error-notice">当前 Baseline 评测版本身份与运行代码不兼容，真实 Agent 启动已阻断，旧实验只读。全部 Bad Case 保留在优化规划中；请先到 Baseline 查看身份预检，核对历史评测与当前规则的兼容性；需要新版评分时使用保存回答判分，不自动重新生成。</p>}
<div className="header-actions agent-secondary-actions">{triedSandbox ? null : planningBlocked && !published ? <button className={stage === "review" ? "secondary" : "primary"} disabled={busy || policyBlocked || hasRunning || !!confirmation} onClick={completePlan}>补齐本轮规划（不收费）</button> : pending.length ? <button className={stage === "review" ? "secondary" : "primary"} disabled={busy || !canBatch} onClick={() => void runBatch()}><Play size={15} />{batchRunning ? "本轮 Sandbox 运行中" : "运行本轮 A/B/C Sandbox"}</button> : <button className={stage === "review" ? "secondary" : "primary"} disabled={policyBlocked || busy || hasRunning || evaluation.status !== "completed" || (!!abc.length && !canContinue) || (!badCases.length && !experiment?.result?.monitoring_context)} onClick={() => void (canContinue ? continueRound() : generate())}><Play size={15} />{busy ? "处理中…" : canContinue ? "继续优化下一轮" : abc.length ? "本轮 Candidate 已生成" : "生成 A / B / C"}</button>}{!published && planningIncomplete && triedSandbox && <button className="secondary" disabled={busy || policyBlocked || hasRunning || !!confirmation} onClick={completePlan}>补齐本轮规划（不收费）</button>}{canBatch && triedSandbox && <button className="secondary" disabled={busy} onClick={() => void runBatch()}>运行本轮 A/B/C Sandbox</button>}</div>
    <Drawer className="workbench-drawer" open={historyOpen} onOpenChange={setHistoryOpen} title="历史实验 · 原 Candidate 与结果只读"><div className="drawer-body"><div className="candidate-cards">{abc.filter(item => (item.reasoning?.round || 1) < roundNumber).map(candidate => <CandidateCard key={candidate.id} candidate={candidate} includeRound baseline={evaluation.config || {}} busy={true} onDetail={()=>{setHistoryOpen(false);setSelectedCandidate(candidate);}} targets={targetRows(candidate,badCases)} onTargets={()=>{setHistoryOpen(false);setTargetCandidate(candidate);}} onRun={()=>void run(candidate)} />)}</div></div></Drawer>
    {error && <p ref={errorRef} tabIndex={-1} className="error-notice" role="alert">{error}</p>}

    {experiment?.result?.generation_status==='no_candidates' && <p className="workbench-status" role="status">本轮没有合法 Candidate，不能运行 Sandbox；未生成不代表优化成功。</p>}
    {experiment?.result?.rejected_candidates?.length>0 && <><p className="workbench-status">本轮保留 {currentRound.length} 个合法 Candidate，拒绝 {experiment.result.rejected_candidates.length} 个 Candidate；拒绝项不会进入 Sandbox。</p></>}
    {experiment?.result?.generation_status==='insufficient_evidence' && <p className="workbench-status" role="status">Candidate 依据不足：{experiment.result.insufficient_evidence || '暂无足够依据生成合格优化假设；待核实原始证据，不补造A/B/C。'}</p>}
    {data.workspace?.baseline_unavailable_reason && <p className="error-notice">{data.workspace.baseline_unavailable_reason}</p>}
    <p className="agent-identity sr-only">{evaluation.id ? `当前 Baseline：${baselineName(evaluation)}` : "当前有效 Baseline 尚未就绪。"}</p>

    {stage === "overview" && <AgentOverview experiment={experiment || data.optimization} model={{...evolutionModel, budget: budgetKnown ? budget : null}} evaluation={evaluation} chosenId={savedRecommended?.id} released={productionReleased} status={agentStatus} cases={processingCases} onCase={setSelectedBadCase}/>}
    {stage === "route" && <div className="route-timeline"><EvolutionTimeline key={experiment?.id} model={evolutionModel}
      questionText={id => questionText(id, evaluation, badCases)} onOpen={id => setSelectedCandidate(candidates.find(candidate => candidate.id === id))} >
      <section className="d-timeline" aria-label="Candidate D 决策"><DStory experiment={experiment} evaluation={evaluation} badCases={badCases} onReport={d ? ()=>setSelectedCandidate(d) : undefined} onRecommendation={()=>setStage("review")}/>{d && d.status !== "evaluated" && <CandidateAction candidate={d} running={activeOperation(d.id)} busy={busy || policyBlocked || hasRunning} onRun={()=>void run(d)}/>}</section>
    </EvolutionTimeline></div>}

    {stage === "comparison" && <div className="story-round-switch" role="group" aria-label="查看轮次">{roundChoices.map(round=><button className="secondary" key={round} aria-pressed={displayRound===round} onClick={()=>setRoundSelection(round)}>Round {round}</button>)}</div>}
    {stage === "comparison" && <><section className="panel">{canContinue && <div className="section-head"><button className="secondary" disabled={busy} onClick={() => void continueRound()}>继续优化下一轮</button></div>}{[displayRound].map(round => <div key={round}><div className="candidate-cards">{abc.filter(item => (item.reasoning?.round || 1) === round).map(candidate => <CandidateCard key={candidate.id} candidate={candidate} baseline={evaluation.config || {}} onDetail={() => setSelectedCandidate(candidate)} onSkip={() => void action("跳过未运行 Candidate",()=>postJson(`/api/candidates/${candidate.id}/skip`,{actor:"当前用户"}))} running={activeOperation(candidate.id)} busy={busy || planningBlocked || policyBlocked || hasRunning || !!confirmation} targets={targetRows(candidate, badCases)} onTargets={() => setTargetCandidate(candidate)} onRun={() => void run(candidate)} />)}</div></div>)}{!experiment && <p className="muted">需先完成真实 Baseline Evaluation 并识别 Bad Case。</p>}</section></>}

    {stage === "comparison" && <Section title={<IconLabel name="target">Sandbox 对比</IconLabel>} action={<button className="text-button" onClick={() => setAdvancedOpen(true)}>查看高级指标</button>}><div className="sandbox-core-table"><CompareTable key={`${experiment?.id}:${displayRound}`} columns={[{ name: "Baseline" }, ...sandboxCandidates.map(candidate => ({ name: schemeName(candidate), status: candidate.id === dWinner?.id ? "winner" as const : candidate.id === savedRecommended?.id ? "recommended" as const : candidate.result?.qualification?.qualified === true ? "qualified" as const : candidate.result?.qualification?.qualified === false ? "failed" as const : ["running", "queued"].includes(candidate.status) ? "running" as const : "waiting" as const }))]} rows={compareRows} highlight={sandboxCandidates.flatMap((candidate, index) => candidate.id === dWinner?.id || candidate.reasoning?.candidate_label === "D" ? [index + 1] : [])} /></div><HoverCard content="全部原 Bad Case 修好：分母是 Baseline 原有的全部 Bad Case。指定目标修好：分母是该 Candidate 保存的指定目标题数。目标题属于原问题的一部分，两行有重叠，不能相加；D 的指定目标也按保存的 Baseline 比较统计。"><button className="text-button sandbox-denominators" aria-label="修复指标分母说明">ⓘ 修复口径</button></HoverCard>{!d && <p className="muted">组合 Candidate D：{compositeWaiting ? "排队中" : composite?.status === "no_effective_composite" ? "已跳过 · 无有效组合" : "等待 人工确认 与组合决策"}</p>}


    </Section>}
    {stage === "review" && <>
      {chosenView ? <><FinalRecommendation chosen={chosenView} runnerUp={runnerUpView}
        baselineCorrect={typeof evaluation.result?.total === "number" && typeof evaluation.result?.bad_case_count === "number" ? evaluation.result.total - evaluation.result.bad_case_count : null}
        reason={recommendationTradeoff(experiment)}
        totalCandidates={candidateViews.length} qualifiedCount={qualifiedViews.length}
        regressionSummary={regressionSummary}
        others={candidateViews.filter(item=>item.id!==chosenView.id && item.id!==runnerUpView?.id)}
        questionText={id => questionText(id, evaluation, badCases)}
        onRelease={() => { location.hash = "versions"; }}
        releaseLabel={productionReleased || savedRecommended?.release_state?.human_release ? "查看发布记录" : "去发布"}
        onOpen={id => setSelectedCandidate(candidates.find(candidate => candidate.id === id))}
      /></> : <><Section title="最终推荐"><h3>{recommendationTitle}</h3><div className="muted-prose"><TruncatedText lines={3}>{storyText(recommendationReason(experiment))}</TruncatedText></div></Section>{regressionSummary}</>}
{!chosenView && confirmation && <p>人工报告确认已完成。</p>}{confirmation && !composite && !compositeWaiting && <button className="secondary" disabled={busy || policyBlocked} onClick={()=>requestPaid("生成智能组合建议","在 Winner 基础上融合",()=>void action("生成智能组合建议",()=>postJson(`/api/experiments/${experiment.id}/composite`,{authorize_provider:true})))}>生成智能组合建议</button>}
{!confirmation && qualified.length > 0 && abc.every(item => item.status === "skipped" || item.status === "evaluated" && item.result?.evaluation_complete !== false) && <div className="review-batch"><label>人工确认 · 确认 A/B/C 报告并选择合格 Winner<FilterButtons label="选择合格 Winner" value={selectedWinner} onChange={setWinnerId} options={qualified.map(candidate=>({value:candidate.id,label:candidateName(candidate)}))} /></label><button className="primary" disabled={busy || policyBlocked} onClick={() => requestPaid("确认报告与 Winner", "确认已保存的 A/B/C 报告并记录人工选择。", () => void action("确认 A/B/C 报告", () => postJson(`/api/experiments/${experiment.id}/recommendation`, { candidate_id: selectedWinner, actor: "human" })))}>确认报告与 Winner</button></div>}
</>}
    <Drawer className="workbench-drawer" open={!!comparisonCase} onOpenChange={open=>!open && setComparisonCase(null)} title="Regression Check · 前后对比"><div className="drawer-body bad-case-details">{comparisonCase && <><section className="candidate-card drawer-section"><h3>业务问题与 Regression 结论</h3><CaseAnswer text={comparisonCase.question || "历史未保存问题"}/><p>Baseline {comparisonCase.before?.passed===true?"通过":comparisonCase.before?.passed===false?"未通过":"未采集"} → Candidate {comparisonCase.after?.passed===true?"通过":comparisonCase.after?.passed===false?"未通过":"未采集"} · {comparisonCase.after?.severity==="critical"?"严重":comparisonCase.after?.severity==="ordinary"?"普通":"严重程度未采集"}</p></section><section className="candidate-card drawer-section"><h3>Baseline 回答</h3><CaseAnswer text={comparisonCase.before?.model_answer || "历史未保存回答"} final={comparisonCase.before?.programmatic_metrics?.retrieval_trace?.final ?? comparisonCase.before?.retrieved_chunks ?? []}/><p>{coreEvidence(comparisonCase.before || {})}</p></section><section className="candidate-card drawer-section"><h3>Candidate 回答</h3><CaseAnswer text={comparisonCase.after?.model_answer || "历史未保存回答"} final={comparisonCase.after?.programmatic_metrics?.retrieval_trace?.final ?? comparisonCase.after?.retrieved_chunks ?? []}/><p>{coreEvidence(comparisonCase.after || {})}</p></section>{[["Baseline",comparisonCase.before,comparisonCase.baseline],["Candidate",comparisonCase.after,comparisonCase.current]].map(([label,item,run])=><StoryDisclosure className="candidate-card drawer-section" key={label} label={<>{label} · 证据变化与完整审计</>}><CaseDetails item={item || {}} snapshot={run?.dataset_snapshot || {}} config={run?.config || {}} gates={run?.gate_details || []}/></StoryDisclosure>)}</>}</div></Drawer>
    <Drawer className="workbench-drawer" open={advancedOpen} onOpenChange={setAdvancedOpen} title="Sandbox · 高级指标"><div className="drawer-body"><p>诊断与比较指标不替代 Hard Gate / Regression Check 资格判定。</p><div className="table-scroll"><DataTable><thead><tr><th>指标</th><th className="num">Baseline</th>{orderedCandidates.map(candidate => <th className="num" key={candidate.id}>{schemeName(candidate)}</th>)}</tr></thead><tbody>{[["Positive", "positive_correctness"], ["Ablation", "ablation_correctness"], ["综合分", "overall_score"], ["TTFT", "ttft_seconds"], ["Input Tokens", "input_tokens"], ["Output Tokens", "output_tokens"], ["Recall@K", "recall_at_k"], ["Precision@K", "precision_at_k"], ["MRR", "mrr"], ...( [evaluation,...orderedCandidates].some(source=>billedCostText(source.result?.comparison_metrics).startsWith("¥ ")) ? [["费用（保存估算）","token_cost"]] : [])].filter(([,key])=>[evaluation,...orderedCandidates].some(source=>{const result=source.result;return key==='token_cost' || typeof (result?.comparison_metrics?.[key] ?? result?.metrics?.[key] ?? result?.[key])==='number';})).map(([label, key]) => <tr key={key}><td>{label}</td><td className="num">{key==="token_cost" && !metricText(evaluation.result,key).startsWith("¥ ") ? "—" : metricText(evaluation.result, key)}</td>{orderedCandidates.map(candidate => <td className="num" key={candidate.id}>{key==="token_cost" && !metricText(candidate.result,key).startsWith("¥ ") ? "—" : metricText(candidate.result, key)}</td>)}</tr>)}</tbody></DataTable></div></div></Drawer>
    <Drawer className="workbench-drawer" open={!!selectedCandidate} onOpenChange={open=>!open && setSelectedCandidate(null)} title={`${candidateName(selectedCandidate)} · Candidate 详情`}><div className="drawer-body story-details">{selectedCandidate && <>
      {selectedCandidate.resume_plan && <Section title="运行进度与费用"><p>已完成 {selectedCandidate.resume_plan.completed ?? selectedCandidate.result?.completed}/{selectedCandidate.resume_plan.total ?? selectedCandidate.result?.total} · 可复用 {selectedCandidate.resume_plan.reusable ?? "待核"} 题</p><div className="muted-prose"><TruncatedText lines={3}>{selectedCandidate.resume_plan.can_resume ? `仅补 ${selectedCandidate.resume_plan.pending_answers} 次回答、${selectedCandidate.resume_plan.pending_judges} 次Judge；另计Embedding/Rerank，启动前须付费确认。` : selectedCandidate.resume_plan.reason}</TruncatedText></div><p>费用：{accountingText(selectedCandidate.result?.request_accounting)}</p></Section>}
      <Section title="优化目标"><p>评测执行：{selectedCandidate.status === "evaluated" ? "已完成" : selectedCandidate.status === "failed" ? "运行失败" : ["running","queued"].includes(selectedCandidate.status) ? "运行中" : "未运行"} · Candidate 资格：{selectedCandidate.status === "evaluated" ? metricText(selectedCandidate.result,"qualification") : "未判定"} · 发布资格：{selectedCandidate.status === "evaluated" ? metricText(selectedCandidate.result,"release_qualification") : "未判定"} · Hard Gate：{selectedCandidate.result?.evaluation_complete === false ? "未完成" : selectedCandidate.result?.gates?.passed === true ? "通过" : selectedCandidate.result?.gates?.passed === false ? "未通过" : "未运行"}</p>{targetRows(selectedCandidate,badCases).map(row=><div key={row.id}><span className="muted">{questionLabel(row.question_id)} · {caseData(row).diagnostic_view?.diagnosis_category || "分类未知"}</span><p>{caseData(row).question}</p></div>)}{!targetRows(selectedCandidate,badCases).length && <p>未匹配当前技术优化目标，原始引用保留在高级审计。</p>}</Section>
      <Section title="逐题追踪"><div className="review-filters" aria-label="Regression 案例类型"><button aria-pressed={comparisonKind==="regression"} onClick={()=>setComparisonKind("regression")}>新增 Bad Case</button><button aria-pressed={comparisonKind==="fixed"} onClick={()=>setComparisonKind("fixed")}>原问题修复</button></div><CandidateCaseComparison candidates={[selectedCandidate]} baselineId={evaluation.id} kind={comparisonKind} onCompare={setComparisonCase} onSelect={row=>setSelectedBadCase({question_id:row.question_id,result:row})}/></Section>
      <Section title="Candidate 内容"><StrategyPresentation reasoning={selectedCandidate.reasoning}/></Section>
      <Section title="Config Diff · 参数差异" action={<button className="secondary" onClick={() => setSearchOpen(true)}>查看可调参数</button>}><ConfigDiff base={evaluation.config || {}} candidate={selectedCandidate}/></Section>
      <Section title="真实实验结果"><p>{qualificationExplanation(selectedCandidate)}</p><p>{selectedCandidate.status === "evaluated" ? regressionText(selectedCandidate.result) : "没有完整 Sandbox，Regression 结论未判定。"}</p><p>Regression Check：{metricText(selectedCandidate.result,"regression")} · 目标修复 {metricText(selectedCandidate.result,"target_bad_cases_fixed")} · 净改善 {metricText(selectedCandidate.result,"net_improvement")}</p>{selectedCandidate.result?.evaluation_complete !== false && selectedCandidate.result?.regression_interpretation && <p>{selectedCandidate.result.regression_review ? "严重新增上限 0、普通新增上限 1；修好的题不能抵消新增的 Bad Case" : selectedCandidate.result.regression_interpretation}</p>}{selectedCandidate.result?.evaluation_complete === false ? <p>完整50题后判定修复与退化；历史部分比较保留在高级审计。</p> : <p>已修复：{(selectedCandidate.result?.all_fixed_question_ids || []).map(questionLabel).join("、") || "未采集"} · 新增 Bad Case：{(selectedCandidate.result?.new_regression_question_ids || []).map(questionLabel).join("、") || "未采集"}</p>}</Section>
      {selectedCandidate.reasoning?.candidate_label === "D" && <Section title="组合来源与冲突"><div className="muted-prose"><TruncatedText lines={3}>基础 Winner：{candidateName(candidates.find(item=>item.id === selectedCandidate.reasoning.winner_id))}</TruncatedText></div>{(selectedCandidate.reasoning.sources || []).map((source:any,index:number)=><p key={source.candidate_id || index}>{(source.source_candidates || [source.candidate_id]).filter(Boolean).map((id:string)=>schemeName(candidates.find(item=>item.id===id),id)).join("、") || "来源 Candidate 待核对"} · <StoryText value={source.why_merge || source.reason}/></p>)}<div className="muted-prose"><TruncatedText lines={3}>冲突：{selectedCandidate.reasoning.conflicts ? Object.keys(selectedCandidate.reasoning.conflicts).join("、") || "无冲突" : "未采集"}</TruncatedText></div></Section>}
      {selectedCandidate.reasoning?.candidate_label==='D' && <Section title="副作用检查"><DSideEffects changes={selectedCandidate.reasoning.changes || []}/></Section>}
      <StoryDisclosure key={`metrics:${selectedCandidate.id}`} label="用量、耗时与审计" onToggle={event=>setCandidateMetricsOpen(event.currentTarget.open)}>{reportError ? <p role="alert">{reportError}</p> : candidateMetricsOpen && selectedCandidate.status === "evaluated" && selectedCandidate.result?.evaluation_run_id && !candidateReport ? <LoadingSkeleton label="正在读取 Candidate 用量与耗时" /> : <ExecutionMetrics metrics={candidateReport?.cases?.find((row:any)=>row.programmatic_metrics?.stages)?.programmatic_metrics || {input_tokens:selectedCandidate.result?.comparison_metrics?.input_tokens,output_tokens:selectedCandidate.result?.comparison_metrics?.output_tokens}}/>}</StoryDisclosure>
      <StoryDisclosure key={`audit:${selectedCandidate.id}`} label="完整逐题报告与原始 Candidate 审计" onToggle={event=>setCandidateAuditOpen(event.currentTarget.open)}>{reportError ? <p role="alert">{reportError}</p> : candidateAuditOpen && selectedCandidate.status === "evaluated" && selectedCandidate.result?.evaluation_run_id && !candidateReport ? <LoadingSkeleton label="正在读取 Candidate 逐题报告" /> : <>{candidateReport?.cases?.length>200 && <div className="review-batch"><button disabled={reportPage===1} onClick={()=>setReportPage(reportPage-1)}>上一页</button><span>第 {reportPage} / {Math.ceil(candidateReport.cases.length/200)} 页</span><button disabled={reportPage*200>=candidateReport.cases.length} onClick={()=>setReportPage(reportPage+1)}>下一页</button></div>}{candidateReport?.cases?.length>0 && <div className="table-scroll"><DataTable><colgroup><col/><col style={{width:100}}/><col style={{width:150}}/></colgroup><thead><tr><th>问题</th><th>判定</th><th>根因</th></tr></thead><tbody>{candidateReport.cases.slice((reportPage-1)*200,reportPage*200).map((row:any)=><tr key={row.question_id}><td><TruncatedText lines={1}>{row.question}</TruncatedText></td><td><TableVerdict value={row.passed} pass="通过" fail="未通过"/></td><td className="muted">{rootName(rootCause(row))}</td></tr>)}</tbody></DataTable></div>}</>}{auditError ? <p role="alert">{auditError}</p> : candidateAuditOpen && selectedCandidate.experiment_id && !candidateAudit ? <LoadingSkeleton label="正在读取 Candidate 审计" /> : <pre className="technical-record">{candidateAuditOpen ? JSON.stringify(candidateAudit || selectedCandidate,null,2) : null}</pre>}</StoryDisclosure>
    </>}</div></Drawer>
    <Drawer className="workbench-drawer" open={!!targetCandidate} onOpenChange={open => !open && setTargetCandidate(null)} title={`${candidateName(targetCandidate)} · 目标问题`}><div className="drawer-body"><p className="muted">来自已保存目标引用，只展示当前 Baseline 中可匹配的问题。</p><p>指定目标修好 {metricText(targetCandidate?.result,"target_bad_cases_fixed")} / {targetRows(targetCandidate,badCases).length}；卡片“修好”列出全部已修复题号，包含指定目标之外的改善，不能相加。</p><DiagnosisTable business rows={targetRows(targetCandidate,badCases)} strategy={()=>targetCandidate?.reasoning?.hypothesis || '优化假设未采集'} onSelect={row=>{setTargetCandidate(null);setSelectedBadCase({...row,result:{...row.result,optimization_strategy:targetCandidate?.reasoning?.hypothesis}})}} /></div></Drawer>
    <Drawer className="workbench-drawer search-space-drawer" open={searchOpen} onOpenChange={setSearchOpen} title={`可调参数${searchSpace?.search_space ? ` · ${Object.keys(searchSpace.search_space).length}` : ""}`} ><div className="drawer-body"><p>优化 Agent 只能修改以下字段；参数类型、允许值来自后端 Validator 的同一策略。</p>{searchSpace?.search_space ? <SearchSpaceTable contract={searchSpace.search_space} baseline={evaluation.config || {}} /> : error ? <p role="alert">{error}</p> : <LoadingSkeleton label="正在读取可调参数" />}</div></Drawer>
    <Drawer className="workbench-drawer" open={!!selectedBadCase} onOpenChange={open => !open && setSelectedBadCase(null)} title="Bad Case 诊断"><div className="drawer-body">{selectedBadCase?.load_error ? <p role="alert">{selectedBadCase.load_error}</p> : selectedBadCase?.details_loaded === false ? <LoadingSkeleton label="正在读取完整案例证据" /> : selectedBadCase && <><Section title="Agent 规划" action={<button className="secondary" onClick={() => setSearchOpen(true)}>查看可调参数</button>}><p>{savedDirections(selectedBadCase)}</p><p>{coreEvidence(selectedBadCase)}</p>{coverage?.matrix?.filter((row:any) => row.question_id === selectedBadCase.question_id).map((row:any) => <p key={row.question_id}>{row.gap ? coverageReason(row.gap) : row.validation_requirements}</p>)}</Section><CaseDetails item={{ ...caseData(selectedBadCase), question_id: selectedBadCase.question_id || selectedBadCase.result?.question_id, primary_root_cause: rootCause(selectedBadCase) }} snapshot={selectedBadCase.dataset_snapshot || snapshot} config={evaluation.config || {}} gates={gateDetails} /></>}</div></Drawer>

  </PageShell>;
}

function coverageReason(value:unknown):string {
  if (typeof value !== 'string' || !value.trim()) return '具体原因暂未记录';
  if (value === '本轮剩余A/B/C容量不足，需明确调整规划，不能宣称完成') return '本轮三个 Candidate 的名额已用完，需要调整规划';
  return businessSummary(value).replace('当前规则模板未找到通过严格验证的干预；', '当前可用的调整方法暂时不能覆盖这道题；');
}

function candidateState(candidate:any, running=false):{label:string;tone:'neutral'|'accent'|'warning'|'good'|'bad'} {
  if (candidate.result?.price_pause?.paused) return {label:'已暂停',tone:'warning'};
  if (running || ['running','queued'].includes(candidate.status)) return {label:'运行中',tone:'accent'};
  if (candidate.status === 'skipped') return {label:'已跳过（未运行）',tone:'neutral'};
  if (candidate.status === 'failed') return candidate.product_interruption === true ? {label:'评测中断',tone:'warning'} : {label:'评测停止',tone:'warning'};
  if (candidate.status === 'evaluated' && candidate.result?.evaluation_complete === false) return {label:'评测未完成',tone:'warning'};
  if (candidate.status === 'evaluated') return candidate.result?.qualification?.qualified === true ? {label:'合格',tone:'good'} : candidate.result?.qualification?.qualified === false ? {label:'未通过',tone:'bad'} : {label:'已评测，资格未知',tone:'neutral'};
  return {label:'待评测',tone:'neutral'};
}

function businessSummary(value:unknown):string { return storyText(value); }

function candidateProgress(candidate:any, running?:{current?:number;total?:number}, pause?:any):string {
  if (candidate.status === "skipped") return "已跳过（未运行）";
  const completed = candidate.result?.completed ?? running?.current ?? candidate.resume_plan?.completed;
  const total = candidate.result?.total ?? running?.total ?? candidate.resume_plan?.total;
  const count = completed != null && total != null ? ` ${completed}/${total}` : " · 进度暂无";
  if (candidate.result?.price_pause?.paused || pause?.paused && ["running","queued"].includes(candidate.status)) return `已暂停${count}`;
  if (running || ["running","queued"].includes(candidate.status)) return `运行中${count}`;
  return candidateState(candidate).label;
}

function CandidateCard({ candidate, baseline, onDetail, targets, onTargets, running, busy, onRun, onSkip, includeRound = false }: { includeRound?: boolean; candidate: any; baseline: Record<string, any>; onDetail: () => void; targets: any[]; onTargets: () => void; running?: { current?: number; total?: number; stage?: string }; busy: boolean; onRun: () => void; onSkip?: () => void }) {
  const reasoning = candidate.reasoning || {}, result = candidate.result;
  const evaluated = candidate.status === "evaluated" && result?.evaluation_complete !== false;
  const interrupted = candidate.status === "failed" && candidate.product_interruption === true;
  const state = candidateState(candidate, !!running);
  const after=candidate.config || (reasoning.changed_parameters ? {...baseline,...reasoning.changed_parameters} : null);
  const changes=after ? Object.keys(storyParameterNames).filter(key=>key in baseline && key in after && JSON.stringify(baseline[key])!==JSON.stringify(after[key])).map(key=>`${storyParameterNames[key]} ${storyValue(baseline[key])} → ${storyValue(after[key])}`).join('；') || '已保存参数没有变化。' : '配置快照未保存，变化未知。';
  const risks:string[]=Array.isArray(reasoning.risks) && reasoning.risks.length ? reasoning.risks.map((risk:any)=>risk.reason || '暂无') : [reasoning.risk || '暂无'];
  const questionBadges=(ids:any,tone:'fixed'|'broken')=>Array.isArray(ids) ? ids.length ? ids.map((id:string)=><QuestionBadge key={id} id={shortQuestionId(id)} tone={tone} question={targets.find(row=>row.question_id===id) ? caseData(targets.find(row=>row.question_id===id)).question : undefined}/>) : '无' : '暂无';
  return <article className="candidate-card drawer-section"><div className="candidate-card-header"><div><h3>{schemeName(candidate, undefined, includeRound)}</h3></div><Badge tone={candidate.result?.price_pause?.paused ? "warning" : state.tone}>{candidate.result?.price_pause?.paused ? "已暂停" : state.label}</Badge></div><div className="candidate-card-body" tabIndex={0} role="region" aria-label={`Candidate ${reasoning.candidate_label} 正文`}>
    <CandidateField label="思路"><ClampText lines={2} text={agentDisplayText([reasoning.direction || (reasoning.intervention_direction ? optimizationDirection(reasoning.intervention_direction) : ''),reasoning.strategy_name,reasoning.core_idea || reasoning.hypothesis || '暂无'].filter(Boolean).join(' · '))}/></CandidateField>
    <CandidateField label="改动参数"><ClampText lines={2} text={changes}/></CandidateField>
    <CandidateField label="针对的题">{targets.length ? targets.map(row=><QuestionBadge key={row.question_id} id={shortQuestionId(row.question_id)} question={caseData(row).question}/>) : '暂无可匹配的题目'}</CandidateField>
    <CandidateField label="预期效果"><ClampText lines={2} text={agentDisplayText(reasoning.expected_improvement || reasoning.expected || '暂无')}/></CandidateField>
    <CandidateField label="风险"><ClampText lines={2} text={agentDisplayText(risks.join("；"))}/></CandidateField>
    <CandidateField label="结果">{evaluated ? <dl className="candidate-result"><div><dt>答对</dt><dd>{typeof result.total === "number" && typeof result.bad_case_count === "number" ? result.total - result.bad_case_count : "未知"} / {result.total ?? "未知"}</dd></div><div><dt>修好</dt><dd>{questionBadges(result?.all_fixed_question_ids,"fixed")}</dd></div><div><dt>新增 Bad Case</dt><dd>{questionBadges(result?.new_regression_question_ids,"broken")}</dd></div></dl> : <><p>{candidateProgress(candidate,running)}</p>{result?.evaluation_complete === false && <div className="muted-prose"><TruncatedText lines={3}>已完成 {result.completed ?? "暂无"}/{result.total ?? "暂无"}{candidate.resume_plan?.can_resume === false ? ` · ${businessSummary(candidate.resume_plan.reason)}` : " · 已保存进度"}</TruncatedText></div>}<p className={interrupted ? "candidate-interruption-note" : "muted"}>{interrupted ? "产品故障，会自动续跑；已完成的题不重复调用。" : candidate.status === "failed" ? "Sandbox 运行停止，原因见详情。" : running || ["running","queued"].includes(candidate.status) ? "等待完整资格结论。" : "Sandbox 尚未运行"}</p></>}</CandidateField>
  </div><div className="candidate-card-footer">{targets.length>0 && <button className="secondary small" onClick={onTargets}><Icon name="target" size={14}/>查看目标 {targets.length} 题</button>}<button className="secondary small" onClick={event => { event.currentTarget.focus(); onDetail(); }}><Icon name="report" size={14}/>查看 Candidate 与完整报告</button>{candidate.status === "generated" && onSkip && <button className="text-button" disabled={busy || !!running} onClick={onSkip}>跳过此 Candidate</button>}{candidate.status !== "evaluated" && <CandidateAction candidate={candidate} running={running} busy={busy} onRun={onRun} />}</div></article>;
}

function CandidateField({label,children}:{label:string;children:React.ReactNode}) {
  return <section className="candidate-story-block ui-field lines-2"><h4 className="field-label ui-kicker" style={{margin:0}}>{label}</h4><div className="candidate-field-content" style={label==="结果" ? undefined : {height:"calc(1.6em * 2)",overflow:"hidden"}}>{children}</div></section>;
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
  const counts = r.new_critical_failures != null && r.new_ordinary_failures != null ? `新增严重 ${r.new_critical_failures}、普通 ${r.new_ordinary_failures} 个 Bad Case（上限分别为 0、1）` : "新增 Bad Case 明细未采集";
  const classification = result.regression_review ? "；按当前上限核对，最终资格保留保存结论" : "";
  const continued = result.continued_failure_new_critical_question_ids || r.continued_failure_new_critical_question_ids;
  const risk = Array.isArray(continued) && continued.length ? `；持续失败题新增严重风险 ${continued.length} 题，阻断资格` : '';
  const incomplete = result.comparison_complete === false || r.comparison_complete === false ? '；评测执行未完成，比较与资格阻断' : '';
  return `${fixed == null ? "问题修复数未采集" : `修复 ${fixed} 个${result.comparison_version ? "指定目标" : "原问题（历史统计）"}`}；${counts}。${classification}${risk}${incomplete}`;
}

function accountingText(value:any):string {
  if (!value) return "历史费用未完整记录，不能按0元计算";
  const cost=value.cost_estimation;
  return `${value.call_events ?? "未采集"} 次调用记录，${value.unknown_usage_events ?? "未采集"} 次Usage未知；${cost?.status === "estimated" ? `${yuanText(cost.amount, cost.currency) || "费用未知"}（按Usage核算，非账户实扣）` : "完整费用待账单核对"}`;
}
