import { useEffect, useState } from "react";
import { Send } from "lucide-react";
import { errorMessage, postJson } from "../api";
import { Badge } from "../components/Primitives";
import type { Citation, PipelinePreview } from "../types";

type Run = { startedAt?: number; result?: PipelinePreview; error?: string };

export function ExperimentPage({ onOpenCitation }: { onOpenCitation: (citation: Citation) => void }) {
  const [question, setQuestion] = useState("");
  const [baseline, setBaseline] = useState<Run>({});
  const [candidate, setCandidate] = useState<Run>({});
  const loading = Boolean(baseline.startedAt && !baseline.result && !baseline.error);
  const ask = () => {
    setBaseline({ startedAt: Date.now() });
    setCandidate({ startedAt: Date.now() });
    void Promise.all([postJson<PipelinePreview>("/api/preview/baseline", { question }), postJson<PipelinePreview>("/api/preview/candidate", { question })]).then(([baselineResult, candidateResult]) => { setBaseline({ result: baselineResult }); setCandidate({ result: candidateResult }); }).catch(reason => { const error = errorMessage(reason); setBaseline({ error }); setCandidate({ error }); });
  };
  return <div className="page experiment-page"><div className="page-title"><div><h1>问答试验</h1><p>Production Baseline 与已评测 Qualified Candidate 分别以真实配置运行；不会复制 Baseline 回答。</p></div></div><section className="panel experiment-query"><label className="question-input"><textarea aria-label="试验问题" placeholder="请输入你的问题…" maxLength={1000} value={question} onChange={event => setQuestion(event.target.value)} /></label><div className="experiment-composer"><button className="primary" onClick={ask} disabled={loading || !question.trim()}>{loading ? "正在发送…" : <><Send size={15} />发送</>}</button></div></section><section className="experiment-results" aria-label="Pipeline 回答"><AnswerCard label="Production Baseline" run={baseline} loading={loading} onOpenCitation={onOpenCitation} empty="发送问题后显示当前 Production Baseline 的回答。" /><AnswerCard label="Sandbox Candidate" run={candidate} loading={loading} onOpenCitation={onOpenCitation} empty="暂无 Qualified Candidate；先完成真实 Sandbox、Gate 与 Regression。" /><Parameters rows={baseline.result ? [["Production Version", baseline.result.version], ["回答模式", baseline.result.mode === "live" ? "DeepSeek" : "本地拒答"], ["处理延迟", `${baseline.result.latency_ms} ms`]] : [["Production Version", "baseline-v1"], ["状态", "Not Run"], ["处理延迟", "Not Run"]]} /><Parameters rows={candidate.result ? [["Candidate", candidate.result.version || "Not Run"], ["独立 Sandbox", candidate.result.status || "Not Run"], ["处理延迟", `${candidate.result.latency_ms} ms`]] : [["候选状态", "Not Run"], ["独立 Sandbox", "Not Run"], ["比较结论", "暂无真实结果"]]} /></section></div>;
}

function AnswerCard({ label, run, loading, onOpenCitation, empty }: { label: string; run: Run; loading: boolean; onOpenCitation: (citation: Citation) => void; empty: string }) { return <article className="experiment-answer-card"><div className="answer-card-header"><Badge tone="neutral">{label}</Badge></div><div className="answer-scroll">{loading ? <Thinking startedAt={run.startedAt!} /> : run.error ? <p className="error-notice" role="alert">预览失败：{run.error}</p> : run.result ? <><Answer content={run.result.answer} />{run.result.evidence?.length ? <div className="evidence-list"><span>检索证据</span>{run.result.evidence.map(citation => <button className="document-link" key={citation.chunk_id} onClick={() => onOpenCitation(citation)}>{citation.document} · P.{citation.page_start} · {citation.chunk_id} · {citation.score.toFixed(2)}</button>)}</div> : null}</> : <p className="muted">{empty}</p>}</div></article>; }

function Answer({ content }: { content: string }) {
  const [length, setLength] = useState(1);
  useEffect(() => { setLength(1); const timer = window.setInterval(() => setLength(current => Math.min(current + 1, content.length)), 18); return () => window.clearInterval(timer); }, [content]);
  return <div className="answer-content" aria-live="polite">{content.slice(0, length).split(/\n+/).filter(Boolean).map((line, index) => <p key={index}>{line}</p>)}{length < content.length && <span className="typing-cursor" aria-hidden="true">|</span>}</div>;
}

function Thinking({ startedAt }: { startedAt: number }) {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => { const timer = window.setInterval(() => setElapsed((Date.now() - startedAt) / 1000), 100); return () => window.clearInterval(timer); }, [startedAt]);
  return <div className="experiment-thinking" aria-live="polite"><time>{elapsed.toFixed(1)} 秒</time><p>正在思考…</p></div>;
}

function Parameters({ rows }: { rows: string[][] }) { return <dl className="run-parameters">{rows.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value || "Not Run"}</dd></div>)}</dl>; }
