// @vitest-environment jsdom
import { act, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import { KnowledgePage } from "./pages/KnowledgePage";
import { SettingsPage } from "./pages/SettingsPage";
import { EvaluationPage } from "./pages/EvaluationPage";
import { EvolutionPage } from "./pages/EvolutionPage";

const versions = [
  { id: "v1.0", name: "Baseline", score: 72, status: "Active", settings: {} },
  { id: "v1.2", name: "Candidate B", score: 88, status: "Recommended", settings: {} },
];
const data = {
  workspace: { name: "测试工作区", environment: "Production" },
  overview: { active_version: "v1.0", kpis: {}, pipeline: [{ label: "Knowledge", value: "1" }, { label: "Evaluation", value: "40" }, { label: "Bad Cases", value: "8" }], distribution: [], latest_optimization: [], recent_runs: [] },
  documents: [{ id: "doc-1", name: "报修流程.pdf", category: "服务", pages: 3, chunks: 2, status: "Indexed", updated_at: "Today 14:32", parser: "PDF text parser", chunk_strategy: "512 tokens / 80 overlap", samples: ["报修请联系物业"] }],
  dataset: [], evaluation: { id: "EVAL-1", config: "baseline", dataset: "golden", questions: 40, status: "Completed", sla: [] },
  badCases: [{ id: "BC-1", question: "空调坏了怎么办？", failure_type: "Retrieval Failure", score: 20, severity: "High", status: "Open", trace: [], evidence: [] }],
  optimization: { id: "OPT-1", timeline: [], diagnosis: { primary: "Retrieval", secondary: "Generation", summary: "test", other: {} }, candidates: [], recommendation: { bad_cases_resolved: 6, unresolved: 2 } },
  versions, readiness: { mode: "live", model: "test-model", status: "Configured (Unverified)", last_probe: null },
};
const preview = { question: "空调", mode: "live", model: "test-model", latency_ms: 321, fallback_reason: null, baseline: { version: "v1.0", answer: "旧基线样例" }, candidate_b: { version: "v1.2", answer: "本次真实回答", sources: ["报修流程"] } };
let root: Root;
let host: HTMLDivElement;
let routes: Record<string, unknown>;
let post: (path: string) => unknown;

beforeEach(() => {
  (globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
  vi.stubGlobal("ResizeObserver", class { observe() {} unobserve() {} disconnect() {} });
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
  routes = Object.fromEntries(Object.entries(data).map(([key, value]) => [`/api/${key === "badCases" ? "bad-cases" : key}`, structuredClone(value)]));
  post = () => { throw new Error("请求失败，请重试"); };
  vi.stubGlobal("fetch", vi.fn(async (url: string, options?: RequestInit) => {
    const path = new URL(url).pathname;
    const value = options?.method === "POST" ? await post(path) : routes[path];
    if (value === undefined) throw new Error(`No fixture: ${path}`);
    return new Response(JSON.stringify(value), { status: 200 });
  }));
});
afterEach(async () => { await act(async () => root.unmount()); host.remove(); vi.unstubAllGlobals(); vi.useRealTimers(); });
async function render(node: ReactNode) { await act(async () => root.render(node)); }
function button(text: string) { const found = [...document.querySelectorAll("button")].find(item => item.textContent?.includes(text)); expect(found, `button: ${text}`).toBeTruthy(); return found!; }
async function click(text: string) { await act(async () => button(text).click()); }
function content() { return document.body.textContent || ""; }

describe("Preview trust and recovery", () => {
  it("waits for explicit submission and identifies live output separately from the seeded baseline", async () => {
    post = () => preview;
    await render(<App />); await click("预览");
    expect(content()).not.toContain("本次真实回答");
    expect(content()).toContain("DeepSeek");
    await click("对比版本");
    expect(content()).toContain("真实回答（Live）");
    expect(content()).toContain("test-model"); expect(content()).toContain("321 ms");
    expect(content()).toContain("基线样例（模拟）");
  });
  it("labels fallback output as mock with its reason, then clears it on request failure and supports retry", async () => {
    post = () => ({ ...preview, mode: "mock", model: null, latency_ms: null, fallback_reason: "Provider 超时", candidate_b: { ...preview.candidate_b, answer: "模拟回答样例" } });
    await render(<App />); await click("预览"); await click("对比版本");
    expect(content()).toContain("模拟回答（Mock）"); expect(content()).toContain("Provider 超时");
    post = () => { throw new Error("网络中断"); };
    await click("对比版本");
    expect(document.querySelector('[role="alert"]')?.textContent).toContain("网络中断");
    expect(content()).not.toContain("模拟回答样例"); expect(button("对比版本").disabled).toBe(false);
    post = () => preview; await click("对比版本"); expect(content()).toContain("本次真实回答");
  });
});

describe("Readiness and action errors", () => {
  it.each([["Configured (Unverified)", "已配置（未验证）", "warning"], ["Ready", "已验证可用", "good"], ["Unavailable", "不可用", "bad"]])("maps %s with accurate severity", async (status, label, tone) => {
    await render(<SettingsPage data={{ ...data, readiness: { ...data.readiness, status } }} />);
    expect([...document.querySelectorAll(`.badge.${tone}`)].some(item => item.textContent === label)).toBe(true);
    expect(content()).toContain("不上传原文件"); expect(content()).toContain("问题与相关知识片段"); expect(content()).toContain("DeepSeek");
  });
  it("clears previous probe success on failure and displays a retryable local error", async () => {
    post = () => ({ ...data.readiness, status: "Ready", last_probe: { status: "passed", latency_ms: 0 } });
    await render(<SettingsPage data={data} />); await click("验证 Provider 连接"); expect(content()).toContain("已验证可用");
    post = () => { throw new Error("探测中断"); }; await click("验证 Provider 连接");
    expect(document.querySelector('[role="alert"]')?.textContent).toContain("探测中断"); expect(content()).not.toContain("已验证可用");
    post = () => ({ ...data.readiness, status: "Unavailable", last_probe: { status: "failed", reason: "鉴权失败" } });
    await click("验证 Provider 连接"); expect(content()).toContain("不可用"); expect(content()).toContain("鉴权失败");
  });
  it("shows an evaluation error and permits another manual attempt", async () => {
    await render(<EvaluationPage data={data} navigate={() => {}} />);
    expect(content()).toContain("问题与相关知识片段");
    await click("运行真实评测"); expect(document.querySelector('[role="alert"]')).not.toBeNull(); expect(button("运行真实评测").disabled).toBe(false);
    post = () => ({ mode: "mock", completed: 40, failed: 0, average_score: null, reason: "未配置 Provider", latency_ms: 0 });
    await click("运行真实评测"); expect(content()).toContain("未配置 Provider"); expect(content()).not.toContain("真实评测：模拟");
  });
  it("labels replay and recovers from start and polling failures", async () => {
    vi.useFakeTimers();
    await render(<EvolutionPage data={data} />); expect(content()).toContain("模拟重放");
    await click("运行模拟重放"); expect(document.querySelector('[role="alert"]')).not.toBeNull();
    post = () => ({ id: "EXP-1", status: "queued", candidates: [], mode: "mock", source: "seeded_replay" });
    await click("运行模拟重放");
    await act(async () => { await vi.advanceTimersByTimeAsync(750); });
    expect(document.querySelector('[role="alert"]')).not.toBeNull(); expect(button("运行模拟重放").disabled).toBe(false);
  });
});

describe("Navigation, details and active version", () => {
  it("shows the server active version even when overview has no active-version field", async () => {
    routes["/api/overview"] = { ...data.overview, active_version: undefined };
    await render(<App />);
    expect(document.querySelector(".production")?.textContent).toContain("v1.0");
  });
  it("opens Bad Cases from overview in evaluation and removes the workspace pseudo button", async () => {
    await render(<App />); expect([...document.querySelectorAll("button")].some(item => item.textContent?.includes("测试工作区"))).toBe(false);
    await click("问题案例"); expect(document.querySelector("h1")?.textContent).toBe("评测报告");
  });
  it("exposes mobile navigation to every page", async () => {
    await render(<App />); await click("菜单");
    const nav = document.querySelector('[aria-label="移动导航"]'); expect(nav).not.toBeNull();
    expect(nav?.querySelectorAll("button")).toHaveLength(6);
    await act(async () => [...nav!.querySelectorAll("button")].find(item => item.textContent === "设置")!.click());
    expect(document.querySelector("h1")?.textContent).toBe("设置");
  });
  it("counts actual documents, opens native detail buttons and gives empty searches feedback", async () => {
    await render(<KnowledgePage data={data} />);
    expect([...document.querySelectorAll(".metric")].find(item => item.textContent?.includes("文档数"))?.querySelector("strong")?.textContent).toBe("1");
    await click("报修流程.pdf"); expect(document.querySelector('[role="dialog"]')).not.toBeNull();
    await act(async () => (document.querySelector('[aria-label="关闭"]') as HTMLButtonElement).click());
    const input = document.querySelector('input[placeholder="搜索文档"]') as HTMLInputElement;
    await act(async () => { Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(input, "missing"); input.dispatchEvent(new Event("input", { bubbles: true })); });
    expect(content()).toContain("未找到匹配文档");
    expect(document.querySelector(".table-scroll table")).not.toBeNull();
  });
  it("opens bad-case details through a native button", async () => {
    await render(<EvaluationPage data={data} navigate={() => {}} />); await click("BC-1"); expect(document.querySelector('[role="dialog"]')?.textContent).toContain("空调坏了怎么办");
  });
  it("reloads authoritative active status after activation and shares it with overview", async () => {
    await render(<App />); await click("版本管理");
    await click("设为演示启用版本"); expect(document.querySelector('[role="alert"]')).not.toBeNull();
    post = () => { routes["/api/versions"] = versions.map(item => ({ ...item, status: item.id === "v1.2" ? "Demo Active" : "Archived" })); routes["/api/overview"] = { ...data.overview, active_version: "v1.2" }; return { id: "v1.2", name: "Candidate B" }; };
    await click("设为演示启用版本");
    expect([...document.querySelectorAll("tbody .badge")].filter(item => item.textContent?.includes("已启用"))).toHaveLength(1);
    await click("概览"); expect(document.querySelector(".production")?.textContent).toContain("v1.2");
  });
});
