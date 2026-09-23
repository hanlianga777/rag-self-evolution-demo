import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { getJson } from "./api";

type Operation = { id: string; title: string; status: "running" | "completed" | "failed"; kind?: "generation" | "evaluation"; stage?: string; current?: number; total?: number; slot?: string; attempt?: number; skipped?: number; error?: string; failedStage?: string };
type OperationContextValue = {
  start: (title: string, detail?: Partial<Operation>) => string;
  update: (id: string, detail: Partial<Operation>) => void;
  succeed: (id: string) => void;
  fail: (id: string, reason: unknown) => void;
  run: <T>(title: string, work: () => Promise<T>) => Promise<T>;
  watchGeneration: (id: string) => void;
  watchEvaluation: (id: string, title: string) => void;
};

const fallback: OperationContextValue = { start: () => "", update: () => {}, succeed: () => {}, fail: () => {}, run: (_title, work) => work(), watchGeneration: () => {}, watchEvaluation: () => {} };
const OperationContext = createContext<OperationContextValue>(fallback);
export function useOperation() { return useContext(OperationContext); }

function generation(run: any): Partial<Operation> {
  const progress = run.artifacts?.hard_validation?.progress || {};
  const stage = progress.stage || run.status;
  const current = stage === "generating" || stage === "validation" || stage === "failed" || stage === "completed" ? progress.completed_slots : stage === "probing" ? progress.probe_completed : stage === "qc" ? progress.qc_completed : undefined;
  return { status: run.status === "failed" ? "failed" : run.status === "completed" ? "completed" : "running", stage, current, total: current == null ? undefined : progress.total_slots, slot: progress.slot, attempt: progress.attempt, skipped: progress.qc_skipped, failedStage: run.artifacts?.hard_validation?.failed_stage, error: run.artifacts?.hard_validation?.error };
}

function evaluation(run: any): Partial<Operation> {
  let total: number | undefined;
  try { total = JSON.parse(run.dataset_snapshot_json || "{}").question_ids?.length; } catch { /* old run has no readable snapshot */ }
  return { status: run.status === "running" ? "running" : run.status === "completed" ? "completed" : "failed", stage: run.status === "running" ? "正在运行 Golden Case" : run.status === "completed" ? "评测完成" : "评测失败", current: run.cases?.length, total, error: run.error_message };
}

export function OperationProvider({ children, restore = true }: { children: ReactNode; restore?: boolean }) {
  const [operations, setOperations] = useState<Operation[]>([]);
  const [showDetail, setShowDetail] = useState(false);
  const update = useCallback((id: string, detail: Partial<Operation>) => setOperations(current => current.map(item => item.id === id ? { ...item, ...detail } : item)), []);
  const start = useCallback((title: string, detail: Partial<Operation> = {}) => {
    const id = detail.id || `operation-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    setOperations(current => [...current.filter(item => item.id !== id), { id, title, status: "running", ...detail }]);
    setShowDetail(false);
    return id;
  }, []);
  const succeed = useCallback((id: string) => {
    update(id, { status: "completed" });
    window.setTimeout(() => setOperations(current => current.filter(item => item.id !== id)), 700);
  }, [update]);
  const fail = useCallback((id: string, reason: unknown) => update(id, { status: "failed", error: reason instanceof Error ? reason.message : String(reason) }), [update]);
  const run: OperationContextValue["run"] = useCallback(async (title, work) => {
    const id = start(title);
    try { const result = await work(); succeed(id); return result; }
    catch (reason) { fail(id, reason); throw reason; }
  }, [start, succeed, fail]);
  const watchGeneration = useCallback((id: string) => start("Golden Dataset Generation", { id, kind: "generation" }), [start]);
  const watchEvaluation = useCallback((id: string, title: string) => start(title, { id, kind: "evaluation" }), [start]);

  useEffect(() => {
    if (!restore) return;
    let cancelled = false;
    Promise.all([getJson<any[]>("/api/governance/generation-runs"), getJson<any[]>("/api/evaluations")]).then(([runs, evaluations]) => {
      if (cancelled) return;
      const activeGeneration = runs.find(item => ["queued", "coverage", "generating", "validation", "probing", "qc"].includes(item.status));
      if (activeGeneration) start("Golden Dataset Generation", { id: activeGeneration.id, kind: "generation", ...generation(activeGeneration) });
      for (const item of evaluations.filter(item => item.status === "running")) start(item.config?.candidate_id ? `Candidate ${item.config.candidate_id} Sandbox` : "Baseline Evaluation", { id: item.id, kind: "evaluation" });
    }).catch(() => {});
    return () => { cancelled = true; };
  }, [restore, start]);

  useEffect(() => {
    const active = operations.filter(item => item.status === "running" && item.kind);
    if (!active.length) return;
    const timer = window.setInterval(() => {
      for (const item of active) {
        const path = item.kind === "generation" ? `/api/governance/generation-runs/${item.id}` : `/api/evaluations/${item.id}`;
        void getJson<any>(path).then(result => {
          const next = item.kind === "generation" ? generation(result) : evaluation(result);
          update(item.id, next);
          if (next.status === "completed") succeed(item.id);
        }).catch(reason => fail(item.id, reason));
      }
    }, 1000);
    return () => window.clearInterval(timer);
  }, [operations, update, succeed, fail]);

  const visible = operations.at(-1);
  const stages: Record<string, string> = { queued: "排队中", coverage: "规划覆盖", generating: "逐题生成与修复", validation: "硬校验", candidate_persistence: "候选题入库", probing: "检索验证", qc: "质量检查", completed: "已完成", failed: "运行失败" };
  const label = visible?.stage === "generating" ? (visible.attempt && visible.attempt > 1 ? "正在修复测试题" : "正在生成测试题") : stages[visible?.stage || ""] || visible?.stage || "运行中";
  return <OperationContext.Provider value={{ start, update, succeed, fail, run, watchGeneration, watchEvaluation }}>
    {children}
    {visible && <section className="operation-console" aria-label="运行状态" role={visible.status === "failed" ? "alert" : "status"}>
      <div className="operation-head"><strong>{visible.title}</strong><button aria-label="关闭运行状态" onClick={() => setOperations(current => current.filter(item => item.id !== visible.id))}>×</button></div>
      <p>{visible.status === "failed" ? "运行失败" : visible.status === "completed" ? "✓ 完成" : label}<span className="operation-cursor" aria-hidden="true">_</span></p>
      {visible.slot && <small>{visible.slot}{visible.attempt ? ` · 第 ${visible.attempt} 次尝试` : ""}</small>}
      {visible.current != null && visible.total != null && <><div className="operation-count">{visible.current} / {visible.total}<span>{Math.round(visible.current / visible.total * 100)}%</span></div><progress value={visible.current} max={visible.total} /></>}
      {visible.current == null && visible.status === "running" && <progress />}
      {visible.skipped ? <small>QC 跳过 {visible.skipped} 题（Probe 未通过）</small> : null}
      {visible.status === "failed" && <><small>阶段：{stages[visible.failedStage || ""] || visible.failedStage || label}</small><button className="operation-detail-button" aria-label="查看错误详情" onClick={() => setShowDetail(value => !value)}>查看错误详情</button>{showDetail && <pre>{visible.error || "请查看运行审计"}</pre>}</>}
    </section>}
  </OperationContext.Provider>;
}
