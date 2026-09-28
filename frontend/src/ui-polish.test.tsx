// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { StageStepper, CustomSelect } from "./components/Primitives";
import { OverviewPage } from "./pages/OverviewPage";
import { EvaluationPage } from "./pages/EvaluationPage";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
let root: ReturnType<typeof createRoot> | undefined;
afterEach(() => { if (root) act(() => root!.unmount()); root = undefined; document.body.innerHTML = ""; vi.unstubAllGlobals(); });

it("supports keyboard selection with a labelled listbox", async () => {
  const onChange = vi.fn();
  root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root!.render(<CustomSelect ariaLabel="方案" value="a" onChange={onChange} options={[{ value: "a", label: "方案 A" }, { value: "b", label: "方案 B", description: "已评测" }]} />));
  const trigger = document.querySelector('[role="combobox"]') as HTMLButtonElement;
  await act(async () => { trigger.focus(); trigger.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowDown", bubbles: true })); });
  expect(document.querySelector('[role="listbox"]')).not.toBeNull();
  await act(async () => trigger.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true })));
  expect(onChange).toHaveBeenCalledWith("b");
});

it("uses the stage flow on Overview without redundant numbered storyline", async () => {
  root = createRoot(document.body.appendChild(document.createElement("div")));
  const data = { documents: [], overview: { dataset: {}, production: { id: "production-long-id", provenance: "published", config: {} } }, versions: [], evaluation: {}, optimization: {} };
  await act(async () => root!.render(<OverviewPage data={data} navigate={() => {}} />));
  expect(document.querySelector('ol[aria-label="Lifecycle"].stage-stepper')).not.toBeNull();
  expect(document.body.textContent).not.toContain("Baseline 发现问题 → Agent 提出假设");
  expect(document.body.textContent).not.toContain("production-long-id");
  expect(document.body.textContent).not.toContain("01");
});

it("marks completed and current lifecycle stages accessibly", async () => {
  root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root!.render(<StageStepper ariaLabel="Lifecycle" steps={[{ label: "Knowledge", state: "completed" }, { label: "Tuning", state: "current" }, { label: "Release", state: "pending" }]} />));
  expect(document.querySelector('[aria-current="step"]')?.textContent).toContain("Tuning");
  expect(document.querySelectorAll(".stage-stepper li.completed")).toHaveLength(1);
  expect(document.querySelectorAll(".stage-stepper li.pending")).toHaveLength(1);
});

it("formats Baseline time locally and shortens the run ID", async () => {
  const run = { id: "EVAL-20260927140423956071", status: "completed", created_at: "2026-09-27T14:04:23.956836+00:00", dataset_snapshot: { question_ids: [] }, result: { gates: { gates: [], total: 11, passed_count: 9 } } };
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => new Response(JSON.stringify(String(input).endsWith("/api/bad-cases") ? [] : run), { status: 200 })));
  root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => { root!.render(<EvaluationPage data={{ evaluation: run, badCases: [] }} />); await Promise.resolve(); });
  expect(document.body.textContent).toContain("2026-09-27 22:04:23");
  expect(document.querySelector("details")?.textContent).toContain(run.created_at);
  expect(document.querySelector("details")?.hasAttribute("open")).toBe(false);
  expect(document.querySelector(".short-id")?.textContent).not.toBe(run.id);
});

it("keeps the Baseline Bad Case table compact and detail ready", async () => {
  const run = { id: "EVAL-1", status: "completed", dataset_snapshot: { question_ids: ["Q1"] }, result: { gates: { gates: [], total: 11, passed_count: 8 } }, cases: [{ question_id: "Q1", question: "发生故障后如何恢复运行？", passed: false, primary_root_cause: "Generation", failure_tags: ["Hallucination", "Citation Failure", "Unsupported Claim"] }] };
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => new Response(JSON.stringify(String(input).endsWith("/api/bad-cases") ? [] : run), { status: 200 })));
  root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => { root!.render(<EvaluationPage data={{ evaluation: run, badCases: [] }} />); await Promise.resolve(); });
  await act(async () => [...document.querySelectorAll("button")].find(button => button.textContent === "Bad Case 诊断")!.click());
  expect([...document.querySelectorAll("thead th")].map(item => item.textContent)).toEqual(["Case", "Question", "Root Cause", "Affected Gate", "Evidence"]);
  expect(document.querySelector("tbody")?.textContent).toContain("+1");
  expect(document.querySelector("tbody")?.textContent).not.toContain("Not Passed");
});
