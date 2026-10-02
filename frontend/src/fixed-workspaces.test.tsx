// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it } from "vitest";
import { GovernancePage } from "./pages/GovernancePage";
import { EvolutionPage } from "./pages/EvolutionPage";
import { Status } from "./components/Primitives";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
afterEach(() => { document.body.innerHTML = ""; });

it("colors Not Qualified as a failed state", async () => {
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<Status value="Not Qualified" />));
  expect(document.querySelector(".badge.bad")?.textContent).toBe("Gate 未通过");
  await act(async () => root.unmount());
});

it("keeps only the selected governance workspace visible", async () => {
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<GovernancePage data={{ dataset: [], generationRuns: [], snapshots: [] }} />));
  expect(document.body.textContent).toContain("当前测试集");
  expect(document.body.textContent).not.toContain("历史 Candidate（未验证）");
  await act(async () => [...document.querySelectorAll("button")].find(button => button.textContent === "历史 Snapshot")!.click());
  expect(document.body.textContent).toContain("历史 Candidate（未验证）");
  expect(document.querySelector('button[aria-pressed="true"]')?.textContent).toBe("当前测试集");
  await act(async () => root.unmount());
});

it("shows one Evolution stage instead of four stacked cards", async () => {
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<EvolutionPage data={{ evaluation: {}, badCases: [] }} />));
  expect(document.body.textContent).toContain("Root Cause Diagnosis");
  expect(document.body.textContent).not.toContain("Sandbox 对比");
  await act(async () => [...document.querySelectorAll("button")].find(button => button.textContent?.includes("Sandbox"))!.click());
  expect(document.body.textContent).toContain("Sandbox 对比");
  expect(document.body.textContent).not.toContain("Root Cause Diagnosis");
  await act(async () => root.unmount());
});

it("shows no effective composite without inventing a D candidate", async () => {
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  const optimization = { id: "EXP-1", candidates: [], result: { report_confirmation: { winner_id: "C-1" }, composite: { status: "no_effective_composite" } } };
  await act(async () => root.render(<EvolutionPage data={{ evaluation: {}, badCases: [], optimization }} />));
  await act(async () => [...document.querySelectorAll("button")].find(button => button.textContent === "A / B / C / D")!.click());
  expect(document.body.textContent).toContain("保留 Gate 2 Winner");
  expect(document.body.textContent).toContain("没有有效的 Composite D");
  expect(document.querySelectorAll(".composite-card .candidate-card")).toHaveLength(0);
  await act(async () => root.unmount());
});
