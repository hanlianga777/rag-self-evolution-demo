// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it } from "vitest";
import { GovernancePage } from "./pages/GovernancePage";
import { EvolutionPage } from "./pages/EvolutionPage";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
afterEach(() => { document.body.innerHTML = ""; });

it("keeps only the selected governance workspace visible", async () => {
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<GovernancePage data={{ dataset: [], generationRuns: [], snapshots: [] }} />));
  expect(document.body.textContent).toContain("当前 V1 Generation Run");
  expect(document.body.textContent).not.toContain("历史 Candidate（Legacy / 未验证）");
  await act(async () => [...document.querySelectorAll("button")].find(button => button.textContent === "Legacy")!.click());
  expect(document.body.textContent).toContain("历史 Candidate（Legacy / 未验证）");
  expect(document.body.textContent).not.toContain("当前 V1 Generation Run");
  await act(async () => root.unmount());
});

it("shows one Evolution stage instead of four stacked cards", async () => {
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<EvolutionPage data={{ evaluation: {}, badCases: [] }} />));
  expect(document.body.textContent).toContain("Bad Case 分析");
  expect(document.body.textContent).not.toContain("Sandbox Compare");
  await act(async () => [...document.querySelectorAll("button")].find(button => button.textContent?.includes("Sandbox"))!.click());
  expect(document.body.textContent).toContain("Sandbox Compare");
  expect(document.body.textContent).not.toContain("Bad Case 分析");
  await act(async () => root.unmount());
});
