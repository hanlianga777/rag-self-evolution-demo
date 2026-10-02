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
  useEffect(() => { let cancelled = false; void getJson("/api/pipeline").then(value => { if (!cancelled) setPipeline(value); }).catch(reason => { if (!cancelled) setError(errorMessage(reason)); }); return () => { cancelled = true; }; }, []);
  const r = probe || data.readiness || {};
  const config = pipeline?.config || data.versions?.find((version: any) => version.status === "active")?.config || data.evaluation?.config || {};
  const index = pipeline?.index || {};
  const docs = data.documents || [];
  const unique = (key: string) => [...new Set(docs.map((doc: any) => doc[key]).filter(Boolean))].join("；") || "未采集";
  const displayValue = (value: unknown) => typeof value === "string" && ["未采集", "未实现", "未配置"].includes(value) ? <Badge tone="neutral">{value}</Badge> : formatValue(value);
  const groups: { title: string; rows: [string, unknown, boolean][] }[] = [
    { title: "Document Processing", rows: [["解析器", unique("parser"), false], ["OCR", unique("ocr"), false], ["Chunk 策略", unique("chunk_strategy"), false], ["父 Chunk 大小", "未实现", false], ["子 Chunk 大小", "未实现", false], ["Chunk 目标长度", index.chunk_target_tokens, false], ["重叠长度", index.chunk_overlap_tokens, false]] },
    { title: "Embedding & Index", rows: [["Embedding 模型", index.embedding_model, false], ["向量维度", "未采集", false], ["索引类型", index.vector_index, false], ["全文引擎能力", index.full_text?.supported ? "支持" : "未采集", false], ["全文产物状态", index.full_text?.status === "ready" ? "已就绪" : index.full_text?.status === "invalid" ? "无效，需检查产物" : "未采集", false], ["全文解析覆盖", index.full_text?.coverage?.status === "complete" ? "已采集全部页" : index.full_text?.coverage?.status === "insufficient" ? "覆盖不足，不能证明原文缺失" : "未采集", false]] },
    { title: "Query Processing", rows: [["Query Rewrite", config.query_rewrite, true], ["MultiQuery", config.multi_query, true], ["HyDE", config.hyde, true], ["别名映射", config.alias_mapping, true]] },
    { title: "Retrieval & Ranking", rows: [["CandidateK", config.candidate_k, true], ["TopK", config.top_k, true], ["MinScore", config.min_score, true], ["Hybrid", config.hybrid_search, true], ["Hybrid 权重", config.hybrid_alpha, true], ["元数据筛选", config.metadata_filter, true], ["Rerank", config.rerank, true]] },
    { title: "Generation", rows: [["生成模型", r.model, false], ["Prompt 策略", config.prompt_strategy, true], ["Temperature", data.evaluation?.judge?.execution_snapshot?.temperature, false], ["检索最大 Token 数", "未采集", false]] },
    { title: "Evaluation Configuration", rows: [["Judge 模型", data.evaluation?.judge?.model, false], ["Golden Snapshot", data.evaluation?.dataset_version_id, false], ["指标版本", data.evaluation?.judge?.scoring_policy, false], ["Hard Gate 数", data.evaluation?.result?.gates?.total, false]] },
  ];
  const verify = async () => {
    setChecking(true); setError(""); setProbe(null);
    try { setProbe(await operation.run("验证 DeepSeek Provider", async () => { const result: any = await postJson("/api/ai-readiness/probe"); if (result.probe === "failed") throw new Error(result.last_probe?.reason || "Provider 连接失败"); return result; })); }
    catch (reason) { setError(errorMessage(reason)); }
    finally { setChecking(false); }
  };
  return <div className="page settings-page">
    <div className="page-title"><div><h1>Pipeline 配置</h1><p>当前有效配置与 Agent 修改权限来自冻结规则源。</p></div></div>
    <Section title="Knowledge Preparation"><div className="light-stepper"><span>Parse / OCR</span><span>Chunk</span><span>Embedding</span><span>Index</span></div></Section>
    <Section title="Online QA"><div className="light-stepper"><span>Query Processing</span><span>Retrieval</span><span>Rerank & Context</span><span>Generation</span></div></Section>
    {error && <p className="error-notice" role="alert">验证失败：{error}</p>}
    <div className="config-groups">{groups.map(group => <Section key={group.title} title={group.title}>{group.title === "Evaluation Configuration" && <p className="muted">Evaluation 不属于每次 Production 问答 Runtime。</p>}<div className="parameter-list">{group.rows.map(([name, value]) => { const key = Object.keys(parameterNames).find(item => parameterNames[item] === name); const allowed = key ? !!pipeline?.search_space?.[key] : false; return <div key={name}><span>{name}</span><strong>{displayValue(value)}</strong><Badge tone={allowed ? "accent" : "neutral"}>{allowed ? "Agent 可调" : "Frozen"}</Badge></div>; })}</div></Section>)}</div>
    <Section title="Provider"><p className="muted">当前状态：<Status value={r.status || "not_run"} />。验证连接会调用 DeepSeek，请仅在需要时手动执行。</p><button className="secondary" onClick={() => void verify()} disabled={checking}>{checking ? "正在验证…" : "验证服务连接"}</button>{r.last_probe && <p className="muted">最后验证：{displayText(r.last_probe.status)}{r.last_probe.latency_ms != null ? ` · ${r.last_probe.latency_ms} ms` : ""}</p>}</Section>
  </div>;
}
