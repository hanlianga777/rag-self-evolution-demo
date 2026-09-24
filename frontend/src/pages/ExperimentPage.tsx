import { useEffect, useState } from "react";
import { Send } from "lucide-react";
import { errorMessage, postJson } from "../api";
import { Badge } from "../components/Primitives";
import type { Citation, PipelinePreview } from "../types";

type Run = { status?: "running" | "completed" | "failed"; startedAt?: number; durationMs?: number; result?: PipelinePreview; error?: string };

export function ExperimentPage({ onOpenCitation }: { onOpenCitation: (citation: Citation) => void }) {
  const [question, setQuestion] = useState(""); const [baseline, setBaseline] = useState<Run>({}); const [candidate, setCandidate] = useState<Run>({}); const [busy, setBusy] = useState(false);
  const ask = async () => {
    const startedAt = Date.now();
    setBusy(true); setBaseline({ status: "running", startedAt }); setCandidate({ status: "running", startedAt });
    const request = (path: string, setRun: (run: Run) => void) => postJson<PipelinePreview>(path, { question })
      .then(result => setRun({ status: "completed", startedAt, durationMs: Date.now() - startedAt, result }))
      .catch(reason => setRun({ status: "failed", startedAt, durationMs: Date.now() - startedAt, error: errorMessage(reason) }));
    await Promise.all([request("/api/preview/baseline", setBaseline), request("/api/preview/candidate", setCandidate)]);
    setBusy(false);
  };
  return <div className="page experiment-page"><div className="page-title"><div><h2>Before / After 验证</h2><p>同一问题分别调用当前 Production 与已评测 Candidate；没有 Qualified Candidate 时保持真实空状态。</p></div></div><section className="panel experiment-query"><label className="question-input"><textarea aria-label="试验问题" placeholder="请输入你的问题…" maxLength={1000} value={question} onChange={event => setQuestion(event.target.value)} /></label><button className="primary" disabled={busy || !question.trim()} onClick={() => void ask()}><Send size={15} />{busy ? "正在发送…" : "发送"}</button></section><section className="experiment-results" aria-label="Pipeline 回答"><AnswerCard label="Production Baseline" run={baseline} onOpenCitation={onOpenCitation} empty="发送问题后显示当前 Production 回答。" /><AnswerCard label="Sandbox Candidate" run={candidate} onOpenCitation={onOpenCitation} empty="暂无 Qualified Candidate；先完成真实 Sandbox、Gate 与 Regression。" /></section></div>;
}

function AnswerCard({ label, run, onOpenCitation, empty }: { label: string; run: Run; onOpenCitation: (citation: Citation) => void; empty: string }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => { if (run.status !== "running") return; const timer = window.setInterval(() => setNow(Date.now()), 100); return () => window.clearInterval(timer); }, [run.status]);
  const elapsed = run.startedAt == null ? "" : `${((run.durationMs ?? Math.max(0, now - run.startedAt)) / 1000).toFixed(1)}s`;
  return <article className="experiment-answer-card"><div className="answer-card-header"><Badge tone="neutral">{label}</Badge><span className={run.status || "waiting"}>{run.status === "running" ? `正在回答 · ${elapsed}` : run.status === "completed" ? `已完成 · ${elapsed}` : run.status === "failed" ? `失败 · ${elapsed}` : "等待发送"}</span></div><div className="answer-scroll">{run.error ? <p className="error-notice" role="alert">预览失败：{run.error}</p> : run.result ? <><p>{run.result.answer}</p><p className="muted">版本 {run.result.version} · 延迟 {run.result.latency_ms} ms</p>{run.result.evidence?.map(item => <button className="document-link" key={item.chunk_id} onClick={() => onOpenCitation(item)}>{item.document} · P.{item.page_start} · {item.chunk_id}</button>)}</> : run.status === "running" ? <p className="muted">正在等待结果…</p> : <p className="muted">{empty}</p>}</div></article>;
}
