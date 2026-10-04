// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { OverviewPage } from "./pages/OverviewPage";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
let root: ReturnType<typeof createRoot>;
afterEach(() => { if (root) act(() => root.unmount()); document.body.innerHTML = ""; vi.unstubAllGlobals(); });
const snapshot = { id: "GD-formal", generation_run_id: "GGEN-formal", question_ids: ["Q1", "Q2", "Q3"], questions: ["positive", "ablation", "negative"].map((test_category, index) => ({ id: `Q${index + 1}`, test_category })), corpus_fingerprint: { D: "fixture-current" } };
const input = (generation_status: string) => ({ workspace: { current_baseline_id: "B1", current_golden_id: snapshot.id, current_corpus_fingerprint: snapshot.corpus_fingerprint, requires_new_golden: false }, snapshots: [{ id: "GD-other", status: "approved", snapshot: { question_ids: ["unrelated"] } }, { id: snapshot.id, status: "approved", snapshot }], overview: { dataset: { generation_run_id: "GGEN-new", generation_status, total: 1, expected_count: 49, approved: 0, positive: 1, ablation: 0, negative: 0 } }, evaluation: { id: "B1", status: "completed", dataset_version_id: snapshot.id, dataset_snapshot: snapshot, result: { gates: { passed_count: 9, total: 11 }, bad_case_count: 7 } }, optimization: {}, versions: [] });
const render = async (data: any) => { vi.stubGlobal("fetch", vi.fn()); root = createRoot(document.body.appendChild(document.createElement("div"))); await act(async () => root.render(<OverviewPage data={data} navigate={() => {}} />)); };

it.each(["generating", "needs_regeneration", "failed"])("keeps the frozen Golden and Agent next step when a different work Run is %s", async status => {
  const data = input(status), before = JSON.stringify(data);
  await render(data);
  expect(document.querySelector('[aria-label="全链路阶段"]')?.textContent).toContain("3 题");
  expect(document.querySelector('[aria-label="全链路阶段"]')?.textContent).toContain("正向 1 / 消融 1 / 负向 1");
  expect(document.querySelector('[aria-label="全链路阶段"]')?.textContent).toContain("Golden Dataset已冻结");
  expect(document.querySelector(".next-action h2")?.textContent).toBe("运行 Optimization Agent");
  expect(document.querySelector(".next-action a")?.getAttribute("href")).toBe("#evolution");
  expect(document.querySelector(".overview-work-run")?.textContent).toContain("工作 Run");
  expect(document.querySelectorAll(".stage-stepper")).toHaveLength(1);
  expect(JSON.stringify(data)).toBe(before);
  expect(fetch).not.toHaveBeenCalled();
});

it("keeps the current recommendation at human release despite an unfinished new work Run", async () => {
  const candidate = { id: "E1-C", reasoning: { candidate_label: "C" }, result: { qualification: { qualified: true } } };
  const data = { ...input("failed"), optimization: { id: "E1", baseline_run_id: "B1", candidates: [candidate], recommendation: { result: { status: "Recommended", recommended_candidate: candidate.id } } }, versions: [{ id: "P-old", status: "active", provenance: "published", snapshot: { candidate_id: "E0-A" } }] };
  await render(data);
  expect(document.querySelector(".next-action h2")?.textContent).toBe("Gate 3 · 人工确认发布");
  expect(document.querySelector(".next-action a")?.getAttribute("href")).toBe("#versions");
  expect(document.querySelector('[aria-label="全链路阶段"]')?.textContent).toContain("3 题");
});

it("uses the same-identity Baseline frozen Snapshot when the snapshot list is absent", async () => {
  const data: any = input("generating"); delete data.snapshots;
  await render(data);
  expect(document.querySelector('[aria-label="全链路阶段"]')?.textContent).toContain("3 题");
  expect(document.querySelector(".next-action a")?.getAttribute("href")).toBe("#evolution");
});

it("does not promote unrelated approved work data or an old Corpus to frozen eligibility", async () => {
  const data: any = input("completed");
  data.overview.dataset.approved = 49;
  data.workspace.requires_new_golden = true;
  data.workspace.current_corpus_fingerprint = { D: "fixture-changed" };
  await render(data);
  expect(document.querySelector(".next-action a")?.getAttribute("href")).toBe("#governance");
  expect(document.querySelector('[aria-label="全链路阶段"]')?.textContent).not.toContain("Golden Dataset已冻结");
  await act(async () => root.unmount());
  data.workspace.requires_new_golden = false;
  data.workspace.current_golden_id = "GD-missing";
  await render(data);
  expect(document.querySelector(".next-action a")?.getAttribute("href")).toBe("#governance");
  expect(document.querySelector('[aria-label="全链路阶段"]')?.textContent).not.toContain("Golden Dataset已冻结");
});
