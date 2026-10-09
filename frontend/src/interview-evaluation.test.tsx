// @vitest-environment jsdom
import { act, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { EvaluationPage } from "./pages/EvaluationPage";
import { EvolutionPage } from "./pages/EvolutionPage";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
let root: ReturnType<typeof createRoot>;
afterEach(() => { if (root) act(() => root.unmount()); document.body.innerHTML = ""; vi.unstubAllGlobals(); });
const render = async (node: ReactNode) => { root = createRoot(document.body.appendChild(document.createElement("div"))); await act(async () => { root.render(node); await Promise.resolve(); }); };
const click = async (label: string) => act(async () => [...document.querySelectorAll<HTMLButtonElement>("button")].find(button => button.textContent === label)!.click());
const gates = ["positive_correctness", "positive_faithfulness", "positive_completeness", "ablation_correctness", "ablation_faithfulness", "ablation_completeness", "safe_rejection_rate", "safety_critical_accuracy", "prompt_injection_resistance", "latency_p50_seconds", "latency_p99_seconds"].map((metric, index) => ({ metric, actual: index === 3 ? 72 : metric.startsWith("latency") ? 2 : 100, threshold: metric.startsWith("latency") ? 8 : 90, operator: metric.startsWith("latency") ? "<=" : ">=", status: index === 3 ? "FAIL" : "PASS" }));
const caseRow = { question_id: "Q-stored", question: "持久化问题", test_category: "ablation", passed: false, reference_answer: "持久化参考答案", model_answer: "持久化回答", primary_root_cause: "Query", secondary_root_causes: ["Retrieval"], failure_tags: ["Evidence Miss"], programmatic_metrics: { retrieval_hit: false, latency_ms: 24 }, judge_result: { correctness: 72, reason: "保存的 Judge 依据" } };
const run = { id: "EVAL-stored", status: "completed", dataset_version_id: "GD-stored", created_at: "2026-09-27T14:04:23Z", judge: { model: "judge-only-model" }, config: { candidate_k: 8, top_k: 3, prompt_strategy: "grounded" }, dataset_snapshot: { id: "GD-stored", question_ids: ["Q-stored"], questions: [{ id: "Q-stored", acceptable_evidence: [{ source_chunk_ids: ["CH-stored"], evidence_key_points: ["冻结证据"] }] }] }, cases: [caseRow], gate_details: gates.map(gate => ({ ...gate, contributing_cases: gate.status === "FAIL" ? [{ question_id: "Q-stored", value: 72, passed: false }] : [] })), result: { gates: { gates, total: 11, passed_count: 10, passed: false }, bad_case_count: 1, comparison_metrics: { input_tokens: 17, output_tokens: 9, recall_at_k: 50 } } };
const bad = { id: "BC-stored", run_id: run.id, question_id: caseRow.question_id, category: "Query", result: caseRow };

it("keeps Baseline conclusions inside the report, hides technical identity, and preserves the stored Primary separately from signals", async () => {
  const input = { evaluation: run, badCases: [bad] }, frozen = JSON.stringify(input);
  vi.stubGlobal("fetch", vi.fn(async (url: string) => new Response(JSON.stringify(url.endsWith("/api/bad-cases") ? [bad] : run))));
  await render(<EvaluationPage data={input} />);
  expect(document.querySelectorAll(".stage-stepper li")).toHaveLength(4);
  expect(document.querySelector(".baseline-metrics")?.textContent).toContain("10 / 11");
  expect(document.querySelector(".baseline-conclusion")?.textContent).toContain("未通过 Hard Gate");
  expect(document.querySelector(".baseline-conclusion")?.textContent).toContain("仍有 1 个单题问题");
  expect(document.querySelector(".baseline-conclusion")?.textContent).toContain("Ablation Correctness");
  expect(document.querySelector(".baseline-run-summary")?.textContent).toContain("judge-only-model");
  expect(document.body.textContent).not.toContain("Run ID");
  await click("Hard Gate");
  expect(document.querySelectorAll("tbody tr")).toHaveLength(11);
  expect(document.querySelector("tbody")?.textContent).toContain("72.00%");
  expect(document.querySelector("tbody")?.textContent).toContain("≥ 90.00%");
  expect(new Set([...document.querySelectorAll("tbody tr td:nth-child(2)")].map(cell => cell.textContent)).size).toBe(4);
  await click("Bad Case 诊断");
  expect([...document.querySelectorAll("thead th")].map(cell => cell.textContent)).toEqual(["问题", "初步类型", "失败观察", "关键指标", "详情"]);
  expect(document.querySelector("tbody tr td:nth-child(2)")?.textContent).toBe("Query");
  await click("查看案例");
  expect([...document.querySelectorAll(".case-details > section > h3")].map(header => header.textContent)).toEqual(["问题", "预期与实际回答", "Golden Evidence", "Retrieved Evidence", "Judge", "初步诊断", "Secondary Signals", "关联 Gate", "身份与审计"]);
  expect(document.querySelector('[role="dialog"]')?.textContent).toContain("Query");
  expect(JSON.stringify(input)).toBe(frozen);
  expect((fetch as any).mock.calls.every((call: any[]) => !call[1]?.method || call[1].method === "GET")).toBe(true);
});

it("uses saved generation evidence only and keeps technical identity in its Drawer", async () => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => new Response(JSON.stringify(url.endsWith("/api/bad-cases") ? [bad] : run))));
  await render(<EvaluationPage data={{ evaluation: run, badCases: [bad] }} />);
  expect(document.querySelector(".config-summary-grid")?.textContent).not.toContain("judge-only-model");
  await click("查看评测依据");
  expect(document.querySelector('[role="dialog"]')?.textContent).toContain("judge-only-model");
  expect(document.querySelector('[role="dialog"]')?.textContent).toContain("EVAL-stored");
});

it("keeps Agent diagnosis source-backed, lists saved hypotheses once, and restores the experiment plan and six Sandbox decision rows", async () => {
  const search_space = { top_k: { type: "integer", allowed: [3, 6] }, prompt_strategy: { type: "string", allowed: ["grounded", "abstention"] } };
  const candidates = ["A", "B", "C"].map((label, index) => ({ id: `C-${label}`, status: "evaluated", config: { ...run.config, top_k: index === 0 ? 6 : 3, prompt_strategy: index === 2 ? "abstention" : "grounded" }, reasoning: { candidate_label: label, observed_evidence: [bad.id], proposal: `保存理由 ${label}`, hypothesis: `保存假设 ${label}` }, result: { gates: { passed_count: index === 2 ? 11 : 10, total: 11 }, bad_case_count: index === 2 ? 0 : 1, regression: { status: index === 1 ? "FAIL" : "PASS" }, qualification: { qualified: index === 2 }, comparison_metrics: { input_tokens: 13, output_tokens: 6 } } }));
  const input = { evaluation: run, badCases: [bad], optimization: { id: "EXP-stored", candidates, evaluation_budget: { used: 3, max: 12, reserved_for_d: 1 }, result: { root_cause_cluster: "保存的诊断" } } }, frozen = JSON.stringify(input);
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ search_space }))));
  await render(<EvolutionPage data={input} />);
  expect(document.querySelectorAll(".stage-stepper li")).toHaveLength(6);
  expect(document.querySelector(".diagnosis-cards")?.textContent).toContain("查询表达");
  expect(document.querySelector(".diagnosis-cards")?.textContent).toContain("1 个 Bad Case");
  expect(document.querySelector(".diagnosis-cards")?.textContent).toContain("当前证据不足以确定原因");
  expect(document.querySelector(".diagnosis-cards")?.textContent).not.toContain("Evidence Miss");
  expect(document.querySelector(".diagnosis-cards")?.textContent).toContain("Ablation Correctness");
  await click("优化 Agent");
  expect(document.querySelectorAll(".candidate-card")).toHaveLength(0);
  expect([...document.querySelectorAll(".panel > .section-head h2")].map(header => header.textContent)).toEqual(["实验概览", "Agent Diagnosis", "Experiment Plan"]);
  expect(document.body.textContent).toContain("保存假设 A");
  expect(document.body.textContent).toContain("Search Space · 2");
  await click("A / B / C / D");
  expect(document.querySelectorAll(".candidate-card")).toHaveLength(3);
  expect([...document.querySelectorAll(".candidate-card:first-child .candidate-story-block > .field-label")].map(label => label.textContent)).toEqual(["WHY", "TARGET", "CHANGE", "EXPECTED", "RISK", "RESULT"]);
  expect(document.querySelector(".candidate-card")?.textContent).toContain("保存理由 A");
  await click("Sandbox");
  expect([...document.querySelectorAll("tbody tr > td:first-child")].map(cell => cell.textContent)).toEqual(["Hard Gate", "Bad Case", "修复原 Bad Case", "新增失败", "Regression", "Qualification"]);
  expect(document.body.textContent).not.toContain("Input Tokens");
  await click("查看高级指标");
  expect(document.querySelector('[role="dialog"]')?.textContent).toContain("Input Tokens");
  expect(JSON.stringify(input)).toBe(frozen);
  expect((fetch as any).mock.calls.every((call: any[]) => !call[1]?.method || call[1].method === "GET")).toBe(true);
});

it.each([
  { status: "generated", result: {}, expected: "等待完整 Sandbox" },
  { status: "evaluated", result: { qualification: { qualified: true }, regression: { status: "PASS" }, gates: { passed_count: 11, total: 11 } }, expected: "保留 Candidate C" },
])("reports Composite D $status without inventing failure or replacing the saved Winner", async ({ status, result, expected }) => {
  const winner = { id: "C-C", status: "evaluated", reasoning: { candidate_label: "C" }, result: { qualification: { qualified: true } } };
  const d = { id: "C-D", status, reasoning: { candidate_label: "D", winner_id: winner.id, sources: [] }, result };
  const optimization = { id: "EXP-stored", candidates: [winner, d], result: { report_confirmation: { winner_id: winner.id } }, recommendation: { result: { recommended_candidate: status === "evaluated" ? winner.id : null } } };
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ search_space: {} }))));
  await render(<EvolutionPage data={{ evaluation: run, badCases: [bad], optimization }} />);
  await click("A / B / C / D");
  expect(document.querySelector(".composite-decision")?.textContent).toContain(expected);
});
