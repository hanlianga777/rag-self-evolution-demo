import { useEffect, useState } from "react";
import { Send } from "lucide-react";
import { errorMessage, postJson } from "../api";
import { Badge } from "../components/Primitives";
import type { Citation, PipelinePreview } from "../types";

const pipelineOptions = [["v1.0", "Baseline · v1.0"], ["v1.1", "Candidate A · v1.1"], ["v1.2", "Candidate B · v1.2"], ["v1.3", "Candidate C · v1.3"]];
type PipelineRun = { startedAt?: number; result?: PipelinePreview; error?: string };

const isThinking = (run: PipelineRun) => !!run.startedAt && !run.result && !run.error;

export function ExperimentPage({ onOpenCitation }: { onOpenCitation: (citation: Citation) => void }) {
  const [question, setQuestion] = useState(""); const [baseline, setBaseline] = useState<PipelineRun>({}); const [candidate, setCandidate] = useState<PipelineRun>({}); const [pipelineA, setPipelineA] = useState("v1.0"); const [pipelineB, setPipelineB] = useState("v1.2");
  const loading = isThinking(baseline) || isThinking(candidate);
  const ask = () => {
    const startedAt = Date.now();
    setBaseline({ startedAt }); setCandidate({ startedAt });
    void postJson<PipelinePreview>("/api/preview/baseline", { question }).then(result => setBaseline({ result })).catch(reason => setBaseline({ error: errorMessage(reason) }));
    void postJson<PipelinePreview>("/api/preview/candidate", { question }).then(result => setCandidate({ result })).catch(reason => setCandidate({ error: errorMessage(reason) }));
  };
  const baselineRows = baseline.result ? [["版本", baseline.result.version], ["生成模型", "基线展示"], ["处理延迟", `${baseline.result.latency_ms} ms`], ["Top K", "—"], ["检索状态", "未运行独立检索"]] : [["版本", "v1.0"], ["生成模型", "基线展示"], ["处理延迟", isThinking(baseline) ? "正在思考" : "未运行"], ["Top K", "—"], ["检索状态", baseline.error ? "本次失败" : "等待提问"]];
  const candidateRows = candidate.result ? [["版本", candidate.result.version], ["回答模式", candidate.result.mode === "live" ? "服务回答" : "本地响应"], ["生成模型", candidate.result.model ?? "未返回有效模型回答"], ["处理延迟", `${candidate.result.latency_ms} ms`], ["Top K", "4"], ["检索", "BGE + FAISS"], ["处理说明", candidate.result.fallback_reason || "无"]] : [["版本", "v1.2"], ["回答模式", "等待提问"], ["生成模型", "未运行"], ["处理延迟", isThinking(candidate) ? "正在思考" : "未运行"], ["Top K", "未运行"], ["检索", "未运行"], ["处理说明", candidate.error || "无"]];
  return <div className="page experiment-page"><div className="page-title"><div><h1>问答试验</h1></div></div><section className="panel experiment-query"><label className="question-input"><textarea aria-label="试验问题" placeholder="请输入你的问题…" maxLength={1000} value={question} onChange={event => setQuestion(event.target.value)} /></label><div className="experiment-composer"><button className="primary" onClick={ask} disabled={loading || !question.trim()}>{loading ? "正在发送…" : <><Send size={15} />发送</>}</button></div></section><section className="experiment-pipelines" aria-label="对比 Pipeline"><label className="pipeline-selector"><select aria-label="Pipeline A 演示配置" value={pipelineA} onChange={event => setPipelineA(event.target.value)}>{pipelineOptions.slice(0, 2).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><label className="pipeline-selector"><select aria-label="Pipeline B 演示配置" value={pipelineB} onChange={event => setPipelineB(event.target.value)}>{pipelineOptions.slice(2).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label></section><section className="experiment-results" aria-label="Pipeline 回答"><article className="experiment-answer-card"><div className="answer-card-header"><Badge tone="neutral">Pipeline A · Baseline</Badge></div><div className="answer-scroll">{isThinking(baseline) ? <ExperimentThinking startedAt={baseline.startedAt!} /> : baseline.error ? <p className="error-notice" role="alert">预览失败：{baseline.error}。请重试。</p> : baseline.result ? <Answer content={baseline.result.answer} /> : <p className="muted">发送问题后显示 Pipeline A 的回答。</p>}</div></article><article className="experiment-answer-card"><div className="answer-card-header"><Badge tone="neutral">Pipeline B · 候选方案 B</Badge></div><div className="answer-scroll">{isThinking(candidate) ? <ExperimentThinking startedAt={candidate.startedAt!} /> : candidate.error ? <p className="error-notice" role="alert">预览失败：{candidate.error}。请重试。</p> : candidate.result ? <><Answer content={candidate.result.answer} />{candidate.result.evidence?.length ? <div className="evidence-list"><span>检索证据</span>{candidate.result.evidence.map(citation => <button className="document-link" key={citation.chunk_id} onClick={() => onOpenCitation(citation)}>{citation.document} · P.{citation.page_start} · {citation.chunk_id} · {citation.score.toFixed(2)}</button>)}</div> : null}</> : <p className="muted">发送问题后显示 Pipeline B 的回答。</p>}</div></article><Parameters rows={baselineRows} /><Parameters rows={candidateRows} /></section></div>;
}

function Answer({ content }: { content: string }) {
  const [length, setLength] = useState(1);
  useEffect(() => { setLength(1); const timer = window.setInterval(() => setLength(current => Math.min(current + 1, content.length)), 18); return () => window.clearInterval(timer); }, [content]);
  const visible = content.slice(0, length);
  const lines = visible.replace(/(\d+\.\s+\*\*)/g, "\n$1").replace(/\s+-\s+/g, "\n- ").split(/\n+/).filter(Boolean);
  return <div className="answer-content" aria-live="polite">{lines.map((line, index) => <p key={index}>{line.split(/(\*\*[^*]+\*\*)/g).map((part, partIndex) => part.startsWith("**") ? <strong key={partIndex}>{part.slice(2, -2)}</strong> : part)}</p>)}{length < content.length && <span className="typing-cursor" aria-hidden="true">|</span>}</div>;
}

function ExperimentThinking({ startedAt }: { startedAt: number }) {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => { const timer = window.setInterval(() => setElapsed((Date.now() - startedAt) / 1000), 100); return () => window.clearInterval(timer); }, [startedAt]);
  return <div className="experiment-thinking" aria-live="polite"><time>{elapsed.toFixed(1)} 秒</time><p>正在思考<span className="thinking-dots" aria-hidden="true">...</span></p></div>;
}

function Parameters({ rows }: { rows: string[][] }) { return <dl className="run-parameters">{rows.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>; }
