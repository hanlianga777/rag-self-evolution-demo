import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { getJson, postJson, identityKey } from "./api";

type Operation = { id: string; runId?: string; candidateId?: string; title: string; status: "running" | "completed" | "failed"; kind?: "evaluation" | "revision"; stage?: string; stageCode?: string; current?: number; total?: number; error?: string; errorDetail?: string; provider?: string; model?: string; attempt?: number; startedAt?: number; endedAt?: number; dismissed?: boolean; restored?: boolean };
type BatchRequest = { experimentId: string; baselineId: string; round: number; candidateIds: string[]; identity?: string };
type OperationContextValue = {
  runCandidateBatch: (request: BatchRequest) => Promise<void>;
  operations: Operation[];
  start: (title: string, detail?: Partial<Operation>) => string;
  update: (id: string, detail: Partial<Operation>) => void;
  succeed: (id: string) => void;
  fail: (id: string, reason: unknown) => void;
  run: <T>(title: string, work: () => Promise<T>) => Promise<T>;
  startEvaluation: (title: string, work: () => Promise<{ id: string }>, candidateId?: string) => Promise<void>;
  watchEvaluation: (id: string, title: string) => void;
  watchRevision: (id: string) => void;
  registerCandidateRefresh: (refresh: () => Promise<void>) => void;
  unregisterCandidateRefresh: (refresh: () => Promise<void>) => void;
  registerDialogHost: (node: HTMLElement) => void;
  unregisterDialogHost: (node: HTMLElement) => void;
};

const fallback: OperationContextValue = { runCandidateBatch: async () => { throw new Error("运行实验需要共享 Operation 上下文"); }, operations: [], start: () => "", update: () => {}, succeed: () => {}, fail: () => {}, run: (_title, work) => work(), startEvaluation: async (_title, work) => { await work(); }, watchEvaluation: () => {}, watchRevision: () => {}, registerCandidateRefresh: () => {}, unregisterCandidateRefresh: () => {}, registerDialogHost: () => {}, unregisterDialogHost: () => {} };
const OperationContext = createContext<OperationContextValue>(fallback);
export function useOperation() { return useContext(OperationContext); }

function evaluation(run: any): Partial<Operation> {
  let total: number | undefined;
  try { total = JSON.parse(run.dataset_snapshot_json || "{}").question_ids?.length; } catch { /* old run has no readable snapshot */ }
  return { status: ["queued", "running"].includes(run.status) ? "running" : run.status === "completed" ? "completed" : "failed", stage: ["queued", "running"].includes(run.status) ? "正在运行 Golden Case" : run.status === "completed" ? "评测完成" : "评测失败", current: run.cases?.length, total, error: run.error_message };
}

const revisionStages: Record<string, string> = {
  queued: "等待草案", material_selected: "材料已选定", generating: "AI 单题生成", generated: "草案已生成",
  validating: "Hard Validation", hard_validation: "Hard Validation", probing: "Probe", probe: "Probe",
  qc: "QC · 正在运行质量审核", preview_ready: "草案待确认应用", completed: "待人工复审",
};

function revision(run: any): Partial<Operation> {
  const failed = run.apply_blocked || ["failed", "failed_quality", "interrupted"].includes(run.status);
  const code = failed ? run.failed_stage || run.interrupted_stage || (run.apply_blocked ? "hard_validation" : run.status === "failed_quality" ? Object.values(run.quality_results || {}).some((value: any) => value.probe === "passed" && !value.qc) ? "qc" : "probe" : run.stage) : run.stage || run.status;
  const lastAttempt = [...(run.runtime_attempts || [])].reverse().find((attempt: any) => attempt.stage === code);
  return {
    status: failed ? "failed" : ["preview_ready", "completed", "cancelled"].includes(run.status) ? "completed" : "running",
    stageCode: code, stage: revisionStages[code] || (run.status === "interrupted" ? "进程已中断，需手动继续" : code),
    current: run.progress?.current, total: run.progress?.total,
    error: run.error || (run.status === "interrupted" ? "进程重启后 Worker 不会自动恢复" : undefined),
    errorDetail: run.error_detail || run.error, provider: lastAttempt?.provider, model: lastAttempt?.model, attempt: lastAttempt?.attempt,
  };
}

export function shortError(error?: string) {
  if (!error) return "请查看运行审计";
  return /DeepSeek/i.test(error) && /timed out|请求超时/i.test(error) ? "DeepSeek 请求超时，请重试" : error.split("\n")[0].slice(0, 120);
}

export function OperationProvider({ children, restore = true }: { children: ReactNode; restore?: boolean }) {
  const [operations, setOperations] = useState<Operation[]>([]);
  const [dialogHosts, setDialogHosts] = useState<HTMLElement[]>([]);
  const [detailId, setDetailId] = useState<string | null>(null);
  const [now, setNow] = useState(Date.now());
  const timers = useRef<Set<number>>(new Set());
  const candidateRefresh = useRef<(() => Promise<void>) | null>(null);
  const activeBatches = useRef(new Set<string>());
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const syncing = useRef<Set<string>>(new Set());
  useEffect(() => () => { for (const timer of timers.current) window.clearTimeout(timer); }, []);
  useEffect(() => {
    if (!operations.some(item => item.status === "running" && !item.dismissed)) return;
    const timer = window.setInterval(() => setNow(Date.now()), 100);
    return () => window.clearInterval(timer);
  }, [operations]);
  const update = useCallback((id: string, detail: Partial<Operation>) => setOperations(current => current.map(item => item.id === id ? { ...item, ...detail } : item)), []);
  const start = useCallback((title: string, detail: Partial<Operation> = {}) => {
    const id = detail.id || `operation-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    setOperations(current => [...current.filter(item => item.id !== id), { id, title, status: "running", startedAt: detail.restored ? undefined : Date.now(), ...detail }]);
    return id;
  }, []);
  const succeed = useCallback((id: string) => {
    update(id, { status: "completed", endedAt: Date.now() });
    const timer = window.setTimeout(() => { setOperations(current => current.filter(item => item.id !== id)); timers.current.delete(timer); }, 3000);
    timers.current.add(timer);
  }, [update]);
  const fail = useCallback((id: string, reason: unknown) => update(id, { status: "failed", endedAt: Date.now(), dismissed: false, error: reason instanceof Error ? reason.message : String(reason) }), [update]);
  const run: OperationContextValue["run"] = useCallback(async (title, work) => {
    const id = start(title);
    try { const result = await work(); succeed(id); return result; }
    catch (reason) { fail(id, reason); throw reason; }
  }, [start, succeed, fail]);
  const startEvaluation: OperationContextValue["startEvaluation"] = useCallback(async (title, work, candidateId) => {
    const id = start(title, { candidateId });
    try { const started = await work(); update(id, { kind: "evaluation", runId: started.id }); }
    catch (reason) { fail(id, reason); throw reason; }
  }, [start, update, fail]);
  const runCandidateBatch: OperationContextValue["runCandidateBatch"] = useCallback(async request => {
    const id = `sandbox-round:${request.experimentId}:${request.round}`;
    if (activeBatches.current.has(id)) return;
    activeBatches.current.add(id);
    start(`第 ${request.round} 轮 A/B/C Sandbox`, { id, current: 0, total: request.candidateIds.length, stage: "核对当前实验" });
    let completed = 0, failed = 0;
    try {
      for (const candidateId of request.candidateIds) {
        if (!mounted.current) return;
        const [workspace, experiment] = await Promise.all([getJson<any>("/api/workspace"), getJson<any>(`/api/experiments/${request.experimentId}`)]);
        if (!mounted.current) return;
        if (workspace.current_baseline_id !== request.baselineId || (request.identity && identityKey(workspace) !== request.identity) || experiment.baseline_run_id !== request.baselineId) throw new Error("当前实验身份已变化，停止本轮运行");
        if (experiment.result?.report_confirmation) throw new Error("Gate 2 已确认，本轮结果不能改变");
        const candidate = experiment.candidates?.find((item: any) => item.id === candidateId);
        if (!candidate || candidate.reasoning?.round !== request.round || !["A", "B", "C"].includes(candidate.reasoning?.candidate_label)) throw new Error("候选不属于本轮 A/B/C");
        if (["evaluated", "failed"].includes(candidate.status)) { completed++; update(id, { current: completed }); continue; }
        if (candidate.status !== "generated" || experiment.candidates.some((item: any) => ["running", "queued"].includes(item.status))) throw new Error("已有实验运行中，请等待后再继续");
        const budget = experiment.evaluation_budget;
        if (!budget || budget.used >= budget.max - (budget.reserved_for_d ?? 1)) throw new Error("Sandbox 预算不足，保留 D 额度");
        const itemId = start(`Candidate ${candidate.reasoning.candidate_label} · Sandbox`, { candidateId, stage: "正在预约评测" });
        try {
          const started = await postJson<{ id: string }>(`/api/candidates/${candidateId}/run`);
          update(itemId, { runId: started.id });
          // ponytail: browser-owned serial queue; refresh requires a new explicit click for unstarted candidates.
          let result: any;
          do {
            if (!mounted.current) return;
            result = await getJson<any>(`/api/evaluations/${started.id}`);
            update(itemId, evaluation(result));
            if (["queued", "running"].includes(result.status)) await new Promise(resolve => window.setTimeout(resolve, 1000));
          } while (["queued", "running"].includes(result.status));
          if (!mounted.current) return;
          // Evaluation completion precedes Candidate qualification persistence; wait for both.
          let saved: any;
          do {
            const next = await getJson<any>(`/api/experiments/${request.experimentId}`);
            saved = next.candidates?.find((item: any) => item.id === candidateId);
            if (!saved) throw new Error("运行候选记录缺失，停止并核对审计");
            if (["running", "queued"].includes(saved.status)) await new Promise(resolve => window.setTimeout(resolve, 1000));
          } while (mounted.current && ["running", "queued"].includes(saved.status));
          if (!mounted.current) return;
          if (saved.result?.interrupted) throw new Error("服务器重启中断本项；其余未运行方案等待再次点击，不自动继续");
          if (saved.status === "evaluated" && result.status === "completed") succeed(itemId);
          else { failed++; fail(itemId, result.error_message || saved.result?.error || "评测未完整，预算已消耗"); }
        } catch (reason) { fail(itemId, reason); throw reason; }
        completed++; update(id, { current: completed, stage: `已结束 ${completed}/${request.candidateIds.length}${failed ? ` · ${failed} 项失败` : ""}` });
      }
      if (failed) throw new Error(`本轮已结束，${failed} 项运行失败；已完成结果保留，不自动重试`);
      succeed(id);
    } catch (reason) { fail(id, reason); throw reason; }
    finally { activeBatches.current.delete(id); }
  }, [start, update, succeed, fail]);
  const watchEvaluation = useCallback((id: string, title: string) => start(title, { id, kind: "evaluation" }), [start]);
  const watchRevision = useCallback((id: string) => start("局部修订", { id, kind: "revision" }), [start]);
  const registerCandidateRefresh = useCallback((refresh: () => Promise<void>) => { candidateRefresh.current = refresh; }, []);
  const unregisterCandidateRefresh = useCallback((refresh: () => Promise<void>) => { if (candidateRefresh.current === refresh) candidateRefresh.current = null; }, []);
  const registerDialogHost = useCallback((node: HTMLElement) => setDialogHosts(current => [...current.filter(item => item !== node), node]), []);
  const unregisterDialogHost = useCallback((node: HTMLElement) => setDialogHosts(current => current.filter(item => item !== node)), []);

  useEffect(() => {
    if (!restore) return;
    let cancelled = false;
    getJson<any[]>("/api/evaluations").then(evaluations => {
      if (cancelled) return;
      for (const item of evaluations.filter(item => item.status === "running")) start(item.config?.candidate_id ? `Candidate ${item.config.candidate_id} Sandbox` : "Baseline Evaluation", { id: item.id, runId: item.id, candidateId: item.config?.candidate_id, kind: "evaluation", restored: true, startedAt: item.created_at ? Date.parse(item.created_at) : undefined });
    }).catch(() => {});
    getJson<any[]>("/api/governance/revisions").then(revisions => {
      if (cancelled) return;
      for (const item of revisions.filter(item => ["queued", "generating", "validating", "probing", "qc"].includes(item.status))) start("局部修订", { id: item.id, kind: "revision", restored: true, startedAt: item.created_at ? Date.parse(item.created_at) : undefined });
    }).catch(() => {});
    return () => { cancelled = true; };
  }, [restore, start]);

  useEffect(() => {
    const active = operations.filter(item => item.status === "running" && item.kind);
    if (!active.length) return;
    const timer = window.setInterval(() => {
      for (const item of active) {
        if (syncing.current.has(item.id)) continue;
        syncing.current.add(item.id);
        void getJson<any>(item.kind === "revision" ? `/api/governance/revisions/${item.id}` : `/api/evaluations/${item.runId || item.id}`).then(async result => {
          const next: Partial<Operation> = item.kind === "revision" ? revision(result) : evaluation(result);
          if (item.kind === "revision" && next.status === "completed" && candidateRefresh.current) {
            update(item.id, { ...next, status: "running", stage: "正在同步 Candidate 状态" });
            try { await candidateRefresh.current(); }
            catch (reason) { throw new Error(`后台已完成，但候选题刷新失败：${reason instanceof Error ? reason.message : String(reason)}`); }
          }
          update(item.id, next);
          if (next.status === "completed") succeed(item.id);
          if (next.status === "failed") fail(item.id, next.error || "评测失败");
        }).catch(reason => fail(item.id, reason)).finally(() => syncing.current.delete(item.id));
      }
    }, 1000);
    return () => window.clearInterval(timer);
  }, [operations, update, succeed, fail]);

  const visible = operations.filter(item => !item.dismissed).slice(-3);
  const console = !!visible.length && <div className="operation-stack" aria-label="运行状态">{visible.map(item => <section className="operation-console" key={item.id} role={item.status === "failed" ? "alert" : "status"}>
      <div className="operation-head"><strong>{item.title}</strong><button aria-label="关闭运行状态" onClick={() => setOperations(current => current.map(row => row.id === item.id && row.status === "running" ? { ...row, dismissed: true } : row).filter(row => row.id !== item.id || row.status === "running"))}>×</button></div>
      <p>{item.status === "failed" ? "运行失败" : item.status === "completed" ? "✓ 完成" : item.restored ? `数据库记录：${item.stage || "运行中"}（Worker 未确认）` : item.stage || "运行中"}{item.startedAt != null && <span> · {Math.max(0, ((item.endedAt ?? now) - item.startedAt) / 1000).toFixed(1)}s</span>}</p>
      {item.current != null && item.total != null && item.total > 1 && <><div className="operation-count">{item.current} / {item.total}<span>{Math.round(item.current / item.total * 100)}%</span></div><progress value={item.current} max={item.total} /></>}
      {item.status === "failed" && <><small className="operation-error-summary">{shortError(item.error)}</small><button className="operation-detail-button" aria-label="查看错误详情" aria-expanded={detailId === item.id} aria-controls={`operation-detail-${item.id}`} onClick={() => setDetailId(current => current === item.id ? null : item.id)}>查看错误详情</button>{detailId === item.id && <div id={`operation-detail-${item.id}`} className="operation-details"><div>阶段：{item.stage || "未记录"}</div><div>耗时：{item.startedAt != null ? `${Math.max(0, ((item.endedAt ?? now) - item.startedAt) / 1000).toFixed(1)}s` : "未记录"}</div><div>错误：{item.errorDetail || item.error || "未记录"}</div><div>Operation ID：{item.id}</div>{item.provider && <div>Provider：{item.provider}</div>}{item.model && <div>Model：{item.model}</div>}{item.attempt != null && <div>Attempt：{item.attempt}</div>}</div>}</>}
    </section>)}</div>;
  return <OperationContext.Provider value={{ operations, runCandidateBatch, start, update, succeed, fail, run, startEvaluation, watchEvaluation, watchRevision, registerCandidateRefresh, unregisterCandidateRefresh, registerDialogHost, unregisterDialogHost }}>
    {children}
    {dialogHosts.length ? createPortal(console, dialogHosts[dialogHosts.length - 1]) : console}
  </OperationContext.Provider>;
}
