import "./evaluation-workspaces.css";
import { StoryDisclosure, StoryEmpty } from "../components/Storytelling";
import { CaseAnswer } from "../components/CaseAnswer";
import { displayText, narrativeText } from "../display";
import { PageShell } from "../components/PageShell";
import { useEffect, useRef, useState } from "react";
import { errorMessage, getJson, postJson } from "../api";
import { ConclusionCard, Section, Status, TruncatedText } from "../components/Primitives";
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
  const [historyPage, setHistoryPage] = useState(1);
  const [historyBusy, setHistoryBusy] = useState(false);
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
  useEffect(() => { setMonitoring(data.monitoring || {}); setHistoryPage(1); }, [data.monitoring]);
  useEffect(() => () => { requests.current++; }, []);
  const [citation, setCitation] = useState<Citation | null>(null), [sourceText, setSourceText] = useState("");
  useEffect(() => writeSession("rag-qa-tab", { tab }), [tab]);
  useEffect(() => { setSourceText(""); if (!citation) return; let cancelled = false; void getJson<any>(`/api/documents/${encodeURIComponent(citation.document_id)}`).then(value => { if (!cancelled) setSourceText(value.chunks?.find((chunk: any) => chunk.chunk_id === citation.chunk_id)?.chunk_text || citation.content_preview); }).catch(() => { if (!cancelled) setSourceText(citation.content_preview); }); return () => { cancelled = true; }; }, [citation]);
  const refresh = async (page=historyPage) => { const ticket = ++requests.current; setHistoryBusy(true); try { const value = await getJson(`/api/monitoring?page=${page}&limit=50`); if (ticket === requests.current) { setMonitoring(value); setHistoryPage(page); } } finally { if(ticket===requests.current)setHistoryBusy(false); } };
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


    {tab === "qa" && <AssistantPage productionVersion={production?.id || data.workspace?.active_version} isReleased={released} badCases={data.badCases || []} onOpenBadCase={() => { location.hash = "evaluation"; }} onOpenCitation={setCitation} onOpenDocument={onOpenDocument} onOpenMonitoring={()=>{setTab("monitoring");void refresh().catch(reason=>setError(errorMessage(reason)));}} />}
    {tab === "compare" && <ExperimentPage data={data} onOpenCitation={setCitation} />}
    {tab === "monitoring" && <><ConclusionCard title={monitoring.events?.length ? `${monitoring.events.length} 条本页实际问答反馈，等待或保留人工判定` : "反馈闭环已就绪，当前尚无实际问答记录"} tone="neutral">问答产生记录，人工判断是否属于 Bad Case；符合现有触发规则后，再人工确认关联优化上下文。发现问题不会绕过诊断、评测或人工发布。</ConclusionCard><ol className="decision-chain" aria-label="Monitoring 人工反馈闭环"><li><strong>真实问答</strong><span>保存实际问题、回答与版本</span></li><li><strong>问题反馈</strong><span>人工标注正常、普通或安全问题</span></li><li><strong>人工确认</strong><span>核对真实 Trigger 与优化上下文</span></li><li><strong>下一轮 Agent</strong><span>沿既有优化和评测规则继续</span></li></ol><Section title="实际反馈记录">
      {error && <p className="error-notice" role="alert">{error}</p>}
      {(monitoring.events?.length || historyPage>1) ? <><div className="review-batch"><button disabled={historyBusy || historyPage===1} onClick={()=>void refresh(historyPage-1).catch(reason=>setError(errorMessage(reason)))}>上一页</button><span>第 {historyPage} 页 · 每页最多50条</span><button disabled={historyBusy || Math.max(monitoring.events?.length || 0,monitoring.triggers?.length || 0)<50} onClick={()=>void refresh(historyPage+1).catch(reason=>setError(errorMessage(reason)))}>下一页</button></div><div className="table-scroll monitoring-table"><table><thead><tr><th>问题</th><th>当前状态</th><th>人工判断</th><th>操作</th></tr></thead><tbody>{(monitoring.events || []).map((event: any) => {
        const eventTrigger = (monitoring.triggers || []).find((row: any) => row.event_id === event.id);
        return <tr key={event.id}><td><button className="text-button" onClick={() => setEventDetail(event)}><TruncatedText lines={2}>{event.question}</TruncatedText></button></td><td>{eventTrigger ? <Status value={eventTrigger.status === "human_confirmed" ? "已人工确认" : eventTrigger.status} /> : event.determinable ? "已判定" : "待人工判断"}</td><td>{event.determinable ? event.bad_case ? event.severity === "critical" ? "人工安全 Bad Case" : "人工 Bad Case" : "人工判定正常" : "待判定"}</td><td><button className="text-button" disabled={busy} onClick={() => void assess(event, false, "ordinary")}>正常</button> <button className="text-button" disabled={busy} onClick={() => void assess(event, true, "ordinary")}>Bad Case</button> <button className="text-button" disabled={busy} onClick={() => void assess(event, true, "critical")}>安全问题</button></td></tr>;
      })}</tbody></table></div></> : <StoryEmpty title="当前尚无反馈记录">通过「问答验证」主动运行后，实际问答进入记录；本机优化线索仍需人工核对，不自动成为技术 Bad Case 或发布依据。</StoryEmpty>}
      <div className="monitoring-triggers">{(monitoring.triggers || []).map((row: any) => <div key={row.id}><p>{narrativeText(row.reason || "原因未采集")}</p><Status value={row.status === "human_confirmed" ? "已人工确认" : row.status} /><button className="text-button" aria-pressed={row.id === selectedTrigger.current} onClick={() => { setTriggerId(row.id); setContextDetail(true); }}>查看 Trigger 上下文</button>{row.status === "pending_human_confirm" && <button className="secondary" disabled={busy} onClick={() => { setTriggerId(row.id); void confirm(row); }}>人工确认</button>}</div>)}</div>
      {trigger && <div className="monitoring-context"><div><strong>所选 Trigger</strong><Status value={trigger.status === "human_confirmed" ? "已人工确认" : trigger.status} /></div>{linkedContext ? <><p>{currentContext ? "当前 Baseline" : "历史上下文，只读"} · {linkedContext.status === "pending_agent" ? "待启动 Round 1" : `Agent 状态：${displayText(linkedContext.status)} · Round ${linkedContext.result?.round ?? linkedContext.rounds?.at(-1)?.round ?? "未记录"}`}</p>{linkedContext.status === "pending_agent" && <button className="primary" disabled={busy || !currentContext || !!data.workspace?.baseline_unavailable_reason} onClick={() => void startAgent()}>启动此上下文 Agent · Round 1</button>}</> : <p className="muted">{contextId ? "正在读取关联上下文…" : "尚未人工确认，未创建 Optimization 上下文。"}</p>}</div>}
    </Section></>}
    <Drawer className="workbench-drawer" open={!!eventDetail} onOpenChange={open => !open && setEventDetail(null)} title="Production QA 与来源"><div className="drawer-body story-details"><Section title="反馈结论"><p>{eventDetail?.determinable ? eventDetail.bad_case ? "人工判定为 Bad Case，后续以关联 Trigger 为准" : "人工判定正常" : "等待人工判断，尚非已确认 Bad Case"}</p></Section><Section title="问题"><CaseAnswer text={eventDetail?.question || "未保存问题"}/></Section><Section title="实际回答"><CaseAnswer text={eventDetail?.answer || "未保存回答"}/></Section><Section title="版本与引用来源"><p>Production：{eventDetail?.source?.production_version_id || "历史未采集"}</p><p>Corpus：{eventDetail?.source?.corpus_fingerprint || "历史未采集"}</p><p>引用以保存检索记录为准；反馈记录未单独采集引用正文时，不推测来源。</p></Section><StoryDisclosure label="耗时、配置与人工审计"><ExecutionMetrics metrics={eventDetail?.metrics}/><pre className="technical-record">{JSON.stringify(eventDetail,null,2)}</pre></StoryDisclosure></div></Drawer>
    <Drawer className="workbench-drawer" open={contextDetail} onOpenChange={setContextDetail} title="Trigger · Monitoring 实验上下文"><div className="drawer-body"><p>Trigger：{trigger?.id}</p><p>关联实验：{contextId || "尚未确认，未创建上下文"}</p>{linkedContext && <><p>Baseline：{linkedContext.baseline_run_id} · {currentContext ? "当前 Baseline" : "历史上下文，只读"}</p><p>{linkedContext.status === "pending_agent" ? "待启动 Round 1" : `Agent 状态：${displayText(linkedContext.status)} · Round ${linkedContext.result?.round ?? linkedContext.rounds?.at(-1)?.round ?? "未记录"}`}</p></>}</div></Drawer>
    <Drawer className="workbench-drawer" open={!!citation} onOpenChange={open => !open && setCitation(null)} title="问答证据"><div className="drawer-body story-details"><Section title="引用来源"><p>{citation?.document} · P.{citation?.page_start} · {citation?.section_path}</p><CaseAnswer text={sourceText || citation?.content_preview || "未记录证据文本"}/></Section></div></Drawer>
  </PageShell>;
}
