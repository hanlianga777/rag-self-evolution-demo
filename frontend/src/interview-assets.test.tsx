// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { KnowledgePage } from "./pages/KnowledgePage";
import { SettingsPage } from "./pages/SettingsPage";
import { GovernancePage } from "./pages/GovernancePage";
import { BusinessImportPanel } from "./pages/BusinessImportPanel";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
afterEach(() => { document.body.innerHTML = ""; vi.restoreAllMocks(); vi.unstubAllGlobals(); });

it("uses persisted corpus totals and actual index dimensions in six asset cards and three strategy cards", async () => {
  const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({ index: { embedding_model: "BAAI/bge-small-zh-v1.5", vector_index: "FAISS IndexFlatIP", dimension: 384, indexed_count: 6 } }), { status: 200 }));
  vi.stubGlobal("fetch", fetcher);
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<KnowledgePage data={{ documents: [{ id: "DOC-1", name: "说明.pdf", pages: 9, chunks: 7, parser: "PyMuPDF", chunk_strategy: "页级/段落 fallback", status: "Indexed" }] }} />));
  expect(document.querySelector(".light-stepper")).toBeNull();
  expect(document.querySelector(".metrics-grid")).toBeNull();
  expect(document.querySelectorAll(".knowledge-strategy-card")).toHaveLength(3);
  expect(document.querySelector(".asset-summary")?.textContent).toContain("384d");
  expect(document.querySelector(".knowledge-notice")?.textContent).toContain("Legacy");
  expect(document.querySelector(".asset-summary")?.textContent).toContain("9 Pages");
  expect(document.querySelector(".asset-summary")?.textContent).toContain("Index6Legacy");
  expect([...document.querySelectorAll("thead th")].map(item => item.textContent)).toEqual(["文档名", "页数", "Chunk 数", "解析状态", "索引状态", "操作"]);
  expect(fetcher.mock.calls.every(([, init]) => !init?.method || init.method === "GET")).toBe(true);
  await act(async () => root.unmount());
});

it("hides missing index measurements instead of deriving them from chunks", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ index: { embedding_model: "BAAI/bge-small-zh-v1.5", vector_index: "FAISS IndexFlatIP", dimension: null, indexed_count: null } }), { status: 200 })));
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<KnowledgePage data={{ documents: [{ id: "DOC-1", name: "说明.pdf", pages: 9, chunks: 7, parser: "PyMuPDF", status: "Indexed" }] }} />));
  expect(document.querySelector(".asset-summary")?.textContent).toContain("IndexUnavailable");
  expect(document.querySelector(".knowledge-strategies")?.textContent).not.toContain("512");
  expect(document.querySelector(".knowledge-strategies")?.textContent).not.toContain("未采集");
  await act(async () => root.unmount());
});

it("groups pipeline configuration by purpose and marks parameters by their contract keys", async () => {
  const pipeline = { config: { query_rewrite: false, top_k: 6, prompt_strategy: "Grounded" }, index: { embedding_model: "BGE", vector_index: "FAISS", dimension: 384 }, search_space: { top_k: { type: "integer", allowed: [4, 6] }, prompt_strategy: { type: "string", allowed: ["Grounded"] } } };
  const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify(pipeline), { status: 200 }));
  vi.stubGlobal("fetch", fetcher);
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<SettingsPage data={{ documents: [{ parser: "PyMuPDF", chunk_strategy: "Section-aware" }], versions: [{ status: "active", snapshot: { generation_model: "generation-model" } }], readiness: { status: "ready", model: "provider-model" }, evaluation: { judge: { model: "judge-model", temperature: 0.9, execution_snapshot: { generation_model: "generation-model", temperature: 0.2 } } } }} />));
  expect(document.querySelector(".light-stepper")).toBeNull();
  expect([...document.querySelectorAll(".pipeline-group h2")].map(item => item.textContent)).toEqual(["知识处理配置", "检索策略", "生成策略", "评测配置"]);
  expect(document.querySelector('[data-parameter="query_rewrite"] .badge')?.textContent).toBe("Frozen");
  expect(document.querySelector('[data-parameter="top_k"] .badge')?.textContent).toBe("Agent 可调");
  expect(document.querySelector('[data-parameter="generation_model"]')?.textContent).toContain("generation-model");
  expect(document.querySelector('[data-parameter="temperature"]')?.textContent).toContain("0.2");
  expect(document.querySelector('[data-parameter="temperature"]')?.textContent).not.toContain("0.9");
  expect(document.querySelector(".config-groups")?.textContent).not.toMatch(/未采集|未实现|未配置/);
  expect(fetcher.mock.calls).toHaveLength(1);
  await act(async () => root.unmount());
});

it("keeps current frozen Golden separate from the latest work Run and hides an empty risk area", async () => {
  const row = { id: "new-Q01", slot: "Q01", question: "待审核的新题", test_category: "positive", stage: "candidate", probe_status: "probe_passed", qc_status: "qc_passed", review_status: "human_review_pending", evidence: [] };
  const workRun = { id: "GGEN-new", status: "completed", profile: { expected_count: 1 }, question_ids: [row.id], artifacts: {} };
  const snapshots = [{ id: "GD-other", status: "approved", snapshot: { questions: [{ id: "other", test_category: "positive" }], question_ids: ["other"] } }, { id: "GD-current", status: "approved", snapshot: { questions: [{ id: "old-1", test_category: "positive" }, { id: "old-2", test_category: "ablation" }, { id: "old-3", test_category: "negative" }], question_ids: ["old-1", "old-2", "old-3"] } }];
  const fetcher = vi.fn((url: string, _init?: RequestInit) => Promise.resolve(new Response(JSON.stringify(url.includes("/export") ? { questions: [row] } : []), { status: 200 })));
  vi.stubGlobal("fetch", fetcher);
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<GovernancePage data={{ workspace: { current_golden_id: "GD-current" }, generationRuns: [workRun], snapshots, dataset: [row], documents: [] }} />));
  const summary = document.querySelector(".current-golden-summary")!;
  expect(summary.textContent).toContain("3 题");
  expect(summary.textContent).toContain("1 Positive");
  expect(summary.textContent).toContain("1 Ablation");
  expect(summary.textContent).toContain("1 Negative");
  expect(summary.textContent).toContain("Frozen");
  expect(summary.textContent).toContain("Legacy");
  expect(document.querySelector(".review-table tbody")?.textContent).toContain("待审核的新题");
  expect(document.querySelector(".stage-stepper")).toBeNull();
  expect(document.querySelector(".exception-summary")).toBeNull();
  expect(document.body.textContent).not.toContain("当前未记录质量异常");
  expect(fetcher.mock.calls.every(([, init]) => !init?.method || init.method === "GET")).toBe(true);
  await act(async () => root.unmount());
});

it("keeps candidate filters, search and explicit actions in a single toolbar", async () => {
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  const rows = [{ id: "pool-1", question: "刷盘检查", stage: "candidate", test_category: "positive", review_status: "human_review_pending", raw: { source: "business_import" } }, { id: "pool-2", question: "电池维护", stage: "candidate", test_category: "negative", review_status: "human_review_pending", raw: { source: "business_import" } }];
  const fetcher = vi.fn(); vi.stubGlobal("fetch", fetcher);
  await act(async () => root.render(<BusinessImportPanel items={rows} onCreated={async () => {}} />));
  const toolbar = document.querySelector(".candidate-pool-toolbar")!;
  expect(toolbar.querySelectorAll('[role="combobox"]')).toHaveLength(4);
  expect(toolbar.querySelector('input[type="search"]')).not.toBeNull();
  expect(toolbar.textContent).toContain("导入业务用例");
  expect(toolbar.textContent).toContain("创建新的 Golden 测试集");
  const search = toolbar.querySelector<HTMLInputElement>('input[type="search"]')!;
  await act(async () => { Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(search, "刷盘"); search.dispatchEvent(new Event("input", { bubbles: true })); });
  expect(document.querySelectorAll("tbody tr")).toHaveLength(1);
  expect(fetcher).not.toHaveBeenCalled();
  await act(async () => root.unmount());
});

it("joins legacy Frozen question IDs to persisted categories without replacing frozen content", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify([]))));
  const frozen = { id: "GD-current", snapshot: { question_ids: ["Q1", "Q2", "Q3"], questions: [{ id: "Q1", question: "冻结原文" }, { id: "Q2" }, { id: "Q3" }] } };
  const before = JSON.stringify(frozen);
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<GovernancePage data={{ workspace: { current_golden_id: frozen.id }, snapshots: [frozen], generationRuns: [], dataset: ["positive", "ablation", "negative"].map((test_category, i) => ({ id: `Q${i + 1}`, test_category })) }} />));
  expect(document.querySelector(".current-golden-summary")?.textContent).toContain("1 Positive · 1 Ablation · 1 Negative");
  expect(JSON.stringify(frozen)).toBe(before);
  await act(async () => root.unmount());
});
