// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { KnowledgePage } from "./pages/KnowledgePage";

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
let root: ReturnType<typeof createRoot>;
afterEach(() => { act(() => root?.unmount()); document.body.innerHTML = ""; vi.unstubAllGlobals(); });

it("shows only the two business topic levels and placeholders before a new exam is frozen", async () => {
  const legacy = { coverage: { clusters: [{ label: "旧主题", size: 44, quotas: { positive: 100 } }] } };
  const topics = [{ name: "维修", size: 90, questions: null, clusters: [
    { id: "5-01", name: "5.1.1 部件（占 75.0%）", size: 40, purity: 0.75, questions: null },
    { id: "5-02", name: "5.2 装回", size: 50, purity: 0.5, questions: null },
  ] }];
  const fetcher = vi.fn(async (url: string) => new Response(JSON.stringify(
    url.endsWith("/api/knowledge/topics") ? { has_frozen_exam: false, topics } : { knowledge: legacy }
  )));
  vi.stubGlobal("fetch", fetcher);
  root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<KnowledgePage data={{ documents: [], overview: { knowledge: legacy } }} />));

  const coverage = document.querySelector(".knowledge-coverage")!;
  expect(coverage.textContent).toContain("题卷导入后显示");
  expect(coverage.textContent).not.toMatch(/旧主题|规划题位|Coverage Plan|cluster|slot/);
  expect([...coverage.querySelectorAll("tbody > tr:first-child > td")].map(td => td.textContent)).toEqual(["90", "—", "—", "—"]);
  expect(coverage.querySelector(".ui-kc-bar i")).not.toBeNull();
  const toggle = [...coverage.querySelectorAll("button")].find(button => button.textContent === "维修")!;
  expect(toggle.getAttribute("aria-expanded")).toBe("false");
  await act(async () => toggle.click());
  expect(toggle.getAttribute("aria-expanded")).toBe("true");
  expect([...coverage.querySelectorAll("table table tbody tr")].map(row => [...row.children].map(cell => cell.textContent))).toEqual([
    ["5.1.1 部件（占 75.0%）", "40", "75.0%", "—"],
    ["5.2 装回", "50", "50.0%", "—"],
  ]);
  expect(fetcher.mock.calls.some(([url]) => url.includes("/api/knowledge/clusters/"))).toBe(false);
});
