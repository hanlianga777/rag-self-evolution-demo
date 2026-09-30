import { useEffect, useState } from "react";
import { Send } from "lucide-react";
import { errorMessage, getJson, postJson } from "../api";
import { Badge, CustomSelect, Section, ShortId, TechnicalDetails } from "../components/Primitives";
import { readSession, writeSession } from "../session";
import { ParameterDiff, ExecutionMetrics, parameterGroups, formatValue } from "../components/PipelineFields";
import type { Citation, PipelinePreview } from "../types";

type Run = { status?: "running" | "completed" | "failed"; startedAt?: number; durationMs?: number; result?: PipelinePreview; error?: string };
type Scheme = { id: string; label: string; evaluationId?: string; config?: Record<string, unknown>; sourceId?: string };

function validRun(run: Run): boolean { return !!run && !Array.isArray(run) && typeof run === "object" && run.status !== "running" && (!run.result || typeof run.result.answer === "string" && (!run.result.evidence || Array.isArray(run.result.evidence) && run.result.evidence.every(row => typeof row.chunk_id === "string"))); }

export function ExperimentPage({ data = {}, onOpenCitation }: { data?: any; onOpenCitation: (citation: Citation) => void; baselineLabel?: string }) {
  const versions: any[] = data.versions || [];
  const candidates: any[] = data.optimization?.candidates || [];
  const active = versions.find(version => version.status === "active");
  const previous = versions.find(version => version.id === active?.previous_version_id);
  const qualified = candidates.find(candidate => candidate.result?.qualification?.qualified && candidate.reasoning?.candidate_label !== "D");
  const baseline = data.evaluation || {};
  const schemes: Scheme[] = [{ id: "baseline", label: "Baseline", evaluationId: baseline.id, config: baseline.config, sourceId: baseline.id }, ...candidates.filter(candidate => candidate.reasoning?.candidate_label !== "D").map(candidate => ({ id: candidate.id, label: `Candidate ${candidate.reasoning?.candidate_label}`, evaluationId: candidate.result?.evaluation_run_id, config: candidate.config, sourceId: candidate.id })), ...versions.map(version => ({ id: version.id, label: version.id === active?.id ? version.provenance === "published" ? "当前 Production" : "当前 Baseline" : version.provenance === "bootstrap" ? "Baseline · 初始配置" : version.id === previous?.id ? "上一 Production" : version.id, evaluationId: version.evaluation_run_id || (version.provenance === "bootstrap" ? baseline.id : undefined), config: version.config, sourceId: version.snapshot?.candidate_id || version.snapshot?.source_candidate_id || version.id }))];
  const [saved] = useState(() => readSession("rag-qa-compare", { leftId: active?.provenance === "published" && previous ? previous.id : "baseline", rightId: active?.provenance === "published" ? active.id : qualified?.id || "", question: "", selectedCase: "", left: {} as Run, right: {} as Run, history: null as { left?: any; right?: any } | null }));
  const [leftId, setLeftId] = useState(typeof saved.leftId === "string" ? saved.leftId : "baseline");
  const [rightId, setRightId] = useState(typeof saved.rightId === "string" ? saved.rightId : "");
  const [question, setQuestion] = useState(typeof saved.question === "string" ? saved.question : "");
  const [selectedCase, setSelectedCase] = useState(typeof saved.selectedCase === "string" ? saved.selectedCase : "");
  const [left, setLeft] = useState<Run>(validRun(saved.left) ? saved.left : {});
  const [right, setRight] = useState<Run>(validRun(saved.right) ? saved.right : {});
  const [history, setHistory] = useState(saved.history && [saved.history.left, saved.history.right].every(item => !item || typeof item.model_answer === "string") ? saved.history : null);
  const [busy, setBusy] = useState(false);
  const badCases = (data.badCases || []).filter((item: any) => item.run_id === baseline.id);
  const leftScheme = schemes.find(item => item.id === leftId);
  const rightScheme = schemes.find(item => item.id === rightId);
  const fixedCase = badCases.find((row: any) => row.id === selectedCase);
  const sameSource = leftId === rightId || !!leftScheme?.sourceId && leftScheme.sourceId === rightScheme?.sourceId && Object.values(parameterGroups).flat().every(key => leftScheme.config?.[key] === rightScheme.config?.[key]);
  useEffect(() => writeSession("rag-qa-compare", { leftId, rightId, question, selectedCase, left, right, history }), [leftId, rightId, question, selectedCase, left, right, history]);
  const chooseLeft = (id: string) => { setLeftId(id); setLeft({}); setRight({}); setHistory(null); };
  const chooseRight = (id: string) => { setRightId(id); setLeft({}); setRight({}); setHistory(null); };

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
    if (!question.trim() || !leftId || !rightId || sameSource) return;
    const startedAt = Date.now(); setBusy(true); setHistory(null); setLeft({ status: "running", startedAt }); setRight({ status: "running", startedAt });
    const request = (schemeId: string, setRun: (run: Run) => void) => postJson<PipelinePreview>("/api/preview/scheme", { question, scheme_id: schemeId })
      .then(result => setRun({ status: "completed", startedAt, durationMs: Date.now() - startedAt, result }))
      .catch(reason => setRun({ status: "failed", startedAt, durationMs: Date.now() - startedAt, error: errorMessage(reason) }));
    await Promise.all([request(leftId, setLeft), request(rightId, setRight)]); setBusy(false);
  };
  return <div className="page experiment-page"><div className="page-title"><div><h2>方案对比</h2><p>同一个问题比较两个已保存方案。历史评测与实时预览分别标明来源。</p></div></div>
    <div className="scheme-selectors"><label>方案 A<CustomSelect ariaLabel="方案 A" value={leftId} onChange={chooseLeft} options={schemes.map(item => ({ value: item.id, label: item.label }))} /></label><span>对比</span><label>方案 B<CustomSelect ariaLabel="方案 B" value={rightId} onChange={chooseRight} options={[{ value: "", label: "选择方案" }, ...schemes.map(item => ({ value: item.id, label: item.label }))]} /></label></div>
    {badCases.length > 0 && <div className="fixed-case-control"><label>选择真实 Baseline Bad Case<CustomSelect ariaLabel="选择真实 Bad Case" value={selectedCase} onChange={setSelectedCase} placeholder="选择本轮 Baseline Bad Case" options={[{ value: "", label: "选择本轮 Baseline Bad Case" }, ...badCases.map((item: any) => ({ value: item.id, label: item.result?.question || "未记录问题", description: `${item.test_category || item.category || "Bad Case"}${item.category ? ` · ${item.category}` : ""}` }))]} /></label><button className="secondary" disabled={!selectedCase} onClick={() => void useBadCase()}>使用该问题</button>{fixedCase && <TechnicalDetails label="当前 Bad Case 技术信息">{JSON.stringify({ question_id: fixedCase.question_id, id: fixedCase.id }, null, 2)}</TechnicalDetails>}</div>}
    <section className="panel experiment-query"><label className="question-input"><textarea aria-label="试验问题" placeholder="请输入同一个真实问题…" maxLength={1000} value={question} onChange={event => setQuestion(event.target.value)} /></label><div className="query-action"><button className="primary" disabled={busy || !question.trim() || !rightId || sameSource} onClick={() => void ask()}><Send size={15} />{busy ? "正在回答…" : "运行实时对比"}</button></div></section>
    {sameSource && <p className="error-notice">请选择来源与配置有实际差异的方案；Candidate 与其发布版本不能自比。</p>}
    <Section title="方案参数差异"><ParameterDiff before={leftScheme?.config} after={rightScheme?.config} /></Section>
    <section className="experiment-results" aria-label="实时回答"><AnswerCard label={leftScheme?.label || "方案 A"} run={left} onOpenCitation={onOpenCitation} /><AnswerCard label={rightScheme?.label || "方案 B"} run={right} onOpenCitation={onOpenCitation} /></section>
    {history && <details className="panel history-evaluation"><summary>历史评测 <span>查看本题在已保存实验中的评分和证据</span></summary><div className="experiment-results"><HistoricalAnswer label={leftScheme?.label || "方案 A"} item={history.left} /><HistoricalAnswer label={rightScheme?.label || "方案 B"} item={history.right} /></div></details>}
  </div>;
}

function HistoricalAnswer({ label, item }: { label: string; item?: any }) {
  return <article className="experiment-answer-card"><div className="answer-card-header"><Badge tone="neutral">{label}</Badge><span>已保存的评测结果</span></div>{item ? <div className="answer-scroll"><MarkdownAnswer text={item.model_answer || "未记录"} /><p className="muted">题目 <ShortId value={item.question_id} /> · {item.passed ? "通过" : "未通过"}</p><details><summary>证据 / 引用 · {item.retrieved_chunks?.length || 0}</summary>{(item.retrieved_chunks || []).map((row: any) => <p key={row.chunk_id}>{row.document} · P.{row.page_start} · <ShortId value={row.chunk_id} /></p>)}</details></div> : <p className="muted">该方案没有对应的已保存逐题结果。</p>}</article>;
}

function AnswerCard({ label, run, onOpenCitation }: { label: string; run: Run; onOpenCitation: (citation: Citation) => void }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => { if (run.status !== "running") return; const timer = window.setInterval(() => setNow(Date.now()), 100); return () => window.clearInterval(timer); }, [run.status]);
  const elapsed = run.startedAt == null ? "" : `${((run.durationMs ?? Math.max(0, now - run.startedAt)) / 1000).toFixed(1)}s`;
  return <article className="experiment-answer-card"><div className="answer-card-header"><Badge tone="neutral">{label}</Badge><span className={run.status || "waiting"}>{run.status === "running" ? `实时预览中 · ${elapsed}` : run.status === "completed" ? `实时预览 · ${elapsed}` : run.status === "failed" ? `失败 · ${elapsed}` : "等待运行"}</span></div><div className="answer-scroll">{run.error ? <p className="error-notice" role="alert">预览失败：{run.error}</p> : run.result ? <><p className="muted">Prompt 策略 · {formatValue(run.result.config?.prompt_strategy)} · TopK {formatValue(run.result.config?.top_k)} · 延迟 {run.result.latency_ms} ms</p><MarkdownAnswer text={run.result.answer} /><ExecutionMetrics metrics={run.result} /><details><summary>证据 / 引用 · {run.result.evidence?.length || 0}</summary>{run.result.evidence?.map(item => <button className="document-link" key={item.chunk_id} onClick={() => onOpenCitation(item)}>{item.document} · P.{item.page_start} · {item.chunk_id}</button>)}</details></> : <p className="muted">运行后显示该方案的实时回答。</p>}</div></article>;
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
