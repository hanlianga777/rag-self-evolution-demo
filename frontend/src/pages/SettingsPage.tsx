import { useEffect, useState } from "react";
import { errorMessage, getJson, postJson } from "../api";
import { Badge, Section, ShortId, Status } from "../components/Primitives";
import { ExecutionMetrics, formatValue, parameterNames } from "../components/PipelineFields";
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
  const displayValue = (value: unknown) => typeof value === "string" && ["未采集", "未实现", "未配置"].includes(value) ? <Badge tone="neutral">{value}</Badge> : formatValue(value);
  const groups: { title: string; rows: [string, unknown, boolean][] }[] = [
    { title: "文档接入与解析", rows: [["解析器", unique("parser"), false], ["OCR", unique("ocr"), false], ["Chunk 策略", unique("chunk_strategy"), false], ["父 Chunk 大小", "未实现", false], ["子 Chunk 大小", "未实现", false], ["Chunk 目标长度", index.chunk_target_tokens, false], ["重叠长度", index.chunk_overlap_tokens, false]] },
    { title: "Embedding 与索引", rows: [["Embedding 模型", index.embedding_model, false], ["向量维度", "未采集", false], ["索引类型", index.vector_index, false]] },
    { title: "Query", rows: [["Query Rewrite", config.query_rewrite, true], ["MultiQuery", config.multi_query, true], ["HyDE", config.hyde, true], ["Query 拆解", "未实现", false]] },
    { title: "检索", rows: [["CandidateK", config.candidate_k, true], ["TopK", config.top_k, true], ["MinScore", config.min_score, true], ["Hybrid", config.hybrid_search, true], ["Hybrid 权重", config.hybrid_alpha, true], ["元数据筛选", config.metadata_filter, true], ["别名映射", config.alias_mapping, true]] },
    { title: "Rerank", rows: [["Rerank", config.rerank, true], ["Rerank 模型", "无独立模型 · 轻量二阶段重排", false], ["Rerank TopN", "未配置", false]] },
    { title: "生成", rows: [["生成模型", r.model, false], ["Prompt 策略", config.prompt_strategy, true], ["Temperature", data.evaluation?.judge?.execution_snapshot?.temperature, false], ["检索最大 Token 数", "未采集", false]] },
    { title: "评测", rows: [["Judge 模型", data.evaluation?.judge?.model, false], ["Golden Snapshot", data.evaluation?.dataset_version_id, false], ["指标版本", data.evaluation?.judge?.scoring_policy, false], ["Hard Gate 数", data.evaluation?.result?.gates?.total, false]] },
  ];
  const verify = async () => {
    setChecking(true); setError(""); setProbe(null);
    try { setProbe(await operation.run("验证 DeepSeek Provider", async () => { const result: any = await postJson("/api/ai-readiness/probe"); if (result.probe === "failed") throw new Error(result.last_probe?.reason || "Provider 连接失败"); return result; })); }
    catch (reason) { setError(errorMessage(reason)); }
    finally { setChecking(false); }
  };
  return <div className="page settings-page">
    <div className="page-title"><div><h1>RAG Pipeline 配置</h1><p>当前有效配置按处理阶段展示；Agent 只能修改冻结 Search Space 内的字段。</p></div><ShortId value={pipeline?.active_version_id} /></div>
    <div className="environment-chips"><span>LLM <strong>{r.model || "未配置"}</strong></span><span>Parser <strong>{unique("parser")}</strong></span><span>Embedding <strong>{index.embedding_model || "未采集"}</strong></span><span>Rerank <strong>{formatValue(config.rerank)}</strong></span><span>知识库 <strong>{docs.reduce((sum: number, doc: any) => sum + (doc.chunks || 0), 0)} 个 Chunk</strong></span><span>Provider <strong>{displayText(r.status || "未验证")}</strong></span></div>
    <Section title="最近实际问答阶段"><ExecutionMetrics metrics={pipeline?.last_execution_metrics} /></Section>
    <Section title="RAG Pipeline 流程"><div className="pipeline-flow">{[["文档接入", `${unique("parser")} · ${unique("ocr")}`], ["Embedding", index.embedding_model || "未采集"], ["Query", `Rewrite ${formatValue(config.query_rewrite)} · MultiQuery ${formatValue(config.multi_query)}`], ["检索", `CandidateK ${formatValue(config.candidate_k)} · TopK ${formatValue(config.top_k)}`], ["Rerank", formatValue(config.rerank)], ["生成", `${formatValue(config.prompt_strategy)} · ${r.model || "未配置"}`], ["评测", `${data.evaluation?.result?.gates?.total ?? "未采集"} 项 Hard Gate`]].map(([label, value]) => <div key={label}><small>{label}</small><strong>{value}</strong></div>)}</div></Section>
    {error && <p className="error-notice" role="alert">验证失败：{error}</p>}
    <div className="config-groups">{groups.map(group => <Section key={group.title} title={group.title}><div className="parameter-list">{group.rows.map(([name, value, tunable]) => { const key = Object.keys(parameterNames).find(item => parameterNames[item] === name); const allowed = key ? !!pipeline?.search_space?.[key] : false; return <div key={name}><span>{name}</span><strong>{displayValue(value)}</strong><Badge tone={allowed || !pipeline && tunable ? "accent" : "neutral"}>{allowed || !pipeline && tunable ? "Agent 可调" : "固定"}</Badge></div>; })}</div></Section>)}</div>
    <Section title="Provider"><p className="muted">当前状态：<Status value={r.status || "not_run"} />。验证连接会调用 DeepSeek，请仅在需要时手动执行。</p><button className="secondary" onClick={() => void verify()} disabled={checking}>{checking ? "正在验证…" : "验证服务连接"}</button>{r.last_probe && <p className="muted">最后验证：{displayText(r.last_probe.status)}{r.last_probe.latency_ms != null ? ` · ${r.last_probe.latency_ms} ms` : ""}</p>}</Section>
  </div>;
}
