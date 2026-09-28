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

  expect(document.body.textContent).toContain("RAG Self-Evolution Lifecycle");
  expect(document.body.textContent).toContain("Golden Dataset");
  expect(document.body.textContent).toContain("QA Playground");
  expect([...document.querySelectorAll('nav[aria-label="主导航"] a')].map(item => item.textContent)).toEqual(["Overview", "Knowledge", "Pipeline", "Golden Dataset", "Baseline", "Tuning", "Release", "QA Playground"]);
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
  expect(document.querySelector("h1")?.textContent).toBe("Knowledge Base");
  await act(async () => { (document.querySelector('nav[aria-label="主导航"] a[href="#evaluation"]') as HTMLAnchorElement).click(); });
  expect(location.hash).toBe("#evaluation");
  expect(document.querySelector("h1")?.textContent).toContain("Baseline");
  await act(async () => { location.hash = "#knowledge"; window.dispatchEvent(new HashChangeEvent("hashchange")); });
  expect(document.querySelector("h1")?.textContent).toBe("Knowledge Base");
});
