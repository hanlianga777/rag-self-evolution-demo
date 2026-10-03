import { useEffect, useRef, useState } from "react";
import { Send } from "lucide-react";
import { errorMessage, identityKey, postJson } from "../api";
import { Badge, CustomSelect, TechnicalDetails } from "../components/Primitives";
import { readSession, writeSession } from "../session";
import { ExecutionMetrics, formatValue, parameterNames } from "../components/PipelineFields";
import type { Citation, PipelinePreview } from "../types";

type Run = { status?: "running" | "completed" | "failed"; startedAt?: number; durationMs?: number; result?: PipelinePreview; error?: string; label?: string; comparisonId?: string; question?: string; sourceId?: string };
type Scheme = { id: string; label: string; version?: string; config?: Record<string, unknown> };
const validRun = (run: Run) => !!run && typeof run === "object" && !Array.isArray(run) && run.status !== "running" && (!run.result || typeof run.result.answer === "string");

export function ExperimentPage({ data = {}, onOpenCitation }: { data?: any; onOpenCitation: (citation: Citation) => void; baselineLabel?: string }) {
  const baseline = data.evaluation || {};
  const active = (data.versions || []).find((version: any) => version.status === "active" && version.provenance === "published");
  const baselineId = data.workspace?.current_baseline_id === undefined ? baseline.id : data.workspace.current_baseline_id;
  const blocked = !baselineId || baselineId !== baseline.id ? data.workspace?.baseline_unavailable_reason || "需要当前有效 Baseline" : !active ? "尚无已发布 Production，请先完成人工发布。" : "";
  const identity = JSON.stringify(["interview-v1", identityKey(data.workspace || baseline), baselineId, active?.id]);
  const leftScheme: Scheme = { id: "baseline", label: "Baseline", version: baselineId, config: baseline.config };
  const source = active?.snapshot?.candidate_id?.match(/(?:^|-)R\d+-([ABC])$/)?.[1];
  const rightScheme: Scheme = { id: active?.id || "", label: source ? `Production ${source}` : "Production", version: active?.id, config: active?.snapshot?.pipeline_config || active?.config };
  const [saved] = useState(() => readSession("rag-qa-compare", { identity: "", question: "", selectedCase: "", left: {} as Run, right: {} as Run }));
  const [question, setQuestion] = useState(saved.identity === identity ? saved.question : "");
  const [selectedCase, setSelectedCase] = useState(saved.identity === identity ? saved.selectedCase : "");
  const [left, setLeft] = useState<Run>(saved.identity === identity && validRun(saved.left) ? saved.left : {});
  const [right, setRight] = useState<Run>(saved.identity === identity && validRun(saved.right) ? saved.right : {});
  const [busy, setBusy] = useState(false);
  const requests = useRef(0), currentIdentity = useRef(identity), previousIdentity = useRef(identity);
  currentIdentity.current = identity;
  useEffect(() => {
    if (previousIdentity.current === identity) return;
    previousIdentity.current = identity; requests.current++; setLeft({}); setRight({}); setBusy(false); setSelectedCase(""); setQuestion("");
  }, [identity]);
  useEffect(() => () => { requests.current++; }, []);
  useEffect(() => writeSession("rag-qa-compare", { identity, question, selectedCase, left, right }), [identity, question, selectedCase, left, right]);
  const badCases = (data.badCases || []).filter((item: any) => item.run_id === baselineId);
  const clearResults = () => { requests.current++; setBusy(false); setLeft({}); setRight({}); };
  const ask = async () => {
    if (blocked || !question.trim()) return;
    const ticket = ++requests.current, captured = identity, askedQuestion = question.trim();
    const startedAt = Date.now(), comparisonId = `compare-${startedAt}-${ticket}`; setBusy(true);
    const request = async (scheme: Scheme, setRun: (run: Run) => void) => {
      const frozen = { startedAt, label: scheme.label, sourceId: scheme.version, comparisonId, question: askedQuestion };
      setRun({ ...frozen, status: "running" });
      try {
        const result = await postJson<PipelinePreview>("/api/preview/scheme", { question: askedQuestion, scheme_id: scheme.id });
        if (ticket !== requests.current || captured !== currentIdentity.current) return;
        if (result.version !== scheme.version) throw new Error(`${scheme.label} 已变化，请重新运行对比`);
        setRun({ ...frozen, status: "completed", durationMs: Date.now() - startedAt, result });
      } catch (reason) { if (ticket === requests.current && captured === currentIdentity.current) setRun({ ...frozen, status: "failed", durationMs: Date.now() - startedAt, error: errorMessage(reason) }); }
    };
    await Promise.all([request(leftScheme, setLeft), request(rightScheme, setRight)]);
    if (ticket === requests.current && captured === currentIdentity.current) setBusy(false);
  };
  const keys = Object.keys(parameterNames).filter(key => leftScheme.config?.[key] !== rightScheme.config?.[key]);
  const summaryKeys = keys.length ? keys : ["prompt_strategy", "candidate_k", "top_k", "rerank"];
  return <div className="page experiment-page">
    <p className="comparison-source">同一道问题，比较正式 Baseline 与当前 Production。</p>
    <section className="experiment-query compare-toolbar">
      <CustomSelect ariaLabel="选择真实 Bad Case" value={selectedCase} onChange={id => { clearResults(); setSelectedCase(id); const item = badCases.find((row: any) => row.id === id); if (item) setQuestion(item.result?.question || ""); }} placeholder="Baseline Bad Case" options={[{ value: "", label: "Baseline Bad Case" }, ...badCases.map((item: any) => ({ value: item.id, label: item.result?.question || item.id }))]} />
      <textarea aria-label="试验问题" placeholder="输入或编辑同一道问题…" maxLength={1000} value={question} onChange={event => { clearResults(); setQuestion(event.target.value); }} />
      <div className="query-action"><button className="primary" disabled={busy || !question.trim() || !!blocked} onClick={() => void ask()}><Send size={15} />{busy ? "正在回答…" : "运行实时对比"}</button></div>
    </section>
    {blocked && <p className="error-notice" role="status">{blocked}</p>}
    <section className="experiment-results" aria-label="实时回答"><AnswerCard scheme={leftScheme} keys={summaryKeys} run={left} onOpenCitation={onOpenCitation} /><AnswerCard scheme={rightScheme} keys={summaryKeys} run={right} onOpenCitation={onOpenCitation} /></section>
  </div>;
}

function AnswerCard({ scheme, keys, run, onOpenCitation }: { scheme: Scheme; keys: string[]; run: Run; onOpenCitation: (citation: Citation) => void }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => { if (run.status !== "running") return; const timer = window.setInterval(() => setNow(Date.now()), 100); return () => window.clearInterval(timer); }, [run.status]);
  const elapsed = run.startedAt == null ? "" : `${((run.durationMs ?? Math.max(0, now - run.startedAt)) / 1000).toFixed(1)}s`;
  const result: any = run.result;
  const config = result?.config || scheme.config || {};
  return <article className={`experiment-answer-card ${scheme.id === "baseline" ? "compare-baseline" : "compare-production"}`}><div className="answer-card-header"><Badge tone="neutral">{run.label || scheme.label}</Badge><span className={run.status || "waiting"}>{run.status === "running" ? `等待 · ${elapsed}` : run.status === "completed" ? "已完成" : run.status === "failed" ? "失败" : "等待运行"}</span></div>
    <div className="answer-config">{keys.filter(key => config[key] != null).map(key => <span key={key}>{parameterNames[key]}: <strong>{formatValue(config[key])}</strong></span>)}</div>
    <div className="answer-scroll">{run.error ? <p className="error-notice" role="alert">回答失败：{run.error}</p> : result ? <MarkdownAnswer text={result.answer} /> : <p className="muted">点击运行后显示实际回答。</p>}</div>
    <div className="answer-evidence">{result?.evidence?.length ? result.evidence.map((item: Citation) => <button className="document-link" key={item.chunk_id} onClick={() => onOpenCitation(item)}>{item.document} · P.{item.page_start}</button>) : result ? <span className="muted">本次回答未返回可定位 Evidence。</span> : null}</div>
    <footer className="answer-metrics-footer"><ExecutionMetrics compact metrics={result} /><TechnicalDetails label="请求身份与指标审计">{JSON.stringify({ comparisonId: run.comparisonId, question: run.question, sourceId: run.sourceId, actual_version: result?.version, config }, null, 2)}{result && <ExecutionMetrics metrics={result} />}</TechnicalDetails></footer>
  </article>;
}

function MarkdownAnswer({ text }: { text: string }) {
  const inline = (value: string) => value.split(/(\*\*[^*]+\*\*)/g).map((part, index) => part.startsWith("**") && part.endsWith("**") ? <strong key={index}>{part.slice(2, -2)}</strong> : part);
  return <div className="answer-markdown">{text.split(/\n{2,}/).map((block, index) => {
    const lines = block.split("\n");
    if (lines.every(line => /^\s*[-*]\s+/.test(line))) return <ul key={index}>{lines.map((line, lineIndex) => <li key={lineIndex}>{inline(line.replace(/^\s*[-*]\s+/, ""))}</li>)}</ul>;
    const heading = block.match(/^#{1,3}\s+(.+)$/);
    return heading ? <h3 key={index}>{inline(heading[1])}</h3> : <p key={index}>{lines.map((line, lineIndex) => <span key={lineIndex}>{lineIndex > 0 && <br />}{inline(line)}</span>)}</p>;
  })}</div>;
}
