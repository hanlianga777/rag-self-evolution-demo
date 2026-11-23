// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import App from "./App";

let root: ReturnType<typeof createRoot>;
afterEach(() => { root?.unmount(); document.body.innerHTML = ""; location.hash = ""; vi.restoreAllMocks(); });

it("opens the overview with the V1.3 lifecycle navigation", async () => {
  const data: Record<string, unknown> = {
    "/api/workspace": { active_version: "baseline-v1" }, "/api/overview": { dataset: { approved: 0, pending_review: 40 }, monitoring: { pending_triggers: 0 } },
    "/api/documents": [], "/api/dataset": [], "/api/evaluation": { status: "not_run" }, "/api/bad-cases": [],
    "/api/optimization": { status: "not_run" }, "/api/versions": [], "/api/readiness": {}, "/api/monitoring": { events: [], triggers: [] },
  };
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => new Response(JSON.stringify(data[new URL(String(input)).pathname]), { status: 200 })));
  root = createRoot(document.body.appendChild(document.createElement("div")));

  await act(async () => { root.render(<App />); await Promise.resolve(); await Promise.resolve(); });

  expect(document.body.textContent).toContain("RAG 自进化概览");
  expect(document.body.textContent).toContain("黄金测试集");
  expect(document.body.textContent).toContain("问答验证");
  const desktop = document.querySelector('nav[aria-label="主导航"]');
  expect(desktop?.querySelector('[href="#evaluation"]')?.getAttribute("aria-description")).toBe("基准评测");
  await act(async () => document.querySelector<HTMLButtonElement>(".mobile-menu")!.click());
  const mobile = document.querySelector('nav[aria-label="移动导航"]');
  expect([...mobile!.querySelectorAll("a")].map(link => link.getAttribute("href")))
    .toEqual([...desktop!.querySelectorAll("a")].map(link => link.getAttribute("href")));
  for (const [route, meaning] of Object.entries({ overview: "检索增强生成", settings: "处理流程", evaluation: "基准评测", evolution: "优化智能体" })) {
    expect(mobile?.querySelector(`[href="#${route}"] small`)?.textContent).toBe(meaning);
    expect(desktop?.querySelector(`[href="#${route}"]`)?.getAttribute("aria-description")).toBe(meaning);
  }
  expect([...document.querySelectorAll('nav[aria-label="主导航"] a')].map(item => item.textContent)).toEqual(["RAG 自进化概览", "知识库", "黄金测试集", "Pipeline 配置", "Baseline", "Agent 工作台", "发布", "问答验证"]);
});

it("opens a deep link and keeps navigation in browser history", async () => {
  location.hash = "#knowledge";
  const data: Record<string, unknown> = {
    "/api/workspace": { active_version: "baseline-v1" }, "/api/overview": {}, "/api/documents": [], "/api/dataset": [],
    "/api/evaluation": { status: "not_run" }, "/api/bad-cases": [], "/api/optimization": { status: "not_run" },
    "/api/versions": [], "/api/readiness": {}, "/api/monitoring": { events: [], triggers: [] },
  };
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => new Response(JSON.stringify(data[new URL(String(input)).pathname]), { status: 200 })));
  root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => { root.render(<App />); await Promise.resolve(); await Promise.resolve(); });
  expect(document.querySelector("h1")?.textContent).toBe("知识库");
  await act(async () => { (document.querySelector('nav[aria-label="主导航"] a[href="#evaluation"]') as HTMLAnchorElement).click(); });
  expect(location.hash).toBe("#evaluation");
  expect(document.querySelector("h1")?.textContent).toContain("Baseline");
  await act(async () => { location.hash = "#knowledge"; window.dispatchEvent(new HashChangeEvent("hashchange")); });
  expect(document.querySelector("h1")?.textContent).toBe("知识库");
});
