// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { EvolutionPage } from "../../pages/EvolutionPage";

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
let root: ReturnType<typeof createRoot> | undefined;
afterEach(() => {
  if (root) act(() => root!.unmount());
  document.body.replaceChildren();
  sessionStorage.clear();
  history.replaceState(null, "", "/");
  vi.unstubAllGlobals();
});

const e2Id = "EXP-20261123010322145772";
const e3Id = "EXP-20261123150407867927";
const evaluation = { id: "base", status: "completed", result: { total: 20, bad_case_count: 5 } };
const candidate = (id: string, label: string, round: number, failures: number, qualified: boolean) => ({
  id, status: "evaluated",
  reasoning: { candidate_label: label, round, winner_id: label === "D" ? "b" : undefined },
  result: { evaluation_run_id: id, total: 20, bad_case_count: failures, evaluation_complete: true,
    qualification: { qualified, reasons: qualified ? [] : ["出现新错"] },
    all_fixed_question_ids: ["Q09"], new_regression_question_ids: [], continued_failure_question_ids: ["Q15"],
    winner_comparison: label === "D" ? { fixed_cases: [], new_failures: [], promote: false, winner_id: "b" } : undefined },
});
const a = candidate("a", "A", 1, 1, false);
const b = candidate("b", "B", 1, 2, true);
const d = candidate("d", "D", 4, 2, true);
const review = (rows: any[]) => ({ prediction_comparison: { rows } });
const e3 = {
  id: e3Id, baseline_run_id: "base", status: "completed",
  rounds: [{ round: 1, candidate_ids: ["a", "b"], complete: true }],
  candidates: [a, b, d],
  recommendation: { status: "Recommended", result: { recommended_candidate: "b", final_decision: { reason: "D 与 Winner 打平" } } },
  result: {
    mechanism_contract: "113b", decision_stop: null,
    optimization_cycle: { phase: "before_release", hypothesis_terminal_check: { round: 1, outcome: "true", actual_action: "D", reason: "合格后转 D" } },
    hypothesis_chain: { 1: { candidate_id: "a", hypothesis: "增加最终资料可补回证据", question_ids: ["Q09"], inherit: [], exclude: [] } },
    fault_stages: { Baseline: { Q15: { stage: "进了 Final 但生成出错", subtype: "表格归类" } } },
    round_conclusions: {
      1: review([
        { candidate_id: "a", predicted_fixed_question_ids: [], matched_question_ids: [] },
        { candidate_id: "b", predicted_fixed_question_ids: ["Q09", "Q15"], matched_question_ids: ["Q09"] },
      ]),
      D: review([{ candidate_id: "d", predicted_fixed_question_ids: [], matched_question_ids: [] }]),
    },
    parameter_effect_ledger: { current: [
      { candidate_id: "b", display_question_id: "Q09", parameter: "top_k", base_id: "Baseline", changes: { top_k: 6 }, status: "修好", evidence: [{ chunk_id: "saved", before: { final: "未进入" }, after: { final: 2 } }] },
      { candidate_id: "a", display_question_id: "Q15", parameter: null, changes: { top_k: 6, hybrid_alpha: 0.7 }, status: "修好" },
    ], historical: [] },
  },
};
const e2 = { id: e2Id, baseline_run_id: "base", candidates: [candidate("old", "B", 1, 3, true)], result: {
  optimization_cycle: { phase: "before_release" },
  round_conclusions: { 1: review([{ candidate_id: "old", predicted_fixed_question_ids: ["Q09"], matched_question_ids: ["Q09"] }]) },
} };
const retest = (answers: Record<string, (boolean | null)[]>) => ({ identity: "same", questions: answers });
const diagnostics = { runs: {
  base: retest({ Q09: [false, false, false], Q15: [false, false, false], Q03: [true, true, true] }),
  b: retest({ Q09: [true, true, true], Q15: [false, false, false], Q03: [true, false, true] }),
  old: retest({ Q09: [true, true, true], Q15: [false, false, false] }),
} };

async function mount(experiment: any, comparison = e2) {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => new Response(JSON.stringify(
    url.includes("round-trace/1") ? { status: "saved", result: { validation_retries: [
      { attempt: 1, mechanism_checks: { A: [{ decision: "拒绝", display_question_id: "Q15", reason: "作用环节不匹配" }, { decision: "拒绝", display_question_id: "Q09", reason: "缺证据" }] } },
      { attempt: 2, stage: "schema", reason: "格式缺失" },
    ] } } : url.includes(e2Id) ? comparison : url.endsWith("/api/agent/stability-retest") ? diagnostics : {},
  ))));
  root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root!.render(<EvolutionPage data={{ optimization: experiment, evaluation, badCases: [], versions: [] }} />));
}

async function clickButton(label: string) {
  const button = [...document.querySelectorAll("button")].find(item => item.textContent?.trim() === label || item.getAttribute("aria-label") === label);
  expect(button).toBeDefined();
  await act(async () => button!.click());
}

it("shows independent scores, run-bound stability, saved rejection reasons, and the E2/E3 comparison", async () => {
  await mount(e3);
  const chart = document.querySelector('[aria-label="Agent 进化双曲线"]')!;
  const scoreRows = chart.querySelectorAll("tbody tr");
  expect(scoreRows).toHaveLength(5);
  expect(scoreRows[1].textContent).toContain("19/20");
  expect(scoreRows[1].textContent).toContain("18/20");
  expect(scoreRows[1].textContent).toContain("Q09");
  expect(scoreRows[1].textContent).toContain("作用环节不匹配");
  expect(scoreRows[2].textContent).toContain("跳过");
  expect(scoreRows[4].textContent).toContain("18/20");
  const summary = document.querySelector('[aria-label="首屏摘要"]')!;
  expect(summary.textContent).toContain("稳定修好 Q09");
  expect(summary.textContent).toContain("不稳定 Q03");
  expect(summary.textContent).toContain("表格归类");
  const compare = document.querySelector('[aria-label="E2 与 E3 对照"]')!;
  expect(compare.textContent).toContain("1/1");
  expect(compare.textContent).toContain("2/3");
  expect(compare.querySelector('tr[data-metric="prediction"]')?.textContent).toContain("1/2");
  expect(compare.querySelector('tr[data-metric="blocked"] td:last-child')?.textContent).toBe("1");
});

it("checks all three tabs and opens ledger evidence without write requests", async () => {
  await mount(e3);
  await clickButton("进化路线");
  const chain = document.querySelector('[aria-label="跨轮因果链"]')!;
  expect(chain.querySelectorAll("dl")).toHaveLength(4);
  expect([...chain.querySelectorAll("dl")].every(item => item.querySelectorAll("dt").length === 6)).toBe(true);
  expect(chain.textContent).toContain("被拦原因");
  await clickButton("查看参数效果账本");
  expect(document.querySelector('[role="dialog"]')?.textContent).toContain("组合不可归因");
  await clickButton("修好");
  expect(document.querySelector('[role="dialog"]')?.textContent).toContain("未进入 → 第 2 位");
  await clickButton("关闭");
  await clickButton("回归与推荐");
  const ending = document.querySelector('[aria-label="结局卡"]')!;
  expect(ending.textContent).toContain("等待用户决定");
  expect(ending.textContent).toContain("D 与 Winner 打平");
  expect(ending.textContent).toContain("0/3");
  await clickButton("概览");
  expect(document.querySelector('[aria-label="Agent 进化双曲线"]')).not.toBeNull();
  expect(vi.mocked(fetch).mock.calls.every(([, options]) => !options?.method || options.method === "GET")).toBe(true);
});

it("does not borrow results from another Baseline or stability from another recommendation", async () => {
  await mount({ ...e3, recommendation: { status: "Recommended", result: { recommended_candidate: "d" } } },
    { ...e2, baseline_run_id: "another-base" });
  expect(document.querySelector('[aria-label="首屏摘要"]')?.textContent).toContain("稳定性复测未知");
  expect(document.querySelector('[aria-label="E2 与 E3 对照"]')?.textContent).toContain("无法按同一 Baseline 对照");
});

it("shows the saved stop and Baseline fault when no eligible Winner exists", async () => {
  await mount({
    ...e3, candidates: [a], recommendation: null,
    result: { ...e3.result, processing_progress: { baseline_failed_question_ids: ["Q15"] },
      decision_stop: { round: 2, reason: "缺少同环节证据" } },
  });
  const summary = document.querySelector('[aria-label="首屏摘要"]')!;
  expect(summary.textContent).toContain("暂无合格 Winner");
  expect(summary.textContent).toContain("Q15 · 进了 Final 但生成出错");
  expect(summary.textContent).toContain("是 · 缺少同环节证据");
  const round2 = document.querySelectorAll('[aria-label="各阶段成绩与证据"] tbody tr')[2];
  expect(round2.textContent).toContain("未执行");
  expect(round2.textContent).toContain("基准 · 15/20");
});
