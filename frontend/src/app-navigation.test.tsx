// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import App from "./App";

let root: ReturnType<typeof createRoot>;
afterEach(() => { root?.unmount(); document.body.innerHTML = ""; vi.restoreAllMocks(); });

it("opens the overview with the V1.0.1 lifecycle navigation", async () => {
  const data: Record<string, unknown> = {
    "/api/workspace": { active_version: "baseline-v1" }, "/api/overview": { dataset: { approved: 0, pending_review: 40 }, monitoring: { pending_triggers: 0 } },
    "/api/documents": [], "/api/dataset": [], "/api/evaluation": { status: "not_run" }, "/api/bad-cases": [],
    "/api/optimization": { status: "not_run" }, "/api/versions": [], "/api/readiness": {}, "/api/monitoring": { events: [], triggers: [] },
  };
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => new Response(JSON.stringify(data[new URL(String(input)).pathname]), { status: 200 })));
  root = createRoot(document.body.appendChild(document.createElement("div")));

  await act(async () => { root.render(<App />); await Promise.resolve(); await Promise.resolve(); });

  expect(document.body.textContent).toContain("RAG 自进化概览");
  expect(document.body.textContent).toContain("测试集治理");
  expect(document.body.textContent).toContain("问答验证");
  expect(document.body.textContent).not.toContain("问答试验");
});
