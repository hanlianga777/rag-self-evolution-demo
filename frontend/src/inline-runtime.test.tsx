// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { AssistantPage } from "./pages/AssistantPage";
import { ExperimentPage } from "./pages/ExperimentPage";
import { GovernancePage } from "./pages/GovernancePage";
import { OperationProvider } from "./operation";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
afterEach(() => { document.body.innerHTML = ""; localStorage.clear(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

it("shows assistant waiting inline and renders a complete synchronous answer at once", async () => {
  let respond!: (value: Response) => void;
  vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(resolve => { respond = resolve; })));
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<OperationProvider restore={false}><AssistantPage badCases={[]} onOpenBadCase={() => {}} onOpenCitation={() => {}} onOpenDocument={() => {}} /></OperationProvider>));
  await act(async () => document.querySelector<HTMLButtonElement>(".empty-chat button")!.click());
  expect(document.querySelector(".thinking-message")?.textContent).toContain("DeepSeek 思考中");
  expect(document.querySelector(".operation-console")).toBeNull();
  await act(async () => respond(new Response(JSON.stringify({ baseline: { answer: "完整回答内容", sources: [], evidence: [] }, model: "DeepSeek", mode: "live" }), { status: 200 })));
  expect(document.querySelector(".thinking-message")).toBeNull();
  expect(document.body.textContent).toContain("完整回答内容");
  expect(document.querySelector(".typing-cursor")).toBeNull();
  expect(document.body.textContent).toContain("生成耗时");
  await act(async () => root.unmount());
});

it("shows Before result without waiting for After and keeps a one-sided failure local", async () => {
  let baseline!: (value: Response) => void;
  let candidate!: (value: Response) => void;
  vi.stubGlobal("fetch", vi.fn((url: string) => new Promise<Response>(resolve => { if (url.endsWith("/baseline")) baseline = resolve; else candidate = resolve; })));
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<OperationProvider restore={false}><ExperimentPage onOpenCitation={() => {}} /></OperationProvider>));
  await act(async () => { const textarea = document.querySelector("textarea")!; Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")!.set!.call(textarea, "测试"); textarea.dispatchEvent(new Event("input", { bubbles: true })); });
  await act(async () => document.querySelector<HTMLButtonElement>(".experiment-query button")!.click());
  expect(document.querySelectorAll(".experiment-answer-card .running")).toHaveLength(2);
  expect(document.querySelector(".operation-console")).toBeNull();
  await act(async () => baseline(new Response(JSON.stringify({ answer: "生产答案", version: "v1", latency_ms: 100, evidence: [] }), { status: 200 })));
  expect(document.querySelectorAll(".experiment-answer-card")[0].textContent).toContain("生产答案");
  expect(document.querySelectorAll(".experiment-answer-card")[1].textContent).not.toContain("生产答案");
  await act(async () => candidate(new Response(JSON.stringify({ detail: "候选不可用" }), { status: 503 })));
  expect(document.querySelectorAll(".experiment-answer-card")[0].textContent).not.toContain("预览失败");
  expect(document.querySelectorAll(".experiment-answer-card")[1].textContent).toContain("候选不可用");
  await act(async () => root.unmount());
});

it("restores Generation counters inline without creating partial candidates", async () => {
  const run = { id: "GGEN-live", status: "qc", created_at: new Date(Date.now() - 2000).toISOString(), question_ids: [], artifacts: { hard_validation: { progress: { stage: "qc", completed_slots: 20, total_slots: 20, probe_completed: 20, qc_completed: 13, qc_skipped: 7 } } } };
  vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(new Response(JSON.stringify(run), { status: 200 }))));
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<OperationProvider restore={false}><GovernancePage data={{ generationRuns: [run], dataset: [] }} /></OperationProvider>));
  expect(document.querySelector(".run-summary")?.textContent).toContain("QC 跳过 7");
  expect(document.querySelector(".run-summary")?.textContent).toContain("运行耗时");
  expect(document.querySelectorAll(".review-table tbody button")).toHaveLength(0);
  expect(document.querySelector(".operation-console")).toBeNull();
  await act(async () => root.unmount());
});
