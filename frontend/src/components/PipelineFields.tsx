import { Badge } from "./Primitives";

export const parameterNames: Record<string, string> = {
  candidate_k: "CandidateK", top_k: "TopK", min_score: "MinScore", hybrid_search: "Hybrid", hybrid_alpha: "Hybrid Alpha",
  rerank: "Rerank", query_rewrite: "Query Rewrite", multi_query: "MultiQuery", hyde: "HyDE",
  metadata_filter: "Metadata Filter", alias_mapping: "Alias Mapping", prompt_strategy: "Prompt Strategy",
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
  return <div className="table-scroll"><table className="search-space-table"><thead><tr><th>Parameter</th><th>Current Baseline</th><th>Type</th><th>Allowed Values</th><th>Dependency</th><th>Agent Tunable</th><th>Explanation</th></tr></thead><tbody>{Object.entries(contract).map(([key, rule]) => <tr key={key}><td>{parameterNames[key] || key}</td><td>{formatValue(baseline[key])}</td><td>{rule.type}</td><td>{rule.allowed.map(formatValue).join(" / ")}</td><td>{key === "top_k" ? "CandidateK ≥ TopK" : key === "hybrid_alpha" ? "Hybrid = ON" : "—"}</td><td><Badge tone="accent">Yes</Badge></td><td>{descriptions[key] || "—"}</td></tr>)}</tbody></table></div>;
}
