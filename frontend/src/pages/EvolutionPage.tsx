import { currentQualification } from '../candidateQualification';
import { coreTerm, pagePurpose } from "../helpText";
import { RoundConclusion } from '../components/RoundStrategy';
import { CandidateOverviewTable, CandidateResultSummary, SummaryText, candidateStrategyName, candidateSummary, evaluatedCandidate, QualificationVersions, qualificationLabel, qualificationReasons, sandboxBlock, candidateEvidence, candidateValue } from '../components/AgentStrategySummary';
import { yuanText } from "../components/PipelineFields";
import { judgePresentation } from "../components/judgePresentation";
import { agentDisplayText } from "../display";
import { Icon, IconLabel, IconTile } from "../ui/icons";
import { HoverCard } from "../ui/HoverCard";
import {DStory, DSideEffects, questionText, schemeName, completeResult, storyText, StoryText, recommendationReason, recommendationTradeoff, dProgressLabel, ChangedParameters, storyParameterNames, storyValue, shortQuestionId} from "../components/EvolutionStory";
import { AgentOverview } from "../ui/evolution/AgentOverview";
import { AgentNarrative } from "../ui/evolution/AgentNarrative";
import { useAgentNarrative } from "../ui/evolution/narrative";
import { FinalRecommendation } from "../ui/evolution/FinalRecommendation";
import { EvolutionTimeline } from "../ui/evolution/EvolutionTimeline";
import { QuestionBadge, QuestionList } from "../ui/Primitives";
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
import { ConfirmDialog, Drawer, QuestionDrawer } from "../components/Dialog";
import { useOperation } from "../operation";
import { displayText, narrativeText, baselineName } from "../display";
import { CaseAnswer } from "../components/CaseAnswer";
import { CaseDetails, gateNames } from "./EvaluationPage";

const rootCause = currentRoot;

const archivedExperimentId = "EXP-20261120224619556715";

export function EvolutionPage({ data }: { data: any }) {
  const current = data.optimization;
  const [selection, select] = useState<"current" | "archive" | null>(null);
  const selected = selection ?? (current?.id === archivedExperimentId ? "archive" : "current");
  const [archive, setArchive] = useState<any>(null);
  const [failure, setFailure] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    if (selected !== "archive" || (current?.id === archivedExperimentId && current.baseline_run_id === data.evaluation?.id)) return;
    let active = true;
    setFailure("");
    void getJson<any>(`/api/experiments/${archivedExperimentId}?light=true`).then(async optimization => {
      const baseline = encodeURIComponent(optimization.baseline_run_id);
      const [evaluation, badCases] = await Promise.all([
        detailJson(`/api/evaluations/${baseline}`),
        getJson(`/api/bad-cases?light=true&baseline_id=${baseline}`),
      ]);
      if (active) setArchive({ optimization, evaluation, badCases });
    }).catch(reason => { if (active) setFailure(errorMessage(reason)); });
    return () => { active = false; };
  }, [selected, current?.id, current?.baseline_run_id, data.evaluation?.id, attempt]);

  const unavailable = selected === "current" && current?.id === archivedExperimentId;
  const view = selected === "archive" && (current?.id !== archivedExperimentId || current?.baseline_run_id !== data.evaluation?.id)
    ? archive && { ...data, ...archive }
    : unavailable ? { ...data, optimization: null } : data;
  const selector = <label className="agent-experiment-select">实验
    <select aria-label="选择 Agent 实验" value={selected} onChange={event => select(event.target.value as "current" | "archive")}>
      <option value="current">{current?.id && current.id !== archivedExperimentId ? `当前实验 · ${current.id}` : "当前实验 · 尚无新记录"}</option>
      <option value="archive">旧实验 · {archivedExperimentId}（只读）</option>
    </select>
  </label>;
  if (!view) return <PageShell className="page evolution-page" header={<div className="page-title"><h1>Agent 工作台</h1>{selector}</div>}>
    {failure ? <p role="alert">旧实验读取失败。{failure} <button onClick={() => setAttempt(attempt + 1)}>重试</button></p> : <LoadingSkeleton label="正在读取旧实验及对应 Baseline"/>}
  </PageShell>;
  return <EvolutionWorkspace key={`${selected}:${view.optimization?.id ?? ''}`} data={view} selector={selector}
    readOnly={selected === "archive" || unavailable} archive={selected === "archive"} unavailable={unavailable}/>;
}

function EvolutionWorkspace({ data, selector, readOnly, archive, unavailable }: {
  data: any; selector: React.ReactNode; readOnly: boolean; archive: boolean; unavailable: boolean;
}) {
  const operation = useOperation();
  const [historyOpen, setHistoryOpen] = useState(false);
  const [savedStage, setStage] = usePageTab("evolution", ["overview", "route", "candidate-comparison", "comparison", "review", "candidates", "sandbox", "regression", "recommendation"] as const, "overview");
  const stage = ["candidates","sandbox","comparison"].includes(savedStage) ? "route" : ["candidate-comparison","regression","recommendation"].includes(savedStage) ? "review" : savedStage;
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
  const [rawCandidate, setRawCandidate] = useState<any>();
  const [selectedCandidate, setSelectedCandidate] = useState<any>(null), [candidateReport, setCandidateReport] = useState<any>(null);
  const [reportError,setReportError]=useState('');
  useEffect(()=>{
    setReportError('');const id=selectedCandidate?.result?.evaluation_run_id;
    setCandidateReport(id && selectedCandidate.status==='evaluated'?cachedJson<any>(`/api/evaluations/${id}`) || null:null);
    if(!id || selectedCandidate.status!=='evaluated')return;
    let active=true;void detailJson(`/api/evaluations/${id}`).then(value=>{if(active)setCandidateReport(value);}).catch(reason=>{if(active)setReportError(errorMessage(reason));});
    return()=>{active=false;};
  },[selectedCandidate]);
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
  const [matrixQuestion, setMatrixQuestion] = useState<{ id: string; candidate?: any }>();

  const [comparisonKind,setComparisonKind]=useState<"fixed"|"regression">("regression");
  const refreshed = useRef(new Set<string>());
  const [winnerId, setWinnerId] = useState("");
  const evaluation = data.evaluation || {};
  const narrative = useAgentNarrative(experiment, evaluation);
  const identity = identityKey(data.workspace || data.evaluation);
  const currentIdentity = useRef(identity); currentIdentity.current = identity;
  useEffect(() => { setExperiment(data.optimization?.id ? data.optimization : null); setSelectedCandidate(null); setRawCandidate(undefined); setCandidateReport(null); setSelectedBadCase(null); setComparisonCase(null); setMatrixQuestion(undefined); setWinnerId(""); setSearchOpen(false); setAdvancedOpen(false); setSearchSpace(null); setError(""); setBusy(false); setConfirmationAction(null); }, [identity]);
  useEffect(() => { setExperiment(data.optimization?.id ? data.optimization : null); }, [data.optimization]);
  const [targetCandidate, setTargetCandidate] = useState<any>(null);
  useEffect(() => { setTargetCandidate(null); }, [identity]);
  const badCases = (data.badCases || []).filter((item: any) => item.run_id === evaluation.id);
  const candidates: any[] = experiment?.candidates || [];
  const hover = useHoverPrefetch();
  useDetailPrefetch([
    ...(evaluation.id ? [`/api/evaluations/${evaluation.id}`] : []),
    ...candidates.filter(candidate => candidate.status === "evaluated" && candidate.result?.evaluation_run_id).map(candidate => `/api/evaluations/${candidate.result.evaluation_run_id}`),
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
  const savedRecommendation = experiment?.recommendation?.result || experiment?.recommendation || {};
  const recommendation = { ...savedRecommendation, status: experiment?.recommendation?.status || savedRecommendation.status };
  const keepBaseline = recommendation.status === "Recommended" && !recommendation.recommended_candidate;
  const recordedRecommendation = candidates.find(item => item.id === recommendation.recommended_candidate);
  const invalidRecommendation = currentQualification(recordedRecommendation?.result)?.qualified === false;
  const savedRecommended = invalidRecommendation || recommendation.status && recommendation.status !== "Recommended" ? undefined : recordedRecommendation;
  const confirmation = experiment?.result?.report_confirmation || recommendation.report_confirmation;
  const gate2Correction = experiment?.result?.gate2_audit_correction;
  const decisionStop = experiment?.result?.decision_stop;
  const composite = experiment?.result?.composite || recommendation.composite;
  const compositeSchedule = experiment?.result?.composite_schedule;
  const compositeWaiting = ["scheduled", "waiting", "queued", "running"].includes(compositeSchedule?.status) || !!compositeSchedule?.price_pause?.paused;
  const cycle = experiment?.result?.optimization_cycle;
  const pricePause = [cycle?.price_pause, experiment?.result?.price_pause, compositeSchedule?.price_pause].find(pause => pause?.paused);
  const sandboxPause = pricePause || currentRound.find(candidate => candidate.result?.price_pause?.paused)?.result.price_pause;
  const dWinner = candidates.find(item => item.id === (d?.reasoning?.winner_id || confirmation?.winner_id));
  const orderedCandidates = [...displayedCandidates, ...(d ? [d] : [])];
  const reviewCandidates = [...abc, ...(d ? [d] : [])];
  const budget = experiment?.evaluation_budget || data.optimization?.evaluation_budget || {};
  const budgetKnown = Number.isFinite(budget.used) && Number.isFinite(budget.max);
  const latestRound = experiment?.rounds?.at(-1);
  const agentRule = searchSpace?.rules?.agent;
  const roundSize = agentRule?.candidates_per_round ?? latestRound?.total;
  const reservedForD = budget.reserved_for_d ?? budget.reserved_for_d1;
  const remainingForRound = budgetKnown && Number.isFinite(reservedForD) ? budget.max - budget.used - reservedForD : undefined;
  const staged = experiment?.result?.round_policy?.mode === "full_rounds";
  const canContinue = latestRound?.complete && !confirmation && remainingForRound !== undefined
    && (staged ? remainingForRound > 0 : Number.isFinite(roundSize) && remainingForRound >= roundSize);
  const agentSearchSpace = searchSpace?.search_space && Object.fromEntries(
    Object.entries(searchSpace.search_space).filter(([key]) => !agentRule?.tunable || agentRule.tunable.includes(key))
  ) as typeof searchSpace.search_space;
  const qualified = candidates.filter(item => ["A", "B", "C"].includes(item.reasoning?.candidate_label) && evaluatedCandidate(item) && currentQualification(item.result)?.qualified === true);
  const selectedWinner = qualified.some(item => item.id === winnerId) ? winnerId : recommendation.suggested_winner || qualified[0]?.id || "";
  const batchId = `sandbox-round:${experiment?.id}:${roundNumber}`;
  const batchRunning = operation.operations.some(item => item.id === batchId && item.status === "running");
  const hasRunning = cycle?.status === "running" || compositeWaiting || candidates.some(item => ["running", "queued"].includes(item.status)) || operation.operations.some(item => item.candidateId && item.status === "running") || batchRunning;
  const published = (data.versions || []).some((version:any) => version.status === "active" && version.provenance === "published" && candidates.some(candidate => candidate.id === version.snapshot?.candidate_id));
  const pending = currentRound.filter(item => ["generated", "failed"].includes(item.status));
  const policyBlocked = !!evaluation.requires_policy_upgrade || !!data.workspace?.requires_policy_upgrade;
  const coverage = experiment?.coverage_plan;
  const planningIncomplete = coverage?.status === "incomplete" && !!experiment?.result?.strategy_contract
    && experiment.result.decision_contract_version !== "109c";
  const planningBlocked = planningIncomplete && currentRound.length < 3;
  const triedSandbox = candidates.some(candidate => ["running","queued","evaluated","failed"].includes(candidate.status) || candidate.result?.evaluation_run_id);
  const completePlan = () => void action("零调用补齐本轮规划", () => postJson(`/api/experiments/${experiment.id}/complete-plan`, { binding: coverage.binding }));
  const canBatch = remainingForRound !== undefined && remainingForRound > 0 && !planningBlocked && !policyBlocked && !!pending.length && !confirmation && !hasRunning;
  const executeBatch = async () => {
    const captured = identity; setError("");
    try { await operation.runCandidateBatch({ experimentId: experiment.id, baselineId: evaluation.id, round: roundNumber, candidateIds: pending.map(item => item.id), identity: data.workspace ? identity : undefined }); await refresh(); }
    catch (reason) { if (currentIdentity.current === captured) { setError(errorMessage(reason)); await refresh(); } }
  };
  const requestPaid = (title: string, description: string, execute: () => void) => { if (!readOnly) setConfirmationAction({title, description, execute}); };
  const runBatch = () => requestPaid('运行本轮 A/B/C Sandbox', `Golden ${evaluation.dataset_snapshot?.question_ids?.length ?? evaluation.cases?.length ?? '未采集'} 题，待运行 ${pending.length} 个 Candidate；每题回答+Judge；评测次数 ${budget.used}/${budget.max}${reservedForD ? `，为 D 预留 ${reservedForD} 次` : ""}。Rewrite/MultiQuery/HyDE 启用时有额外模型调用。`, () => void executeBatch());
  const activeOperation = (candidateId: string) => operation.operations.find(item => item.candidateId === candidateId && item.status === "running");
  const processingCases=agentDiagnosisRows(badCases);

  const gateDetails = evaluation.gate_details || [];
  useEffect(() => {
    if (!matrixQuestion) return;
    const { id, candidate } = matrixQuestion;
    const runId = candidate ? completeResult(candidate)?.evaluation_run_id : evaluation.id;
    if (!runId) { setMatrixQuestion(undefined); return; }
    let active = true;
    const read = (run: string) => detailJson<any>(`/api/evaluations/${encodeURIComponent(run)}/cases/${encodeURIComponent(id)}`);
    const match = async () => {
      if (!candidate) return;
      const runs = await Promise.all([evaluation.id, runId].map(id => detailJson<any>(`/api/evaluations/${encodeURIComponent(id)}/comparison-cases`)));
      const [base, current] = runs;
      if (base.id !== evaluation.id || current.id !== runId ||
          !base.dataset_version_id || current.dataset_version_id !== base.dataset_version_id ||
          !base.judge?.evaluation_identity || current.judge?.evaluation_identity !== base.judge.evaluation_identity ||
          !base.config?.knowledge_identity?.corpus_snapshot_id ||
          current.config?.knowledge_identity?.corpus_snapshot_id !== base.config.knowledge_identity.corpus_snapshot_id) {
        throw new Error("评测身份不一致，无法对照");
      }
    };
    void match().then(() => Promise.all([read(evaluation.id), candidate ? read(runId) : null])).then(([before, after]) => {
      if (!active) return;
      if (before.status !== "completed" || after && after.status !== "completed") throw new Error("评测未完成");
      const question = { ...before.question, id };
      const boundSnapshot = { questions: [question] };
      if (after) {
        setComparisonCase({ question_id: id, question: before.case?.question || after.case?.question, before: before.case,
          after: after.case, beforeNotes: before.independent_review_notes, afterNotes: after.independent_review_notes,
          baseline: { config: evaluation.config, dataset_snapshot: boundSnapshot },
          current: { config: candidate.config, dataset_snapshot: boundSnapshot } });
      } else {
        setSelectedBadCase({ question_id: id, result: before.case, dataset_snapshot: boundSnapshot,
          independentReviewNotes: before.independent_review_notes });
      }
      setMatrixQuestion(undefined);
    }).catch(reason => {
      if (active) {
        setSelectedBadCase({ question_id: id, load_error: errorMessage(reason) });
        setMatrixQuestion(undefined);
      }
    });
    return () => { active = false; };
  }, [matrixQuestion, evaluation.id]);
  const snapshot = savedSnapshot(evaluation);
  const refresh = async () => { const captured = identity; const value: any = await getJson("/api/optimization?light=true&planning=true"); if (currentIdentity.current === captured && (!value.current_baseline_id || value.current_baseline_id === evaluation.id)) setExperiment(value.id ? value : null); };
  const polling = !readOnly && (hasRunning || experiment?.result?.optimization_cycle?.status === "running");
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
    if (readOnly) return;
    for (const item of operation.operations) if (item.candidateId && item.status !== "running" && !refreshed.current.has(item.id)) {
      refreshed.current.add(item.id); void refresh();
    }
  }, [operation.operations, readOnly]);

  const action = async (title: string, work: () => Promise<unknown>) => {
    if (readOnly) return;
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
  const missingRoundReview = experiment?.result?.decision_contract_version === '109c'
    && experiment.result.round_conclusions?.[String(roundNumber)]?.status !== 'saved';
  const continueRound = () => requestPaid('生成下一轮建议',
    missingRoundReview ? '先复盘本轮已保存结果，再生成下一轮方案。' : '读取已保存历史实验反馈，生成下一轮方案。',
    () => void action('生成下一轮A/B/C', () => postJson(`/api/experiments/${experiment.id}/continue`)));
  const run = (candidate: any) => candidate.resume_plan?.can_resume === false ? setError(candidate.resume_plan.reason || '当前无法继续，请查看原因') : requestPaid('运行 Candidate Sandbox', '继续完成尚未结束的评测；会产生模型费用。', () => void executeCandidate(candidate));
  const executeCandidate = async (candidate: any) => {
    if (readOnly || !["generated", "failed"].includes(candidate.status) || activeOperation(candidate.id)) return;
    const captured = identity;
    setBusy(true); setError("");
    try { await operation.startEvaluation(`${candidateName(candidate)} · Sandbox 评测`, () => postJson(`/api/candidates/${candidate.id}/run`, { authorize_provider: true }), candidate.id); await refresh(); }
    catch (reason) { if (currentIdentity.current === captured) setError(errorMessage(reason)); }
    finally { if (currentIdentity.current === captured) setBusy(false); }
  };


  const nextRoundBlocker = confirmation ? "实验报告已确认，后续决策进入方案 D。"
    : policyBlocked ? "当前 Baseline 的评测身份需要更新。"
    : hasRunning ? "正在运行当前方案，完成后再评估下一轮。"
    : !latestRound?.complete ? "当前轮尚未保存完整评测。"
    : remainingForRound === undefined ? "保存记录缺少可核对的剩余预算。"
    : !canContinue ? "剩余预算不足以启动下一轮并保留方案 D。"
    : "";
  const dSavedResult = completeResult(d);
  const dComparison = dSavedResult?.winner_comparison;
  const dRule = currentQualification(dSavedResult)?.rule_version || experiment?.result?.qualification_version;
  const dStages = [
    { label: "方案 D 规划", state: d ? "方案已保存" : compositeWaiting ? "等待规划" : "尚无 D 方案",
      id: d?.id || composite?.candidate_id, support: d?.reasoning?.winner_id || composite?.winner_id },
    { label: "D 沙盒评测", state: dSavedResult ? "已保存完整结果" : d ? candidateState(d, false).label : "待 D 规划",
      id: d?.result?.evaluation_run_id, support: d?.result?.evaluation_identity },
    { label: "D 与优胜方案回归", state: dComparison ? "对照已保存" : "未保存逐题对照",
      id: dWinner?.result?.evaluation_run_id, support: dComparison?.status },
    { label: "推荐决策", state: savedRecommended ? `已推荐 ${schemeName(savedRecommended)}` : keepBaseline ? "已决定保持 Baseline" : "等待保存的决策",
      id: savedRecommended?.id, support: recommendation.final_decision?.reason },
  ];
  const evaluatedCount = currentRound.filter(item => item.status === "evaluated").length;
  const roundComplete = !!currentRound.length && currentRound.every(item => item.status === "skipped" || item.status === "evaluated" && item.result?.evaluation_complete !== false);
  const recommendationTitle=invalidRecommendation ? "保存的推荐方案未通过当前资格" : recommendation.status === "Recommended" && !recommendation.recommended_candidate ? "保存推荐：保持 Baseline" : !roundComplete ? currentRound.some(c=>c.status === "failed") ? "本轮实验尚未完成 · 有运行失败" : "本轮实验尚未完成" : recommendation.status==="No Qualified Candidate" ? "保存结论：本轮暂无合格方案" : recommendation.status === "Needs Report Confirmation" ? "待报告确认（Gate 2）" : recommendation.recommended_candidate ? savedRecommended ? `保存推荐：${candidateName(savedRecommended)}` : "已有保存推荐，Candidate 详情未采集" : currentRound.some(item=>typeof currentQualification(item.result)?.qualified !== "boolean") ? "资格或推荐结论未采集" : qualified.length ? "已有合格 Candidate，等待保存的最终决策" : "推荐结论未采集";
  const activeCandidate = currentRound.find(candidate => ["running", "queued"].includes(candidate.status) || candidate.result?.price_pause?.paused);
  const steps = [
    { label: "诊断", state: evaluation.status === "completed" ? "completed" : "blocked", detail: evaluation.status === "completed" ? `${evaluation.result?.bad_case_count ?? badCases.length} 个 Bad Case 已读取` : "等待有效 Baseline", onSelect: openDiagnosis },
    { label: "生成 A/B/C", state: planningIncomplete && (!roundComplete || Number.isFinite(roundSize) && currentRound.length < roundSize) || experiment?.status === "generating" ? "current" : experiment?.status === "failed" ? "blocked" : currentRound.length ? "completed" : "pending", detail: experiment?.status === "failed" ? "本轮 Candidate 生成失败" : planningIncomplete && (!roundComplete || Number.isFinite(roundSize) && currentRound.length < roundSize) ? `${currentRound.length} 个 Candidate · 有覆盖缺口` : `${currentRound.length} 个 Candidate`, onSelect: () => setStage("route") },
    { label: "Candidate A/B/C/D", state: planningIncomplete && (!roundComplete || Number.isFinite(roundSize) && currentRound.length < roundSize) ? "current" : currentRound.length ? "completed" : "pending", detail: `${currentRound.length} 个 Candidate · ${dProgressLabel(experiment)}`, onSelect: () => setStage("route") },
    { label: "Sandbox", state: sandboxPause || hasRunning ? "current" : currentRound.some(candidate => candidate.status === "failed") ? "blocked" : roundComplete ? "completed" : "pending", detail: activeCandidate ? `${activeCandidate.reasoning?.candidate_label} ${candidateProgress(activeCandidate, activeOperation(activeCandidate.id), sandboxPause)}` : sandboxPause ? "已暂停" : currentRound.length ? `${evaluatedCount}/${currentRound.length} 已评测` : "尚无待评测 Candidate", onSelect: () => setStage("route") },
    { label: "Regression Check", state: roundComplete ? "completed" : "pending", detail: roundComplete ? `${evaluatedCount} 个 Candidate 已保存判定` : "等待完整评测", onSelect: () => setStage("review") },
    { label: "最终推荐", state: savedRecommended && confirmation ? "completed" : roundComplete ? "current" : "pending", detail: savedRecommended && confirmation ? schemeName(savedRecommended) : confirmation ? "等待组合 Candidate D" : "等待完整报告与人工确认", onSelect: () => setStage("review") },
  ] as const;
  const evolutionModel = buildEvolutionModel(experiment, evaluation.config, metric => gateNames[metric] ?? metric, schemeName);
  const candidateViews = [...evolutionModel.rounds.flatMap(round => round.candidates), ...(evolutionModel.d ? [evolutionModel.d] : [])];
  const qualifiedViews = candidateViews.filter(candidate => candidate.complete && candidate.qualified === true);
  const chosenView = candidateViews.find(candidate => candidate.id === savedRecommended?.id && candidate.qualified !== false);
  const runnerUpView = candidateViews.find(candidate => candidate.id === evolutionModel.winnerId && candidate.id !== chosenView?.id) || null;
  const production = data.overview?.production || data.versions?.find((item: any) => item.status === "active");
  const productionReleased = production?.provenance === "published" && !!savedRecommended && production.snapshot?.candidate_id === savedRecommended.id && production.snapshot?.human_release?.decision === "approved";
  const phaseDetails = [...new Set(steps.filter(step => step.state === "current" || step.state === "blocked").map(step => step.detail))].join(" · ");
  const agentStatus = hasRunning || busy ? `${activeCandidate ? `${schemeName(activeCandidate)} · ${candidateProgress(activeCandidate, activeOperation(activeCandidate.id), sandboxPause)}` : "Agent 评测中"} · ${dProgressLabel(experiment)}${savedRecommended ? ` · 当前保存推荐：${schemeName(savedRecommended)}` : ""}` : keepBaseline ? '评测已完成，保持 Baseline' : productionReleased ? schemeName(savedRecommended).replace(/^Round \d+ · /, "") : savedRecommended ? `推荐 ${schemeName(savedRecommended)}，待人工发布 · ${dProgressLabel(experiment)}` : sandboxPause ? "已暂停，进度已保存" : `${latestRound ? `Round ${latestRound.round} · ${latestRound.evaluated ?? "未知"}/${latestRound.total ?? "未知"} · ` : ""}${phaseDetails || "等待生成优化 Candidate"}${!budgetKnown && experiment ? " · 预算尚未同步" : ""}`;

  const qualificationRules = searchSpace?.qualification_description;
  const regressionSummary = <section className="panel regression-check"><div className="section-head"><h2>回归检查 · 各方案</h2></div><div className="table-scroll regression-summary-table"><DataTable><colgroup><col style={{width:'25%'}}/>{[15,15,15,15,15].map((width,index)=><col key={index} style={{width:`${width}%`}}/>)}</colgroup><thead><tr>{["方案","修好","新增严重","新增普通","回归检查","正式资格"].map((label,index)=><th key={label} className={index>0 && index<4?"num":undefined}>{label}</th>)}</tr></thead><tbody>{reviewCandidates.map(candidate=>{const review=candidate.result?.regression_review;const regression=candidate.result?.regression;const view=candidateViews.find(item=>item.id===candidate.id);const complete=view?.complete;return <tr key={candidate.id} className={complete && view.qualified===true ? "qualified" : undefined}><td><button className="regression-candidate" onClick={()=>setSelectedCandidate(candidate)}>{schemeName(candidate)}</button></td><td className="num">{review?.fixed_count ?? "未知"}</td><td className="num">{complete ? review?.new_critical_failures ?? regression?.new_critical_failures ?? "未知" : "未判定"}</td><td className="num">{complete ? review?.new_ordinary_failures ?? regression?.new_ordinary_failures ?? "未知" : "未判定"}</td><td><TableVerdict value={complete && ["PASS","FAIL"].includes(candidate.result?.regression?.status) ? candidate.result.regression.status === "PASS" : undefined} pass="通过" fail="未通过"/></td><td>{complete ? qualificationLabel(candidate.result) : "未判定"}</td></tr>})}{!reviewCandidates.length && <tr><td colSpan={6}>尚无 Candidate Regression 结论</td></tr>}</tbody></DataTable></div><p className="regression-limit-note">{qualificationRules ? `当前资格要求：${qualificationRules}。` : "资格结论取自后端评测记录。"}单独 Regression 结论见 Candidate 详情。</p></section>;
  return <PageShell className="page evolution-page" header={<><div className="page-title"><div><h1><IconTile name="agent" />Agent 工作台</h1><p className="ui-kicker page-purpose">{pagePurpose.evolution}</p></div><div className="header-actions">{selector}{hasRunning && !readOnly && <button className="secondary" onClick={() => setStage("route")}>查看 Sandbox 进度</button>}</div></div></>} tabs={<div className="tabs"><button data-label="概览" aria-pressed={stage === "overview"} className={stage === "overview" ? "active" : ""} onClick={() => setStage("overview")}>概览</button><button data-label="进化路线" aria-pressed={stage === "route"} className={stage === "route" ? "active" : ""} onClick={() => setStage("route")}>进化路线</button><button data-label="回归与推荐" aria-pressed={stage === "review"} className={stage === "review" ? "active" : ""} onClick={() => setStage("review")}>回归与推荐</button></div>} resetKey={stage}>
    {archive && <p className="workbench-status">旧实验只读 · {experiment?.id} · Baseline {evaluation.id}</p>}
    {unavailable && <p className="workbench-status">当前 Baseline 尚无保存的新实验。</p>}


    <ConfirmDialog open={!!confirmationAction} onOpenChange={open => !open && setConfirmationAction(null)} title={confirmationAction?.title || "确认操作"} onConfirm={() => { const next = confirmationAction; setConfirmationAction(null); next?.execute(); }}><div className="muted-prose"><TruncatedText lines={3}>{confirmationAction?.description}</TruncatedText></div></ConfirmDialog>
    {!readOnly && <PricePauseNotice pause={pricePause} experimentId={experiment?.id} onChanged={refresh} />}
    {!readOnly && candidates.filter(candidate => !pricePause && candidate.result?.price_pause?.paused).map(candidate => <PricePauseNotice key={candidate.id} pause={candidate.result.price_pause} evaluationId={candidate.result.evaluation_run_id} onChanged={refresh} />)}
    {cycle?.status === "qualified" && !confirmation && <p className="workbench-status" role="status">本轮 A/B/C 已完成，等待人工确认报告与 Winner；确认后才能生成组合 Candidate D。</p>}
    {cycle?.status === "budget_exhausted" && <p className="workbench-status" role="status">优化循环已停止：已评测 {budget.used} / {budget.max} 次，剩余 {Math.max(0, budget.max - budget.used)} 次{reservedForD ? `（其中 ${reservedForD} 次留给 D）` : ""}。剩余次数不足以运行完整 A/B/C；只有合格 Winner 经人工确认后才能进入 D。</p>}
    {policyBlocked && <p className="error-notice">当前 Baseline 评测版本身份与运行代码不兼容，真实 Agent 启动已阻断，旧实验只读。全部 Bad Case 保留在优化规划中；请先到 Baseline 查看身份预检，核对历史评测与当前规则的兼容性；需要新版评分时使用保存回答判分，不自动重新生成。</p>}
{!readOnly && <div className="header-actions agent-secondary-actions">{triedSandbox ? null : planningBlocked && !published ? <button className={stage === "review" ? "secondary" : "primary"} disabled={busy || policyBlocked || hasRunning || !!confirmation} onClick={completePlan}>补齐本轮规划（不收费）</button> : pending.length ? <button className={stage === "review" ? "secondary" : "primary"} disabled={busy || !canBatch} onClick={() => void runBatch()}><Play size={15} />{batchRunning ? "本轮 Sandbox 运行中" : "运行本轮 A/B/C Sandbox"}</button> : <button className={stage === "review" ? "secondary" : "primary"} disabled={policyBlocked || busy || hasRunning || evaluation.status !== "completed" || (!!abc.length && !canContinue) || (!badCases.length && !experiment?.result?.monitoring_context)} onClick={() => void (canContinue ? continueRound() : generate())}><Play size={15} />{busy ? "处理中…" : canContinue ? "继续优化下一轮" : abc.length ? "本轮 Candidate 已生成" : "生成 A / B / C"}</button>}{!published && planningIncomplete && triedSandbox && <button className="secondary" disabled={busy || policyBlocked || hasRunning || !!confirmation} onClick={completePlan}>补齐本轮规划（不收费）</button>}{canBatch && triedSandbox && <button className="secondary" disabled={busy} onClick={() => void runBatch()}>运行本轮 A/B/C Sandbox</button>}{triedSandbox && canContinue && !pending.length && <button className="primary" disabled={policyBlocked || busy || hasRunning || evaluation.status !== "completed"} onClick={() => continueRound()}><Play size={15} />{busy ? "处理中…" : "继续优化下一轮"}</button>}</div>}
    {!readOnly && !confirmation && triedSandbox && !canContinue && nextRoundBlocker && <p className="workbench-status">{nextRoundBlocker}</p>}
    <Drawer className="workbench-drawer" open={historyOpen} onOpenChange={setHistoryOpen} title="历史实验 · 原 Candidate 与结果只读"><div className="drawer-body"><div className="candidate-cards">{abc.filter(item => (item.reasoning?.round || 1) < roundNumber).map(candidate => <CandidateCard key={candidate.id} experiment={experiment} candidate={candidate} includeRound readOnly baseline={evaluation.config || {}} busy={true} onDetail={()=>{setHistoryOpen(false);setSelectedCandidate(candidate);}} targets={targetRows(candidate,badCases)} onTargets={()=>{setHistoryOpen(false);setTargetCandidate(candidate);}} onRun={()=>void run(candidate)} />)}</div></div></Drawer>
    {error && <p ref={errorRef} tabIndex={-1} className="error-notice" role="alert">{error}</p>}

    {experiment?.result?.generation_status==='no_candidates' && <p className="workbench-status" role="status">本轮没有合法 Candidate，不能运行 Sandbox；未生成不代表优化成功。</p>}
    {experiment?.result?.rejected_candidates?.length>0 && <><p className="workbench-status">本轮保留 {currentRound.length} 个合法 Candidate，拒绝 {experiment.result.rejected_candidates.length} 个 Candidate；拒绝项不会进入 Sandbox。</p></>}
    <MechanismDecisions result={experiment?.result} round={displayRound}/>
    {decisionStop && <details className="workbench-status" open>
      <summary>{decisionStop.reason}</summary>
      <ul>{Object.values(decisionStop.questions || {}).map((row: any) => <li key={row.display_question_id}>
        {row.display_question_id} · {row.fault.stage} · {row.reason} · 建议{row.next_action}
      </li>)}</ul>
    </details>}
    {!decisionStop && experiment?.result?.generation_status==='insufficient_evidence' && <p className="workbench-status" role="status">Candidate 依据不足：{experiment.result.insufficient_evidence || '暂无足够依据生成合格优化假设；待核实原始证据，不补造A/B/C。'}</p>}
    {data.workspace?.baseline_unavailable_reason && <p className="error-notice">{data.workspace.baseline_unavailable_reason}</p>}
    <p className="agent-identity sr-only">{evaluation.id ? `${archive ? "关联" : "当前"} Baseline：${baselineName(evaluation)}` : "当前有效 Baseline 尚未就绪。"}</p>

    {narrative && <AgentNarrative experiment={experiment} evaluation={evaluation} data={narrative} stage={stage} released={productionReleased}/>}
    {stage === "overview" && <AgentOverview experiment={experiment || data.optimization} model={{...evolutionModel, budget: budgetKnown ? budget : null}} evaluation={evaluation} chosenId={chosenView?.id} released={productionReleased} status={agentStatus} cases={processingCases} onCase={setSelectedBadCase}/>}
    {stage === "route" && <div className="route-timeline"><EvolutionTimeline key={experiment?.id} model={evolutionModel} experiment={experiment} onRoundChange={setRoundSelection} renderCandidate={id=>{const candidate=candidates.find(c=>c.id===id);return <CandidateCard key={id} experiment={experiment} route routeWinner={id===evolutionModel.winnerId && currentQualification(candidate.result)?.qualified !== false} candidate={candidate} readOnly={readOnly} primaryRun={id===displayedCandidates.find(item=>['generated','failed'].includes(item.status))?.id} baseline={evaluation.config || {}} onDetail={()=>setSelectedCandidate(candidate)} onSkip={()=>void action('跳过未运行 Candidate',()=>postJson(`/api/candidates/${id}/skip`,{actor:'当前用户'}))} running={activeOperation(id)} busy={busy || planningBlocked || policyBlocked || hasRunning || !!confirmation} targets={targetRows(candidate,badCases)} onTargets={()=>setTargetCandidate(candidate)} onRun={()=>void run(candidate)}/>;}} sandbox={round => <button className="text-button" onClick={() => { setRoundSelection(round); setStage("review"); }}>查看沙盒评测和逐题回归</button>}
      questionText={id => questionText(id, evaluation, badCases)} onOpen={id => setSelectedCandidate(candidates.find(candidate => candidate.id === id))} >
      <section className="d-timeline" aria-label="Candidate D 决策">
        <Section title="报告确认（Gate 2）">
          <p>{confirmation ? `已确认优胜方案 ${schemeName(dWinner, confirmation.winner_id)}` : "等待已保存的报告确认"}</p>
          {gate2Correction && <p>已授权确认，审计字段后补</p>}
          {confirmation && <details><summary>查看确认依据</summary><dl className="report-grid">
            <div><dt>实验</dt><dd>{experiment?.id}</dd></div>
            <div><dt>确认时间</dt><dd>{confirmation.confirmed_at || "未记录"}</dd></div>
            <div><dt>规则版本</dt><dd>{confirmation.rule_version || experiment?.result?.qualification_version || "未记录"}</dd></div>
            {gate2Correction && <div><dt>审计更正</dt><dd>审批 {gate2Correction.original_approval.id} · {gate2Correction.corrected_by} · {gate2Correction.corrected_at}。{gate2Correction.reason}</dd></div>}
          </dl><a href="#versions">查看发布页的审批记录</a></details>}
        </Section>
        <ol className="d-stage-records" aria-label="D 的保存记录">
          {dStages.map(stage => <li key={stage.label}><details>
            <summary><strong>{stage.label}</strong> · {stage.state}</summary>
            <dl className="report-grid">
              <div><dt>关联记录</dt><dd>{stage.id || "未记录"}</dd></div>
              <div><dt>依据</dt><dd>{stage.support || "未记录"}</dd></div>
              <div><dt>适用资格规则</dt><dd>{dRule || "未记录"}</dd></div>
            </dl>
          </details></li>)}
        </ol>{evaluatedCandidate(d) && <Section title="组合方案 D 的四层结论">
        <dl className="candidate-four-layers">
          <div><dt>正式资格</dt><dd><QualificationVersions result={d.result}/></dd></div>
          <div><dt>实验效果</dt><dd><CandidateResultSummary result={d.result}/></dd></div>
          <div><dt>证据可信度</dt><dd>{candidateEvidence(d, experiment)}</dd></div>
          <div><dt>推荐价值</dt><dd>{candidateValue(d, experiment)}</dd></div>
        </dl>
      </Section>}<DStory experiment={experiment} evaluation={evaluation} badCases={badCases} onReport={d ? ()=>setSelectedCandidate(d) : undefined} onRecommendation={()=>setStage("review")}/>{d?.status === "evaluated" && experiment?.result?.round_conclusions?.D && <RoundConclusion experiment={experiment} round="D"/>}{!readOnly && d && d.status !== "evaluated" && <CandidateAction primary candidate={d} running={activeOperation(d.id)} busy={busy || policyBlocked || hasRunning} onRun={()=>void run(d)}/>}</section>
    </EvolutionTimeline></div>}

    {stage === "review" && <>
      <CandidateOverviewTable key={experiment?.id} evaluation={evaluation} candidates={reviewCandidates}
        rounds={experiment?.rounds || []} experiment={experiment} selectedRound={displayRound} onRoundChange={setRoundSelection} targets={badCases} onOpen={setSelectedCandidate}
        onQuestion={(id, candidate) => setMatrixQuestion({ id, candidate })} onAdvanced={() => setAdvancedOpen(true)}/>
      {matrixQuestion && <p role="status">正在读取 {shortQuestionId(matrixQuestion.id)} 的保存记录…</p>}
      {chosenView ? <><FinalRecommendation chosen={chosenView} runnerUp={runnerUpView}
        baselineCorrect={typeof evaluation.result?.total === "number" && typeof evaluation.result?.bad_case_count === "number" ? evaluation.result.total - evaluation.result.bad_case_count : null}
        reason={recommendationTradeoff(experiment)}
        totalCandidates={candidateViews.filter(candidate => candidate.complete && candidate.qualified !== null && candidate.qualificationVersion === chosenView.qualificationVersion).length}
        qualifiedCount={qualifiedViews.filter(candidate => candidate.qualificationVersion === chosenView.qualificationVersion).length}
        regressionSummary={regressionSummary}
        others={candidateViews.filter(item=>item.id!==chosenView.id && item.id!==runnerUpView?.id)}
        questionText={id => questionText(id, evaluation, badCases)}
        onRelease={() => { location.hash = "versions"; }}
        releaseLabel={productionReleased || savedRecommended?.release_state?.human_release ? "查看发布记录" : "去发布"}
        onOpen={id => setSelectedCandidate(candidates.find(candidate => candidate.id === id))}
      /></> : <><Section title={recommendation.status === "Needs Report Confirmation" ? "报告确认（Gate 2）" : "最终推荐"}><h3>{recommendationTitle}</h3>
      {recommendation.status === "Needs Report Confirmation" && recommendation.suggested_winner &&
        <p>暂定优胜方案 · {schemeName(candidates.find(candidate => candidate.id === recommendation.suggested_winner), recommendation.suggested_winner)}</p>}
      {keepBaseline ? <ol className="ui-fin-reason">
        <li>一、质量：Baseline 答对 {typeof evaluation.result?.total === 'number' && typeof evaluation.result?.bad_case_count === 'number' ? evaluation.result.total-evaluation.result.bad_case_count : '未知'} / {evaluation.result?.total ?? '未知'}。{recommendationReason(experiment)}</li>
        <li>二、安全：Baseline 上线门槛 {metricText(evaluation.result,'gates')}；各 Candidate 的门槛结果见下表。</li>
        <li>三、速度：Baseline 中位耗时 {metricText(evaluation.result,'latency_p50_seconds')}；最慢耗时 {metricText(evaluation.result,'latency_p99_seconds')}。</li>
        <li>四、回归：候选修好和新增问题见下表；修好不能抵消新增 Bad Case，本轮不推荐 Candidate。</li>
      </ol> : <div className="muted-prose"><TruncatedText lines={3}>{storyText(recommendationReason(experiment))}</TruncatedText></div>}</Section>{regressionSummary}{keepBaseline && <Section title="落选原因"><div className="candidate-rejections">{reviewCandidates.map(candidate=><button type="button" key={candidate.id} onClick={()=>setSelectedCandidate(candidate)}><strong>{schemeName(candidate)}</strong><span>{qualificationExplanation(candidate)}</span><Icon name="go" size={14}/></button>)}</div></Section>}</>}
{!chosenView && confirmation && <p>人工报告确认已完成。</p>}{!readOnly && confirmation && !d && (!composite || composite.status === 'failed') && !compositeWaiting && <button className="secondary" disabled={busy || policyBlocked || hasRunning} onClick={()=>requestPaid("生成智能组合建议","在 Winner 基础上融合",()=>void action("生成智能组合建议",()=>postJson(`/api/experiments/${experiment.id}/composite`,{authorize_provider:true})))}>{composite?.status === 'failed' ? '重新生成 Candidate D' : '生成智能组合建议'}</button>}
{!readOnly && !confirmation && qualified.length > 0 && abc.every(item => item.status === "skipped" || item.status === "evaluated" && item.result?.evaluation_complete !== false) && <div className="review-batch"><label>人工确认 · 确认 A/B/C 报告并选择合格 Winner<FilterButtons label="选择合格 Winner" value={selectedWinner} onChange={setWinnerId} options={qualified.map(candidate=>({value:candidate.id,label:candidateName(candidate)}))} /></label><button className="primary" disabled={busy || policyBlocked} onClick={() => requestPaid("确认报告与 Winner", "确认已保存的 A/B/C 报告并记录人工选择。", () => void action("确认 A/B/C 报告", () => postJson(`/api/experiments/${experiment.id}/recommendation`, { candidate_id: selectedWinner, actor: "human" })))}>确认报告与 Winner</button></div>}
</>}
    <QuestionDrawer className="workbench-drawer" open={!!comparisonCase} onOpenChange={open=>!open && setComparisonCase(null)} questionLabel={comparisonCase?.question_id && shortQuestionId(comparisonCase.question_id)}><div className="drawer-body bad-case-details">{comparisonCase && <><section className="candidate-card drawer-section"><h3>问题与正式判定</h3><CaseAnswer text={comparisonCase.question || "历史未保存问题"}/><p>Baseline（{coreTerm.baseline}）{comparisonCase.before?.passed===true?"通过":comparisonCase.before?.passed===false?"未通过":"未采集"} → Candidate（候选方案）{comparisonCase.after?.passed===true?"通过":comparisonCase.after?.passed===false?"未通过":"未采集"} · {comparisonCase.after?.severity==="critical"?"严重":comparisonCase.after?.severity==="ordinary"?"普通":"严重程度未采集"}</p></section><section className="candidate-card drawer-section"><h3>参考答案</h3><CaseAnswer text={comparisonCase.baseline?.dataset_snapshot?.questions?.find((row: any) => (row.id || row.question_id) === comparisonCase.question_id)?.reference_answer || "未保存参考答案"}/></section><section className="candidate-card drawer-section"><h3>Baseline 回答</h3><CaseAnswer text={comparisonCase.before?.model_answer || "历史未保存回答"} final={comparisonCase.before?.programmatic_metrics?.retrieval_trace?.final ?? comparisonCase.before?.retrieved_chunks ?? []}/><p>{coreEvidence(comparisonCase.before || {})}</p></section><section className="candidate-card drawer-section"><h3>Candidate 回答</h3><CaseAnswer text={comparisonCase.after?.model_answer || "历史未保存回答"} final={comparisonCase.after?.programmatic_metrics?.retrieval_trace?.final ?? comparisonCase.after?.retrieved_chunks ?? []}/><p>{coreEvidence(comparisonCase.after || {})}</p></section>{[["Baseline",comparisonCase.before,comparisonCase.baseline],["Candidate",comparisonCase.after,comparisonCase.current]].map(([label,item,run])=><StoryDisclosure className="candidate-card drawer-section" key={label} label={<>{label} · 逐题证据</>}><CaseDetails item={item || {}} snapshot={run?.dataset_snapshot || {}} config={run?.config || {}} gates={run?.gate_details || []}/></StoryDisclosure>)}
      {Array.isArray(comparisonCase.beforeNotes) && <IndependentReviewNotes baseline={comparisonCase.beforeNotes} candidate={comparisonCase.afterNotes}/>}
    </>}</div></QuestionDrawer>
    <Drawer className="workbench-drawer" open={advancedOpen} onOpenChange={setAdvancedOpen} title="沙盒评测 · 高级指标">
      <div className="drawer-body">
        <p>检索对照来自各次评测保存的对照统计（<code>comparison_metrics</code>）。各指标只统计有对应检索记录的题，具体题数未单独保存。</p>
        <div className="table-scroll"><DataTable>
          <thead><tr><th>指标</th><th className="num">Baseline</th>{orderedCandidates.map(candidate => <th className="num" key={candidate.id}>{schemeName(candidate)}</th>)}</tr></thead>
          <tbody>{[
            ["正向正确性", "positive_correctness"], ["消融正确性", "ablation_correctness"], ["综合分", "overall_score"],
            ["首字延迟（TTFT）", "ttft_seconds"], ["输入 Token", "input_tokens"], ["输出 Token", "output_tokens"],
            ["对照统计 · 前 K 条召回率（%）", "recall_at_k"], ["对照统计 · 前 K 条相关比例（%）", "precision_at_k"],
            ["平均倒数排名（MRR）", "mrr"], ["费用（保存估算）", "token_cost"],
          ].filter(([,key]) => [evaluation, ...orderedCandidates].some(source => {
            const result = source.result;
            return key === "token_cost" ? billedCostText(result?.comparison_metrics).startsWith("¥ ")
              : Number.isFinite(metricValue(result, key));
          })).map(([label, key]) => <tr key={key}>
            <th scope="row">{label}</th>
            {[evaluation, ...orderedCandidates].map((source, index) => <td key={index === 0 ? "baseline" : source.id} className="num">
              {key === "token_cost" && !billedCostText(source.result?.comparison_metrics).startsWith("¥ ") ? "未采集" : metricText(source.result, key)}
            </td>)}
          </tr>)}</tbody>
        </DataTable></div>
      </div>
    </Drawer>
    <Drawer className="workbench-drawer" open={!!selectedCandidate} onOpenChange={open=>!open && setSelectedCandidate(null)} title={`${candidateName(selectedCandidate)} · Candidate 详情`}><div className="drawer-body story-details">{selectedCandidate && <>
      {selectedCandidate.resume_plan && <Section title="运行进度与费用"><p>已完成 {selectedCandidate.resume_plan.completed ?? selectedCandidate.result?.completed}/{selectedCandidate.resume_plan.total ?? selectedCandidate.result?.total} · 可复用 {selectedCandidate.resume_plan.reusable ?? "待核"} 题</p><div className="muted-prose"><TruncatedText lines={3}>{selectedCandidate.resume_plan.can_resume ? `仅补 ${selectedCandidate.resume_plan.pending_answers} 次回答、${selectedCandidate.resume_plan.pending_judges} 次Judge；另计Embedding/Rerank，启动前须付费确认。` : selectedCandidate.resume_plan.reason}</TruncatedText></div><p>费用：{accountingText(selectedCandidate.result?.request_accounting)}</p></Section>}
      <Section title="优化目标"><p>评测执行：{selectedCandidate.status === "evaluated" ? "已完成" : selectedCandidate.status === "failed" ? "运行失败" : ["running","queued"].includes(selectedCandidate.status) ? "运行中" : "未运行"} · Candidate 资格：{selectedCandidate.status === "evaluated" ? metricText(selectedCandidate.result,"qualification") : "未判定"} · 发布资格：{selectedCandidate.status === "evaluated" ? metricText(selectedCandidate.result,"release_qualification") : "未判定"} · Hard Gate：{selectedCandidate.result?.evaluation_complete === false ? "未完成" : selectedCandidate.result?.gates?.passed === true ? "通过" : selectedCandidate.result?.gates?.passed === false ? "未通过" : "未运行"}</p>{targetRows(selectedCandidate,badCases).map(row=><div key={row.id}><span className="muted">{questionLabel(row.question_id)} · {caseData(row).diagnostic_view?.diagnosis_category || "分类未知"}</span><p>{caseData(row).question}</p></div>)}{!targetRows(selectedCandidate,badCases).length && <p>未匹配当前技术优化目标，原始引用保留在高级审计。</p>}</Section>
      <Section title="逐题追踪"><div className="review-filters" aria-label="Regression 案例类型"><button aria-pressed={comparisonKind==="regression"} onClick={()=>setComparisonKind("regression")}>新增 Bad Case</button><button aria-pressed={comparisonKind==="fixed"} onClick={()=>setComparisonKind("fixed")}>原问题修复</button></div><CandidateCaseComparison candidates={[selectedCandidate]} baselineId={evaluation.id} kind={comparisonKind} onCompare={setComparisonCase} onSelect={row=>setSelectedBadCase({question_id:row.question_id,result:row})}/></Section>
      {reportError && <p role="alert">逐题结果读取失败：{reportError}</p>}
      {selectedCandidate.status==='evaluated' && selectedCandidate.result?.evaluation_run_id && !candidateReport && !reportError && <LoadingSkeleton label="正在读取保存的逐题结果"/>}
      {candidateReport?.cases?.length>0 && <Section title="逐题结果"><div className="table-scroll candidate-saved-cases"><DataTable><thead><tr><th>问题</th><th>判定</th><th>诊断</th></tr></thead><tbody>{candidateReport.cases.map((row:any)=><tr key={row.question_id} role="button" tabIndex={0} onClick={()=>setSelectedBadCase({question_id:row.question_id,result:row,dataset_snapshot:candidateReport.dataset_snapshot})} onKeyDown={event=>{if(event.key==='Enter')setSelectedBadCase({question_id:row.question_id,result:row,dataset_snapshot:candidateReport.dataset_snapshot});}}><td><TruncatedText lines={1}>{row.question}</TruncatedText></td><td><TableVerdict value={row.passed}/></td><td>{row.diagnostic_view?.diagnosis_category || '未知'}</td></tr>)}</tbody></DataTable></div></Section>}
      <Section title="Candidate 内容"><p>{storyText(selectedCandidate.reasoning?.core_idea || selectedCandidate.reasoning?.hypothesis)}</p><StrategyPresentation reasoning={selectedCandidate.reasoning}/>{selectedCandidate.reasoning?.proposal && <p>{storyText(selectedCandidate.reasoning.proposal)}</p>}{selectedCandidate.reasoning?.why && <p>{storyText(selectedCandidate.reasoning.why)}</p>}{selectedCandidate.reasoning?.expected_improvement && <p>{storyText(selectedCandidate.reasoning.expected_improvement)}</p>}{selectedCandidate.reasoning?.evidence_assertions?.map((row:any,i:number)=><p key={i}>{storyText(row.observation)}</p>)}</Section>
      <Section title="参数差异" action={<button className="secondary" onClick={() => setSearchOpen(true)}>查看可调参数</button>}><ConfigDiff base={evaluation.config || {}} candidate={selectedCandidate}/></Section>
      <Section title="真实实验结果"><QualificationVersions result={selectedCandidate.result}/><p>{storyText(qualificationExplanation(selectedCandidate))}</p><p>{selectedCandidate.status === "evaluated" ? regressionText(selectedCandidate.result) : "没有完整 Sandbox，Regression 结论未判定。"}</p><p>Regression Check：{metricText(selectedCandidate.result,"regression")} · 目标修复 {metricText(selectedCandidate.result,"target_bad_cases_fixed")} · 净改善 {metricText(selectedCandidate.result,"net_improvement")}</p>{selectedCandidate.result?.evaluation_complete !== false && selectedCandidate.result?.regression_interpretation && <p>{selectedCandidate.result.regression_review ? qualificationRules : selectedCandidate.result.regression_interpretation}</p>}{selectedCandidate.result?.evaluation_complete === false ? <p>完整评测后判定修复与退化；历史部分比较保留在高级审计。</p> : <p>已修复：{(selectedCandidate.result?.all_fixed_question_ids || []).map(questionLabel).join("、") || "未采集"} · 新增 Bad Case：{(selectedCandidate.result?.new_regression_question_ids || []).map(questionLabel).join("、") || "未采集"}</p>}</Section>
      {selectedCandidate.reasoning?.candidate_label === "D" && <Section title="组合来源与冲突"><div className="muted-prose"><TruncatedText lines={3}>基础 Winner：{candidateName(candidates.find(item=>item.id === selectedCandidate.reasoning.winner_id))}</TruncatedText></div>{(selectedCandidate.reasoning.sources || []).map((source:any,index:number)=><p key={source.candidate_id || index}>{(source.source_candidates || [source.candidate_id]).filter(Boolean).map((id:string)=>schemeName(candidates.find(item=>item.id===id),id)).join("、") || "来源 Candidate 待核对"} · <StoryText value={source.why_merge || source.reason}/></p>)}<div className="muted-prose"><TruncatedText lines={3}>冲突：{selectedCandidate.reasoning.conflicts ? Object.keys(selectedCandidate.reasoning.conflicts).join("、") || "无冲突" : "未采集"}</TruncatedText></div></Section>}
      {selectedCandidate.reasoning?.candidate_label==='D' && <Section title="副作用检查"><DSideEffects changes={selectedCandidate.reasoning.changes || []}/></Section>}
      <Section title="保存记录">
        <dl className="report-grid"><div><dt>实验</dt><dd>{experiment?.id || "未记录"}</dd></div>
          <div><dt>候选方案</dt><dd>{selectedCandidate.id}</dd></div>
          <div><dt>沙盒评测</dt><dd>{selectedCandidate.result?.evaluation_run_id || "未记录"}</dd></div></dl>
        <button className="text-button" onClick={() => setRawCandidate(selectedCandidate)}>查看原始记录</button>
      </Section>


    </>}</div></Drawer>
    <Drawer open={!!rawCandidate} onOpenChange={open => !open && setRawCandidate(undefined)} title="方案原始记录">
      {rawCandidate && <div className="drawer-body"><pre className="raw-record">{JSON.stringify({id: rawCandidate.id, reasoning: rawCandidate.reasoning,
        result: rawCandidate.result}, null, 2)}</pre></div>}
    </Drawer>
    <Drawer className="workbench-drawer" open={!!targetCandidate} onOpenChange={open => !open && setTargetCandidate(null)} title={`${candidateName(targetCandidate)} · 目标问题`}><div className="drawer-body"><p className="muted">来自已保存目标引用，只展示当前 Baseline 中可匹配的问题。</p><p>指定目标修好 {metricText(targetCandidate?.result,"target_bad_cases_fixed")} / {targetRows(targetCandidate,badCases).length}；卡片“修好”列出全部已修复题号，包含指定目标之外的改善，不能相加。</p><DiagnosisTable business rows={targetRows(targetCandidate,badCases)} strategy={()=>targetCandidate?.reasoning?.hypothesis || '优化假设未采集'} onSelect={row=>{setTargetCandidate(null);setSelectedBadCase({...row,result:{...row.result,optimization_strategy:targetCandidate?.reasoning?.hypothesis}})}} /></div></Drawer>
    <Drawer className="workbench-drawer search-space-drawer" open={searchOpen} onOpenChange={setSearchOpen} title={`可调参数${agentSearchSpace ? ` · ${Object.keys(agentSearchSpace).length}` : ""}`} ><div className="drawer-body"><p>{agentRule ? `每轮最多 ${agentRule.candidates_per_round} 个方案，单方案最多改 ${agentRule.max_changed_parameters} 个参数，D 最多改 ${agentRule.d_max_changed_parameters} 个参数。总预算 ${agentRule.budget} 次，含 D。` : "当前接口未返回 Agent 白名单。下表为运行配置范围，实际权限由实验规则校验。"}</p>{agentSearchSpace ? <SearchSpaceTable contract={agentSearchSpace} baseline={evaluation.config || {}} /> : error ? <p role="alert">{error}</p> : <LoadingSkeleton label="正在读取可调参数" />}</div></Drawer>
    <QuestionDrawer className="workbench-drawer" open={!!selectedBadCase} onOpenChange={open => !open && setSelectedBadCase(null)} questionLabel={selectedBadCase?.question_id && shortQuestionId(selectedBadCase.question_id)}><div className="drawer-body">{selectedBadCase?.load_error ? <p role="alert">{selectedBadCase.load_error}</p> : selectedBadCase?.details_loaded === false ? <LoadingSkeleton label="正在读取完整案例证据" /> : selectedBadCase && <>{caseData(selectedBadCase).passed !== true && <Section title={`Agent（${coreTerm.agent}）规划`} action={<button className="secondary" onClick={() => setSearchOpen(true)}>查看可调参数</button>}><p>{savedDirections(selectedBadCase)}</p><p>{coreEvidence(selectedBadCase)}</p>{coverage?.matrix?.filter((row:any) => row.question_id === selectedBadCase.question_id).map((row:any) => <p key={row.question_id}>{row.gap ? coverageReason(row.gap) : row.validation_requirements}</p>)}</Section>}<CaseDetails item={{ ...caseData(selectedBadCase), question_id: selectedBadCase.question_id || selectedBadCase.result?.question_id, primary_root_cause: rootCause(selectedBadCase) }} snapshot={selectedBadCase.dataset_snapshot || snapshot} config={evaluation.config || {}} gates={gateDetails} />
      {Array.isArray(selectedBadCase.independentReviewNotes) && <IndependentReviewNotes baseline={selectedBadCase.independentReviewNotes}/>}
    </>}</div></QuestionDrawer>

  </PageShell>;
}

type MechanismDecision = {
  question_id: string;
  display_question_id: string;
  fault: { stage: string; subtype?: string };
  decision: string;
  reason: string;
  mechanism?: string;
};

function MechanismDecisions({ result, round }: { result: any; round: number }) {
  if (result?.mechanism_contract !== '113b') return null;
  const current = !result.round || result.round === round;
  const rows = (checks?: Record<string, MechanismDecision[]>) =>
    Object.entries(checks ?? {}).flatMap(([label, decisions]) => decisions.map(row => ({ label, row })));
  const decisions = [
    ...(current ? (result?.validation_retries ?? []).flatMap((attempt: { mechanism_checks?: Record<string, MechanismDecision[]> }) =>
      rows(attempt.mechanism_checks).filter(item => item.row.decision === '拒绝')) : []),
    ...rows(current ? result?.mechanism_checks : result?.agent_strategies?.[String(round)]?.mechanism_checks),
    ...(current ? (result?.composite?.attempts ?? []).flatMap((attempt: { mechanism_checks?: MechanismDecision[] }) =>
      rows({ D: attempt.mechanism_checks ?? [] })) : []),
  ];
  if (!decisions.length) return null;
  return <details className="workbench-status">
    <summary>逐题机制校验</summary>
    <ul>{decisions.map(({ label, row }, index) => <li key={`${label}-${row.question_id}-${index}`}>
      <strong>方案 {label} · {row.display_question_id} · {row.fault.stage} · {row.decision}</strong>
      <p>{row.fault.subtype ? `${row.fault.subtype}。 ` : ''}{row.reason} {row.mechanism}</p>
    </li>)}</ul>
  </details>;
}

function coverageReason(value:unknown):string {
  if (typeof value !== 'string' || !value.trim()) return '具体原因暂未记录';
  if (value === '本轮剩余A/B/C容量不足，需明确调整规划，不能宣称完成') return '本轮三个 Candidate 的名额已用完，需要调整规划';
  return businessSummary(value).replace('当前规则模板未找到通过严格验证的干预；', '当前可用的调整方法暂时不能覆盖这道题；');
}

function IndependentReviewNotes({ baseline, candidate }: { baseline: string[]; candidate?: string[] }) {
  const reviews: [string, string[]][] = [["Baseline", baseline]];
  if (candidate) reviews.push(["Candidate", candidate]);
  return <section className="candidate-card drawer-section">
    <h3><IconLabel name="info">独立审核备注</IconLabel></h3>
    <p>来源为已保存的第 106 单审计表。</p>
    <dl>{reviews.map(([label, notes]) =>
      <div key={label}><dt>{label}</dt><dd>{notes.length
        ? <ul>{notes.map(note => <li key={note}>{note}</li>)}</ul>
        : '这次运行无匹配的审核备注。'}</dd></div>)}</dl>
  </section>;
}

function candidateState(candidate:any, running=false):{label:string;tone:'neutral'|'accent'|'warning'|'good'|'bad'} {
  if (candidate.result?.price_pause?.paused) return {label:'已暂停',tone:'warning'};
  if (running || ['running','queued'].includes(candidate.status)) return {label:'运行中',tone:'accent'};
  if (candidate.status === 'skipped') return {label:'已跳过（未运行）',tone:'neutral'};
  if (candidate.status === 'failed') return candidate.product_interruption === true ? {label:'评测中断',tone:'warning'} : {label:'评测停止',tone:'warning'};
  if (candidate.status === 'evaluated' && candidate.result?.evaluation_complete === false) return {label:'评测未完成',tone:'warning'};
  if (candidate.status === 'evaluated') return currentQualification(candidate.result)?.qualified === true ? {label:qualificationLabel(candidate.result),tone:'good'} : currentQualification(candidate.result)?.qualified === false ? {label:qualificationLabel(candidate.result),tone:'bad'} : {label:'已评测，资格未知',tone:'neutral'};
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

function CandidateCard({ candidate, experiment, baseline, onDetail, targets, onTargets, running, busy, onRun, onSkip, includeRound = false, primaryRun = false, route = false, routeWinner = false, readOnly = false }: {
  candidate: any; experiment: any; baseline: Record<string, unknown>; onDetail: () => void; targets: any[];
  onTargets: () => void; running?: { current?: number; total?: number; stage?: string }; busy: boolean;
  onRun: () => void; readOnly?: boolean; onSkip?: () => void; includeRound?: boolean; primaryRun?: boolean; route?: boolean; routeWinner?: boolean;
}) {
  const reasoning = candidate.reasoning || {}, result = candidate.result;
  const evaluated = evaluatedCandidate(candidate);
  const interrupted = candidate.status === "failed" && candidate.product_interruption === true;
  const state = candidateState(candidate, !!running);
  const blocked = evaluated && sandboxBlock(result);
  const inherited = reasoning.inherited_parameters || {};
  const risks = Array.isArray(reasoning.risks) && reasoning.risks.length
    ? reasoning.risks.map((risk: any) => risk.reason || '暂无') : [reasoning.risk || '暂无'];
  const thought = storyText([
    reasoning.direction || (reasoning.intervention_direction ? optimizationDirection(reasoning.intervention_direction) : ''),
    reasoning.strategy_name, reasoning.core_idea || reasoning.hypothesis || '暂无',
  ].filter(Boolean).join(' · '));
  return <article className={`candidate-card candidate-summary-card drawer-section${route ? " ui-evo-card" : ""}${routeWinner ? " winner" : ""}${blocked ? " sandbox-blocked" : ""}`}
    onClick={event => { if (route && !(event.target as HTMLElement).closest("button,details")) onDetail(); }}>
    <div className="candidate-card-summary">
      <div className="candidate-card-header">
        <h3><SummaryText text={`${schemeName(candidate, undefined, includeRound)} · ${candidateStrategyName(candidate)}`}/></h3>
        <Badge tone={state.tone}>{state.label}</Badge>
      </div>
      {blocked && !route && <p className="sandbox-block-message">{blocked}</p>}
      <dl>
        {candidateSummary(candidate, baseline, experiment, targets).map(([label, value]) => <div key={label} className="candidate-summary-row">
          <dt>{label}</dt><dd><SummaryText text={value}/></dd>
        </div>)}
        {evaluated && !route && <div className="candidate-summary-row"><dt>实验效果</dt><dd><CandidateResultSummary result={result}/></dd></div>}
        {evaluated && !route && <div className="candidate-summary-row"><dt>正式资格</dt><dd><QualificationVersions result={result} showVerdict={false}/></dd></div>}
        {evaluated && !route && <>
          <div className="candidate-summary-row"><dt>证据可信度</dt><dd>{candidateEvidence(candidate, experiment)}</dd></div>
          <div className="candidate-summary-row"><dt>推荐价值</dt><dd>{candidateValue(candidate, experiment)}</dd></div>
        </>}
      </dl>
    </div>
    <div className="candidate-card-body" role="region" aria-label={`Candidate ${reasoning.candidate_label} 正文`}>
      {!evaluated && <div className="candidate-run-note">
        <p>{candidate.status === "generated" ? "Sandbox 尚未运行" : candidateProgress(candidate, running)}</p>
        {result?.evaluation_complete === false && <p>已完成 {result.completed ?? "暂无"}/{result.total ?? "暂无"}
          {candidate.resume_plan?.can_resume === false ? ` · ${businessSummary(candidate.resume_plan.reason)}` : " · 已保存进度"}</p>}
        {interrupted && <p className="candidate-interruption-note">产品故障，会自动续跑；已完成的题不重复调用。</p>}
      </div>}
      <details className="agent-strategy-details">
        <summary>展开 Agent 完整思考</summary>
        <p>{thought}</p>
        {reasoning.inherited_from && <p className="muted">在 Candidate {String(reasoning.inherited_from).match(/(?:^|-)([ABC])$/)?.[1] || reasoning.inherited_from} 的基础上 · {Object.entries(inherited).map(([key,value])=>`${storyParameterNames[key] || key} ${storyValue(value,key)}`).join("；")}</p>}
        {targets.length > 0 && <p>目标题 {targets.map(row => <QuestionBadge key={row.question_id} id={shortQuestionId(row.question_id)} question={caseData(row).question}/>)}</p>}
        <p>预期效果 · {storyText(reasoning.expected_improvement || reasoning.expected || '暂无')}</p>
        <p>风险 · {storyText(risks.join("；"))}</p>
      </details>
    </div>
    <div className="candidate-card-footer">
      {targets.length > 0 && <button className="secondary small" onClick={onTargets}><Icon name="target" size={14}/>查看目标 {targets.length} 题</button>}
      <button className="secondary small" onClick={event => { event.currentTarget.focus(); onDetail(); }}><Icon name="report" size={14}/>查看 Candidate 与完整报告</button>
      {!readOnly && candidate.status === "generated" && onSkip && <button className="text-button" disabled={busy || !!running} onClick={onSkip}>跳过此 Candidate</button>}
      {!readOnly && candidate.status !== "evaluated" && <CandidateAction primary={primaryRun} candidate={candidate} running={running} busy={busy} onRun={onRun}/>}
    </div>
  </article>;
}

function ConfigDiff({ base, candidate }: { base: Record<string, any>; candidate: any }) {
  const after = candidate.config || (candidate.reasoning?.changed_parameters ? { ...base, ...candidate.reasoning.inherited_parameters, ...candidate.reasoning.changed_parameters } : null);
  if(!after || !Object.keys(base).length)return <p className="muted">历史未保存完整Baseline配置，无法核对参数差异。</p>;
  const keys=Object.keys(parameterNames).filter(key=>key in base && key in after);
  return <div className="candidate-config-diff"><ParameterDiff before={Object.fromEntries(keys.map(key=>[key,base[key]]))} after={Object.fromEntries(keys.map(key=>[key,after[key]]))}/>{keys.length<Object.keys(parameterNames).length && <p className="muted">部分参数缺少前后记录，未纳入比较；完整配置保留在接口。</p>}</div>;
}

function CandidateAction({ candidate, running, busy, onRun, primary = false }: { primary?: boolean; candidate: any; running?: { current?: number; total?: number }; busy: boolean; onRun: () => void }) {
  return <div className="candidate-card-action"><button className={primary ? "primary" : "secondary"} disabled={busy || !!running || !["generated", "failed"].includes(candidate.status)} onClick={onRun}>{running ? "Sandbox 运行中" : candidate.status === "skipped" ? "已跳过（未运行）" : candidate.status === "evaluated" ? "已评测" : candidate.status === "failed" ? "继续 Sandbox" : "运行 Sandbox"}</button>{running && running.current != null && running.total != null && <span>{running.current} / {running.total}</span>}</div>;
}

const candidateName = (candidate?: any) => candidate ? schemeName(candidate) : displayText("Candidate");

function metricValue(result: any, key: string) {
  const comparison = result?.comparison_metrics?.[key];
  return ["recall_at_k", "precision_at_k", "mrr"].includes(key) ? comparison
    : comparison ?? result?.metrics?.[key] ?? result?.[key];
}

function metricText(result: any, key: string) {
  if (result?.evaluation_complete === false && !["token_cost", "input_tokens", "output_tokens"].includes(key)) return key === "bad_case_count" ? "待完成" : key === "gates" ? "未完成" : "未判定";
  if (!result || !Object.keys(result).length) return "待运行";
  if (key === "all_fixed_count") return Array.isArray(result.all_fixed_question_ids) ? String(new Set(result.all_fixed_question_ids).size) : result.comparison_version ? "未采集" : result.target_bad_cases_fixed ?? "未采集";
  if (key === "new_failures") { const r = result.regression_review || result.regression; return r && r.new_critical_failures != null && r.new_ordinary_failures != null ? `${!result.regression_review && Array.isArray(result.formal_blocking_question_ids)?"正式阻断 · ":""}严重 ${r.new_critical_failures} / 普通 ${r.new_ordinary_failures}` : "未采集"; }
  if (key === "gates") return result.gates?.passed_count!=null && result.gates?.total!=null ? `${result.gates.passed_count} / ${result.gates.total}` : "未采集";
  if (key === "regression") return result.regression_review || result.regression ? displayText((result.regression_review || result.regression).status || "未采集") : "未判定";
  if (key === "release_qualification") return currentQualification(result)?.qualified === false ? "不可发布" : result.release_qualification?.qualified === true ? "可发布" : result.release_qualification?.qualified === false ? "不可发布" : "未判定";
  if (key === "qualification") return qualificationLabel(result);
  if (key === "token_cost") return billedCostText(result.comparison_metrics);
  const value = metricValue(result, key);
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
  const currentReasons = qualificationReasons(candidate.result || {});
  if (currentReasons) return currentReasons;
  if(currentQualification(candidate.result)?.qualified===true && candidate.result?.release_qualification?.qualified===false){
    const releaseNames:Record<string,string>={hard_gates:'Hard Gate 未通过',zero_new_failures:'新增 Bad Case 超过发布上限',at_least_one_fixed:'未修好原问题'};
    return Object.entries(candidate.result.release_qualification.checks || {}).filter(([,passed])=>passed===false).map(([key])=>releaseNames[key] || '其他保存的发布条件未通过').join('；') || '候选合格，但保存的发布资格未通过。';
  }
  const names:Record<string,string>={hard_gates:"Hard Gate 未通过",regression:"Regression Check 未通过",target_bad_case_fixed:"未满足目标修复条件",total_bad_cases_reduced:"未满足失败总数减少条件"};
  const failed=Object.entries(currentQualification(candidate.result)?.checks || {}).filter(([,passed])=>passed===false).map(([key])=>names[key] || "其他保存的资格条件未通过");
  return failed.join("；") || (currentQualification(candidate.result)?.qualified===true?"保存的质量、安全与 Regression 资格通过；正式推荐以已保存决策为准。":"历史未保存具体未通过原因。");
}

function regressionText(result: any): string {
  const r = result?.regression_review || result?.regression;
  if (!r) return "Regression Check 尚未运行。";
  const fixed = result.target_bad_cases_fixed;
  const counts = r.new_critical_failures != null && r.new_ordinary_failures != null ? `新增严重 ${r.new_critical_failures}、普通 ${r.new_ordinary_failures} 个 Bad Case` : "新增 Bad Case 明细未采集";
  const classification = result.regression_review ? "；最终资格见该方案判定" : "";
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
