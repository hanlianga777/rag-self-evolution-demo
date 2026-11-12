// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { OverviewPage } from "./pages/OverviewPage";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
afterEach(() => { vi.unstubAllGlobals(); document.body.innerHTML = ""; });

it("renders project results and the new architecture tabs without writes", async () => {
  const fetch = vi.fn(); vi.stubGlobal("fetch", fetch);
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<OverviewPage data={{}} navigate={() => {}} />));
  expect(document.querySelector(".ui-vc")).toBeNull();
  expect(document.querySelector(".page-content")?.firstElementChild?.classList.contains("ui-ov")).toBe(true);
  await act(async () => [...document.querySelectorAll("button")].find(button => button.textContent === "业务架构")!.click());
  expect(document.querySelector(".ui-problems")?.textContent).toContain("智能客服上线以后");
  expect(document.querySelectorAll(".ui-arch-row")).toHaveLength(3);
  expect(document.querySelectorAll(".ui-arch-node")).toHaveLength(18);
  expect([...document.querySelectorAll(".ui-arch-gate")].map(node => node.textContent)).toEqual(["Gate 1人工审核", "Gate 2人工审核", "Gate 3人工审批"]);
  expect(document.querySelector(".architecture-figure")).toBeNull();
  expect(document.body.textContent).not.toContain("已保存参考图");
  expect(document.querySelector('input[type="file"]')).toBeNull();
  await act(async () => [...document.querySelectorAll("button")].find(button => button.textContent === "技术架构")!.click());
  expect(document.querySelectorAll(".ui-tech-layer")).toHaveLength(5);
  expect(document.body.textContent).toContain("RAG Pipeline");
  expect([...document.querySelectorAll(".ui-tech-tag.tunable")].map(node => node.textContent)).toEqual(["Query Rewrite", "Multi-Query", "HyDE", "Candidate K", "Hybrid Search", "Embedding Retrieval 权重", "Rerank", "Top-K", "MinScore", "上下文容量", "Prompt 策略", "Thinking 档位"]);
  expect(document.querySelector(".ui-tech")?.textContent).toContain("deepseek-flash");
  expect(document.body.textContent).not.toMatch(/平价|断点续跑/);
  expect(fetch).not.toHaveBeenCalled();
  const ids = [...document.querySelectorAll('svg [id]')].map(node => node.id);
  expect(new Set(ids).size).toBe(ids.length);
  await act(async () => root.unmount());
});
