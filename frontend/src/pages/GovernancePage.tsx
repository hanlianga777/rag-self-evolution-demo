import { useEffect, useMemo, useState } from "react";
import { apiUrl, errorMessage, getJson, postJson } from "../api";
import { Badge, Section, Status } from "../components/Primitives";
import { Drawer } from "../components/Dialog";
import { displayText } from "../display";
import { useOperation } from "../operation";
import { CandidateWorkspace } from "./CandidateWorkspace";

type Candidate = Record<string, any>;
type Filter = "all" | "positive" | "ablation" | "negative" | "probe" | "qc" | "pending" | "approved" | "revision";

const stageName: Record<string, string> = { queued: "排队中", coverage: "规划覆盖", generating: "逐题生成与修复", validation: "硬校验", candidate_persistence: "候选题入库", probing: "检索验证", qc: "质量检查", completed: "已完成", failed: "运行失败", candidate_generated: "候选题已生成" };
const probeLabel = (value?: string) => value === "probe_passed" ? "通过" : value === "needs_revision" ? "未通过" : "未运行";
const qcLabel = (value?: string) => value === "qc_passed" ? "通过" : value === "qc_failed" ? "未通过" : "未运行";
const reviewLabel = (row: Candidate) => displayText(row.review_status || "human_review_pending");

export function GovernancePage({ data }: { data: any }) {
  const operation = useOperation();
  const [tab, setTab] = useState<"run" | "snapshot" | "legacy">("run");
  const [items, setItems] = useState<Candidate[]>(data.dataset || []);
  const [runs, setRuns] = useState<Candidate[]>(data.generationRuns || []);
  const [snapshots, setSnapshots] = useState<Candidate[]>(data.snapshots || []);
  const [review, setReview] = useState<Candidate[]>([]);
  const [revisions, setRevisions] = useState<Candidate[]>([]);
  const [filter, setFilter] = useState<Filter>("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [runErrorOpen, setRunErrorOpen] = useState(false);
  const [now, setNow] = useState(Date.now());
  const [runDuration, setRunDuration] = useState<{ id: string; ms: number } | null>(null);
  const currentRun = runs[0];
  const expectedCount = currentRun?.profile?.expected_count || ["positive", "ablation", "negative"].reduce((total, category) => total + (currentRun?.profile?.[category] || 0), 0) || 20;
  const currentIds: string[] = currentRun?.question_ids || [];
  const current = currentIds.map(id => review.find(row => row.id === id) || items.find(row => row.id === id)).filter(Boolean) as Candidate[];
  const legacy = items.filter(row => row.legacy_question_type !== "v1_mini");
  const selected = current.find(row => row.id === selectedId) || legacy.find(row => row.id === selectedId);
  const running = ["queued", "coverage", "generating", "validation", "probing", "qc"].includes(currentRun?.status);
  const qualityRerun = currentRun?.artifacts?.hard_validation?.quality_rerun;
  const qualityRunning = qualityRerun?.status === "running";
  const progress = currentRun?.artifacts?.hard_validation?.progress;
  const runStartedAt = currentRun?.created_at ? Date.parse(currentRun.created_at) : NaN;
  const elapsed = Number.isFinite(runStartedAt) && (running || runDuration?.id === currentRun?.id) ? `${(Math.max(0, (runDuration?.id === currentRun?.id ? runDuration?.ms : now - runStartedAt) ?? 0) / 1000).toFixed(1)}s` : null;
  useEffect(() => { if (!running && !qualityRunning) return; const timer = window.setInterval(() => setNow(Date.now()), 100); return () => window.clearInterval(timer); }, [running, qualityRunning]);

  const loadReview = async (run: Candidate | undefined) => {
    const count = run?.profile?.expected_count || ["positive", "ablation", "negative"].reduce((total, category) => total + (run?.profile?.[category] || 0), 0);
    if (run && count && run.question_ids?.length === count) {
      const result = await getJson<{ questions: Candidate[] }>(`/api/governance/generation-runs/${run.id}/export?format=json`);
      setReview(result.questions);
    } else setReview([]);
  };
  const reload = async () => {
    const [questions, generationRuns, goldenSnapshots, revisionRuns] = await Promise.all([
      getJson<Candidate[]>("/api/dataset"), getJson<Candidate[]>("/api/governance/generation-runs"), getJson<Candidate[]>("/api/governance/snapshots"), getJson<Candidate[]>("/api/governance/revisions"),
    ]);
    setItems(questions); setRuns(generationRuns); setSnapshots(goldenSnapshots); setRevisions(Array.isArray(revisionRuns) ? revisionRuns : []);
    await loadReview(generationRuns[0]);
  };
  useEffect(() => {
    if (!data.generationRuns) void reload().catch(reason => setError(errorMessage(reason)));
    else { void loadReview(data.generationRuns[0]).catch(reason => setError(errorMessage(reason))); if (data.generationRuns[0]?.question_ids?.length === (data.generationRuns[0]?.profile?.expected_count || 20)) void getJson<Candidate[]>("/api/governance/revisions").then(value => setRevisions(Array.isArray(value) ? value : [])).catch(() => {}); }
  }, [data.generationRuns]);
  useEffect(() => {
    if ((!running && !qualityRunning) || !currentRun?.id) return;
    let cancelled = false;
    const poll = async () => {
      try {
        const updated = await getJson<Candidate>(`/api/governance/generation-runs/${currentRun.id}`);
        if (cancelled) return;
        setRuns(previous => [updated, ...previous.filter(row => row.id !== updated.id)]);
        if (updated.question_ids?.length === (updated.profile?.expected_count || expectedCount)) void loadReview(updated).catch(reason => setError(errorMessage(reason)));
        if (["completed", "failed"].includes(updated.status) && updated.created_at) setRunDuration({ id: updated.id, ms: Date.now() - Date.parse(updated.created_at) });
        if (["completed", "failed"].includes(updated.status) && (running || updated.artifacts?.hard_validation?.quality_rerun?.status !== "running")) void reload().catch(reason => setError(errorMessage(reason)));
      } catch (reason) { if (!cancelled) setError(errorMessage(reason)); }
    };
    void poll();
    const timer = window.setInterval(() => void poll(), 1000);
    return () => { cancelled = true; window.clearInterval(timer); };
  }, [currentRun?.id, currentRun?.status, qualityRunning]);

  const filters = useMemo(() => [
    { key: "all", label: "全部", count: current.length, match: (_row: Candidate) => true },
    { key: "positive", label: "正向", count: current.filter(row => row.test_category === "positive").length, match: (row: Candidate) => row.test_category === "positive" },
    { key: "ablation", label: "鲁棒性", count: current.filter(row => row.test_category === "ablation").length, match: (row: Candidate) => row.test_category === "ablation" },
    { key: "negative", label: "负向", count: current.filter(row => row.test_category === "negative").length, match: (row: Candidate) => row.test_category === "negative" },
    { key: "probe", label: "Probe 未通过", count: current.filter(row => row.probe_status === "needs_revision").length, match: (row: Candidate) => row.probe_status === "needs_revision" },
    { key: "qc", label: "QC 未通过", count: current.filter(row => row.qc_status === "qc_failed").length, match: (row: Candidate) => row.qc_status === "qc_failed" },
    { key: "pending", label: "待人工审核", count: current.filter(row => row.review_status === "human_review_pending").length, match: (row: Candidate) => row.review_status === "human_review_pending" },
    { key: "approved", label: "已批准", count: current.filter(row => row.stage === "golden").length, match: (row: Candidate) => row.stage === "golden" },
    { key: "revision", label: "需修订 / 已拒绝", count: current.filter(row => ["needs_revision", "rejected"].includes(row.review_status)).length, match: (row: Candidate) => ["needs_revision", "rejected"].includes(row.review_status) },
  ] as const, [current]);
  const visible = current.filter(filters.find(item => item.key === filter)?.match || (() => true));
  const gateBlocked = current.filter(row => row.stage !== "golden" && (row.probe_status !== "probe_passed" || row.qc_status !== "qc_passed"));
  const manualBlocked = current.filter(row => row.stage !== "golden" && row.review_history?.some((event: Candidate) => ["needs_revision", "rejected"].includes(event.decision)));
  const probeFailed = current.filter(row => row.probe_status === "needs_revision").length;
  const qcFailed = current.filter(row => row.qc_status === "qc_failed").length;
  const probePending = current.filter(row => !["probe_passed", "needs_revision"].includes(row.probe_status)).length;
  const qcPending = current.filter(row => !["qc_passed", "qc_failed"].includes(row.qc_status)).length;
  const batchReason = current.length !== expectedCount ? `本轮尚未完整入库 ${expectedCount} 道题` : gateBlocked.length || manualBlocked.length ? `仍有 ${new Set([...gateBlocked, ...manualBlocked].map(row => row.id)).size} 道阻塞题（Probe 未通过 ${probeFailed}，QC 未通过 ${qcFailed}${probePending ? `，待 Probe ${probePending}` : ""}${qcPending ? `，待 QC ${qcPending}` : ""}${manualBlocked.length ? `，人工需修订 / 已拒绝 ${manualBlocked.length}` : ""}）` : current.every(row => row.stage === "golden") ? "本轮全部题目已批准" : !confirmed ? "请先确认已人工审核全部有效 Candidate" : "";
  const action = async (work: () => Promise<unknown>, title: string) => {
    setBusy(true); setError("");
    try { await operation.run(title, work); return true; } catch (reason) { setError(errorMessage(reason)); return false; }
    finally { await reload().catch(() => {}); setBusy(false); }
  };
  const createMini = async () => {
    setBusy(true); setError(""); setRunDuration(null);
    try {
      const started: { run_id: string } = await postJson("/api/governance/generate-mini");
      const run = await getJson<Candidate>(`/api/governance/generation-runs/${started.run_id}`);
      setRuns(previous => [run, ...previous.filter(row => row.id !== run.id)]);
      setReview([]); setFilter("all");
    } catch (reason) { setError(errorMessage(reason)); }
    finally { setBusy(false); }
  };
  const rerunQuality = async () => {
    setBusy(true); setError("");
    try {
      await postJson(`/api/governance/generation-runs/${currentRun.id}/rerun-quality`);
      const updated = await getJson<Candidate>(`/api/governance/generation-runs/${currentRun.id}`);
      setRuns(previous => [updated, ...previous.filter(row => row.id !== updated.id)]);
    } catch (reason) { setError(errorMessage(reason)); }
    finally { setBusy(false); }
  };
  const questionAction = (id: string, name: "probe" | "qc") => action(() => postJson(`/api/governance/questions/${id}/${name}`), name === "probe" ? "运行单题 Probe" : "运行单题 QC");
  const reviewAction = (id: string, decision: string, reason?: string, tags?: string[]) => action(() => postJson(`/api/governance/questions/${id}/review`, { decision, reason, tags }), "人工审核 Candidate");

  return <div className={`page governance-page ${!currentRun && tab === "run" ? "is-empty" : ""}`}>
    <div className="page-title"><div><h1>测试集治理</h1><p>Coverage → Hard Validation → Probe ≥90 → QC ≥85 → Human Review → Snapshot</p></div><button className="secondary" disabled={busy || running || qualityRunning} onClick={() => void createMini()}>{currentRun?.status === "failed" ? "重新运行 V1 Mini 8 / 4 / 8" : "生成 V1 Mini 8 / 4 / 8"}</button></div>
    {error && <p className="error-notice" role="alert">{error}</p>}
    <div className="tabs"><button aria-pressed={tab === "run"} className={tab === "run" ? "active" : ""} onClick={() => setTab("run")}>当前 V1 Run</button><button aria-pressed={tab === "snapshot"} className={tab === "snapshot" ? "active" : ""} onClick={() => setTab("snapshot")}>Golden Snapshot</button><button aria-pressed={tab === "legacy"} className={tab === "legacy" ? "active" : ""} onClick={() => setTab("legacy")}>Legacy</button></div>
    {tab === "run" && <Section title="当前 V1 Generation Run" action={<div className="header-actions">{currentRun && <Badge tone="accent">{currentRun.id}</Badge>}{current.length === expectedCount && currentRun?.status === "completed" && <button className="secondary" disabled={busy || qualityRunning} onClick={() => void rerunQuality()}>重新运行 Probe / QC</button>}{current.length === expectedCount && <details className="export-menu"><summary className="secondary">导出测试集 ▾</summary><div>{(["markdown", "csv", "json"] as const).map(format => <a key={format} href={apiUrl(`/api/governance/generation-runs/${currentRun.id}/export?format=${format}`)} download>导出 {format === "markdown" ? "Markdown" : format.toUpperCase()}</a>)}</div></details>}</div>}>
      {currentRun ? <>
        {current.length === expectedCount && current.every(row => row.stage === "golden") && <div className="snapshot-next"><span>✓ V1 Mini 已全部完成人工审核</span><button className="primary" disabled={busy} onClick={() => void action(() => postJson(`/api/governance/generation-runs/${currentRun.id}/snapshot`), "创建 Golden Snapshot")}>创建 Golden Snapshot</button></div>}
        <div className="run-summary"><span role="status">{qualityRerun ? "首次生成：" : ""}{stageName[currentRun.status] || displayText(currentRun.status)} · {current.length} 题 · Slot {progress?.completed_slots || 0} / {progress?.total_slots || expectedCount}{progress?.slot ? ` · ${progress.slot}` : ""} · Probe {progress?.probe_completed || 0} / {expectedCount} · QC {progress?.qc_completed || 0} / {expectedCount}{progress?.qc_skipped ? ` · QC 跳过 ${progress.qc_skipped}` : ""}{elapsed ? ` · 运行耗时 ${elapsed}` : ""}{running ? " · 状态来自数据库（Worker 未验证）" : ""}</span>{currentRun.status === "failed" && <button className="text-button" onClick={() => setRunErrorOpen(true)}>查看错误</button>}</div>
        {qualityRerun && <div className="run-summary" role="status"><span>Probe / QC 重跑：{qualityRerun.status === "running" ? "运行中" : qualityRerun.status === "completed" ? "已完成" : "运行失败"} · {qualityRerun.stage === "qc" ? "质量检查" : qualityRerun.stage === "probe" ? "检索验证" : "—"} {qualityRerun.slot || ""} · {qualityRerun.completed || 0} / {expectedCount} · Probe 通过 {qualityRerun.probe_passed || 0}，失败 {qualityRerun.probe_failed || 0} · QC 通过 {qualityRerun.qc_passed || 0}，失败 {qualityRerun.qc_failed || 0}，跳过 {qualityRerun.qc_skipped || 0}{qualityRunning && qualityRerun.started_at ? ` · 运行耗时 ${((now - Date.parse(qualityRerun.started_at)) / 1000).toFixed(1)}s` : ""}{qualityRunning ? " · 状态来自数据库（Worker 未验证）" : ""}</span>{qualityRerun.status === "failed" && <button className="text-button" onClick={() => setRunErrorOpen(true)}>查看错误</button>}</div>}
        <div className="review-filters" aria-label="Candidate 筛选">{filters.map(item => <button key={item.key} aria-pressed={filter === item.key} className={filter === item.key ? "active" : ""} onClick={() => setFilter(item.key)}>{item.label} {item.count}</button>)}</div>
        <QuestionTable rows={visible} onDetail={row => setSelectedId(row.id)} />
        {current.length === expectedCount && <div className="review-batch"><label><input type="checkbox" checked={confirmed} onChange={event => setConfirmed(event.target.checked)} /> 我已人工审核本次 V1 Mini 的全部有效 Candidate</label><button className="primary" disabled={busy || !!batchReason} onClick={() => void action(() => postJson("/api/governance/review-batch", { question_ids: currentIds, confirmed_manual_review: true }), "批量批准 Golden")}>批量批准 Golden</button>{batchReason && <span className="muted">{batchReason}</span>}</div>}
      </> : <p className="muted">尚未生成当前 V1 Mini。历史题不会计入本轮统计。</p>}
    </Section>}
    {tab === "snapshot" && <Section title="Approved Golden Snapshot"><div className="run-list">{snapshots.map(snapshot => <div key={snapshot.id}><strong>{snapshot.id}</strong><span>{snapshot.snapshot?.generation_run_id || "历史快照"} · {snapshot.snapshot?.question_ids?.length || 0} 题</span><Status value={snapshot.status} /></div>)}{!snapshots.length && <p className="muted">尚未创建正式 Golden Snapshot。</p>}</div></Section>}
    {tab === "legacy" && <Section title="历史 Candidate（Legacy / 未验证）"><details><summary>展开 {legacy.length} 道历史 Candidate</summary><p className="muted">仅供追溯，不参与本轮统计、正式 Baseline 或发布判断。</p><QuestionTable rows={legacy} onDetail={row => setSelectedId(row.id)} /></details></Section>}
    <Drawer open={!!selected} onOpenChange={open => !open && setSelectedId(null)} title={selected ? `${selected.slot || "历史题"} · ${displayText(selected.test_category)}` : "候选题审核"} className="candidate-workspace"><CandidateWorkspace key={selected?.id} row={selected} peers={current} revision={revisions.find(item => item.question_ids?.includes(selected?.id))} rerunSlot={qualityRerun?.slots?.[selected?.slot]} busy={busy} onRun={questionAction} onReview={reviewAction} onRefresh={reload} operation={operation} /></Drawer>
    <Drawer open={runErrorOpen} onOpenChange={setRunErrorOpen} title="Run 错误详情"><div className="drawer-body"><p>阶段：{qualityRerun?.status === "failed" ? qualityRerun?.slots?.[qualityRerun?.slot]?.failed_stage || qualityRerun?.stage : stageName[currentRun?.artifacts?.hard_validation?.failed_stage] || "未知"}</p><pre>{qualityRerun?.status === "failed" ? qualityRerun.error : currentRun?.artifacts?.hard_validation?.error || "请查看运行审计"}</pre></div></Drawer>
  </div>;
}

function QuestionTable({ rows, onDetail }: { rows: Candidate[]; onDetail: (row: Candidate) => void }) {
  return <div className="table-scroll review-table"><table><thead><tr><th>#</th><th>类型</th><th>问题</th><th>Probe</th><th>QC</th><th>人工审核</th><th>操作</th></tr></thead><tbody>{rows.map(row => <tr key={row.id}><td>{row.slot || row.id}</td><td><Badge tone={row.test_category === "negative" ? "warning" : "neutral"}>{displayText(row.test_category)}</Badge></td><td><span className="review-question">{row.question}</span></td><td>{probeLabel(row.probe_status)}</td><td>{qcLabel(row.qc_status)}</td><td>{reviewLabel(row)}</td><td><button className="secondary" onClick={() => onDetail(row)}>查看详情</button></td></tr>)}{!rows.length && <tr><td colSpan={7} className="empty-state">暂无对应数据。</td></tr>}</tbody></table></div>;
}
