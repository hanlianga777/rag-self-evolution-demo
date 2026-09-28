import { useEffect, useState } from "react";
import { Send } from "lucide-react";
import { errorMessage, getJson, postJson } from "../api";
import { Badge, Section, ShortId } from "../components/Primitives";
import { formatValue } from "../components/PipelineFields";
import type { Citation, PipelinePreview } from "../types";

type Run = { status?: "running" | "completed" | "failed"; startedAt?: number; durationMs?: number; result?: PipelinePreview; error?: string };
type Scheme = { id: string; label: string; evaluationId?: string };

export function ExperimentPage({ data = {}, onOpenCitation }: { data?: any; onOpenCitation: (citation: Citation) => void; baselineLabel?: string }) {
  const versions: any[] = data.versions || [];
  const candidates: any[] = data.optimization?.candidates || [];
  const active = versions.find(version => version.status === "active");
  const previous = versions.find(version => version.id === active?.previous_version_id);
  const qualified = candidates.find(candidate => candidate.result?.qualification?.qualified && candidate.reasoning?.candidate_label !== "D");
  const baseline = data.evaluation || {};
  const schemes: Scheme[] = [{ id: "baseline", label: "Baseline", evaluationId: baseline.id }, ...candidates.filter(candidate => candidate.reasoning?.candidate_label !== "D").map(candidate => ({ id: candidate.id, label: `Candidate ${candidate.reasoning?.candidate_label}`, evaluationId: candidate.result?.evaluation_run_id })), ...versions.map(version => ({ id: version.id, label: version.id === active?.id ? version.provenance === "published" ? "Current Production" : "Current Baseline" : version.id === previous?.id ? "Previous Production" : version.id, evaluationId: version.evaluation_run_id || (version.provenance === "bootstrap" ? baseline.id : undefined) }))];
  const [leftId, setLeftId] = useState(active?.provenance === "published" && previous ? previous.id : "baseline");
  const [rightId, setRightId] = useState(active?.provenance === "published" ? active.id : qualified?.id || "");
  const [question, setQuestion] = useState("");
  const [selectedCase, setSelectedCase] = useState("");
  const [left, setLeft] = useState<Run>({});
  const [right, setRight] = useState<Run>({});
  const [history, setHistory] = useState<{ left?: any; right?: any } | null>(null);
  const [busy, setBusy] = useState(false);
  const badCases = (data.badCases || []).filter((item: any) => item.run_id === baseline.id);
  const leftScheme = schemes.find(item => item.id === leftId);
  const rightScheme = schemes.find(item => item.id === rightId);
  useEffect(() => { setLeft({}); setRight({}); setHistory(null); }, [leftId, rightId]);

  const useBadCase = async () => {
    const item = badCases.find((row: any) => row.id === selectedCase) || badCases[0];
    if (!item) return;
    setSelectedCase(item.id); setQuestion(item.result?.question || ""); setHistory(null);
    const read = async (scheme?: Scheme) => {
      if (!scheme?.evaluationId) return null;
      const run: any = await getJson(`/api/evaluations/${scheme.evaluationId}`);
      return run.cases?.find((row: any) => row.question_id === item.question_id) || null;
    };
    try { const [before, after] = await Promise.all([read(leftScheme), read(rightScheme)]); setHistory({ left: before, right: after }); }
    catch { setHistory(null); }
  };
  const ask = async () => {
    if (!question.trim() || !leftId || !rightId || leftId === rightId) return;
    const startedAt = Date.now(); setBusy(true); setHistory(null); setLeft({ status: "running", startedAt }); setRight({ status: "running", startedAt });
    const request = (schemeId: string, setRun: (run: Run) => void) => postJson<PipelinePreview>("/api/preview/scheme", { question, scheme_id: schemeId })
      .then(result => setRun({ status: "completed", startedAt, durationMs: Date.now() - startedAt, result }))
      .catch(reason => setRun({ status: "failed", startedAt, durationMs: Date.now() - startedAt, error: errorMessage(reason) }));
    await Promise.all([request(leftId, setLeft), request(rightId, setRight)]); setBusy(false);
  };
  const changes = Object.entries(right.result?.config || {}).filter(([key, value]) => left.result?.config?.[key] !== value);
  return <div className="page experiment-page"><div className="page-title"><div><h2>Before / After</h2><p>同一个问题比较两个已持久化方案。历史评测与实时预览分别标明来源。</p></div></div>
    <div className="scheme-selectors"><label>Scheme A<select aria-label="Scheme A" value={leftId} onChange={event => setLeftId(event.target.value)}>{schemes.map(item => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label><span>vs</span><label>Scheme B<select aria-label="Scheme B" value={rightId} onChange={event => setRightId(event.target.value)}><option value="">选择方案</option>{schemes.map(item => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label></div>
    {badCases.length > 0 && <div className="fixed-case-control"><label>Use Fixed Bad Case<select aria-label="选择真实 Bad Case" value={selectedCase} onChange={event => setSelectedCase(event.target.value)}><option value="">选择本轮 Baseline Bad Case</option>{badCases.map((item: any) => <option key={item.id} value={item.id}>{item.question_id} · {item.result?.question?.slice(0, 45)}</option>)}</select></label><button className="secondary" onClick={() => void useBadCase()}>使用该问题</button></div>}
    <section className="panel experiment-query"><label className="question-input"><textarea aria-label="试验问题" placeholder="请输入同一个真实问题…" maxLength={1000} value={question} onChange={event => setQuestion(event.target.value)} /></label><button className="primary" disabled={busy || !question.trim() || !rightId || leftId === rightId} onClick={() => void ask()}><Send size={15} />{busy ? "正在回答…" : "运行实时对比"}</button></section>
    {leftId === rightId && <p className="error-notice">请选择两个不同方案。</p>}
    {history && <Section title="已保存的逐题 Evaluation · 历史证据"><div className="experiment-results"><HistoricalAnswer label={leftScheme?.label || "Scheme A"} item={history.left} /><HistoricalAnswer label={rightScheme?.label || "Scheme B"} item={history.right} /></div></Section>}
    <section className="experiment-results" aria-label="实时回答"><AnswerCard label={leftScheme?.label || "Scheme A"} run={left} onOpenCitation={onOpenCitation} /><AnswerCard label={rightScheme?.label || "Scheme B"} run={right} onOpenCitation={onOpenCitation} /></section>
    {changes.length > 0 && <details className="panel"><summary>Config Diff · {changes.length} 项</summary><div className="table-scroll"><table><thead><tr><th>Parameter</th><th>Before</th><th>After</th></tr></thead><tbody>{changes.map(([key, value]) => <tr key={key}><td>{key}</td><td>{formatValue(left.result?.config?.[key])}</td><td>{formatValue(value)}</td></tr>)}</tbody></table></div></details>}
  </div>;
}

function HistoricalAnswer({ label, item }: { label: string; item?: any }) {
  return <article className="experiment-answer-card"><div className="answer-card-header"><Badge tone="neutral">{label}</Badge><span>已保存的 Evaluation</span></div>{item ? <div className="answer-scroll"><p>{item.model_answer || "未记录"}</p><p className="muted">Case <ShortId value={item.question_id} /> · {item.passed ? "PASS" : "FAIL"}</p><details><summary>Evidence / Citation · {item.retrieved_chunks?.length || 0}</summary>{(item.retrieved_chunks || []).map((row: any) => <p key={row.chunk_id}>{row.document} · P.{row.page_start} · <ShortId value={row.chunk_id} /></p>)}</details></div> : <p className="muted">该方案没有对应的已保存逐题结果。</p>}</article>;
}

function AnswerCard({ label, run, onOpenCitation }: { label: string; run: Run; onOpenCitation: (citation: Citation) => void }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => { if (run.status !== "running") return; const timer = window.setInterval(() => setNow(Date.now()), 100); return () => window.clearInterval(timer); }, [run.status]);
  const elapsed = run.startedAt == null ? "" : `${((run.durationMs ?? Math.max(0, now - run.startedAt)) / 1000).toFixed(1)}s`;
  return <article className="experiment-answer-card"><div className="answer-card-header"><Badge tone="neutral">{label}</Badge><span className={run.status || "waiting"}>{run.status === "running" ? `实时预览中 · ${elapsed}` : run.status === "completed" ? `实时预览 · ${elapsed}` : run.status === "failed" ? `失败 · ${elapsed}` : "等待运行"}</span></div><div className="answer-scroll">{run.error ? <p className="error-notice" role="alert">预览失败：{run.error}</p> : run.result ? <><p>{run.result.answer}</p><p className="muted">版本 <ShortId value={run.result.version} /> · Prompt {formatValue(run.result.config?.prompt_strategy)} · TopK {formatValue(run.result.config?.top_k)} · Latency {run.result.latency_ms} ms</p><details><summary>Evidence / Citation · {run.result.evidence?.length || 0}</summary>{run.result.evidence?.map(item => <button className="document-link" key={item.chunk_id} onClick={() => onOpenCitation(item)}>{item.document} · P.{item.page_start} · {item.chunk_id}</button>)}</details></> : <p className="muted">运行后显示该方案的实时回答。</p>}</div></article>;
}
