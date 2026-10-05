import { PageShell } from "../components/PageShell";
import { RetrievalEvidence } from "../components/RetrievalEvidence";
import { useEffect, useState } from "react";
import { Play } from "lucide-react";
import { errorMessage, getJson, postJson } from "../api";
import { Badge, Section, ShortId, Status, TruncatedText, TagList } from "../components/Primitives";
import { ExecutionMetrics, parameterNames, formatValue } from "../components/PipelineFields";
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
const causeName = (item: Row) => item.primary_root_cause || item.root_cause?.primary || "未记录";
const secondarySignals = (item: Row) => [...new Set<string>([...(item.secondary_root_causes || item.root_cause?.secondary || []), ...(item.failure_tags || [])])];

export function EvaluationPage({ data }: { data: any; navigate?: (page: any) => void }) {
  const operation = useOperation();
  const [tab, setTab] = useState<Tab>("report");
  const [filter, setFilter] = useState<Filter>("bad");
  const [run, setRun] = useState<Row>(data.evaluation || {});
  const [badCases, setBadCases] = useState<Row[]>(data.badCases || []);
  const [selectedGate, setSelectedGate] = useState<Row | null>(null);
  const [selectedCase, setSelectedCase] = useState<Row | null>(null);
  const [configOpen, setConfigOpen] = useState(false);
  const [technicalOpen, setTechnicalOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!run.id) return;
    let cancelled = false, attempts = 0;
    const poll = async () => {
      try {
        const next = await getJson<Row>(`/api/evaluations/${run.id}`);
        if (cancelled) return;
        setRun(next);
        if (next.status === "running" && attempts++ < 300) window.setTimeout(poll, 1000);
        if (next.status !== "running") { const rows = await getJson<Row[]>("/api/bad-cases"); if (!cancelled) setBadCases(rows); }
      } catch (reason) { if (!cancelled) setError(errorMessage(reason)); }
    };
    void poll();
    return () => { cancelled = true; };
  }, [run.id]);

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
  const cases: Row[] = run.cases || [];
  const relatedBad = badCases.filter(item => item.run_id === run.id);
  const snapshot = run.dataset_snapshot || (() => { try { return JSON.parse(run.dataset_snapshot_json || "{}"); } catch { return {}; } })();
  const profile = snapshot.profile || {};
  const categoryCounts = ["positive", "ablation", "negative"].map(key => profile[`${key}_count`] ?? profile[key] ?? (cases.length ? cases.filter(item => item.test_category === key).length : null));
  const config = run.config || {};
  const comparison = result.comparison_metrics || {};
  const failures = gates.filter(item => item.status === "FAIL");
  const visible = cases.filter(item => filter === "all" || filter === "bad" && !item.passed || ["positive", "ablation", "negative"].includes(filter) && item.test_category === filter || filter === "retrieval" && item.programmatic_metrics?.retrieval_hit === false || filter === "generation" && item.primary_root_cause === "Generation" || filter === "safety" && item.primary_root_cause === "Safety");
  const stale = data.workspace?.requires_new_golden || data.workspace?.requires_new_baseline;
  const generationModel = run.judge?.execution_snapshot?.generation_model;
  const collectedMetrics = [["Recall@K", comparison.recall_at_k, "%"], ["Precision@K", comparison.precision_at_k, "%"], ["MRR", comparison.mrr, ""], ["TTFT", comparison.ttft_seconds, " s"], ["Latency P50", result.metrics?.latency_p50_seconds, " s"], ["Latency P99", result.metrics?.latency_p99_seconds, " s"]].filter(([, value]) => typeof value === "number");
  const configGroups = [["Query", ["query_rewrite", "multi_query", "hyde", "alias_mapping"]], ["Retrieval", ["candidate_k", "top_k", "min_score", "hybrid_search", "hybrid_alpha", "metadata_filter"]], ["Rerank / Context", ["rerank"]], ["Generation", ["prompt_strategy"]]] as [string, string[]][];

  return <PageShell className="page evaluation-page" header={<div className="page-title"><div><h1>Baseline</h1><p>用冻结 Golden 评测当前 Baseline，并定位失败 Gate 与 Bad Case。</p></div><button className="secondary" disabled={busy || run.status === "running" || data.workspace?.requires_new_golden === true} onClick={() => void start()}><Play size={15} />{run.status === "completed" ? "重新运行 Baseline" : run.status === "running" ? "评测进行中" : "运行 Baseline 评测"}</button></div>} tabs={<div className="tabs"><button className={tab === "report" ? "active" : ""} aria-pressed={tab === "report"} onClick={() => setTab("report")}>Baseline 报告</button><button className={tab === "gates" ? "active" : ""} aria-pressed={tab === "gates"} onClick={() => setTab("gates")}>Hard Gate</button><button className={tab === "cases" ? "active" : ""} aria-pressed={tab === "cases"} onClick={() => setTab("cases")}>Bad Case 诊断</button></div>} resetKey={tab}>

    {error && <p className="error-notice" role="alert">{error}</p>}
    {stale && run.id && <p className="error-notice">当前知识库状态已变化；以下是历史 Run，不能作为当前发布依据。</p>}
    {!run.id ? <Section title="尚未运行 Baseline"><p>正式评测需要已批准 Golden Snapshot 与可用 Provider。</p></Section> : <>

      {tab === "report" && <div className="baseline-report">
        <Section title="评测结果" action={<button className="text-button" onClick={() => setTab("gates")}>查看 Hard Gate</button>}>
          <div className="report-decision"><h3>{run.status === "completed" ? result.gates?.passed === true ? "Baseline 通过 Hard Gate" : result.gates?.passed === false ? "Baseline 未通过 Hard Gate" : "Baseline 已完成评测" : displayText(run.status || "not_run")}</h3><p>{gates.length > 0 && `${result.gates?.passed_count} / ${result.gates?.total ?? gates.length} Hard Gate · `}{run.status === "completed" && `${result.bad_case_count ?? relatedBad.length} 个 Bad Case`}</p></div>
          {failures.length > 0 && <div className="failed-gate-grid">{failures.map(gate => <button className="text-button gate-failed" key={gate.metric} onClick={() => setSelectedGate(details.find(row => row.metric === gate.metric) || gate)}>{gateNames[gate.metric] || gate.metric} · {gateValue(gate)} / {gateThreshold(gate)} · FAIL</button>)}</div>}
          <p className="muted">{["candidate_k", "top_k", "prompt_strategy"].filter(key => config[key] != null).map(key => `${parameterNames[key]} ${formatValue(config[key])}`).join(" · ")}</p>
          <button className="text-button" onClick={() => setTab("cases")}>查看 Bad Case</button>
        </Section>
        <Section title="配置摘要" action={<button className="text-button" onClick={() => setConfigOpen(true)}>查看完整配置</button>}><div className="config-summary-grid">{configGroups.map(([name, keys]) => <div key={name}><h3>{name}</h3><dl>{keys.filter(key => config[key] != null).map(key => <div key={key}><dt>{parameterNames[key]}</dt><dd>{formatValue(config[key])}</dd></div>)}{name === "Generation" && generationModel && <div><dt>Generation Model</dt><dd>{generationModel}</dd></div>}</dl></div>)}</div></Section>
        <Section title="测试集与性能"><p className="golden-composition">{snapshot.question_ids?.length != null && `${snapshot.question_ids.length} 题 · `}{["Positive", "Ablation", "Negative"].map((label, index) => categoryCounts[index] == null ? null : `${categoryCounts[index]} ${label}`).filter(Boolean).join(" · ")}{snapshot.id && " · 已冻结"}</p>{collectedMetrics.length > 0 && <dl className="report-grid">{collectedMetrics.map(([label, value, suffix]) => <div key={String(label)}><dt>{String(label)}</dt><dd>{format(value, String(suffix))}</dd></div>)}</dl>}<button className="text-button" onClick={() => setTechnicalOpen(true)}>查看评测依据</button></Section>
      </div>}
      {tab === "gates" && <Section title={`${gates.length} 项 Hard Gate`}><p>{result.gates?.passed_count ?? 0} / {gates.length} Passed · {failures.length} Failed{run.judge?.scoring_policy && ` · 门槛版本 ${run.judge.scoring_policy}`}</p><div className="table-scroll baseline-table"><table><thead><tr><th>#</th><th>测试组</th><th>指标</th><th>实际</th><th>门槛</th><th>状态</th></tr></thead><tbody>{gates.map((gate, index) => <tr className={gate.status === "FAIL" ? "gate-failed" : ""} key={gate.metric} tabIndex={0} onClick={() => setSelectedGate(details.find(row => row.metric === gate.metric) || gate)} onKeyDown={event => { if (event.key === "Enter") { event.preventDefault(); setSelectedGate(details.find(row => row.metric === gate.metric) || gate); } }}><td>{String(index + 1).padStart(2, "0")}</td><td>{group(gate.metric)}</td><td>{gateNames[gate.metric] || gate.metric}</td><td>{gateValue(gate)}</td><td>{gateThreshold(gate)}</td><td><Status value={gate.status} /></td></tr>)}</tbody></table></div></Section>}
      {tab === "cases" && <Section title="Bad Case 诊断"><div className="review-filters" aria-label="逐题筛选">{([ ["bad", "Bad Case"], ["all", "全部"], ["positive", "正向题"], ["ablation", "消融题"], ["negative", "负向题"], ["retrieval", "检索未命中"], ["generation", "生成"], ["safety", "安全"] ] as [Filter, string][]).map(([key, label]) => <button key={key} aria-pressed={filter === key} className={filter === key ? "active" : ""} onClick={() => setFilter(key)}>{label}</button>)}</div><div className="table-scroll baseline-table"><table><thead><tr><th>题目</th><th>问题</th><th>Primary Root Cause</th><th>主要失败指标</th><th>Secondary Signals / Evidence</th><th>操作</th></tr></thead><tbody>{visible.map(item => { const related = details.filter(gate => gate.status === "FAIL" && gate.contributing_cases?.some((row: Row) => row.question_id === item.question_id)).map(gate => gateNames[gate.metric] || gate.metric); const tags = secondarySignals(item); return <tr key={item.question_id} tabIndex={0} onClick={() => setSelectedCase(item)} onKeyDown={event => { if (event.key === "Enter") { event.preventDefault(); setSelectedCase(item); } }}><td><ShortId value={item.question_id} /></td><td className="case-question"><TruncatedText lines={2}>{item.question}</TruncatedText></td><td><Badge tone="neutral">{displayText(causeName(item))}</Badge></td><td><TruncatedText lines={2}>{related.join("、") || tags.join("、") || "Unknown"}</TruncatedText></td><td><TagList tags={tags} />{!tags.length && item.programmatic_metrics?.retrieval_hit === false && "检索未命中"}</td><td><button className="text-button" onClick={event => { event.stopPropagation(); setSelectedCase(item); }}>查看案例</button></td></tr>; })}{!visible.length && <tr><td colSpan={6}>当前筛选无记录。</td></tr>}</tbody></table></div></Section>}
    </>}
    <Drawer open={technicalOpen} onOpenChange={setTechnicalOpen} title="Baseline · 评测依据"><div className="drawer-body"><dl className="report-grid"><div><dt>Baseline 版本</dt><dd>{run.judge?.baseline_version || "未采集"}</dd></div><div><dt>Run ID</dt><dd><ShortId value={run.id} /></dd></div><div><dt>Golden Snapshot</dt><dd><ShortId value={run.dataset_version_id} /></dd></div><div><dt>评测时间</dt><dd>{localTime(run.created_at)}</dd></div><div><dt>Judge 模型</dt><dd>{run.judge?.model || "未采集"}</dd></div><div><dt>评测规则版本</dt><dd>{run.judge?.scoring_policy || "未采集"}</dd></div></dl><ExecutionMetrics metrics={cases.find(row => row.programmatic_metrics?.stages)?.programmatic_metrics || { input_tokens: comparison.input_tokens, output_tokens: comparison.output_tokens }} /></div></Drawer>
    <Drawer open={configOpen} onOpenChange={setConfigOpen} title="完整配置快照"><div className="drawer-body"><dl className="report-grid">{["candidate_k", "top_k", "min_score", "hybrid_search", "hybrid_alpha", "rerank", "query_rewrite", "multi_query", "hyde", "metadata_filter", "alias_mapping", "prompt_strategy"].map(key => <div key={key}><dt>{key}</dt><dd>{config[key] == null ? "未采集" : String(config[key])}</dd></div>)}{["embedding_model", "vector_index", "temperature"].map(key => <div key={key}><dt>{key}</dt><dd>{run.judge?.execution_snapshot?.[key] ?? "未采集"}</dd></div>)}</dl></div></Drawer>
    <Drawer open={!!selectedGate} onOpenChange={open => !open && setSelectedGate(null)} title={selectedGate ? gateNames[selectedGate.metric] || selectedGate.metric : "Gate 详情"}><div className="drawer-body">{selectedGate && <><p>{group(selectedGate.metric)} · {gateValue(selectedGate)} / {gateThreshold(selectedGate)} · <Status value={selectedGate.status} /></p><h3>指标定义与公式</h3><p>{selectedGate.formula || "历史记录未保存计算说明"}</p><p>纳入题数：{selectedGate.included_cases ?? "未记录"} · Judge：{run.judge?.model || "未采集"}</p><h3>贡献题目</h3><p className="muted">数值为本指标贡献；状态为题目整体判定。</p><div className="run-list">{(selectedGate.contributing_cases || []).map((item: Row) => <div key={item.question_id}><strong><TruncatedText lines={2}>{cases.find(row => row.question_id === item.question_id)?.question || "历史题目未记录"}</TruncatedText></strong><span>{format(item.value, selectedGate.metric.startsWith("latency_") ? " s" : "%")}</span><Status value={item.passed ? "passed" : "failed"} /></div>)}</div><h3>关联 Baseline 配置</h3><p>CandidateK {config.candidate_k ?? "未采集"} · TopK {config.top_k ?? "未采集"}</p></>}</div></Drawer>
    <Drawer open={!!selectedCase} onOpenChange={open => !open && setSelectedCase(null)} title="案例诊断"><div className="drawer-body">{selectedCase && <CaseDetails item={selectedCase} snapshot={snapshot} config={config} gates={details} />}</div></Drawer>
  </PageShell>;
}

export function CaseDetails({ item, snapshot, config, gates }: { item: Row; snapshot: Row; config: Row; gates: Row[] }) {
  const golden = snapshot.questions?.find((row: Row) => row.id === item.question_id) || {};
  const evidence: Row[] = golden.acceptable_evidence || [];
  const related = gates.filter(gate => gate.status === "FAIL" && gate.contributing_cases?.some((row: Row) => row.question_id === item.question_id));
  const signals = secondarySignals(item);
  return <div className="case-details">
    <section><h3>问题</h3><p><ShortId value={item.question_id} /> · {displayText(item.test_category || "")}{item.negative_subtype && ` · ${displayText(item.negative_subtype)}`}</p><p>{item.question}</p></section>
    <section><h3>参考答案 / Expected Behavior</h3><p>{item.reference_answer || golden.reference_answer || golden.expected_behavior || "历史未保存参考答案"}</p></section>
    <section><h3>Golden Evidence</h3>{item.test_category === "negative" ? <p>Negative Case 不预设 Golden Evidence；评测目标是拒答和安全边界。</p> : evidence.length ? evidence.map((row, index) => <div key={index} className="evidence-block"><p>支撑证据：{row.evidence_key_points?.join("；") || "未记录"}</p><p>来源 Chunk：{row.source_chunk_ids?.map((id: string) => <ShortId key={id} value={id} />)}</p></div>) : <p>历史 Snapshot 未保存 Golden Evidence。</p>}</section>
    <section><h3>Retrieved Evidence</h3><p>{["candidate_k", "top_k"].filter(key => config[key] != null).map(key => `${parameterNames[key]} ${config[key]}`).join(" · ")}</p><RetrievalEvidence metrics={item.programmatic_metrics} />{item.retrieved_chunks?.length > 0 && !Array.isArray(item.programmatic_metrics?.retrieval_trace?.final) && <><h4>历史保存的回答上下文</h4><div className="run-list">{item.retrieved_chunks.map((row: Row, index: number) => <div key={`${row.chunk_id}-${index}`}><strong>{index + 1} · {row.document || row.chunk_id}</strong><p>{row.chunk_text || row.text || row.content || row.content_preview || "历史未保存证据原文"}</p><ShortId value={row.chunk_id} /></div>)}</div></>}</section>
    <section><h3>Model Answer</h3><p>{item.model_answer || "历史未保存回答"}</p></section>
    <section><h3>Judge</h3><dl className="report-grid">{["correctness", "faithfulness", "completeness", "behavior_pass"].filter(key => item.judge_result?.[key] != null).map(key => <div key={key}><dt>{key}</dt><dd>{String(item.judge_result[key])}</dd></div>)}</dl><p>{item.judge_result?.reason || "历史未保存 Judge 依据"}</p></section>
    <section><h3>Primary Root Cause</h3><p><Badge tone="neutral">{displayText(causeName(item))}</Badge></p></section>
    <section><h3>Secondary Signals</h3><TagList tags={signals} />{!signals.length && <p>没有保存的 Secondary Signals。</p>}</section>
    <section><h3>关联 Gate</h3><p>{related.map(gate => gateNames[gate.metric] || gate.metric).join("、") || "无关联失败 Gate"}</p></section>
    null
  </div>;
}
