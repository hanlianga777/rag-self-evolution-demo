import { Badge } from "./Primitives";

export const parameterNames: Record<string, string> = {
  candidate_k: "CandidateK", top_k: "TopK", min_score: "MinScore", hybrid_search: "Hybrid", hybrid_alpha: "Hybrid 权重",
  rerank: "Rerank", query_rewrite: "Query Rewrite", multi_query: "MultiQuery", hyde: "HyDE",
  metadata_filter: "元数据筛选", alias_mapping: "别名映射", prompt_strategy: "Prompt 策略",
};

const descriptions: Record<string, string> = {
  candidate_k: "初始候选召回数量", top_k: "进入回答上下文的证据数量", min_score: "进入上下文前的最低相关分",
  hybrid_search: "组合向量与关键词检索", hybrid_alpha: "向量检索在 Hybrid 中的权重", rerank: "轻量二阶段重排",
  query_rewrite: "生成标准化检索问法", multi_query: "生成互补检索问法", hyde: "使用假设文本辅助检索",
  metadata_filter: "按可靠元数据筛选", alias_mapping: "使用已审核别名映射", prompt_strategy: "回答约束策略",
};

export function formatValue(value: unknown): string {
  return value == null ? "未采集" : typeof value === "boolean" ? value ? "ON" : "OFF" : String(value);
}

export function SearchSpaceTable({ contract, baseline }: { contract: Record<string, { type: string; allowed: unknown[] }>; baseline: Record<string, unknown> }) {
  return <div className="table-scroll"><table className="search-space-table"><thead><tr><th>参数</th><th>当前 Baseline</th><th>类型</th><th>允许值</th><th>依赖关系</th><th>Agent 可调</th><th>说明</th></tr></thead><tbody>{Object.entries(contract).map(([key, rule]) => <tr key={key}><td>{parameterNames[key] || key}</td><td>{formatValue(baseline[key])}</td><td>{rule.type}</td><td>{rule.allowed.map(formatValue).join(" / ")}</td><td>{key === "top_k" ? "CandidateK ≥ TopK" : key === "hybrid_alpha" ? "Hybrid = ON" : "—"}</td><td><Badge tone="accent">是</Badge></td><td>{descriptions[key] || "—"}</td></tr>)}</tbody></table></div>;
}

export const parameterGroups: Record<string, string[]> = { Query: ["query_rewrite", "multi_query", "hyde", "alias_mapping"], Retrieval: ["candidate_k", "top_k", "min_score", "hybrid_search", "hybrid_alpha", "metadata_filter"], Rerank: ["rerank"], Generation: ["prompt_strategy"] };
export function ParameterDiff({ before = {}, after = {} }: { before?: Record<string, unknown>; after?: Record<string, unknown> }) {
  const keys = Object.values(parameterGroups).flat().filter(key => key in before || key in after);
  const changed = keys.filter(key => before[key] !== after[key]);
  const render = (selected: string[]) => Object.entries(parameterGroups).map(([name, members]) => { const rows = members.filter(key => selected.includes(key)); return rows.length ? <section className="parameter-group" key={name}><h3>{name}</h3><div className="table-scroll"><table><thead><tr><th>参数</th><th>优化前</th><th>优化后</th></tr></thead><tbody>{rows.map(key => <tr key={key} className={changed.includes(key) ? "parameter-changed" : ""}><td>{parameterNames[key] || key}</td><td>{formatValue(before[key])}</td><td>{formatValue(after[key])}</td></tr>)}</tbody></table></div></section> : null; });
  return <div className="parameter-diff">{render(changed)}{!changed.length && <p className="muted">{keys.length ? "两个保存配置的参数一致。" : "未保存可比较的配置。"}</p>}{keys.length > changed.length && <details className="disclosure"><summary>未变参数 · {keys.length - changed.length}</summary>{render(keys.filter(key => !changed.includes(key)))}</details>}</div>;
}

export function ExecutionMetrics({ metrics }: { metrics?: any }) {
  const stages: any[] = Array.isArray(metrics?.stages) ? metrics.stages.filter((row: any) => row && typeof row.stage_name === "string" && typeof row.duration_ms === "number") : [];
  const names: Record<string, string> = { query_processing: "查询处理", retrieval: "检索总计", vector_search: "向量检索", bm25: "BM25", hybrid_fusion: "Hybrid 融合", candidate_selection: "候选筛选", rerank: "Rerank", context_build: "上下文构建", generation: "回答生成", judge: "Judge" };
  const grouped = stages.reduce((result: Record<string, { duration: number; parent?: string }>, stage) => { const value = result[stage.stage_name] || { duration: 0, parent: stage.parent }; value.duration += stage.duration_ms; result[stage.stage_name] = value; return result; }, {});
  const usage = metrics?.token_usage;
  return <section className="execution-metrics"><h3>耗时与 Token</h3><p>回答总耗时：{metrics?.latency_ms == null ? "未采集" : `${metrics.latency_ms} ms`} · Judge：{Array.isArray(metrics?.judge_stages) && metrics.judge_stages.every((row: any) => typeof row?.duration_ms === "number") && metrics.judge_stages.length ? `${metrics.judge_stages.reduce((sum: number, row: any) => sum + row.duration_ms, 0).toFixed(1)} ms` : "未采集"}</p>{stages.length ? <dl className="report-grid">{Object.entries(grouped).map(([name, value]: [string, any]) => <div key={name}><dt>{value.parent && "↳ "}{names[name] || name}</dt><dd>{value.duration.toFixed(1)} ms</dd></div>)}</dl> : <p className="muted">阶段耗时：未采集</p>}<p>回答输入 Token：{metrics?.input_tokens ?? usage?.generation?.prompt_tokens ?? "未采集"} · 输出 Token：{metrics?.output_tokens ?? usage?.generation?.completion_tokens ?? "未采集"}</p><p>辅助查询调用：{usage?.auxiliary_queries?.length ?? "未采集"} · Judge Usage：{metrics?.judge_usage ? "已采集" : "未采集"}</p><p>费用：{metrics?.estimated_cost ? `${metrics.estimated_cost.amount} ${metrics.estimated_cost.currency}（按调用时配置估算）` : "暂未配置单价 / Usage 不完整；历史费用未采集"}</p><p className="muted">检索子阶段已包含在检索总计中，不重复累加。回答耗时与 Judge 分开；Gate 仍采用原回答耗时。</p></section>;
}
