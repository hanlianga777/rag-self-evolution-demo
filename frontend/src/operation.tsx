import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { getJson, postJson, identityKey, invalidateReads } from "./api";
import type { PricePause } from "./components/RuntimeSettings";

import { RunProgressPanel } from "./ui/RunProgressPanel";

type Operation = { id: string; runId?: string; candidateId?: string; experimentId?: string; pricePause?: PricePause; title: string; status: "running" | "completed" | "failed" | "stopped"; stopping?: boolean; stopError?: string; kind?: "evaluation" | "revision" | "cycle"; stage?: string; stageCode?: string; current?: number; total?: number; error?: string; errorDetail?: string; provider?: string; model?: string; attempt?: number; startedAt?: number; endedAt?: number; dismissed?: boolean; restored?: boolean };
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
  let total: number | undefined = run.result?.total;
  const current = run.result?.completed ?? run.cases?.length;
  try { total ??= JSON.parse(run.dataset_snapshot_json || "{}").question_ids?.length; } catch { /* old run has no readable snapshot */ }
  if (run.result?.stop_request) {
    const active = ["queued", "running"].includes(run.status);
    return { status: active ? "running" : "stopped", stopping: active, stage: active ? "正在停止，等待当前请求结束并保存断点" : "已停止，断点已保存", current, total, ...(!active ? { endedAt: Date.now() } : {}) };
  }
  return { status: ["queued", "running"].includes(run.status) ? "running" : run.status === "completed" ? "completed" : "failed", stage: ["queued", "running"].includes(run.status) ? "正在运行 Golden Case" : run.status === "completed" ? "评测完成" : "评测失败", current, total, pricePause: run.result?.price_pause, error: run.error_message };
}

function cycleProgress(saved: any): Partial<Operation> {
  const cycle = saved.result.optimization_cycle, budget = saved.evaluation_budget;
  const stopped = ["stopped", "analysis_exhausted"].includes(cycle.status);
  return { status: cycle.status === "running" ? "running" : cycle.status === "failed" ? "failed" : stopped ? "stopped" : "completed",
    stopping: cycle.status === "running" && !!cycle.stop_request, error: cycle.last_error,
    current: budget?.used ?? cycle.used, total: budget?.max ?? 12,
    pricePause: [cycle.price_pause, saved.result.price_pause].find(pause => pause?.paused) || cycle.price_pause,
    stage: cycle.stop_request ? "正在停止，等待当前请求结束并保存断点" : `已用 ${budget?.used ?? cycle.used} 次，剩余 ${cycle.remaining} 次（含合并方案预留）` };
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
    pricePause: run.price_pause,
    error: run.error || (run.status === "interrupted" ? "进程重启后 Worker 不会自动恢复" : undefined),
    errorDetail: run.error_detail || run.error, provider: lastAttempt?.provider, model: lastAttempt?.model, attempt: lastAttempt?.attempt,
  };
}

export function elapsedText(milliseconds: number) {
  const seconds = Math.max(0, Math.floor(milliseconds / 1000));
  return `${Math.floor(seconds / 60)} 分 ${seconds % 60} 秒`;
}

export function evaluationTitle(run: any) {
  if (!run.config?.candidate_id) return run.config?.run_target === "answer_replay" || run.result?.judge_replay ? "历史回答判分回放" : "Baseline 评测";
  const label = run.config.candidate_label || String(run.config.candidate_id).match(/[-_]([ABCD])$/)?.[1];
  return `${/^[ABCD]$/.test(label || "") ? `Candidate ${label}` : "Candidate"} · Sandbox 试跑`;
}

export function operationTitle(title: string) {
  const candidate = title.match(/(?:Round \d+ · )?Candidate [ABCD](?![A-Z])/);
  if (candidate) return candidate[0];
  if (/Round \d+.*A\/B\/C/.test(title)) return title.match(/Round \d+/)![0] + " · A/B/C";
  if (/Baseline/.test(title)) return "Baseline";
  return title.replace(/(?:EVAL|EXP|CAND|REV)-[\w-]+/g, "").trim() || "运行任务";
}

export function shortError(error?: string) {
  if (!error) return "请查看运行审计";
  return /DeepSeek/i.test(error) && /timed out|请求超时/i.test(error) ? "DeepSeek 请求超时，请重试" : error.split("\n")[0].slice(0, 120);
}

function runErrorText(error?: string) {
  if (!error) return "运行遇到问题，请稍后重试";
  const summary = shortError(error);
  return /[\u4e00-\u9fff]/.test(summary) ? summary.replace(/(?:EVAL|EXP|CAND|REV)-[\w-]+/g, "相关任务") : "运行遇到问题，请稍后重试";
}

export function OperationProvider({ children, restore = true }: { children: ReactNode; restore?: boolean }) {
  const [operations, setOperations] = useState<Operation[]>([]);
  const [dialogHosts, setDialogHosts] = useState<HTMLElement[]>([]);
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
    start(`Round ${request.round} A/B/C · Sandbox 试跑`, { id, experimentId: request.experimentId, current: 0, total: request.candidateIds.length, stage: "核对当前实验" });
    try {
      const [workspace, experiment] = await Promise.all([getJson<any>("/api/workspace"), getJson<any>(`/api/experiments/${request.experimentId}`)]);
      if (workspace.current_baseline_id !== request.baselineId || (request.identity && identityKey(workspace) !== request.identity) || experiment.baseline_run_id !== request.baselineId) throw new Error("当前实验身份已变化，请刷新");
      if (experiment.result?.report_confirmation) throw new Error("报告已确认，本轮结果不能改变");
      if (experiment.result?.optimization_cycle?.status !== "running") await postJson(`/api/experiments/${request.experimentId}/run-cycle`, {});
      while (mounted.current) {
        const saved = await getJson<any>(`/api/experiments/${request.experimentId}?light=true`);
        const cycle = saved.result?.optimization_cycle;
        if (!cycle) throw new Error("记录缺失：优化批次状态");
        update(id, cycleProgress(saved));
        if (candidateRefresh.current) await candidateRefresh.current();
        if (cycle.status !== "running") {
          if (cycle.status === "failed") throw new Error(cycle.last_error || "本批次已停止");
          if (cycle.status === "analysis_exhausted") { update(id,{status:"stopped",stage:cycle.last_error || "连续 3 次方案不合规，已停止",endedAt:Date.now()}); break; }
          if (cycle.status === "stopped") { update(id,{status:"stopped",endedAt:Date.now()}); break; }
          succeed(id); break;
        }
        await new Promise(resolve => window.setTimeout(resolve, 1000));
      }
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
    void Promise.resolve().then(()=>{
    if(cancelled)return;
    getJson<any[]>("/api/evaluations?active_only=true").then(evaluations => {
      if (cancelled) return;
      for (const item of evaluations.filter(item => ["running", "queued"].includes(item.status))) start(evaluationTitle(item), { id: item.id, runId: item.id, candidateId: item.config?.candidate_id, kind: "evaluation", pricePause: item.result?.price_pause, restored: true, startedAt: item.created_at ? Date.parse(item.created_at) : undefined });
    }).catch(() => {});
    getJson<any[]>("/api/governance/revisions?active_only=true&light=true").then(revisions => {
      if (cancelled) return;
      for (const item of revisions.filter(item => ["queued", "generating", "validating", "probing", "qc"].includes(item.status))) start("局部修订", { id: item.id, kind: "revision", restored: true, startedAt: item.created_at ? Date.parse(item.created_at) : undefined });
    }).catch(() => {});
    getJson<any>("/api/optimization?light=true").then(saved => {
      if (cancelled || saved.result?.optimization_cycle?.status !== "running") return;
      start("A/B/C · Sandbox 自动循环", { id: `cycle:${saved.id}`, experimentId: saved.id, kind: "cycle", restored: true, ...cycleProgress(saved) });
    }).catch(() => {});
    });
    return () => { cancelled = true; };
  }, [restore, start]);

  useEffect(() => {
    const active = operations.filter(item => item.status === "running" && item.kind);
    if (!active.length) return;
    const timer = window.setInterval(() => {
      for (const item of active) {
        if (syncing.current.has(item.id) || continuingRuns.current.has(item.id)) continue;
        syncing.current.add(item.id);
        void getJson<any>(item.kind === "cycle" ? `/api/experiments/${item.experimentId}?light=true` : item.kind === "revision" ? `/api/governance/revisions/${item.id}?light=true` : `/api/evaluations/${item.runId || item.id}?light=true`).then(async result => {
          const next: Partial<Operation> = item.kind === "cycle" ? cycleProgress(result) : item.kind === "revision" ? revision(result) : evaluation(result);
          if (item.kind === "revision" && next.status === "completed" && candidateRefresh.current) {
            invalidateReads();
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

  const stoppingRuns = useRef(new Set<string>());
  const stopEvaluation = async (item: Operation) => {
    if (stoppingRuns.current.has(item.id)) return;
    stoppingRuns.current.add(item.id);
    update(item.id, { stopping: true, stopError: undefined });
    try {
      const result = await postJson<any>(item.experimentId ? `/api/experiments/${item.experimentId}/stop-cycle` : `/api/evaluations/${item.runId || item.id}/stop`, {});
      update(item.id, item.experimentId ? cycleProgress({result:{optimization_cycle:result}}) : evaluation(result));
    } catch (reason) {
      update(item.id, { stopping: false, stopError: `停止请求失败：${reason instanceof Error ? reason.message : String(reason)}` });
    } finally { stoppingRuns.current.delete(item.id); }
  };

  const continuingRuns = useRef(new Set<string>());
  const continueOperation = async (item: Operation) => {
    if ((item.status === "running" && item.pricePause?.paused) || continuingRuns.current.has(item.id)) return;
    continuingRuns.current.add(item.id);
    update(item.id, { status: "running", stopping: false, stopError: undefined });
    try {
      if (item.experimentId) {
        await postJson(`/api/experiments/${item.experimentId}/run-cycle`, {});
        update(item.id, { kind: "cycle" });
      } else if (item.candidateId) {
        const started = await postJson<{ id: string }>(`/api/candidates/${item.candidateId}/run`, { authorize_provider: true });
        update(item.id, { kind: "evaluation", runId: started.id });
      } else if (item.kind === "revision") {
        await postJson(`/api/governance/revisions/${item.id}/resume`);
      } else {
        const source = item.runId || item.id;
        const preflight = await getJson<any>(`/api/evaluation/preflight?resume_source_id=${encodeURIComponent(source)}`);
        if (!preflight.can_start || !preflight.can_resume || preflight.resume_source_id !== source) throw new Error(preflight.reason || preflight.resume_reason || "当前断点不能继续，请回到 Baseline 查看预检");
        const started = await postJson<{ id: string }>("/api/evaluations/run", { resume_source_id: source });
        update(item.id, { kind: "evaluation", runId: started.id });
      }
      update(item.id, { error: undefined, endedAt: undefined });
    } catch (reason) { fail(item.id, reason); }
    finally { continuingRuns.current.delete(item.id); }
  };

  const visible = operations.filter(item => !item.dismissed).slice(-3);
  const console = !!visible.length && <div className="operation-stack" aria-label="运行状态">{visible.map(item => <div key={item.id} className="operation-panel">
    <RunProgressPanel
      title={operationTitle(item.title)}
      subtitle={item.status === "running" && !item.pricePause?.paused ? item.stage || (item.kind === "revision" ? "局部修订" : item.experimentId ? "Sandbox 批次" : "评测") : item.kind === "revision" ? "局部修订" : item.candidateId || item.experimentId ? "Sandbox 评测" : "Baseline"}
      status={item.status === "running" && item.pricePause?.paused ? "waiting" : item.status}
      current={item.current} total={item.total}
      elapsedMs={item.startedAt != null ? (item.endedAt ?? now) - item.startedAt : undefined}
      errorText={runErrorText(item.error)}
      onContinue={item.experimentId || item.candidateId || item.kind === "revision" || item.kind === "evaluation" ? () => void continueOperation(item) : undefined}
      onStop={item.experimentId || item.kind === "evaluation" || item.runId ? () => void stopEvaluation(item) : undefined}
      stopping={item.stopping}
    />
    {item.stopError && <small role="alert" className="operation-error-summary">{runErrorText(item.stopError)}</small>}
  </div>)}</div>;
  return <OperationContext.Provider value={{ operations, runCandidateBatch, start, update, succeed, fail, run, startEvaluation, watchEvaluation, watchRevision, registerCandidateRefresh, unregisterCandidateRefresh, registerDialogHost, unregisterDialogHost }}>
    {children}
    {dialogHosts.length ? createPortal(console, dialogHosts[dialogHosts.length - 1]) : console}
  </OperationContext.Provider>;
}
