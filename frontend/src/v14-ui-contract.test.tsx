// @vitest-environment jsdom
import { act, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { ExperimentPage } from "./pages/ExperimentPage";
import { Drawer } from "./components/Dialog";
import { VersionsPage } from "./pages/VersionsPage";
import { EvolutionPage } from "./pages/EvolutionPage";
import { ExecutionMetrics } from "./components/PipelineFields";
import { RetrievalEvidence } from "./components/RetrievalEvidence";
import { getJson, loadAppData } from "./api";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
let root: ReturnType<typeof createRoot>;
afterEach(() => { if (root) act(() => root.unmount()); document.body.innerHTML = ""; sessionStorage.clear(); vi.unstubAllGlobals(); });
const render = async (node: ReactNode) => { root = createRoot(document.body.appendChild(document.createElement("div"))); await act(async () => root.render(node)); };
const identity = (baseline: string, experiment?: string) => ({ current_baseline_id: baseline, current_experiment_id: experiment, current_golden_id: "GD-fixture", current_corpus_fingerprint: { D: "fixture" } });
const data = (baseline = "B0") => ({ workspace: identity(baseline), evaluation: { id: baseline }, versions: [{ id: "P0", status: "active", provenance: "published", config: { top_k: 6 } }] });
const fill = async (question: string) => act(async () => { const input = document.querySelector("textarea")!; Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")!.set!.call(input, question); input.dispatchEvent(new Event("input", { bubbles: true })); });

it("ID-08 ignores an old same-question comparison after Baseline changes", async () => {
  const replies: ((reply: Response) => void)[] = [];
  vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(resolve => replies.push(resolve))));
  await render(<ExperimentPage data={data()} onOpenCitation={() => {}} />);
  await fill("同一个问题");
  await act(async () => document.querySelector<HTMLButtonElement>(".query-action button")!.click());
  expect(replies).toHaveLength(2);
  await act(async () => root.render(<ExperimentPage data={data("B1")} onOpenCitation={() => {}} />));
  await act(async () => replies.forEach(reply => reply(new Response(JSON.stringify({ answer: "旧 B0 回答", version: "B0" })))));
  expect(document.body.textContent).not.toContain("旧 B0 回答");
  expect(document.querySelectorAll(".experiment-answer-card .running")).toHaveLength(0);
});

it("ID-08 clears Candidate Drawer and rejects an old candidate report after identity changes", async () => {
  let resolveReport!: (reply: Response) => void;
  vi.stubGlobal("fetch", vi.fn((url: string) => url.includes("/evaluations/") ? new Promise<Response>(resolve => { resolveReport = resolve; }) : Promise.resolve(new Response(JSON.stringify({ search_space: {} })))));
  const old = { workspace: identity("B0", "E0"), evaluation: { id: "B0" }, optimization: { id: "E0", candidates: [{ id: "A0", config: {}, reasoning: { candidate_label: "A" }, result: { evaluation_run_id: "R0" } }] } };
  await render(<EvolutionPage data={old} />);
  await act(async () => [...document.querySelectorAll("button")].find(button => button.textContent === "A / B / C / D")!.click());
  await act(async () => [...document.querySelectorAll("button")].find(button => button.textContent?.includes("查看方案与完整报告"))!.click());
  expect(document.querySelector('[role="dialog"]')).not.toBeNull();
  await act(async () => root.render(<EvolutionPage data={{ workspace: identity("B1"), evaluation: { id: "B1" }, optimization: { status: "not_run" } }} />));
  await act(async () => resolveReport(new Response(JSON.stringify({ cases: [{ question: "旧身份案例" }] }))));
  expect(document.querySelector('[role="dialog"]')).toBeNull();
  expect(document.body.textContent).not.toContain("旧身份案例");
});

it("CT-04 displays collected zero cost and unknown cost reason separately", async () => {
  await render(<><ExecutionMetrics metrics={{ ttft_ms: null, cost_estimation: { status: "estimated", amount: 0, currency: "USD" } }} /><ExecutionMetrics metrics={{ cost_estimation: { status: "unavailable", amount: null, reason: "billing_period_ambiguous" } }} /></>);
  expect(document.body.textContent).toContain("0 USD");
  expect(document.body.textContent).toContain("计费时段或节假日日历未确认");
  expect(document.body.textContent).toContain("未采集真实首输出时间");
});

it("VP-07/09 keeps Candidate AnyHit separate from Final AllHit and missing observations", async () => {
  await render(<RetrievalEvidence metrics={{ retrieval_trace: { candidates: [{ chunk_id: "C1", content: "真实合成材料" }], final: [] }, evidence_coverage: { candidate_recall: { any_hit: true, all_hit: false }, final_context: { any_hit: false, all_hit: false } } }} />);
  expect(document.body.textContent).toContain("Any Hit：是 · All Hit：否");
  expect(document.body.textContent).toContain("真实合成材料");
  expect(document.body.textContent).toContain("实际采集 0 条");
  await act(async () => root.render(<RetrievalEvidence metrics={{ retrieval_trace: { candidates: null, final: [] } }} />));
  expect(document.body.textContent).toContain("历史未采集，不能用另一层列表替代");
});

it("surfaces structured retrieval failures without object coercion", async () => {
  await expect(getJson("/api/preview", vi.fn(async () => new Response(JSON.stringify({ detail: { code: "RETRIEVAL_EXECUTION_FAILED", message: "本地检索执行失败，请检查索引" } }), { status: 503 })))).rejects.toThrow("本地检索执行失败，请检查索引");
});

it("ID-08 refuses incoherent parallel app identities after one bounded retry", async () => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => new Response(JSON.stringify({ ...identity(url.includes("optimization") ? "B0" : "B1") }))));
  await expect(loadAppData()).rejects.toThrow("工作区身份正在变化");
  expect(fetch).toHaveBeenCalledTimes(20);
});


it("RL-03/05 uses centered confirmation and keeps failed release visible without fake success", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ detail: "提交时资格已失效" }), { status: 409 })));
  const candidate = { id: "A-fixture", status: "evaluated", reasoning: { candidate_label: "A" }, release_state: { sandbox: true, qualified: true, recommended: true, round_complete: true } };
  await render(<VersionsPage data={{ versions: [{ id: "P0", status: "active" }], optimization: { candidates: [candidate] } }} />);
  await act(async () => document.querySelector<HTMLButtonElement>(".release-actions button")!.click());
  expect(document.querySelector(".confirm-dialog")?.textContent).toContain("Gate 3");
  await act(async () => [...document.querySelectorAll<HTMLButtonElement>(".confirm-dialog button")].find(button => button.textContent === "确认")!.click());
  expect(document.querySelector(".confirm-dialog")?.textContent).toContain("提交时资格已失效");
  expect(document.querySelector(".release-actions")?.textContent).toBe("确认发布");
  expect(document.querySelector(".version-records")?.textContent || "").not.toContain("P1");
  expect(fetch).toHaveBeenCalledTimes(1);
});


it("preserves unsaved Drawer edits until explicit discard confirmation", async () => {
  const change = vi.fn();
  await render(<Drawer open guardEdits title="Fixture 编辑" onOpenChange={change}><input aria-label="未保存内容" /></Drawer>);
  const input = document.querySelector<HTMLInputElement>("input")!;
  await act(async () => { Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(input, "未保存修改"); input.dispatchEvent(new Event("input", { bubbles: true })); });
  await act(async () => document.querySelector<HTMLButtonElement>(".drawer-head button")!.click());
  expect(change).not.toHaveBeenCalled();
  expect(document.querySelector(".confirm-dialog")?.textContent).toContain("放弃未保存修改");
  await act(async () => document.querySelector<HTMLButtonElement>(".confirm-dialog button.primary")!.click());
  expect(change).toHaveBeenCalledWith(false);
});
