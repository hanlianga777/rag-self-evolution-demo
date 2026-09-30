import { useEffect, useState } from "react";
import { Play } from "lucide-react";
import { errorMessage, getJson, postJson } from "../api";
import { Badge, Metric, Section, ShortId, Status, TechnicalDetails, StageStepper, TruncatedText, TagList } from "../components/Primitives";
import { ExecutionMetrics } from "../components/PipelineFields";
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
  prompt_injection_resistance: "Prompt Injection Resistance（提示注入抵抗）", latency_p50_seconds: "Latency P50", latency_p99_seconds: "Latency P99",
};
const format = (value: unknown, suffix = "") => typeof value === "number" ? `${value.toFixed(2)}${suffix}` : "未采集";
const group = (metric: string) => metric.startsWith("positive_") ? "正向题（Positive）" : metric.startsWith("ablation_") ? "消融题（Ablation）" : metric.startsWith("latency_") ? "性能" : "负向题（Negative）";
const gateValue = (gate: Row) => format(gate.actual, gate.metric.startsWith("latency_") ? " s" : "%");
const gateThreshold = (gate: Row) => `${gate.operator === ">=" ? "≥" : "≤"} ${format(gate.threshold, gate.metric.startsWith("latency_") ? " s" : "%")}`;
const localTime = (value?: string) => {
  if (!value) return "未记录";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "未记录" : new Intl.DateTimeFormat("zh-CN", { timeZone: "Asia/Shanghai", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false }).format(date).replaceAll("/", "-");
};
const causeName = (item: Row) => item.primary_root_cause || "未记录";

export function EvaluationPage({ data }: { data: any; navigate?: (page: any) => void }) {
  const operation = useOperation();
  const [tab, setTab] = useState<Tab>("report");
  const [filter, setFilter] = useState<Filter>("bad");
  const [run, setRun] = useState<Row>(data.evaluation || {});
  const [badCases, setBadCases] = useState<Row[]>(data.badCases || []);
  const [selectedGate, setSelectedGate] = useState<Row | null>(null);
  const [selectedCase, setSelectedCase] = useState<Row | null>(null);
  const [configOpen, setConfigOpen] = useState(false);
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
        if (next.status !== "running") setBadCases(await getJson<Row[]>("/api/bad-cases"));
      } catch (reason) { if (!cancelled) setError(errorMessage(reason)); }
    };
    void poll();
    return () => { cancelled = true; };
  }, [run.id]);

  const start = async () => {
    if (run.status === "completed" && !window.confirm("重新运行 Baseline 将产生新的 Evaluation Run；当前报告保留为历史。确认继续？")) return;
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

  return <div className="page evaluation-page">
    <div className="page-title"><div><h1>Baseline · RAG 体检报告</h1><p>冻结配置、11 项 Hard Gate 与逐题 Bad Case 诊断。</p></div><button className="secondary" disabled={busy || run.status === "running" || data.workspace?.requires_new_golden === true} onClick={() => void start()}><Play size={15} />{run.status === "completed" ? "重新运行 Baseline" : run.status === "running" ? "评测进行中" : "运行 Baseline 评测"}</button></div>
    <StageStepper ariaLabel="Baseline 阶段" steps={[{ label: "Golden 冻结", state: run.dataset_version_id ? "completed" : "pending" }, { label: "回答与 Judge", state: run.status === "completed" ? "completed" : run.status === "running" ? "current" : "pending" }, { label: "Hard Gate", state: result.gates?.passed ? "completed" : "pending", detail: run.status === "completed" ? result.gates?.passed ? "通过" : "未通过" : "未运行" }, { label: "Bad Case 诊断", state: run.status === "completed" ? "completed" : "pending" }]} />
    {error && <p className="error-notice" role="alert">{error}</p>}
    {stale && run.id && <p className="error-notice">当前知识库状态已变化；以下是历史 Run，不能作为当前发布依据。</p>}
    <div className="metrics-grid baseline-metrics"><Metric label="Hard Gate" value={gates.length ? `${result.gates.passed_count} / ${result.gates.total}` : "未运行"} /><Metric label="综合评分" value={format(result.overall_score)} note="仅用于比较" /><Metric label="Bad Case" value={run.status === "completed" ? result.bad_case_count ?? relatedBad.length : "未运行"} /></div>
    <div className="baseline-status"><Badge tone={run.status === "completed" ? "good" : "neutral"}>{run.status === "completed" ? "已完成评测" : displayText(run.status || "not_run")}</Badge>{run.status === "completed" && <Badge tone={result.gates?.passed ? "good" : "warning"}>{result.gates?.passed ? "Gate 通过" : "Gate 未通过"}</Badge>}</div>
    {!run.id ? <Section title="尚未运行 Baseline"><p>正式评测需要已批准 Golden Snapshot 与可用 Provider。</p></Section> : <>
      <div className="tabs"><button className={tab === "report" ? "active" : ""} aria-pressed={tab === "report"} onClick={() => setTab("report")}>Baseline 报告</button><button className={tab === "gates" ? "active" : ""} aria-pressed={tab === "gates"} onClick={() => setTab("gates")}>Hard Gate</button><button className={tab === "cases" ? "active" : ""} aria-pressed={tab === "cases"} onClick={() => setTab("cases")}>Bad Case 诊断</button></div>
      {tab === "report" && <div className="baseline-report">
        <Section title="运行摘要"><dl className="report-grid"><div><dt>Baseline 版本</dt><dd>{run.judge?.baseline_version || "未采集"}</dd></div><div><dt>评测 Run ID</dt><dd><ShortId value={run.id} /></dd></div><div><dt>Golden Snapshot</dt><dd><ShortId value={run.dataset_version_id} /></dd></div><div><dt>评测时间</dt><dd>{localTime(run.created_at)}{run.created_at && <TechnicalDetails label="查看原始时间">{run.created_at}</TechnicalDetails>}</dd></div><div><dt>Judge 模型</dt><dd>{run.judge?.model || "未采集"}</dd></div><div><dt>评测规则版本</dt><dd>{run.judge?.scoring_policy || "未采集"}</dd></div><div><dt>测试集规模</dt><dd>{profile.name || ({ 20: "Mini", 49: "Medium", 98: "Full" } as Record<number, string>)[snapshot.question_ids?.length] || "未记录"} · {snapshot.question_ids?.length ?? "未记录"} 题</dd></div></dl></Section>
        <Section title="配置快照" action={<button className="text-button" onClick={() => setConfigOpen(true)}>查看完整配置</button>}><div className="config-summary-grid"><div><h3>Query</h3><p>Rewrite {String(config.query_rewrite ?? "未采集")} · MultiQuery {String(config.multi_query ?? "未采集")} · HyDE {String(config.hyde ?? "未采集")}</p></div><div><h3>检索</h3><p>CandidateK {config.candidate_k ?? "未采集"} · TopK {config.top_k ?? "未采集"} · MinScore {config.min_score ?? "未采集"} · Hybrid {config.hybrid_search ? `ON / ${config.hybrid_alpha}` : "OFF"}</p></div><div><h3>Rerank</h3><p>{config.rerank ? "ON · 轻量二阶段重排" : "OFF"}</p></div><div><h3>生成</h3><p>{config.prompt_strategy || "未采集"} · {run.judge?.execution_snapshot?.generation_model || run.judge?.model || "未采集"}</p></div></div></Section>
        <Section title="测试集组成"><dl className="report-grid"><div><dt>正向题（Positive）</dt><dd>{categoryCounts[0] ?? "未记录"}</dd></div><div><dt>消融题（Ablation）</dt><dd>{categoryCounts[1] ?? "未记录"}</dd></div><div><dt>负向题（Negative）</dt><dd>{categoryCounts[2] ?? "未记录"}</dd></div><div><dt>状态</dt><dd>{snapshot.id ? "已批准 / 已冻结" : "未记录"}</dd></div><div><dt>Corpus 指纹</dt><dd>{snapshot.corpus_fingerprint ? "已记录" : "未采集"}</dd></div></dl></Section>
        <Section title="Gate 总览" action={<button className="text-button" onClick={() => setTab("gates")}>查看质量门禁</button>}><p>{gates.length} 项 Hard Gate · 通过 {result.gates?.passed_count ?? 0} · 未通过 {failures.length}</p><div className="failed-gate-grid">{failures.map(gate => <p key={gate.metric}>{String(gates.indexOf(gate) + 1).padStart(2, "0")} {group(gate.metric)} {gateNames[gate.metric]}：{gateValue(gate)} / {gateThreshold(gate)}</p>)}</div></Section>
        <Section title="性能与检索"><dl className="report-grid"><div><dt>Recall@K · 诊断指标</dt><dd>{format(comparison.recall_at_k, "%")}</dd></div><div><dt>Precision@K · 诊断指标</dt><dd>{format(comparison.precision_at_k, "%")}</dd></div><div><dt>MRR · 诊断指标</dt><dd>{format(comparison.mrr)}</dd></div><div><dt>TTFT · 诊断指标</dt><dd>{format(comparison.ttft_seconds, " s")}</dd></div><div><dt>Token 成本 · 对比指标</dt><dd>{comparison.token_cost ?? "暂未配置单价"}</dd></div><div><dt>延迟 P50 · Hard Gate</dt><dd>{format(result.metrics?.latency_p50_seconds, " s")}</dd></div><div><dt>延迟 P99 · Hard Gate</dt><dd>{format(result.metrics?.latency_p99_seconds, " s")}</dd></div></dl><p>历史回答输入 / 输出 Token：{comparison.input_tokens ?? "未采集"} / {comparison.output_tokens ?? "未采集"}</p><ExecutionMetrics metrics={cases.find(row => row.programmatic_metrics?.stages)?.programmatic_metrics} /></Section>
      </div>}
      {tab === "gates" && <Section title="11 项 Hard Gate"><div className="table-scroll baseline-table"><table><thead><tr><th>#</th><th>测试组</th><th>指标</th><th>实际</th><th>门槛</th><th>状态</th></tr></thead><tbody>{gates.map((gate, index) => <tr key={gate.metric} tabIndex={0} onClick={() => setSelectedGate(details[index] || gate)} onKeyDown={event => { if (event.key === "Enter") setSelectedGate(details[index] || gate); }}><td>{String(index + 1).padStart(2, "0")}</td><td>{group(gate.metric)}</td><td>{gateNames[gate.metric] || gate.metric}</td><td>{gateValue(gate)}</td><td>{gateThreshold(gate)}</td><td><Status value={gate.status} /></td></tr>)}</tbody></table></div></Section>}
      {tab === "cases" && <Section title="Bad Case 诊断"><div className="review-filters" aria-label="逐题筛选">{([ ["bad", "Bad Case"], ["all", "全部"], ["positive", "正向题"], ["ablation", "消融题"], ["negative", "负向题"], ["retrieval", "检索未命中"], ["generation", "生成"], ["safety", "安全"] ] as [Filter, string][]).map(([key, label]) => <button key={key} aria-pressed={filter === key} className={filter === key ? "active" : ""} onClick={() => setFilter(key)}>{label}</button>)}</div><div className="table-scroll baseline-table"><table><thead><tr><th>题目</th><th>问题</th><th>根因</th><th>关联 Gate</th><th>证据</th></tr></thead><tbody>{visible.map(item => { const related = details.filter(gate => gate.status === "FAIL" && gate.contributing_cases?.some((row: Row) => row.question_id === item.question_id)).map(gate => gateNames[gate.metric] || gate.metric); const tags: string[] = item.failure_tags || []; return <tr key={item.question_id} tabIndex={0} onClick={() => setSelectedCase(item)} onKeyDown={event => { if (event.key === "Enter") setSelectedCase(item); }}><td><ShortId value={item.question_id} /></td><td className="case-question"><TruncatedText lines={2}>{item.question}</TruncatedText></td><td><Badge tone="neutral">{causeName(item)}</Badge></td><td><TruncatedText lines={2}>{related.join("、") || "未关联"}</TruncatedText></td><td><TagList tags={tags} />{!tags.length && (item.programmatic_metrics?.retrieval_hit === false ? "检索未命中" : "已记录")}</td></tr>; })}{!visible.length && <tr><td colSpan={5}>当前筛选无记录。</td></tr>}</tbody></table></div></Section>}
    </>}
    <Drawer open={configOpen} onOpenChange={setConfigOpen} title="完整配置快照"><div className="drawer-body"><dl className="report-grid">{["candidate_k", "top_k", "min_score", "hybrid_search", "hybrid_alpha", "rerank", "query_rewrite", "multi_query", "hyde", "metadata_filter", "alias_mapping", "prompt_strategy"].map(key => <div key={key}><dt>{key}</dt><dd>{config[key] == null ? "未采集" : String(config[key])}</dd></div>)}{["embedding_model", "vector_index", "temperature"].map(key => <div key={key}><dt>{key}</dt><dd>{run.judge?.execution_snapshot?.[key] ?? "未采集"}</dd></div>)}</dl></div></Drawer>
    <Drawer open={!!selectedGate} onOpenChange={open => !open && setSelectedGate(null)} title={selectedGate ? gateNames[selectedGate.metric] || selectedGate.metric : "Gate 详情"}><div className="drawer-body">{selectedGate && <><p>{group(selectedGate.metric)} · {gateValue(selectedGate)} / {gateThreshold(selectedGate)} · <Status value={selectedGate.status} /></p><h3>指标定义与公式</h3><p>{selectedGate.formula || "历史记录未保存计算说明"}</p><p>纳入题数：{selectedGate.included_cases ?? "未记录"} · Judge：{run.judge?.model || "未采集"}</p><h3>贡献题目</h3><div className="run-list">{(selectedGate.contributing_cases || []).map((item: Row) => <div key={item.question_id}><strong><TruncatedText lines={2}>{cases.find(row => row.question_id === item.question_id)?.question || "历史题目未记录"}</TruncatedText></strong><span>{format(item.value, selectedGate.metric.startsWith("latency_") ? " s" : "%")}</span><Status value={item.passed ? "passed" : "failed"} /></div>)}</div><h3>关联 Baseline 配置</h3><p>CandidateK {config.candidate_k ?? "未采集"} · TopK {config.top_k ?? "未采集"}</p></>}</div></Drawer>
    <Drawer open={!!selectedCase} onOpenChange={open => !open && setSelectedCase(null)} title="案例诊断"><div className="drawer-body">{selectedCase && <CaseDetails item={selectedCase} snapshot={snapshot} config={config} gates={details} />}</div></Drawer>
  </div>;
}

function CaseDetails({ item, snapshot, config, gates }: { item: Row; snapshot: Row; config: Row; gates: Row[] }) {
  const golden = snapshot.questions?.find((row: Row) => row.id === item.question_id) || {};
  const evidence: Row[] = golden.acceptable_evidence || [];
  const retrieved: Row[] = item.retrieved_chunks || [];
  const sourceIds = new Set(evidence.flatMap(row => row.source_chunk_ids || []));
  const related = gates.filter(gate => gate.status === "FAIL" && gate.contributing_cases?.some((row: Row) => row.question_id === item.question_id));
  return <div className="case-details"><section><h3>问题</h3><p><ShortId value={item.question_id} /> · {displayText(item.test_category)} · {item.negative_subtype || "—"}</p><p>{item.question}</p></section><section><h3>参考答案</h3><p>{item.reference_answer || "未记录"}</p></section><section><h3>Golden 证据</h3>{item.test_category === "negative" ? <p>Negative Case 不预设 Golden Evidence；评测目标是拒答和安全边界。</p> : evidence.map((row, index) => <div key={index} className="evidence-block"><p>支撑证据：{row.evidence_key_points?.join("；") || "未记录"}</p><p>来源 Chunk：{row.source_chunk_ids?.map((id: string) => <ShortId key={id} value={id} />)}</p></div>)}</section><section><h3>检索</h3><p>CandidateK {config.candidate_k ?? "未采集"} · TopK {config.top_k ?? "未采集"} · {item.test_category === "negative" ? "不适用" : item.programmatic_metrics?.retrieval_hit === true ? "命中 Golden 证据" : item.programmatic_metrics?.retrieval_hit === false ? "未命中 Golden 证据" : "未采集"}</p><div className="table-scroll"><table><thead><tr><th>排名</th><th>Chunk</th><th>文档</th><th>分数</th><th>命中 Golden</th></tr></thead><tbody>{retrieved.map((row, index) => <tr key={`${row.chunk_id}-${index}`}><td>{index + 1}</td><td><ShortId value={row.chunk_id} /></td><td>{row.document || "未记录"}</td><td>{typeof row.score === "number" ? row.score.toFixed(3) : "未采集"}</td><td>{item.test_category === "negative" ? "不适用" : sourceIds.has(row.chunk_id) ? "是" : "否"}</td></tr>)}</tbody></table></div></section><section><h3>模型回答</h3><p>{item.model_answer || "未记录"}</p></section><ExecutionMetrics metrics={item.programmatic_metrics} /><section><h3>Judge 结果</h3><div className="report-grid">{(["correctness", "faithfulness", "completeness"] as const).map(key => <div key={key}><dt>{key}</dt><dd>{item.judge_result?.[key] ?? "未采集"}</dd></div>)}</div><p>{item.judge_result?.reason || "未采集"}</p></section><section><h3>根因与关联 Gate</h3><p>{item.primary_root_cause || "未记录"} · {item.failure_tags?.join("、") || "无失败标签"}</p><p>{related.map(gate => gateNames[gate.metric] || gate.metric).join("、") || "无关联失败 Gate"}</p><p>关联配置：CandidateK {config.candidate_k ?? "—"} · TopK {config.top_k ?? "—"} · Prompt {config.prompt_strategy || "—"}</p></section><TechnicalDetails label="原始 JSON">{JSON.stringify({ golden_evidence: evidence, retrieval: retrieved, judge: item.judge_result }, null, 2)}</TechnicalDetails></div>;
}
