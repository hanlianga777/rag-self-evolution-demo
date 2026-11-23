import {qualityHelp,questionClassification} from '../components/QuestionClassification';
import { pagePurpose } from "../helpText";
import { usePageTab } from "../usePageTab";
import { HoverCard } from "../ui/HoverCard";
import { Icon, IconLabel, IconTile } from "../ui/icons";
import { GoldenPipeline } from "../ui/pages3";
import { readableSourceName } from "../components/ComparisonAnswer";
import { DataTable } from "../components/DataTable";
import { PageShell } from "../components/PageShell";
import { useEffect, useMemo, useRef, useState } from "react";
import { apiUrl, errorMessage, getJson, cachedJson, postJson } from "../api";
import { LoadingSkeleton, CustomSelect, Section, ShortId, Status, Badge, TruncatedText } from "../components/Primitives";
import { ConfirmDialog, Drawer, QuestionDrawer } from "../components/Dialog";
import { displayText, presentationText, isMachineQualified, localShortTime } from "../display";
import { useOperation } from "../operation";
import { BusinessImportPanel, CoverageSummary, CurrentCoveragePreview } from "./BusinessImportPanel";
import { FrozenQuestionDetails, goldenQuality, questionSources } from "./FrozenQuestionDetails";
import "./golden-workspace.css";
import { CandidateWorkspace } from "./CandidateWorkspace";
import { PricePauseNotice } from "../components/RuntimeSettings";

import { goldenCached, goldenFetch, invalidateGolden } from "../goldenCache";
import { detailJson, useHoverPrefetch } from "../preload";
import { ScrollablePagedTable, usePagedCandidates } from "../components/ScrollablePagedTable";

type Candidate = Record<string, any>;
type Filter = string;

const stageName: Record<string, string> = { queued: "排队中", coverage: "规划覆盖", generating: "逐题生成与修复", validation: "硬校验", needs_regeneration: "待补齐失败题", probing: "检索验证", qc: "质量检查", completed: "已完成", failed: "运行失败" };
const probeLabel = (value?: string) => value === "probe_passed" ? "通过" : value === "needs_revision" ? "未通过" : "未运行";
const qcLabel = (value?: string) => value === "qc_passed" ? "通过" : value === "qc_failed" ? "未通过" : "未运行";

export function GovernancePage({ data }: { data: any }) {
  const operation = useOperation();
  const profiles = data.workspace?.generation_profiles || data.overview?.generation_profiles || {};
  const profileOptions = Object.entries(profiles).map(([value, counts]: [string, any]) => ({ value, label: `${value.toUpperCase()} · ${counts.expected_count}题（${counts.positive_count} / ${counts.ablation_count} / ${counts.negative_count}）` }));
  const cacheIdentity = JSON.stringify(data.workspace?.current_corpus_fingerprint);
  const [poolVersion, setPoolVersion] = useState(0);
  const [syncing, setSyncing] = useState(false), [newRunConfirm, setNewRunConfirm] = useState(false);
  const [tab, setTab] = usePageTab("governance", ["run", "import"] as const, "run");
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyId, setHistoryId] = useState<string>();
  const [historyQuestion, setHistoryQuestion] = useState<Candidate>();
  const [historySnapshots, setHistorySnapshots] = useState<Candidate[]>([]);
  const [historyError, setHistoryError] = useState("");
  const refreshTicket = useRef(0);
  const [profile, setProfile] = useState<"mini" | "medium" | "full">("mini");
  const [historyPage, setHistoryPage] = useState(0);
  const items: Candidate[] = data.dataset || [];
  const [runs, setRuns] = useState<Candidate[]>(goldenCached<Candidate[]>(cacheIdentity, "/api/governance/generation-runs?light=true") || data.generationRuns || []);
  const [snapshots, setSnapshots] = useState<Candidate[]>(goldenCached<Candidate[]>(cacheIdentity, "/api/governance/snapshots?light=true") || data.snapshots || []);
  const [revisions, setRevisions] = useState<Candidate[]>([]);
  const [filter, setFilter] = useState<Filter>("all");
  const [metadataLoaded, setMetadataLoaded] = useState(!!(goldenCached(cacheIdentity, "/api/governance/generation-runs?light=true") || data.generationRuns) && (!data.workspace?.current_golden_id || snapshots.some(snapshot => snapshot.id === data.workspace.current_golden_id)));
  const [poolDetail, setPoolDetail] = useState<Candidate | null>(null);
  const [detailStatus, setDetailStatus] = useState("");
  const poolTicket = useRef(0);
  const [candidateDirty, setCandidateDirty] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const actionPending = useRef(false);
  const [error, setError] = useState("");
  const [regenerateConfirm, setRegenerateConfirm] = useState(false);
  const [runErrorOpen, setRunErrorOpen] = useState(false);
  const [runDetailsOpen, setRunDetailsOpen] = useState(false), [auditRun, setAuditRun] = useState<Candidate | null>(null);
  const [errorSlot, setErrorSlot] = useState<string | null>(null);
  const [now, setNow] = useState(Date.now());
  const [runDuration, setRunDuration] = useState<{ id: string; ms: number } | null>(null);
  const currentGolden = snapshots.find(snapshot => snapshot.id === data.workspace?.current_golden_id);
  const reanchored = currentGolden?.snapshot?.reanchor && (!runs[0] || runs[0].id === currentGolden.snapshot.generation_run_id) ? currentGolden.snapshot : undefined;
  const workRun = reanchored ? { id: reanchored.generation_run_id, status: "completed", profile: reanchored.profile, question_ids: reanchored.question_ids, artifacts: { hard_validation: { frozen_plan: reanchored.coverage_plan } } } : runs[0];
  const listPath = `/api/governance/candidates?run_id=${workRun?.id}&status=all&group=all`;
  const paged = usePagedCandidates(JSON.stringify([cacheIdentity, workRun?.id, workRun?.profile?.name]), listPath, !reanchored && !!(workRun?.question_ids?.length || workRun?.artifacts?.hard_validation?.slot_persistence_v1));
  const latestReview = useRef(paged.refresh); latestReview.current = paged.refresh;
  const review: Candidate[] = paged.rows, currentIndex: Candidate[] = paged.candidate_index || [], listing = paged.loading;
  const fullSnapshot = reanchored || currentGolden?.snapshot?.reviewed_import && currentGolden.snapshot;
  const formalDetailsLoaded = !fullSnapshot || fullSnapshot.questions?.every((row: Candidate) => typeof row.question === "string" && (!!reanchored || "evidence" in row || typeof row.reference_answer === "string"));
  useEffect(() => {
    if (formalDetailsLoaded) return;
    let cancelled = false;
    void goldenFetch<Candidate[]>(cacheIdentity, "/api/governance/snapshots").then(value => {
      if (!cancelled && Array.isArray(value)) setSnapshots(value);
    }).catch(reason => { if (!cancelled) setError(errorMessage(reason)); });
    return () => { cancelled = true; };
  }, [currentGolden?.id, cacheIdentity, formalDetailsLoaded]);
  const historyVersions = [...snapshots, ...runs.filter(run => !snapshots.some(snapshot => snapshot.snapshot?.generation_run_id === run.id))];
  const versionNumbers = new Map([...historyVersions].reverse().sort((a, b) => (Date.parse(a.created_at) || 0) - (Date.parse(b.created_at) || 0)).map((version, index) => [version.id, index + 1]));
  const historyVersion = historyVersions.find(version => version.id === historyId) || historyVersions.find(version => (version.snapshot?.generation_run_id || version.id) === workRun?.id) || currentGolden || historyVersions[0];
  const historyRunId = historyVersion?.snapshot?.generation_run_id || (!historyVersion?.snapshot ? historyVersion?.id : undefined);
  const historyRun = runs.find(run => run.id === historyRunId);
  const historyExportable = !!historyRunId && (historyRun ? historyRun.question_ids?.length === (historyRun.profile?.expected_count || 20) : !!historyVersion?.snapshot?.question_ids?.length);
  const historyCandidates = usePagedCandidates(cacheIdentity, `/api/governance/candidates?run_id=${historyRunId}&status=all&group=all`, historyOpen && !!historyRunId && !historyVersion?.snapshot);
  const historyQuestions: Candidate[] = historyVersion?.snapshot ? (historySnapshots.find(snapshot => snapshot.id === historyVersion.id) || historyVersion).snapshot?.questions || [] : historyCandidates.rows;
  const historyComplete = historyQuestions.length > 0 && historyQuestions.every(row => typeof row.question === "string");
  const historyDisplayRows = historyQuestions.map(row => ({ ...row, slot: row.slot || row.display_id || row.coverage_slot || row.raw?.coverage_slot }));
  useEffect(() => {
    if (!historyOpen || !historyVersion?.snapshot || historyComplete) return;
    let cancelled = false;
    setHistoryError("");
    void goldenFetch<Candidate[]>(cacheIdentity, "/api/governance/snapshots").then(value => { if (!cancelled) setHistorySnapshots(value); }).catch(reason => { if (!cancelled) setHistoryError(errorMessage(reason)); });
    return () => { cancelled = true; };
  }, [historyOpen, historyVersion?.id, cacheIdentity]);
  const checkingSnapshot = !!data.workspace?.current_golden_id && !currentGolden;
  const goldenQuestions: Candidate[] = currentGolden?.snapshot?.questions || (currentGolden?.snapshot?.question_ids || []).map((id: string) => items.find(row => row.id === id)).filter(Boolean);
  const goldenCount = currentGolden?.snapshot?.question_ids?.length ?? goldenQuestions.length;
  const goldenV2 = !!(currentGolden?.snapshot?.planner_version || currentGolden?.snapshot?.coverage_plan?.planner_version);
  const goldenGroups = (currentGolden?.snapshot?.question_ids || goldenQuestions.map(row => row.id)).map((id: string) => {
    const frozen = goldenQuestions.find(row => row.id === id);
    const saved = items.find(row => row.id === id);
    return frozen?.test_category || frozen?.evaluation_group || saved?.test_category || saved?.evaluation_group;
  });
  const goldenCategoriesComplete = goldenGroups.length === goldenCount && goldenGroups.every((group: string) => ["positive", "ablation", "negative"].includes(group));
  const expectedCount = workRun?.profile?.expected_count || ["positive", "ablation", "negative"].reduce((total, category) => total + (workRun?.profile?.[category] || 0), 0) || 20;
  const currentIds: string[] = workRun?.question_ids || [];
  const gate1Snapshot = snapshots.find(snapshot => snapshot.status === "approved" && snapshot.snapshot?.generation_run_id === workRun?.id && JSON.stringify(snapshot.snapshot?.question_ids) === JSON.stringify(currentIds));
  const savedTopicCount = workRun?.artifacts?.hard_validation?.frozen_plan?.clusters?.length;
  const [coverage, setCoverage] = useState<Candidate | null | undefined>(null);
  useEffect(() => {
    if (!workRun || savedTopicCount != null) return;
    let cancelled = false;
    setCoverage(null);
    void getJson<Candidate>("/api/pipeline").then(result => { if (!cancelled) setCoverage(result.knowledge?.coverage); }).catch(() => { if (!cancelled) setCoverage(undefined); });
    return () => { cancelled = true; };
  }, [cacheIdentity, workRun?.id, savedTopicCount]);
  const topicCount = savedTopicCount ?? coverage?.clusters?.length ?? coverage?.final_k;
  const frozen = !!gate1Snapshot;
  const frozenDate = localShortTime(gate1Snapshot?.snapshot?.gate1?.confirmed_at || gate1Snapshot?.created_at);
  const plannedSlots = new Map((workRun?.artifacts?.question_plan || []).map((row: Candidate) => [row.question_id, row.coverage_slot]));
  const frozenRows: Candidate[] = reanchored?.questions?.map((question: Candidate) => ({ ...question, raw: question, slot: question.display_id, stage: "golden", review_status: "approved", qualification_status: "human_approved", probe_status: question.probe_status, qc_status: reanchored.reanchor.qc_reuse?.[question.id]?.qc_status ?? question.qc_status, probe: reanchored.reanchor.probe_results?.[question.id]?.observation ?? question.probe })) || [];
  const current: Candidate[] = currentIds.map(id => {
    const row = frozenRows.find(row => row.id === id) || currentIndex.find(row => row.id === id) || review.find(row => row.id === id) || items.find(row => row.id === id);
    const saved = frozen ? gate1Snapshot?.snapshot?.questions?.find((question: Candidate) => question.id === id && typeof question.question === "string") : undefined;
    return saved ? { ...row, ...saved, raw: { ...row?.raw, ...saved }, stage: "golden", review_status: "approved", slot: saved.display_id || row?.slot } : row;
  }).filter((row): row is Candidate => !!row).map(row => ({ ...row, slot: row.slot || row.raw?.coverage_slot || plannedSlots.get(row.id) }));
  const historical = items.filter(row => !currentIds.includes(row.id) && row.stage !== "golden");
  const selected = poolDetail?.id === selectedId ? poolDetail : current.find(row => row.id === selectedId) || items.find(row => row.id === selectedId);
  const candidateContentKey = JSON.stringify([selected?.id, selected?.question, selected?.reference_answer, selected?.evidence, selected?.raw?.revision_version]);
  const running = ["queued", "coverage", "generating", "validation", "probing", "qc"].includes(workRun?.status);
  const qualityRerun = workRun?.artifacts?.hard_validation?.quality_rerun;
  const qualityRunning = qualityRerun?.status === "running";
  const progress = workRun?.artifacts?.hard_validation?.progress;
  const operationProgress = workRun?.operation_progress;
  const partial = !!workRun?.artifacts?.hard_validation?.slot_persistence_v1 && workRun?.status !== "completed";
  const failedSlots: string[] = workRun?.artifacts?.hard_validation?.slot_persistence_v1 && workRun?.status === "needs_regeneration" ? (workRun?.artifacts?.coverage_plan || []).map((item: Candidate) => item.slot).filter((slot: string) => !current.some(row => row.slot === slot)) : [];
  const runStartedAt = workRun?.created_at ? Date.parse(workRun.created_at) : NaN;
  const elapsed = Number.isFinite(runStartedAt) && (running || runDuration?.id === workRun?.id) ? `${(Math.max(0, (runDuration?.id === workRun?.id ? runDuration?.ms : now - runStartedAt) ?? 0) / 1000).toFixed(1)}s` : null;
  useEffect(() => { setConfirmed(false); if (workRun?.profile?.name) setProfile(workRun.profile.name); }, [workRun?.id]);
  useEffect(() => { if (!running && !qualityRunning) return; const timer = window.setInterval(() => setNow(Date.now()), 100); return () => window.clearInterval(timer); }, [running, qualityRunning]);

  const loadReview = async (run: Candidate | undefined, _ticket = refreshTicket.current) => { if (run?.id === workRun?.id) await latestReview.current(); };
  const reload = async () => {
    const ticket = ++refreshTicket.current;
    setSyncing(!metadataLoaded);
    try {
      const [generationRuns, goldenSnapshots] = await Promise.all([
        goldenFetch<Candidate[]>(cacheIdentity, "/api/governance/generation-runs?light=true"), goldenFetch<Candidate[]>(cacheIdentity, "/api/governance/snapshots?light=true"),
      ]);
      if (ticket !== refreshTicket.current) return;
      setRuns(generationRuns); setSnapshots(goldenSnapshots);
      await loadReview(generationRuns[0], ticket);
      if (ticket === refreshTicket.current) setPoolVersion(value => value + 1);
      if (selectedId) { const detail = await getJson<Candidate>(`/api/governance/questions/${selectedId}`); if (ticket === refreshTicket.current) setPoolDetail(detail); }
    } finally { if (ticket === refreshTicket.current) { setSyncing(false); setMetadataLoaded(true); } }

  };
  useEffect(() => () => { refreshTicket.current++; }, []);
  useEffect(() => {
    operation.registerCandidateRefresh(reload);
    return () => operation.unregisterCandidateRefresh(reload);
  }, [operation.registerCandidateRefresh, operation.unregisterCandidateRefresh, reload]);
  useEffect(() => {
    if (!data.generationRuns || checkingSnapshot) void reload().catch(reason => setError(errorMessage(reason)));
    else { void loadReview(data.generationRuns[0]).catch(reason => setError(errorMessage(reason))); if (data.generationRuns[0]?.question_ids?.length === (data.generationRuns[0]?.profile?.expected_count || 20)) void getJson<Candidate[]>("/api/governance/revisions").then(value => setRevisions(Array.isArray(value) ? value : [])).catch(() => {}); }
  }, [data.generationRuns, data.dataset]);
  useEffect(() => {
    if ((!running && !qualityRunning) || !workRun?.id) return;
    let cancelled = false;
    let timer: number;
    const poll = async () => {
      try {
        const updated = await getJson<Candidate>(`/api/governance/generation-runs/${workRun.id}?light=true`);
        if (cancelled) return;
        setRuns(previous => {
          const saved = previous.find(row => row.id === updated.id);
          return [{...saved, ...updated, artifacts:{...saved?.artifacts,...updated.artifacts,hard_validation:{...saved?.artifacts?.hard_validation,...updated.artifacts?.hard_validation}}}, ...previous.filter(row => row.id !== updated.id)];
        });
        if (["completed", "failed"].includes(updated.status) && updated.created_at) setRunDuration({ id: updated.id, ms: Date.now() - Date.parse(updated.created_at) });
        if (["completed", "failed", "needs_regeneration"].includes(updated.status) && (running || updated.artifacts?.hard_validation?.quality_rerun?.status !== "running")) void reload().catch(reason => setError(errorMessage(reason)));
      } catch (reason) { if (!cancelled) setError(errorMessage(reason)); }
      if (!cancelled) timer = window.setTimeout(poll, 1000);
    };
    void poll();
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [workRun?.id, workRun?.status, qualityRunning]);


  const needsAttention = (row: Candidate) => row.qualification_status ? row.qualification_status === "needs_human_review" : row.stage !== "golden" && (row.probe_status !== "probe_passed" || row.qc_status !== "qc_passed") || ["P0", "P1"].includes(row.qc?.priority) || ["FAKE_NEGATIVE_RISK", "RETRIEVAL_INCOHERENT", "RETRIEVAL_EXECUTION_FAILED"].includes(row.probe?.probe_details?.classification) || ["needs_revision", "rejected"].includes(row.review_status) || row.approval_eligibility?.blocking_reasons?.length > 0 || row.approval_eligibility?.requires_qc_p0_acceptance;
  const attention = current.filter(needsAttention);
  const filters = useMemo(() => [
    { key: "all", label: "全部", count: current.length + failedSlots.length, match: (_row: Candidate) => true },
    { key: "attention", label: "需要人工关注", count: attention.length + failedSlots.length, match: needsAttention },
    { key: "positive", label: "正向（Positive）", count: current.filter(row => row.test_category === "positive").length, match: (row: Candidate) => row.test_category === "positive" },
    { key: "ablation", label: "消融（Ablation）", count: current.filter(row => row.test_category === "ablation").length, match: (row: Candidate) => row.test_category === "ablation" },
    { key: "negative", label: "负向（Negative）", count: current.filter(row => row.test_category === "negative").length, match: (row: Candidate) => row.test_category === "negative" },
    { key: "pending", label: "校验通过", count: current.filter(row => isMachineQualified(row.qualification_status)).length, match: (row: Candidate) => isMachineQualified(row.qualification_status) },
  ] as const, [current, failedSlots]);
  const riskFilters = [
    { key: "probe-risk", label: "Probe 未通过", match: (row: Candidate) => row.probe_status === "needs_revision" },
    { key: "qc-risk", label: "QC 未通过", match: (row: Candidate) => row.qc_status === "qc_failed" },
    { key: "p0", label: "QC P0", match: (row: Candidate) => row.qc?.priority === "P0" },
    { key: "p1", label: "QC P1", match: (row: Candidate) => row.qc?.priority === "P1" },
    { key: "qc-review", label: "QC 需人工看过", match: (row: Candidate) => row.attention_reasons?.some((reason: string) => ["QC P1", "QC 低分待审阅"].includes(reason)) },
    { key: "p0-acceptance", label: "QC P0 待人工接受", match: (row: Candidate) => row.approval_eligibility?.requires_qc_p0_acceptance && row.approval_eligibility?.blocking_reasons?.length === 0 },
    { key: "fake-negative", label: "疑似伪负向", match: (row: Candidate) => row.probe?.probe_details?.classification === "FAKE_NEGATIVE_RISK" },
    { key: "retrieval-incoherent", label: "检索不连贯", match: (row: Candidate) => row.probe?.probe_details?.classification === "RETRIEVAL_INCOHERENT" },
    { key: "execution-failed", label: "检索执行失败", match: (row: Candidate) => row.probe?.probe_details?.probe_execution_status === "failed" || row.probe?.probe_details?.classification === "RETRIEVAL_EXECUTION_FAILED" },
    { key: "approval-blocked", label: "审批阻断", match: (row: Candidate) => row.approval_eligibility?.blocking_reasons?.length > 0 },
    { key: "revision-risk", label: "需修订 / 已拒绝", match: (row: Candidate) => ["needs_revision", "rejected"].includes(row.review_status) },
  ].map(item => ({ ...item, count: current.filter(item.match).length })).filter(item => item.count > 0);
  const listRows = review.length || currentIndex.length ? review : current.filter(row => row.question);
  const visible = listRows.filter(filters.find(item => item.key === filter)?.match || (() => true));
  const gateBlocked = current.filter(row => row.qualification_status ? row.qualification_status === "needs_human_review" : row.stage !== "golden" && !(row.approval_eligibility?.can_approve ?? (row.probe_status === "probe_passed" && row.qc_status === "qc_passed")));
  const manualBlocked = current.filter(row => ["needs_revision", "rejected"].includes(row.review_status) || row.approval_eligibility?.requires_qc_p0_acceptance);
  const batchReason = current.length !== expectedCount ? `本轮尚未完整入库 ${expectedCount} 道题` : gateBlocked.length || manualBlocked.length ? `仍有 ${new Set([...gateBlocked, ...manualBlocked].map(row => row.id)).size} 道异常尚未处理（含 QC P0 风险）` : gate1Snapshot ? "本轮已确认 Golden 测试集" : !confirmed ? "请确认冻结当前完整且异常已关闭的数据集" : "";
  const action = async (work: () => Promise<unknown>, title: string) => {
    if (actionPending.current) return false;
    actionPending.current = true; setBusy(true); setError("");
    try { await operation.run(title, async () => { await work(); invalidateGolden(); try { await reload(); } catch (reason) { throw new Error(`后台已完成，但候选题刷新失败：${errorMessage(reason)}`); } }); return true; }
    catch (reason) { setError(errorMessage(reason)); return false; }
    finally { actionPending.current = false; setBusy(false); }
  };
  const refreshAfterMutation = async () => { invalidateGolden(); await reload(); };
  const createMini = async () => {
    setBusy(true); setError(""); setRunDuration(null);
    try {
      const started: { run_id: string } = await postJson("/api/governance/generate", { profile, strategy: profile === "medium" ? "business_v2" : "evidence_v1" });
      invalidateGolden();
      const run = await getJson<Candidate>(`/api/governance/generation-runs/${started.run_id}`);
      setRuns(previous => [run, ...previous.filter(row => row.id !== run.id)]);
      setFilter("attention");
    } catch (reason) { setError(errorMessage(reason)); }
    finally { setBusy(false); }
  };
  const regenerate = async () => {
    setBusy(true); setError("");
    try {
      await postJson(`/api/governance/generation-runs/${workRun.id}/regenerate-failed`);
      invalidateGolden();
      const updated = await getJson<Candidate>(`/api/governance/generation-runs/${workRun.id}`);
      setRuns(previous => [updated, ...previous.filter(row => row.id !== updated.id)]);
    } catch (reason) { setError(errorMessage(reason)); }
    finally { setBusy(false); }
  };
  const questionAction = (id: string, name: "probe" | "qc") => action(() => postJson(`/api/governance/questions/${id}/${name}`), name === "probe" ? "运行单题 Probe" : "运行单题 QC");
  const reviewAction = async (id: string, decision: string, reason?: string, tags?: string[], acceptQcP0?: boolean) => {
    const approved = await action(() => postJson(`/api/governance/questions/${id}/review`, { decision, reason, tags, ...(acceptQcP0 ? { accept_qc_p0: true } : {}) }), "人工审核 Candidate");
    if (approved && decision === "approved") setSelectedId(null);
    return approved;
  };

  const openRunAudit = async (runId = workRun?.id) => {
    if (!runId) return;
    setAuditRun(runs.find(run => run.id === runId) || { id: runId }); setRunDetailsOpen(true);
    try { const detail = await getJson<Candidate>(`/api/governance/generation-runs/${runId}`);
      if (detail.artifacts?.hard_validation?.frozen_plan?.generation_strategy === "business_v2") detail.naturalness_audit = await getJson(`/api/governance/generation-runs/${runId}/naturalness-audit`);
      setAuditRun({ ...detail, id: runId }); }
    catch (reason) { setError(errorMessage(reason)); }
  };
  const openPoolDetail = async (row: Candidate) => {
    const ticket = ++poolTicket.current;
    const cached = reanchored ? undefined : cachedJson<Candidate>(`/api/governance/questions/${row.id}`);
    setPoolDetail(cached || row); setSelectedId(row.id); setDetailStatus(cached ? "" : "正在读取候选题详情…");
    try {
      let result = await detailJson<Candidate>(`/api/governance/questions/${row.id}`);
      if (frozen && gate1Snapshot?.snapshot?.reanchor && currentIds.includes(row.id)) {
        const versions = await goldenFetch<Candidate[]>(cacheIdentity, "/api/governance/snapshots");
        const snapshot = versions.find(version => version.id === gate1Snapshot.id)?.snapshot;
        const question = snapshot?.questions?.find((item: Candidate) => item.id === row.id);
        if (!question) throw new Error("冻结题卷缺少该题详情");
        const observation = snapshot.reanchor.probe_results?.[row.id]?.observation;
        result = { ...result, ...question, raw: question,
          evidence_details: [{ chunks: (question.business_requirements?.sources || []).map((source: Candidate) => ({ ...source, chunk_text: source.quote })) }],
          probe: observation || { score: null, question_validity_reason: "硬校验通过；沿用已保存的题目审核。", retrieval_observation: "详见本题已保存的检索诊断记录。" },
          qc: { ...result.qc, association: snapshot.reanchor.qc_reuse?.[row.id] } };
      } else if (frozen && currentIds.includes(row.id)) {
        result = { ...result, ...row, raw: { ...result.raw, ...row.raw }, evidence_details: result.evidence_details,
          probe: row.probe ?? result.probe, qc: row.qc ?? result.qc };
      }
      if (ticket === poolTicket.current) { setPoolDetail(result); setRevisions(result.revision_history || []); setDetailStatus(""); }
    }
    catch (reason) { if (ticket === poolTicket.current) setDetailStatus(errorMessage(reason)); }

  };
  const loadingWorkspace = !metadataLoaded || checkingSnapshot || !!reanchored && !formalDetailsLoaded || !!workRun && !current.length && listing;
  return <PageShell className={`page governance-page governance-${tab} ${!workRun && tab === "run" ? "is-empty" : ""}`} header={<div className="page-title"><div><h1><IconTile name="golden" />黄金测试集</h1><p className="ui-kicker page-purpose">{pagePurpose.governance}</p></div></div>} tabs={<div className="tabs"><button data-label="当前测试集" aria-pressed={tab === "run"} className={tab === "run" ? "active" : ""} onClick={() => setTab("run")}>当前测试集</button><button data-label="候选池" aria-pressed={tab === "import"} className={tab === "import" ? "active" : ""} onClick={() => setTab("import")}>候选池</button></div>} resetKey={tab}>

{!loadingWorkspace && tab === "run" && <div className="header-actions page-data-actions">{historyVersions.length > 0 && <button className="secondary" onClick={() => setHistoryOpen(true)}>查看题卷历史</button>}{!frozen && workRun?.status === "needs_regeneration" && <button className="primary" disabled={busy} onClick={() => setRegenerateConfirm(true)}>补齐失败题（{expectedCount - current.length}）</button>}</div>}
{!loadingWorkspace && !frozen && tab === "run" && workRun?.status !== "needs_regeneration" && <div className="golden-new-run-actions"><label className="profile-selector"><CustomSelect ariaLabel="测试集 Profile" value={profile} onChange={value => setProfile(value as typeof profile)} options={profileOptions} /></label><button className="secondary" disabled={busy || running || qualityRunning} onClick={() => setNewRunConfirm(true)}>新建测试集</button></div>}
    {error && <p className="error-notice" role="alert">{error}</p>}
    {loadingWorkspace ? <div className="golden-skeleton golden-initial-skeleton" role="status" aria-label="正在读取黄金测试集"><span>{checkingSnapshot ? "正在读取当前冻结题卷…" : "正在读取题卷…"}</span>{[1, 2, 3, 4, 5, 6].map(index => <span key={index} aria-hidden="true" />)}</div> : tab === "run" && <div className="golden-workspace">



      <PricePauseNotice pause={workRun?.artifacts?.hard_validation?.price_pause} target={workRun ? {generation_id:workRun.id} : undefined} onChanged={reload} />
      {workRun && (running || qualityRerun || ['failed','needs_regeneration','awaiting_review'].includes(workRun.status)) && <section className="generation-status" aria-label="考卷处理进度"><div className="run-summary">当前阶段：{stageName[workRun.status] || displayText(workRun.status)} · 已处理 {operationProgress?.processed_slots ?? 0} / {expectedCount}{progress?.slot ? ` · ${progress.slot}` : ''} · Probe {operationProgress?.probe_processed ?? 0} / {expectedCount} · QC {operationProgress?.qc_processed ?? 0} / {expectedCount}{progress?.qc_skipped ? ` · QC 跳过 ${progress.qc_skipped}` : ''}</div><div className="generation-progress" role="status">{operationProgress && <span>{operationProgress.phase_label} · 已处理 {operationProgress.phase_processed}/{operationProgress.phase_total} · {operationProgress.phase_percent}% · Round {operationProgress.refill_round}/{operationProgress.refill_max_rounds} · 剩余 {operationProgress.failed_count} 道 · Hard Valid {operationProgress.hard_valid_completed}/{operationProgress.hard_valid_total} · Probe {operationProgress.probe_processed}/{expectedCount} · QC {operationProgress.qc_processed}/{expectedCount}</span>}</div>{qualityRerun && <p>质量重跑：{displayText(qualityRerun.status)} · {qualityRerun.completed || 0} / {qualityRerun.total || expectedCount}</p>}</section>}
      <GoldenPipeline total={current.length} split={["positive", "ablation", "negative"].map(group => ({ label: displayText(group), count: current.filter(row => row.test_category === group).length }))} steps={[
        { label: displayText("Coverage"), done: !!(gate1Snapshot || workRun?.artifacts?.coverage_plan?.length), value: topicCount != null ? `${topicCount} 个主题` : !workRun ? "待规划" : coverage === null ? <LoadingSkeleton label="正在读取覆盖主题" /> : "未知 个主题" },
        { label: displayText("Question Generation"), done: current.length === expectedCount, value: `${current.length}/${expectedCount}` },
        { label: displayText("Hard Validation"), done: current.length === expectedCount, value: `${current.length}/${expectedCount}` },
        { label: "检索探针", done: current.length === expectedCount && current.every(row => row.probe_status === "probe_passed"), value: reanchored
          ? `${current.filter(row => row.probe).length}/${expectedCount} 已记录`
          : current.some(row => !row.probe_status) ? "部分质检记录待读取"
          : `${current.filter(row => row.probe_status === "probe_passed").length}/${expectedCount}${current.some(row => row.probe_status === "needs_revision") ? " 待处理" : ""}` },
        { label: "质检", done: current.length === expectedCount && current.every(row => row.qc_status === "qc_passed"), value: current.some(row => !row.qc_status) ? "部分质检记录待读取"
          : `${current.filter(row => row.qc_status === "qc_passed").length}/${expectedCount}${current.some(row => row.qc_status === "qc_failed") ? " 待处理" : ""}` },
        { label: "题卷确认（Gate 1）", done: !!gate1Snapshot, value: frozen ? gate1Snapshot?.snapshot?.gate1?.confirmed_at ? "已保存确认时间" : "签署未记录" : "待人工确认", accent: true },
      ]} frozen={{ ok: frozen, text: frozen ? `已冻结 · ${frozenDate}` : "尚未冻结" }} />
      {workRun ? <Section title={<IconLabel name="golden">题目审核</IconLabel>}>
        <div className="review-filters" aria-label="题目筛选">{filters.filter(item => item.key !== "attention" || item.count > 0).filter(item => !frozen || item.key !== "pending").map(item => <button key={item.key} aria-pressed={filter === item.key} className={filter === item.key ? "active" : ""} onClick={() => setFilter(item.key)}>{item.label} {item.count}</button>)}        <small className="muted golden-review-role" role="status">{syncing || listing ? "正在同步…" : ""}</small></div>

        {(syncing || listing) && !listRows.length ? <div className="golden-skeleton" role="status" aria-label="正在读取候选题">{[1,2,3,4].map(index => <span key={index} aria-hidden="true" />)}</div> : <QuestionTable rows={["all", "attention"].includes(filter) ? [...visible, ...failedSlots.map(slot => ({ id: `missing-${slot}`, slot, question: "生成失败，待补齐", failed: true }))].sort((a, b) => String(a.slot || "").localeCompare(String(b.slot || ""))) : visible} onDetail={row => row.failed ? (setErrorSlot(row.slot), setRunErrorOpen(true)) : void openPoolDetail(row)} paging={reanchored ? undefined : paged} resetKey={filter} coveragePlan={workRun?.artifacts?.hard_validation?.frozen_plan} />}
        {paged.error && <p role="alert" className="error-notice">{paged.error} <button className="text-button" onClick={() => void paged.refresh()}>重试</button></p>}
        {current.length === expectedCount && workRun.status === "completed" && !gate1Snapshot && !checkingSnapshot && <div className="review-batch gate-one-action"><label><input type="checkbox" checked={confirmed} onChange={event => setConfirmed(event.target.checked)} /> {workRun?.human_gate?.status === "ready" ? "我确认冻结当前黄金测试集" : "我已人工审核当前完整题集"}</label><button className="primary" aria-description={batchReason} disabled={busy || !!batchReason} onClick={() => void action(() => workRun?.human_gate?.status === "ready" ? postJson(`/api/governance/generation-runs/${workRun.id}/snapshot`, {}) : postJson("/api/governance/review-batch", { question_ids: currentIds, confirmed_manual_review: true }), workRun?.human_gate?.status === "ready" ? "冻结 Golden 测试集" : "审核 Golden 测试集")}>{workRun?.human_gate?.status === "ready" ? "冻结 Golden Dataset" : "确认人工审核"}</button></div>}
      </Section> : <Section title={<IconLabel name="golden">题目审核</IconLabel>}><p className="muted">尚未生成工作题卷，可生成题目或从候选池创建测试集。</p></Section>}
    </div>}
    <ConfirmDialog open={regenerateConfirm} onOpenChange={setRegenerateConfirm} title="确认补齐失败题" busy={busy} onConfirm={() => { setRegenerateConfirm(false); void regenerate(); }}><p>仅补齐当前测试集的失败题，会调用模型并产生费用，并继续执行 Probe / QC。</p><p>不会影响当前线上版本。</p></ConfirmDialog>
    <ConfirmDialog open={newRunConfirm} onOpenChange={setNewRunConfirm} title="新建测试集" busy={busy} onConfirm={() => { setNewRunConfirm(false); void createMini(); }}><p>新测试集：{profileOptions.find(option => option.value === profile)?.label}</p><p>{frozen ? "当前题卷已冻结。" : "当前工作集尚未完成最终确认。"}新建测试集将调用模型并产生费用，是否继续？</p></ConfirmDialog>

    {!loadingWorkspace && <div className="golden-pool" hidden={tab !== "import"}><BusinessImportPanel refreshVersion={poolVersion} readOnly={frozen} profiles={profiles} items={items} onCreated={refreshAfterMutation} onDetail={row => void openPoolDetail(row)} initialProfile={profile} currentQuestionIds={currentIds} coveragePlan={workRun?.artifacts?.hard_validation?.frozen_plan} corpusFingerprint={data.workspace?.current_corpus_fingerprint} />{workRun || frozen
      ? <CoverageSummary run={workRun} questions={current} documents={data.documents || []} persistedPlan={gate1Snapshot?.snapshot?.coverage_plan}/>
      : !frozen && <CurrentCoveragePreview profile={profile} corpusFingerprint={data.workspace?.current_corpus_fingerprint} documents={data.documents || []}/>}</div>}

    <Drawer showCloseFooter={false} open={historyOpen} onOpenChange={setHistoryOpen} title="题卷历史 · 只读"><div className="drawer-body snapshot-history">
      <Section title="题卷版本"><div className="run-list">{historyVersions.map(version => <div key={version.id} className="snapshot-version-row" aria-current={version.id === historyVersion?.id ? "true" : undefined}>
        <HoverCard content={version.id}><strong tabIndex={0}>第 {versionNumbers.get(version.id)} 版 · {localShortTime(version.created_at)} · {(version.snapshot?.question_ids || version.question_ids)?.length ?? "未知"} 题</strong></HoverCard>
        <Status value={version.status} />{version.id === currentGolden?.id && <Badge tone="accent">当前使用</Badge>}
        <button className="secondary ui-action-sm" onClick={() => setHistoryId(version.id)}>查看</button>
      </div>)}{!historyVersions.length && <p className="muted">尚无 Golden 版本。</p>}</div></Section>
      {historyVersion && <Section title="选中版本题目" action={<div className="header-actions snapshot-history-toolbar" aria-label="选中版本操作">
        {([['markdown', 'Markdown'], ['csv', 'CSV'], ['json', 'JSON']] as const).map(([format, label]) => historyExportable ? <a className="secondary ui-action-sm" key={format} href={apiUrl(`/api/governance/generation-runs/${historyRunId}/export?format=${format}`)} download>导出 {label}</a> : <HoverCard key={format} content={!historyRunId ? "没有关联的工作集，无法导出。" : "题目尚未齐全，无法导出。"}><span tabIndex={0}><button className="secondary ui-action-sm" disabled>导出 {label}</button></span></HoverCard>)}

      </div>}><div className="snapshot-version-preview">{(historyError || historyCandidates.error) ? <p role="alert">{historyError || historyCandidates.error}</p> : historyComplete ? <QuestionTable rows={historyDisplayRows} onDetail={setHistoryQuestion} /> : historyCandidates.loading || historyVersion.snapshot && !historySnapshots.length ? <LoadingSkeleton label="正在读取选中版本" /> : <p>该版本未保存完整题目。</p>}</div></Section>}
      <Section title="历史 Candidate（未验证）"><section><h3 className="disclosure-heading">{historical.length} 道历史 {displayText("Candidate")}</h3><p className="muted">仅供追溯，不参与当前 Golden、Baseline 或发布判断。</p><QuestionTable rows={historical.length <= 200 ? historical : historical.slice(historyPage * 200, historyPage * 200 + 200)} onDetail={setHistoryQuestion} />{historical.length > 200 && <div className="history-pagination"><button className="secondary" disabled={historyPage === 0} onClick={() => setHistoryPage(page => page - 1)}>上一页</button><span>{historyPage + 1} / {Math.max(1, Math.ceil(historical.length / 200))}</span><button className="secondary" disabled={(historyPage + 1) * 200 >= historical.length} onClick={() => setHistoryPage(page => page + 1)}>下一页</button></div>}</section></Section>
    </div></Drawer>
    <QuestionDrawer showCloseFooter={false} open={!!historyQuestion} onOpenChange={open => !open && setHistoryQuestion(undefined)}
      questionLabel={historyQuestion?.display_id || historyQuestion?.slot || "历史题"}>
      {historyQuestion && <FrozenQuestionDetails frozen={historyVersion?.status === "approved" && !!historyVersion.snapshot} row={{ ...historyQuestion, raw: { ...historyQuestion, ...historyQuestion.raw } }} />}
    </QuestionDrawer>
    <QuestionDrawer showCloseFooter={false} guardEdits editDirty={candidateDirty} contentKey={candidateContentKey} open={!!selected} onOpenChange={open => { if (!open) { poolTicket.current++; setSelectedId(null); } }} questionLabel={selected?.slot || selected?.display_id} className={`candidate-workspace${frozen ? " frozen-question-workspace" : ""}`}>{detailStatus ? <div className="drawer-body">{detailStatus.startsWith("正在读取") ? <LoadingSkeleton label={detailStatus} /> : <p role="alert">{detailStatus}</p>}</div> : frozen ? selected ? <FrozenQuestionDetails row={selected} showSource={new Set(current.map(row => row.raw?.source)).size > 1} /> : null : <CandidateWorkspace key={candidateContentKey} row={selected} peers={current} revision={revisions.find(item => item.question_ids?.includes(selected?.id))} rerunSlot={qualityRerun?.slots?.[selected?.slot]} busy={busy} readOnly={partial || !currentIds.includes(selected?.id || "")} readOnlyReason={!currentIds.includes(selected?.id || "") ? "来源候选题只读；匹配 Profile 与 覆盖规划 题位 后创建待审核副本。" : undefined} onRun={questionAction} onReview={reviewAction} onRefresh={refreshAfterMutation} operation={operation} onDirtyChange={setCandidateDirty} />}</QuestionDrawer>
    <Drawer showCloseFooter={false} open={runErrorOpen} onOpenChange={setRunErrorOpen} title="题目处理情况"><div className="drawer-body"><Section title="哪些题未完成"><p>{errorSlot || '本次处理'} 尚未形成可供审核的题目，不能当作有效测试结果。</p></Section><Section title="卡在哪一步"><p>{stageName[qualityRerun?.slots?.[qualityRerun?.slot]?.failed_stage || qualityRerun?.stage || workRun?.artifacts?.hard_validation?.failed_stage || workRun?.status] || '处理阶段未知'}尚未通过。</p></Section><Section title="接下来怎么做"><p>回到题目列表补齐失败题；已完成的题目继续保留。</p></Section></div></Drawer>
  </PageShell>;
}

const tableSourceNames: Record<string, string> = {
  "KIRA B 50 操作说明": "KIRA 操作说明",
  "B2 用户手册": "B2 用户手册",
  "B2 电池与充电器使用说明": "B2 电池说明",
  "B2 遥控器使用说明": "B2 遥控器说明",
};
const tableSources = (summary?: string) => summary?.split(/[；;]/).map(source => source.split(" · ").map(part => tableSourceNames[readableSourceName(part)] || readableSourceName(part)).join(" · ").replace(/第\s*(\d+(?:[–—−-]\d+)?)\s*页/g, "p$1"));

export function QuestionTable({ rows, onDetail, paging, resetKey, coveragePlan }: { rows: Candidate[]; onDetail: (row: Candidate) => void; paging?: any; resetKey?: string; coveragePlan?: any }) {
  const hover = useHoverPrefetch();
  const optional = [
    {label:'业务主题',width:90,style:'muted',value:(row:Candidate)=>row.business_topic || row.raw?.business_topic || questionClassification(row, coveragePlan).topic || "未记录"},
    {label:'负向子类',width:86,style:'muted',value:(row:Candidate)=>questionClassification(row).negative},
    {label:'考查环节',width:86,style:'muted',value:(row:Candidate)=>questionClassification(row).stage},
    {label:'出处',width:160,style:'muted',value:(row:Candidate)=>{const sources=tableSources(row.source_summary || questionSources(row))?.filter(source => source !== "保存记录缺少来源");return sources?.length?`${sources[0]}${sources.length>1?` +${sources.length-1}`:''}`:'未记录';}},
    {label:'出题方式',width:76,style:'muted',value:(row:Candidate)=>row.raw?.generation_method || row.generation_method || '未记录'},
    {label:'检索探针', help:'Probe',width:65,style:'num',value:(row:Candidate)=>goldenQuality(row, 'probe')},
    {label:'质检', help:'QC',width:54,style:'num',value:(row:Candidate)=>goldenQuality(row, 'qc')},
  ];
  return <ScrollablePagedTable className="review-table" resetKey={resetKey} loading={paging?.loading} hasMore={paging?.hasMore} onMore={paging?.loadMore}><DataTable><colgroup><col style={{width:60}}/><col style={{width:60}}/><col/>{optional.map(column=><col key={column.label} style={{width:column.width}}/>)}<col style={{width:32}}/></colgroup><thead><tr><th>题号</th><th>题型</th><th>问题</th>{optional.map(column=><th key={column.label} className={column.style}>{column.label}{qualityHelp(column.help || column.label)}</th>)}<th aria-label="打开详情"/></tr></thead><tbody>{rows.slice(0, paging?.visibleCount ?? rows.length).map(row => <tr key={row.id} tabIndex={0} role="button" aria-label={`${row.slot || "题目"} · ${presentationText(row.question || "")}`} {...hover(row.failed ? [] : [`/api/governance/questions/${row.id}`])} onClick={event => { event.currentTarget.focus(); onDetail(row); }} onKeyDown={event => { if (event.target === event.currentTarget && (event.key === "Enter" || event.key === " ")) { event.preventDefault(); onDetail(row); } }}><td className="id">{row.slot || row.raw?.coverage_slot || row.id}</td><td className="muted">{({positive:"正向",ablation:"消融",negative:"负向"} as Record<string,string>)[row.test_category] || displayText(row.test_category || (row.failed ? "生成失败" : "类型未记录"))}</td><td><TruncatedText lines={1}>{presentationText(row.question || "")}</TruncatedText></td>{optional.map(column=><td key={column.label} className={column.style}>{<TruncatedText lines={1}>{column.label === "出处" ? <HoverCard content={row.source_summary || questionSources(row)}><span>{column.value(row) ?? "未记录"}</span></HoverCard> : column.value(row) ?? "未记录"}</TruncatedText>}</td>)}<td><span className="ui-row-go"><Icon name="go" size={15}/></span></td></tr>)}{!rows.length && !paging?.loading && !paging?.error && <tr><td colSpan={4+optional.length} className="empty-state">还没有符合筛选条件的题目。<p>题目完成生成与校验后会显示在这里。</p></td></tr>}</tbody></DataTable></ScrollablePagedTable>;
}
