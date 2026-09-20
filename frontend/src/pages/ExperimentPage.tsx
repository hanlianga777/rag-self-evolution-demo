import { useEffect, useState } from "react";
import { Send } from "lucide-react";
import { errorMessage, postJson } from "../api";
import { Badge } from "../components/Primitives";
import type { Citation, PipelinePreview } from "../types";

type Run = { startedAt?: number; result?: PipelinePreview; error?: string };

export function ExperimentPage({ onOpenCitation }: { onOpenCitation: (citation: Citation) => void }) {
  const [question, setQuestion] = useState("");
  const [baseline, setBaseline] = useState<Run>({});
  const loading = Boolean(baseline.startedAt && !baseline.result && !baseline.error);
  const ask = () => {
    setBaseline({ startedAt: Date.now() });
    void postJson<PipelinePreview>("/api/preview/baseline", { question }).then(result => setBaseline({ result })).catch(reason => setBaseline({ error: errorMessage(reason) }));
  };
  return <div className="page experiment-page"><div className="page-title"><div><h1>问答试验</h1><p>Production Baseline 使用当前真实检索配置；候选方案必须先完成 Sandbox 评测才可比较。</p></div></div><section className="panel experiment-query"><label className="question-input"><textarea aria-label="试验问题" placeholder="请输入你的问题…" maxLength={1000} value={question} onChange={event => setQuestion(event.target.value)} /></label><div className="experiment-composer"><button className="primary" onClick={ask} disabled={loading || !question.trim()}>{loading ? "正在发送…" : <><Send size={15} />发送</>}</button></div></section><section className="experiment-results" aria-label="Pipeline 回答"><article className="experiment-answer-card"><div className="answer-card-header"><Badge tone="neutral">Production Baseline</Badge></div><div className="answer-scroll">{loading ? <Thinking startedAt={baseline.startedAt!} /> : baseline.error ? <p className="error-notice" role="alert">预览失败：{baseline.error}</p> : baseline.result ? <><Answer content={baseline.result.answer} />{baseline.result.evidence?.length ? <div className="evidence-list"><span>检索证据</span>{baseline.result.evidence.map(citation => <button className="document-link" key={citation.chunk_id} onClick={() => onOpenCitation(citation)}>{citation.document} · P.{citation.page_start} · {citation.chunk_id} · {citation.score.toFixed(2)}</button>)}</div> : null}</> : <p className="muted">发送问题后显示当前 Production Baseline 的回答。</p>}</div></article><article className="experiment-answer-card"><div className="answer-card-header"><Badge tone="neutral">Sandbox Candidate</Badge></div><div className="answer-scroll"><p className="muted">暂无可比较候选。请先完成真实 Evaluation、生成候选配置并运行独立 Sandbox 回归。</p></div></article><Parameters rows={baseline.result ? [["Production Version", baseline.result.version], ["回答模式", baseline.result.mode === "live" ? "DeepSeek" : "本地拒答"], ["处理延迟", `${baseline.result.latency_ms} ms`]] : [["Production Version", "baseline-v1"], ["状态", "Not Run"], ["处理延迟", "Not Run"]]} /><Parameters rows={[["候选状态", "Not Run"], ["独立 Sandbox", "Not Run"], ["比较结论", "暂无真实结果"]]} /></section></div>;
}

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
