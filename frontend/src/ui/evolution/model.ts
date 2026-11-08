/**
 * 进化路线的数据整理（纯函数，不发请求、不改数据）。
 * 输入：优化实验对象（/api/optimization 的 experiment）、Baseline 评测、Baseline 配置。
 * 输出：页面直接渲染用的轮次 / Candidate 模型。所有文字都由保存数据生成，不编。
 */

export type ParamChange = { key: string; label: string; from?: string; to: string };
export type CandidateView = {
  id: string; label: string; round: number; name: string; direction: string; efficiency: boolean;
  params: ParamChange[]; fixed: string[]; broken: string[]; gateFailures: string[];
  qualified: boolean | null; winner: boolean; correct: number | null; total: number | null;
  p50: number | null; p99: number | null; complete: boolean;
};
export type RoundView = { round: number; candidates: CandidateView[]; summary: string; fastestId: string | null };
export type EvolutionModel = { rounds: RoundView[]; winnerId: string | null; d: CandidateView | null; budget: { used: number; max: number } | null };

export const PARAM_LABELS: Record<string, string> = {
  candidate_k: "Candidate K", top_k: "Top-K", generation_thinking: "Thinking", multi_query: "Multi-Query",
  query_rewrite: "Query Rewrite", query_decompose: "Query Decompose", hyde: "HyDE", hybrid_search: "Hybrid Search",
  hybrid_alpha: "向量权重", rerank: "Rerank", prompt_strategy: "回答策略", min_score: "最低相关分", retrieval_max_tokens: "Retrieval Max Tokens",
};

const THINKING: Record<string, string> = { off: "Off", low: "Low", medium: "Medium", high: "High", max: "Max" };
const STRATEGY: Record<string, string> = { Grounded: "有据生成", Tiered: "分级回答" };

export function paramValue(key: string, value: unknown): string {
  if (value === undefined || value === null) return "未知";
  if (key === "generation_thinking" && typeof value === "string") return THINKING[value] ?? value;
  if (key === "prompt_strategy" && typeof value === "string") return STRATEGY[value] ?? value;
  if (key === "multi_query" && (value === false || value === 0)) return "关闭";
  if (typeof value === "boolean") return value ? "开启" : "关闭";
  return String(value);
}

export const shortId = (id: string): string => {
  const number = id.match(/^Q(\d+)$/i)?.[1] || id.match(/^(?:CSV|V1G)-[\dA-Za-z-]*?-(\d{1,3})(?:-R[\dA-Za-z-]+)?$/)?.[1];
  return number ? `Q${number.padStart(2, "0")}` : id;
};

const list = (value: unknown): string[] => Array.isArray(value) ? value.filter((item): item is string => typeof item === "string").map(shortId) : [];
const firstList = (...values: unknown[]): string[] => { for (const value of values) if (Array.isArray(value)) return list(value); return []; };

function complete(candidate: any): boolean {
  const result = candidate?.result;
  return !!result && ["completed", "evaluated"].includes(candidate.status) && result.evaluation_complete !== false && !result.technical_failed;
}

function gateFailures(result: any, gateLabel: (metric: string) => string): string[] {
  const gates: any[] = result?.gates?.gates || [];
  return gates.filter(gate => gate.passed === false || gate.status === "FAIL").map(gate => {
    const latency = typeof gate.metric === "string" && gate.metric.startsWith("latency_");
    const unit = latency ? " 秒" : "%";
    const actual = typeof gate.actual === "number" ? `${Math.round(gate.actual * 10) / 10}${unit}` : "";
    const limit = typeof gate.threshold === "number" ? `${gate.operator === "<=" ? "上限" : "下限"} ${gate.threshold}${unit}` : "";
    return `${[gateLabel(gate.metric), actual].filter(Boolean).join(" ")}${limit ? `（${limit}）` : ""}`;
  });
}

function latency(result: any, metric: string): number | null {
  const gate = (result?.gates?.gates || []).find((row: any) => row.metric === metric);
  return typeof gate?.actual === "number" ? gate.actual : null;
}

export function candidateView(candidate: any, baselineConfig: Record<string, unknown> | undefined, winnerId: string | null, gateLabel: (metric: string) => string, nameOf: (candidate: any) => string): CandidateView {
  const result = candidate?.result || {};
  const reasoning = candidate?.reasoning || {};
  const changed: Record<string, unknown> = reasoning.changed_parameters || {};
  const params = Object.entries(changed).map(([key, value]) => ({
    key, label: PARAM_LABELS[key] ?? key, to: paramValue(key, value),
    from: baselineConfig && key in baselineConfig ? paramValue(key, baselineConfig[key]) : undefined,
  })).filter(item => item.from === undefined || item.from !== item.to);
  const qualification = result.release_qualification ?? result.qualification;
  const total = typeof result.total_cases === "number" ? result.total_cases : typeof result.case_count === "number" ? result.case_count : 50;
  const bad = typeof result.bad_case_count === "number" ? result.bad_case_count : null;
  return {
    id: candidate.id, label: reasoning.candidate_label || candidate.id.slice(-1), round: reasoning.round || 1, name: nameOf(candidate),
    direction: reasoning.direction || reasoning.optimization_direction || "", efficiency: /效率/.test(reasoning.direction || ""),
    params,
    fixed: firstList(result.all_fixed_question_ids, result.regression?.all_fixed_question_ids),
    broken: firstList(result.new_regression_question_ids, result.newly_failed, result.comparison?.newly_failed, result.regression?.new_regression_question_ids),
    gateFailures: gateFailures(result, gateLabel),
    qualified: typeof qualification?.qualified === "boolean" ? qualification.qualified : null,
    winner: candidate.id === winnerId,
    correct: bad === null ? null : total - bad, total,
    p50: latency(result, "latency_p50_seconds"), p99: latency(result, "latency_p99_seconds"),
    complete: complete(candidate),
  };
}

export function roundSummary(candidates: CandidateView[]): string {
  const done = candidates.filter(item => item.complete);
  if (!done.length) return "本轮评测尚未完成";
  const winner = done.find(item => item.winner) || done.find(item => item.qualified);
  if (winner) return `${winner.name.replace(/^Round \d+ · /, "")} 零新增 Bad Case、Hard Gate 全过，成为 Winner`;
  const broke = done.filter(item => item.broken.length).length;
  const gates = done.filter(item => item.gateFailures.length).length;
  const parts = [broke ? `${broke} 个新增了 Bad Case` : "", gates ? `${gates} 个没过 Hard Gate` : ""].filter(Boolean);
  return `本轮没有合格 Candidate${parts.length ? `：${parts.join("，")}` : ""}`;
}

export function buildEvolutionModel(experiment: any, baselineConfig: Record<string, unknown> | undefined, gateLabel: (metric: string) => string, nameOf: (candidate: any) => string): EvolutionModel {
  const candidates: any[] = experiment?.candidates || [];
  const state = experiment?.result || {};
  const rec = experiment?.recommendation?.result || experiment?.recommendation || {};
  const dRaw = candidates.find(item => item.reasoning?.candidate_label === "D");
  const winnerId: string | null = dRaw?.reasoning?.winner_id || state.d_facts?.winner_id || state.report_confirmation?.winner_id || rec.winner_id || null;
  const views = candidates.filter(item => ["A", "B", "C"].includes(item.reasoning?.candidate_label)).map(item => candidateView(item, baselineConfig, winnerId, gateLabel, nameOf));
  const roundNumbers = Array.from(new Set(views.map(item => item.round))).sort((a, b) => a - b);
  const rounds = roundNumbers.map(round => {
    const items = views.filter(item => item.round === round).sort((a, b) => a.label.localeCompare(b.label));
    const timed = items.filter(item => item.p50 !== null);
    const fastest = timed.length ? timed.reduce((best, item) => (item.p50 as number) < (best.p50 as number) ? item : best) : null;
    return { round, candidates: items, summary: roundSummary(items), fastestId: fastest?.id ?? null };
  });
  const budget = experiment?.evaluation_budget && typeof experiment.evaluation_budget.used === "number" ? { used: experiment.evaluation_budget.used, max: experiment.evaluation_budget.max } : null;
  return { rounds, winnerId, d: dRaw ? candidateView(dRaw, baselineConfig, winnerId, gateLabel, nameOf) : null, budget };
}
