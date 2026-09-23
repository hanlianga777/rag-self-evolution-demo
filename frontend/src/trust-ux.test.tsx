// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it } from "vitest";
import { EvaluationPage } from "./pages/EvaluationPage";
import { OverviewPage } from "./pages/OverviewPage";

let root: ReturnType<typeof createRoot>;
afterEach(() => { root?.unmount(); document.body.innerHTML = ""; });

it("shows Not Run rather than a historical seed score", async () => {
  root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => { root.render(<EvaluationPage data={{ evaluation: { status: "not_run" } }} navigate={() => {}} />); });
  expect(document.body.textContent).toContain("未运行");
  expect(document.body.textContent).toContain("尚未运行 Baseline");
});

it("summarizes current governance without inventing an optimization result", async () => {
  root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => { root.render(<OverviewPage data={{ overview: { dataset: { approved: 0, pending_review: 40 } }, versions: [], badCases: [], optimization: { status: "not_run" } }} navigate={() => {}} />); });
  expect(document.body.textContent).toContain("待人工审核");
  expect(document.body.textContent).not.toContain("87.6");
});
