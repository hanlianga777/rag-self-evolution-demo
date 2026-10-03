import { useEffect, useState } from "react";
import { errorMessage, getJson, postJson } from "../api";
import { Badge, Section, Status } from "../components/Primitives";
import { Drawer } from "../components/Dialog";
import { formatValue, parameterNames, SearchSpaceTable } from "../components/PipelineFields";
import { displayText } from "../display";
import { useOperation } from "../operation";

export function SettingsPage({ data }: { data: any }) {
  const operation = useOperation();
  const [pipeline, setPipeline] = useState<any>(null);
  const [probe, setProbe] = useState<any>(null);
  const [checking, setChecking] = useState(false);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [spaceOpen, setSpaceOpen] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { let cancelled = false; void getJson("/api/pipeline").then(value => { if (!cancelled) setPipeline(value); }).catch(reason => { if (!cancelled) setError(errorMessage(reason)); }); return () => { cancelled = true; }; }, []);
  const r = probe || data.readiness || {};
  const active = data.versions?.find((version: any) => version.status === "active");
  const config = pipeline?.config || active?.config || data.evaluation?.config || {};
  const index = pipeline?.index || {};
  const docs = data.documents || [];
  const unique = (key: string) => [...new Set(docs.map((doc: any) => doc[key]).filter(Boolean))].join("；");
  const execution = data.evaluation?.judge?.execution_snapshot || {};
  const generationModel = active?.snapshot?.generation_model || execution.generation_model;
  const generationTemperature = active?.snapshot?.temperature ?? (execution.generation_model && execution.generation_model === generationModel ? execution.temperature : undefined);
  const available = (value: unknown) => value != null && value !== "" && !["未采集", "未实现", "未配置", "未记录", "待解析", "待构建"].includes(String(value));
  const groups: { title: string; rows: [string, string, unknown][] }[] = [
    { title: "知识处理配置", rows: [["parser", "解析器", unique("parser")], ["ocr", "OCR Fallback", unique("ocr")], ["chunk_method", "Chunk 策略", unique("chunk_strategy")], ["chunk_size", "Chunk 目标长度", index.chunk_target_tokens], ["chunk_overlap", "重叠长度", index.chunk_overlap_tokens], ["embedding_model", "Embedding 模型", index.embedding_model], ["dimension", "向量维度", index.dimension], ["vector_index", "索引类型", index.vector_index], ["metadata", "Metadata", "section_path · page_start / page_end"]] },
    { title: "检索策略", rows: ["query_rewrite", "multi_query", "hyde", "alias_mapping", "candidate_k", "top_k", "min_score", "hybrid_search", "hybrid_alpha", "metadata_filter", "rerank"].map(key => [key, parameterNames[key] || key, config[key]]) },
    { title: "生成策略", rows: [["prompt_strategy", "Prompt 策略", config.prompt_strategy], ["generation_model", "Generation Model", generationModel], ["temperature", "Temperature", generationTemperature], ["max_tokens", "Max Tokens", active?.snapshot?.max_tokens ?? (execution.generation_model === generationModel ? execution.max_tokens : undefined)]] },
    { title: "评测配置", rows: [["golden_dataset", "Golden Dataset", data.workspace?.current_golden_id || data.evaluation?.dataset_version_id], ["judge", "Judge 模型", data.evaluation?.judge?.model], ["metrics_version", "指标版本", data.evaluation?.judge?.scoring_policy], ["hard_gate", "Hard Gate 数", data.evaluation?.result?.gates?.total], ["regression", "Regression", data.evaluation?.result?.regression?.status]] },
  ];
  const verify = async () => {
    setChecking(true); setError(""); setProbe(null);
    try { setProbe(await operation.run("验证 DeepSeek Provider", async () => { const result: any = await postJson("/api/ai-readiness/probe"); if (result.probe === "failed") throw new Error(result.last_probe?.reason || "Provider 连接失败"); return result; })); }
    catch (reason) { setError(errorMessage(reason)); }
    finally { setChecking(false); }
  };
  return <div className="page settings-page">
    <div className="page-title"><div><h1>Pipeline 配置</h1><p>说明当前 RAG 的关键策略，以及 Frozen 与 Agent 可调的参数边界。</p></div><div className="header-actions"><button className="secondary" onClick={() => setSpaceOpen(true)}>Search Space · {Object.keys(pipeline?.search_space || {}).length}</button><button className="text-button" onClick={() => setDetailsOpen(true)}>技术详情</button></div></div>
    <p className="muted pipeline-boundary">Agent 仅在受控 Search Space 内调优；固定知识处理、模型与评测规则。</p>
    {error && <p className="error-notice" role="alert">请求失败：{error}</p>}
    <div className="config-groups">{groups.map(group => <div className="pipeline-group" key={group.title}><Section title={group.title}><div className="parameter-list">{group.rows.filter(([, , value]) => available(value)).map(([key, name, value]) => { const allowed = Object.prototype.hasOwnProperty.call(pipeline?.search_space || {}, key); return <div key={key} data-parameter={key}><span>{name}</span><strong>{formatValue(value)}</strong>{pipeline?.search_space && <Badge tone={allowed ? "accent" : "neutral"}>{allowed ? "Agent 可调" : "Frozen"}</Badge>}</div>; })}</div></Section></div>)}</div>
    <div className="provider-status-row"><span>Provider 配置：<Status value={r.status || "not_run"} />{r.model && ` · ${r.model}`}</span><button className="secondary" onClick={() => void verify()} disabled={checking}>{checking ? "正在验证…" : "验证服务连接"}</button>{r.last_probe && <span className="muted">最后验证：{displayText(r.last_probe.status)}{r.last_probe.latency_ms != null ? ` · ${r.last_probe.latency_ms} ms` : ""}</span>}<small className="muted">手动验证会调用 DeepSeek。</small></div>
    <Drawer open={spaceOpen} onOpenChange={setSpaceOpen} title="Search Space" className="search-space-drawer"><div className="drawer-body"><SearchSpaceTable contract={pipeline?.search_space || {}} baseline={pipeline?.baseline_config || config} /></div></Drawer>
    <Drawer open={detailsOpen} onOpenChange={setDetailsOpen} title="Pipeline 技术详情"><div className="drawer-body"><p>主页面仅展示已保存的值。未实现的父 / 子 Chunk、未保存的 Generation Temperature / Max Tokens 不补造；Judge 的 Temperature 不作为 Generation 配置。</p><p>生成模型优先来自当前发布 Snapshot；温度仅采用对应模型的明确生成执行快照。Provider 配置状态不等于当前发布模型。</p><pre className="technical-raw">{JSON.stringify({ pipeline, production_snapshot: active?.snapshot, generation_execution_snapshot: execution.generation_model ? execution : null, hidden_fields: groups.map(group => ({ group: group.title, fields: group.rows.filter(([, , value]) => !available(value)).map(([, label]) => label) })) }, null, 2)}</pre></div></Drawer>
  </div>;
}
