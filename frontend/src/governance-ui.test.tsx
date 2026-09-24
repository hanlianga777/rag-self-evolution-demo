// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { GovernancePage } from "./pages/GovernancePage";

afterEach(() => { document.body.innerHTML = ""; vi.restoreAllMocks(); });

it("keeps Golden approval disabled until Probe and QC both pass", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ stage: "golden" }), { status: 200 })));
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => { root.render(<GovernancePage data={{ generationRuns: [{ id: "GGEN-test", status: "candidate_generated", question_ids: ["GGC-001"], artifacts: {} }], dataset: [{ id: "GGC-001", legacy_question_type: "v1_mini", question: "测试题", test_category: "positive", review_status: "human_review_pending", probe_status: "probe_pending", stage: "candidate", evidence: [] }] }} />); });

  expect(document.body.textContent).toContain("测试集治理");
  await act(async () => { ([...document.querySelectorAll("button")].find(button => button.textContent === "查看详情") as HTMLButtonElement).click(); });
  const approval = [...document.querySelectorAll("button")].find(button => button.textContent === "批准")!;
  expect((approval as HTMLButtonElement).disabled).toBe(true);
  expect(document.body.textContent).toContain("Probe 未通过");
});

it("enables Golden approval only after both checks pass", async () => {
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => { root.render(<GovernancePage data={{ generationRuns: [{ id: "GGEN-test", status: "candidate_generated", question_ids: ["GGC-033"], artifacts: {} }], dataset: [{ id: "GGC-033", legacy_question_type: "v1_mini", question: "测试题", test_category: "negative", review_status: "human_review_pending", probe_status: "probe_passed", qc_status: "qc_passed", stage: "candidate", evidence: [] }] }} />); });
  await act(async () => { ([...document.querySelectorAll("button")].find(button => button.textContent === "查看详情") as HTMLButtonElement).click(); });
  const approval = [...document.querySelectorAll("button")].find(button => button.textContent === "批准")!;
  expect((approval as HTMLButtonElement).disabled).toBe(false);
});

it("restores a running generation and reads persisted slot progress", async () => {
  const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({ id: "GGEN-live", status: "generating", question_ids: [], artifacts: { hard_validation: { progress: { stage: "generating", slot: "Q03", completed_slots: 2, total_slots: 20 } } } }), { status: 200 }));
  vi.stubGlobal("fetch", fetcher);
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => { root.render(<GovernancePage data={{ generationRuns: [{ id: "GGEN-live", status: "queued", question_ids: [], artifacts: {} }], dataset: [] }} />); });
  expect(fetcher).toHaveBeenCalledWith(expect.stringContaining("/api/governance/generation-runs/GGEN-live"));
  expect(document.body.textContent).toContain("Q03");
  expect(document.body.textContent).toContain("2 / 20");
  expect((([...document.querySelectorAll("button")].find(button => button.textContent?.includes("生成 V1 Mini"))) as HTMLButtonElement).disabled).toBe(true);
  await act(async () => root.unmount());
});

it("shows 20 compact review rows, honest filters, and three full-run exports", async () => {
  const questions = Array.from({ length: 20 }, (_, index) => ({
    id: `GGC-${index + 1}`, slot: `Q${String(index + 1).padStart(2, "0")}`,
    question: `测试问题 ${index + 1}`, test_category: index < 8 ? "positive" : index < 12 ? "ablation" : "negative",
    legacy_question_type: "v1_mini", probe_status: index < 7 ? "needs_revision" : "probe_passed",
    qc_status: index < 7 ? "qc_failed" : index === 7 ? "qc_pending" : "qc_passed", review_status: "human_review_pending", stage: "candidate", evidence: [],
    probe: { score: index < 7 ? 72 : 95, threshold: 90 }, qc: { score: index < 7 ? 72 : 90, threshold: 85 },
  }));
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ questions }), { status: 200 })));
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => { root.render(<GovernancePage data={{ generationRuns: [{ id: "GGEN-20", status: "completed", question_ids: questions.map(row => row.id), artifacts: {} }], dataset: questions }} />); });

  expect(document.querySelectorAll(".review-table tbody tr")).toHaveLength(20);
  expect(document.querySelectorAll(".review-table tbody button")).toHaveLength(20);
  expect(document.body.textContent).toContain("Probe 未通过 7");
  expect(document.body.textContent).toContain("QC 未通过 7");
  expect(document.body.textContent).toContain("仍有 8 道阻塞题");
  expect(document.body.textContent).toContain("待 QC 1");
  expect(document.querySelectorAll(".export-menu a")).toHaveLength(3);
  await act(async () => { ([...document.querySelectorAll(".review-filters button")].find(button => button.textContent?.includes("Probe 未通过")) as HTMLButtonElement).click(); });
  expect(document.querySelectorAll(".review-table tbody tr")).toHaveLength(7);
  expect(document.querySelectorAll(".export-menu a")).toHaveLength(3);
  await act(async () => { ([...document.querySelectorAll(".review-table tbody button")][0] as HTMLButtonElement).click(); });
  expect(document.body.textContent).toContain("Probe 72 < 90");
  await act(async () => root.unmount());
});

it("shows persisted quality rerun progress and resumes polling after refresh", async () => {
  const questions = Array.from({ length: 20 }, (_, index) => ({ id: `V1-${index}`, slot: `Q${String(index + 1).padStart(2, "0")}`, question: "测试题", test_category: "positive", legacy_question_type: "v1_mini", probe_status: "probe_pending", qc_status: "qc_pending", qc: { score: 73 }, stage: "candidate", evidence: [] }));
  const run = { id: "GGEN-quality", status: "completed", question_ids: questions.map(row => row.id), artifacts: { hard_validation: { quality_rerun: { status: "running", stage: "probe", slot: "Q05", completed: 4, probe_passed: 3, probe_failed: 1, qc_passed: 2, qc_failed: 1, qc_skipped: 1, slots: { Q01: { qc: "skipped" } }, started_at: new Date().toISOString() } } } };
  vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string) => Promise.resolve(new Response(JSON.stringify(url.includes("export") ? { questions } : run), { status: 200 }))));
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => { root.render(<GovernancePage data={{ generationRuns: [run], dataset: questions }} />); });
  expect(document.body.textContent).toContain("4 / 20");
  expect(document.body.textContent).toContain("QC 通过 2，失败 1，跳过 1");
  expect((([...(document.querySelectorAll("button"))].find(button => button.textContent === "重新运行 Probe / QC")) as HTMLButtonElement).disabled).toBe(true);
  expect(fetch).toHaveBeenCalledWith(expect.stringContaining("/api/governance/generation-runs/GGEN-quality"));
  await act(async () => { ([...document.querySelectorAll("button")].find(button => button.textContent === "查看详情") as HTMLButtonElement).click(); });
  expect(document.body.textContent).toContain("本次重跑因 Probe 未通过，已跳过 QC");
  await act(async () => root.unmount());
});

it("shows only Revision Draft while a paired preview is active", async () => {
  const questions = Array.from({ length: 20 }, (_, index) => ({ id: `V1-${index + 1}`, slot: `Q${String(index + 1).padStart(2, "0")}`, question: `原题 ${index + 1}`, reference_answer: index < 12 ? "正确操作" : null, test_category: index < 8 ? "positive" : index < 12 ? "ablation" : "negative", legacy_question_type: "v1_mini", probe_status: "probe_passed", qc_status: "qc_passed", review_status: index === 0 || index === 8 ? "needs_revision" : "approved", stage: index === 0 || index === 8 ? "candidate" : "golden", evidence: index === 0 || index === 8 ? [{ source_chunk_ids: ["C1"] }] : [], evidence_details: index === 0 || index === 8 ? [{ chunks: [{ chunk_id: "C1", document_id: "DOC-001" }] }] : [] }));
  const revision = { id: "REV-test", status: "preview_ready", stage: "preview_ready", question_ids: ["V1-1", "V1-9"], before: { "V1-1": { ...questions[0], raw: { coverage_slot: "Q01" } }, "V1-9": { ...questions[8], raw: { coverage_slot: "Q09" } } }, drafts: { "V1-1": { ...questions[0], question: "新题 1" }, "V1-9": { ...questions[8], question: "新题 9" } }, progress: { current: 2, total: 2 } };
  vi.stubGlobal("fetch", vi.fn((url: string) => Promise.resolve(new Response(JSON.stringify(url.includes("/api/governance/revisions") ? [revision] : url.includes("/api/documents/") ? { chunks: [{ chunk_id: "C1", section_path: "操作", page_start: 2, chunk_text: "正确操作" }] } : { questions }), { status: 200 }))));
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<GovernancePage data={{ generationRuns: [{ id: "GGEN-20", status: "completed", question_ids: questions.map(item => item.id), artifacts: {} }], dataset: questions }} />));
  await act(async () => document.querySelector<HTMLButtonElement>(".review-table tbody button")!.click());
  expect(document.body.textContent).toContain("Revision Draft");
  expect(document.body.textContent).toContain("新题 1");
  expect(document.body.textContent).not.toContain("发起 Candidate 修订");
  expect([...document.querySelectorAll("button")].some(button => button.textContent === "生成修订草案")).toBe(false);
  expect(document.body.textContent).toContain("确认应用并运行 Probe / QC");
  await act(async () => root.unmount());
});

it("starts Q09 alone by default and includes Q01 only when explicitly checked", async () => {
  const questions = Array.from({ length: 20 }, (_, index) => ({ id: `V1-${index + 1}`, slot: `Q${String(index + 1).padStart(2, "0")}`, question: `原题 ${index + 1}`, reference_answer: "正确操作", test_category: index < 8 ? "positive" : "ablation", legacy_question_type: "v1_mini", probe_status: "probe_passed", qc_status: "qc_passed", review_status: index === 0 || index === 8 ? "needs_revision" : "approved", stage: index === 0 || index === 8 ? "candidate" : "golden", evidence: [{ source_chunk_ids: ["C1"] }], evidence_details: [{ chunks: [{ chunk_id: "C1", document_id: "DOC-001" }] }] }));
  questions[8].evidence = [{ source_chunk_ids: ["C2"] }];
  questions[8].evidence_details = [{ chunks: [{ chunk_id: "C2", document_id: "DOC-001" }] }];
  const requests: Array<{ url: string; init?: RequestInit }> = [];
  vi.stubGlobal("fetch", vi.fn((url: string, init?: RequestInit) => {
    requests.push({ url, init });
    const body = url.endsWith("/revision") ? { id: "REV-new" } : url.includes("/api/governance/revisions/REV-new") ? { id: "REV-new", status: "preview_ready", question_ids: ["V1-9"], drafts: {} } : url.endsWith("/api/governance/revisions") ? [] : url.includes("/api/documents/") ? { chunks: [{ chunk_id: "C1", document_id: "DOC-001", section_path: "操作" }, { chunk_id: "C2", document_id: "DOC-001", section_path: "其他操作" }] } : url.includes("export") ? { questions } : [];
    return Promise.resolve(new Response(JSON.stringify(body), { status: 200 }));
  }));
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<GovernancePage data={{ generationRuns: [{ id: "GGEN-20", status: "completed", question_ids: questions.map(item => item.id), artifacts: {} }], dataset: questions }} />));
  await act(async () => (document.querySelectorAll<HTMLButtonElement>(".review-table tbody button")[8]).click());
  expect(document.body.textContent).toContain("关联 Positive：Q01");
  const pair = document.querySelector<HTMLInputElement>(".revision-pair input[type='checkbox']")!;
  expect(pair.checked).toBe(false);
  expect(document.querySelectorAll(".revision-form .revision-question")).toHaveLength(0);
  await act(async () => pair.click());
  expect(pair.checked).toBe(true);
  expect(document.querySelectorAll(".revision-form fieldset")).toHaveLength(2);
  await act(async () => pair.click());
  expect(pair.checked).toBe(false);
  expect(document.querySelectorAll(".revision-form fieldset")).toHaveLength(1);
  const reason = document.querySelector<HTMLInputElement>(".revision-form input[placeholder]")!;
  await act(async () => { Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(reason, "独立修 Q09"); reason.dispatchEvent(new Event("input", { bubbles: true })); });
  await act(async () => ([...document.querySelectorAll("button")].find(button => button.textContent === "生成修订草案") as HTMLButtonElement).click());
  const started = requests.find(item => item.url.endsWith("/api/governance/questions/V1-9/revision"));
  expect(started).toBeTruthy();
  expect(JSON.parse(started!.init!.body as string).paired).toBe(false);
  expect(Object.keys(JSON.parse(started!.init!.body as string).changes)).toEqual(["V1-9"]);
  await act(async () => root.unmount());
});

it("lets a paired preview regenerate only Q09 and discard without applying", async () => {
  vi.spyOn(window, "confirm").mockReturnValue(true);
  const questions = Array.from({ length: 20 }, (_, index) => ({ id: `V1-${index + 1}`, slot: `Q${String(index + 1).padStart(2, "0")}`, question: `原题 ${index + 1}`, reference_answer: "正确操作", test_category: index < 8 ? "positive" : "ablation", legacy_question_type: "v1_mini", probe_status: "probe_passed", qc_status: "qc_passed", review_status: index === 0 || index === 8 ? "needs_revision" : "approved", stage: index === 0 || index === 8 ? "candidate" : "golden", evidence: [{ source_chunk_ids: ["C1"] }], evidence_details: [{ chunks: [{ chunk_id: "C1", document_id: "DOC-001" }] }] }));
  const revision: any = { id: "REV-pair", status: "preview_ready", stage: "preview_ready", question_ids: ["V1-1", "V1-9"], before: { "V1-1": { ...questions[0], raw: { coverage_slot: "Q01" } }, "V1-9": { ...questions[8], raw: { coverage_slot: "Q09" } } }, drafts: { "V1-1": { ...questions[0], question: "新题 1" }, "V1-9": { ...questions[8], question: "新题 9" } }, new_hash: { "V1-1": "hash-one", "V1-9": "hash-nine" }, progress: { current: 2, total: 2 } };
  const requests: Array<{ url: string; init?: RequestInit }> = [];
  vi.stubGlobal("fetch", vi.fn((url: string, init?: RequestInit) => {
    requests.push({ url, init });
    if (url.endsWith("/edit-draft")) { revision.apply_blocked = true; revision.error = "Q09: Chunk 不存在于当前索引"; }
    const body = url.includes("/api/governance/revisions/REV-pair") ? revision : url.endsWith("/api/governance/revisions") ? [revision] : url.includes("/api/documents/") ? { chunks: [{ chunk_id: "C1", document_id: "DOC-001", section_path: "操作", page_start: 2, chunk_text: "正确操作" }] } : url.includes("export") ? { questions } : url.endsWith("/api/dataset") ? questions : url.endsWith("/api/governance/generation-runs") ? [{ id: "GGEN-20", status: "completed", question_ids: questions.map(item => item.id), artifacts: {} }] : [];
    return Promise.resolve(new Response(JSON.stringify(body), { status: 200 }));
  }));
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<GovernancePage data={{ generationRuns: [{ id: "GGEN-20", status: "completed", question_ids: questions.map(item => item.id), artifacts: {} }], dataset: questions }} />));
  await act(async () => document.querySelector<HTMLButtonElement>(".review-table tbody button")!.click());
  expect(document.body.textContent).toContain("编辑当前草案");
  expect(document.body.textContent).toContain("重新生成当前题");
  expect(document.body.textContent).toContain("放弃草案");
  const target = document.querySelector<HTMLSelectElement>("[aria-label='选择要调整的题目']")!;
  await act(async () => { target.value = "V1-9"; target.dispatchEvent(new Event("change", { bubbles: true })); });
  await act(async () => ([...document.querySelectorAll("button")].find(button => button.textContent === "编辑当前草案") as HTMLButtonElement).click());
  expect(document.querySelector<HTMLTextAreaElement>(".revision-status textarea")?.value).toBe("新题 9");
  expect((document.querySelector<HTMLInputElement>(".revision-status .revision-chunks input[type='checkbox']")?.checked)).toBe(true);
  await act(async () => ([...document.querySelectorAll("button")].find(button => button.textContent === "保存并校验草案") as HTMLButtonElement).click());
  const editRequest = requests.find(item => item.url.endsWith("/edit-draft"));
  expect(Object.keys(JSON.parse(editRequest!.init!.body as string).changes)).toEqual(["V1-9"]);
  expect((([...document.querySelectorAll("button")].find(button => button.textContent === "确认应用并运行 Probe / QC")) as HTMLButtonElement).disabled).toBe(true);
  await act(async () => ([...document.querySelectorAll("button")].find(button => button.textContent === "重新生成当前题") as HTMLButtonElement).click());
  const regeneration = requests.find(item => item.url.endsWith("/regenerate-draft"));
  expect(regeneration).toBeTruthy();
  expect(JSON.parse(regeneration!.init!.body as string)).toEqual({ question_id: "V1-9", expected_hash: "hash-nine" });
  await act(async () => ([...document.querySelectorAll("button")].find(button => button.textContent === "放弃草案") as HTMLButtonElement).click());
  expect(requests.some(item => item.url.endsWith("/discard"))).toBe(true);
  expect(requests.some(item => item.url.endsWith("/apply"))).toBe(false);
  await act(async () => root.unmount());
});
