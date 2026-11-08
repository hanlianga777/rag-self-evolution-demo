// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { EvolutionPage } from "./pages/EvolutionPage";

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
let root: ReturnType<typeof createRoot>;
afterEach(() => { if (root) act(() => root.unmount()); document.body.innerHTML = ""; vi.unstubAllGlobals(); });
const bad = { id: "BC1", run_id: "E1", question_id: "Q1", category: "Generation", result: { passed: false, question: "设备停机后如何恢复运行？", failure_tags: ["Hallucination"], diagnostic_view: {is_technical_bad_case: true, analysis_category: "rag_failure", primary_root_cause: "Generation", target_eligible: true, optimization_directions: ["grounded_generation"]}, primary_root_cause: "Generation" } };
const candidates = ["A", "B", "C"].map((candidate_label, i) => ({ id: `EXP-R1-${candidate_label}`, status: "generated", config: { top_k: 4 + i, prompt_strategy: "grounded" }, reasoning: { round: 1, candidate_label, hypothesis: `验证假设${candidate_label}`, proposal: `方案依据${candidate_label}`, risk: "可能增加噪声", observed_evidence: ["BC1"] }, result: {} }));
const data = { workspace: { current_baseline_id: "E1" }, evaluation: { id: "E1", status: "completed", config: { top_k: 4 }, result: { gates: { passed: true, passed_count: 11, total: 11 }, bad_case_count: 1 } }, badCases: [bad], optimization: { id: "EXP", baseline_run_id: "E1", candidates, evaluation_budget: { used: 0, max: 12, reserved_for_d: 1 }, rounds: [{ round: 1, total: 3, evaluated: 0, complete: false }], result: { root_cause_cluster: "基于已保存证据验证回答边界" } } };
async function mount(value: any = data) { vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ search_space: {} })))); root = createRoot(document.body.appendChild(document.createElement("div"))); await act(async () => root.render(<EvolutionPage data={value} />)); }
async function click(label: string) { await act(async () => [...document.querySelectorAll<HTMLButtonElement>("button")].find(b => b.textContent === label)!.click()); }

it("restores stages and complete generated plans without inventing evaluated results", async () => {
  const frozen = JSON.stringify(data); await mount();
  expect(document.querySelectorAll(".tabs button")).toHaveLength(5); expect(document.querySelectorAll(".ui-agent-stats > div")).toHaveLength(4);
  expect(document.body.textContent).toContain("1 个 Bad Case");
  await click("进化路线");
  expect(document.body.textContent).toContain("问题与策略关联");
  expect(document.querySelectorAll(".strategy-hypotheses > section")).toHaveLength(3);
  expect(document.body.textContent).not.toMatch(/null|undefined|\[object Object\]/);
  await click("A/B/C/D");
  expect([...document.querySelectorAll(".candidate-card:first-child .field-label")].map(e => e.textContent)).toEqual(["方向", "核心思路", "参数变化", "针对的题", "预期效果", "风险", "结果"]);
  expect(document.querySelector(".candidate-card")?.textContent).toContain("Sandbox 尚未运行");
  await click("查看目标 1 题");
  expect(document.querySelector('[role="dialog"]')?.textContent).toContain(bad.result.question);
  expect(JSON.stringify(data)).toBe(frozen);
  expect((fetch as any).mock.calls.every(([, init]: any) => !init?.method)).toBe(true);
});

it("shows a status row and separate candidate/release decision rows and blocks Gate2 while another candidate is generated", async () => {
  const value = { ...data, optimization: { ...data.optimization, candidates: [{ ...candidates[0], status: "evaluated", result: { qualification: { qualified: true }, gates: { total: 11, passed_count: 11 }, regression: { status: "PASS", new_critical_failures: 0, new_ordinary_failures: 0 }, target_bad_cases_fixed: 1 } }, candidates[1], candidates[2]] } };
  await mount(value); await click("Sandbox");
  expect(document.querySelectorAll(".sandbox-core-table tbody tr")).toHaveLength(5);
  await act(async()=>document.querySelector<HTMLButtonElement>(".ui-ct-more")!.click());
  expect(document.querySelector(".sandbox-core-table")?.textContent).toContain("全部原 Bad Case 修好");
  expect(document.body.textContent).not.toContain("确认报告与赢家");
  expect(document.body.textContent).toContain("运行本轮 A/B/C Sandbox");
});

it("keeps a failed next-round generation visible alongside prior saved candidates", async () => {
  await mount({ ...data, optimization: { ...data.optimization, status: "failed" } });
  const generation = document.querySelector(".ui-agent-stats")!;
  expect(generation.textContent).toContain("生成失败");
});

it("confirms an eligible Sandbox continuation before executing it", async () => {
  await mount({ ...data, optimization:{ ...data.optimization, candidates:[{ ...candidates[0],status:"failed",result:{evaluation_run_id:"PARTIAL"}},candidates[1],candidates[2]] } });
  await click("A/B/C/D");
  const button=[...document.querySelectorAll<HTMLButtonElement>("button")].find(b=>b.textContent==="继续 Sandbox")!;
  expect(button.disabled).toBe(false);
  await click("继续 Sandbox");
  expect(document.querySelector(".confirm-dialog")).not.toBeNull();
  expect((fetch as any).mock.calls.some(([,init]:any)=>init?.method==="POST")).toBe(false);
  await act(async()=>document.querySelector<HTMLButtonElement>(".confirm-dialog button.primary")!.click());
  expect((fetch as any).mock.calls.some(([,init]:any)=>init?.method==="POST")).toBe(true);
});

it("allows manual continuation of an interrupted candidate when its cycle is no longer running", async () => {
  await mount({...data,optimization:{...data.optimization,result:{optimization_cycle:{status:'failed'}},candidates:[{...candidates[0],status:'failed',product_interruption:true,result:{evaluation_complete:false,completed:17,total:50,evaluation_run_id:'PARTIAL'}},candidates[1],candidates[2]]}});
  await click('A/B/C/D');
  const button=[...document.querySelectorAll<HTMLButtonElement>('button')].find(b=>b.textContent==='继续 Sandbox');
  expect(button).toBeDefined();
  expect(button!.disabled).toBe(false);
  await click('继续 Sandbox');
  await act(async()=>document.querySelector<HTMLButtonElement>('.confirm-dialog button.primary')!.click());
  expect((fetch as any).mock.calls.some(([url,init]:any)=>url.endsWith('/candidates/EXP-R1-A/run') && init?.method==='POST')).toBe(true);
});

it("runs three saved candidates while retaining an honest uncovered-question warning", async () => {
  await mount({...data,optimization:{...data.optimization,coverage_plan:{status:'incomplete',covered_count:5,total:6,matrix:[{question_id:'Q38',candidates:[],gap:'本轮剩余A/B/C容量不足'}]}}});
  await click('A/B/C/D');
  const runButton=[...document.querySelectorAll<HTMLButtonElement>('button')].find(b=>b.textContent==='运行 Sandbox')!;
  expect(runButton.disabled).toBe(false);
  await act(async()=>runButton.click());
  await act(async()=>document.querySelector<HTMLButtonElement>('.confirm-dialog button.primary')!.click());
  expect((fetch as any).mock.calls.some(([url,init]:any)=>url.endsWith('/candidates/EXP-R1-A/run') && init?.method==='POST')).toBe(true);
});

it("keeps incomplete coverage out of Sandbox and offers same-round zero-call completion", async () => {
  await mount({ ...data, optimization:{...data.optimization,candidates:[candidates[0]],coverage_plan:{status:"incomplete",covered_count:1,total:10,binding:"reviewed",matrix:[{question_id:"Q1",candidates:[],gap:"缺口待记录"}]}}});
  expect(document.body.textContent).toContain("补齐本轮规划（不收费）");
  expect(document.body.textContent).not.toContain("运行本轮 A/B/C Sandbox");
  await click("进化路线");
  expect(document.body.textContent).toContain("规划未完成");
  await click("A/B/C/D");
  expect([...document.querySelectorAll<HTMLButtonElement>("button")].find(b=>b.textContent==="运行 Sandbox")?.disabled).toBe(true);
  expect((fetch as any).mock.calls.every(([,init]:any)=>init?.method!=="POST")).toBe(true);
});

it("suppresses incomplete final scores, preserves progress and blocks unreconciled paid continuation", async () => {
  const incomplete={evaluation_complete:false,completed:38,total:50,gates:{passed_count:0,total:11,passed:null},bad_case_count:6,regression:{status:"FAIL",new_critical_failures:12,new_ordinary_failures:3},qualification:{qualified:false},request_accounting:{call_events:156,unknown_usage_events:1}};
  await mount({...data,optimization:{...data.optimization,candidates:[{...candidates[0],status:"failed",result:incomplete,resume_plan:{can_resume:false,reusable:38,completed:38,total:50,next_question_id:"Q39",reason:"需先对账：Embedding请求结果未知"}},candidates[1],candidates[2]],recommendation:{status:"No Qualified Candidate"}}});
  await click("Sandbox");
  await act(async()=>document.querySelector<HTMLButtonElement>(".ui-ct-more")!.click());
  expect(document.querySelector('.sandbox-core-table')?.textContent).toContain("未完成");
  expect(document.querySelector('.sandbox-core-table')?.textContent).toContain("未完成");
  expect(document.querySelector('.sandbox-core-table')?.textContent).not.toContain("0 / 11");
  expect(document.querySelector('.sandbox-core-table')?.textContent).not.toContain("严重 12");
  await click("最终推荐");
  expect(document.body.textContent).toContain("本轮实验尚未完成");
  expect(document.body.textContent).not.toContain("保存结论：本轮暂无合格候选方案");
  await click("A/B/C/D");
  expect(document.body.textContent).toContain("已完成 38/50");
  expect(document.body.textContent).toContain("需先对账");
  expect([...document.querySelectorAll<HTMLButtonElement>('button')].find(b=>b.textContent==='继续 Sandbox')?.disabled).toBe(false);
  await click('继续 Sandbox');
  expect(document.querySelector('[role="alert"]')?.textContent).toContain('对账');
  expect(document.querySelector('[role="dialog"]')).toBeNull();
  expect((fetch as any).mock.calls.every(([,init]:any)=>init?.method!=="POST")).toBe(true);
});
