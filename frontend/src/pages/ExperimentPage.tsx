import { useState } from "react";
import { Send } from "lucide-react";
import { errorMessage, postJson } from "../api";
import { Badge } from "../components/Primitives";
import type { Citation, PipelinePreview } from "../types";

type Run = { result?: PipelinePreview; error?: string };

export function ExperimentPage({ onOpenCitation }: { onOpenCitation: (citation: Citation) => void }) {
  const [question, setQuestion] = useState(""); const [baseline, setBaseline] = useState<Run>({}); const [candidate, setCandidate] = useState<Run>({}); const [busy, setBusy] = useState(false);
  const ask = async () => { setBusy(true); setBaseline({}); setCandidate({}); try { const [base, sandbox] = await Promise.all([postJson<PipelinePreview>("/api/preview/baseline", { question }), postJson<PipelinePreview>("/api/preview/candidate", { question })]); setBaseline({ result: base }); setCandidate({ result: sandbox }); } catch (reason) { const error = errorMessage(reason); setBaseline({ error }); setCandidate({ error }); } finally { setBusy(false); } };
  return <div className="page experiment-page"><div className="page-title"><div><h1>Before / After 验证</h1><p>同一问题分别调用当前 Production 与已评测 Candidate；没有 Qualified Candidate 时保持真实空状态。</p></div></div><section className="panel experiment-query"><label className="question-input"><textarea aria-label="试验问题" placeholder="请输入你的问题…" maxLength={1000} value={question} onChange={event => setQuestion(event.target.value)} /></label><button className="primary" disabled={busy || !question.trim()} onClick={() => void ask()}><Send size={15} />{busy ? "正在发送…" : "发送"}</button></section><section className="experiment-results" aria-label="Pipeline 回答"><AnswerCard label="Production Baseline" run={baseline} onOpenCitation={onOpenCitation} empty="发送问题后显示当前 Production 回答。" /><AnswerCard label="Sandbox Candidate" run={candidate} onOpenCitation={onOpenCitation} empty="暂无 Qualified Candidate；先完成真实 Sandbox、Gate 与 Regression。" /></section></div>;
}

function AnswerCard({ label, run, onOpenCitation, empty }: { label: string; run: Run; onOpenCitation: (citation: Citation) => void; empty: string }) { return <article className="experiment-answer-card"><div className="answer-card-header"><Badge tone="neutral">{label}</Badge></div><div className="answer-scroll">{run.error ? <p className="error-notice" role="alert">预览失败：{run.error}</p> : run.result ? <><p>{run.result.answer}</p><p className="muted">版本 {run.result.version} · 延迟 {run.result.latency_ms} ms</p>{run.result.evidence?.map(item => <button className="document-link" key={item.chunk_id} onClick={() => onOpenCitation(item)}>{item.document} · P.{item.page_start} · {item.chunk_id}</button>)}</> : <p className="muted">{empty}</p>}</div></article>; }
