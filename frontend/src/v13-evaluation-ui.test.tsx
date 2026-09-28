// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { EvaluationPage } from "./pages/EvaluationPage";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
afterEach(() => { document.body.innerHTML = ""; vi.unstubAllGlobals(); });

it("filters persisted Baseline cases and opens their diagnostic detail", async () => {
  const cases = [
    { question_id: "Q01", question: "正常题", test_category: "positive", passed: true, overall_score: 95, programmatic_metrics: { retrieval_hit: true }, judge_result: {} },
    { question_id: "Q02", question: "未召回题", test_category: "ablation", passed: false, overall_score: 50, failure_tags: ["Retrieval Failure"], primary_root_cause: "Retrieval", programmatic_metrics: { retrieval_hit: false }, judge_result: {} },
  ];
  const run = { id: "EVAL-1", status: "completed", dataset_snapshot: { id: "GD-1", question_ids: ["Q01", "Q02"] }, cases, result: { overall_score: 72.5, gates: { gates: [], passed_count: 0, total: 11 } } };
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => new Response(JSON.stringify(String(input).endsWith("/api/bad-cases") ? [] : run), { status: 200 })));
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => { root.render(<EvaluationPage data={{ evaluation: run, badCases: [] }} />); await Promise.resolve(); });
  await act(async () => [...document.querySelectorAll("button")].find(button => button.textContent === "逐题诊断")!.click());
  expect(document.querySelector("tbody")?.textContent).toContain("Q02");
  expect(document.querySelector("tbody")?.textContent).not.toContain("Q01");
  await act(async () => [...document.querySelectorAll("button")].find(button => button.textContent === "全部")!.click());
  expect(document.querySelector("tbody")?.textContent).toContain("Q01");
  await act(async () => [...document.querySelectorAll("button")].find(button => button.textContent === "Retrieval Miss")!.click());
  expect(document.querySelector("tbody")?.textContent).toContain("Q02");
  expect(document.querySelector("tbody")?.textContent).not.toContain("Q01");
  await act(async () => (document.querySelector("tbody tr") as HTMLTableRowElement).click());
  expect(document.querySelector("[role=dialog]")?.textContent).toContain("未召回题");
  await act(async () => root.unmount());
});
