import { PageShell } from "../components/PageShell";
import { useEffect, useRef, useState } from "react";
import { errorMessage, getJson, postJson } from "../api";
import { Section, Status, TruncatedText } from "../components/Primitives";
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
  const [contextDetail, setContextDetail] = useState(false);
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
  const production = data.versions?.find((version: any) => version.status === "active");
  const released = production?.provenance === "published";
  return <PageShell className="page verification-page" header={<div className="page-title"><div><h1>问答验证</h1><p>通过实时问答验证当前 Production，并观察同一道问题优化前后的实际回答。</p></div></div>} tabs={<div className="tabs"><button aria-pressed={tab === "qa"} className={tab === "qa" ? "selected" : ""} onClick={() => setTab("qa")}>问答验证</button><button aria-pressed={tab === "compare"} className={tab === "compare" ? "selected" : ""} onClick={() => setTab("compare")}>方案对比</button><button aria-pressed={tab === "monitoring"} className={tab === "monitoring" ? "selected" : ""} onClick={() => { setTab("monitoring"); void refresh().catch(reason => setError(errorMessage(reason))); }}>Monitoring</button></div>} resetKey={tab}>


    {tab === "qa" && <AssistantPage productionVersion={production?.id || data.workspace?.active_version} isReleased={released} badCases={data.badCases || []} onOpenBadCase={() => {}} onOpenCitation={setCitation} onOpenDocument={onOpenDocument} />}
    {tab === "compare" && <ExperimentPage data={data} onOpenCitation={setCitation} />}
    {tab === "monitoring" && <Section title="Monitoring">
      <p className="muted">Production QA → 人工判断 Bad Case → Confirm Trigger → 下一轮 Optimization Agent</p>
      {error && <p className="error-notice" role="alert">{error}</p>}
      <div className="table-scroll monitoring-table"><table><thead><tr><th>问题</th><th>当前状态</th><th>人工判断</th><th>操作</th></tr></thead><tbody>{(monitoring.events || []).map((event: any) => {
        const eventTrigger = (monitoring.triggers || []).find((row: any) => row.event_id === event.id);
        return <tr key={event.id}><td><button className="text-button" onClick={() => setEventDetail(event)}><TruncatedText lines={2}>{event.question}</TruncatedText></button></td><td>{eventTrigger ? <Status value={eventTrigger.status} /> : event.determinable ? "已判定" : "待人工判断"}</td><td>{event.determinable ? event.bad_case ? event.severity === "critical" ? "人工安全 Bad Case" : "人工 Bad Case" : "人工判定正常" : "待判定"}</td><td><button className="text-button" disabled={busy} onClick={() => void assess(event, false, "ordinary")}>正常</button> <button className="text-button" disabled={busy} onClick={() => void assess(event, true, "ordinary")}>Bad Case</button> <button className="text-button" disabled={busy} onClick={() => void assess(event, true, "critical")}>安全问题</button></td></tr>;
      })}</tbody></table>{!(monitoring.events || []).length && <p className="muted">暂无真实问答记录。</p>}</div>
      <div className="monitoring-triggers">{(monitoring.triggers || []).map((row: any) => <div key={row.id}><strong>{row.reason}</strong><Status value={row.status} /><button className="text-button" aria-pressed={row.id === selectedTrigger.current} onClick={() => { setTriggerId(row.id); setContextDetail(true); }}>查看 Trigger 上下文</button>{row.status === "pending_human_confirm" && <button className="secondary" disabled={busy} onClick={() => { setTriggerId(row.id); void confirm(row); }}>人工确认</button>}</div>)}</div>
      {trigger && <div className="monitoring-context"><div><strong>所选 Trigger</strong><Status value={trigger.status} /></div>{linkedContext ? <><p>{currentContext ? "当前 Baseline" : "历史上下文，只读"} · {linkedContext.status === "pending_agent" ? "待启动 Round 1" : `Agent 状态：${linkedContext.status} · Round ${linkedContext.result?.round ?? linkedContext.rounds?.at(-1)?.round ?? "未记录"}`}</p>{linkedContext.status === "pending_agent" && <button className="primary" disabled={busy || !currentContext || !!data.workspace?.baseline_unavailable_reason} onClick={() => void startAgent()}>启动此上下文 Agent · Round 1</button>}</> : <p className="muted">{contextId ? "正在读取关联上下文…" : "尚未人工确认，未创建 Optimization 上下文。"}</p>}</div>}
    </Section>}
    <Drawer open={!!eventDetail} onOpenChange={open => !open && setEventDetail(null)} title="Production QA 与来源"><div className="drawer-body"><h3>{eventDetail?.question}</h3><p>{eventDetail?.answer}</p><p>Production：{eventDetail?.source?.production_version_id || "历史未采集"}</p><ExecutionMetrics metrics={eventDetail?.metrics} /><h3>版本 / 配置 / Corpus 与人工审计</h3></div></Drawer>
    <Drawer open={contextDetail} onOpenChange={setContextDetail} title="Trigger · Monitoring 实验上下文"><div className="drawer-body"><p>Trigger：{trigger?.id}</p><p>关联实验：{contextId || "尚未确认，未创建上下文"}</p>{linkedContext && <><p>Baseline：{linkedContext.baseline_run_id} · {currentContext ? "当前 Baseline" : "历史上下文，只读"}</p><p>{linkedContext.status === "pending_agent" ? "待启动 Round 1" : `Agent 状态：${linkedContext.status} · Round ${linkedContext.result?.round ?? linkedContext.rounds?.at(-1)?.round ?? "未记录"}`}</p></>}</div></Drawer>
    <Drawer open={!!citation} onOpenChange={open => !open && setCitation(null)} title="问答证据"><div className="drawer-body"><p>{citation?.document} · P.{citation?.page_start} · {citation?.section_path}</p><p>{sourceText || citation?.content_preview || "未记录证据文本"}</p></div></Drawer>
  </PageShell>;
}
