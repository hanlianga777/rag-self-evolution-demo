// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { EvolutionPage } from "./pages/EvolutionPage";

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
let root: ReturnType<typeof createRoot>;
afterEach(() => { if (root) act(() => root.unmount()); document.body.innerHTML = ""; vi.unstubAllGlobals(); });
const bad = { id: "BC1", run_id: "E1", question_id: "Q1", category: "Generation", result: { question: "设备停机后如何恢复运行？", failure_tags: ["Hallucination"], primary_root_cause: "Generation" } };
const candidates = ["A", "B", "C"].map((candidate_label, i) => ({ id: `EXP-R1-${candidate_label}`, status: "generated", config: { top_k: 4 + i, prompt_strategy: "grounded" }, reasoning: { round: 1, candidate_label, hypothesis: `验证假设${candidate_label}`, proposal: `方案依据${candidate_label}`, risk: "可能增加噪声", observed_evidence: ["BC1"] }, result: {} }));
const data = { workspace: { current_baseline_id: "E1" }, evaluation: { id: "E1", status: "completed", config: { top_k: 4 }, result: { gates: { passed: true, passed_count: 11, total: 11 }, bad_case_count: 1 } }, badCases: [bad], optimization: { id: "EXP", baseline_run_id: "E1", candidates, evaluation_budget: { used: 0, max: 12, reserved_for_d: 1 }, rounds: [{ round: 1, total: 3, evaluated: 0, complete: false }], result: { root_cause_cluster: "基于已保存证据验证回答边界" } } };
async function mount(value: any = data) { vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ search_space: {} })))); root = createRoot(document.body.appendChild(document.createElement("div"))); await act(async () => root.render(<EvolutionPage data={value} />)); }
async function click(label: string) { await act(async () => [...document.querySelectorAll<HTMLButtonElement>("button")].find(b => b.textContent === label)!.click()); }

it("restores stages and complete generated plans without inventing evaluated results", async () => {
  const frozen = JSON.stringify(data); await mount();
  expect(document.querySelectorAll(".stage-stepper li")).toHaveLength(6);
  expect(document.body.textContent).toContain("仍有 1 个 Bad Case");
  await click("优化 Agent");
  expect(document.body.textContent).toContain("实验概览");
  expect(document.querySelectorAll(".experiment-plan article")).toHaveLength(3);
  expect(document.body.textContent).not.toMatch(/null|undefined|\[object Object\]/);
  await click("A / B / C / D");
  expect([...document.querySelectorAll(".candidate-card:first-child .field-label")].map(e => e.textContent)).toEqual(["WHY", "TARGET", "CHANGE", "EXPECTED", "RISK", "RESULT"]);
  expect(document.querySelector(".candidate-card")?.textContent).toContain("Sandbox 尚未运行");
  await click("查看目标 1 题");
  expect(document.querySelector('[role="dialog"]')?.textContent).toContain(bad.result.question);
  expect(JSON.stringify(data)).toBe(frozen);
  expect((fetch as any).mock.calls.every(([, init]: any) => !init?.method)).toBe(true);
});

it("shows six decision rows and blocks Gate2 while another candidate is generated", async () => {
  const value = { ...data, optimization: { ...data.optimization, candidates: [{ ...candidates[0], status: "evaluated", result: { qualification: { qualified: true }, gates: { total: 11, passed_count: 11 }, regression: { status: "PASS", new_critical_failures: 0, new_ordinary_failures: 0 }, target_bad_cases_fixed: 1 } }, candidates[1], candidates[2]] } };
  await mount(value); await click("Sandbox");
  expect(document.querySelectorAll(".sandbox-core-table tbody tr")).toHaveLength(6);
  expect(document.querySelector(".sandbox-core-table")?.textContent).toContain("修复原 Bad Case");
  expect(document.body.textContent).not.toContain("确认报告与赢家");
  expect(document.body.textContent).toContain("运行本轮 A/B/C Sandbox");
});

it("keeps a failed next-round generation visible alongside prior saved candidates", async () => {
  await mount({ ...data, optimization: { ...data.optimization, status: "failed" } });
  const generation = document.querySelectorAll(".stage-stepper li")[1];
  expect(generation.classList.contains("blocked")).toBe(true);
  expect(generation.textContent).toContain("生成失败");
});
