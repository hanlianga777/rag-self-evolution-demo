import { shortSourceName } from "./FrozenQuestionDetails";
import { IconLabel, IconTile } from "../ui/icons";
import { parameterValue } from "../components/comparisonData";
import {SavedAnswerComparison} from "../components/SavedAnswerComparison";
import {remainingQuestionIds,shortQuestionId,schemeName} from "../components/EvolutionStory";
import { DataTable } from "../components/DataTable";
import "./evaluation-workspaces.css";
import { StoryDisclosure } from "../components/Storytelling";
import { CaseAnswer } from "../components/CaseAnswer";
import { displayText, narrativeText, productionName } from "../display";
import { PageShell } from "../components/PageShell";
import { useContext, useEffect, useRef, useState } from "react";
import { preloadHistory } from "../listPreload";
import { detailJson, PageWarmupContext, useDetailPrefetch } from "../preload";
import { cachedJson, errorMessage, getJson, postJson } from "../api";
import { Section, Status, TruncatedText } from "../components/Primitives";
import { ConfirmDialog, Drawer } from "../components/Dialog";
import { ExecutionMetrics } from "../components/PipelineFields";
import { savedSnapshot } from "../evaluationProgress";
import { AssistantPage, type ChatExample } from "./AssistantPage";
import type { Citation } from "../types";
import { useOperation } from "../operation";

export function VerificationPage({ data, onOpenDocument }: { data: any; onOpenCitation: (citation: Citation) => void; onOpenDocument: (name: string) => void }) {
  const pagesWarming = useContext(PageWarmupContext);
  const operation = useOperation();
  const [tab, setTab] = useState<"qa" | "compare" | "monitoring">(() => { const value = new URLSearchParams(location.hash.split("?")[1]).get("tab") || "compare"; return ["qa", "compare", "monitoring"].includes(value) ? value as "qa" | "compare" | "monitoring" : "compare"; }), [busy, setBusy] = useState(false), [error, setError] = useState(""), [monitoring, setMonitoring] = useState<any>(data.monitoring || {});
  const [questionId, setQuestionId] = useState(() => new URLSearchParams(location.hash.split("?")[1]).get("q") || undefined);
  useEffect(() => {
    const sync = () => {
      if (!location.hash.startsWith("#verification?")) return;
      const params = new URLSearchParams(location.hash.split("?")[1]);
      const next=params.get("tab");
      if (next === "qa" || next === "compare" || next === "monitoring") { setTab(next); setQuestionId(params.get("q") || undefined); }
    };
    window.addEventListener("hashchange", sync);
    return () => window.removeEventListener("hashchange", sync);
  }, []);
  const [historyPage, setHistoryPage] = useState(1);
  const historyRows = (monitoring.events || []).length <= 200 ? monitoring.events || [] : monitoring.events.slice((historyPage - 1) * 200, historyPage * 200);
  const [eventDetail, setEventDetail] = useState<any>(null);
  const [contextDetail, setContextDetail] = useState(false);
  const [agentConfirm, setAgentConfirm] = useState(false);
  const [triggerId, setTriggerId] = useState<string | null>(null);
  const [context, setContext] = useState<any>(null);
  const trigger = (monitoring.triggers || []).find((row: any) => row.id === triggerId) || monitoring.triggers?.[0];
  const contextId = trigger?.optimization_run_id;
  const selectedTrigger = useRef(trigger?.id); selectedTrigger.current = trigger?.id;
  const linkedContext = context?.id === contextId ? context : null;
  const currentContext = !!linkedContext && linkedContext.baseline_run_id === data.workspace?.current_baseline_id;
  useEffect(() => {
    setContext(contextId ? cachedJson(`/api/experiments/${encodeURIComponent(contextId)}`) || null : null);
    if (!contextId) return;
    let cancelled = false;
    void detailJson<any>(`/api/experiments/${encodeURIComponent(contextId)}`).then(value => { if (!cancelled) setContext(value); }).catch(reason => { if (!cancelled) setError(errorMessage(reason)); });
    return () => { cancelled = true; };
  }, [contextId]);

  useDetailPrefetch((monitoring.triggers || []).filter((row: any) => row.optimization_run_id).map((row: any) => `/api/experiments/${encodeURIComponent(row.optimization_run_id)}`));
  const requests = useRef(0);
  useEffect(() => { setMonitoring(data.monitoring || {}); setHistoryPage(1); }, [data.monitoring]);
  useEffect(() => () => { requests.current++; }, []);
  const [citation, setCitation] = useState<Citation | null>(null), [sourceText, setSourceText] = useState("");
  useEffect(() => { setSourceText(""); if (!citation) return; if ((citation as any).savedEvidence) { setSourceText(citation.content_preview); return; } let cancelled = false; void getJson<any>(`/api/documents/${encodeURIComponent(citation.document_id)}`).then(value => { if (!cancelled) setSourceText(value.chunks?.find((chunk: any) => chunk.chunk_id === citation.chunk_id)?.chunk_text || citation.content_preview); }).catch(() => { if (!cancelled) setSourceText(citation.content_preview); }); return () => { cancelled = true; }; }, [citation]);
  const refresh = async () => { const ticket = ++requests.current; const value = await getJson<any>("/api/monitoring?page=1&limit=50").then(first => preloadHistory("/api/monitoring", first)); if (ticket === requests.current) { setMonitoring(value); setHistoryPage(1); } };
  const assess = async (event: any, bad_case: boolean, severity: "ordinary" | "critical") => { setBusy(true); setError(""); try { await operation.run("保存人工监控判定", () => postJson(`/api/monitoring/events/${event.id}/assessment`, { bad_case, severity })); await refresh(); } catch (reason) { setError(errorMessage(reason)); } finally { setBusy(false); } };
  const confirm = async (trigger: any) => { setBusy(true); setError(""); try { await operation.run("确认 Optimization Trigger", () => postJson(`/api/monitoring/triggers/${trigger.id}/confirm`, { decision: "approved" })); await refresh(); } catch (reason) { setError(errorMessage(reason)); } finally { setBusy(false); } };
  const startAgent = async () => {
    if (!trigger || !currentContext || linkedContext.status !== "pending_agent") return;
    const captured = trigger.id;
    setBusy(true); setError("");
    try {
      const result = await operation.run("启动 监控 Agent Round 1", () => postJson<any>("/api/experiments/run", { trigger_id: captured }));
      if (selectedTrigger.current === captured) {
        if (result.id !== contextId) throw new Error("监控 返回了不同实验上下文");
        setContext(result);
      }
      await refresh();
    } catch (reason) { if (selectedTrigger.current === captured) setError(errorMessage(reason)); }
    finally { setBusy(false); }
  };
  const exampleBaseline = data.evaluation;
  const exampleBaselineId = exampleBaseline?.id;
  const [exampleRun, setExampleRun] = useState<any>(() => exampleBaselineId ? cachedJson(`/api/evaluations/${encodeURIComponent(exampleBaselineId)}`) || null : null);
  const [exampleFailureId, setExampleFailureId] = useState<string>();
  useEffect(() => {
    let cancelled = false;
    if (tab !== "qa" || !exampleBaselineId || exampleBaseline.status !== "completed" || Array.isArray(exampleBaseline.cases)) return;
    setExampleFailureId(undefined);
    void getJson<any>(`/api/evaluations/${encodeURIComponent(exampleBaselineId)}`).then(run => {
      if (run.id !== exampleBaselineId) throw new Error("示例身份不匹配");
      if (!cancelled) setExampleRun(run);
    }).catch(() => { if (!cancelled) setExampleFailureId(exampleBaselineId); });
    return () => { cancelled = true; };
  }, [tab, exampleBaselineId, exampleBaseline?.status]);
  const exampleSource = Array.isArray(exampleBaseline?.cases) ? exampleBaseline : exampleRun?.id === exampleBaselineId ? exampleRun : null;
  const examples = !data.workspace?.requires_new_golden && !data.workspace?.requires_new_baseline && !data.workspace?.baseline_unavailable_reason && data.workspace?.current_baseline_id === exampleBaselineId ? frozenChatExamples(exampleSource, data.workspace?.current_golden_id) : [];
  const examplesLoading = !!exampleBaselineId && exampleBaseline?.status === "completed" && !exampleSource && exampleFailureId !== exampleBaselineId;
  const production = data.versions?.find((version: any) => version.status === "active");
  const released = production?.provenance === "published";
  const baselineId=data.workspace?.current_baseline_id || data.evaluation?.id;
  const remaining=!data.optimization?.baseline_run_id || data.optimization.baseline_run_id===baselineId ? remainingQuestionIds(data.optimization) : null;
  const markedBadCases=(monitoring.events || []).filter((event:any)=>event.determinable && event.bad_case).length;
  const openRemaining=(id:string)=>{setQuestionId(id);setTab("compare");location.hash=`verification?tab=compare&q=${encodeURIComponent(id)}`;};
  return <PageShell className="page verification-page" header={<div className="page-title"><div><h1><IconTile name="verify" />问答验证</h1><p className="ui-kicker page-purpose">Before / After 的真实回答对比</p></div></div>} tabs={<div className="tabs"><button aria-pressed={tab === "compare"} className={tab === "compare" ? "selected" : ""} onClick={() => setTab("compare")}>Before/After</button><button aria-pressed={tab === "qa"} className={tab === "qa" ? "selected" : ""} onClick={() => setTab("qa")}>实时问答</button><button aria-pressed={tab === "monitoring"} className={tab === "monitoring" ? "selected" : ""} onClick={() => setTab("monitoring")}>线上反馈 → 再次进化</button></div>} resetKey={tab}>


    {tab === "qa" && <AssistantPage examples={examples} examplesLoading={examplesLoading} examplesFailed={!!exampleBaselineId && exampleFailureId === exampleBaselineId} onAnswered={()=>{void refresh().catch(reason=>setError(errorMessage(reason)));}} productionLabel={released ? `当前线上：${schemeName(data.optimization?.candidates?.find((c:any)=>c.id===production.snapshot?.candidate_id),production.snapshot?.candidate_id).replace(/^Round \d+ · /, "")}（Candidate K ${parameterValue(production.config?.candidate_k)} · Top-K ${parameterValue(production.config?.top_k)} · Thinking ${parameterValue(production.config?.generation_thinking)}）` : "当前线上：Baseline（初始配置）"} productionVersion={production?.id || data.workspace?.active_version} isReleased={released} badCases={data.badCases || []} onOpenBadCase={() => { location.hash = "evaluation"; }} onOpenCitation={setCitation} onOpenDocument={onOpenDocument} onOpenMonitoring={()=>{setTab("monitoring");void refresh().catch(reason=>setError(errorMessage(reason)));}} />}
    {(tab === "compare" || !pagesWarming) && <div hidden={tab !== "compare"}><SavedAnswerComparison questionId={questionId} data={data} onOpenCitation={setCitation}/></div>}
    {tab === "monitoring" && <><Section title={<IconLabel name="rounds">把线上问题带回下一轮</IconLabel>}>
      <div className="feedback-loop" aria-label="线上反馈闭环"><ol className="feedback-loop-nodes">
        {[
          ["线上问答（附出处）","保存回答、版本与检索记录"],
          ["人工标记 Bad Case","正常、Bad Case 或安全问题"],
          ["进入下一轮输入","安全问题或积累的 Bad Case，由人工确认后进入"],
          ["Agent 新一轮 → Golden 复测 → 人工发布","用同一份冻结题卷验证修复与副作用"],
        ].map(([title,detail],index)=><li className="feedback-loop-node" key={title}><span className="feedback-loop-number">{index+1}</span><strong>{title}</strong><small>{detail}</small></li>)}
      </ol></div>
      <div className="feedback-next-inputs"><h3>下一轮已知输入</h3><p>本轮仍未修好：{remaining===null ? "未知" : remaining.length ? remaining.map((id,index)=><span key={id}>{index>0 && "、"}<button className="text-button" onClick={()=>openRemaining(id)}>{shortQuestionId(id)}</button></span>) : "无"}<span className="feedback-input-divider"> · </span>线上标记的 Bad Case：{markedBadCases} 条</p></div>
    </Section>
    {!monitoring.events?.length && <p className="ui-body-muted feedback-empty">暂无线上反馈；在「实时问答」提问后，可在这里标注回答是否属于 Bad Case。</p>}
    {(monitoring.events?.length || monitoring.triggers?.length || error) ? <Section title={<IconLabel name="verify">实际反馈记录</IconLabel>}>
      {error && <p className="error-notice" role="alert">{error}</p>}
      {(monitoring.events?.length || historyPage>1) ? <>{(monitoring.events?.length || 0) > 200 && <div className="review-batch"><button disabled={historyPage===1} onClick={()=>setHistoryPage(historyPage-1)}>上一页</button><span>第 {historyPage} 页 · 每页最多200条</span><button disabled={historyPage * 200 >= (monitoring.events?.length || 0)} onClick={()=>setHistoryPage(historyPage+1)}>下一页</button></div>}<div className="table-scroll monitoring-table"><DataTable><thead><tr><th>问题</th><th>当前状态</th><th>人工判断</th><th>操作</th></tr></thead><tbody>{historyRows.map((event: any) => {
        const eventTrigger = (monitoring.triggers || []).find((row: any) => row.event_id === event.id);
        return <tr key={event.id}><td><button className="text-button" onClick={() => setEventDetail(event)}><TruncatedText lines={1} hoverOnly>{event.question}</TruncatedText></button></td><td>{eventTrigger ? <Status value={eventTrigger.status === "human_confirmed" ? "已人工确认" : eventTrigger.status} /> : event.determinable ? "已判定" : "待人工判断"}</td><td>{event.determinable ? event.bad_case ? event.severity === "critical" ? "人工安全 Bad Case" : "人工 Bad Case" : "人工判定正常" : "待判定"}</td><td><div className="monitoring-assessment"><button className="text-button" disabled={busy} onClick={() => void assess(event, false, "ordinary")}>正常</button> <button className="text-button" disabled={busy} onClick={() => void assess(event, true, "ordinary")}>Bad Case</button> <button className="text-button" disabled={busy} onClick={() => void assess(event, true, "critical")}>安全问题</button></div></td></tr>;
      })}</tbody></DataTable></div></> : null}
      <div className="monitoring-triggers">{(monitoring.triggers || []).map((row: any) => <div key={row.id}><div className="muted-prose"><TruncatedText lines={3}>{narrativeText(row.reason || "原因未采集")}</TruncatedText></div><Status value={row.status === "human_confirmed" ? "已人工确认" : row.status} /><button className="text-button" aria-pressed={row.id === selectedTrigger.current} onClick={() => { setTriggerId(row.id); setContextDetail(true); }}>查看进化上下文</button>{row.status === "pending_human_confirm" && <button className="secondary" disabled={busy} onClick={() => { setTriggerId(row.id); void confirm(row); }}>人工确认</button>}</div>)}</div>
      {trigger && <div className="monitoring-context"><div><strong>所选进化线索</strong><Status value={trigger.status === "human_confirmed" ? "已人工确认" : trigger.status} /></div>{linkedContext ? <><p>{currentContext ? "当前 Baseline" : "历史上下文，只读"} · {linkedContext.status === "pending_agent" ? "待启动Round 1" : `Agent 状态：${displayText(linkedContext.status)} · Round ${linkedContext.result?.round ?? linkedContext.rounds?.at(-1)?.round ?? "未记录"}`}</p>{linkedContext.status === "pending_agent" && <button className="primary" disabled={busy || !currentContext || !!data.workspace?.baseline_unavailable_reason} onClick={() => setAgentConfirm(true)}>启动此上下文 Agent · Round 1</button>}</> : <p className="muted">{contextId ? "正在读取关联上下文…" : "尚未人工确认，未创建 Optimization 上下文。"}</p>}</div>}
    </Section> : null}</>}
    <ConfirmDialog open={agentConfirm} onOpenChange={setAgentConfirm} title="确认启动监控 Agent" busy={busy} onConfirm={() => { setAgentConfirm(false); void startAgent(); }}><p>将为所选反馈生成 Round 1 优化 Candidate，会调用模型并产生费用。</p><p>不会影响当前线上版本。</p></ConfirmDialog>
    <Drawer className="workbench-drawer" open={!!eventDetail} onOpenChange={open => !open && setEventDetail(null)} title="线上问答与来源"><div className="drawer-body story-details"><Section title="反馈结论"><p>{eventDetail?.determinable ? eventDetail.bad_case ? "人工判定为 Bad Case，后续以关联 Trigger 为准" : "人工判定正常" : "等待人工判断，尚非已确认 Bad Case"}</p></Section><Section title="问题"><CaseAnswer text={eventDetail?.question || "未保存问题"}/></Section><Section title="实际回答"><CaseAnswer text={eventDetail?.answer || "未保存回答"}/></Section><Section title="版本与引用来源"><p>请求时版本：{productionName((data.versions || []).find((version:any)=>version.id===eventDetail?.source?.production_version_id))}</p><p>引用以保存检索记录为准；反馈记录未单独采集引用正文时，不推测来源。</p></Section><StoryDisclosure label="耗时、配置与人工审计"><ExecutionMetrics metrics={eventDetail?.metrics}/><pre className="technical-record">{JSON.stringify(eventDetail,null,2)}</pre></StoryDisclosure></div></Drawer>
    <Drawer className="workbench-drawer" open={contextDetail} onOpenChange={setContextDetail} title="监控触发与实验上下文"><div className="drawer-body"><Section title="反馈与实验上下文"><p>反馈状态：{trigger ? displayText(trigger.status) : "暂无反馈"}</p><p>关联优化：{linkedContext ? "已建立" : "尚未确认，未创建上下文"}</p>{linkedContext && <><p>Baseline：{currentContext ? "当前 Baseline" : "历史上下文，只读"}</p><p>{linkedContext.status === "pending_agent" ? "待启动Round 1" : `Agent 状态：${displayText(linkedContext.status)} · Round ${linkedContext.result?.round ?? linkedContext.rounds?.at(-1)?.round ?? "未记录"}`}</p></>}</Section></div></Drawer>
    <Drawer className="workbench-drawer" open={!!citation} onOpenChange={open => !open && setCitation(null)} title="问答证据"><div className="drawer-body story-details"><Section title="引用来源"><p>{shortSourceName(citation?.document || "")} · p{citation?.page_start} · {citation?.section_path}</p><CaseAnswer text={sourceText || citation?.content_preview || "未记录证据文本"}/></Section></div></Drawer>
  </PageShell>;
}

function frozenChatExamples(run: any, goldenId: string | undefined): ChatExample[] {
  if (!run || run.status !== "completed" || !goldenId || run.dataset_version_id !== goldenId) return [];
  const snapshot = savedSnapshot(run);
  const questions = (snapshot.questions || []).filter((q: any) => snapshot.question_ids?.includes(q.id));
  const positives = questions.filter((q: any) => q.test_category === "positive").map((q: any) => ({q, row: run.cases?.find((c: any) => c.question_id === q.id)})).filter(({row}: any) => row?.passed === true && typeof row.programmatic_metrics?.latency_ms === "number");
  positives.sort((a: any, b: any) => a.row.programmatic_metrics.latency_ms - b.row.programmatic_metrics.latency_ms);
  return [
    {label: "正常问答", question: positives[0]?.q.question},
    {label: "应拒答 / 安全", question: questions.find((q: any) => q.test_category === "negative" && q.negative_subtype === "safety_critical")?.question},
    {label: "需要追问", question: questions.find((q: any) => q.test_category === "negative" && q.negative_subtype === "clarify")?.question},
  ];
}
