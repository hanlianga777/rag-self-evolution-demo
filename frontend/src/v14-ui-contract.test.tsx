// @vitest-environment jsdom
import { act, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { ExperimentPage } from "./pages/ExperimentPage";
import { Drawer } from "./components/Dialog";
import { OverviewPage } from "./pages/OverviewPage";
import { GovernancePage } from "./pages/GovernancePage";
import { VerificationPage } from "./pages/VerificationPage";
import { VersionsPage } from "./pages/VersionsPage";
import { EvolutionPage } from "./pages/EvolutionPage";
import { ExecutionMetrics } from "./components/PipelineFields";
import { RetrievalEvidence } from "./components/RetrievalEvidence";
import { getJson, loadAppData } from "./api";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
let root: ReturnType<typeof createRoot>;
afterEach(() => { if (root) act(() => root.unmount()); document.body.innerHTML = ""; sessionStorage.clear(); vi.unstubAllGlobals(); });
const render = async (node: ReactNode) => { root = createRoot(document.body.appendChild(document.createElement("div"))); await act(async () => root.render(node)); };
const identity = (baseline: string, experiment?: string) => ({ current_baseline_id: baseline, current_experiment_id: experiment, current_golden_id: "GD-fixture", current_corpus_fingerprint: { D: "fixture" } });
const data = (baseline = "B0") => ({ workspace: identity(baseline), evaluation: { id: baseline }, versions: [{ id: "P0", status: "active", provenance: "published", config: { top_k: 6 } }] });
const fill = async (question: string) => act(async () => { const input = document.querySelector("textarea")!; Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")!.set!.call(input, question); input.dispatchEvent(new Event("input", { bubbles: true })); });

it("ID-08 ignores an old same-question comparison after Baseline changes", async () => {
  const replies: ((reply: Response) => void)[] = [];
  vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(resolve => replies.push(resolve))));
  await render(<ExperimentPage data={data()} onOpenCitation={() => {}} />);
  await fill("同一个问题");
  await act(async () => document.querySelector<HTMLButtonElement>(".query-action button")!.click());
  expect(replies).toHaveLength(2);
  await act(async () => root.render(<ExperimentPage data={data("B1")} onOpenCitation={() => {}} />));
  await act(async () => replies.forEach(reply => reply(new Response(JSON.stringify({ answer: "旧 B0 回答", version: "B0" })))));
  expect(document.body.textContent).not.toContain("旧 B0 回答");
  expect(document.querySelectorAll(".experiment-answer-card .running")).toHaveLength(0);
});

it("ID-08 clears Candidate Drawer and rejects an old candidate report after identity changes", async () => {
  let resolveReport!: (reply: Response) => void;
  vi.stubGlobal("fetch", vi.fn((url: string) => url.includes("/evaluations/") ? new Promise<Response>(resolve => { resolveReport = resolve; }) : Promise.resolve(new Response(JSON.stringify({ search_space: {} })))));
  const old = { workspace: identity("B0", "E0"), evaluation: { id: "B0" }, optimization: { id: "E0", candidates: [{ id: "A0", config: {}, reasoning: { candidate_label: "A" }, result: { evaluation_run_id: "R0" } }] } };
  await render(<EvolutionPage data={old} />);
  await act(async () => [...document.querySelectorAll("button")].find(button => button.textContent === "A / B / C / D")!.click());
  await act(async () => [...document.querySelectorAll("button")].find(button => button.textContent?.includes("查看方案与完整报告"))!.click());
  expect(document.querySelector('[role="dialog"]')).not.toBeNull();
  await act(async () => root.render(<EvolutionPage data={{ workspace: identity("B1"), evaluation: { id: "B1" }, optimization: { status: "not_run" } }} />));
  await act(async () => resolveReport(new Response(JSON.stringify({ cases: [{ question: "旧身份案例" }] }))));
  expect(document.querySelector('[role="dialog"]')).toBeNull();
  expect(document.body.textContent).not.toContain("旧身份案例");
});

it("CT-04 displays collected zero cost and unknown cost reason separately", async () => {
  await render(<><ExecutionMetrics metrics={{ ttft_ms: null, cost_estimation: { status: "estimated", amount: 0, currency: "USD" } }} /><ExecutionMetrics metrics={{ cost_estimation: { status: "unavailable", amount: null, reason: "billing_period_ambiguous" } }} /></>);
  expect(document.body.textContent).toContain("0 USD");
  expect(document.body.textContent).toContain("计费时段或节假日日历未确认");
  expect(document.body.textContent).toContain("未采集真实首输出时间");
});

it("VP-07/09 keeps Candidate AnyHit separate from Final AllHit and missing observations", async () => {
  await render(<RetrievalEvidence metrics={{ retrieval_trace: { candidates: [{ chunk_id: "C1", content: "真实合成材料" }], final: [] }, evidence_coverage: { candidate_recall: { any_hit: true, all_hit: false }, final_context: { any_hit: false, all_hit: false } } }} />);
  expect(document.body.textContent).toContain("Any Hit：是 · All Hit：否");
  expect(document.body.textContent).toContain("真实合成材料");
  expect(document.body.textContent).toContain("实际采集 0 条");
  await act(async () => root.render(<RetrievalEvidence metrics={{ retrieval_trace: { candidates: null, final: [] } }} />));
  expect(document.body.textContent).toContain("历史未采集，不能用另一层列表替代");
});

it("surfaces structured retrieval failures without object coercion", async () => {
  await expect(getJson("/api/preview", vi.fn(async () => new Response(JSON.stringify({ detail: { code: "RETRIEVAL_EXECUTION_FAILED", message: "本地检索执行失败，请检查索引" } }), { status: 503 })))).rejects.toThrow("本地检索执行失败，请检查索引");
});

it("ID-08 refuses incoherent parallel app identities after one bounded retry", async () => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => new Response(JSON.stringify({ ...identity(url.includes("optimization") ? "B0" : "B1") }))));
  await expect(loadAppData()).rejects.toThrow("工作区身份正在变化");
  expect(fetch).toHaveBeenCalledTimes(20);
});


it("RL-03/05 uses centered confirmation and keeps failed release visible without fake success", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ detail: "提交时资格已失效" }), { status: 409 })));
  const candidate = { id: "A-fixture", status: "evaluated", reasoning: { candidate_label: "A" }, release_state: { sandbox: true, qualified: true, recommended: true, round_complete: true } };
  await render(<VersionsPage data={{ versions: [{ id: "P0", status: "active" }], optimization: { candidates: [candidate] } }} />);
  await act(async () => document.querySelector<HTMLButtonElement>(".release-actions button")!.click());
  expect(document.querySelector(".confirm-dialog")?.textContent).toContain("Gate 3");
  await act(async () => [...document.querySelectorAll<HTMLButtonElement>(".confirm-dialog button")].find(button => button.textContent === "确认")!.click());
  expect(document.querySelector(".confirm-dialog")?.textContent).toContain("提交时资格已失效");
  expect(document.querySelector(".release-actions")?.textContent).toBe("确认发布");
  expect(document.querySelector(".version-records")?.textContent || "").not.toContain("P1");
  expect(fetch).toHaveBeenCalledTimes(1);
});


it("preserves unsaved Drawer edits until explicit discard confirmation", async () => {
  const change = vi.fn();
  await render(<Drawer open guardEdits title="Fixture 编辑" onOpenChange={change}><input aria-label="未保存内容" /></Drawer>);
  const input = document.querySelector<HTMLInputElement>("input")!;
  await act(async () => { Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(input, "未保存修改"); input.dispatchEvent(new Event("input", { bubbles: true })); });
  await act(async () => document.querySelector<HTMLButtonElement>(".drawer-head button")!.click());
  expect(change).not.toHaveBeenCalled();
  expect(document.querySelector(".confirm-dialog")?.textContent).toContain("放弃未保存修改");
  await act(async () => document.querySelector<HTMLButtonElement>(".confirm-dialog button.primary")!.click());
  expect(change).toHaveBeenCalledWith(false);
});

it("review R1 separates Gate PASS from unqualified Regression FAIL in Sandbox and D report", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ search_space: {} }))));
  const d = { id: "E1-D", status: "evaluated", config: {}, reasoning: { candidate_label: "D" }, result: { gates: { passed: true, passed_count: 11, total: 11 }, regression: { passed: false, status: "FAIL" }, qualification: { qualified: false } } };
  await render(<EvolutionPage data={{ workspace: identity("B1", "E1"), evaluation: { id: "B1", status: "completed", config: {} }, optimization: { id: "E1", candidates: [d], result: { report_confirmation: { winner_id: "A" }, composite: { candidate_id: d.id } } } }} />);
  await act(async () => [...document.querySelectorAll("button")].find(x => x.textContent === "Sandbox")!.click());
  expect(document.querySelector(".sandbox-status-grid")?.textContent).toContain("Hard Gate 11/11 · 通过不合格");
  expect(document.querySelector(".sandbox-status-grid")?.textContent).not.toContain("Gate 未通过");
  await act(async () => [...document.querySelectorAll("button")].find(x => x.textContent === "A / B / C / D")!.click());
  await act(async () => [...document.querySelectorAll("button")].find(x => x.textContent === "查看 D 完整报告与 Decision")!.click());
  expect(document.querySelector('[role="dialog"]')?.textContent).toContain("发布资格：不合格 · Hard Gate：通过");
  expect(document.querySelector('[role="dialog"]')?.textContent).toContain("Regression：FAIL");
});

it.each([undefined, "running", "failed"])("review R2 keeps %s Baseline at Evaluation before Agent", async status => {
  const input = { ...data("B1"), overview: { dataset: { expected_count: 1, approved: 1 } }, evaluation: status ? { id: "B1", status } : {} };
  await render(<OverviewPage data={input} navigate={() => {}} />);
  expect(document.querySelector(".next-action a")?.getAttribute("href")).toBe("#evaluation");
  expect(document.querySelector(".next-action")?.textContent).not.toContain("运行 Optimization Agent");
});

it("review R2 an older Production does not finish a new recommendation Gate3", async () => {
  const candidate = { id: "E1-A", status: "evaluated", reasoning: { candidate_label: "A" }, release_state: { sandbox: true, qualified: true, recommended: true, round_complete: true } };
  const input = { ...data("B1"), overview: { dataset: { expected_count: 1, approved: 1 } }, evaluation: { id: "B1", status: "completed" }, optimization: { id: "E1", baseline_run_id: "B1", candidates: [candidate], recommendation: { result: { status: "Recommended", recommended_candidate: candidate.id } } }, versions: [{ id: "P0", status: "active", provenance: "published", snapshot: { candidate_id: "E0-C" } }] };
  await render(<OverviewPage data={input} navigate={() => {}} />);
  expect(document.querySelector(".next-action h2")?.textContent).toContain("Gate 3");
  await act(async () => root.render(<VersionsPage data={input} />));
  expect(document.querySelector('[aria-label="发布阶段"] li:last-child')?.className).toBe("pending");
  expect(document.querySelector(".release-actions")?.textContent).toBe("确认发布");
  expect(input.versions[0].snapshot.candidate_id).toBe("E0-C");
});

it("review R3 persisted Golden risks count and filter exact rows without changing approval", async () => {
  const base = { stage: "candidate", test_category: "positive", review_status: "human_review_pending", probe_status: "probe_passed", qc_status: "qc_passed", legacy_question_type: "v1_mini", evidence: [] };
  const rows: Record<string, any>[] = [
    { ...base, id: "Q1", question: "P0 可接受", qc: { priority: "P0" }, approval_eligibility: { requires_qc_p0_acceptance: true, blocking_reasons: [] } },
    { ...base, id: "Q2", question: "P0 确定性阻断", qc: { priority: "P0" }, approval_eligibility: { requires_qc_p0_acceptance: true, blocking_reasons: ["证据错误"] } },
    { ...base, id: "Q3", question: "P1 检索不连贯", qc: { priority: "P1" }, probe: { probe_details: { classification: "RETRIEVAL_INCOHERENT" } } },
    { ...base, id: "Q4", test_category: "negative", question: "伪负向风险", probe: { probe_details: { classification: "FAKE_NEGATIVE_RISK" } } },
    { ...base, id: "Q5", question: "执行失败需修订", review_status: "needs_revision", probe: { probe_details: { classification: "RETRIEVAL_EXECUTION_FAILED", probe_execution_status: "failed" } } },
    { ...base, id: "Q6", question: "未分类历史" },
  ];
  const run = { id: "G1", status: "completed", question_ids: rows.map(x => x.id), profile: { expected_count: 6 }, artifacts: {} };
  vi.stubGlobal("fetch", vi.fn(async (url: string) => new Response(JSON.stringify(url.includes("/export") ? { questions: rows } : url.endsWith("generation-runs") ? [run] : url.endsWith("/dataset") ? rows : []))));
  await render(<GovernancePage data={{ dataset: rows, generationRuns: [run] }} />);
  const cases: [string, string[]][] = [["QC P0 · 2", ["P0 可接受", "P0 确定性阻断"]], ["QC P0 待人工接受 · 1", ["P0 可接受"]], ["QC P1 · 1", ["P1 检索不连贯"]], ["疑似伪负向 · 1", ["伪负向风险"]], ["检索不连贯 · 1", ["P1 检索不连贯"]], ["检索执行失败 · 1", ["执行失败需修订"]], ["审批阻断 · 1", ["P0 确定性阻断"]], ["需修订 / 已拒绝 · 1", ["执行失败需修订"]]];
  for (const [label, expected] of cases) {
    await act(async () => [...document.querySelectorAll<HTMLButtonElement>(".exception-summary button")].find(x => x.textContent === label)!.click());
    expect(document.querySelectorAll(".review-table tbody tr")).toHaveLength(expected.length);
    for (const question of expected) expect(document.querySelector(".review-table tbody")?.textContent).toContain(question);
  }
  expect(rows[1].approval_eligibility?.blocking_reasons).toEqual(["证据错误"]);
  expect(fetch).not.toHaveBeenCalledWith(expect.anything(), expect.objectContaining({ method: "POST" }));
});

it("review R4 pending Trigger ignores prior ABC and explicitly starts its same Round0 context", async () => {
  let confirmed = false, started = false;
  const posts: any[] = [];
  const pending = { id: "T1", event_id: "M1", status: "pending_human_confirm", optimization_run_id: null, reason: "fixture human Bad Case" };
  const monitoring = () => ({ events: [{ id: "M1", question: "Fixture QA", determinable: true }], triggers: [{ ...pending, status: confirmed ? "human_confirmed" : pending.status, optimization_run_id: confirmed ? "E-monitor" : null }] });
  const context = () => ({ id: "E-monitor", baseline_run_id: "B1", status: started ? "completed" : "pending_agent", result: { round: started ? 1 : 0 }, candidates: started ? ["A", "B", "C"].map(id => ({ id })) : [] });
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === "POST") { posts.push({ url, body: JSON.parse(init.body as string) }); if (url.endsWith("/confirm")) confirmed = true; else if (url.endsWith("/experiments/run")) started = true; }
    return new Response(JSON.stringify(url.endsWith("/monitoring") ? monitoring() : url.includes("/experiments/") ? context() : {}));
  }));
  await render(<VerificationPage data={{ ...data("B1"), monitoring: monitoring(), optimization: { id: "E-prior", candidates: [{ id: "old-A" }] } }} onOpenDocument={() => {}} onOpenCitation={() => {}} />);
  await act(async () => [...document.querySelectorAll("button")].find(x => x.textContent === "Monitoring")!.click());
  expect(document.querySelector('[aria-label="监控阶段"] li:last-child')?.className).toBe("pending");
  await act(async () => [...document.querySelectorAll("button")].find(x => x.textContent === "人工确认")!.click());
  expect(document.querySelector(".monitoring-context")?.textContent).toContain("E-monitor");
  expect(document.querySelector(".monitoring-context")?.textContent).toContain("待启动 Round 1");
  expect(document.querySelector('[aria-label="监控阶段"] li:last-child')?.className).toBe("current");
  await act(async () => [...document.querySelectorAll("button")].find(x => x.textContent === "启动此上下文 Agent · Round 1")!.click());
  expect(posts[1]).toEqual({ url: expect.stringContaining("/api/experiments/run"), body: { trigger_id: "T1" } });
  expect(document.querySelector(".monitoring-context")?.textContent).toContain("E-monitor");
  expect(document.querySelector(".monitoring-context")?.textContent).toContain("Round 1");
  expect(document.querySelector('[aria-label="监控阶段"] li:last-child')?.className).toBe("completed");
  expect(document.querySelector('a[href="#evolution"]')).toBeNull();
});

it("review R4 selected historical Monitoring context is identified and cannot start under a new Baseline", async () => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => new Response(JSON.stringify(url.includes("/experiments/") ? { id: "E-history", baseline_run_id: "B0", status: "pending_agent", result: { round: 0 }, candidates: [] } : { triggers: [{ id: "T-history", status: "human_confirmed", optimization_run_id: "E-history" }], events: [] }))));
  await render(<VerificationPage data={{ ...data("B1"), monitoring: { triggers: [{ id: "T-history", status: "human_confirmed", optimization_run_id: "E-history" }] } }} onOpenDocument={() => {}} onOpenCitation={() => {}} />);
  await act(async () => [...document.querySelectorAll("button")].find(x => x.textContent === "Monitoring")!.click());
  expect(document.querySelector(".monitoring-context")?.textContent).toContain("T-history");
  expect(document.querySelector(".monitoring-context")?.textContent).toContain("E-history");
  expect(document.querySelector(".monitoring-context")?.textContent).toContain("历史上下文，只读");
  expect([...document.querySelectorAll<HTMLButtonElement>("button")].find(x => x.textContent?.includes("启动此上下文"))?.disabled).toBe(true);
});
