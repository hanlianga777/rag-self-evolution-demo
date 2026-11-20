// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { KnowledgePage } from "./pages/KnowledgePage";

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
let root: ReturnType<typeof createRoot>;
afterEach(() => { act(() => root?.unmount()); document.body.innerHTML = ""; vi.unstubAllGlobals(); });

const legacy = { coverage: { clusters: [{ label: "旧主题", size: 44, quotas: { positive: 100 } }] } };
const repairSections = [{ number: "5.6.2", title: "更换轴 2 电机" }];
const repair = {
  name: "维修", model: "IRB 1300（手册）", size: 90, quota: 7, questions: null, sections: repairSections,
  clusters: [{ id: "06-01", name: "电机更换", size: 90, homogeneity: 0.75, quota: 7, questions: null,
    sections: repairSections }],
};
const safety = {
  name: "安全", model: "IRB 1300（手册）", size: 12, quota: 1, questions: null, clusters: [],
  sections: [{ number: "1.6.3", title: "制动闸测试" }],
};

async function renderCoverage(topics: unknown[], frozen: boolean) {
  const fetcher = vi.fn(async (url: string) => new Response(JSON.stringify(
    url.endsWith("/api/knowledge/topics") ? { has_frozen_exam: frozen, topics } : { knowledge: legacy }
  )));
  vi.stubGlobal("fetch", fetcher);
  root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<KnowledgePage data={{ documents: [], overview: { knowledge: legacy } }} />));
  expect(fetcher.mock.calls.some(([url]) => url.includes("/api/knowledge/clusters/"))).toBe(false);
  return document.querySelector(".knowledge-coverage")!;
}

const cells = (row: Element) => [...row.children].filter(cell => cell.tagName === "TD").map(cell => cell.textContent);

it("shows source models, targets and section directories before a new exam is frozen", async () => {
  const coverage = await renderCoverage([repair, safety], false);
  expect(coverage.textContent).toContain("题卷冻结后显示");
  expect(coverage.textContent).not.toMatch(/旧主题|规划题位|Coverage Plan|cluster|slot/);
  expect(cells(coverage.querySelector(".business-topic-row")!)).toEqual(["90", "7", "—", "—", "—", ""]);
  expect(coverage.querySelector(".ui-kc-bar i")).not.toBeNull();
  const toggle = [...coverage.querySelectorAll("button")].find(button => button.textContent === "维修")!;
  expect(toggle.getAttribute("aria-expanded")).toBe("false");
  await act(async () => toggle.click());
  expect(toggle.getAttribute("aria-expanded")).toBe("true");
  expect(coverage.querySelector(".business-topic-detail")!.textContent).toContain("电机更换");
  expect(coverage.querySelector(".business-topic-detail li")!.textContent).toBe("5.6.2 更换轴 2 电机");
  await act(async () => [...coverage.querySelectorAll("button")].find(button => button.textContent === "安全")!.click());
  expect(coverage.querySelector(".business-topic-detail li")!.textContent).toBe("1.6.3 制动闸测试");
});

it("shows actual counts, positive shortfalls and the outside-knowledge negative row", async () => {
  const coverage = await renderCoverage([
    { ...repair, questions: { positive: 5, ablation: 3, negative: 2 } },
    { ...safety, questions: { positive: 1, ablation: 0, negative: 0 } },
    { name: "知识库外（负向）", model: null, size: null, quota: null, clusters: [], sections: [],
      questions: { positive: 0, ablation: 0, negative: 4 } },
  ], true);
  const rows = [...coverage.querySelectorAll(".business-topics > tbody > tr")];
  expect(rows.map(cells)).toEqual([["90", "7", "5", "3", "2", "2"], ["12", "1", "1", "0", "0", ""], ["—", "—", "0", "0", "4", ""]]);
  expect(rows[2].textContent).toContain("知识库外（负向）");
  expect(rows[2].querySelector("button")).toBeNull();
});
