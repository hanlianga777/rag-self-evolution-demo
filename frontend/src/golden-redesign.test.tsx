// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { GovernancePage } from "./pages/GovernancePage";
import { invalidateGolden } from "./goldenCache";
import { goldenFixture } from "./golden-test-fixture";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
afterEach(() => { invalidateGolden(); document.body.innerHTML = ""; sessionStorage.clear(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
const row = { id: "frozen-04", slot: "Q04", question: "如何长期存放？", test_category: "positive", stage: "golden", reference_answer: "1. 室内存放\n2. 电池完全充电", probe_status: "probe_passed", qc_status: "qc_passed", qualification_status: "human_approved", raw: { source: "reviewed_csv_machine_checks" }, probe: { score: 100, reason: "Evidence exists but the production pipeline did not recall it", probe_details: { classification: "RETRIEVAL_INCOHERENT", question_validity: "valid", risk: "P1", evidence_coverage: { final_context: { all_hit: false, coverage: 0.5 } } } }, qc: { score: 95, reason: "参考答案由原文支持" }, evidence_details: [{ chunks: [{ chunk_id: "SECRET-CHUNK", document_name: "设备手册.pdf", page_start: 85, chunk_text: "只在室内存放设备" }] }] };
const run = { id: "run-frozen", status: "completed", profile: { name: "medium", expected_count: 1, positive_count: 1, ablation_count: 0, negative_count: 0 }, question_ids: [row.id], artifacts: {}, human_gate: { status: "ready" } };
const snapshot = { id: "GD-frozen", status: "approved", created_at: "2026-11-01T15:19:40Z", snapshot: { generation_run_id: run.id, question_ids: [row.id] } };
const frozenData = { generationRuns: [run], snapshots: [snapshot], dataset: [row], workspace: { current_golden_id: snapshot.id, generation_profiles: { medium: run.profile } } };
function stubFrozen() { const fetcher = vi.fn(async (url: string, init?: RequestInit) => { if (init?.method && init.method !== "GET") throw new Error("禁止写接口"); return new Response(JSON.stringify(url.includes("/candidates?") || /\/questions\/[^/]+$/.test(url) ? goldenFixture(url, [row]) : [])); }); vi.stubGlobal("fetch", fetcher); return fetcher; }

it("shows a cached frozen dataset after a minute while metadata revalidation is pending", async () => {
  let hold = false;
  const pending: Array<() => void> = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    if (hold) await new Promise<void>(resolve => pending.push(resolve));
    return new Response(JSON.stringify(url.includes('generation-runs?') ? [run] : url.includes('snapshots?') ? [snapshot] : goldenFixture(url, [row])));
  }));
  const container = document.body.appendChild(document.createElement('div'));
  let root = createRoot(container);
  const data = { workspace: frozenData.workspace };
  await act(async () => root.render(<GovernancePage data={data} />));
  expect(document.querySelector('.review-table')?.textContent).toContain(row.question);
  await act(async () => root.unmount());
  vi.spyOn(Date, 'now').mockReturnValue(Date.now() + 60000);
  hold = true;
  root = createRoot(container);
  try {
    await act(async () => root.render(<GovernancePage data={data} />));
    expect(document.querySelector('.golden-initial-skeleton')).toBeNull();
    expect(document.querySelector('.review-table')?.textContent).toContain(row.question);
    expect(document.querySelector('.ui-gp')?.textContent).toContain('已冻结');
  } finally {
    await act(async () => root.unmount());
    await act(async () => pending.forEach(resolve => resolve()));
  }
});

it("shows a skeleton until the initial run and frozen snapshot resolve", async () => {
  const pending: Array<() => void> = [];
  vi.stubGlobal("fetch", vi.fn((url: string) => new Promise(resolve => pending.push(() => resolve(new Response(JSON.stringify(url.includes("generation-runs?") ? [run] : url.includes("snapshots?") ? [snapshot] : goldenFixture(url, [row]))))))));
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<GovernancePage data={{ workspace: frozenData.workspace }} />));
  expect(document.querySelector('[aria-label="正在读取 Golden Dataset"]')).not.toBeNull();
  expect(document.body.textContent).not.toContain("未生成");
  expect(document.body.textContent).not.toContain("20 题位");
  expect(document.querySelector('[aria-label="测试集 Profile"]')).toBeNull();
  await act(async () => { pending.splice(0).forEach(resolve => resolve()); });
  await act(async () => { pending.splice(0).forEach(resolve => resolve()); });
  expect(document.querySelector(".golden-metrics")).toBeNull();
  expect(document.querySelector('.review-filters button[aria-pressed="true"]')?.textContent).toBe("全部 1");
  await act(async () => root.unmount());
});

it("hides frozen editing controls and renders numbered answers and source evidence", async () => {
  const fetcher = stubFrozen();
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<GovernancePage data={frozenData} />));
  expect(document.querySelector(".ui-gp")?.textContent).toContain("已冻结 · 11-01");
  expect(document.querySelector(".review-filters")?.textContent).not.toContain("需要人工关注 0");
  expect(document.querySelectorAll(".review-table th")).toHaveLength(6);
  expect(document.querySelector(".review-table")?.textContent).toContain("95");
  expect(document.querySelector(".review-table")?.textContent).not.toContain("人工审核");
  await act(async () => document.querySelector<HTMLElement>(".review-table tbody tr")!.click());
  expect(document.querySelectorAll(".golden-answer-list li")).toHaveLength(2);
  expect(document.querySelector(".frozen-question-details")?.textContent).toContain("设备手册 · p85");
  expect(document.querySelector(".golden-probe-result")?.textContent).toContain("题目与证据校验通过");
  expect(document.querySelector(".golden-probe-result")?.textContent).toContain("P1 召回观察");
  for (const label of ["运行 Probe", "运行 QC"]) {
    const button = [...document.querySelectorAll("button")].find(button => button.textContent === label)!;
    expect(button).toBeDefined();
    expect(button.disabled).toBe(false);
  }
  expect(document.querySelector('button[title="已冻结，修改需新建题卷版本"]')).toBeNull();
  expect(document.body.textContent).toContain("题卷已冻结，只读");
  expect(document.querySelector('.candidate-workspace [aria-label="更多操作"]')).toBeNull();
  expect(fetcher.mock.calls.every(([, init]) => !init?.method || init.method === "GET")).toBe(true);
  await act(async () => root.unmount());
});

it("keeps the frozen pool read only even when an older selection is stashed", async () => {
  sessionStorage.setItem('golden-pool-selection:undefined', JSON.stringify([row]));
  const fetcher = stubFrozen();
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<GovernancePage data={frozenData} />));
  await act(async () => [...document.querySelectorAll<HTMLButtonElement>(".tabs button")].find(button => button.textContent === "候选池")!.click());
  expect(document.body.textContent).not.toContain("这些题已全部进入冻结题卷");
  expect(document.querySelector(".candidate-pool-table")?.textContent).toContain("人工审核");
  expect(document.body.textContent).not.toContain("创建Golden");
  expect(document.querySelector('input[type="file"]')).toBeNull();
  expect(fetcher.mock.calls.every(([, init]) => !init?.method || init.method === "GET")).toBe(true);
  await act(async () => root.unmount());
});

it("preserves checkbox Space handling while pool row keys open details", async () => {
  const { BusinessImportPanel } = await import("./pages/BusinessImportPanel");
  const onDetail = vi.fn();
  vi.stubGlobal("fetch", vi.fn(async (url: string) => new Response(JSON.stringify(url.includes("/candidates?") ? goldenFixture(url, [row]) : { valid: true, validations: {} }))));
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<BusinessImportPanel items={[row]} profiles={{ mini: { positive_count: 1, ablation_count: 0, negative_count: 0 } }} onCreated={async () => {}} onDetail={onDetail} />));
  await act(async () => [...document.querySelectorAll<HTMLButtonElement>("button")].find(button => button.textContent === "创建Golden")!.click());
  const checkbox = document.querySelector<HTMLInputElement>('input[type="checkbox"]')!;
  const key = new KeyboardEvent("keydown", { key: " ", bubbles: true, cancelable: true });
  await act(async () => { checkbox.focus(); checkbox.dispatchEvent(key); });
  expect(key.defaultPrevented).toBe(false);
  expect(onDetail).not.toHaveBeenCalled();
  await act(async () => checkbox.click());
  expect(checkbox.checked).toBe(true);
  expect(onDetail).not.toHaveBeenCalled();
  await act(async () => checkbox.closest("tr")!.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true })));
  expect(onDetail).toHaveBeenCalledWith(row);
  await act(async () => root.unmount());
});

it("closes a frozen question and opens the next question without rendering missing details", async () => {
  const next = { ...row, id: "frozen-21", slot: "Q21", question: "证据缺失时怎样回答？", test_category: "ablation" };
  const rows = [row, next], ids = rows.map(item => item.id);
  const currentRun = { ...run, profile: { ...run.profile, expected_count: 2, ablation_count: 1 }, question_ids: ids };
  const currentSnapshot = { ...snapshot, snapshot: { ...snapshot.snapshot, question_ids: ids } };
  vi.stubGlobal("fetch", vi.fn(async (url: string) => new Response(JSON.stringify(url.includes("/candidates?") || /\/questions\/[^/]+$/.test(url) ? goldenFixture(url, rows) : []))));
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<GovernancePage data={{ ...frozenData, generationRuns: [currentRun], snapshots: [currentSnapshot], dataset: rows }} />));
  await act(async () => document.querySelector<HTMLElement>('.review-table tr[aria-label^="Q04"]')!.click());
  expect(document.querySelector(".frozen-question-details")?.textContent).toContain(row.question);
  await act(async () => document.querySelector<HTMLButtonElement>('.candidate-workspace [aria-label="关闭"]')!.click());
  expect(document.querySelector(".candidate-workspace")).toBeNull();
  expect(document.querySelectorAll(".review-table tbody tr")).toHaveLength(2);
  await act(async () => document.querySelector<HTMLElement>('.review-table tr[aria-label^="Q21"]')!.click());
  expect(document.querySelector(".frozen-question-details")?.textContent).toContain(next.question);
  await act(async () => document.querySelector<HTMLButtonElement>('.candidate-workspace [aria-label="关闭"]')!.click());
  expect(document.querySelector(".candidate-workspace")).toBeNull();
  await act(async () => root.unmount());
});
