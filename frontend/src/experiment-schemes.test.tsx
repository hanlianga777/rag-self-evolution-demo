// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { ExperimentPage } from "./pages/ExperimentPage";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
afterEach(() => { document.body.innerHTML = ""; sessionStorage.clear(); vi.unstubAllGlobals(); });

it("compares previous and current production after release and reads saved Bad Case evidence", async () => {
  const fetcher = vi.fn(async (input: RequestInfo | URL) => new Response(JSON.stringify({ cases: [{ question_id: "Q-1", model_answer: "已保存答案" }] }), { status: 200 }));
  vi.stubGlobal("fetch", fetcher);
  const data = {
    evaluation: { id: "EVAL-1" },
    badCases: [{ id: "BAD-1", run_id: "EVAL-1", question_id: "Q-1", result: { question: "固定问题" } }],
    versions: [
      { id: "production-1", status: "active", provenance: "published", previous_version_id: "baseline-v1", evaluation_run_id: "EVAL-C" },
      { id: "baseline-v1", status: "superseded", provenance: "bootstrap" },
    ],
  };
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<ExperimentPage data={data} onOpenCitation={() => {}} />));
  expect(document.querySelector('[role="combobox"][aria-label="方案 A"]')?.textContent).toContain("Baseline · 初始配置");
  expect(document.querySelector('[role="combobox"][aria-label="方案 B"]')?.textContent).toContain("当前 Production");
  await act(async () => (document.querySelector('[role="combobox"][aria-label="选择真实 Bad Case"]') as HTMLButtonElement).click());
  await act(async () => (document.querySelector('[role="option"][data-value="BAD-1"]') as HTMLDivElement).click());
  await act(async () => (document.querySelector(".fixed-case-control button.secondary") as HTMLButtonElement).click());
  expect(document.body.textContent).toContain("已保存答案");
  expect((document.querySelector(".history-evaluation") as HTMLDetailsElement).open).toBe(false);
  expect(document.querySelector(".history-evaluation")?.textContent).toContain("查看本题在已保存实验中的评分和证据");
  expect(fetcher.mock.calls.map(([url]) => String(url))).toEqual(expect.arrayContaining([expect.stringContaining("/api/evaluations/EVAL-1"), expect.stringContaining("/api/evaluations/EVAL-C")]));
  await act(async () => root.unmount());
});

it("defaults to Baseline and a qualified Candidate before release", async () => {
  const data = { evaluation: { id: "EVAL-1" }, optimization: { candidates: [{ id: "C-1", reasoning: { candidate_label: "C" }, result: { qualification: { qualified: true } } }] }, versions: [{ id: "baseline-v1", status: "active", provenance: "bootstrap" }] };
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<ExperimentPage data={data} onOpenCitation={() => {}} />));
  expect(document.querySelector('[role="combobox"][aria-label="方案 A"]')?.textContent).toContain("Baseline");
  expect(document.querySelector('[role="combobox"][aria-label="方案 B"]')?.textContent).toContain("Candidate C");
  await act(async () => root.unmount());
});

it("shows parameter differences before readable live answers", async () => {
  vi.stubGlobal("fetch", vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
    const request = JSON.parse(String(init?.body || "{}"));
    return new Response(JSON.stringify({ answer: "## 结论\n\n请 **停机**。\n\n- 关闭电源", version: request.scheme_id, config: { prompt_strategy: request.scheme_id === "baseline" ? "Grounded" : "Abstention", top_k: 4 }, latency_ms: 120, evidence: [] }), { status: 200 });
  }));
  const data = { evaluation: { id: "EVAL-1" }, optimization: { candidates: [{ id: "C-1", reasoning: { candidate_label: "C" }, result: { qualification: { qualified: true } } }] }, versions: [{ id: "baseline-v1", status: "active", provenance: "bootstrap" }] };
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<ExperimentPage data={data} onOpenCitation={() => {}} />));
  const textarea = document.querySelector("textarea") as HTMLTextAreaElement;
  const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")!.set!;
  await act(async () => { setter.call(textarea, "机器人如何操作？"); textarea.dispatchEvent(new Event("input", { bubbles: true })); });
  await act(async () => { (document.querySelector(".query-action button") as HTMLButtonElement).click(); await Promise.resolve(); await Promise.resolve(); });
  const diff = [...document.querySelectorAll(".section-head h2")].find(node => node.textContent === "方案参数差异")!;
  const answers = document.querySelector(".experiment-results")!;
  expect(diff.compareDocumentPosition(answers) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(document.querySelector(".answer-markdown strong")?.textContent).toBe("停机");
  expect(document.querySelector(".answer-markdown")?.textContent).not.toContain("**");
  await act(async () => root.unmount());
});
