import { useEffect, useState } from "react";
import { errorMessage, getJson, postJson } from "../api";
import { Badge, Section, Status } from "../components/Primitives";
import { formatValue, parameterNames } from "../components/PipelineFields";
import { displayText } from "../display";
import { useOperation } from "../operation";

export function SettingsPage({ data }: { data: any }) {
  const operation = useOperation();
  const [pipeline, setPipeline] = useState<any>(null);
  const [probe, setProbe] = useState<any>(null);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { void getJson("/api/pipeline").then(setPipeline).catch(reason => setError(errorMessage(reason))); }, []);
  const r = probe || data.readiness || {};
  const config = pipeline?.config || data.versions?.find((version: any) => version.status === "active")?.config || data.evaluation?.config || {};
  const index = pipeline?.index || {};
  const docs = data.documents || [];
  const unique = (key: string) => [...new Set(docs.map((doc: any) => doc[key]).filter(Boolean))].join("；") || "未采集";
  const groups: { title: string; rows: [string, unknown, boolean][] }[] = [
    { title: "Ingest / Parsing", rows: [["Parser", unique("parser"), false], ["OCR", unique("ocr"), false], ["Chunk Strategy", unique("chunk_strategy"), false], ["Parent Chunk Size", "未实现", false], ["Child Chunk Size", "未实现", false], ["Chunk Target", index.chunk_target_tokens, false], ["Overlap", index.chunk_overlap_tokens, false]] },
    { title: "Embedding / Index", rows: [["Embedding Model", index.embedding_model, false], ["Dimension", "未采集", false], ["Index Type", index.vector_index, false]] },
    { title: "Query", rows: [["Query Rewrite", config.query_rewrite, true], ["MultiQuery", config.multi_query, true], ["HyDE", config.hyde, true], ["Query Decompose", "未实现", false]] },
    { title: "Retrieval", rows: [["CandidateK", config.candidate_k, true], ["TopK", config.top_k, true], ["MinScore", config.min_score, true], ["Hybrid", config.hybrid_search, true], ["Hybrid Alpha", config.hybrid_alpha, true], ["Metadata Filter", config.metadata_filter, true], ["Alias Mapping", config.alias_mapping, true]] },
    { title: "Rerank", rows: [["Rerank", config.rerank, true], ["Rerank Model", "无独立模型 · 轻量二阶段重排", false], ["Rerank TopN", "未配置", false]] },
    { title: "Generation", rows: [["Generation Model", r.model, false], ["Prompt Strategy", config.prompt_strategy, true], ["Temperature", data.evaluation?.judge?.execution_snapshot?.temperature, false], ["Retrieval MaxTokens", "未采集", false]] },
    { title: "Evaluation", rows: [["Judge Model", data.evaluation?.judge?.model, false], ["Golden Snapshot", data.evaluation?.dataset_version_id, false], ["Metrics Version", data.evaluation?.judge?.scoring_policy, false], ["Hard Gates", data.evaluation?.result?.gates?.total, false]] },
  ];
  const verify = async () => {
    setChecking(true); setError(""); setProbe(null);
    try { setProbe(await operation.run("验证 DeepSeek Provider", async () => { const result: any = await postJson("/api/ai-readiness/probe"); if (result.probe === "failed") throw new Error(result.last_probe?.reason || "Provider 连接失败"); return result; })); }
    catch (reason) { setError(errorMessage(reason)); }
    finally { setChecking(false); }
  };
  return <div className="page settings-page">
    <div className="page-title"><div><h1>RAG Pipeline Config</h1><p>当前有效配置按处理阶段展示；Agent 只能修改冻结 Search Space 内的字段。</p></div><Badge tone="neutral">{pipeline?.active_version_id || "当前配置"}</Badge></div>
    <div className="environment-chips"><span>LLM <strong>{r.model || "未配置"}</strong></span><span>Parser <strong>{unique("parser")}</strong></span><span>Embedding <strong>{index.embedding_model || "未采集"}</strong></span><span>Rerank <strong>{formatValue(config.rerank)}</strong></span><span>Corpus <strong>{docs.reduce((sum: number, doc: any) => sum + (doc.chunks || 0), 0)} Chunks</strong></span><span>Provider <strong>{displayText(r.status || "未验证")}</strong></span></div>
    <Section title="RAG Pipeline Flow"><div className="pipeline-flow">{[["Query", "输入问题"], ["Query Processing", `Rewrite ${formatValue(config.query_rewrite)}`], ["Candidate Retrieval", `CandidateK ${formatValue(config.candidate_k)}`], ["Hybrid", `${formatValue(config.hybrid_search)} / ${formatValue(config.hybrid_alpha)}`], ["Rerank", formatValue(config.rerank)], ["MinScore", formatValue(config.min_score)], ["TopK", formatValue(config.top_k)], ["Generation", `${formatValue(config.prompt_strategy)} / ${r.model || "未配置"}`]].map(([label, value]) => <div key={label}><small>{label}</small><strong>{value}</strong></div>)}</div></Section>
    {error && <p className="error-notice" role="alert">验证失败：{error}</p>}
    <div className="config-groups">{groups.map(group => <Section key={group.title} title={group.title}><div className="parameter-list">{group.rows.map(([name, value, tunable]) => { const key = Object.keys(parameterNames).find(item => parameterNames[item] === name); const allowed = key ? !!pipeline?.search_space?.[key] : false; return <div key={name}><span>{name}</span><strong>{formatValue(value)}</strong><Badge tone={allowed || !pipeline && tunable ? "accent" : "neutral"}>{allowed || !pipeline && tunable ? "Agent Tunable" : "Fixed"}</Badge></div>; })}</div></Section>)}</div>
    <Section title="Provider"><p className="muted">当前状态：<Status value={r.status || "not_run"} />。验证连接会调用 DeepSeek，请仅在需要时手动执行。</p><button className="secondary" onClick={() => void verify()} disabled={checking}>{checking ? "正在验证…" : "验证 Provider 连接"}</button>{r.last_probe && <p className="muted">最后验证：{displayText(r.last_probe.status)}{r.last_probe.latency_ms != null ? ` · ${r.last_probe.latency_ms} ms` : ""}</p>}</Section>
  </div>;
}
