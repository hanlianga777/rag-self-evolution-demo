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
  await act(async () => { ([...document.querySelectorAll("button")].find(button => button.textContent === "查看详情") as HTMLButtonElement).click(); });
  const approval = [...document.querySelectorAll("button")].find(button => button.textContent === "批准")!;
  expect((approval as HTMLButtonElement).disabled).toBe(true);
  expect(document.body.textContent).toContain("Probe 未通过");
});

it("enables Golden approval only after both checks pass", async () => {
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => { root.render(<GovernancePage data={{ generationRuns: [{ id: "GGEN-test", status: "candidate_generated", question_ids: ["GGC-033"], artifacts: {} }], dataset: [{ id: "GGC-033", legacy_question_type: "v1_mini", question: "测试题", test_category: "negative", review_status: "human_review_pending", probe_status: "probe_passed", qc_status: "qc_passed", stage: "candidate", evidence: [] }] }} />); });
  await act(async () => { ([...document.querySelectorAll("button")].find(button => button.textContent === "查看详情") as HTMLButtonElement).click(); });
  const approval = [...document.querySelectorAll("button")].find(button => button.textContent === "批准")!;
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

it("shows 20 compact review rows, honest filters, and three full-run exports", async () => {
  const questions = Array.from({ length: 20 }, (_, index) => ({
    id: `GGC-${index + 1}`, slot: `Q${String(index + 1).padStart(2, "0")}`,
    question: `测试问题 ${index + 1}`, test_category: index < 8 ? "positive" : index < 12 ? "ablation" : "negative",
    legacy_question_type: "v1_mini", probe_status: index < 7 ? "needs_revision" : "probe_passed",
    qc_status: index < 7 ? "qc_failed" : index === 7 ? "qc_pending" : "qc_passed", review_status: "human_review_pending", stage: "candidate", evidence: [],
    probe: { score: index < 7 ? 72 : 95, threshold: 90 }, qc: { score: index < 7 ? 72 : 90, threshold: 85 },
  }));
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ questions }), { status: 200 })));
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => { root.render(<GovernancePage data={{ generationRuns: [{ id: "GGEN-20", status: "completed", question_ids: questions.map(row => row.id), artifacts: {} }], dataset: questions }} />); });

  expect(document.querySelectorAll(".review-table tbody tr")).toHaveLength(20);
  expect(document.querySelectorAll(".review-table tbody button")).toHaveLength(20);
  expect(document.body.textContent).toContain("Probe 未通过 7");
  expect(document.body.textContent).toContain("QC 未通过 7");
  expect(document.body.textContent).toContain("仍有 8 道阻塞题");
  expect(document.body.textContent).toContain("待 QC 1");
  expect(document.querySelectorAll(".export-menu a")).toHaveLength(3);
  await act(async () => { ([...document.querySelectorAll(".review-filters button")].find(button => button.textContent?.includes("Probe 未通过")) as HTMLButtonElement).click(); });
  expect(document.querySelectorAll(".review-table tbody tr")).toHaveLength(7);
  expect(document.querySelectorAll(".export-menu a")).toHaveLength(3);
  await act(async () => { ([...document.querySelectorAll(".review-table tbody button")][0] as HTMLButtonElement).click(); });
  expect(document.body.textContent).toContain("Probe 72 < 90");
  await act(async () => root.unmount());
});

it("shows persisted quality rerun progress and resumes polling after refresh", async () => {
  const questions = Array.from({ length: 20 }, (_, index) => ({ id: `V1-${index}`, slot: `Q${String(index + 1).padStart(2, "0")}`, question: "测试题", test_category: "positive", legacy_question_type: "v1_mini", probe_status: "probe_pending", qc_status: "qc_pending", qc: { score: 73 }, stage: "candidate", evidence: [] }));
  const run = { id: "GGEN-quality", status: "completed", question_ids: questions.map(row => row.id), artifacts: { hard_validation: { quality_rerun: { status: "running", stage: "probe", slot: "Q05", completed: 4, probe_passed: 3, probe_failed: 1, qc_passed: 2, qc_failed: 1, qc_skipped: 1, slots: { Q01: { qc: "skipped" } }, started_at: new Date().toISOString() } } } };
  vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string) => Promise.resolve(new Response(JSON.stringify(url.includes("export") ? { questions } : run), { status: 200 }))));
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => { root.render(<GovernancePage data={{ generationRuns: [run], dataset: questions }} />); });
  expect(document.body.textContent).toContain("4 / 20");
  expect(document.body.textContent).toContain("QC 通过 2，失败 1，跳过 1");
  expect((([...(document.querySelectorAll("button"))].find(button => button.textContent === "重新运行 Probe / QC")) as HTMLButtonElement).disabled).toBe(true);
  expect(fetch).toHaveBeenCalledWith(expect.stringContaining("/api/governance/generation-runs/GGEN-quality"));
  await act(async () => { ([...document.querySelectorAll("button")].find(button => button.textContent === "查看详情") as HTMLButtonElement).click(); });
  expect(document.body.textContent).toContain("本次重跑因 Probe 未通过，已跳过 QC");
  await act(async () => root.unmount());
});
