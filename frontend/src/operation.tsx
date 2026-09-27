import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { getJson } from "./api";

type Operation = { id: string; title: string; status: "running" | "completed" | "failed"; kind?: "evaluation" | "revision"; stage?: string; stageCode?: string; current?: number; total?: number; error?: string; errorDetail?: string; provider?: string; model?: string; attempt?: number; startedAt?: number; endedAt?: number; dismissed?: boolean; restored?: boolean };
type OperationContextValue = {
  start: (title: string, detail?: Partial<Operation>) => string;
  update: (id: string, detail: Partial<Operation>) => void;
  succeed: (id: string) => void;
  fail: (id: string, reason: unknown) => void;
  run: <T>(title: string, work: () => Promise<T>) => Promise<T>;
  watchEvaluation: (id: string, title: string) => void;
  watchRevision: (id: string) => void;
  registerDialogHost: (node: HTMLElement) => void;
  unregisterDialogHost: (node: HTMLElement) => void;
};

const fallback: OperationContextValue = { start: () => "", update: () => {}, succeed: () => {}, fail: () => {}, run: (_title, work) => work(), watchEvaluation: () => {}, watchRevision: () => {}, registerDialogHost: () => {}, unregisterDialogHost: () => {} };
const OperationContext = createContext<OperationContextValue>(fallback);
export function useOperation() { return useContext(OperationContext); }

function evaluation(run: any): Partial<Operation> {
  let total: number | undefined;
  try { total = JSON.parse(run.dataset_snapshot_json || "{}").question_ids?.length; } catch { /* old run has no readable snapshot */ }
  return { status: run.status === "running" ? "running" : run.status === "completed" ? "completed" : "failed", stage: run.status === "running" ? "正在运行 Golden Case" : run.status === "completed" ? "评测完成" : "评测失败", current: run.cases?.length, total, error: run.error_message };
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
  const watchEvaluation = useCallback((id: string, title: string) => start(title, { id, kind: "evaluation" }), [start]);
  const watchRevision = useCallback((id: string) => start("局部修订", { id, kind: "revision" }), [start]);
  const registerDialogHost = useCallback((node: HTMLElement) => setDialogHosts(current => [...current.filter(item => item !== node), node]), []);
  const unregisterDialogHost = useCallback((node: HTMLElement) => setDialogHosts(current => current.filter(item => item !== node)), []);

  useEffect(() => {
    if (!restore) return;
    let cancelled = false;
    getJson<any[]>("/api/evaluations").then(evaluations => {
      if (cancelled) return;
      for (const item of evaluations.filter(item => item.status === "running")) start(item.config?.candidate_id ? `Candidate ${item.config.candidate_id} Sandbox` : "Baseline Evaluation", { id: item.id, kind: "evaluation", restored: true, startedAt: item.created_at ? Date.parse(item.created_at) : undefined });
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
        void getJson<any>(item.kind === "revision" ? `/api/governance/revisions/${item.id}` : `/api/evaluations/${item.id}`).then(result => {
          const next: Partial<Operation> = item.kind === "revision" ? revision(result) : evaluation(result);
          update(item.id, next);
          if (next.status === "completed") succeed(item.id);
          if (next.status === "failed") fail(item.id, next.error || "评测失败");
        }).catch(reason => fail(item.id, reason));
      }
    }, 1000);
    return () => window.clearInterval(timer);
  }, [operations, update, succeed, fail]);

  const visible = operations.filter(item => !item.dismissed).slice(-3);
  const console = !!visible.length && <div className="operation-stack" aria-label="运行状态">{visible.map(item => <section className="operation-console" key={item.id} role={item.status === "failed" ? "alert" : "status"}>
      <div className="operation-head"><strong>{item.title}</strong><button aria-label="关闭运行状态" onClick={() => setOperations(current => current.map(row => row.id === item.id && row.status === "running" ? { ...row, dismissed: true } : row).filter(row => row.id !== item.id || row.status === "running"))}>×</button></div>
      <p>{item.status === "failed" ? "运行失败" : item.status === "completed" ? "✓ 完成" : item.restored ? `数据库记录：${item.stage || "运行中"}（Worker 未确认）` : item.stage || "运行中"}{item.startedAt != null && <span> · {Math.max(0, ((item.endedAt ?? now) - item.startedAt) / 1000).toFixed(1)}s</span>}</p>
      {item.kind === "revision" && item.total === 1 && item.status === "running" && <progress />}
      {!(item.kind === "revision" && item.total === 1) && item.current != null && item.total != null && item.total > 0 && <><div className="operation-count">{item.current} / {item.total}<span>{Math.round(item.current / item.total * 100)}%</span></div><progress value={item.current} max={item.total} /></>}
      {(item.current == null || item.total == null || item.total <= 0) && item.status === "running" && !(item.kind === "revision" && item.total === 1) && <progress />}
      {item.status === "failed" && <><small className="operation-error-summary">{shortError(item.error)}</small><button className="operation-detail-button" aria-label="查看错误详情" aria-expanded={detailId === item.id} aria-controls={`operation-detail-${item.id}`} onClick={() => setDetailId(current => current === item.id ? null : item.id)}>查看错误详情</button>{detailId === item.id && <div id={`operation-detail-${item.id}`} className="operation-details"><div>阶段：{item.stage || "未记录"}</div><div>耗时：{item.startedAt != null ? `${Math.max(0, ((item.endedAt ?? now) - item.startedAt) / 1000).toFixed(1)}s` : "未记录"}</div><div>错误：{item.errorDetail || item.error || "未记录"}</div><div>Operation ID：{item.id}</div>{item.provider && <div>Provider：{item.provider}</div>}{item.model && <div>Model：{item.model}</div>}{item.attempt != null && <div>Attempt：{item.attempt}</div>}</div>}</>}
    </section>)}</div>;
  return <OperationContext.Provider value={{ start, update, succeed, fail, run, watchEvaluation, watchRevision, registerDialogHost, unregisterDialogHost }}>
    {children}
    {dialogHosts.length ? createPortal(console, dialogHosts[dialogHosts.length - 1]) : console}
  </OperationContext.Provider>;
}
