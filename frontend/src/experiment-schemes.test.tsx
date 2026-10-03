// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { ExperimentPage } from "./pages/ExperimentPage";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
afterEach(() => { document.body.innerHTML = ""; sessionStorage.clear(); vi.unstubAllGlobals(); });
const data = {
  workspace: { current_baseline_id: "EVAL-1" },
  evaluation: { id: "EVAL-1", config: { prompt_strategy: "Grounded" } },
  badCases: [{ id: "BAD-1", run_id: "EVAL-1", question_id: "Q-1", result: { question: "固定问题" } }],
  versions: [{ id: "production-1", status: "active", provenance: "published", snapshot: { candidate_id: "C-1" }, config: { prompt_strategy: "Abstention" } }],
};
async function mount(value: any = data) {
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<ExperimentPage data={value} onOpenCitation={() => {}} />));
  return root;
}
async function chooseCase() {
  await act(async () => (document.querySelector('[role="combobox"][aria-label="选择真实 Bad Case"]') as HTMLButtonElement).click());
  await act(async () => (document.querySelector('[role="option"][data-value="BAD-1"]') as HTMLDivElement).click());
}
async function run() { await act(async () => { (document.querySelector(".query-action button") as HTMLButtonElement).click(); await Promise.resolve(); }); }

it("fixes Baseline and Production and selecting a Bad Case only fills the question", async () => {
  const fetcher = vi.fn(); vi.stubGlobal("fetch", fetcher);
  const root = await mount(); await chooseCase();
  expect((document.querySelector("textarea") as HTMLTextAreaElement).value).toBe("固定问题");
  expect(document.querySelector('[aria-label="方案 A"]')).toBeNull();
  expect(document.querySelector('[aria-label="方案 B"]')).toBeNull();
  expect(document.querySelector(".history-evaluation")).toBeNull();
  expect(fetcher).not.toHaveBeenCalled();
  await act(async () => root.unmount());
});

it("blocks before real Production exists, even with a qualified Candidate", async () => {
  const value = { ...data, optimization: { candidates: [{ id: "C-1", reasoning: { candidate_label: "C" }, result: { qualification: { qualified: true } } }] }, versions: [{ id: "baseline-v1", status: "active", provenance: "bootstrap", snapshot: { candidate_id: "" }, config: {} }] };
  const root = await mount(value); await chooseCase();
  expect((document.querySelector(".query-action button") as HTMLButtonElement).disabled).toBe(true);
  expect(document.body.textContent).toContain("尚无已发布 Production");
  await act(async () => root.unmount());
});

it("captures the same question, shows config inside each answer, and keeps one-side success", async () => {
  const fetcher = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
    const request = JSON.parse(String(init?.body || "{}"));
    return request.scheme_id === "baseline" ? new Response(JSON.stringify({ detail: "模拟失败" }), { status: 503 }) : new Response(JSON.stringify({ answer: "## 结论\n\n请 **停机**。", version: request.scheme_id, config: { prompt_strategy: "Abstention" }, latency_ms: 120, input_tokens: 0, output_tokens: 3, evidence: [] }), { status: 200 });
  }); vi.stubGlobal("fetch", fetcher);
  const root = await mount(); await chooseCase(); await run();
  expect(fetcher.mock.calls.map(([, init]) => JSON.parse(String(init?.body)).question)).toEqual(["固定问题", "固定问题"]);
  expect(document.querySelectorAll(".answer-config")).toHaveLength(2);
  expect(document.querySelector(".answer-markdown strong")?.textContent).toBe("停机");
  expect(document.body.textContent).toContain("模拟失败");
  expect(document.querySelectorAll(".answer-metrics-footer")[1].textContent).toContain("Input Tokens0");
  expect(document.querySelectorAll(".answer-metrics-footer")[1].textContent).not.toContain("历史费用未采集");
  await act(async () => root.unmount());
});

it("clears results when active Production changes and ignores late responses", async () => {
  const finishes: ((value: Response) => void)[] = [];
  vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(resolve => { finishes.push(resolve); })));
  const root = await mount(); await chooseCase(); await run();
  const next = { ...data, versions: [{ ...data.versions[0], id: "production-2" }] };
  await act(async () => root.render(<ExperimentPage data={next} onOpenCitation={() => {}} />));
  await act(async () => finishes.forEach(finish => finish(new Response(JSON.stringify({ answer: "过期回答", version: "production-1", latency_ms: 1 }), { status: 200 }))));
  expect(document.body.textContent).not.toContain("过期回答");
  expect(document.body.textContent).not.toContain("等待 ·");
  expect(sessionStorage.getItem("rag-qa-compare") || "").not.toContain('"history"');
  await act(async () => root.unmount());
});
