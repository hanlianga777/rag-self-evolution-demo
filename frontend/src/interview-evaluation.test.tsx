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
const caseRow = { question_id: "Q-stored", question: "持久化问题", test_category: "ablation", passed: false, reference_answer: "持久化参考答案", model_answer: "持久化回答", diagnostic_view: {is_technical_bad_case: true, analysis_category: "rag_failure", diagnosis_category: "检索失败", subfeature: "标准证据未进候选", tuning_directions: ["候选召回覆盖"], primary_root_cause: "Retrieval", target_eligible: true, optimization_directions: ["candidate_recall"]}, primary_root_cause: "Query", secondary_root_causes: ["Retrieval"], failure_tags: ["Evidence Miss"], programmatic_metrics: { retrieval_hit: false, latency_ms: 24 }, judge_result: { correctness: 72, reason: "保存的 Judge 依据" } };
const run = { id: "EVAL-stored", status: "completed", dataset_version_id: "GD-stored", created_at: "2026-09-27T14:04:23Z", judge: { model: "judge-only-model" }, config: { candidate_k: 8, top_k: 3, prompt_strategy: "grounded" }, dataset_snapshot: { id: "GD-stored", question_ids: ["Q-stored"], questions: [{ id: "Q-stored", acceptable_evidence: [{ source_chunk_ids: ["CH-stored"], evidence_key_points: ["冻结证据"] }] }] }, cases: [caseRow], gate_details: gates.map(gate => ({ ...gate, contributing_cases: gate.status === "FAIL" ? [{ question_id: "Q-stored", value: 72, passed: false }] : [] })), result: { gates: { gates, total: 11, passed_count: 10, passed: false }, bad_case_count: 1, comparison_metrics: { input_tokens: 17, output_tokens: 9, recall_at_k: 50 } } };
const bad = { id: "BC-stored", run_id: run.id, question_id: caseRow.question_id, category: "Query", result: caseRow };

it("keeps Baseline conclusions and saved identity inside the report, and preserves the stored Primary separately from signals", async () => {
  const input = { evaluation: run, badCases: [bad] }, frozen = JSON.stringify(input);
  vi.stubGlobal("fetch", vi.fn(async (url: string) => new Response(JSON.stringify(url.endsWith("/api/bad-cases") ? [bad] : run))));
  await render(<EvaluationPage data={input} />);
  expect(document.querySelectorAll(".stage-stepper li")).toHaveLength(0);
  expect(document.querySelector(".baseline-metrics")?.textContent).toContain("10 / 11");
  expect(document.querySelector(".baseline-conclusion")?.textContent).toContain("1 项 Hard Gate 未达标");
  expect(document.querySelectorAll(".baseline-metrics > div")).toHaveLength(4);
  expect(document.querySelector(".baseline-conclusion")?.textContent).toContain("消融（Ablation）正确性");
  expect(document.querySelector(".baseline-run-summary")?.textContent).not.toContain("judge-only-model");
  expect(document.querySelector(".baseline-run-summary")?.textContent).not.toContain("EVAL-stored");
  expect(document.body.textContent).not.toContain("EVAL-stored");
  await click("Hard Gate");
  expect(document.querySelectorAll(".ui-hg-card li")).toHaveLength(11);
  expect(document.querySelectorAll(".ui-hg-card")[1]?.textContent).toContain("72%");
  expect(document.querySelector(".ui-hg-card ul")?.textContent).toContain("≥ 90%");
  expect(document.querySelectorAll(".ui-hg-card")).toHaveLength(4);
  await click("Bad Case 诊断");
  expect([...document.querySelectorAll(".product-diagnosis-table thead th")].map(cell => cell.textContent)).toEqual(["题号", "问题", "分类", "缺了什么", "严重程度", ""]);
  expect(document.querySelector(".product-diagnosis-table tbody tr td:nth-child(3)")?.textContent).toBe("检索失败");
  await act(async()=>document.querySelector<HTMLElement>(".product-diagnosis-table tbody tr")!.click());
  expect([...document.querySelectorAll(".case-details > section > h3")].map(header => header.textContent)).toEqual(["业务问题", "答案对比", "检索路径", "优化方向"]);
  expect(document.querySelector('[role="dialog"]')?.textContent).not.toContain("技术详情");
  expect(document.querySelector<HTMLDetailsElement>(".bad-case-details > details")?.open).toBe(false);
  expect(JSON.stringify(input)).toBe(frozen);
  expect((fetch as any).mock.calls.every((call: any[]) => !call[1]?.method || call[1].method === "GET")).toBe(true);
});

it("uses saved generation evidence only and keeps technical identity in its Drawer", async () => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => new Response(JSON.stringify(url.endsWith("/api/bad-cases") ? [bad] : run))));
  await render(<EvaluationPage data={{ evaluation: run, badCases: [bad] }} />);
  expect(document.querySelector(".config-summary-grid")).toBeNull();
  expect([...document.querySelectorAll("button")].some(button=>button.textContent==="查看评测依据")).toBe(false);
  expect(document.body.textContent).not.toContain("judge-only-model");
  expect(document.body.textContent).not.toContain("EVAL-stored");
});

it("keeps Agent diagnosis source-backed, lists saved hypotheses once, and restores the experiment plan and six Sandbox decision rows", async () => {
  const search_space = { top_k: { type: "integer", allowed: [3, 6] }, prompt_strategy: { type: "string", allowed: ["grounded", "abstention"] } };
  const candidates = ["A", "B", "C"].map((label, index) => ({ id: `C-${label}`, status: "evaluated", config: { ...run.config, top_k: index === 0 ? 6 : 3, prompt_strategy: index === 2 ? "abstention" : "grounded" }, reasoning: { candidate_label: label, observed_evidence: [bad.id], proposal: `保存理由 ${label}`, hypothesis: `保存假设 ${label}` }, result: { gates: { passed_count: index === 2 ? 11 : 10, total: 11 }, bad_case_count: index === 2 ? 0 : 1, regression: { status: index === 1 ? "FAIL" : "PASS" }, qualification: { qualified: index === 2 }, comparison_metrics: { input_tokens: 13, output_tokens: 6 } } }));
  const input = { evaluation: run, badCases: [bad], optimization: { id: "EXP-stored", candidates, evaluation_budget: { used: 3, max: 12, reserved_for_d: 1 }, result: { root_cause_cluster: "保存的诊断" } } }, frozen = JSON.stringify(input);
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ search_space }))));
  await render(<EvolutionPage data={input} />);
  expect(document.querySelectorAll(".tabs button")).toHaveLength(4);
  expect(document.querySelectorAll(".agent-case-destinations tbody tr")).toHaveLength(1);
  expect(document.querySelector(".agent-case-destinations")?.textContent).toContain("Candidate A");
  expect(document.querySelector(".agent-case-destinations")?.textContent).not.toContain("Evidence Miss");
  expect(document.querySelectorAll(".diagnosis-cards")).toHaveLength(0);
  await click("进化路线");
  expect(document.querySelectorAll(".candidate-card")).toHaveLength(0);
  expect(document.querySelectorAll(".agent-design-intent")).toHaveLength(3);expect(document.querySelector(".route-planning")).toBeNull();
  expect(document.body.textContent).toContain("保存假设 A");

  await click("Candidate 对比");
  expect(document.querySelectorAll(".candidate-card")).toHaveLength(3);
  expect([...document.querySelectorAll(".candidate-card:first-child .candidate-story-block > .field-label")].map(label => label.textContent)).toEqual(["思路","改动参数","针对的题","预期效果","风险","结果"]);
  expect(document.querySelector(".candidate-card")?.textContent).toContain("Q-stored");
  const target=document.querySelector<HTMLElement>('.candidate-card .candidate-story-block:nth-child(3) .ui-q')!;
  await act(async()=>{target.focus();await new Promise(resolve=>setTimeout(resolve,150));});
  expect(document.querySelector('[role=tooltip]')?.textContent).toContain("持久化问题");
  await click("Candidate 对比");
  expect([...document.querySelectorAll(".ui-ct tbody th")].map(cell => cell.textContent)).toEqual(["答对", "新增 Bad Case", "Hard Gate", "安全拒答率", "P50", "P99"]);
  await act(async()=>document.querySelector<HTMLButtonElement>(".ui-ct-more")!.click());
  for(const label of ["Regression Check"]) expect(document.querySelector(".ui-ct")?.textContent).toContain(label);
  expect(document.body.textContent).not.toContain("Input Tokens");
  await click("查看高级指标");
  expect(document.querySelector('[role="dialog"]')?.textContent).toContain("Input Tokens");
  expect(JSON.stringify(input)).toBe(frozen);
  expect((fetch as any).mock.calls.every((call: any[]) => !call[1]?.method || call[1].method === "GET")).toBe(true);
});

it.each([
  { status: "generated", result: {}, expected: "等待完整评测" },
  { status: "evaluated", result: { qualification: { qualified: true }, regression: { status: "PASS" }, gates: { passed_count: 11, total: 11 } }, expected: "发布资格通过，但保存的最终决策未选择 D，因此保留 Candidate C" },
])("reports 组合 Candidate D $status without inventing failure or replacing the saved Winner", async ({ status, result, expected }) => {
  const winner = { id: "C-C", status: "evaluated", reasoning: { candidate_label: "C" }, result: { qualification: { qualified: true } } };
  const d = { id: "C-D", status, reasoning: { candidate_label: "D", winner_id: winner.id, sources: [] }, result };
  const optimization = { id: "EXP-stored", candidates: [winner, d], result: { report_confirmation: { winner_id: winner.id } }, recommendation: { result: { recommended_candidate: status === "evaluated" ? winner.id : null } } };
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ search_space: {} }))));
  await render(<EvolutionPage data={{ evaluation: run, badCases: [bad], optimization }} />);
  await click("进化路线");await click("Candidate D");
  expect(document.querySelector(".d-story")?.textContent).toContain(expected);
});
