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
  expect(document.querySelectorAll(".stage-stepper li")).toHaveLength(0);
  expect(document.querySelector(".baseline-metrics")?.textContent).toContain("11 / 11");
  expect(document.querySelector(".baseline-metrics")?.textContent).toContain("92.50");
  expect(document.body.textContent).toContain("仍有 20 个逐题失败");
  await act(async () => [...document.querySelectorAll<HTMLButtonElement>("button")].find(b => b.textContent === "Bad Case 诊断")!.click());
  expect([...document.querySelectorAll("thead th")].map(th => th.textContent)).toEqual(["题号 / 问题", "失败现象", "主要技术根因", "优化方向", "详情"]);
  expect(document.querySelector("tbody")?.textContent).not.toContain("Hallucination");
  expect(document.querySelector("tbody")?.textContent).toContain("当前组合筛选无记录");
  expect(document.querySelector(".quality-audit")?.textContent).toContain("历史记录缺少");
  expect(document.querySelector(".baseline-metrics")).toBeNull();
  expect(JSON.stringify(run)).toBe(frozen);
  expect((fetch as any).mock.calls.every((call: any[]) => !call[1]?.method || call[1].method === "GET")).toBe(true);
});
it("orders business evidence before diagnosis and preserves negative anchors and stored primary", async () => {
  await render(<CaseDetails item={{ question_id: "q", question: "业务问题", test_category: "negative", primary_root_cause: "Generation", model_answer: "回答", programmatic_metrics: { retrieval_trace: { candidates: [], final: [] }, evidence_coverage: { candidate_recall: { any_hit: false }, final_context: { any_hit: false }, diagnostic_basis: "保存的证据观察" } } }} snapshot={{ questions: [{ id: "q", acceptable_evidence: [{ source_chunk_ids: ["child"], evidence_key_points: ["业务材料锚点"] }] }] }} config={{}} gates={[]} />);
  const heads = [...document.querySelectorAll(".case-details > section > h3")].map(h => h.textContent);
  expect(heads.indexOf("预期与实际回答")).toBeLessThan(heads.indexOf("证据依据"));
  expect(heads.indexOf("证据依据")).toBeLessThan(heads.indexOf("诊断与优化方向"));
  expect(document.body.textContent).toContain("负向题的材料锚点用于来源追溯");
  expect(document.body.textContent).toContain("业务材料锚点");
  expect(document.body.textContent).toContain("保存的证据观察");
  expect(document.body.textContent).toContain("Generation");
});

it("shows Partial progress and timeout without calling it unrun or identity stale", async () => {
  const run={id:"partial",status:"partial",error_message:"Judge request timed out",dataset_snapshot:{id:"frozen",question_ids:Array(50).fill("q")},result:{completed:8,total:50}};
  vi.stubGlobal("fetch",vi.fn(async (url:string)=>new Response(JSON.stringify(url.endsWith("/api/bad-cases")?[]:run))));
  await render(<EvaluationPage data={{evaluation:run,workspace:{requires_new_baseline:true,current_golden_id:"frozen"}}}/>);
  expect(document.body.textContent).toContain("已完成 8 / 50");
  expect(document.body.textContent).toContain("Judge request timed out");
  expect(document.body.textContent).not.toContain("尚未运行 Baseline");
  expect(document.body.textContent).not.toContain("历史评测 · 当前身份已失效");
});

it("offers a fresh versioned run for an incompatible partial baseline", async () => {
  const run={id:"old",status:"partial",requires_policy_upgrade:true,result:{completed:3,total:50},dataset_snapshot:{question_ids:["q"]},cases:[]};
  vi.stubGlobal("fetch",vi.fn(async (url:string)=>new Response(JSON.stringify(url.endsWith("/api/bad-cases")?[]:run))));
  await render(<EvaluationPage data={{evaluation:run}}/>);
  expect([...document.querySelectorAll("button")].some(b=>b.textContent?.includes("重新运行 Baseline（新版本）"))).toBe(true);
});

it("also labels the historical completed baseline as a new-version rerun", async () => {
  const run={id:"old-completed",status:"completed",requires_policy_upgrade:true,result:{completed:50},dataset_snapshot:{question_ids:["q"]},cases:[]};
  vi.stubGlobal("fetch",vi.fn(async (url:string)=>new Response(JSON.stringify(url.endsWith("/api/bad-cases")?[]:run))));
  await render(<EvaluationPage data={{evaluation:run}}/>);
  expect([...document.querySelectorAll("button")].some(b=>b.textContent?.includes("重新运行 Baseline（新版本）"))).toBe(true);
});
