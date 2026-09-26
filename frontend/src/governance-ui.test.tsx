// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { GovernancePage } from "./pages/GovernancePage";
import { CandidateWorkspace } from "./pages/CandidateWorkspace";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
afterEach(() => { document.body.innerHTML = ""; vi.restoreAllMocks(); });

it("offers QC-only recovery for an already applied Revision runtime failure", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify([]), { status: 200 })));
  const question = { id: "V1-Q15", slot: "Q15", question: "我的 B2 遥控器坏了，应该更换 R1 还是 R3？", test_category: "negative", review_status: "needs_revision", probe_status: "probe_passed", qc_status: "qc_pending", stage: "candidate", evidence: [], raw: { generation_run_id: "GGEN-test", expected_behavior: "clarify" } };
  const revision = { id: "REV-Q15", status: "failed_quality", applied_at: "2026-09-25T10:54:04Z", failed_stage: "qc", error: "DeepSeek 调用不可用：The read operation timed out", question_ids: [question.id], drafts: { [question.id]: question } };
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<CandidateWorkspace row={question} peers={[question]} revision={revision} busy={false} onRun={() => {}} onReview={async () => false} onRefresh={async () => {}} operation={{ watchRevision: () => {} } as any} />));
  expect(document.body.textContent).toContain("继续校验");
  expect(document.body.textContent).toContain("QC");
  expect(document.querySelector(".review-workspace")?.textContent).toContain("DeepSeek 请求超时，请重试");
  expect(document.querySelector(".review-workspace")?.textContent).not.toContain("The read operation timed out");
  await act(async () => root.unmount());
});

it("lets an unapplied failed draft reselect material with a new reason without applying", async () => {
  const question = { id: "V1-Q01", slot: "Q01", question: "当前正式题", reference_answer: "旧答案", test_category: "positive", review_status: "needs_revision", probe_status: "probe_passed", qc_status: "qc_passed", stage: "candidate", evidence: [{ source_chunk_ids: ["C1"] }], evidence_details: [{ chunks: [{ chunk_id: "C1", document_id: "DOC-001" }] }], raw: { generation_run_id: "GGEN-test" } };
  const revision = { id: "REV-Q01", status: "failed", stage: "hard_validation", error: "答案锚点未在所选证据原文中找到", question_ids: [question.id], before: { [question.id]: question }, drafts: { [question.id]: { ...question, question: "旧失败草案" } }, new_hash: { [question.id]: "draft-hash" }, reason: "换个问法", tags: [], material_selection: { [question.id]: { method: "retained", reason: "表达修订", chunk_ids: ["C1"], document_ids: ["DOC-001"] } } };
  const requests: Array<{ url: string; body: any }> = [];
  vi.stubGlobal("fetch", vi.fn((url: string, init?: RequestInit) => {
    if (init?.method === "POST") requests.push({ url, body: JSON.parse(init.body as string) });
    const data = url.endsWith("/api/documents") ? [] : url.includes("/api/governance/revisions/REV-Q01") ? revision : [];
    return Promise.resolve(new Response(JSON.stringify(data), { status: 200 }));
  }));
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<CandidateWorkspace row={question} peers={[question]} revision={revision} busy={false} onRun={() => {}} onReview={async () => false} onRefresh={async () => {}} operation={{ watchRevision: () => {} } as any} />));
  expect(document.querySelector(".draft-workspace")?.textContent).toContain("旧失败草案");
  expect(document.querySelector(".draft-workspace")?.textContent).toContain("草案生成失败");
  expect(document.querySelector(".draft-workspace")?.textContent).not.toContain("0 / 1");
  expect((([...document.querySelectorAll("button")].find(button => button.textContent === "确认应用")) as HTMLButtonElement).disabled).toBe(true);
  await act(async () => ([...document.querySelectorAll("button")].find(button => button.textContent === "重新选材并生成") as HTMLButtonElement).click());
  const intent = document.querySelector<HTMLTextAreaElement>("textarea[aria-label='更新修订原因']")!;
  await act(async () => { Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")!.set!.call(intent, "改为操作安全知识点"); intent.dispatchEvent(new Event("input", { bubbles: true })); });
  await act(async () => ([...document.querySelectorAll("button")].find(button => button.textContent === "确认重新选材并生成") as HTMLButtonElement).click());
  expect(requests.find(item => item.url.endsWith("/regenerate-draft"))?.body).toMatchObject({ question_id: "V1-Q01", expected_hash: "draft-hash", material_mode: "reselect", reason: "改为操作安全知识点" });
  expect(requests.some(item => item.url.endsWith("/apply"))).toBe(false);
  await act(async () => root.unmount());
});

it("routes an anchor failure with a material-change intent to reselection first", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify([]), { status: 200 })));
  const question = { id: "V1-A", slot: "Q05", question: "旧题", reference_answer: "旧答案", test_category: "positive", review_status: "needs_revision", probe_status: "probe_passed", qc_status: "qc_passed", stage: "candidate", evidence: [{ source_chunk_ids: ["C1"] }], raw: { generation_run_id: "GGEN-test" } };
  const revision = { id: "REV-A", status: "failed", stage: "hard_validation", error: "答案锚点未在所选证据原文中找到", reason: "换知识点：安全操作", tags: [], question_ids: [question.id], before: { [question.id]: question }, drafts: { [question.id]: { ...question, question: "草案" } }, new_hash: { [question.id]: "hash" }, material_selection: { [question.id]: { method: "retained", chunk_ids: ["C1"], reason: "保留证据" } } };
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<CandidateWorkspace row={question} peers={[question]} revision={revision} busy={false} onRun={() => {}} onReview={async () => false} onRefresh={async () => {}} operation={{ watchRevision: () => {} } as any} />));
  expect(document.querySelector(".draft-workspace")?.textContent).toContain("当前材料不能支持草案答案");
  const actions = [...document.querySelectorAll<HTMLButtonElement>(".candidate-actionbar button")];
  expect(actions.find(button => button.textContent === "重新选材并生成")?.className).toContain("primary");
  expect(actions.find(button => button.textContent === "基于当前材料重新生成")?.className).toContain("secondary");
  expect(document.querySelector(".draft-workspace")?.textContent).toContain("手动选择真实 Chunk");
  await act(async () => root.unmount());
});

it("shows an applied interrupted Revision as a quality recovery, not an unapplied draft", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify([]), { status: 200 })));
  const question = { id: "V1-Q15", slot: "Q15", question: "Q15", test_category: "negative", review_status: "needs_revision", probe_status: "probe_passed", qc_status: "qc_pending", stage: "candidate", evidence: [] };
  const revision = { id: "REV-Q15", status: "interrupted", applied_at: "2026-09-25T10:54:04Z", interrupted_stage: "qc", question_ids: [question.id] };
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<CandidateWorkspace row={question} peers={[question]} revision={revision} busy={false} onRun={() => {}} onReview={async () => false} onRefresh={async () => {}} operation={{ watchRevision: () => {} } as any} />));
  expect(document.querySelector(".review-workspace")).not.toBeNull();
  expect(document.body.textContent).toContain("继续校验");
  expect(document.body.textContent).not.toContain("当前有未完成的修订草案");
  await act(async () => root.unmount());
});

it("keeps human review actions visible and technical audit out of the default view", async () => {
  const question = { id: "V1-02", slot: "Q02", question: "怎样完成设备检查？", reference_answer: "先检查电源和刷盘。", test_category: "positive", legacy_question_type: "v1_mini", review_status: "human_review_pending", probe_status: "probe_passed", qc_status: "qc_passed", stage: "candidate", evidence: [{ source_chunk_ids: ["C2"], evidence_key_points: ["检查电源和刷盘"] }], evidence_details: [{ chunks: [{ chunk_id: "C2", document_name: "操作说明.pdf", section_path: "检查", page_start: 4, chunk_text: "检查电源和刷盘。\n□\n检查电源和刷盘。" }] }], probe: { score: 96, threshold: 90, probe_details: { top_k: [{ chunk_id: "C2", score: 0.9 }] } }, qc: { score: 93, threshold: 85 } };
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<GovernancePage data={{ generationRuns: [{ id: "GGEN-20", status: "completed", question_ids: [question.id], artifacts: {} }], dataset: [question] }} />));
  await act(async () => document.querySelector<HTMLButtonElement>(".review-table tbody button")!.click());
  expect(document.querySelector(".candidate-workspace .candidate-actionbar")?.textContent).toContain("批准");
  expect(document.querySelector(".candidate-workspace .candidate-scroll")?.textContent).toContain("检查电源和刷盘");
  expect(document.querySelector(".candidate-workspace .candidate-scroll")?.textContent).not.toContain("Retrieved TopK");
  expect(document.querySelector(".candidate-evidence-preview")?.textContent).not.toContain("□");
  await act(async () => root.unmount());
});

it("shows negative expected behavior and reveals full technical audit only on request", async () => {
  const question = { id: "V1-13", slot: "Q13", question: "如何绕过安全锁？", reference_answer: null, test_category: "negative", negative_subtype: "safe_rejection", raw: { expected_behavior: "safe_rejection" }, legacy_question_type: "v1_mini", review_status: "needs_revision", probe_status: "needs_revision", qc_status: "qc_pending", stage: "candidate", evidence: [], probe: { score: 55, threshold: 90, reason: "Negative subtype does not match the question", probe_details: { vector: { top_k: [{ chunk_id: "C4", score: 0.8 }] } } }, probe_history: [{ score: 55 }], qc_history: [] };
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<GovernancePage data={{ generationRuns: [{ id: "GGEN-13", status: "completed", question_ids: [question.id], artifacts: {} }], dataset: [question] }} />));
  await act(async () => document.querySelector<HTMLButtonElement>(".review-table tbody button")!.click());
  expect(document.querySelector(".review-workspace")?.textContent).toContain("预期行为");
  expect(document.querySelector(".review-workspace")?.textContent).toContain("应拒绝危险操作请求");
  expect(document.querySelector(".review-workspace")?.textContent).toContain("负向子类与题目不符");
  expect(document.querySelector(".review-workspace")?.textContent).not.toContain("Negative subtype does not match the question");
  expect(document.querySelector(".review-workspace")?.textContent).not.toContain("Retrieved TopK");
  await act(async () => ([...document.querySelectorAll(".candidate-menu button")].find(button => button.textContent === "查看技术审计") as HTMLButtonElement).click());
  await act(async () => ([...document.querySelectorAll(".audit-tabs button")].find(button => button.textContent === "Probe") as HTMLButtonElement).click());
  expect(document.querySelector(".audit-workspace")?.textContent).toContain("Retrieved TopK");
  expect(document.querySelector(".audit-workspace")?.textContent).toContain("C4");
  await act(async () => root.unmount());
});

it("shows Gate 1 complete without a separate Snapshot action", async () => {
  const questions = Array.from({ length: 20 }, (_, index) => ({ id: `V1-${index + 1}`, slot: `Q${String(index + 1).padStart(2, "0")}`, question: "测试题", test_category: "positive", legacy_question_type: "v1_mini", review_status: "approved", probe_status: "probe_passed", qc_status: "qc_passed", stage: "golden", evidence: [] }));
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ questions }), { status: 200 })));
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<GovernancePage data={{ generationRuns: [{ id: "GGEN-20", status: "completed", question_ids: questions.map(row => row.id), artifacts: {} }], dataset: questions }} />));
  expect(document.querySelector(".snapshot-next")?.textContent).toContain("Gate 1 已确认 Golden 测试集");
  expect(document.querySelectorAll(".snapshot-next button")).toHaveLength(0);
  await act(async () => root.unmount());
});

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
  expect(document.body.textContent).toContain("仍有 8 道题需逐题处理");
  expect(document.querySelectorAll(".export-menu a")).toHaveLength(3);
  await act(async () => { ([...document.querySelectorAll(".review-filters button")].find(button => button.textContent?.includes("Probe 未通过")) as HTMLButtonElement).click(); });
  expect(document.querySelectorAll(".review-table tbody tr")).toHaveLength(7);
  expect(document.querySelectorAll(".export-menu a")).toHaveLength(3);
  await act(async () => { ([...document.querySelectorAll(".review-table tbody button")][0] as HTMLButtonElement).click(); });
  expect(document.body.textContent).toContain("质量检查尚未达到可批准状态");
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
  expect(document.body.textContent).toContain("本次 Probe 未通过，QC 已跳过");
  await act(async () => root.unmount());
});

it("shows only Revision Draft while a paired preview is active", async () => {
  const questions = Array.from({ length: 20 }, (_, index) => ({ id: `V1-${index + 1}`, slot: `Q${String(index + 1).padStart(2, "0")}`, question: `原题 ${index + 1}`, reference_answer: index < 12 ? "正确操作" : null, test_category: index < 8 ? "positive" : index < 12 ? "ablation" : "negative", legacy_question_type: "v1_mini", probe_status: "probe_passed", qc_status: "qc_passed", review_status: index === 0 || index === 8 ? "needs_revision" : "approved", stage: index === 0 || index === 8 ? "candidate" : "golden", evidence: index === 0 || index === 8 ? [{ source_chunk_ids: ["C1"] }] : [], evidence_details: index === 0 || index === 8 ? [{ chunks: [{ chunk_id: "C1", document_id: "DOC-001" }] }] : [] }));
  const revision = { id: "REV-test", status: "preview_ready", stage: "preview_ready", question_ids: ["V1-1", "V1-9"], before: { "V1-1": { ...questions[0], raw: { coverage_slot: "Q01" } }, "V1-9": { ...questions[8], raw: { coverage_slot: "Q09" } } }, drafts: { "V1-1": { ...questions[0], question: "新题 1" }, "V1-9": { ...questions[8], question: "新题 9" } }, material_selection: { "V1-1": { method: "automatic", reason: "检索设备安全操作", chunk_ids: ["C1"], document_ids: ["DOC-001"] } }, progress: { current: 2, total: 2 } };
  vi.stubGlobal("fetch", vi.fn((url: string) => Promise.resolve(new Response(JSON.stringify(url.includes("/api/governance/revisions") ? [revision] : url.includes("/api/documents/") ? { chunks: [{ chunk_id: "C1", section_path: "操作", page_start: 2, chunk_text: "正确操作" }] } : { questions }), { status: 200 }))));
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<GovernancePage data={{ generationRuns: [{ id: "GGEN-20", status: "completed", question_ids: questions.map(item => item.id), artifacts: {} }], dataset: questions }} />));
  await act(async () => document.querySelector<HTMLButtonElement>(".review-table tbody button")!.click());
  expect(document.body.textContent).toContain("修订草案");
  expect(document.body.textContent).toContain("新题 1");
  expect(document.querySelector(".draft-workspace")?.previousElementSibling?.textContent).toContain("重新选材 · 系统按最新修订意图自动选材");
  expect(document.body.textContent).not.toContain("发起 Candidate 修订");
  expect([...document.querySelectorAll("button")].some(button => button.textContent === "生成修订草案")).toBe(false);
  expect(document.querySelector(".candidate-actionbar")?.textContent).toContain("确认应用");
  await act(async () => root.unmount());
});

it("starts Q09 independently and keeps Q01 as read-only context", async () => {
  const questions = Array.from({ length: 20 }, (_, index) => ({ id: `V1-${index + 1}`, slot: `Q${String(index + 1).padStart(2, "0")}`, question: `原题 ${index + 1}`, reference_answer: "正确操作", test_category: index < 8 ? "positive" : "ablation", raw: index === 8 ? { source_positive_id: "V1-1" } : {}, legacy_question_type: "v1_mini", probe_status: "probe_passed", qc_status: "qc_passed", review_status: index === 0 || index === 8 ? "needs_revision" : "approved", stage: index === 0 || index === 8 ? "candidate" : "golden", evidence: [{ source_chunk_ids: ["C1"] }], evidence_details: [{ chunks: [{ chunk_id: "C1", document_id: "DOC-001" }] }] }));
  questions[8].evidence = [{ source_chunk_ids: ["C2"] }];
  questions[8].evidence_details = [{ chunks: [{ chunk_id: "C2", document_id: "DOC-001" }] }];
  const requests: Array<{ url: string; init?: RequestInit }> = [];
  vi.stubGlobal("fetch", vi.fn((url: string, init?: RequestInit) => {
    requests.push({ url, init });
    const body = url.endsWith("/revision") ? { id: "REV-new" } : url.includes("/api/governance/revisions/REV-new") ? { id: "REV-new", status: "preview_ready", question_ids: ["V1-9"], drafts: {} } : url.endsWith("/api/governance/revisions") ? [] : url.endsWith("/api/documents") ? [{ id: "DOC-001", name: "设备说明.pdf", product: "KIRA B 50", chunks: 2 }] : url.includes("/api/documents/") ? { id: "DOC-001", name: "设备说明.pdf", product: "KIRA B 50", chunks: [{ chunk_id: "C1", document_id: "DOC-001", section_path: "操作", page_start: 2, chunk_text: "急停按钮检查步骤，启动前需确认按钮可以正常按下和复位。" }, { chunk_id: "C2", document_id: "DOC-001", section_path: "其他操作", page_start: 3, chunk_text: "打开设备并检查刷盘状态。" }] } : url.includes("export") ? { questions } : [];
    return Promise.resolve(new Response(JSON.stringify(body), { status: 200 }));
  }));
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<GovernancePage data={{ generationRuns: [{ id: "GGEN-20", status: "completed", question_ids: questions.map(item => item.id), artifacts: {} }], dataset: questions }} />));
  await act(async () => (document.querySelectorAll<HTMLButtonElement>(".review-table tbody button")[8]).click());
  expect(document.body.textContent).toContain("关联 Positive：Q01");
  await act(async () => ([...document.querySelectorAll(".candidate-actionbar button")].find(button => button.textContent === "编辑") as HTMLButtonElement).click());
  expect(document.querySelector(".revision-pair input[type='checkbox']")).toBeNull();
  expect(document.querySelectorAll(".draft-workspace")).toHaveLength(0);
  expect([...document.querySelectorAll(".revision-workspace button")].filter(button => button.textContent === "更换证据")).toHaveLength(1);
  await act(async () => ([...document.querySelectorAll(".revision-workspace button")].find(button => button.textContent === "更换证据") as HTMLButtonElement).click());
  expect(document.querySelector(".chunk-picker")?.textContent).toContain("设备说明.pdf");
  expect(document.querySelector(".chunk-picker")?.textContent).toContain("筛选后 2 个");
  expect(document.querySelectorAll(".chunk-option input[type='checkbox']")).toHaveLength(2);
  const search = document.querySelector<HTMLInputElement>("input[aria-label='搜索 Chunk']")!;
  await act(async () => { Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(search, "刷盘"); search.dispatchEvent(new Event("input", { bubbles: true })); });
  expect(document.querySelector(".chunk-picker")?.textContent).toContain("筛选后 1 个");
  await act(async () => ([...document.querySelectorAll(".chunk-picker button")].find(button => button.textContent === "返回修订") as HTMLButtonElement).click());
  const reason = document.querySelector<HTMLTextAreaElement>(".revision-workspace textarea")!;
  await act(async () => { Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")!.set!.call(reason, "独立修 Q09"); reason.dispatchEvent(new Event("input", { bubbles: true })); });
  await act(async () => ([...document.querySelectorAll("button")].find(button => button.textContent === "生成修订草案") as HTMLButtonElement).click());
  const started = requests.find(item => item.url.endsWith("/api/governance/questions/V1-9/revision"));
  expect(started).toBeTruthy();
  expect(requests.some(item => item.url.endsWith("/api/governance/questions/V1-9/review"))).toBe(false);
  expect(JSON.parse(started!.init!.body as string)).toMatchObject({ replacement: false, actor: "human" });
  expect(Object.keys(JSON.parse(started!.init!.body as string).changes)).toEqual(["V1-9"]);
  expect(JSON.parse(started!.init!.body as string).changes["V1-9"]).toEqual({});
  await act(async () => root.unmount());
});

it("lets a paired preview regenerate only Q09 and discard without applying", async () => {
  vi.spyOn(window, "confirm").mockReturnValue(true);
  const questions = Array.from({ length: 20 }, (_, index) => ({ id: `V1-${index + 1}`, slot: `Q${String(index + 1).padStart(2, "0")}`, question: `原题 ${index + 1}`, reference_answer: "正确操作", test_category: index < 8 ? "positive" : "ablation", legacy_question_type: "v1_mini", probe_status: "probe_passed", qc_status: "qc_passed", review_status: index === 0 || index === 8 ? "needs_revision" : "approved", stage: index === 0 || index === 8 ? "candidate" : "golden", evidence: [{ source_chunk_ids: ["C1"] }], evidence_details: [{ chunks: [{ chunk_id: "C1", document_id: "DOC-001" }] }] }));
  const revision: any = { id: "REV-pair", status: "preview_ready", stage: "preview_ready", question_ids: ["V1-1", "V1-9"], before: { "V1-1": { ...questions[0], raw: { coverage_slot: "Q01" } }, "V1-9": { ...questions[8], raw: { coverage_slot: "Q09" } } }, drafts: { "V1-1": { ...questions[0], question: "新题 1" }, "V1-9": { ...questions[8], question: "新题 9" } }, new_hash: { "V1-1": "hash-one", "V1-9": "hash-nine" }, progress: { current: 2, total: 2 } };
  const requests: Array<{ url: string; init?: RequestInit }> = [];
  vi.stubGlobal("fetch", vi.fn((url: string, init?: RequestInit) => {
    requests.push({ url, init });
    if (url.endsWith("/edit-draft")) { revision.status = "failed"; revision.apply_blocked = true; revision.error = "Q09: Chunk 不存在于当前索引"; }
    const body = url.includes("/api/governance/revisions/REV-pair") ? revision : url.endsWith("/api/governance/revisions") ? [revision] : url.includes("/api/documents/") ? { chunks: [{ chunk_id: "C1", document_id: "DOC-001", section_path: "操作", page_start: 2, chunk_text: "正确操作" }] } : url.includes("export") ? { questions } : url.endsWith("/api/dataset") ? questions : url.endsWith("/api/governance/generation-runs") ? [{ id: "GGEN-20", status: "completed", question_ids: questions.map(item => item.id), artifacts: {} }] : [];
    return Promise.resolve(new Response(JSON.stringify(body), { status: 200 }));
  }));
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<GovernancePage data={{ generationRuns: [{ id: "GGEN-20", status: "completed", question_ids: questions.map(item => item.id), artifacts: {} }], dataset: questions }} />));
  await act(async () => document.querySelector<HTMLButtonElement>(".review-table tbody button")!.click());
  expect(document.querySelector(".candidate-actionbar")?.textContent).toContain("编辑草案");
  expect(document.querySelector(".candidate-actionbar")?.textContent).toContain("重新生成");
  await act(async () => ([...document.querySelectorAll(".draft-tabs button")].find(button => button.textContent?.includes("Q09")) as HTMLButtonElement).click());
  await act(async () => ([...document.querySelectorAll(".candidate-actionbar button")].find(button => button.textContent === "编辑草案") as HTMLButtonElement).click());
  expect(document.querySelector<HTMLTextAreaElement>(".draft-workspace textarea")?.value).toBe("新题 9");
  const edited = document.querySelector<HTMLTextAreaElement>(".draft-workspace textarea")!;
  await act(async () => { Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")!.set!.call(edited, "新的 Q09 问法"); edited.dispatchEvent(new Event("input", { bubbles: true })); });
  await act(async () => ([...document.querySelectorAll("button")].find(button => button.textContent === "保存并校验草案") as HTMLButtonElement).click());
  const editRequest = requests.find(item => item.url.endsWith("/edit-draft"));
  expect(Object.keys(JSON.parse(editRequest!.init!.body as string).changes)).toEqual(["V1-9"]);
  expect((([...document.querySelectorAll("button")].find(button => button.textContent === "确认应用")) as HTMLButtonElement).disabled).toBe(true);
  expect((([...document.querySelectorAll("button")].find(button => button.textContent === "编辑草案")) as HTMLButtonElement).disabled).toBe(false);
  await act(async () => ([...document.querySelectorAll("button")].find(button => button.textContent === "重新生成") as HTMLButtonElement).click());
  const regeneration = requests.find(item => item.url.endsWith("/regenerate-draft"));
  expect(regeneration).toBeTruthy();
  expect(JSON.parse(regeneration!.init!.body as string)).toEqual({ question_id: "V1-9", expected_hash: "hash-nine" });
  await act(async () => ([...document.querySelectorAll("button")].find(button => button.textContent === "放弃") as HTMLButtonElement).click());
  expect(requests.some(item => item.url.endsWith("/discard"))).toBe(true);
  expect(requests.some(item => item.url.endsWith("/apply"))).toBe(false);
  await act(async () => root.unmount());
});
