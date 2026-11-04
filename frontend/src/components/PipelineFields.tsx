import { DataTable } from "./DataTable";
import { useState } from "react";
import { displayText, parameterNames, descriptions } from "../display";
import { Drawer } from "./Dialog";

export { parameterNames, descriptions } from "../display";
export const draftDefaults: Record<string, unknown> = { generation_thinking: "high", retrieval_max_tokens: false };

export function thinkingLabel(value: unknown): string {
  if (value && typeof value === "object") {
    const saved = value as { thinking?: { type?: string }; reasoning_effort?: string };
    if (saved.thinking?.type === "disabled") return "OFF";
    return saved.thinking?.type === "enabled" ? thinkingLabel(saved.reasoning_effort) : "历史未知";
  }
  const labels: Record<string, string> = { off: "OFF", low: "Low", high: "High", max: "Max" };
  return typeof value === "string" && labels[value] || "历史未知";
}

export function formatValue(value: unknown): string {
  if (typeof value === "string" && ["off", "low", "high", "max"].includes(value)) return thinkingLabel(value);
  return value == null ? "未采集" : typeof value === "boolean" ? value ? "开启" : "关闭" : displayText(String(value));
}

export function SearchSpaceTable({ contract, baseline }: { contract: Record<string, { type: string; allowed: unknown[] }>; baseline: Record<string, unknown> }) {
  return <div className="table-scroll"><DataTable className="search-space-table"><thead><tr><th>参数</th>{Object.keys(baseline).length > 0 && <th>当前 Baseline</th>}<th>允许范围</th><th>依赖关系</th><th>说明</th></tr></thead><tbody>{Object.entries(contract).map(([key, rule]) => <tr key={key}><td>{parameterNames[key] || key}</td>{Object.keys(baseline).length > 0 && <td>{key === "generation_thinking" ? thinkingLabel(baseline[key]) : formatValue(baseline[key])}</td>}<td>{rule.allowed.map(formatValue).join(" / ")}</td><td>{key === "top_k" ? "候选数不能少于保留条数" : key === "hybrid_alpha" ? "混合检索已开启" : "—"}</td><td>{descriptions[key] || "—"}</td></tr>)}</tbody></DataTable></div>;
}

export const parameterGroups: Record<string, string[]> = { Query: ["query_rewrite", "multi_query", "hyde", "query_decompose", "alias_mapping"], Retrieval: ["candidate_k", "top_k", "min_score", "hybrid_search", "hybrid_alpha", "metadata_filter", "retrieval_max_tokens"], Rerank: ["rerank"], Generation: ["prompt_strategy", "generation_thinking"] };
export function ParameterDiff({ before = {}, after = {} }: { before?: Record<string, unknown>; after?: Record<string, unknown> }) {
  const [open, setOpen] = useState(false);
  const keys = Object.values(parameterGroups).flat().filter(key => key in before || key in after);
  const changed = keys.filter(key => before[key] !== after[key]);
  const render = (selected: string[]) => Object.entries(parameterGroups).map(([name, members]) => { const rows = members.filter(key => selected.includes(key)); return rows.length ? <section className="parameter-group" key={name}><h3>{displayText(name)}</h3><div className="table-scroll"><DataTable><thead><tr><th>参数</th><th>优化前</th><th>优化后</th></tr></thead><tbody>{rows.map(key => <tr key={key} className={changed.includes(key) ? "parameter-changed" : ""}><td>{parameterNames[key] || key}</td><td>{formatValue(before[key])}</td><td>{formatValue(after[key])}</td></tr>)}</tbody></DataTable></div></section> : null; });
  return <div className="parameter-diff">{render(changed)}{!changed.length && <p className="muted">{keys.length ? "两个保存配置的参数一致。" : "未保存可比较的配置。"}</p>}{keys.length > changed.length && <><button className="text-button" onClick={() => setOpen(true)}>{changed.length} 项变化 · 未变参数 {keys.length - changed.length}</button><Drawer open={open} onOpenChange={setOpen} title="完整配置与未变参数"><div className="drawer-body">{render(keys)}</div></Drawer></>}</div>;
}

export function estimatedCostText(metrics?: any): string | null {
  const cost = metrics?.cost_estimation || metrics?.estimated_cost;
  if (cost?.status !== "estimated" || typeof cost.amount !== "number" || !Number.isFinite(cost.amount) || cost.amount < 0 || !cost.currency || cost.price_snapshot?.currency !== cost.currency || !Array.isArray(cost.calls) || !cost.calls.length) return null;
  const prefix = cost.currency === "CNY" ? "¥" : cost.currency === "USD" ? "$" : `${cost.currency} `;
  return `${prefix}${cost.amount}`;
}

export function ExecutionMetrics({ metrics, compact = false }: { metrics?: any; compact?: boolean }) {
  const stages: any[] = Array.isArray(metrics?.stages) ? metrics.stages.filter((row: any) => row && typeof row.stage_name === "string" && typeof row.duration_ms === "number") : [];
  const names: Record<string, string> = { query_processing: "查询处理", retrieval: "检索总计", vector_search: "向量检索", bm25: "BM25", hybrid_fusion: "Hybrid 融合", candidate_selection: "候选筛选", rerank: "重排方式", context_build: "上下文构建", generation: "回答生成", judge: "Judge" };
  const grouped = stages.reduce((result: Record<string, { duration: number; parent?: string }>, stage) => { const value = result[stage.stage_name] || { duration: 0, parent: stage.parent }; value.duration += stage.duration_ms; result[stage.stage_name] = value; return result; }, {});
  const usage = metrics?.token_usage;
  const cost = metrics?.cost_estimation || metrics?.estimated_cost;
  const amount = estimatedCostText(metrics);
  if (compact) {
    const count = (value: unknown) => typeof value === "number" && Number.isInteger(value) && value >= 0 ? value : null;
    const values = [["响应耗时", typeof metrics?.latency_ms === "number" && Number.isFinite(metrics.latency_ms) && metrics.latency_ms >= 0 ? `${metrics.latency_ms} ms` : null], ["输入 Token", count(metrics?.input_tokens ?? usage?.generation?.prompt_tokens)], ["输出 Token", count(metrics?.output_tokens ?? usage?.generation?.completion_tokens)], ["估算费用", amount]];
    return <dl className="compact-metrics">{values.filter(([, value]) => value != null && (typeof value !== "number" || Number.isInteger(value) && value >= 0)).map(([label, value]) => <div key={String(label)}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>;
  }
  return <section className="execution-metrics"><h3>耗时与 Token</h3><p>回答总耗时：{metrics?.latency_ms == null ? "未采集" : `${metrics.latency_ms} ms`} · Judge：{Array.isArray(metrics?.judge_stages) && metrics.judge_stages.every((row: any) => typeof row?.duration_ms === "number") && metrics.judge_stages.length ? `${metrics.judge_stages.reduce((sum: number, row: any) => sum + row.duration_ms, 0).toFixed(1)} ms` : "未采集"}</p>{stages.length ? <dl className="report-grid">{Object.entries(grouped).map(([name, value]: [string, any]) => <div key={name}><dt>{value.parent && "↳ "}{names[name] || name}</dt><dd>{value.duration.toFixed(1)} ms</dd></div>)}</dl> : <p className="muted">阶段耗时：未采集</p>}<p>输入 Token：{metrics?.input_tokens ?? usage?.generation?.prompt_tokens ?? "未采集"} · 输出 Token：{metrics?.output_tokens ?? usage?.generation?.completion_tokens ?? "未采集"}</p><p>辅助查询调用：{usage?.auxiliary_queries?.length ?? "未采集"} · Judge Usage：{metrics?.judge_usage ? "已采集" : "未采集"}</p><p>费用：{amount != null ? `${amount}（按调用时配置估算）` : costReason(cost?.reason)}</p><p>TTFT：{metrics?.ttft_ms == null ? "— · 未采集真实首输出时间" : `${metrics.ttft_ms} ms`}</p><p className="muted">检索子阶段已包含在检索总计中，不重复累加。回答耗时与 Judge 分开；Gate 仍采用原回答耗时。</p></section>;
}

export function costReason(reason?: string): string {
  const reasons: Record<string, string> = { price_unavailable: "当前模型价格未配置", model_mismatch: "请求模型与价格配置不匹配", usage_missing: "Usage 未采集", call_timestamp_missing: "调用时间未采集", cache_usage_missing_or_invalid: "缓存 Token 拆分缺失，无法精确估价", usage_missing_or_invalid: "Usage 缺失或无效", cache_usage_inconsistent: "缓存 Token 与总量不一致", billing_period_ambiguous: "计费时段或节假日日历未确认", model_price_not_configured: "当前模型价格未配置", model_not_configured: "模型未记录", price_config_invalid: "价格配置无效", usage_not_collected: "Usage 未采集" };
  return reason ? reasons[reason] || `无法估价：${reason}` : "历史运行未保存完整计费信息，无法准确回算";
}

export function billedCostText(metrics?: any): string {
  const estimate = estimatedCostText(metrics);
  if (estimate != null) return `${estimate}（估算费用）`;
  if (typeof metrics?.token_cost === "number" && metrics.token_cost_status === "MEASURED" && metrics.token_cost_currency && metrics.token_cost_source === "provider_billing") return `${metrics.token_cost} ${metrics.token_cost_currency}（Provider 账单费用）`;
  const reason = metrics?.token_cost_reason || metrics?.token_cost_status;
  return reason && reason !== "MEASURED" ? `费用未采集 · ${reason}` : "费用未采集";
}
