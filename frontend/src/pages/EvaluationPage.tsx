import './evaluation-workspaces.css';
import {DiagnosisFilters, DiagnosisTable, DetectionNotice, allDiagnosis, filterDiagnosis, confidenceCounts, rootName, symptoms, coreEvidence} from '../components/EvaluationDiagnosis';
import { ProviderAuthorization, type PaidRequest } from "../components/ProviderAuthorization";
import { PageShell } from "../components/PageShell";
import { RetrievalEvidence } from "../components/RetrievalEvidence";
import { useEffect, useState } from "react";
import { Play } from "lucide-react";
import { errorMessage, getJson, postJson } from "../api";
import { Badge, Section, ShortId, Status, TruncatedText, TagList, StageStepper } from "../components/Primitives";
import { ExecutionMetrics, parameterNames } from "../components/PipelineFields";
import { Drawer } from "../components/Dialog";
import { displayText } from "../display";
import { useOperation } from "../operation";

type Row = Record<string, any>;
type Tab = "report" | "gates" | "cases";
type Filter = "bad" | "all" | "positive" | "ablation" | "negative" | "retrieval" | "generation" | "safety";

const gateNames: Record<string, string> = {
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
const confidenceLabel = (value?: string) => ({ confirmed: '已确认', disputed: '评测争议', needs_review: '待核实' }[value || 'needs_review'] || '待核实');
const causeName = (item: Row) => rootName(item.primary_root_cause || item.root_cause?.primary);
const secondarySignals = (item: Row) => [...new Set<string>([...(item.secondary_root_causes || item.root_cause?.secondary || []), ...(item.failure_tags || [])])];


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
  const visible = cases.filter(item => filter === "all" || filter === "bad" && !item.passed || ["positive", "ablation", "negative"].includes(filter) && item.test_category === filter || filter === "retrieval" && item.programmatic_metrics?.retrieval_hit === false || filter === "generation" && item.primary_root_cause === "Generation" || filter === "safety" && item.primary_root_cause === "Safety");
  const badCount = result.bad_case_count ?? (cases.length ? cases.filter(item => !item.passed).length : relatedBad.length);
  const completed = run.status === "completed";
  const confidenceRows = cases.length ? cases.filter(item => !item.passed) : relatedBad.map(item => item.result || item);
  const confidence = confidenceCounts(confidenceRows);
  const historicalPolicy=!!(run.requires_policy_upgrade ?? data.workspace?.requires_policy_upgrade);
  const stale = data.workspace?.requires_new_golden || data.workspace?.requires_new_baseline && (completed || data.workspace?.current_golden_id && snapshot.id !== data.workspace.current_golden_id);


  return <PageShell className="page evaluation-page" header={<div className="page-title"><div><h1>Baseline</h1><p>用冻结 Golden 评测当前版本，识别质量门槛、单题失败及可优化问题。</p></div><button className="secondary" disabled={busy || ["queued","running"].includes(run.status) || data.workspace?.requires_new_golden === true} onClick={() => setPaid({ title: ["partial","failed"].includes(run.status) ? "恢复 Baseline 断点评测" : "完整真实 Baseline 重评", description: ["partial","failed"].includes(run.status) ? `已完成 ${result.completed ?? cases.length}/${result.total ?? snapshot.question_ids?.length ?? "未采集"}；复用已完成结果与保存回答，仅处理缺失请求。一次启动覆盖后台自动恢复，费用仅统计；不可恢复错误保留断点并停止。` : `Golden ${snapshot.question_ids?.length ?? "未采集"} 题；每题生成回答及Judge，另含检索/改写调用。一次启动覆盖后台自动恢复，费用仅统计，新评测保留历史结果。`, execute: () => void start() })}><Play size={15} />{run.status === "completed" ? "重新运行 Baseline" : ["queued","running"].includes(run.status) ? "后台评测进行中" : ["partial","failed"].includes(run.status) ? "恢复 Baseline" : "运行 Baseline 评测"}</button></div>} tabs={<div className="tabs"><button className={tab === "report" ? "active" : ""} aria-pressed={tab === "report"} onClick={() => setTab("report")}>Baseline 报告</button><button className={tab === "gates" ? "active" : ""} aria-pressed={tab === "gates"} onClick={() => setTab("gates")}>Hard Gate</button><button className={tab === "cases" ? "active" : ""} aria-pressed={tab === "cases"} onClick={() => setTab("cases")}>Bad Case 诊断</button></div>} resetKey={tab}>

    <ProviderAuthorization request={paid} onClose={() => setPaid(null)} />
    {run.id && <div className="review-batch"><span>{historicalPolicy ? "历史评测规则；新实验需先建立新版Baseline" : "正式Baseline与历史答案评分分开保存"}</span><button className="text-button" onClick={() => setPaid({ title: '历史答案重新评分', description: `复用 ${snapshot.question_ids?.length ?? '未采集'} 题已保存回答，仅调用新版Judge，不生成RAG回答；不成为正式Baseline或Sandbox。`, execute: () => { void operation.startEvaluation('历史答案评分（回放）', async () => { const result = await postJson<Row>(`/api/evaluations/${run.id}/replay`, { authorize_provider: true }); setReplay(result); return result as { id: string }; }).catch(reason => setError(errorMessage(reason))); } })}>评测规则升级验证</button><button className="text-button" onClick={() => { setHistoryOpen(true); void loadHistory(1); }}>历史评测</button>{replay && <button className="text-button" onClick={() => { void getJson<Row>(`/api/evaluations/${replay.id}`).then(value => { setReplay(value); setReplayOpen(true); }).catch(reason => setError(errorMessage(reason))); }}>查看独立回放进度：{replay.status}</button>}</div>}
    <Drawer open={historyOpen} onOpenChange={setHistoryOpen} title="历史评测 · 原记录只读"><div className="drawer-body"><div className="review-batch"><button disabled={historyBusy || historyPage===1} onClick={()=>void loadHistory(historyPage-1)}>上一页</button><span>第 {historyPage} 页 · 每页最多50条</span><button disabled={historyBusy || history.length<50} onClick={()=>void loadHistory(historyPage+1)}>下一页</button></div>{!history.length && <p>暂无历史评测记录。</p>}{history.map(row => <section key={row.id}><h3>{row.config?.run_target === 'answer_replay' ? '历史答案评分（非完整重评）' : row.config?.run_target === 'sandbox_candidate' ? '候选Sandbox' : '正式Baseline'}</h3><p>{localTime(row.created_at)} · {row.status} · {row.judge?.scoring_policy || '历史规则'} · Bad Case {row.result?.bad_case_count ?? '未采集'}</p><button className="text-button" onClick={() => { void getJson<Row>(`/api/evaluations/${row.id}`).then(value => { if (value.config?.run_target === 'answer_replay') { setReplay(value); setReplayOpen(true); } else { setRun(value); } setHistoryOpen(false); }).catch(reason => setError(errorMessage(reason))); }}>查看只读报告</button></section>)}</div></Drawer>
    {run.result?.auto_recovery?.authorized && !completed && <p className="workbench-status" role="status">{run.result.auto_recovery.state==='retrying'?`后台自动重试${run.result.auto_recovery.phase==='judge'?'Judge':'问答请求'} · 本题第${run.result.auto_recovery.retry_count}次恢复，已完成题目不会重复调用。`:run.result.auto_recovery.state==='stopped'?'后台已保存断点并停止：存在不可自动恢复的错误，详见评测依据。':'后台任务持续执行；刷新或关闭页面不停止Worker。'}</p>}
    {(error || run.error_message) && <p className="error-notice" role="alert">{error || run.error_message}</p>}
    {stale && run.id && <p className="error-notice">当前知识库状态已变化；以下是历史 Run，不能作为当前发布依据。</p>}
    {!run.id ? <Section title="尚未运行 Baseline"><p>正式评测需要已批准 Golden Snapshot 与可用 Provider。</p></Section> : <>

      {tab === "report" && <>
      <StageStepper compact ariaLabel="Baseline 评测阶段" steps={[
        { label: "Golden 冻结", state: snapshot.id ? "completed" : "pending", detail: snapshot.id ? "本次冻结 Snapshot" : "等待冻结 Snapshot" },
        { label: "同一评测尺", state: run.judge?.scoring_policy ? "completed" : "pending", detail: run.judge?.scoring_policy || "历史未记录规则身份" },
        { label: "Baseline 评测", state: completed ? "completed" : run.status === "running" ? "current" : ["failed", "partial"].includes(run.status) ? "blocked" : "pending", detail: displayText(run.status || "not_run") },
        { label: "Gate / Bad Case", state: stale || result.gates?.passed === false ? "blocked" : completed && result.gates?.passed === true ? "completed" : "pending", detail: stale ? "历史身份已失效" : completed ? `${badCount} 个单题问题` : "等待评测结果" },
      ]} />
      <div className="baseline-metrics" aria-label="Baseline 核心结果">
        <div><span>Hard Gate</span><strong>{result.gates?.passed_count ?? "—"} / {result.gates?.total ?? (gates.length || "—")}</strong><small>群组质量门槛</small></div>
        <div><span>Overall</span><strong>{format(result.overall_score)}</strong><small>仅用于比较，不替代 Gate</small></div>
        <div><span>Bad Case</span><strong>{completed ? badCount : "—"}</strong><small>逐题失败数量</small></div>
        {[["已确认问题",confidence.confirmed],["待核实问题",confidence.needs_review],["评测争议",confidence.disputed]].map(([label,value])=><div key={label}><span>{label}</span><strong>{confidenceRows.length || badCount === 0 ? value : "未采集"}</strong><small>保存的诊断可信度</small></div>)}
      </div>
      <section className={`baseline-conclusion ${stale ? "warning" : result.gates?.passed === true ? "good" : "neutral"}`}>
        <h2>{historicalPolicy ? "历史Baseline · 旧规则成绩保留" : stale ? "历史评测 · 当前身份已失效" : completed ? result.gates?.passed === true ? "整体质量达标" : result.gates?.passed === false ? "Baseline 未通过 Hard Gate" : "评测已完成 · Gate 无法评估" : displayText(run.status || "not_run")}</h2>
        <p>{completed ? badCount > 0 ? `仍有 ${badCount} 个单题问题。Hard Gate 检查群组聚合门槛，Bad Case 检查逐题失败；可继续受控优化，原有质量与安全门槛保持。` : "当前逐题记录无 Bad Case；后续关注监控反馈。" : `已完成 ${result.completed ?? cases.length} / ${result.total ?? snapshot.question_ids?.length ?? "未采集"} 题；保留已完成结果及失败检查点。`}</p>
        {failures.length > 0 && <div className="failed-gate-grid">{failures.map(gate => <button className="text-button gate-failed" key={gate.metric} onClick={() => setSelectedGate(details.find(row => row.metric === gate.metric) || gate)}>{gateNames[gate.metric] || gate.metric} · {gateValue(gate)} / {gateThreshold(gate)} · FAIL</button>)}</div>}
      </section>
      </>}

      {tab === "report" && <div className="baseline-report">
        <Section title="下一步建议"><p>{historicalPolicy ? '旧规则成绩只读保留；需授权建立新版统一Baseline与新实验，不能直接运行旧B/C。' : !completed ? '先恢复完整评测；部分结果不建立Agent资格。' : confidence.confirmed > 0 ? '可根据已确认问题提出受控实验；争议和待核实先核对证据。' : badCount ? '先复核答案、来源和Judge；不将未知根因直接作为调参目标。' : '继续观察已有QA反馈。'}</p></Section>
        <Section title="运行摘要">
          <dl className="report-grid baseline-run-summary">
            <div><dt>Golden</dt><dd>{profile.name || profile.profile || "冻结测试集"}{snapshot.question_ids?.length != null && ` · ${snapshot.question_ids.length} 题`}</dd></div>

            <div><dt>评测时间</dt><dd>{localTime(run.completed_at || run.created_at)}</dd></div>


            <div><dt>身份状态</dt><dd>{stale ? "已失效 · 历史 Run" : "使用本次保存快照"}</dd></div>
          </dl>
        </Section>
        <div className="workbench-status"><button className="text-button" onClick={()=>setConfigOpen(true)}>完整配置快照</button><button className="text-button" onClick={()=>setTechnicalOpen(true)}>查看评测依据</button></div>
        <EvaluationDimensions result={result} /><Section title="测试集构成"><p className="golden-composition">{snapshot.question_ids?.length != null && `${snapshot.question_ids.length} 题 · `}{["Positive", "Ablation", "Negative"].map((label, index) => categoryCounts[index] == null ? null : `${categoryCounts[index]} ${label}`).filter(Boolean).join(" · ")}{snapshot.id && " · 已冻结"}</p></Section>
      </div>}
      {tab === "gates" && <Section title={`${gates.length} 项 Hard Gate`}><p>{result.gates?.passed_count ?? 0} / {gates.length} Passed · {failures.length} Failed{run.judge?.scoring_policy && ` · 门槛版本 ${run.judge.scoring_policy}`}</p><div className="table-scroll baseline-table baseline-gates-table"><table><thead><tr><th>#</th><th>测试组</th><th>指标</th><th>实际</th><th>门槛</th><th>状态</th></tr></thead><tbody>{gates.map((gate, index) => <tr className={gate.status === "FAIL" ? "gate-failed" : ""} key={gate.metric} tabIndex={0} onClick={() => setSelectedGate(details.find(row => row.metric === gate.metric) || gate)} onKeyDown={event => { if (event.key === "Enter") { event.preventDefault(); setSelectedGate(details.find(row => row.metric === gate.metric) || gate); } }}><td>{String(index + 1).padStart(2, "0")}</td><td>{group(gate.metric)}</td><td>{gateNames[gate.metric] || gate.metric}</td><td>{gateValue(gate)}</td><td>{gateThreshold(gate)}</td><td><Status value={gate.status} /></td></tr>)}</tbody></table></div></Section>}
      {tab === "cases" && <Section title="Bad Case 诊断"><DiagnosisFilters value={diagnosisFilter} onChange={setDiagnosisFilter} rows={cases.filter(item=>!item.passed)} /><details><summary>题型与召回筛选</summary><div className="review-filters" aria-label="逐题筛选">{([["bad","Bad Case"],["all","全部"],["positive","正向题"],["ablation","消融题"],["negative","负向题"],["retrieval","检索未命中"]] as [Filter,string][]).map(([key,label])=><button key={key} aria-pressed={filter===key} onClick={()=>setFilter(key)}>{label}</button>)}</div></details><DiagnosisTable rows={filterDiagnosis(visible,diagnosisFilter)} onSelect={setSelectedCase} /><DetectionNotice rows={cases.filter(item=>!item.passed)} /></Section>}
    </>}
    <Drawer open={replayOpen} onOpenChange={setReplayOpen} title="历史答案重新评分 · 独立回放"><div className="drawer-body"><p>复用历史回答与上下文；不是正式Baseline、Sandbox或发布依据。</p><p>{replay?.id} · {replay?.status} · {replay?.judge?.scoring_policy}</p><p>{replay?.error_message || replay?.result?.error}</p>{replay?.cases?.map((item: Row) => <section key={item.question_id}><h3>{item.question_id}</h3><p>{item.result?.model_answer || item.model_answer}</p><p>{item.result?.judge_result?.reason || item.judge_result?.reason}</p><p>证据充分性：{item.result?.programmatic_metrics?.evidence_sufficiency?.status || item.programmatic_metrics?.evidence_sufficiency?.status || '未采集'}</p></section>)}</div></Drawer>
    <Drawer open={technicalOpen} onOpenChange={setTechnicalOpen} title="Baseline · 评测依据"><div className="drawer-body"><dl className="report-grid"><div><dt>Baseline 版本</dt><dd>{run.judge?.baseline_version || "未采集"}</dd></div><div><dt>Run ID</dt><dd><ShortId value={run.id} /></dd></div><div><dt>Golden Snapshot</dt><dd><ShortId value={run.dataset_version_id} /></dd></div><div><dt>评测时间</dt><dd>{localTime(run.created_at)}</dd></div><div><dt>Judge 模型</dt><dd>{run.judge?.model || "未采集"}</dd></div><div><dt>评测规则版本</dt><dd>{run.judge?.scoring_policy || "未采集"}</dd></div></dl>{run.result?.request_accounting && <section><h3>任务请求统计（含断点恢复谱系）</h3><p>调用事件：{run.result.request_accounting.call_events} · 已知Input Tokens：{run.result.request_accounting.known_input_tokens} · 已知Output Tokens：{run.result.request_accounting.known_output_tokens} · Usage未知：{run.result.request_accounting.unknown_usage_events}</p><p>未知部分不算0费用；统计不会因金额或Token预算阻断任务。</p><details><summary>完整费用与请求统计</summary><pre className="technical-record">{JSON.stringify(run.result.request_accounting,null,2)}</pre></details></section>}{run.result?.checkpoints && <details><summary>失败断点与完整重试审计</summary><pre className="technical-record">{JSON.stringify({auto_recovery:run.result.auto_recovery,checkpoints:run.result.checkpoints},null,2)}</pre></details>}<ExecutionMetrics metrics={cases.find(row => row.programmatic_metrics?.stages)?.programmatic_metrics || { input_tokens: comparison.input_tokens, output_tokens: comparison.output_tokens }} /></div></Drawer>
    <Drawer open={configOpen} onOpenChange={setConfigOpen} title="完整配置快照"><div className="drawer-body"><dl className="report-grid">{["candidate_k", "top_k", "min_score", "hybrid_search", "hybrid_alpha", "rerank", "query_rewrite", "multi_query", "hyde", "metadata_filter", "alias_mapping", "prompt_strategy"].map(key => <div key={key}><dt>{key}</dt><dd>{config[key] == null ? "未采集" : String(config[key])}</dd></div>)}{["embedding_model", "vector_index", "temperature"].map(key => <div key={key}><dt>{key}</dt><dd>{run.judge?.execution_snapshot?.[key] ?? "未采集"}</dd></div>)}</dl></div></Drawer>
    <Drawer open={!!selectedGate} onOpenChange={open => !open && setSelectedGate(null)} title={selectedGate ? gateNames[selectedGate.metric] || selectedGate.metric : "Gate 详情"}><div className="drawer-body">{selectedGate && <><p>{group(selectedGate.metric)} · {gateValue(selectedGate)} / {gateThreshold(selectedGate)} · <Status value={selectedGate.status} /></p><h3>业务影响</h3><p>{selectedGate.metric.startsWith("latency_") ? "响应体验是否达到既有性能门槛。" : selectedGate.metric.startsWith("positive_") || selectedGate.metric.startsWith("ablation_") ? "对应题组的正确性、依据和完整性门槛；通过不代表逐题无失败。" : "拒答、安全关键或注入防护是否达到既有安全门槛。"}</p><h3>评测版本与数据来源</h3><p>{run.judge?.scoring_policy || "历史规则未采集"} · 保存的逐题Judge与回答阶段观测</p><h3>指标定义与公式</h3><p>{selectedGate.formula || "历史记录未保存计算说明"}</p><p>纳入题数：{selectedGate.included_cases ?? "未记录"} · Judge：{run.judge?.model || "未采集"}</p><h3>贡献题目</h3><p className="muted">数值为本指标贡献；状态为题目整体判定。</p><div className="run-list">{(selectedGate.contributing_cases || []).map((item: Row) => <div key={item.question_id}><strong><TruncatedText lines={2}>{cases.find(row => row.question_id === item.question_id)?.question || "历史题目未记录"}</TruncatedText></strong><span>{format(item.value, selectedGate.metric.startsWith("latency_") ? " s" : "%")}</span><Status value={typeof item.passed === "boolean" ? item.passed ? "passed" : "failed" : "not_evaluable"} /><button className="text-button" disabled={!cases.some(row => row.question_id === item.question_id)} onClick={() => { setSelectedGate(null); setSelectedCase(cases.find(row => row.question_id === item.question_id) || null); }}>查看案例</button></div>)}</div><h3>关联 Baseline 配置</h3><p>CandidateK {config.candidate_k ?? "未采集"} · TopK {config.top_k ?? "未采集"}</p></>}</div></Drawer>
    <Drawer open={!!selectedCase} onOpenChange={open => !open && setSelectedCase(null)} title="案例诊断"><div className="drawer-body">{selectedCase && <CaseDetails item={{...selectedCase,optimization_strategy:(data.optimization?.candidates || []).filter((candidate:Row)=>(candidate.reasoning?.observed_evidence || candidate.reasoning?.target_bad_cases || []).some((id:string)=>id===selectedCase.question_id || relatedBad.some(row=>row.id===id && row.question_id===selectedCase.question_id))).map((candidate:Row)=>`${candidate.reasoning?.candidate_label || '未采集'}：${candidate.reasoning?.hypothesis || '假设未采集'}`).join('；')}} snapshot={snapshot} config={config} gates={details} />}</div></Drawer>
  </PageShell>;
}

export function CaseDetails({ item, snapshot, config, gates }: { item: Row; snapshot: Row; config: Row; gates: Row[] }) {
  const golden = snapshot.questions?.find((row: Row) => row.id === item.question_id) || {};
  const evidence: Row[] = golden.evidence || golden.acceptable_evidence || [];
  const related = gates.filter(gate => gate.status === "FAIL" && gate.contributing_cases?.some((row: Row) => row.question_id === item.question_id));
  const signals = secondarySignals(item);
  const sufficiency = item.programmatic_metrics?.evidence_sufficiency;
  const confidence = item.diagnosis?.status === 'confirmed' ? '已确认问题' : item.diagnosis?.status === 'disputed' ? '评测依据存在争议' : '需要进一步核实';
  return <div className="case-details">
    <section><h3>案例结论</h3><p>失败现象：{symptoms(item).join('、') || '未采集 · 待核实'}</p><p>{item.passed ? '保存判定通过' : '保存判定未通过'} · {confidence}</p><p>{item.diagnosis?.reason || '历史规则未采集新版证据充分性；失败标签不等于确认根因。'}</p></section>
    <section><h3>问题</h3><p><ShortId value={item.question_id} /> · {displayText(item.test_category || "")}{item.negative_subtype && ` · ${displayText(item.negative_subtype)}`}</p><p>{item.question}</p></section>
    <section><h3>预期与实际回答</h3><div className="baseline-answer-comparison"><div><h4>参考答案 / Expected Behavior</h4><p>{item.reference_answer || golden.reference_answer || golden.expected_behavior || "历史未保存参考答案"}</p></div><div><h4>Model Answer</h4><p>{item.model_answer || "历史未保存回答"}</p></div></div></section>
    <section><h3>Golden Evidence</h3>{item.test_category === "negative" && <p>Negative 的材料 Anchor 不代表答案 Evidence；这里只保留来源追溯，拒答与澄清仍按保存的预期行为判断。</p>}{evidence.length ? evidence.map((row, index) => <div key={index} className="evidence-block"><p>支撑证据：{row.evidence_key_points?.join("；") || "未记录"}</p><p>{row.document || row.document_id || "来源文档未记录"}{row.page_start != null && ` · P.${row.page_start}`}</p><p>来源 Chunk：{row.source_chunk_ids?.map((id: string) => <ShortId key={id} value={id} />)}</p></div>) : <p>历史 Snapshot 未保存 Golden Evidence。</p>}</section>
    <section><h3>Retrieved Evidence</h3><p>{["candidate_k", "top_k"].filter(key => config[key] != null).map(key => `${parameterNames[key]} ${config[key]}`).join(" · ")}</p>{Array.isArray(item.programmatic_metrics?.retrieval_trace?.final) && <div className="run-list">{item.programmatic_metrics.retrieval_trace.final.map((row: Row, index: number) => <details key={`${row.chunk_id}-${index}`}><summary>最终上下文 {index + 1} · {row.document || row.document_id || '来源未采集'} · P.{row.page_start ?? '未采集'}</summary><p>{row.content || row.chunk_text || row.text || '原文未采集'}</p></details>)}</div>}<details><summary>候选召回、Child命中与排名审计</summary><RetrievalEvidence metrics={item.programmatic_metrics} /></details>{item.retrieved_chunks?.length > 0 && !Array.isArray(item.programmatic_metrics?.retrieval_trace?.final) && <><h4>历史保存的回答上下文</h4><div className="run-list">{item.retrieved_chunks.map((row: Row, index: number) => <div key={`${row.chunk_id}-${index}`}><strong>{index + 1} · {row.document || row.chunk_id}</strong><p>{row.chunk_text || row.text || row.content || row.content_preview || "历史未保存证据原文"}</p><ShortId value={row.chunk_id} /></div>)}</div></>}</section>

    <section><h3>Evidence Matcher · 最终答案证据</h3><p>{sufficiency ? ({ sufficient: '证据充分', insufficient: '证据不足', unknown: '待核实', not_applicable: '负向Anchor不作答案证据' } as Record<string, string>)[sufficiency.status] || '待核实' : '历史规则 / 未采集'}</p><p>{sufficiency?.reason}</p>{sufficiency?.judge_support?.map((fact: Row, i: number) => <div className="evidence-block" key={i}><strong>{fact.fact}</strong><p>{fact.quote}</p><small>来源定位：{fact.chunk_id}</small></div>)}</section>
    <section><h3>Judge</h3><dl className="report-grid">{["correctness", "faithfulness", "completeness", "behavior_pass"].filter(key => item.judge_result?.[key] != null).map(key => <div key={key}><dt>{key}</dt><dd>{String(item.judge_result[key])}</dd></div>)}</dl><p>{item.judge_result?.reason || "历史未保存 Judge 依据"}</p></section>
    <section><h3>分类与可验证优化方向</h3><p>核心证据：{coreEvidence(item)}</p><p>失败现象：{symptoms(item).join('、') || '未采集'}</p><p>主要技术根因：{causeName(item)} · 可信度：{confidence}</p><p>次要技术原因：{(item.secondary_root_causes || item.root_cause?.secondary || []).map(rootName).join('、') || '未采集'}</p>{item.diagnostic_view?.phenomena?.map((p:Row)=><p key={p.name}>{p.name} · 依据：{(p.basis || []).join('；')}</p>)}<p>{item.diagnostic_view?.target_eligible ? '根因已有保存依据；可查看关联Candidate的实际策略，参数仍需Search Space与Sandbox验证。' : '先核验原始证据，不将待核实或争议直接作为调参目标。'}</p>{item.optimization_strategy && <p>保存的优化策略：{item.optimization_strategy}</p>}<details><summary>问答阶段耗时与Judge耗时</summary><ExecutionMetrics metrics={item.programmatic_metrics || {}} />{item.diagnostic_view?.latency?.bottleneck && <p>实测最长独立问答环节：{item.diagnostic_view.latency.bottleneck.stage_name} · {item.diagnostic_view.latency.bottleneck.duration_ms} ms（非根因结论）</p>}</details></section><section><h3>初步诊断</h3><p>保存的初步类型：<Badge tone="neutral">{displayText(causeName(item))}</Badge></p><p>证据观察：{item.programmatic_metrics?.evidence_coverage?.diagnostic_basis || "未采集"}</p><p className="muted">初步类型保留历史归类，不等于已确认根因；证据观察单独展示。</p></section>
    <details><summary>高级技术审计</summary><pre className="technical-record">{JSON.stringify({diagnostic_view:item.diagnostic_view,diagnosis:item.diagnosis,judge:item.judge_result,matcher:item.programmatic_metrics?.claim_assessment},null,2)}</pre><section><h3>失败标签与细分信号</h3><TagList tags={signals} />{!signals.length && <p>没有保存的 Secondary Signals。</p>}</section>
    <section><h3>关联 Gate</h3><p>{related.map(gate => gateNames[gate.metric] || gate.metric).join("、") || "无关联失败 Gate"}</p></section>
    <section><h3>身份与审计</h3><p>Question ID：<ShortId value={item.question_id} /></p><p>Golden Snapshot：<ShortId value={snapshot.id} /></p></section></details>
  </div>;
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
