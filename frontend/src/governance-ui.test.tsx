// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { GovernancePage } from "./pages/GovernancePage";

afterEach(() => { document.body.innerHTML = ""; vi.restoreAllMocks(); });

it("keeps Golden approval disabled until Probe and QC both pass", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ stage: "golden" }), { status: 200 })));
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => { root.render(<GovernancePage data={{ generationRuns: [{ id: "GGEN-test", status: "candidate_generated", question_ids: ["GGC-001"], artifacts: {} }], dataset: [{ id: "GGC-001", legacy_question_type: "v1_mini", question: "测试题", test_category: "positive", review_status: "human_review_pending", probe_status: "probe_pending", stage: "candidate", evidence: [] }] }} />); });

  expect(document.body.textContent).toContain("测试集治理");
  const approval = [...document.querySelectorAll("button")].find(button => button.textContent === "批准为 Golden")!;
  expect((approval as HTMLButtonElement).disabled).toBe(true);
});

it("enables Golden approval only after both checks pass", async () => {
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => { root.render(<GovernancePage data={{ generationRuns: [{ id: "GGEN-test", status: "candidate_generated", question_ids: ["GGC-033"], artifacts: {} }], dataset: [{ id: "GGC-033", legacy_question_type: "v1_mini", question: "测试题", test_category: "negative", review_status: "human_review_pending", probe_status: "probe_passed", qc_status: "qc_passed", stage: "candidate", evidence: [] }] }} />); });
  const approval = [...document.querySelectorAll("button")].find(button => button.textContent === "批准为 Golden")!;
  expect((approval as HTMLButtonElement).disabled).toBe(false);
});

it("restores a running generation and reads persisted slot progress", async () => {
  const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({ id: "GGEN-live", status: "generating", question_ids: [], artifacts: { hard_validation: { progress: { stage: "generating", slot: "Q03", completed_slots: 2, total_slots: 20 } } } }), { status: 200 }));
  vi.stubGlobal("fetch", fetcher);
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => { root.render(<GovernancePage data={{ generationRuns: [{ id: "GGEN-live", status: "queued", question_ids: [], artifacts: {} }], dataset: [] }} />); });
  expect(fetcher).toHaveBeenCalledWith(expect.stringContaining("/api/governance/generation-runs/GGEN-live"));
  expect(document.body.textContent).toContain("Q03");
  expect(document.body.textContent).toContain("2 / 20");
  expect((([...document.querySelectorAll("button")].find(button => button.textContent?.includes("生成 V1 Mini"))) as HTMLButtonElement).disabled).toBe(true);
  await act(async () => root.unmount());
});
