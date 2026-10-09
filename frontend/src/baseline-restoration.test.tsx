// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { EvaluationPage, CaseDetails } from "./pages/EvaluationPage";
(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
let root: ReturnType<typeof createRoot>;
afterEach(() => { act(() => root?.unmount()); document.body.innerHTML = ""; vi.unstubAllGlobals(); });
const render = async (node: React.ReactNode) => { root = createRoot(document.body.appendChild(document.createElement("div"))); await act(async () => root.render(node)); };
it("restores compact Baseline summary without treating aggregate Gate success as all cases passing", async () => {
  const run = { id: "saved", status: "completed", dataset_snapshot: { id: "frozen", profile: { name: "Medium", positive_count: 20, ablation_count: 10, negative_count: 20 }, question_ids: ["q"] }, cases: [{ question_id: "q", question: "业务问题", passed: false, primary_root_cause: "Generation", failure_tags: ["Hallucination"], judge_result: { correctness: 4 } }], result: { overall_score: 92.5, bad_case_count: 20, gates: { passed: true, passed_count: 11, total: 11, gates: [] } } };
  const frozen = JSON.stringify(run);
  vi.stubGlobal("fetch", vi.fn(async (url: string) => new Response(JSON.stringify(url.endsWith("/api/bad-cases") ? [] : run))));
  await render(<EvaluationPage data={{ evaluation: run }} />);
  expect(document.querySelectorAll(".stage-stepper li")).toHaveLength(4);
  expect(document.querySelector(".baseline-metrics")?.textContent).toContain("11 / 11");
  expect(document.querySelector(".baseline-metrics")?.textContent).toContain("92.50");
  expect(document.body.textContent).toContain("仍有 20 个单题问题");
  await act(async () => [...document.querySelectorAll<HTMLButtonElement>("button")].find(b => b.textContent === "Bad Case 诊断")!.click());
  expect([...document.querySelectorAll("thead th")].map(th => th.textContent)).toEqual(["问题", "初步类型", "失败观察", "关键指标", "详情"]);
  expect(document.querySelector("tbody")?.textContent).not.toContain("Hallucination");
  expect(document.querySelector("tbody")?.textContent).toContain("正确性 100.00%");
  expect(JSON.stringify(run)).toBe(frozen);
  expect((fetch as any).mock.calls.every((call: any[]) => !call[1]?.method || call[1].method === "GET")).toBe(true);
});
it("orders business evidence before diagnosis and preserves negative anchors and stored primary", async () => {
  await render(<CaseDetails item={{ question_id: "q", question: "业务问题", test_category: "negative", primary_root_cause: "Generation", model_answer: "回答", programmatic_metrics: { retrieval_trace: { candidates: [], final: [] }, evidence_coverage: { candidate_recall: { any_hit: false }, final_context: { any_hit: false }, diagnostic_basis: "保存的证据观察" } } }} snapshot={{ questions: [{ id: "q", acceptable_evidence: [{ source_chunk_ids: ["child"], evidence_key_points: ["业务材料锚点"] }] }] }} config={{}} gates={[]} />);
  const heads = [...document.querySelectorAll(".case-details > section > h3")].map(h => h.textContent);
  expect(heads.indexOf("预期与实际回答")).toBeLessThan(heads.indexOf("Golden Evidence"));
  expect(heads.indexOf("Judge")).toBeLessThan(heads.indexOf("初步诊断"));
  expect(document.body.textContent).toContain("材料 Anchor 不代表答案 Evidence");
  expect(document.body.textContent).toContain("业务材料锚点");
  expect(document.body.textContent).toContain("保存的证据观察");
  expect(document.body.textContent).toContain("Generation");
});
