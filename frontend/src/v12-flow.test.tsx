// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { CandidateWorkspace } from "./pages/CandidateWorkspace";
import { EvolutionPage } from "./pages/EvolutionPage";
import { GovernancePage } from "./pages/GovernancePage";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
afterEach(() => { document.body.innerHTML = ""; vi.unstubAllGlobals(); });

it("shows null Probe and QC thresholds as advisory in technical audit", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response("[]", { status: 200 })));
  const row = { id: "Q1", slot: "Q01", question: "问题", test_category: "positive", stage: "candidate", probe_status: "probe_passed", qc_status: "qc_passed", probe: { score: 72, threshold: null }, qc: { score: 70, threshold: null }, evidence: [] };
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<CandidateWorkspace row={row} peers={[row]} busy={false} onRun={() => {}} onReview={async () => true} onRefresh={async () => {}} operation={{ watchRevision: () => {} } as any} />));
  await act(async () => [...document.querySelectorAll<HTMLButtonElement>(".candidate-menu button")].find(button => button.textContent === "查看技术审计")!.click());
  await act(async () => [...document.querySelectorAll<HTMLButtonElement>(".audit-tabs button")].find(button => button.textContent === "Probe")!.click());
  expect(document.querySelector(".audit-workspace")?.textContent).toContain("72 / 不作为审批阈值");
  await act(async () => [...document.querySelectorAll<HTMLButtonElement>(".audit-tabs button")].find(button => button.textContent === "QC")!.click());
  expect(document.querySelector(".audit-workspace")?.textContent).toContain("70 / 不作为审批阈值");
  await act(async () => root.unmount());
});

it("accepts a reviewable QC P0 with a recorded reason even when scores are low", async () => {
  const requests: any[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === "POST") requests.push(JSON.parse(init.body as string));
    return new Response(JSON.stringify(url.endsWith("/api/documents") ? [] : {}), { status: 200 });
  }));
  const row = { id: "Q1", slot: "Q01", question: "问题", test_category: "positive", stage: "candidate", review_status: "human_review_pending", probe_status: "needs_revision", qc_status: "qc_failed", probe: { score: 72 }, qc: { score: 70 }, evidence: [], approval_eligibility: { can_approve: false, blocking_reasons: [], requires_qc_p0_acceptance: true, qc_reason: "证据支持待人工判断", qc_created_at: "2026-09-27T00:00:00Z" } };
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<CandidateWorkspace row={row} peers={[row]} busy={false} onRun={() => {}} onReview={async (_id, _decision, reason, _tags, accept_qc_p0) => { requests.push({ reason, accept_qc_p0 }); return true; }} onRefresh={async () => {}} operation={{ watchRevision: () => {} } as any} />));
  const approve = [...document.querySelectorAll<HTMLButtonElement>("button")].find(button => button.textContent === "批准")!;
  expect(approve.disabled).toBe(false);
  expect(document.body.textContent).toContain("证据支持待人工判断");
  await act(async () => approve.click());
  expect(requests.some(item => item?.accept_qc_p0 === true)).toBe(false);
  const reason = document.querySelector<HTMLTextAreaElement>("textarea[aria-label='接受 QC P0 的理由']")!;
  await act(async () => { Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")!.set!.call(reason, "人工确认真实证据支持"); reason.dispatchEvent(new Event("input", { bubbles: true })); });
  await act(async () => [...document.querySelectorAll<HTMLButtonElement>("button")].find(button => button.textContent === "确认接受并批准")!.click());
  expect(requests.at(-1)).toEqual({ accept_qc_p0: true, reason: "人工确认真实证据支持" });
  await act(async () => root.unmount());
});

it("uses one Gate 1 confirmation and never offers a separate Snapshot action", async () => {
  const rows = Array.from({ length: 20 }, (_, index) => ({ id: `Q${index}`, slot: `Q${index}`, question: "问题", test_category: "positive", review_status: "human_review_pending", stage: "candidate", approval_eligibility: { can_approve: true, blocking_reasons: [] } }));
  const requests: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => { if (init?.method === "POST") requests.push(url); return new Response(JSON.stringify(url.includes("export") ? { questions: rows } : []), { status: 200 }); }));
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<GovernancePage data={{ dataset: rows, generationRuns: [{ id: "G1", status: "completed", question_ids: rows.map(row => row.id), profile: { expected_count: 20 }, artifacts: {} }], snapshots: [] }} />));
  expect(document.body.textContent).toContain("确认 Golden 测试集");
  expect(document.body.textContent).not.toContain("创建 Golden Snapshot");
  await act(async () => root.unmount());
  expect(requests).not.toContain(expect.stringContaining("/snapshot"));
});

it("keeps Gate 1 available when every question is approved but the current run has no matching snapshot", async () => {
  const rows = Array.from({ length: 20 }, (_, index) => ({ id: `Q${index}`, slot: `Q${index}`, question: "问题", test_category: "positive", review_status: "approved", stage: "golden", approval_eligibility: { can_approve: true, blocking_reasons: [] } }));
  const run = { id: "G1", status: "completed", question_ids: rows.map(row => row.id), profile: { expected_count: 20 }, artifacts: {} };
  vi.stubGlobal("fetch", vi.fn(async (url: string) => new Response(JSON.stringify(url.includes("export") ? { questions: rows } : []), { status: 200 })));
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<GovernancePage data={{ dataset: rows, generationRuns: [run], snapshots: [{ id: "OLD", snapshot: { generation_run_id: "G1", question_ids: ["old-question"] } }] }} />));
  expect(document.querySelector(".snapshot-next")).toBeNull();
  const confirm = [...document.querySelectorAll<HTMLButtonElement>(".review-batch button")].find(button => button.textContent === "确认 Golden 测试集")!;
  expect(confirm).toBeTruthy();
  await act(async () => document.querySelector<HTMLInputElement>(".review-batch input")!.click());
  expect(confirm.disabled).toBe(false);
  await act(async () => root.unmount());
});

it("sends one atomic Gate 1 review request and shows the frozen version after refresh", async () => {
  const rows = Array.from({ length: 20 }, (_, index) => ({ id: `Q${index}`, slot: `Q${index}`, question: "问题", test_category: "positive", review_status: "human_review_pending", stage: "candidate", approval_eligibility: { can_approve: true, blocking_reasons: [] } }));
  const run = { id: "G1", status: "completed", question_ids: rows.map(row => row.id), profile: { expected_count: 20 }, artifacts: {} };
  const requests: Array<{ url: string; body: any }> = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === "POST") requests.push({ url, body: JSON.parse(init.body as string) });
    const reviewed = rows.map(row => ({ ...row, review_status: "approved", stage: "golden" }));
    const body = url.includes("export") ? { questions: requests.length ? reviewed : rows } : url.endsWith("/api/dataset") ? reviewed : url.endsWith("/api/governance/generation-runs") ? [run] : url.endsWith("/api/governance/snapshots") ? [{ id: "GOLDEN-v1", snapshot: { generation_run_id: "G1", question_ids: run.question_ids } }] : [];
    return new Response(JSON.stringify(body), { status: 200 });
  }));
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<GovernancePage data={{ dataset: rows, generationRuns: [run], snapshots: [] }} />));
  await act(async () => document.querySelector<HTMLInputElement>(".review-batch input")!.click());
  await act(async () => [...document.querySelectorAll<HTMLButtonElement>(".review-batch button")].find(button => button.textContent === "确认 Golden 测试集")!.click());
  expect(requests).toEqual([{ url: expect.stringContaining("/api/governance/review-batch"), body: { question_ids: rows.map(row => row.id), confirmed_manual_review: true } }]);
  expect(document.querySelector(".snapshot-next")?.textContent).toContain("Gate 1 已确认");
  expect(document.querySelector(".review-batch")).toBeNull();
  await act(async () => root.unmount());
});

it("starts replacement as one slot draft without first changing a pending review", async () => {
  const row = { id: "Q9", slot: "Q09", question: "问题", test_category: "positive", review_status: "human_review_pending", stage: "candidate", evidence: [] };
  const requests: Array<{ url: string; body: any }> = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === "POST") requests.push({ url, body: JSON.parse(init.body as string) });
    const body = url.endsWith("/revision") ? { id: "REV9" } : url.includes("/revisions/REV9") ? { id: "REV9", status: "queued", question_ids: ["Q9"] } : [];
    return new Response(JSON.stringify(body), { status: 200 });
  }));
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<CandidateWorkspace row={row} peers={[row]} busy={false} onRun={() => {}} onReview={async () => { throw Error("review must not run"); }} onRefresh={async () => {}} operation={{ watchRevision: () => {} } as any} />));
  await act(async () => [...document.querySelectorAll<HTMLButtonElement>(".candidate-actionbar button")].find(button => button.textContent === "替换")!.click());
  const reason = document.querySelector<HTMLTextAreaElement>(".revision-workspace textarea")!;
  await act(async () => { Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")!.set!.call(reason, "换成另一知识点"); reason.dispatchEvent(new Event("input", { bubbles: true })); });
  await act(async () => [...document.querySelectorAll<HTMLButtonElement>(".candidate-actionbar button")].find(button => button.textContent === "生成修订草案")!.click());
  expect(requests[0]).toEqual({ url: expect.stringContaining("/api/governance/questions/Q9/revision"), body: expect.objectContaining({ replacement: true, actor: "human" }) });
  expect(Object.keys(requests[0].body.changes)).toEqual(["Q9"]);
  await act(async () => root.unmount());
});

it("confirms an evaluated qualified winner and then offers composite D", async () => {
  const requests: Array<{ url: string; body?: any }> = [];
  const candidate = { id: "A1", status: "evaluated", reasoning: { candidate_label: "A", round: 1 }, result: { qualification: { qualified: true }, gates: { passed: true, passed_count: 11, total: 11 }, regression: { status: "passed" } } };
  const experiment = { id: "EXP1", status: "Needs Report Confirmation", candidates: [candidate], evaluation_budget: { used: 3, max: 12, reserved_for_d1: 1 }, rounds: [{ round: 1, complete: true, evaluated: 3 }] };
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => { if (init?.method === "POST") requests.push({ url, body: JSON.parse(init.body as string || "{}") }); return new Response(JSON.stringify(experiment), { status: 200 }); }));
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<EvolutionPage data={{ optimization: experiment, evaluation: { status: "completed" }, badCases: [{}] }} />));
  await act(async () => [...document.querySelectorAll<HTMLButtonElement>("button")].find(button => button.textContent === "Sandbox")!.click());
  await act(async () => [...document.querySelectorAll<HTMLButtonElement>("button")].find(button => button.textContent?.includes("确认报告"))!.click());
  expect(requests[0]).toEqual({ url: expect.stringContaining("/api/experiments/EXP1/recommendation"), body: { candidate_id: "A1", actor: "human" } });
  await act(async () => root.unmount());
});

it("allows a partial final round while keeping one Sandbox slot for D", async () => {
  const experiment = { id: "EXP2", candidates: [], recommendation: { result: { status: "No Qualified Candidate" } }, evaluation_budget: { used: 9, max: 12, reserved_for_d: 1 }, rounds: [{ round: 3, complete: true, evaluated: 2, total: 2 }] };
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<EvolutionPage data={{ optimization: experiment, evaluation: {}, badCases: [] }} />));
  await act(async () => [...document.querySelectorAll<HTMLButtonElement>("button")].find(button => button.textContent === "优化 Agent")!.click());
  expect(document.body.textContent).toContain("Round 3 · 2/2");
  await act(async () => [...document.querySelectorAll<HTMLButtonElement>("button")].find(button => button.textContent === "A / B / C / D")!.click());
  expect(document.body.textContent).toContain("继续优化下一轮");
  await act(async () => root.unmount());
});
