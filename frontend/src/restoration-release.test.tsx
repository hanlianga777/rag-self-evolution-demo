// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { ExperimentPage } from "./pages/ExperimentPage";
import { VersionsPage } from "./pages/VersionsPage";
import { OperationProvider } from "./operation";
(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
let root: ReturnType<typeof createRoot>;
afterEach(() => { if (root) act(() => root.unmount()); document.body.innerHTML = ""; sessionStorage.clear(); vi.unstubAllGlobals(); });
const data = { workspace: { current_baseline_id: "B-new" }, evaluation: { id: "B-new", config: { prompt_strategy: "Grounded", top_k: 4 } }, versions: [{ id: "P-old", status: "active", provenance: "published", config: { prompt_strategy: "Abstention", top_k: 4 }, snapshot: { candidate_id: "EXP-old-C", evaluation_result: { baseline_run_id: "B-old" }, human_release: { decision: "approved" } } }] };
it("separates saved Before/After configuration from live answers and keeps the active publication identity", async () => {
  vi.stubGlobal("fetch", vi.fn());
  root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<ExperimentPage data={data} onOpenCitation={() => {}} />));
  expect(document.querySelector('[aria-label="方案参数差异"]')?.textContent).toContain("Grounded");
  expect(document.querySelector('[aria-label="方案参数差异"]')?.textContent).toContain("Abstention");
  expect(document.querySelector(".comparison-identities")?.textContent).toContain("B-new");
  expect(document.querySelector(".comparison-identities")?.textContent).toContain("P-old");
  expect(document.querySelectorAll(".answer-audit details")).toHaveLength(2);
  expect(document.querySelectorAll(".answer-audit details[open]")).toHaveLength(0);
  expect(fetch).not.toHaveBeenCalled();
});
it("explains the older published baseline and keeps empty history out of the decision screen", async () => {
  root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<OperationProvider restore={false}><VersionsPage data={data} /></OperationProvider>));
  expect(document.querySelector(".release-decision")?.textContent).toContain("来自历史 Baseline");
  await act(async () => root.render(<OperationProvider restore={false}><VersionsPage data={{ versions: [] }} /></OperationProvider>));
  expect(document.querySelector(".release-history")).toBeNull();
});
