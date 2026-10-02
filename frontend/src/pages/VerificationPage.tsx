import { useEffect, useRef, useState } from "react";
import { errorMessage, getJson, postJson } from "../api";
import { Section, Status, StageStepper, TechnicalDetails, TruncatedText } from "../components/Primitives";
import { Drawer } from "../components/Dialog";
import { ExecutionMetrics } from "../components/PipelineFields";
import { readSession, writeSession } from "../session";
import { AssistantPage } from "./AssistantPage";
import { ExperimentPage } from "./ExperimentPage";
import type { Citation } from "../types";
import { useOperation } from "../operation";

export function VerificationPage({ data, onOpenDocument }: { data: any; onOpenCitation: (citation: Citation) => void; onOpenDocument: (name: string) => void }) {
  const operation = useOperation();
  const [tab, setTab] = useState<"qa" | "compare" | "monitoring">(() => { const value = readSession("rag-qa-tab", { tab: "qa" }).tab; return ["qa", "compare", "monitoring"].includes(value) ? value as "qa" | "compare" | "monitoring" : "qa"; }), [busy, setBusy] = useState(false), [error, setError] = useState(""), [monitoring, setMonitoring] = useState<any>(data.monitoring || {});
  const [eventDetail, setEventDetail] = useState<any>(null);
  const [triggerId, setTriggerId] = useState<string | null>(null);
  const [context, setContext] = useState<any>(null);
  const trigger = (monitoring.triggers || []).find((row: any) => row.id === triggerId) || monitoring.triggers?.[0];
  const contextId = trigger?.optimization_run_id;
  const selectedTrigger = useRef(trigger?.id); selectedTrigger.current = trigger?.id;
  const linkedContext = context?.id === contextId ? context : null;
  const currentContext = !!linkedContext && linkedContext.baseline_run_id === data.workspace?.current_baseline_id;
  useEffect(() => {
    setContext(null);
    if (!contextId) return;
    let cancelled = false;
    void getJson<any>(`/api/experiments/${encodeURIComponent(contextId)}`).then(value => { if (!cancelled) setContext(value); }).catch(reason => { if (!cancelled) setError(errorMessage(reason)); });
    return () => { cancelled = true; };
  }, [contextId]);

  const requests = useRef(0);
  useEffect(() => { setMonitoring(data.monitoring || {}); }, [data.monitoring]);
  useEffect(() => () => { requests.current++; }, []);
  const [citation, setCitation] = useState<Citation | null>(null), [sourceText, setSourceText] = useState("");
  useEffect(() => writeSession("rag-qa-tab", { tab }), [tab]);
  useEffect(() => { setSourceText(""); if (!citation) return; let cancelled = false; void getJson<any>(`/api/documents/${encodeURIComponent(citation.document_id)}`).then(value => { if (!cancelled) setSourceText(value.chunks?.find((chunk: any) => chunk.chunk_id === citation.chunk_id)?.chunk_text || citation.content_preview); }).catch(() => { if (!cancelled) setSourceText(citation.content_preview); }); return () => { cancelled = true; }; }, [citation]);
  const refresh = async () => { const ticket = ++requests.current; const value = await getJson("/api/monitoring"); if (ticket === requests.current) setMonitoring(value); };
  const assess = async (event: any, bad_case: boolean, severity: "ordinary" | "critical") => { setBusy(true); setError(""); try { await operation.run("保存人工监控判定", () => postJson(`/api/monitoring/events/${event.id}/assessment`, { bad_case, severity })); await refresh(); } catch (reason) { setError(errorMessage(reason)); } finally { setBusy(false); } };
  const confirm = async (trigger: any) => { setBusy(true); setError(""); try { await operation.run("确认 Optimization Trigger", () => postJson(`/api/monitoring/triggers/${trigger.id}/confirm`, { decision: "approved" })); await refresh(); } catch (reason) { setError(errorMessage(reason)); } finally { setBusy(false); } };
  const startAgent = async () => {
    if (!trigger || !currentContext || linkedContext.status !== "pending_agent") return;
    const captured = trigger.id;
    setBusy(true); setError("");
    try {
      const result = await operation.run("启动 Monitoring Agent Round 1", () => postJson<any>("/api/experiments/run", { trigger_id: captured }));
      if (selectedTrigger.current === captured) {
        if (result.id !== contextId) throw new Error("Monitoring 返回了不同实验上下文");
        setContext(result);
      }
      await refresh();
    } catch (reason) { if (selectedTrigger.current === captured) setError(errorMessage(reason)); }
    finally { setBusy(false); }
  };
  const released = data.versions?.find((version: any) => version.status === "active")?.provenance === "published";
  return <div className="page verification-page"><div className="page-title"><div><h1>问答验证</h1><p>验证当前配置、比较同题方案，并查看运行监控。</p></div></div>{tab === "monitoring" && <StageStepper ariaLabel="监控阶段" steps={[{ label: "Production Signals", state: monitoring.events?.length ? "completed" : "current" }, { label: "Human Review", state: monitoring.events?.some((row: any) => row.id === trigger?.event_id && row.determinable) ? "completed" : "pending" }, { label: "Trigger", state: trigger?.status === "human_confirmed" ? "completed" : "pending" }, { label: "Optimization Agent", state: linkedContext?.candidates?.length ? "completed" : ["pending_agent", "generating"].includes(linkedContext?.status) ? "current" : "pending" }]} />}<div className="tabs"><button aria-pressed={tab === "qa"} className={tab === "qa" ? "selected" : ""} onClick={() => setTab("qa")}>问答验证</button><button aria-pressed={tab === "monitoring"} className={tab === "monitoring" ? "selected" : ""} onClick={() => { setTab("monitoring"); void refresh().catch(reason => setError(errorMessage(reason))); }}>Monitoring</button><button aria-pressed={tab === "compare"} className={tab === "compare" ? "selected" : ""} onClick={() => setTab("compare")}>方案对比</button></div>{tab === "qa" && <AssistantPage productionVersion={data.workspace?.active_version} isReleased={released} badCases={data.badCases || []} onOpenBadCase={() => {}} onOpenCitation={setCitation} onOpenDocument={onOpenDocument} />}{tab === "compare" && <ExperimentPage data={data} onOpenCitation={setCitation} />}{tab === "monitoring" && <Section title="Monitoring"><p className="muted">当前 Production {data.workspace?.active_version || "未记录"} · 最近问答数 {monitoring.events?.length || 0} · 待确认 Trigger 数 {(monitoring.triggers || []).filter((item: any) => item.status === "pending_human_confirm").length}</p>{error && <p className="error-notice" role="alert">{error}</p>}<p className="muted">Trigger → 人工确认 → Optimization Agent；不会自动调参或发布。</p><div className="table-scroll monitoring-table"><table><thead><tr><th>Question</th><th>Feedback Signal</th><th>Safety Signal</th><th>Latency</th><th>Human Status</th><th>操作</th></tr></thead><tbody>{(monitoring.events || []).map((event: any) => <tr key={event.id}><td><button className="text-button" onClick={() => setEventDetail(event)}><TruncatedText lines={2}>{event.question}</TruncatedText></button></td><td>{event.metrics?.feedback_signal ?? "—"}</td><td>{event.metrics?.safety_signal ?? "—"}</td><td>{event.metrics?.latency_ms == null ? "—" : `${event.metrics.latency_ms} ms`}</td><td>{event.determinable ? event.bad_case ? "人工 Bad Case" : "人工判定正常" : "待人工判定"}</td><td><button className="text-button" disabled={busy} onClick={() => void assess(event, false, "ordinary")}>正常</button> <button className="text-button" disabled={busy} onClick={() => void assess(event, true, "ordinary")}>Bad Case</button> <button className="text-button" disabled={busy} onClick={() => void assess(event, true, "critical")}>安全问题</button></td></tr>)}</tbody></table>{!(monitoring.events || []).length && <p className="muted">暂无真实问答记录。</p>}</div><div className="run-list">{(monitoring.triggers || []).map((trigger: any) => <div key={trigger.id}><strong>{trigger.reason}</strong><Status value={trigger.status} /><button className="secondary" aria-pressed={trigger.id === selectedTrigger.current} onClick={() => setTriggerId(trigger.id)}>查看 Trigger 上下文</button>{trigger.status === "pending_human_confirm" && <button className="secondary" disabled={busy} onClick={() => void confirm(trigger)}>人工确认</button>}</div>)}</div>{trigger && <div className="monitoring-context"><h3>当前查看 Trigger · {trigger.id}</h3><p>关联实验：{contextId || "尚未确认，未创建上下文"}</p>{linkedContext && <><p>Baseline：{linkedContext.baseline_run_id} · {currentContext ? "当前 Baseline" : "历史上下文，只读"}</p><p>{linkedContext.status === "pending_agent" ? "待启动 Round 1" : `Agent 状态：${linkedContext.status} · Round ${linkedContext.result?.round ?? linkedContext.rounds?.at(-1)?.round ?? "未记录"}`}</p>{linkedContext.status === "pending_agent" && <button className="primary" disabled={busy || !currentContext || !!data.workspace?.baseline_unavailable_reason} onClick={() => void startAgent()}>启动此上下文 Agent · Round 1</button>}<TechnicalDetails label="所选 Monitoring 实验上下文">{JSON.stringify(linkedContext, null, 2)}</TechnicalDetails></>}</div>}</Section>}<Drawer open={!!eventDetail} onOpenChange={open => !open && setEventDetail(null)} title="Production QA 与来源"><div className="drawer-body"><h3>{eventDetail?.question}</h3><p>{eventDetail?.answer}</p><p>Production：{eventDetail?.source?.production_version_id || "历史未采集"}</p><ExecutionMetrics metrics={eventDetail?.metrics} /><TechnicalDetails label="版本 / 配置 / Corpus 与人工审计">{JSON.stringify(eventDetail, null, 2)}</TechnicalDetails></div></Drawer><Drawer open={!!citation} onOpenChange={open => !open && setCitation(null)} title="问答证据"><div className="drawer-body"><p>{citation?.document} · P.{citation?.page_start} · {citation?.section_path}</p><p>{sourceText || citation?.content_preview || "未记录证据文本"}</p></div></Drawer></div>;
}
