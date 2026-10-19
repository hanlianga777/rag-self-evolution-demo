import { StoryDisclosure } from "../components/Storytelling";
import './evaluation-workspaces.css';
import {DiagnosisFilters, DiagnosisTable, DetectionNotice, allDiagnosis, filterDiagnosis, savedDirections, currentRoot, rootName, symptoms, technicalDiagnosisRows, isTechnicalBadCase, QualityAudit} from '../components/EvaluationDiagnosis';
import { ProviderAuthorization, type PaidRequest } from "../components/ProviderAuthorization";
import { PageShell } from "../components/PageShell";
import { RetrievalEvidence } from "../components/RetrievalEvidence";
import { useEffect, useState } from "react";
import { Play } from "lucide-react";
import { errorMessage, getJson, postJson } from "../api";
import { ConclusionCard, Section, ShortId, Status, TruncatedText } from "../components/Primitives";
import { ExecutionMetrics, parameterNames } from "../components/PipelineFields";
import { CaseAnswer } from "../components/CaseAnswer";
import { Drawer } from "../components/Dialog";
import { displayText } from "../display";
import { useOperation } from "../operation";

type Row = Record<string, any>;
type Tab = "report" | "gates" | "cases";
type Filter = "bad" | "all" | "positive" | "ablation" | "negative" | "retrieval" | "generation" | "safety";

export const gateNames: Record<string, string> = {
  positive_correctness: "Correctness（正确性）", positive_faithfulness: "Faithfulness（忠实性）", positive_completeness: "Completeness（完整性）",
  ablation_correctness: "Ablation Correctness（消融题正确性）", ablation_faithfulness: "Faithfulness（忠实性）", ablation_completeness: "Completeness（完整性）",
  safe_rejection_rate: "Safe Rejection Rate（安全拒答率）", safety_critical_accuracy: "Safety Critical Accuracy（安全关键准确率）",
  prompt_injection_resistance: "Prompt Injection Resistance（提示注入抵抗）", latency_p50_seconds: "Latency P50", latency_p99_seconds: "Latency P99" };
const format = (value: unknown, suffix = "") => typeof value === "number" ? `${value.toFixed(2)}${suffix}` : "未采集";
const group = (metric: string) => metric.startsWith("positive_") ? "正向题（Positive）" : metric.startsWith("ablation_") ? "消融题（Ablation）" : metric.startsWith("latency_") ? "性能（Performance）" : "负向题 / 安全（Negative / Safety）";
const gateValue = (gate: Row) => format(gate.actual, gate.metric.startsWith("latency_") ? " s" : "%");
const gateThreshold = (gate: Row) => `${gate.operator === ">=" ? "≥" : "≤"} ${format(gate.threshold, gate.metric.startsWith("latency_") ? " s" : "%")}`;
const localTime = (value?: string) => {
  if (!value) return "未记录";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "未记录" : new Intl.DateTimeFormat("zh-CN", { timeZone: "Asia/Shanghai", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false }).format(date).replaceAll("/", "-");
};


export function EvaluationPage({ data }: { data: any; navigate?: (page: any) => void }) {
  const operation = useOperation();
  const [paid, setPaid] = useState<PaidRequest | null>(null);
  const [replayOpen, setReplayOpen] = useState(false);
  const [replay, setReplay] = useState<Row | null>(null);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [history, setHistory] = useState<Row[]>([]);
  const [historyPage, setHistoryPage] = useState(1);
  const [historyBusy, setHistoryBusy] = useState(false);
  const [tab, setTab] = useState<Tab>("report");
  const [filter, setFilter] = useState<Filter>("bad");
  const [diagnosisFilter,setDiagnosisFilter]=useState(allDiagnosis);
  useEffect(()=>{setDiagnosisFilter(allDiagnosis);},[tab]);
  const [run, setRun] = useState<Row>(data.evaluation || {});
  const [badCases, setBadCases] = useState<Row[]>(data.badCases || []);
  const [selectedGate, setSelectedGate] = useState<Row | null>(null);
  const [selectedCase, setSelectedCase] = useState<Row | null>(null);
  const [configOpen, setConfigOpen] = useState(false);
  const [technicalOpen, setTechnicalOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(()=>{let cancelled=false;void getJson<Row>('/api/evaluation?active_task=true').then(value=>{if(!cancelled && value.id)setRun(value)}).catch(()=>{});return()=>{cancelled=true};},[]);
  useEffect(() => {
    if (!run.id) return;
    let cancelled = false;
    const poll = async () => {
      if(cancelled)return;
      try {
        const next = await getJson<Row>(`/api/evaluations/${run.id}`);
        if (cancelled) return;
        setRun(next);
        if (["queued","running"].includes(next.status)) window.setTimeout(poll, 1000);
        if (next.status !== "running") { const rows = await getJson<Row[]>("/api/bad-cases"); if (!cancelled) setBadCases(rows); }
      } catch (reason) { if (!cancelled) { setError(errorMessage(reason)); window.setTimeout(poll,2000); } }
    };
    void poll();
    return () => { cancelled = true; };
  }, [run.id]);

  const loadHistory = async (page: number) => {
    setHistoryBusy(true);
    try { const rows = await getJson<Row[]>(`/api/evaluations?page=${page}&limit=50`); setHistory(rows); setHistoryPage(page); }
    catch (reason) { setError(errorMessage(reason)); }
    finally { setHistoryBusy(false); }
  };

  const start = async () => {
    setBusy(true); setError("");
    try {
      await operation.startEvaluation("Baseline Evaluation", async () => { const started: Row = await postJson("/api/evaluations/run"); setRun(started); return started as { id: string }; });
    } catch (reason) { setError(errorMessage(reason)); }
    finally { setBusy(false); }
  };

  const result = run.result || {};
  const gates: Row[] = result.gates?.gates || [];
  const details: Row[] = run.gate_details || [];
  const relatedBad = badCases.filter(item => item.run_id === run.id);
  const cases: Row[] = run.cases || relatedBad.map(row=>({...row.result,question_id:row.question_id}));
  const snapshot = run.dataset_snapshot || (() => { try { return JSON.parse(run.dataset_snapshot_json || "{}"); } catch { return {}; } })();
  const profile = snapshot.profile || {};
  const categoryCounts = ["positive", "ablation", "negative"].map(key => profile[`${key}_count`] ?? profile[key] ?? (cases.length ? cases.filter(item => item.test_category === key).length : null));
  const config = run.config || {};
  const comparison = result.comparison_metrics || {};
  const failures = gates.filter(item => item.status === "FAIL");
  const visible = cases.filter(item => filter === "all" || filter === "bad" && item.passed===false || ["positive", "ablation", "negative"].includes(filter) && item.test_category === filter || filter === "retrieval" && item.programmatic_metrics?.retrieval_hit === false || filter === "generation" && item.primary_root_cause === "Generation" || filter === "safety" && item.primary_root_cause === "Safety");
  const badCount = result.bad_case_count ?? (cases.length && cases.every(item=>typeof item.passed==="boolean") ? cases.filter(item=>item.passed===false).length : relatedBad.length || null);
  const completed = run.status === "completed";
  const diagnosisRows = cases.length ? cases.filter(item => !item.passed) : relatedBad.map(item => item.result || item);
  const technicalCases = technicalDiagnosisRows(diagnosisRows);
  const technicalCollected=diagnosisRows.length ? diagnosisRows.every(item=>!!item.diagnostic_view) : completed && badCount===0;
  const technicalCountLabel=technicalCollected ? technicalCases.length : "未采集";
  const historicalPolicy=!!(run.requires_policy_upgrade ?? data.workspace?.requires_policy_upgrade);
  const stale = data.workspace?.requires_new_golden || data.workspace?.requires_new_baseline && (completed || data.workspace?.current_golden_id && snapshot.id !== data.workspace.current_golden_id);


  return <PageShell className="page evaluation-page" header={<div className="page-title"><div><h1>Baseline</h1><p>用冻结 Golden 评测当前版本，识别质量门槛、单题失败及可优化问题。</p></div><button className="secondary" disabled={busy || ["queued","running"].includes(run.status) || data.workspace?.requires_new_golden === true} onClick={() => setPaid({ title: ["partial","failed"].includes(run.status) ? "恢复 Baseline 断点评测" : "完整真实 Baseline 重评", description: ["partial","failed"].includes(run.status) ? `已完成 ${result.completed ?? cases.length}/${result.total ?? snapshot.question_ids?.length ?? "未采集"}；复用已完成结果与保存回答，仅处理缺失请求。每阶段最多3次尝试、600秒；Unknown请求停止，成功回答复用。` : `Golden ${snapshot.question_ids?.length ?? "未采集"} 题；每题生成回答及Judge，另含检索/改写调用。每阶段最多3次尝试、600秒，新评测保留历史结果。`, execute: () => void start() })}><Play size={15} />{run.status === "completed" ? "重新运行 Baseline" : ["queued","running"].includes(run.status) ? "后台评测进行中" : ["partial","failed"].includes(run.status) ? "恢复 Baseline" : "运行 Baseline 评测"}</button></div>} tabs={<div className="tabs"><button className={tab === "report" ? "active" : ""} aria-pressed={tab === "report"} onClick={() => setTab("report")}>Baseline 报告</button><button className={tab === "gates" ? "active" : ""} aria-pressed={tab === "gates"} onClick={() => setTab("gates")}>Hard Gate</button><button className={tab === "cases" ? "active" : ""} aria-pressed={tab === "cases"} onClick={() => setTab("cases")}>Bad Case 诊断</button></div>} resetKey={tab}>

    <ProviderAuthorization request={paid} onClose={() => setPaid(null)} />

    <Drawer className="workbench-drawer" open={historyOpen} onOpenChange={setHistoryOpen} title="历史评测 · 原记录只读"><div className="drawer-body"><div className="review-batch"><button disabled={historyBusy || historyPage===1} onClick={()=>void loadHistory(historyPage-1)}>上一页</button><span>第 {historyPage} 页 · 每页最多50条</span><button disabled={historyBusy || history.length<50} onClick={()=>void loadHistory(historyPage+1)}>下一页</button></div>{!history.length && <p>暂无历史评测记录。</p>}{history.map(row => <section key={row.id}><h3>{row.config?.run_target === 'answer_replay' ? '历史答案评分（非完整重评）' : row.config?.run_target === 'sandbox_candidate' ? '候选Sandbox' : '正式Baseline'}</h3><p>{localTime(row.created_at)} · {displayText(row.status || "未采集")} · {row.judge?.scoring_policy || '历史规则'} · Bad Case {row.result?.bad_case_count ?? '未采集'}</p><button className="text-button" onClick={() => { void getJson<Row>(`/api/evaluations/${row.id}`).then(value => { if (value.config?.run_target === 'answer_replay') { setReplay(value); setReplayOpen(true); } else { setRun(value); } setHistoryOpen(false); }).catch(reason => setError(errorMessage(reason))); }}>查看只读报告</button></section>)}</div></Drawer>
    {run.result?.auto_recovery?.authorized && !completed && <p className="workbench-status" role="status">{run.result.auto_recovery.state==='retrying'?`后台自动重试${run.result.auto_recovery.phase==='judge'?'Judge':'问答请求'} · 本题第${run.result.auto_recovery.retry_count}次恢复，已完成题目不会重复调用。`:run.result.auto_recovery.state==='stopped'?'后台已保存断点并停止：存在不可自动恢复的错误，详见评测依据。':'后台任务持续执行；刷新或关闭页面不停止Worker。'}</p>}
    {(error || run.error_message) && <p className="error-notice" role="alert">评测执行异常：{error || run.error_message}；未完成题目没有业务判定，不作为技术 Bad Case。</p>}
    {stale && run.id && <p className="error-notice">当前知识库状态已变化；以下是历史 Run，不能作为当前发布依据。</p>}
    {!run.id ? <Section title="尚未运行 Baseline"><p>正式评测需要已批准 Golden Snapshot 与可用 Provider。</p></Section> : <>

      {tab === "report" && <>
      <section className={`baseline-conclusion ${stale ? "warning" : result.gates?.passed === true ? "good" : "neutral"}`}>
        <h2>{historicalPolicy ? "历史Baseline · 旧规则成绩保留" : stale ? "历史评测 · 当前身份已失效" : completed ? result.gates?.passed === true ? "Baseline 群组Gate通过" : result.gates?.passed === false ? "Baseline 未通过 Hard Gate" : "评测已完成 · Gate 无法评估" : displayText(run.status || "not_run")}</h2>
        <p>{historicalPolicy ? `旧规则原始失败 ${badCount ?? "未采集"} 题；历史技术诊断仅供追溯，不作为新版 Agent 目标。新实验需先建立新版 Baseline。` : completed ? badCount == null ? "原始失败与技术诊断数量未采集，无法据此判断逐题质量。" : badCount > 0 ? `原始评测仍有 ${badCount} 个逐题失败，其中技术 Bad Case ${technicalCountLabel} 题。Overall 用于整体比较，Hard Gate 检查群组门槛；门槛通过仍可能存在单题缺陷。技术问题进入 Agent，其他异常保留质量审计。` : "当前逐题记录无 Bad Case；后续关注监控反馈。" : `已完成 ${result.completed ?? cases.length} / ${result.total ?? snapshot.question_ids?.length ?? "未采集"} 题；保留已完成结果及失败检查点。`}</p>
        {failures.length > 0 && <div className="failed-gate-grid">{failures.map(gate => <button className="text-button gate-failed" key={gate.metric} onClick={() => setSelectedGate(details.find(row => row.metric === gate.metric) || gate)}>{gateNames[gate.metric] || gate.metric} · {gateValue(gate)} / {gateThreshold(gate)} · 未通过</button>)}</div>}
      </section>
      <div className="baseline-metrics" aria-label="Baseline 核心结果">
        <div><span>Hard Gate</span><strong>{result.gates?.passed_count ?? "—"} / {result.gates?.total ?? (gates.length || "—")}</strong><small>群组质量门槛</small></div>
        <div><span>Overall</span><strong>{format(result.overall_score)}</strong><small>仅用于比较，不替代 Gate</small></div>
        <div><span>原始失败</span><strong>{completed ? badCount ?? "未采集" : "待完整评测"}</strong><small>保存的逐题失败数量</small></div><div><span>{historicalPolicy ? "历史技术诊断" : "技术 Bad Case"}</span><strong>{completed ? technicalCountLabel : "待完整评测"}</strong><small>{historicalPolicy ? "旧合同只读，不代表新版准入" : "有依据且具备合法优化方向"}</small></div>
      </div>

      </>}

      {tab === "report" && <div className="baseline-report">
        <Section title="评测信息">
          <dl className="report-grid baseline-run-summary">
            <div><dt>Golden</dt><dd>{profile.name || profile.profile || "冻结测试集"}{snapshot.question_ids?.length != null && ` · ${snapshot.question_ids.length} 题`}</dd></div>

            <div><dt>测试集构成</dt><dd>{["Positive", "Ablation", "Negative"].map((label, index) => categoryCounts[index] == null ? null : `${categoryCounts[index]} ${label}`).filter(Boolean).join(" · ") || "历史未保存构成"}</dd></div><div><dt>评测时间</dt><dd>{localTime(run.completed_at || run.created_at)}</dd></div>


            <div><dt>首字延迟 TTFT</dt><dd>{format(comparison.ttft_seconds ?? result.metrics?.ttft_seconds," s")}</dd></div><div><dt>身份状态</dt><dd>{stale ? "已失效 · 历史 Run" : "使用本次保存快照"}</dd></div>
          </dl>
        </Section>
    {run.id && <div className="review-batch"><span>{historicalPolicy ? "历史评测规则；新实验需先建立新版Baseline" : "正式Baseline与历史答案评分分开保存"}</span><button className="text-button" onClick={() => setPaid({ title: '历史答案重新评分', description: `复用 ${snapshot.question_ids?.length ?? '未采集'} 题已保存回答，仅调用新版Judge，不生成RAG回答；不成为正式Baseline或Sandbox。`, execute: () => { void operation.startEvaluation('历史答案评分（回放）', async () => { const result = await postJson<Row>(`/api/evaluations/${run.id}/replay`, { authorize_provider: true }); setReplay(result); return result as { id: string }; }).catch(reason => setError(errorMessage(reason))); } })}>评测规则升级验证</button><button className="text-button" onClick={() => { setHistoryOpen(true); void loadHistory(1); }}>历史评测</button>{replay && <button className="text-button" onClick={() => { void getJson<Row>(`/api/evaluations/${replay.id}`).then(value => { setReplay(value); setReplayOpen(true); }).catch(reason => setError(errorMessage(reason))); }}>查看独立回放进度：{replay.status}</button>}</div>}
        <div className="workbench-status"><button className="text-button" onClick={()=>setConfigOpen(true)}>完整配置快照</button><button className="text-button" onClick={()=>setTechnicalOpen(true)}>查看评测依据</button></div>

      </div>}
      {tab === "gates" && <><ConclusionCard title={result.gates?.passed === true ? "质量、安全与性能门槛已通过" : failures.length ? `${failures.length} 项门槛未达标，需先核对失败依据` : "门槛结果尚不完整"} tone={failures.length ? "warning" : "neutral"}>{result.gates?.passed_count ?? "未采集"} / {result.gates?.total ?? "未采集"} 项通过；质量、安全与性能分别依据下表保存的结果判断。Overall 不能抵消失败门槛，通过也不代表逐题无缺陷。</ConclusionCard><Section title={`${gates.length} 项 Hard Gate`}><p>{result.gates?.passed_count ?? "未采集"} / {gates.length || "未采集"} 通过 · {gates.length ? failures.length : "未采集"} 项未通过{run.judge?.scoring_policy && ` · 门槛版本 ${run.judge.scoring_policy}`}</p><div className="table-scroll baseline-table baseline-gates-table"><table><thead><tr><th>#</th><th>测试组</th><th>指标</th><th>实际</th><th>门槛</th><th>状态</th></tr></thead><tbody>{[...gates].sort((a,b)=>Number(b.status==="FAIL")-Number(a.status==="FAIL")).map((gate, index) => <tr className={gate.status === "FAIL" ? "gate-failed" : ""} key={gate.metric} tabIndex={0} onClick={() => setSelectedGate(details.find(row => row.metric === gate.metric) || gate)} onKeyDown={event => { if (event.key === "Enter") { event.preventDefault(); setSelectedGate(details.find(row => row.metric === gate.metric) || gate); } }}><td>{String(index + 1).padStart(2, "0")}</td><td>{group(gate.metric)}</td><td>{gateNames[gate.metric] || gate.metric}</td><td>{gateValue(gate)}</td><td>{gateThreshold(gate)}</td><td><span className={gate.status === "FAIL" ? "gate-failed" : "muted"}>{displayText(gate.status)}</span></td></tr>)}</tbody></table></div></Section></>}
      {tab === "cases" && <><ConclusionCard title={technicalCases.length ? `${technicalCases.length} 个技术问题有可验证优化方向` : "尚无具备完整依据的技术优化目标"} tone="neutral">原始失败 {badCount ?? "未采集"} 题；{[...new Set(technicalCases.map(item=>rootName(currentRoot(item))))].join("、") || "技术归属尚待核验"}。按失败现象定位问题，再核对根因与证据；评测异常单独审计。</ConclusionCard><Section title="技术 Bad Case 诊断"><p>原始失败 {badCount ?? "未采集"} 题 · 技术 Bad Case {technicalCountLabel} 题；原分数与判定保持。</p><p className="muted">{technicalCases.length ? [...new Set(technicalCases.map(item=>rootName(currentRoot(item))))].join("、")+"存在保存的故障依据；可查看证据及对应优化方向。" : "当前尚无具备完整故障依据和合法优化方向的技术目标。"}</p><DiagnosisFilters value={diagnosisFilter} onChange={setDiagnosisFilter} rows={technicalCases} /><DiagnosisTable rows={filterDiagnosis(technicalCases,diagnosisFilter)} onSelect={setSelectedCase} strategy={savedDirections} /><DetectionNotice rows={technicalCases} /></Section><div className="story-secondary"><StoryDisclosure label={<>评测核验与证据缺口（不作为技术优化目标）</>}><QualityAudit rows={diagnosisRows} onSelect={setSelectedCase} /></StoryDisclosure><StoryDisclosure label={<>全部原始逐题记录 · 只读</>}><div className="review-filters" aria-label="逐题筛选">{([["bad","原始失败"],["all","全部"],["positive","正向题"],["ablation","消融题"],["negative","负向题"],["retrieval","检索未命中"]] as [Filter,string][]).map(([key,label])=><button key={key} aria-pressed={filter===key} onClick={()=>setFilter(key)}>{label}</button>)}</div>{visible.map(item=><p key={item.question_id}><button className="text-button" onClick={()=>setSelectedCase(item)}>{item.question_id} · {item.passed===true?'原判定通过':item.passed===false?'原判定失败':'判定未采集'} · {item.question || '问题未采集'}</button></p>)}</StoryDisclosure></div></>}

    </>}
    <Drawer className="workbench-drawer" open={replayOpen} onOpenChange={setReplayOpen} title="历史答案重新评分 · 独立回放"><div className="drawer-body"><p>复用历史回答与上下文；不是正式Baseline、Sandbox或发布依据。</p><p>{replay?.id} · {replay?.status} · {replay?.judge?.scoring_policy}</p><p>{replay?.error_message || replay?.result?.error}</p>{replay?.cases?.map((item: Row) => <section key={item.question_id}><h3>{item.question_id}</h3><p>{item.result?.model_answer || item.model_answer}</p><p>{item.result?.judge_result?.reason || item.judge_result?.reason}</p><p>证据充分性：{item.result?.programmatic_metrics?.evidence_sufficiency?.status || item.programmatic_metrics?.evidence_sufficiency?.status || '未采集'}</p></section>)}</div></Drawer>
    <Drawer className="workbench-drawer" open={technicalOpen} onOpenChange={setTechnicalOpen} title="Baseline · 评测依据"><div className="drawer-body"><dl className="report-grid"><div><dt>Baseline 版本</dt><dd>{run.judge?.baseline_version || "未采集"}</dd></div><div><dt>Run ID</dt><dd><ShortId value={run.id} /></dd></div><div><dt>Golden Snapshot</dt><dd><ShortId value={run.dataset_version_id} /></dd></div><div><dt>测试集构成</dt><dd>{["Positive", "Ablation", "Negative"].map((label, index) => categoryCounts[index] == null ? null : `${categoryCounts[index]} ${label}`).filter(Boolean).join(" · ") || "历史未保存构成"}</dd></div><div><dt>评测时间</dt><dd>{localTime(run.created_at)}</dd></div><div><dt>Judge 模型</dt><dd>{run.judge?.model || "未采集"}</dd></div><div><dt>评测规则版本</dt><dd>{run.judge?.scoring_policy || "未采集"}</dd></div></dl>{run.result?.request_accounting && <section><h3>任务请求统计（含断点恢复谱系）</h3><p>调用事件：{run.result.request_accounting.call_events} · 已知Input Tokens：{run.result.request_accounting.known_input_tokens} · 已知Output Tokens：{run.result.request_accounting.known_output_tokens} · Usage未知：{run.result.request_accounting.unknown_usage_events}</p><p>未知部分不算0费用；统计不会因金额或Token预算阻断任务。</p><StoryDisclosure label={<>完整费用与请求统计</>}><pre className="technical-record">{JSON.stringify(run.result.request_accounting,null,2)}</pre></StoryDisclosure></section>}{run.result?.checkpoints && <StoryDisclosure label={<>失败断点与完整重试审计</>}><pre className="technical-record">{JSON.stringify({auto_recovery:run.result.auto_recovery,checkpoints:run.result.checkpoints},null,2)}</pre></StoryDisclosure>}<StoryDisclosure label={<>完整质量、检索与性能指标</>}><EvaluationDimensions result={result} /></StoryDisclosure><ExecutionMetrics metrics={cases.find(row => row.programmatic_metrics?.stages)?.programmatic_metrics || { input_tokens: comparison.input_tokens, output_tokens: comparison.output_tokens }} /></div></Drawer>
    <Drawer className="workbench-drawer" open={configOpen} onOpenChange={setConfigOpen} title="完整配置快照"><div className="drawer-body"><dl className="report-grid">{["candidate_k", "top_k", "min_score", "hybrid_search", "hybrid_alpha", "rerank", "query_rewrite", "multi_query", "hyde", "metadata_filter", "alias_mapping", "prompt_strategy"].map(key => <div key={key}><dt>{key}</dt><dd>{config[key] == null ? "未采集" : String(config[key])}</dd></div>)}{["embedding_model", "vector_index", "temperature"].map(key => <div key={key}><dt>{key}</dt><dd>{run.judge?.execution_snapshot?.[key] ?? "未采集"}</dd></div>)}</dl></div></Drawer>
    <Drawer className="workbench-drawer" open={!!selectedGate} onOpenChange={open => !open && setSelectedGate(null)} title={selectedGate ? gateNames[selectedGate.metric] || selectedGate.metric : "Gate 详情"}><div className="drawer-body">{selectedGate && <><p>{group(selectedGate.metric)} · {gateValue(selectedGate)} / {gateThreshold(selectedGate)} · <Status value={selectedGate.status} /></p><h3>业务影响</h3><p>{selectedGate.metric.startsWith("latency_") ? "响应体验是否达到既有性能门槛。" : selectedGate.metric.startsWith("positive_") || selectedGate.metric.startsWith("ablation_") ? "对应题组的正确性、依据和完整性门槛；通过不代表逐题无失败。" : "拒答、安全关键或注入防护是否达到既有安全门槛。"}</p><h3>评测版本与数据来源</h3><p>{run.judge?.scoring_policy || "历史规则未采集"} · 保存的逐题Judge与回答阶段观测</p><h3>指标定义与公式</h3><p>{selectedGate.formula || "历史记录未保存计算说明"}</p><p>纳入题数：{selectedGate.included_cases ?? "未记录"} · Judge：{run.judge?.model || "未采集"}</p><h3>贡献题目</h3><p className="muted">数值为本指标贡献；状态为题目整体判定。</p><div className="run-list">{(selectedGate.contributing_cases || []).map((item: Row) => <div key={item.question_id}><strong><TruncatedText lines={2}>{cases.find(row => row.question_id === item.question_id)?.question || "历史题目未记录"}</TruncatedText></strong><span>{format(item.value, selectedGate.metric.startsWith("latency_") ? " s" : "%")}</span><Status value={typeof item.passed === "boolean" ? item.passed ? "passed" : "failed" : "not_evaluable"} /><button className="text-button" disabled={!cases.some(row => row.question_id === item.question_id)} onClick={() => { setSelectedGate(null); setSelectedCase(cases.find(row => row.question_id === item.question_id) || null); }}>查看案例</button></div>)}</div><h3>关联 Baseline 配置</h3><p>CandidateK {config.candidate_k ?? "未采集"} · TopK {config.top_k ?? "未采集"}</p></>}</div></Drawer>
    <Drawer className="workbench-drawer" open={!!selectedCase} onOpenChange={open => !open && setSelectedCase(null)} title="案例诊断"><div className="drawer-body">{selectedCase && <BaselineCaseDetails item={{...selectedCase,optimization_strategy:(data.optimization?.candidates || []).filter((candidate:Row)=>(candidate.reasoning?.observed_evidence || candidate.reasoning?.target_bad_cases || []).some((id:string)=>id===selectedCase.question_id || relatedBad.some(row=>row.id===id && row.question_id===selectedCase.question_id))).map((candidate:Row)=>`${candidate.reasoning?.candidate_label || '未采集'}：${candidate.reasoning?.hypothesis || '假设未采集'}`).join('；')}} snapshot={snapshot} config={config} gates={details} />}</div></Drawer>
  </PageShell>;
}

const readableDiagnosis = (text?: string) => text && /[\u3400-\u9fff]/.test(text) && !/(?:failure_tags|claim_assessment|source_scope|DOC-\d+-C-|[a-z]+_[a-z]+[.])/i.test(text) ? text : '';

export function BaselineCaseDetails({ item, snapshot, config, gates }: { item: Row; snapshot: Row; config: Row; gates: Row[] }) {
  const golden = snapshot.questions?.find((row: Row) => row.id === item.question_id) || {};
  const evidence: Row[] = golden.evidence || golden.acceptable_evidence || [];
  const view = item.diagnostic_view || {};
  const category = view.analysis_category;
  const root = currentRoot(item);
  const business = item.evaluation_outcome?.contract_version === 'business-vnext-1' ? item.evaluation_outcome : null;
  const summary = (business ? item.judge_result?.reason : '') || readableDiagnosis(view.analysis_reason) || readableDiagnosis(item.diagnosis?.reason) || '已有记录尚不足以说明具体业务差异，请展开原始审计核验。';
  const conclusion = business ? business.execution_complete ? `业务${business.verdict}` : '评测执行未完成；业务结果未产生' : ({ rag_failure: '有依据的回答失败', evaluation_issue: '评测核验未闭合', insufficient_evidence: '证据不足，保留诊断任务' } as Record<string, string>)[category] || (item.passed ? '历史保存判定通过' : '历史保存判定未通过，具体原因以证据核验为准');
  const direction = ({ Retrieval: '围绕已定位的检索阶段提出假设，在允许的搜索空间内验证召回与上下文覆盖。', Generation: '围绕有据生成与产品配置适用范围提出假设，验证回答是否正确使用已有证据。', Safety: '围绕安全限制与拒答后的说明提出假设，验证安全边界和来源依据。', Performance: '围绕实测耗时所在环节提出假设，验证响应体验与质量影响。' } as Record<string, string>)[root];
  const behaviorNames: Record<string, string> = { safe_rejection: '应拒绝危险操作请求，并说明安全风险。', clarify: '缺失必要条件时，应请求澄清。', insufficient_evidence: '现有证据不足以完整回答时，应说明无法确定。', prompt_injection_resistance: '应抵抗提示注入，不泄露内部指令或伪造事实。' };
  const rawReference = item.reference_answer || golden.reference_answer || item.expected_behavior || golden.expected_behavior || item.raw?.expected_behavior || golden.raw?.expected_behavior;
  const expectedResponse = item.expected_response || item.raw?.expected_response || golden.expected_response || golden.raw?.expected_response;
  const reference = (behaviorNames[rawReference] ? expectedResponse || behaviorNames[rawReference] : rawReference || expectedResponse) || '历史未保存参考答案或预期行为';
  const metrics = item.programmatic_metrics || {};
  const finalRecords = metrics.retrieval_trace?.final ?? item.retrieved_chunks;
  const final: Row[] = Array.isArray(finalRecords) ? finalRecords : [];
  const sufficiency = metrics.evidence_sufficiency;
  const evidenceLabel = ({ sufficient: '证据充分', insufficient: '证据不足', unknown: '仍需核验', not_applicable: '负向材料锚点不作为答案证据' } as Record<string, string>)[sufficiency?.status] || '历史记录未采集充分性结论';
  const sourceLocation = (record: Row) => {
    const source = final.find(source => record.chunk_id && (source.chunk_id === record.chunk_id || source.parent_chunk_id === record.chunk_id) || record.document_id && source.document_id === record.document_id) || evidence.find(source => record.document_id && source.document_id === record.document_id || record.chunk_id && source.source_chunk_ids?.includes(record.chunk_id)) || {};
    const document = record.document || source.document;
    const start = record.page_start ?? source.page_start, end = record.page_end ?? source.page_end;
    return [document, start != null ? `第${start}${end != null && end !== start ? `—${end}` : ''}页` : ''].filter(Boolean).join(' · ');
  };
  return <div className="case-details bad-case-details">
    <section className="candidate-card"><h3>案例结论</h3><p><strong>{conclusion}</strong></p><p>失败现象：{symptoms(item).filter(label => !/[_]|[a-z]+[.]/i.test(label)).join('、') || '尚未定位'}</p><p>技术归属：{isTechnicalBadCase(item) ? rootName(root) : '质量审计，尚不构成技术优化目标'}</p><p>证据结论：{summary}</p><p className="muted">当前分析用于诊断；历史判定、分数及 Bad Case 数量保持原记录。</p></section>
    <section className="candidate-card"><h3>业务问题</h3><p className="muted">{displayText(item.test_category || golden.test_category || '')}{item.negative_subtype && ` · ${displayText(item.negative_subtype)}`}</p><CaseAnswer text={item.question || golden.question || '历史未保存问题原文'} />{golden.business_scenario && <p>业务场景：{golden.business_scenario}</p>}</section>
    <section className="candidate-card"><h3>预期与实际回答</h3><div className="case-answer-stack"><div><h4>参考答案 / 预期行为</h4><CaseAnswer text={reference} /></div><div><h4>RAG 实际回答</h4><CaseAnswer text={item.model_answer || '历史未保存回答'} /></div><div><h4>关键差异</h4><p>{summary}</p></div></div></section>
    <section className="candidate-card"><h3>证据依据</h3><h4>Golden 证据</h4>{item.test_category === 'negative' && <p className="muted">负向题的材料锚点用于来源追溯，不能单独视为答案证据。</p>}{evidence.length ? evidence.map((source, index) => <div className="evidence-block" key={index}><p>{source.evidence_key_points?.join('；') || '历史未保存关键事实摘要'}</p><p className="muted">{source.document || '来源文档名称未记录'}{source.page_start != null && ` · 第${source.page_start}${source.page_end && source.page_end !== source.page_start ? `—${source.page_end}` : ''}页`}</p></div>) : <p>历史 Snapshot 未保存证据摘要，原始记录见高级审计。</p>}<h4>召回证据与最终上下文</h4><p>候选召回 {metrics.retrieval_trace?.candidates?.length ?? '未采集'} 条 · 最终上下文 {Array.isArray(finalRecords) ? final.length : '未采集'} 条</p>{final.map((source, index) => <StoryDisclosure key={index} label={<>上下文 {index + 1} · {source.document || '来源名称未记录'}{source.page_start != null && ` · 第${source.page_start}页`}</>}><CaseAnswer text={source.content || source.chunk_text || source.text || source.content_preview || '历史未保存正文'} /></StoryDisclosure>)}<h4>关键事实支持</h4><p>{evidenceLabel}</p>{sufficiency?.judge_support?.map((fact: Row, index: number) => <div className="evidence-block" key={index}><p>{fact.fact}</p><blockquote>{fact.quote}</blockquote></div>)}</section>
    <section className="candidate-card"><h3>诊断与优化方向</h3><p>{summary}</p>{category === 'rag_failure' && (view.evidence_checks || []).map((check: Row, index: number) => <div className="evidence-block" key={index}>{check.fact && <><p>遗漏事实：</p><CaseAnswer text={check.fact} />{sourceLocation(check) && <p className="muted">{sourceLocation(check)}</p>}</>}{(check.answer_quotes || (check.claim || check.answer_quote ? [check.claim || check.answer_quote] : [])).map((quote: string, quoteIndex: number) => <div key={quoteIndex}><p>实际回答片段：</p><blockquote><CaseAnswer text={quote} /></blockquote></div>)}{(check.support || []).map((support: Row, supportIndex: number) => <div key={supportIndex}><p>原文依据{sourceLocation(support) && ` · ${sourceLocation(support)}`}：</p><blockquote><CaseAnswer text={support.quote || '历史未保存引文'} /></blockquote></div>)}</div>)}<p>{category === 'evaluation_issue' ? '保留未闭合主张或范围的质量审计；原失败与资格阻断保持，不形成 RAG 调参目标。' : isTechnicalBadCase(item) ? direction || '依据已定位的技术问题形成可验证假设，参数仍须搜索空间校验及 Sandbox 验证。' : '全部 Bad Case 均进入自动分析；证据不足时保留诊断任务，不生成无依据的正式优化目标。'}</p>{item.optimization_strategy && <p>已保存的优化假设：{item.optimization_strategy}</p>}<p className="muted">方向说明不代表已生成 Candidate，也不代表模型效果已经改善。</p></section>
    <StoryDisclosure className="candidate-card" label={<>高级技术审计</>}><h4>原始参考答案 / 预期行为</h4><pre className="technical-record">{rawReference || expectedResponse || '历史未保存参考答案或预期行为'}</pre><h4>原始模型回答</h4><pre className="technical-record">{item.model_answer || '历史未保存回答'}</pre><h4>Judge、Matcher、诊断及完整案例记录</h4><pre className="technical-record">{JSON.stringify({ case: item, golden, config, related_gates: gates.filter(gate => gate.contributing_cases?.some((row: Row) => row.question_id === item.question_id)) }, null, 2)}</pre><h4>召回与排名审计</h4><RetrievalEvidence storytelling metrics={metrics} /><h4>实测耗时与用量</h4><ExecutionMetrics metrics={metrics} /><p>Question ID：<ShortId value={item.question_id} /> · Golden Snapshot：<ShortId value={snapshot.id} /></p></StoryDisclosure>
  </div>;
}

export function CaseDetails(props: { item: Row; snapshot: Row; config: Row; gates: Row[] }) {
  return <BaselineCaseDetails {...props} />;
}

export function EvaluationDimensions({result}:{result:Row}) {
  const dimensions:[string,string[]][]=[['答案质量',['positive_correctness','positive_faithfulness','positive_completeness','ablation_correctness','ablation_faithfulness','ablation_completeness']],['检索效果',['recall_at_k','precision_at_k','mrr']],['安全鲁棒',['safe_rejection_rate','safety_critical_accuracy','prompt_injection_resistance']],['性能体验',['ttft_seconds','latency_p50_seconds','latency_p99_seconds']]];
  const names:Record<string,string>={...gateNames,recall_at_k:'Recall@K',precision_at_k:'Precision@K',mrr:'MRR',ttft_seconds:'TTFT'};
  return <Section title="四大评估维度"><div className="evaluation-dimensions">{dimensions.map(([title,keys])=><section key={title}><h3>{title}</h3><dl className="report-grid">{keys.map(key=>{
    const gate=result.gates?.gates?.find((item:Row)=>item.metric===key);
    const value=result.metrics?.[key] ?? result.comparison_metrics?.[key] ?? gate?.actual;
    const reason=result.metric_unavailable_reasons?.[key] || gate?.reason || '本次记录未保存该指标，不能按0计算';
    return <div key={key}><dt>{names[key]}</dt><dd>{typeof value==='number'?format(value,key.endsWith('_seconds')?' s':key==='mrr'?'':'%'):<><span>未采集</span><small>{reason}</small></>}</dd></div>;
  })}</dl></section>)}</div><p className="muted">仅读取本次持久化分数；11项Hard Gate及Overall判定保持独立。</p></Section>;
}
