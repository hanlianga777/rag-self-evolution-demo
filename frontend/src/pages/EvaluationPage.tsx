import { useEffect, useState } from "react";
import { Play } from "lucide-react";
import { errorMessage, getJson, postJson } from "../api";
import { Badge, Metric, Section, Status } from "../components/Primitives";
import { Drawer } from "../components/Dialog";
import { displayText } from "../display";
import { useOperation } from "../operation";

type Row = Record<string, any>;
type Tab = "report" | "gates" | "cases";
type Filter = "bad" | "all" | "positive" | "ablation" | "negative" | "retrieval" | "generation" | "safety";

const gateNames: Record<string, string> = {
  positive_correctness: "Correctness（正确性）", positive_faithfulness: "Faithfulness（忠实性）", positive_completeness: "Completeness（完整性）",
  ablation_correctness: "Correctness（正确性）", ablation_faithfulness: "Faithfulness（忠实性）", ablation_completeness: "Completeness（完整性）",
  safe_rejection_rate: "Safe Rejection Rate（安全拒答率）", safety_critical_accuracy: "Safety Critical Accuracy（安全关键准确率）",
  prompt_injection_resistance: "Prompt Injection Resistance（提示注入抵抗）", latency_p50_seconds: "Latency P50", latency_p99_seconds: "Latency P99",
};
const format = (value: unknown, suffix = "") => typeof value === "number" ? `${value.toFixed(2)}${suffix}` : "未采集";
const group = (metric: string) => metric.startsWith("positive_") ? "正向题（Positive）" : metric.startsWith("ablation_") ? "消融题（Ablation）" : metric.startsWith("latency_") ? "Performance" : "负向题（Negative）";
const gateValue = (gate: Row) => format(gate.actual, gate.metric.startsWith("latency_") ? " s" : "%");
const gateThreshold = (gate: Row) => `${gate.operator === ">=" ? "≥" : "≤"} ${format(gate.threshold, gate.metric.startsWith("latency_") ? " s" : "%")}`;
const caseScore = (item: Row) => format(item.overall_score);

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
      const started: Row = await operation.run("启动 Baseline Evaluation", () => postJson("/api/evaluations/run"));
      setRun(started); operation.watchEvaluation(started.id, "Baseline Evaluation");
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
    <div className="page-title"><div><h1>Baseline</h1><p>冻结配置、11 项质量门禁与逐题诊断。</p></div><button className="secondary" disabled={busy || run.status === "running" || data.workspace?.requires_new_golden === true} onClick={() => void start()}><Play size={15} />{run.status === "completed" ? "重新运行 Baseline" : run.status === "running" ? "评测进行中" : "运行 Baseline Evaluation"}</button></div>
    {error && <p className="error-notice" role="alert">{error}</p>}
    {stale && run.id && <p className="error-notice">当前知识库状态已变化；以下是历史 Run，不能作为当前发布依据。</p>}
    <div className="metrics-grid baseline-metrics"><Metric label="Hard Gate" value={gates.length ? `${result.gates.passed_count} / ${result.gates.total}` : "未运行"} /><Metric label="Overall" value={format(result.overall_score)} note="仅用于比较" /><Metric label="Bad Case" value={run.status === "completed" ? result.bad_case_count ?? relatedBad.length : "未运行"} /></div>
    <div className="baseline-status"><Badge tone={run.status === "completed" ? "good" : "neutral"}>{run.status === "completed" ? "Evaluation Completed" : displayText(run.status || "not_run")}</Badge>{run.status === "completed" && <Badge tone={result.gates?.passed ? "good" : "warning"}>{result.gates?.passed ? "Gate Qualified" : "Gate Not Qualified"}</Badge>}</div>
    {!run.id ? <Section title="尚未运行 Baseline"><p>正式评测需要已批准 Golden Snapshot 与可用 Provider。</p></Section> : <>
      <div className="tabs"><button className={tab === "report" ? "active" : ""} aria-pressed={tab === "report"} onClick={() => setTab("report")}>Baseline 报告</button><button className={tab === "gates" ? "active" : ""} aria-pressed={tab === "gates"} onClick={() => setTab("gates")}>质量门禁</button><button className={tab === "cases" ? "active" : ""} aria-pressed={tab === "cases"} onClick={() => setTab("cases")}>逐题诊断</button></div>
      {tab === "report" && <div className="baseline-report">
        <Section title="Run Identity"><dl className="report-grid"><div><dt>Baseline Version</dt><dd>{run.judge?.baseline_version || "未采集"}</dd></div><div><dt>Evaluation Run ID</dt><dd>{run.id}</dd></div><div><dt>Golden Snapshot</dt><dd>{run.dataset_version_id || "未记录"}</dd></div><div><dt>Evaluation Time</dt><dd>{run.created_at || "未记录"}</dd></div><div><dt>Judge Model</dt><dd>{run.judge?.model || "未采集"}</dd></div><div><dt>Metrics Version</dt><dd>{run.judge?.scoring_policy || "未采集"}</dd></div><div><dt>Dataset Profile</dt><dd>{profile.name || ({ 20: "Mini", 49: "Medium", 98: "Full" } as Record<number, string>)[snapshot.question_ids?.length] || "未记录"} · {snapshot.question_ids?.length ?? "未记录"} 题</dd></div></dl></Section>
        <Section title="Config Snapshot" action={<button className="text-button" onClick={() => setConfigOpen(true)}>查看完整配置</button>}><dl className="report-grid"><div><dt>CandidateK</dt><dd>{config.candidate_k ?? "未采集"}</dd></div><div><dt>TopK</dt><dd>{config.top_k ?? "未采集"}</dd></div><div><dt>MinScore</dt><dd>{config.min_score ?? "未采集"}</dd></div><div><dt>Hybrid / Alpha</dt><dd>{config.hybrid_search == null ? "未采集" : config.hybrid_search ? `ON / ${config.hybrid_alpha ?? "未采集"}` : "OFF"}</dd></div><div><dt>Rerank</dt><dd>{config.rerank == null ? "未采集" : config.rerank ? "ON" : "OFF"}</dd></div><div><dt>Generation Model</dt><dd>{run.judge?.model || "未采集"}</dd></div></dl></Section>
        <Section title="测试集组成"><dl className="report-grid"><div><dt>Positive 正向题</dt><dd>{categoryCounts[0] ?? "未记录"}</dd></div><div><dt>Ablation 消融题</dt><dd>{categoryCounts[1] ?? "未记录"}</dd></div><div><dt>Negative 负向题</dt><dd>{categoryCounts[2] ?? "未记录"}</dd></div><div><dt>状态</dt><dd>{snapshot.id ? "Approved / Frozen" : "未记录"}</dd></div><div><dt>Corpus Fingerprint</dt><dd>{snapshot.corpus_fingerprint ? "已记录" : "未采集"}</dd></div></dl></Section>
        <Section title="Gate Summary" action={<button className="text-button" onClick={() => setTab("gates")}>查看质量门禁</button>}><p>{gates.length} Hard Gate · PASS {result.gates?.passed_count ?? 0} · FAIL {failures.length}</p>{failures.map(gate => <p key={gate.metric}>{String(gates.indexOf(gate) + 1).padStart(2, "0")} {group(gate.metric)} {gateNames[gate.metric]}：{gateValue(gate)} / {gateThreshold(gate)}</p>)}</Section>
        <Section title="Performance & Retrieval"><dl className="report-grid"><div><dt>Recall@K · Diagnostic</dt><dd>{format(comparison.recall_at_k, "%")}</dd></div><div><dt>Precision@K · Diagnostic</dt><dd>{format(comparison.precision_at_k, "%")}</dd></div><div><dt>MRR · Diagnostic</dt><dd>{format(comparison.mrr)}</dd></div><div><dt>TTFT · Diagnostic</dt><dd>{format(comparison.ttft_seconds, " s")}</dd></div><div><dt>Token Cost · Comparison</dt><dd>{comparison.token_cost ?? "未采集"}</dd></div><div><dt>Latency P50 · Hard Gate</dt><dd>{format(result.metrics?.latency_p50_seconds, " s")}</dd></div><div><dt>Latency P99 · Hard Gate</dt><dd>{format(result.metrics?.latency_p99_seconds, " s")}</dd></div></dl><p className="muted">阶段耗时未采集。</p></Section>
      </div>}
      {tab === "gates" && <Section title="11 项 Hard Gate"><div className="table-scroll baseline-table"><table><thead><tr><th>#</th><th>测试组</th><th>指标</th><th>实际</th><th>门槛</th><th>状态</th></tr></thead><tbody>{gates.map((gate, index) => <tr key={gate.metric} tabIndex={0} onClick={() => setSelectedGate(details[index] || gate)} onKeyDown={event => { if (event.key === "Enter") setSelectedGate(details[index] || gate); }}><td>{String(index + 1).padStart(2, "0")}</td><td>{group(gate.metric)}</td><td>{gateNames[gate.metric] || gate.metric}</td><td>{gateValue(gate)}</td><td>{gateThreshold(gate)}</td><td><Status value={gate.status} /></td></tr>)}</tbody></table></div></Section>}
      {tab === "cases" && <Section title="逐题诊断"><div className="review-filters" aria-label="逐题筛选">{([ ["bad", "Bad Case"], ["all", "全部"], ["positive", "正向题"], ["ablation", "消融题"], ["negative", "负向题"], ["retrieval", "Retrieval Miss"], ["generation", "Generation"], ["safety", "Safety"] ] as [Filter, string][]).map(([key, label]) => <button key={key} aria-pressed={filter === key} className={filter === key ? "active" : ""} onClick={() => setFilter(key)}>{label}</button>)}</div><div className="table-scroll baseline-table"><table><thead><tr><th>#</th><th>Question</th><th>测试组</th><th>Score</th><th>Retrieval</th><th>Root Cause</th><th>Failure Tag</th><th>Status</th></tr></thead><tbody>{visible.map(item => <tr key={item.question_id} tabIndex={0} onClick={() => setSelectedCase(item)} onKeyDown={event => { if (event.key === "Enter") setSelectedCase(item); }}><td>{item.question_id}</td><td className="case-question">{item.question}</td><td>{displayText(item.test_category)}</td><td>{caseScore(item)}</td><td>{item.test_category === "negative" ? "N/A" : item.programmatic_metrics?.retrieval_hit === true ? "Hit" : item.programmatic_metrics?.retrieval_hit === false ? "Miss" : "未采集"}</td><td>{item.primary_root_cause || "未记录"}</td><td>{item.failure_tags?.join("、") || "—"}</td><td><Status value={item.passed ? "passed" : "failed"} /></td></tr>)}{!visible.length && <tr><td colSpan={8}>当前筛选无记录。</td></tr>}</tbody></table></div></Section>}
    </>}
    <Drawer open={configOpen} onOpenChange={setConfigOpen} title="完整 Config Snapshot"><div className="drawer-body"><dl className="report-grid">{["candidate_k", "top_k", "min_score", "hybrid_search", "hybrid_alpha", "rerank", "query_rewrite", "multi_query", "hyde", "metadata_filter", "alias_mapping", "prompt_strategy"].map(key => <div key={key}><dt>{key}</dt><dd>{config[key] == null ? "未采集" : String(config[key])}</dd></div>)}{["embedding_model", "vector_index", "temperature"].map(key => <div key={key}><dt>{key}</dt><dd>{run.judge?.execution_snapshot?.[key] ?? "未采集"}</dd></div>)}</dl></div></Drawer>
    <Drawer open={!!selectedGate} onOpenChange={open => !open && setSelectedGate(null)} title={selectedGate ? gateNames[selectedGate.metric] || selectedGate.metric : "Gate Detail"}><div className="drawer-body">{selectedGate && <><p>{group(selectedGate.metric)} · {gateValue(selectedGate)} / {gateThreshold(selectedGate)} · <Status value={selectedGate.status} /></p><h3>Metric Definition / Formula</h3><p>{selectedGate.formula || "历史记录未保存计算说明"}</p><p>Included Cases：{selectedGate.included_cases ?? "未记录"} · Judge：{run.judge?.model || "未采集"}</p><h3>Contributing Cases</h3><div className="run-list">{(selectedGate.contributing_cases || []).map((item: Row) => <div key={item.question_id}><strong>{item.question_id}</strong><span>{format(item.value, selectedGate.metric.startsWith("latency_") ? " s" : "%")}</span><Status value={item.passed ? "passed" : "failed"} /></div>)}</div><h3>Related Baseline Config</h3><p>CandidateK {config.candidate_k ?? "未采集"} · TopK {config.top_k ?? "未采集"}</p></>}</div></Drawer>
    <Drawer open={!!selectedCase} onOpenChange={open => !open && setSelectedCase(null)} title={selectedCase ? `Case ${selectedCase.question_id}` : "Case Diagnosis"}><div className="drawer-body">{selectedCase && <CaseDetails item={selectedCase} snapshot={snapshot} config={config} gates={details} />}</div></Drawer>
  </div>;
}

function CaseDetails({ item, snapshot, config, gates }: { item: Row; snapshot: Row; config: Row; gates: Row[] }) {
  const golden = snapshot.questions?.find((row: Row) => row.id === item.question_id) || {};
  const evidence = golden.acceptable_evidence || [];
  const related = gates.filter(gate => gate.status === "FAIL" && gate.contributing_cases?.some((row: Row) => row.question_id === item.question_id));
  return <div className="case-details"><h3>Question</h3><p>{item.question_id} · {displayText(item.test_category)} · {item.negative_subtype || "—"}</p><p>{item.question}</p><p>Reference Answer：{item.reference_answer || "未记录"}</p><h3>Golden Evidence</h3>{item.test_category === "negative" ? <p>此 Negative Case 不预设 Golden Evidence；评测目标为拒答 / 安全边界 / Prompt Injection。</p> : <pre>{JSON.stringify(evidence, null, 2)}</pre>}<h3>Retrieval</h3><p>CandidateK {config.candidate_k ?? "未采集"} · TopK {config.top_k ?? "未采集"} · {item.test_category === "negative" ? "Golden Evidence Hit：N/A" : item.programmatic_metrics?.retrieval_hit === true ? "Golden Evidence Hit" : item.programmatic_metrics?.retrieval_hit === false ? "Golden Evidence Miss" : "未采集"}</p><pre>{JSON.stringify(item.retrieved_chunks || [], null, 2)}</pre><h3>Generation & Judge</h3><p>Model Answer：{item.model_answer || "未记录"}</p><pre>{JSON.stringify(item.judge_result || {}, null, 2)}</pre><p>Redline：{item.redline_pass == null ? "未采集" : item.redline_pass ? "通过" : "未通过"}</p><h3>Diagnosis</h3><p>Root Cause：{item.primary_root_cause || "未记录"} · Failure Tag：{item.failure_tags?.join("、") || "无"}</p><p>关联未通过 Gate：{related.map(gate => gateNames[gate.metric] || gate.metric).join("、") || "无"}</p><p>诊断摘要：{item.diagnosis_summary || "未采集"}</p></div>;
}
