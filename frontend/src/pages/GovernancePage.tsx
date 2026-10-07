import { PageShell } from "../components/PageShell";
import { useEffect, useMemo, useRef, useState } from "react";
import { apiUrl, errorMessage, getJson, postJson } from "../api";
import { Badge, CustomSelect, Section, ShortId, StageStepper, Status, TruncatedText } from "../components/Primitives";
import { ConfirmDialog, Drawer } from "../components/Dialog";
import { displayText } from "../display";
import { useOperation } from "../operation";
import { BusinessImportPanel, CoverageSummary, CurrentCoveragePreview } from "./BusinessImportPanel";
import { CandidateWorkspace } from "./CandidateWorkspace";

type Candidate = Record<string, any>;
type Filter = string;

const stageName: Record<string, string> = { queued: "排队中", coverage: "规划覆盖", generating: "逐题生成与修复", validation: "硬校验", needs_regeneration: "待补齐失败题", probing: "检索验证", qc: "质量检查", completed: "已完成", failed: "运行失败" };
const probeLabel = (value?: string) => value === "probe_passed" ? "通过" : value === "needs_revision" ? "未通过" : "未运行";
const qcLabel = (value?: string) => value === "qc_passed" ? "通过" : value === "qc_failed" ? "未通过" : "未运行";
const reviewLabel = (row: Candidate) => displayText(row.review_status || "human_review_pending");

export function GovernancePage({ data }: { data: any }) {
  const operation = useOperation();
  const [tab, setTab] = useState<"run" | "import">("run");
  const [historyOpen, setHistoryOpen] = useState(false);
  const refreshTicket = useRef(0);
  const [profile, setProfile] = useState<"mini" | "medium" | "full">("mini");
  const [historyPage, setHistoryPage] = useState(0);
  const [items, setItems] = useState<Candidate[]>(data.dataset || []);
  const [runs, setRuns] = useState<Candidate[]>(data.generationRuns || []);
  const [snapshots, setSnapshots] = useState<Candidate[]>(data.snapshots || []);
  const [review, setReview] = useState<Candidate[]>([]);
  const [revisions, setRevisions] = useState<Candidate[]>([]);
  const [filter, setFilter] = useState<Filter>("attention");
  const [rerunConfirm, setRerunConfirm] = useState(false);
  const [poolDetail, setPoolDetail] = useState<Candidate | null>(null);
  const poolTicket = useRef(0);
  const [candidateDirty, setCandidateDirty] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [runErrorOpen, setRunErrorOpen] = useState(false);
  const [runDetailsOpen, setRunDetailsOpen] = useState(false);
  const [errorSlot, setErrorSlot] = useState<string | null>(null);
  const [now, setNow] = useState(Date.now());
  const [runDuration, setRunDuration] = useState<{ id: string; ms: number } | null>(null);
  const workRun = runs[0];
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
  const current: Candidate[] = currentIds.map(id => review.find(row => row.id === id) || items.find(row => row.id === id)).filter((row): row is Candidate => !!row).map(row => ({ ...row, slot: row.slot || row.raw?.coverage_slot || plannedSlots.get(row.id) }));
  const historical = items.filter(row => !currentIds.includes(row.id) && row.stage !== "golden");
  const selected = current.find(row => row.id === selectedId) || (poolDetail?.id === selectedId ? poolDetail : items.find(row => row.id === selectedId));
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

  const loadReview = async (run: Candidate | undefined, ticket = refreshTicket.current) => {
    const count = run?.profile?.expected_count || 20;
    if (run && (run.question_ids?.length || run.artifacts?.hard_validation?.slot_persistence_v1)) {
      const path = run.question_ids?.length === count ? `/api/governance/generation-runs/${run.id}/export?format=json` : `/api/governance/generation-runs/${run.id}/questions`;
      const result = await getJson<{ questions: Candidate[] }>(path);
      if (ticket !== refreshTicket.current) return;
      setReview(Array.isArray(result?.questions) ? result.questions : []);
    } else setReview([]);
  };
  const reload = async () => {
    const ticket = ++refreshTicket.current;
    const [questions, generationRuns, goldenSnapshots, revisionRuns] = await Promise.all([
      getJson<Candidate[]>("/api/dataset"), getJson<Candidate[]>("/api/governance/generation-runs"), getJson<Candidate[]>("/api/governance/snapshots"), getJson<Candidate[]>("/api/governance/revisions"),
    ]);
    if (ticket !== refreshTicket.current) return;
    setItems(questions); setRuns(generationRuns); setSnapshots(goldenSnapshots); setRevisions(Array.isArray(revisionRuns) ? revisionRuns : []);
    await loadReview(generationRuns[0], ticket);
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

  const needsAttention = (row: Candidate) => row.stage !== "golden" && (row.probe_status !== "probe_passed" || row.qc_status !== "qc_passed") || ["P0", "P1"].includes(row.qc?.priority) || ["FAKE_NEGATIVE_RISK", "RETRIEVAL_INCOHERENT", "RETRIEVAL_EXECUTION_FAILED"].includes(row.probe?.probe_details?.classification) || ["needs_revision", "rejected"].includes(row.review_status) || row.approval_eligibility?.blocking_reasons?.length > 0 || row.approval_eligibility?.requires_qc_p0_acceptance;
  const anomalies = current.filter(row => row.stage !== "golden" && (row.probe_status !== "probe_passed" || row.qc_status !== "qc_passed"));
  const attention = current.filter(needsAttention);
  const filters = useMemo(() => [
    { key: "attention", label: "需要人工关注", count: attention.length, match: needsAttention },
    { key: "all", label: "全部", count: current.length, match: (_row: Candidate) => true },
    { key: "positive", label: "正向", count: current.filter(row => row.test_category === "positive").length, match: (row: Candidate) => row.test_category === "positive" },
    { key: "ablation", label: "消融题", count: current.filter(row => row.test_category === "ablation").length, match: (row: Candidate) => row.test_category === "ablation" },
    { key: "negative", label: "负向", count: current.filter(row => row.test_category === "negative").length, match: (row: Candidate) => row.test_category === "negative" },
    { key: "pending", label: "待人工审核", count: current.filter(row => (row.review_status || "human_review_pending") === "human_review_pending").length, match: (row: Candidate) => (row.review_status || "human_review_pending") === "human_review_pending" },
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
  const visible = filter === "attention" && !attention.length ? current.filter(row => (row.review_status || "human_review_pending") === "human_review_pending") : current.filter(filters.find(item => item.key === filter)?.match || (() => true));
  const gateBlocked = current.filter(row => row.stage !== "golden" && !(row.approval_eligibility?.can_approve ?? (row.probe_status === "probe_passed" && row.qc_status === "qc_passed")));
  const manualBlocked = current.filter(row => ["needs_revision", "rejected"].includes(row.review_status) || row.approval_eligibility?.requires_qc_p0_acceptance);
  const batchReason = current.length !== expectedCount ? `本轮尚未完整入库 ${expectedCount} 道题` : gateBlocked.length || manualBlocked.length ? `仍有 ${new Set([...gateBlocked, ...manualBlocked].map(row => row.id)).size} 道题需逐题处理或接受 QC P0 风险` : gate1Snapshot ? "本轮已确认 Golden 测试集" : !confirmed ? "请先确认已人工审核全部有效 Candidate" : "";
  const action = async (work: () => Promise<unknown>, title: string) => {
    setBusy(true); setError("");
    try { await operation.run(title, async () => { await work(); try { await reload(); } catch (reason) { throw new Error(`后台已完成，但候选题刷新失败：${errorMessage(reason)}`); } }); return true; }
    catch (reason) { setError(errorMessage(reason)); return false; }
    finally { setBusy(false); }
  };
  const createMini = async () => {
    setBusy(true); setError(""); setRunDuration(null);
    try {
      const started: { run_id: string } = await postJson("/api/governance/generate", { profile });
      const run = await getJson<Candidate>(`/api/governance/generation-runs/${started.run_id}`);
      setRuns(previous => [run, ...previous.filter(row => row.id !== run.id)]);
      setReview([]); setFilter("attention");
    } catch (reason) { setError(errorMessage(reason)); }
    finally { setBusy(false); }
  };
  const rerunQuality = async () => {
    setBusy(true); setError("");
    try {
      await postJson(`/api/governance/generation-runs/${workRun.id}/rerun-quality?anomalies_only=true`);
      setRerunConfirm(false);
      const updated = await getJson<Candidate>(`/api/governance/generation-runs/${workRun.id}`);
      setRuns(previous => [updated, ...previous.filter(row => row.id !== updated.id)]);
    } catch (reason) { setError(errorMessage(reason)); }
    finally { setBusy(false); }
  };
  const regenerate = async () => {
    setBusy(true); setError("");
    try {
      await postJson(`/api/governance/generation-runs/${workRun.id}/regenerate-failed`);
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

  const openPoolDetail = async (row: Candidate) => {
    const ticket = ++poolTicket.current;
    setPoolDetail(row); setSelectedId(row.id);
    if (!row.raw?.generation_run_id) return;
    try { const result = await getJson<{ questions: Candidate[] }>(`/api/governance/generation-runs/${row.raw.generation_run_id}/questions`); if (ticket === poolTicket.current) setPoolDetail(result.questions.find(item => item.id === row.id) || row); }
    catch (reason) { if (ticket === poolTicket.current) setError(errorMessage(reason)); }
  };
  return <PageShell className={`page governance-page ${!workRun && tab === "run" ? "is-empty" : ""}`} header={<div className="page-title"><div><h1>Golden Dataset</h1><p>人工核对题目、答案与证据，处理修订或批准。</p></div><div className="header-actions">{tab === "run" && <>{workRun?.status === "needs_regeneration" && <button className="primary" disabled={busy} onClick={() => void regenerate()}>补齐失败题（{expectedCount - current.length}）</button>}{workRun?.status !== "needs_regeneration" && <><label className="profile-selector"><CustomSelect ariaLabel="测试集 Profile" value={profile} onChange={value => setProfile(value as typeof profile)} options={Object.entries(data.overview?.generation_profiles || {}).map(([value, counts]: [string, any]) => ({ value, label: `${value.toUpperCase()} · ${counts.expected_count}题（${counts.positive_count} / ${counts.ablation_count} / ${counts.negative_count}）` }))} /></label><button className="secondary" disabled={busy || running || qualityRunning} onClick={() => void createMini()}>生成测试集</button></>}</>}</div></div>} tabs={<div className="tabs"><button aria-pressed={tab === "run"} className={tab === "run" ? "active" : ""} onClick={() => setTab("run")}>当前测试集</button><button aria-pressed={tab === "import"} className={tab === "import" ? "active" : ""} onClick={() => setTab("import")}>候选池</button></div>} resetKey={tab}>

    {error && <p className="error-notice" role="alert">{error}</p>}
    {tab === "run" && <div className="golden-workspace">
      <div className="golden-summary-strip" role="status"><strong>{workRun?.profile?.name?.toUpperCase() || "未生成"} · {current.length} / {expectedCount} Slot</strong><span>{["positive", "ablation", "negative"].map(group => `${group === "positive" ? "正向" : group === "ablation" ? "消融" : "负向"} ${current.filter(row => row.test_category === group).length} / ${workRun?.profile?.[`${group}_count`] ?? workRun?.profile?.[group] ?? "—"}`).join(" · ")}</span><span>Ready {current.filter(row => row.probe_status === "probe_passed" && row.qc_status === "qc_passed").length} · Needs Review {attention.length}</span><Badge tone="warning">Human Gate 1 · {gate1Snapshot ? "已人工确认" : `待人工审核 ${current.filter(row => (row.review_status || "human_review_pending") === "human_review_pending").length}`}</Badge><CoverageSummary run={workRun} questions={current} documents={data.documents || []} /></div>
      <StageStepper compact ariaLabel="Golden 治理阶段" steps={[
        { label: "Coverage", state: workRun?.artifacts?.coverage_plan?.length ? "completed" : "current" },
        { label: "Generation", state: current.length === expectedCount ? "completed" : running ? "current" : "pending" },
        { label: "Hard Validation", state: current.length === expectedCount ? "completed" : "pending" },
        { label: "Probe", state: current.length === expectedCount && current.every(row => row.probe_status === "probe_passed") ? "completed" : workRun?.status === "probing" ? "current" : "pending" },
        { label: "QC", state: current.length === expectedCount && current.every(row => row.qc_status === "qc_passed") ? "completed" : workRun?.status === "qc" ? "current" : "pending" },
        { label: "Human Gate", state: gate1Snapshot ? "completed" : workRun?.human_gate?.status === "ready" ? "current" : "pending", detail: "人工审核与批准" },
      ]} />
      {workRun ? <Section title="Candidate 审核" action={<div className="header-actions"><Badge tone={attention.length ? "warning" : "good"}>{attention.length ? "Needs Review" : current.length === expectedCount ? "Ready" : "Blocked"}</Badge><button className="secondary" disabled={busy || qualityRunning || !anomalies.length || workRun.status !== "completed"} onClick={() => setRerunConfirm(true)}>批量重跑异常项</button><details className="export-menu"><summary className="secondary" aria-label="运行更多操作">⋯</summary><div><button onClick={() => setRunDetailsOpen(true)}>运行审计</button><button onClick={() => setHistoryOpen(true)}>历史 Snapshot</button>{current.length === expectedCount && (["markdown", "csv", "json"] as const).map(format => <a key={format} href={apiUrl(`/api/governance/generation-runs/${workRun.id}/export?format=${format}`)} download>导出 {format.toUpperCase()}</a>)}</div></details></div>}>
        <div className="review-filters" aria-label="Candidate 筛选">{filters.map(item => <button key={item.key} aria-pressed={filter === item.key} className={filter === item.key ? "active" : ""} onClick={() => setFilter(item.key)}>{item.label} {item.count}</button>)}        <small className="muted golden-review-role" role="status">{review.length < current.length ? "正在读取质量记录…" : filter === "attention" && !attention.length ? "无异常，展示待人工审核" : ""}</small></div>

        <QuestionTable rows={["all", "attention"].includes(filter) ? [...visible, ...failedSlots.map(slot => ({ id: `missing-${slot}`, slot, question: "生成失败，待补齐", failed: true }))].sort((a, b) => String(a.slot || "").localeCompare(String(b.slot || ""))) : visible} onDetail={row => row.failed ? (setErrorSlot(row.slot), setRunErrorOpen(true)) : setSelectedId(row.id)} />
        {current.length === expectedCount && workRun.status === "completed" && !gate1Snapshot && <div className="review-batch gate-one-action"><label><input type="checkbox" checked={confirmed} onChange={event => setConfirmed(event.target.checked)} /> 我已人工审核本次测试集的全部有效 Candidate</label><button className="primary" title={batchReason} disabled={busy || !!batchReason} onClick={() => void action(() => postJson("/api/governance/review-batch", { question_ids: currentIds, confirmed_manual_review: true }), "确认 Golden 测试集")}>确认 Golden 测试集</button></div>}
      </Section> : <Section title="Candidate 审核" action={<button className="secondary" onClick={() => setHistoryOpen(true)}>历史 Snapshot</button>}><p className="muted">尚未生成工作 Run，可生成题目或从候选池创建测试集。</p><CurrentCoveragePreview profile={profile} corpusFingerprint={data.workspace?.current_corpus_fingerprint} documents={data.documents || []} /></Section>}
    </div>}
    <ConfirmDialog open={rerunConfirm} onOpenChange={setRerunConfirm} title="批量重跑异常项" busy={busy} onConfirm={() => void rerunQuality()}><p>仅处理 {anomalies.length} 道失败或中断题目；已通过题目不会重跑。将执行所需 Probe / QC 外部调用。</p></ConfirmDialog>
    {tab === "import" && <BusinessImportPanel profiles={data.overview?.generation_profiles || {}} items={items} onCreated={reload} onDetail={row => void openPoolDetail(row)} initialProfile={profile} currentQuestionIds={currentIds} coveragePlan={workRun?.artifacts?.hard_validation?.frozen_plan} />}
    <Drawer showCloseFooter={false} open={runDetailsOpen} onOpenChange={setRunDetailsOpen} title="工作 Run 构造与质量记录"><div className="drawer-body">{workRun && <><div className="run-summary">当前阶段：{stageName[workRun.status] || displayText(workRun.status)} · Run ID：{workRun.id} · Slot {operationProgress?.processed_slots ?? 0} / {operationProgress?.expected_slots ?? expectedCount}{progress?.slot ? ` · ${progress.slot}` : ""} · Probe {operationProgress?.probe_processed ?? 0} / {expectedCount} · QC {operationProgress?.qc_processed ?? 0} / {expectedCount}{progress?.qc_skipped ? ` · QC 跳过 ${progress.qc_skipped}` : ""}{elapsed ? ` · 运行耗时 ${elapsed}` : ""}{running ? " · 状态来自数据库（Worker 未验证）" : ""}{workRun.status === "failed" && <button className="text-button" onClick={() => { setErrorSlot(null); setRunErrorOpen(true); }}>查看错误</button>}</div>
        <CurrentCoveragePreview profile={profile} corpusFingerprint={data.workspace?.current_corpus_fingerprint} documents={data.documents || []} /><div className="generation-progress" role="status">{operationProgress && <span>{operationProgress.phase_label} · 已处理 {operationProgress.phase_processed}/{operationProgress.phase_total} · {operationProgress.phase_percent}% · Round {operationProgress.refill_round}/{operationProgress.refill_max_rounds} · 剩余 {operationProgress.failed_count} 道 · Hard Valid {operationProgress.hard_valid_completed}/{operationProgress.hard_valid_total} · Probe {operationProgress.probe_processed}/{expectedCount} · QC {operationProgress.qc_processed}/{expectedCount}</span>}</div><div className="run-summary">当前 Golden：{currentGolden ? `${goldenCount} 题 · ${goldenV2 ? "V2" : "Legacy"} · Frozen` : "尚未冻结"} · {goldenCategoriesComplete ? "分类完整" : "分类需核对"}</div>{qualityRerun && <p>质量重跑：{displayText(qualityRerun.status)} · {qualityRerun.completed || 0} / {qualityRerun.total || expectedCount} · {qualityRerun.error || ""}</p>}{riskFilters.map(item => <p key={item.key}>{item.label} · {item.count}</p>)}
        {Object.entries(workRun.artifacts?.slot_audit || {}).filter(([, attempts]) => (attempts as Candidate[]).some(attempt => attempt.validation_error)).map(([slot, attempts]) => <details className="slot-audit" key={slot}><summary>{slot} · {(attempts as Candidate[]).length} 次尝试 · {(attempts as Candidate[]).at(-1)?.validation_error ? "未通过" : "重试后通过"}</summary>{(attempts as Candidate[]).map(attempt => <div key={attempt.attempt}><strong>第 {attempt.attempt} 次尝试</strong><p>问题：{attempt.question || "—"}</p><p>答案：{attempt.reference_answer || "—"}</p><p>证据：{attempt.selected_evidence?.map((item: Candidate) => `${item.document_name || item.document_id} · ${item.chunk_id} · ${item.chunk_text}`).join("；") || "—"}</p><pre>{attempt.validation_error || "通过"}</pre></div>)}</details>)}</>}</div></Drawer>
    <Drawer showCloseFooter={false} open={historyOpen} onOpenChange={setHistoryOpen} title="Golden Snapshot 历史"><div className="drawer-body snapshot-history"><Section title="已确认 Golden Snapshots"><div className="run-list">{snapshots.map(snapshot => <div key={snapshot.id}><strong><ShortId value={snapshot.id} /></strong><span>{snapshot.snapshot?.profile?.name || "Legacy"} · {snapshot.snapshot?.question_ids?.length || 0} 题 · {snapshot.created_at || "冻结时间未记录"}</span><Status value={snapshot.status} /></div>)}{!snapshots.length && <p className="muted">尚未创建正式 Golden Snapshot。</p>}</div></Section><Section title="历史 Candidate（未验证）"><details><summary>{historical.length} 道历史 Candidate</summary><p className="muted">仅供追溯，不参与当前 Golden、Baseline 或发布判断。</p><QuestionTable rows={historical.slice(historyPage * 10, historyPage * 10 + 10)} onDetail={row => setSelectedId(row.id)} /><div className="history-pagination"><button className="secondary" disabled={historyPage === 0} onClick={() => setHistoryPage(page => page - 1)}>上一页</button><span>{historyPage + 1} / {Math.max(1, Math.ceil(historical.length / 10))}</span><button className="secondary" disabled={(historyPage + 1) * 10 >= historical.length} onClick={() => setHistoryPage(page => page + 1)}>下一页</button></div></details></Section></div></Drawer>
    <Drawer showCloseFooter={false} guardEdits editDirty={candidateDirty} contentKey={candidateContentKey} open={!!selected} onOpenChange={open => { if (!open) { poolTicket.current++; setSelectedId(null); } }} title={selected ? `${selected.slot || "历史题"} · ${displayText(selected.test_category)}` : "候选题审核"} className="candidate-workspace"><CandidateWorkspace key={candidateContentKey} row={selected} peers={current} revision={revisions.find(item => item.question_ids?.includes(selected?.id))} rerunSlot={qualityRerun?.slots?.[selected?.slot]} busy={busy} readOnly={partial || !currentIds.includes(selected?.id || "")} readOnlyReason={!currentIds.includes(selected?.id || "") ? "来源候选题只读；匹配 Profile 与 Coverage Slot 后创建待审核副本。" : undefined} onRun={questionAction} onReview={reviewAction} onRefresh={reload} operation={operation} onDirtyChange={setCandidateDirty} /></Drawer>
    <Drawer showCloseFooter={false} open={runErrorOpen} onOpenChange={setRunErrorOpen} title="Run 错误详情"><div className="drawer-body"><p>阶段：{qualityRerun?.status === "failed" ? qualityRerun?.slots?.[qualityRerun?.slot]?.failed_stage || qualityRerun?.stage : stageName[workRun?.artifacts?.hard_validation?.failed_stage] || stageName[workRun?.status] || "未知"}</p>{errorSlot && (workRun?.artifacts?.slot_audit?.[errorSlot] || []).map((attempt: Candidate) => <div key={attempt.attempt}><h3>{errorSlot} · 第 {attempt.attempt} 次尝试</h3><p>问题：{attempt.question || "—"}</p><p>答案：{attempt.reference_answer || "—"}</p><p>证据：{attempt.selected_evidence?.map((item: Candidate) => `${item.document_name || item.document_id} · ${item.chunk_id} · ${item.chunk_text}`).join("；") || "—"}</p><pre>{attempt.validation_error || "通过"}</pre></div>)}{!errorSlot && <pre>{qualityRerun?.status === "failed" ? qualityRerun.error : workRun?.artifacts?.hard_validation?.error || "请查看运行详情中的 Slot Audit"}</pre>}</div></Drawer>
  </PageShell>;
}

function QuestionTable({ rows, onDetail }: { rows: Candidate[]; onDetail: (row: Candidate) => void }) {
  return <div className="table-scroll review-table"><table><thead><tr><th>#</th><th>类型</th><th>问题</th><th>Probe</th><th>QC</th><th>人工审核</th><th>操作</th></tr></thead><tbody>{rows.map(row => <tr key={row.id} tabIndex={0} onClick={() => onDetail(row)} onKeyDown={event => { if (event.key === "Enter") { event.preventDefault(); onDetail(row); } }}><td>{row.slot || row.id}</td><td><Badge tone={row.test_category === "negative" ? "warning" : "neutral"}>{row.test_category ? displayText(row.test_category) : "未记录"}</Badge><small className="question-provenance">{(row.construction_type || row.raw?.construction_type) && `${row.construction_type || row.raw?.construction_type} · `}{row.raw?.source === "business_import" ? "业务导入" : row.raw?.generation_run_id ? "AI 生成" : "历史来源"}</small></td><td><TruncatedText lines={2}>{row.question}</TruncatedText></td><td>{probeLabel(row.probe_status)}</td><td>{qcLabel(row.qc_status)}</td><td>{reviewLabel(row)}</td><td><button className="secondary" onClick={() => onDetail(row)}>{row.failed ? "查看错误" : "查看详情"}</button></td></tr>)}{!rows.length && <tr><td colSpan={7} className="empty-state">暂无对应数据。</td></tr>}</tbody></table></div>;
}
