import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { getJson } from "./api";

type Operation = { id: string; title: string; status: "running" | "completed" | "failed"; kind?: "evaluation"; stage?: string; current?: number; total?: number; error?: string; startedAt?: number; endedAt?: number; dismissed?: boolean; restored?: boolean };
type OperationContextValue = {
  start: (title: string, detail?: Partial<Operation>) => string;
  update: (id: string, detail: Partial<Operation>) => void;
  succeed: (id: string) => void;
  fail: (id: string, reason: unknown) => void;
  run: <T>(title: string, work: () => Promise<T>) => Promise<T>;
  watchEvaluation: (id: string, title: string) => void;
};

const fallback: OperationContextValue = { start: () => "", update: () => {}, succeed: () => {}, fail: () => {}, run: (_title, work) => work(), watchEvaluation: () => {} };
const OperationContext = createContext<OperationContextValue>(fallback);
export function useOperation() { return useContext(OperationContext); }

function evaluation(run: any): Partial<Operation> {
  let total: number | undefined;
  try { total = JSON.parse(run.dataset_snapshot_json || "{}").question_ids?.length; } catch { /* old run has no readable snapshot */ }
  return { status: run.status === "running" ? "running" : run.status === "completed" ? "completed" : "failed", stage: run.status === "running" ? "正在运行 Golden Case" : run.status === "completed" ? "评测完成" : "评测失败", current: run.cases?.length, total, error: run.error_message };
}

export function OperationProvider({ children, restore = true }: { children: ReactNode; restore?: boolean }) {
  const [operations, setOperations] = useState<Operation[]>([]);
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

  useEffect(() => {
    if (!restore) return;
    let cancelled = false;
    getJson<any[]>("/api/evaluations").then(evaluations => {
      if (cancelled) return;
      for (const item of evaluations.filter(item => item.status === "running")) start(item.config?.candidate_id ? `Candidate ${item.config.candidate_id} Sandbox` : "Baseline Evaluation", { id: item.id, kind: "evaluation", restored: true, startedAt: item.created_at ? Date.parse(item.created_at) : undefined });
    }).catch(() => {});
    return () => { cancelled = true; };
  }, [restore, start]);

  useEffect(() => {
    const active = operations.filter(item => item.status === "running" && item.kind);
    if (!active.length) return;
    const timer = window.setInterval(() => {
      for (const item of active) {
        void getJson<any>(`/api/evaluations/${item.id}`).then(result => {
          const next = evaluation(result);
          update(item.id, next);
          if (next.status === "completed") succeed(item.id);
          if (next.status === "failed") fail(item.id, next.error || "评测失败");
        }).catch(reason => fail(item.id, reason));
      }
    }, 1000);
    return () => window.clearInterval(timer);
  }, [operations, update, succeed, fail]);

  const visible = operations.filter(item => !item.dismissed).slice(-3);
  return <OperationContext.Provider value={{ start, update, succeed, fail, run, watchEvaluation }}>
    {children}
    {!!visible.length && <div className="operation-stack" aria-label="运行状态">{visible.map(item => <section className="operation-console" key={item.id} role={item.status === "failed" ? "alert" : "status"}>
      <div className="operation-head"><strong>{item.title}</strong><button aria-label="关闭运行状态" onClick={() => setOperations(current => current.map(row => row.id === item.id && row.status === "running" ? { ...row, dismissed: true } : row).filter(row => row.id !== item.id || row.status === "running"))}>×</button></div>
      <p>{item.status === "failed" ? "运行失败" : item.status === "completed" ? "✓ 完成" : item.restored ? `数据库记录：${item.stage || "运行中"}（Worker 未确认）` : item.stage || "运行中"}{item.startedAt != null && <span> · {Math.max(0, ((item.endedAt ?? now) - item.startedAt) / 1000).toFixed(1)}s</span>}</p>
      {item.current != null && item.total != null && item.total > 0 && <><div className="operation-count">{item.current} / {item.total}<span>{Math.round(item.current / item.total * 100)}%</span></div><progress value={item.current} max={item.total} /></>}
      {(item.current == null || item.total == null || item.total <= 0) && item.status === "running" && <progress />}
      {item.status === "failed" && <><button className="operation-detail-button" aria-label="查看错误详情" onClick={() => setDetailId(current => current === item.id ? null : item.id)}>查看错误详情</button>{detailId === item.id && <pre>{item.error || "请查看运行审计"}</pre>}</>}
    </section>)}</div>}
  </OperationContext.Provider>;
}
