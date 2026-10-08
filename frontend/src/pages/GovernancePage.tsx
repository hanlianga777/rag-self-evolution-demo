import { PageShell } from "../components/PageShell";
import { useEffect, useMemo, useRef, useState } from "react";
import { apiUrl, errorMessage, getJson, postJson } from "../api";
import { Badge, CustomSelect, Section, ShortId, StageStepper, Status, TruncatedText } from "../components/Primitives";
import { ConfirmDialog, Drawer } from "../components/Dialog";
import { displayText } from "../display";
import { useOperation } from "../operation";
import { BusinessImportPanel, CoverageSummary, CurrentCoveragePreview } from "./BusinessImportPanel";
import { CandidateWorkspace } from "./CandidateWorkspace";

import { goldenCached, goldenFetch, invalidateGolden } from "../goldenCache";
import { ScrollablePagedTable, usePagedCandidates } from "../components/ScrollablePagedTable";

type Candidate = Record<string, any>;
type Filter = string;

const stageName: Record<string, string> = { queued: "排队中", coverage: "规划覆盖", generating: "逐题生成与修复", validation: "硬校验", needs_regeneration: "待补齐失败题", probing: "检索验证", qc: "质量检查", completed: "已完成", failed: "运行失败" };
const probeLabel = (value?: string) => value === "probe_passed" ? "通过" : value === "needs_revision" ? "未通过" : "未运行";
const qcLabel = (value?: string) => value === "qc_passed" ? "通过" : value === "qc_failed" ? "未通过" : "未运行";
const reviewLabel = (row: Candidate) => displayText(row.review_status || "human_review_pending");

export function GovernancePage({ data }: { data: any }) {
  const operation = useOperation();
  const cacheIdentity = JSON.stringify(data.workspace?.current_corpus_fingerprint);
  const [syncing, setSyncing] = useState(false), [newRunConfirm, setNewRunConfirm] = useState(false);
  const [tab, setTab] = useState<"run" | "import">("run");
  const [historyOpen, setHistoryOpen] = useState(false);
  const refreshTicket = useRef(0);
  const [profile, setProfile] = useState<"mini" | "medium" | "full">("mini");
  const [historyPage, setHistoryPage] = useState(0);
  const [items, setItems] = useState<Candidate[]>(data.dataset || []);
  const [runs, setRuns] = useState<Candidate[]>(goldenCached<Candidate[]>(cacheIdentity, "/api/governance/generation-runs?light=true") || data.generationRuns || []);
  const [snapshots, setSnapshots] = useState<Candidate[]>(data.snapshots || []);
  const [revisions, setRevisions] = useState<Candidate[]>([]);
  const [filter, setFilter] = useState<Filter>("attention");
  const [rerunConfirm, setRerunConfirm] = useState(false);
  const [poolDetail, setPoolDetail] = useState<Candidate | null>(null);
  const [detailStatus, setDetailStatus] = useState("");
  const poolTicket = useRef(0);
  const [candidateDirty, setCandidateDirty] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const actionPending = useRef(false);
  const [error, setError] = useState("");
  const [runErrorOpen, setRunErrorOpen] = useState(false);
  const [runDetailsOpen, setRunDetailsOpen] = useState(false), [auditRun, setAuditRun] = useState<Candidate | null>(null);
  const [errorSlot, setErrorSlot] = useState<string | null>(null);
  const [now, setNow] = useState(Date.now());
  const [runDuration, setRunDuration] = useState<{ id: string; ms: number } | null>(null);
  const workRun = runs[0];
  const listPath = `/api/governance/candidates?run_id=${workRun?.id}&status=${filter === "attention" ? "attention" : filter === "pending" ? "machine" : "all"}&group=${["positive","ablation","negative"].includes(filter) ? filter : "all"}`;
  const paged = usePagedCandidates(JSON.stringify([cacheIdentity, workRun?.id, workRun?.profile?.name]), listPath, !!(workRun?.question_ids?.length || workRun?.artifacts?.hard_validation?.slot_persistence_v1));
  const latestReview = useRef(paged.refresh); latestReview.current = paged.refresh;
  const review: Candidate[] = paged.rows, currentIndex: Candidate[] = paged.candidate_index || [], listing = paged.loading;
  const currentGolden = snapshots.find(snapshot => snapshot.id === data.workspace?.current_golden_id);
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
  const gate1Snapshot = snapshots.find(snapshot => snapshot.snapshot?.generation_run_id === workRun?.id && JSON.stringify(snapshot.snapshot?.question_ids) === JSON.stringify(currentIds));
  const plannedSlots = new Map((workRun?.artifacts?.question_plan || []).map((row: Candidate) => [row.question_id, row.coverage_slot]));
  const current: Candidate[] = currentIds.map(id => currentIndex.find(row => row.id === id) || review.find(row => row.id === id) || items.find(row => row.id === id)).filter((row): row is Candidate => !!row).map(row => ({ ...row, slot: row.slot || row.raw?.coverage_slot || plannedSlots.get(row.id) }));
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
    setSyncing(true);
    try {
      const [generationRuns, goldenSnapshots] = await Promise.all([
        goldenFetch<Candidate[]>(cacheIdentity, "/api/governance/generation-runs?light=true"), goldenFetch<Candidate[]>(cacheIdentity, "/api/governance/snapshots"),
      ]);
      if (ticket !== refreshTicket.current) return;
      setRuns(generationRuns); setSnapshots(goldenSnapshots);
      await loadReview(generationRuns[0], ticket);
      if (selectedId) { const detail = await getJson<Candidate>(`/api/governance/questions/${selectedId}`); if (ticket === refreshTicket.current) setPoolDetail(detail); }
    } finally { if (ticket === refreshTicket.current) setSyncing(false); }

  };
  useEffect(() => () => { refreshTicket.current++; }, []);
  useEffect(() => {
    operation.registerCandidateRefresh(reload);
    return () => operation.unregisterCandidateRefresh(reload);
  }, [operation.registerCandidateRefresh, operation.unregisterCandidateRefresh, reload]);
  useEffect(() => {
    if (!data.generationRuns) void reload().catch(reason => setError(errorMessage(reason)));
    else { void loadReview(data.generationRuns[0]).catch(reason => setError(errorMessage(reason))); if (data.generationRuns[0]?.question_ids?.length === (data.generationRuns[0]?.profile?.expected_count || 20)) void getJson<Candidate[]>("/api/governance/revisions").then(value => setRevisions(Array.isArray(value) ? value : [])).catch(() => {}); }
  }, [data.generationRuns]);
  useEffect(() => {
    if ((!running && !qualityRunning) || !workRun?.id) return;
    let cancelled = false;
    const poll = async () => {
      try {
        const updated = await getJson<Candidate>(`/api/governance/generation-runs/${workRun.id}`);
        if (cancelled) return;
        setRuns(previous => [updated, ...previous.filter(row => row.id !== updated.id)]);
        if (updated.artifacts?.hard_validation?.slot_persistence_v1 || updated.question_ids?.length === (updated.profile?.expected_count || expectedCount)) void loadReview(updated).catch(reason => setError(errorMessage(reason)));
        if (["completed", "failed"].includes(updated.status) && updated.created_at) setRunDuration({ id: updated.id, ms: Date.now() - Date.parse(updated.created_at) });
        if (["completed", "failed", "needs_regeneration"].includes(updated.status) && (running || updated.artifacts?.hard_validation?.quality_rerun?.status !== "running")) void reload().catch(reason => setError(errorMessage(reason)));
      } catch (reason) { if (!cancelled) setError(errorMessage(reason)); }
    };
    void poll();
    const timer = window.setInterval(() => void poll(), 1000);
    return () => { cancelled = true; window.clearInterval(timer); };
  }, [workRun?.id, workRun?.status, qualityRunning]);


  const needsAttention = (row: Candidate) => row.qualification_status ? row.qualification_status === "needs_human_review" : row.stage !== "golden" && (row.probe_status !== "probe_passed" || row.qc_status !== "qc_passed") || ["P0", "P1"].includes(row.qc?.priority) || ["FAKE_NEGATIVE_RISK", "RETRIEVAL_INCOHERENT", "RETRIEVAL_EXECUTION_FAILED"].includes(row.probe?.probe_details?.classification) || ["needs_revision", "rejected"].includes(row.review_status) || row.approval_eligibility?.blocking_reasons?.length > 0 || row.approval_eligibility?.requires_qc_p0_acceptance;
  const anomalies = current.filter(row => row.stage !== "golden" && (row.probe_status !== "probe_passed" || row.qc_status !== "qc_passed"));
  const attention = current.filter(needsAttention);
  const filters = useMemo(() => [
    { key: "attention", label: "需要人工关注", count: attention.length, match: needsAttention },
    { key: "all", label: "全部", count: current.length, match: (_row: Candidate) => true },
    { key: "positive", label: "正向", count: current.filter(row => row.test_category === "positive").length, match: (row: Candidate) => row.test_category === "positive" },
    { key: "ablation", label: "消融题", count: current.filter(row => row.test_category === "ablation").length, match: (row: Candidate) => row.test_category === "ablation" },
    { key: "negative", label: "负向", count: current.filter(row => row.test_category === "negative").length, match: (row: Candidate) => row.test_category === "negative" },
    { key: "pending", label: "机器合格", count: current.filter(row => row.qualification_status === "machine_qualified").length, match: (row: Candidate) => row.qualification_status === "machine_qualified" },
  ] as const, [current]);
  const riskFilters = [
    { key: "probe-risk", label: "Probe 未通过", match: (row: Candidate) => row.probe_status === "needs_revision" },
    { key: "qc-risk", label: "QC 未通过", match: (row: Candidate) => row.qc_status === "qc_failed" },
    { key: "p0", label: "QC P0", match: (row: Candidate) => row.qc?.priority === "P0" },
    { key: "p1", label: "QC P1", match: (row: Candidate) => row.qc?.priority === "P1" },
    { key: "p0-acceptance", label: "QC P0 待人工接受", match: (row: Candidate) => row.approval_eligibility?.requires_qc_p0_acceptance && row.approval_eligibility?.blocking_reasons?.length === 0 },
    { key: "fake-negative", label: "疑似伪负向", match: (row: Candidate) => row.probe?.probe_details?.classification === "FAKE_NEGATIVE_RISK" },
    { key: "retrieval-incoherent", label: "检索不连贯", match: (row: Candidate) => row.probe?.probe_details?.classification === "RETRIEVAL_INCOHERENT" },
    { key: "execution-failed", label: "检索执行失败", match: (row: Candidate) => row.probe?.probe_details?.probe_execution_status === "failed" || row.probe?.probe_details?.classification === "RETRIEVAL_EXECUTION_FAILED" },
    { key: "approval-blocked", label: "审批阻断", match: (row: Candidate) => row.approval_eligibility?.blocking_reasons?.length > 0 },
    { key: "revision-risk", label: "需修订 / 已拒绝", match: (row: Candidate) => ["needs_revision", "rejected"].includes(row.review_status) },
  ].map(item => ({ ...item, count: current.filter(item.match).length })).filter(item => item.count > 0);
  const listRows = review.length || currentIndex.length ? review : current.filter(row => row.question);
  const visible = filter === "attention" && !attention.length ? listRows : listRows.filter(filters.find(item => item.key === filter)?.match || (() => true));
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
  const rerunQuality = async () => {
    setBusy(true); setError("");
    try {
      await postJson(`/api/governance/generation-runs/${workRun.id}/rerun-quality?anomalies_only=true`);
      invalidateGolden(); setRerunConfirm(false);
      const updated = await getJson<Candidate>(`/api/governance/generation-runs/${workRun.id}`);
      setRuns(previous => [updated, ...previous.filter(row => row.id !== updated.id)]);
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

  const openRunAudit = async () => {
    setAuditRun(workRun); setRunDetailsOpen(true);
    try { const detail = await getJson<Candidate>(`/api/governance/generation-runs/${workRun.id}`);
      if (detail.artifacts?.hard_validation?.frozen_plan?.generation_strategy === "business_v2") detail.naturalness_audit = await getJson(`/api/governance/generation-runs/${workRun.id}/naturalness-audit`);
      setAuditRun(detail); }
    catch (reason) { setError(errorMessage(reason)); }
  };
  const openPoolDetail = async (row: Candidate) => {
    const ticket = ++poolTicket.current;
    setPoolDetail(row); setSelectedId(row.id); setDetailStatus("正在读取候选题详情…");
    try { const result = await getJson<Candidate>(`/api/governance/questions/${row.id}`); if (ticket === poolTicket.current) { setPoolDetail(result); setRevisions(result.revision_history || []); setDetailStatus(""); } }
    catch (reason) { if (ticket === poolTicket.current) setDetailStatus(errorMessage(reason)); }

  };
  return <PageShell className={`page governance-page ${!workRun && tab === "run" ? "is-empty" : ""}`} header={<div className="page-title"><div><h1>Golden Dataset</h1><p>机器批量治理，人工处理异常，最终确认冻结。</p></div><div className="header-actions">{!workRun && <button className="secondary" onClick={() => setHistoryOpen(true)}>历史版本</button>}{tab === "run" && <>{workRun?.status === "needs_regeneration" && <button className="primary" disabled={busy} onClick={() => void regenerate()}>补齐失败题（{expectedCount - current.length}）</button>}{workRun?.status !== "needs_regeneration" && <><label className="profile-selector"><CustomSelect ariaLabel="测试集 Profile" value={profile} onChange={value => setProfile(value as typeof profile)} options={Object.entries(data.overview?.generation_profiles || {}).map(([value, counts]: [string, any]) => ({ value, label: `${value.toUpperCase()} · ${counts.expected_count}题（${counts.positive_count} / ${counts.ablation_count} / ${counts.negative_count}）` }))} /></label><>{workRun ? <button className="secondary" disabled={busy || running || qualityRunning} onClick={() => setNewRunConfirm(true)}>新建测试集</button> : <button className="secondary" disabled={busy} onClick={() => void createMini()}>生成测试集</button>}</></>}</>}</div></div>} tabs={<div className="tabs"><button aria-pressed={tab === "run"} className={tab === "run" ? "active" : ""} onClick={() => setTab("run")}>当前测试集</button><button aria-pressed={tab === "import"} className={tab === "import" ? "active" : ""} onClick={() => setTab("import")}>候选池</button></div>} resetKey={tab}>

    {error && <p className="error-notice" role="alert">{error}</p>}
    {tab === "run" && <div className="golden-workspace">

      <div className="golden-summary-strip" role="status"><strong>{workRun?.artifacts?.hard_validation?.frozen_plan?.dataset_label ? "V2 工作集 · " : ""}{workRun?.profile?.name?.toUpperCase() || "未生成"} · {current.length} / {expectedCount} Slot</strong><span>{["positive", "ablation", "negative"].map(group => `${group === "positive" ? "正向" : group === "ablation" ? "消融" : "负向"} ${current.filter(row => row.test_category === group).length} / ${workRun?.profile?.[`${group}_count`] ?? workRun?.profile?.[group] ?? "—"}`).join(" · ")}</span><span>自动校验通过 {current.filter(row => row.probe_status === "probe_passed" && row.qc_status === "qc_passed").length} · 机器合格 {current.filter(row => row.qualification_status === "machine_qualified").length} · 重点复核 {attention.length}</span><Badge tone="warning">Human Gate 1 · {gate1Snapshot ? "已人工确认" : workRun?.human_gate?.status === "ready" ? "Ready · 待确认" : "Pending"}</Badge><CoverageSummary run={workRun} questions={current} documents={data.documents || []} persistedPlan={data.overview?.knowledge?.coverage} /></div>
      <StageStepper compact ariaLabel="Golden 治理阶段" steps={[
        { label: "Coverage", state: workRun?.artifacts?.coverage_plan?.length ? "completed" : "current" },
        { label: "Generation", state: current.length === expectedCount ? "completed" : running ? "current" : "pending" },
        { label: "Hard Validation", state: current.length === expectedCount ? "completed" : "pending" },
        { label: "Probe", state: current.length === expectedCount && current.every(row => row.probe_status === "probe_passed") ? "completed" : workRun?.status === "probing" ? "current" : current.some(row => ["probe_passed", "needs_revision"].includes(row.probe_status)) ? "blocked" : "pending", detail: `${current.filter(row => row.probe_status === "probe_passed").length} / ${expectedCount} 通过` },
        { label: "QC", state: current.length === expectedCount && current.every(row => row.qc_status === "qc_passed") ? "completed" : workRun?.status === "qc" ? "current" : current.some(row => ["qc_passed", "qc_failed"].includes(row.qc_status)) ? "blocked" : "pending", detail: `${current.filter(row => row.qc_status === "qc_passed").length} / ${expectedCount} 通过` },
        { label: "Human Gate", state: gate1Snapshot ? "completed" : workRun?.human_gate?.status === "ready" ? "current" : workRun?.status === "completed" && attention.length ? "blocked" : "pending", detail: "异常治理与数据集确认" },
      ]} />
      {workRun ? <Section title="Candidate 审核" action={<div className="header-actions"><Badge tone={attention.length ? "warning" : "good"}>{attention.length ? "需要关注" : current.length === expectedCount ? "机器检查完成" : "待补齐"}</Badge><button className="secondary" disabled={busy || qualityRunning || !anomalies.length || workRun.status !== "completed"} onClick={() => setRerunConfirm(true)}>批量重跑异常项</button><button className="secondary" onClick={() => setHistoryOpen(true)}>历史版本</button></div>}>
        <div className="review-filters" aria-label="Candidate 筛选">{filters.map(item => <button key={item.key} aria-pressed={filter === item.key} className={filter === item.key ? "active" : ""} onClick={() => setFilter(item.key)}>{item.label} {item.count}</button>)}        <small className="muted golden-review-role" role="status">{syncing || listing ? "正在同步…" : filter === "attention" && !attention.length ? "无异常，展示机器合格题" : ""}</small></div>

        {(syncing || listing) && !listRows.length ? <div className="golden-skeleton" role="status" aria-label="正在读取候选题">{[1,2,3,4].map(index => <span key={index} aria-hidden="true" />)}</div> : <QuestionTable rows={["all", "attention"].includes(filter) ? [...visible, ...failedSlots.map(slot => ({ id: `missing-${slot}`, slot, question: "生成失败，待补齐", failed: true }))].sort((a, b) => String(a.slot || "").localeCompare(String(b.slot || ""))) : visible} onDetail={row => row.failed ? (setErrorSlot(row.slot), setRunErrorOpen(true)) : void openPoolDetail(row)} paging={paged} resetKey={listPath} />}
        {paged.error && <p role="alert" className="error-notice">{paged.error}</p>}
        {current.length === expectedCount && workRun.status === "completed" && !gate1Snapshot && <div className="review-batch gate-one-action"><label><input type="checkbox" checked={confirmed} onChange={event => setConfirmed(event.target.checked)} /> 我确认异常已关闭，并冻结当前 Golden Dataset</label><button className="primary" title={batchReason} disabled={busy || !!batchReason} onClick={() => void action(() => postJson("/api/governance/review-batch", { question_ids: currentIds, confirmed_manual_review: true }), "确认 Golden 测试集")}>确认并冻结 Golden Dataset</button></div>}
      </Section> : <Section title="Candidate 审核" action={<button className="secondary" onClick={() => setHistoryOpen(true)}>历史 Snapshot</button>}><p className="muted">尚未生成工作 Run，可生成题目或从候选池创建测试集。</p><CurrentCoveragePreview profile={profile} corpusFingerprint={data.workspace?.current_corpus_fingerprint} documents={data.documents || []} /></Section>}
    </div>}
    <ConfirmDialog open={newRunConfirm} onOpenChange={setNewRunConfirm} title="新建测试集" busy={busy} onConfirm={() => { setNewRunConfirm(false); void createMini(); }}><p>当前 Run 尚未完成最终确认。开始新 Run 将使用真实 Provider 并消耗 Token，是否继续？</p></ConfirmDialog>
    <ConfirmDialog open={rerunConfirm} onOpenChange={setRerunConfirm} title="批量重跑异常项" busy={busy} onConfirm={() => void rerunQuality()}><p>仅处理 {anomalies.length} 道失败或中断题目；已通过题目不会重跑。将执行所需 Probe / QC 外部调用。</p></ConfirmDialog>
    {tab === "import" && <BusinessImportPanel profiles={data.overview?.generation_profiles || {}} items={items} onCreated={refreshAfterMutation} onDetail={row => void openPoolDetail(row)} initialProfile={profile} currentQuestionIds={currentIds} coveragePlan={workRun?.artifacts?.hard_validation?.frozen_plan} corpusFingerprint={data.workspace?.current_corpus_fingerprint} />}
    <Drawer showCloseFooter={false} open={runDetailsOpen} onOpenChange={setRunDetailsOpen} title="工作 Run 构造与质量记录"><div className="drawer-body">{auditRun?.naturalness_audit?.question_count != null && <Section title="数据集自然度与多样性"><p>本地诊断 · {auditRun.naturalness_audit.question_count}题 · 提供修订建议，不新增冻结门槛。差异追溯最近一次修订，包含历史修订。</p><p>{Object.entries(auditRun.naturalness_audit.frequencies).map(([phrase,count])=>`${phrase} ${count}题`).join(" · ")}</p>{auditRun.naturalness_audit.questions.filter((item:Candidate)=>item.findings.length || item.changed).map((item:Candidate)=><details key={item.question_id}><summary>{item.slot || item.question_id} · {item.findings.map((finding:Candidate)=>finding.type).join(" / ") || "已改写"}</summary><p>{item.before}</p>{item.changed && <p>修订后：{item.after}</p>}{item.findings.map((finding:Candidate,index:number)=><p key={index}>{finding.reason}；建议：{finding.action}</p>)}</details>)}</Section>}{workRun && <><div className="run-summary">当前阶段：{stageName[workRun.status] || displayText(workRun.status)} · Run ID：{workRun.id} · Slot {operationProgress?.processed_slots ?? 0} / {operationProgress?.expected_slots ?? expectedCount}{progress?.slot ? ` · ${progress.slot}` : ""} · Probe {operationProgress?.probe_processed ?? 0} / {expectedCount} · QC {operationProgress?.qc_processed ?? 0} / {expectedCount}{progress?.qc_skipped ? ` · QC 跳过 ${progress.qc_skipped}` : ""}{elapsed ? ` · 运行耗时 ${elapsed}` : ""}{running ? " · 状态来自数据库（Worker 未验证）" : ""}{workRun.status === "failed" && <button className="text-button" onClick={() => { setErrorSlot(null); setRunErrorOpen(true); }}>查看错误</button>}</div>
        <CurrentCoveragePreview profile={profile} corpusFingerprint={data.workspace?.current_corpus_fingerprint} documents={data.documents || []} /><div className="generation-progress" role="status">{operationProgress && <span>{operationProgress.phase_label} · 已处理 {operationProgress.phase_processed}/{operationProgress.phase_total} · {operationProgress.phase_percent}% · Round {operationProgress.refill_round}/{operationProgress.refill_max_rounds} · 剩余 {operationProgress.failed_count} 道 · Hard Valid {operationProgress.hard_valid_completed}/{operationProgress.hard_valid_total} · Probe {operationProgress.probe_processed}/{expectedCount} · QC {operationProgress.qc_processed}/{expectedCount}</span>}</div><div className="run-summary">当前 Golden：{currentGolden ? `${goldenCount} 题 · ${goldenV2 ? "V2" : "Legacy"} · Frozen` : "尚未冻结"} · {goldenCategoriesComplete ? "分类完整" : "分类需核对"}</div>{qualityRerun && <p>质量重跑：{displayText(qualityRerun.status)} · {qualityRerun.completed || 0} / {qualityRerun.total || expectedCount} · {qualityRerun.error || ""}</p>}{riskFilters.map(item => <p key={item.key}>{item.label} · {item.count}</p>)}
        {Object.entries(auditRun?.artifacts?.slot_audit || workRun.artifacts?.slot_audit || {}).filter(([, attempts]) => (attempts as Candidate[]).some(attempt => attempt.validation_error)).map(([slot, attempts]) => <details className="slot-audit" key={slot}><summary>{slot} · {(attempts as Candidate[]).length} 次尝试 · {(attempts as Candidate[]).at(-1)?.validation_error ? "未通过" : "重试后通过"}</summary>{(attempts as Candidate[]).map(attempt => <div key={attempt.attempt}><strong>第 {attempt.attempt} 次尝试</strong><p>问题：{attempt.question || "—"}</p><p>答案：{attempt.reference_answer || "—"}</p><p>证据：{attempt.selected_evidence?.map((item: Candidate) => `${item.document_name || item.document_id} · ${item.chunk_id} · ${item.chunk_text}`).join("；") || "—"}</p><pre>{attempt.validation_error || "通过"}</pre></div>)}</details>)}</>}</div></Drawer>
    <Drawer showCloseFooter={false} open={historyOpen} onOpenChange={setHistoryOpen} title="Golden 历史版本"><div className="drawer-body snapshot-history"><Section title="当前工作集高级功能"><div className="header-actions"><button className="secondary" disabled={!workRun} onClick={() => { setHistoryOpen(false); void openRunAudit(); }}>运行审计</button>{workRun && current.length === expectedCount && (["markdown", "csv", "json"] as const).map(format => <a className="secondary" key={format} href={apiUrl(`/api/governance/generation-runs/${workRun.id}/export?format=${format}`)} download>导出 {format.toUpperCase()}</a>)}</div></Section><Section title="已确认 Golden Snapshots"><div className="run-list">{snapshots.map(snapshot => <div key={snapshot.id}><strong><ShortId value={snapshot.id} /></strong><span>{snapshot.snapshot?.profile?.name || "Legacy"} · {snapshot.snapshot?.question_ids?.length || 0} 题 · {snapshot.created_at || "冻结时间未记录"}</span><Status value={snapshot.status} /></div>)}{!snapshots.length && <p className="muted">尚未创建正式 Golden Snapshot。</p>}</div></Section><Section title="历史 Candidate（未验证）"><details><summary>{historical.length} 道历史 Candidate</summary><p className="muted">仅供追溯，不参与当前 Golden、Baseline 或发布判断。</p><QuestionTable rows={historical.slice(historyPage * 10, historyPage * 10 + 10)} onDetail={row => setSelectedId(row.id)} /><div className="history-pagination"><button className="secondary" disabled={historyPage === 0} onClick={() => setHistoryPage(page => page - 1)}>上一页</button><span>{historyPage + 1} / {Math.max(1, Math.ceil(historical.length / 10))}</span><button className="secondary" disabled={(historyPage + 1) * 10 >= historical.length} onClick={() => setHistoryPage(page => page + 1)}>下一页</button></div></details></Section></div></Drawer>
    <Drawer showCloseFooter={false} guardEdits editDirty={candidateDirty} contentKey={candidateContentKey} open={!!selected} onOpenChange={open => { if (!open) { poolTicket.current++; setSelectedId(null); } }} title={selected ? `${selected.slot || "历史题"} · ${displayText(selected.test_category)}` : "候选题审核"} className="candidate-workspace">{detailStatus ? <p className="drawer-body" role="status">{detailStatus}</p> : <CandidateWorkspace key={candidateContentKey} row={selected} peers={current} revision={revisions.find(item => item.question_ids?.includes(selected?.id))} rerunSlot={qualityRerun?.slots?.[selected?.slot]} busy={busy} readOnly={partial || !currentIds.includes(selected?.id || "")} readOnlyReason={!currentIds.includes(selected?.id || "") ? "来源候选题只读；匹配 Profile 与 Coverage Slot 后创建待审核副本。" : undefined} onRun={questionAction} onReview={reviewAction} onRefresh={refreshAfterMutation} operation={operation} onDirtyChange={setCandidateDirty} />}</Drawer>
    <Drawer showCloseFooter={false} open={runErrorOpen} onOpenChange={setRunErrorOpen} title="Run 错误详情"><div className="drawer-body"><p>阶段：{qualityRerun?.status === "failed" ? qualityRerun?.slots?.[qualityRerun?.slot]?.failed_stage || qualityRerun?.stage : stageName[workRun?.artifacts?.hard_validation?.failed_stage] || stageName[workRun?.status] || "未知"}</p>{errorSlot && (workRun?.artifacts?.slot_audit?.[errorSlot] || []).map((attempt: Candidate) => <div key={attempt.attempt}><h3>{errorSlot} · 第 {attempt.attempt} 次尝试</h3><p>问题：{attempt.question || "—"}</p><p>答案：{attempt.reference_answer || "—"}</p><p>证据：{attempt.selected_evidence?.map((item: Candidate) => `${item.document_name || item.document_id} · ${item.chunk_id} · ${item.chunk_text}`).join("；") || "—"}</p><pre>{attempt.validation_error || "通过"}</pre></div>)}{!errorSlot && <pre>{qualityRerun?.status === "failed" ? qualityRerun.error : workRun?.artifacts?.hard_validation?.error || "请查看运行详情中的 Slot Audit"}</pre>}</div></Drawer>
  </PageShell>;
}

function QuestionTable({ rows, onDetail, paging, resetKey }: { rows: Candidate[]; onDetail: (row: Candidate) => void; paging?: any; resetKey?: string }) {
  return <ScrollablePagedTable className="review-table" resetKey={resetKey} loading={paging?.loading} hasMore={paging?.hasMore} onMore={paging?.loadMore}><table><thead><tr><th>#</th><th>类型</th><th>问题</th><th>Probe</th><th>QC</th><th>资格 / 关注原因</th><th>操作</th></tr></thead><tbody>{rows.map(row => <tr key={row.id} tabIndex={0} onClick={() => onDetail(row)} onKeyDown={event => { if (event.key === "Enter") { event.preventDefault(); onDetail(row); } }}><td>{row.slot || row.id}</td><td><Badge tone={row.test_category === "negative" ? "warning" : "neutral"}>{row.test_category ? displayText(row.test_category) : "未记录"}</Badge><small className="question-provenance">{(row.construction_type || row.raw?.construction_type) && `${row.construction_type || row.raw?.construction_type} · `}{row.raw?.source === "business_import" ? "业务导入" : row.raw?.generation_run_id ? "AI 生成" : "历史来源"}</small></td><td><TruncatedText lines={2}>{row.question}</TruncatedText></td><td>{probeLabel(row.probe_status)}</td><td>{qcLabel(row.qc_status)}{row.qc?.priority === "P1" ? " · P1" : ""}</td><td>{row.qualification_status === "machine_qualified" ? "机器合格" : row.qualification_status === "human_approved" ? "人工通过" : row.attention_reasons?.[0] || reviewLabel(row)}</td><td><button className="secondary" onClick={() => onDetail(row)}>{row.failed ? "查看错误" : "查看详情"}</button></td></tr>)}{!rows.length && <tr><td colSpan={7} className="empty-state">暂无对应数据。</td></tr>}</tbody></table></ScrollablePagedTable>;
}
