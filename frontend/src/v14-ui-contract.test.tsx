// @vitest-environment jsdom
import { goldenFixture } from "./golden-test-fixture";
import { invalidateGolden } from "./goldenCache";
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
import { CurrentCoveragePreview } from "./pages/BusinessImportPanel";
import { CandidateWorkspace } from "./pages/CandidateWorkspace";
import { ExecutionMetrics } from "./components/PipelineFields";
import { RetrievalEvidence } from "./components/RetrievalEvidence";
import { getJson, loadAppData } from "./api";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
let root: ReturnType<typeof createRoot>;
afterEach(() => { invalidateGolden(); if (root) act(() => root.unmount()); document.body.innerHTML = ""; sessionStorage.clear(); vi.unstubAllGlobals(); });
const render = async (node: ReactNode) => { root = createRoot(document.body.appendChild(document.createElement("div"))); await act(async () => root.render(node)); };
const identity = (baseline: string, experiment?: string) => ({ current_baseline_id: baseline, current_experiment_id: experiment, current_golden_id: "GD-fixture", current_corpus_fingerprint: { D: "fixture" } });
const data = (baseline = "B0") => ({ workspace: identity(baseline), evaluation: { id: baseline }, versions: [{ id: "P0", status: "active", provenance: "published", config: { top_k: 6 } }] });
const fill = async (question: string) => act(async () => { const input = document.querySelector("textarea")!; Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")!.set!.call(input, question); input.dispatchEvent(new Event("input", { bubbles: true })); });

const clickText = async (label: string) => act(async () => [...document.querySelectorAll<HTMLButtonElement>("button")].find(button => button.textContent === label)!.click());
const previewPlan = (profile = "mini", corpus = { D: "fixture" }) => ({ plan_id: `PLAN-${profile}`, planner_version: "fixture-v2", profile: { name: profile }, corpus_fingerprint: corpus, chunk_clusters: { C1: 0 }, initial_k: 2, final_k: 1, merge_mapping: [{ from: 1, to: 0 }], clusters: [{ cluster_id: 0, size: 1, anchor_quota: 20, quotas: { positive: 8, ablation: 4, negative: 8 }, representative_chunk_ids: ["C1"] }], slots: [{ slot_id: "Q01", topic_cluster: 0, document_id: "D", material_chunk_ids: ["C1"], construction_type: "Fact" }], reuse_statistics: { reused_slots: 0 }, gaps: [] });

it.each([true, false])("I4 manual current Preview is available with legacy Run=%s and preserves saved objects", async legacy => {
  const run = { id: "legacy", status: "completed", profile: { expected_count: 20 }, artifacts: {}, question_ids: [] };
  const input = { ...data("B1"), dataset: [], generationRuns: legacy ? [run] : [], snapshots: [] };
  const frozen = JSON.stringify(input), posts: any[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => { if (init?.method === "POST") { posts.push({ url, body: JSON.parse(init.body as string) }); return new Response(JSON.stringify(previewPlan())); } return new Response(JSON.stringify([])); }));
  await render(<GovernancePage data={input} />);
  expect(posts).toHaveLength(0);
  if (legacy) await clickText("运行审计");
  await clickText("预览当前 Corpus Coverage");
  expect(posts).toEqual([{ url: expect.stringContaining("/api/governance/coverage-preview"), body: { profile: "mini" } }]);
  expect(document.body.textContent).toContain("当前 Corpus · V2 Coverage Preview");
  expect(document.body.textContent).toContain("初始 K 2 → 最终 K 1");
  expect(JSON.stringify(input)).toBe(frozen);
});

it.each(["profile", "corpus"])("I4 suppresses delayed Preview after %s changes", async change => {
  const replies: ((reply: Response) => void)[] = [];
  vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(resolve => replies.push(resolve))));
  await render(<CurrentCoveragePreview profile="mini" corpusFingerprint={{ D: "fixture" }} documents={[]} />);
  await clickText("预览当前 Corpus Coverage");
  await act(async () => root.render(<CurrentCoveragePreview profile={change === "profile" ? "full" : "mini"} corpusFingerprint={{ D: change === "corpus" ? "new" : "fixture" }} documents={[]} />));
  await act(async () => replies[0](new Response(JSON.stringify(previewPlan()))));
  expect(document.querySelector('[role="dialog"]')).toBeNull();
  expect(document.body.textContent).toContain("尚无当前 Preview");
  expect(fetch).toHaveBeenCalledTimes(1);
});

it.each(["mini", "medium", "full"])("I4 Preview carries selected %s Profile and reports server failure", async profile => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ detail: "Fixture planner unavailable" }), { status: 422 })));
  await render(<CurrentCoveragePreview profile={profile} documents={[]} />);
  await clickText("预览当前 Corpus Coverage");
  expect(JSON.parse((fetch as any).mock.calls[0][1].body)).toEqual({ profile });
  expect(document.body.textContent).toContain("Preview 失败：Fixture planner unavailable");
  expect(document.querySelector('[role="dialog"]')).toBeNull();
});

it.each([{ proposal: "实际持久化 proposal" }, { why: "兼容 Why 字段" }, {}])("I5 candidate report renders persisted rationale %j", async reasoning => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ search_space: {} }))));
  const candidate = { id: "E1-A", status: "generated", config: {}, reasoning: { candidate_label: "A", hypothesis: "假设", risk: "风险", observed_evidence: [], ...reasoning }, result: {} };
  await render(<EvolutionPage data={{ ...data("B1"), optimization: { id: "E1", candidates: [candidate] } }} />);
  await clickText("A / B / C / D"); await clickText("查看方案与完整报告");
  expect(document.querySelector('[role="dialog"]')?.textContent).toContain(`Why：${(reasoning as any).proposal || (reasoning as any).why || "未记录"}`);
});

it.each([0, 1.25, null])("M4 Sandbox and release keep frozen estimated cost %s and source-backed missing reason", async cost => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ search_space: {} }))));
  const candidate = { id: "E1-A", status: "evaluated", config: {}, reasoning: { candidate_label: "A" }, result: { comparison_metrics: { token_cost: cost, token_cost_status: "Token Usage / Provider Cost unavailable", cost_estimation: cost == null ? { status: "unavailable", amount: null, reason: "usage_missing" } : { status: "estimated", amount: cost, currency: "USD", price_snapshot: { currency: "USD", version: "fixture-price-v1" }, calls: [{ model: "fixture-model", input_tokens: 5, output_tokens: 0, amount: cost, currency: "USD" }] } } } };
  const input = { ...data("B1"), optimization: { id: "E1", candidates: [candidate] } };
  await render(<EvolutionPage data={input} />); await clickText("Sandbox");
  const expected = cost == null ? "费用未采集 · Token Usage / Provider Cost unavailable" : `$${cost}（估算费用）`;
  expect(document.querySelector(".sandbox-core-table")?.textContent).not.toContain("费用");
  await clickText("查看高级指标");
  expect(document.querySelector('[role="dialog"]')?.textContent).toContain(expected);
  expect(document.body.textContent).not.toContain("暂未配置单价");
  await act(async () => root.render(<VersionsPage data={input} />)); await clickText("查看其他 Candidate"); await clickText("查看 Candidate 评测报告");
  expect(document.querySelector('[role="dialog"]')?.textContent).toContain(expected);
  expect(document.querySelector('[role="dialog"]')?.textContent).not.toContain("暂未配置单价");
});

it("M7 restores completed comparison on same-identity remount and rejects a different identity", async () => {
  vi.stubGlobal("fetch", vi.fn(async (_url: string, init?: RequestInit) => new Response(JSON.stringify({ answer: JSON.parse(init?.body as string).scheme_id === "baseline" ? "保留 Baseline 回答" : "保留 Production 回答", version: JSON.parse(init?.body as string).scheme_id === "baseline" ? "B1" : "P0", evidence: [] }))));
  await render(<ExperimentPage data={data("B1")} onOpenCitation={() => {}} />);
  await fill("保留同一个问题"); await act(async () => document.querySelector<HTMLButtonElement>(".query-action button")!.click());
  expect(document.body.textContent).toContain("保留 Baseline 回答");
  await act(async () => root.unmount());
  await render(<ExperimentPage data={data("B1")} onOpenCitation={() => {}} />);
  expect(document.body.textContent).toContain("保留 Baseline 回答");
  expect(document.body.textContent).toContain("保留 Production 回答");
  expect(fetch).toHaveBeenCalledTimes(2);
  expect((fetch as any).mock.calls.map((call: any[]) => JSON.parse(call[1].body).scheme_id)).toEqual(["baseline", "P0"]);
  await act(async () => root.unmount());
  await render(<ExperimentPage data={data("B2")} onOpenCitation={() => {}} />);
  expect(document.body.textContent).not.toContain("保留 Baseline 回答");
  expect(document.body.textContent).not.toContain("保留 Production 回答");
});

it("M3 clean/save, cancel, content replacement and external close reset the Drawer contract", async () => {
  const change = vi.fn();
  const drawer = (dirty: boolean, key: string, open = true) => <Drawer open={open} guardEdits editDirty={dirty} contentKey={key} title="Fixture 编辑" onOpenChange={change}><input defaultValue="草稿" /></Drawer>;
  await render(drawer(true, "Q1"));
  await act(async () => document.querySelector<HTMLButtonElement>(".drawer-head button")!.click());
  await clickText("取消");
  expect(change).not.toHaveBeenCalled(); expect(document.querySelector<HTMLInputElement>("input")?.value).toBe("草稿");
  await act(async () => root.render(drawer(false, "Q1")));
  await act(async () => document.querySelector<HTMLButtonElement>(".drawer-head button")!.click());
  expect(change).toHaveBeenCalledWith(false); expect(document.querySelector(".confirm-dialog")).toBeNull();
  await act(async () => root.render(drawer(true, "Q1")));
  await act(async () => document.querySelector<HTMLButtonElement>(".drawer-head button")!.click());
  await act(async () => root.render(drawer(false, "Q2")));
  expect(document.querySelector(".confirm-dialog")).toBeNull();
  await act(async () => root.render(drawer(true, "Q2")));
  await act(async () => document.querySelector<HTMLButtonElement>(".drawer-head button")!.click());
  await act(async () => root.render(drawer(false, "Q2", false)));
  await act(async () => root.render(drawer(false, "Q2")));
  expect(document.querySelector(".confirm-dialog")).toBeNull();
});

it("M3 saved Candidate draft becomes clean and returning an edit to saved content is clean", async () => {
  const question = { id: "Q1", question: "原问题", reference_answer: "原答案", test_category: "positive", evidence: [{ source_chunk_ids: ["C1"] }], raw: {} };
  let revision: any = { id: "REV1", status: "preview_ready", question_ids: ["Q1"], drafts: { Q1: question }, new_hash: { Q1: "old" }, before: { Q1: question }, reason: "已有原因", tags: [] };
  vi.stubGlobal("fetch", vi.fn(async (_url: string, init?: RequestInit) => { if (init?.method === "POST") { const payload = JSON.parse(init.body as string); revision = { ...revision, drafts: { Q1: { ...question, ...payload.changes.Q1 } }, new_hash: { Q1: "new" } }; } return new Response(JSON.stringify(init?.method === "POST" ? revision : [])); }));
  const dirty = vi.fn();
  await render(<CandidateWorkspace row={question} peers={[question]} revision={revision} busy={false} onRun={() => {}} onReview={async () => false} onRefresh={async () => {}} operation={{ watchRevision: () => {} } as any} onDirtyChange={dirty} />);
  expect(dirty).toHaveBeenLastCalledWith(false);
  await clickText("编辑草案");
  expect(dirty).toHaveBeenLastCalledWith(false);
  const input = document.querySelector<HTMLTextAreaElement>('textarea[aria-label="草案问题"]') || document.querySelector<HTMLTextAreaElement>(".draft-workspace textarea");
  expect(input).not.toBeNull();
  const edit = async (value: string) => act(async () => { Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")!.set!.call(input, value); input!.dispatchEvent(new Event("input", { bubbles: true })); });
  await edit("已编辑的问题"); expect(dirty).toHaveBeenLastCalledWith(true);
  await edit("原问题"); expect(dirty).toHaveBeenLastCalledWith(false);
  await edit("已编辑的问题"); await clickText("保存并校验草案");
  expect(dirty).toHaveBeenLastCalledWith(false);
});

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
  await render(<><ExecutionMetrics metrics={{ ttft_ms: null, cost_estimation: { status: "estimated", amount: 0, currency: "USD", price_snapshot: { currency: "USD", version: "fixture-price-v1" }, calls: [{ model: "fixture-model", input_tokens: 0, output_tokens: 0, amount: 0, currency: "USD" }] } }} /><ExecutionMetrics metrics={{ cost_estimation: { status: "unavailable", amount: null, reason: "billing_period_ambiguous" } }} /></>);
  expect(document.body.textContent).toContain("$0（按调用时配置估算）");
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
  const coreRows = [...document.querySelectorAll(".sandbox-core-table tbody tr")];
  expect(coreRows.map(row => row.querySelector("td")?.textContent)).toEqual(["Hard Gate", "Bad Case", "Regression", "Qualification"]);
  expect(coreRows.find(row => row.querySelector("td")?.textContent === "Hard Gate")?.lastElementChild?.textContent).toBe("11 / 11");
  expect(coreRows.find(row => row.querySelector("td")?.textContent === "Regression")?.lastElementChild?.textContent).toBe("FAIL");
  expect(coreRows.find(row => row.querySelector("td")?.textContent === "Qualification")?.lastElementChild?.textContent).toBe("FAIL");
  await act(async () => [...document.querySelectorAll("button")].find(x => x.textContent === "A / B / C / D")!.click());
  await act(async () => [...document.querySelectorAll("button")].find(x => x.textContent === "查看 D 完整报告与 Decision")!.click());
  expect(document.querySelector('[role="dialog"]')?.textContent).toContain("发布资格：不合格 · Hard Gate：通过");
  expect(document.querySelector('[role="dialog"]')?.textContent).toContain("Regression：FAIL");
});

it.each([undefined, "running", "failed"])("review R2 keeps %s Baseline at Evaluation before Agent", async status => {
  const input = { ...data("B1"), snapshots: [{ id: identity("B1").current_golden_id, status: "approved", snapshot: { question_ids: ["Q1"], questions: [{ id: "Q1", test_category: "positive" }] } }], overview: { dataset: { expected_count: 1, approved: 1 } }, evaluation: status ? { id: "B1", status } : {} };
  await render(<OverviewPage data={input} navigate={() => {}} />);
  expect(document.querySelector(".next-action a")?.getAttribute("href")).toBe("#evaluation");
  expect(document.querySelector(".next-action")?.textContent).not.toContain("运行 Optimization Agent");
});

it("review R2 an older Production does not finish a new recommendation Gate3", async () => {
  const candidate = { id: "E1-A", status: "evaluated", reasoning: { candidate_label: "A" }, release_state: { sandbox: true, qualified: true, recommended: true, round_complete: true } };
  const input = { ...data("B1"), snapshots: [{ id: identity("B1").current_golden_id, status: "approved", snapshot: { question_ids: ["Q1"], questions: [{ id: "Q1", test_category: "positive" }] } }], overview: { dataset: { expected_count: 1, approved: 1 } }, evaluation: { id: "B1", status: "completed" }, optimization: { id: "E1", baseline_run_id: "B1", candidates: [candidate], recommendation: { result: { status: "Recommended", recommended_candidate: candidate.id } } }, versions: [{ id: "P0", status: "active", provenance: "published", snapshot: { candidate_id: "E0-C" } }] };
  await render(<OverviewPage data={input} navigate={() => {}} />);
  expect(document.querySelector(".next-action h2")?.textContent).toContain("Gate 3");
  await act(async () => root.render(<VersionsPage data={input} />));
  expect(document.querySelector('[aria-label="发布阶段"]')).toBeNull();
  expect(document.querySelector(".unpublished-candidates")?.textContent).toContain("Candidate A");
  expect(document.querySelector(".unpublished-candidates")?.textContent).toContain("本轮推荐，尚未发布");
  expect(document.querySelector<HTMLButtonElement>(".release-actions button")?.disabled).toBe(false);
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
  vi.stubGlobal("fetch", vi.fn(async (url: string) => new Response(JSON.stringify((url.includes("/candidates?") || /\/questions\/[^/]+$/.test(url)) ? goldenFixture(url, rows) : url.replace("?light=true", "").endsWith("generation-runs") ? [run] : url.endsWith("/dataset") ? rows : []))));
  await render(<GovernancePage data={{ dataset: rows, generationRuns: [run] }} />);
  expect(document.querySelectorAll(".review-table tbody tr")).toHaveLength(5);
  expect(document.querySelector(".review-table tbody")?.textContent).toContain("P0 确定性阻断");
  expect(document.querySelector(".exception-summary")).toBeNull();
  await clickText("运行审计");
  expect(document.querySelector(".drawer-body")?.textContent).toContain("QC P0 · 2");
  expect(document.querySelector(".drawer-body")?.textContent).toContain("疑似伪负向 · 1");
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
  expect(document.querySelector('[aria-label="监控阶段"]')).toBeNull();
  expect(document.querySelector(".monitoring-context")?.textContent).toContain("尚未人工确认，未创建 Optimization 上下文");
  expect([...document.querySelectorAll("button")].some(button => button.textContent?.includes("启动此上下文"))).toBe(false);
  expect(document.body.textContent).not.toContain("old-A");
  await clickText("人工确认");
  expect(posts[0]).toEqual({ url: expect.stringContaining("/api/monitoring/triggers/T1/confirm"), body: { decision: "approved" } });
  expect(document.querySelector(".monitoring-context")?.textContent).toContain("待启动 Round 1");
  expect([...document.querySelectorAll<HTMLButtonElement>("button")].find(button => button.textContent === "启动此上下文 Agent · Round 1")?.disabled).toBe(false);
  await clickText("查看 Trigger 上下文");
  expect(document.querySelector('[role="dialog"]')?.textContent).toContain("Trigger：T1");
  expect(document.querySelector('[role="dialog"]')?.textContent).toContain("关联实验：E-monitor");
  expect(document.querySelector('[role="dialog"]')?.textContent).not.toContain("E-prior");
  await act(async () => document.querySelector<HTMLButtonElement>(".drawer-head button")!.click());
  await clickText("启动此上下文 Agent · Round 1");
  expect(posts[1]).toEqual({ url: expect.stringContaining("/api/experiments/run"), body: { trigger_id: "T1" } });
  expect(posts).toHaveLength(2);
  expect(document.querySelector(".monitoring-context")?.textContent).toContain("Agent 状态：completed · Round 1");
  expect([...document.querySelectorAll("button")].some(button => button.textContent?.includes("启动此上下文"))).toBe(false);
  await clickText("查看 Trigger 上下文");
  expect(document.querySelector('[role="dialog"]')?.textContent).toContain("关联实验：E-monitor");
  expect(document.querySelector('[role="dialog"]')?.textContent).toContain("Round 1");
  expect(document.querySelector('a[href="#evolution"]')).toBeNull();
});

it("review R4 selected historical Monitoring context is identified and cannot start under a new Baseline", async () => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => new Response(JSON.stringify(url.includes("/experiments/") ? { id: "E-history", baseline_run_id: "B0", status: "pending_agent", result: { round: 0 }, candidates: [] } : { triggers: [{ id: "T-history", status: "human_confirmed", optimization_run_id: "E-history" }], events: [] }))));
  await render(<VerificationPage data={{ ...data("B1"), monitoring: { triggers: [{ id: "T-history", status: "human_confirmed", optimization_run_id: "E-history" }] } }} onOpenDocument={() => {}} onOpenCitation={() => {}} />);
  await act(async () => [...document.querySelectorAll("button")].find(x => x.textContent === "Monitoring")!.click());
  await clickText("查看 Trigger 上下文");
  expect(document.querySelector('[role="dialog"]')?.textContent).toContain("Trigger：T-history");
  expect(document.querySelector('[role="dialog"]')?.textContent).toContain("关联实验：E-history");
  expect(document.querySelector('[role="dialog"]')?.textContent).toContain("Baseline：B0");
  expect(document.querySelector(".monitoring-context")?.textContent).toContain("历史上下文，只读");
  expect([...document.querySelectorAll<HTMLButtonElement>("button")].find(x => x.textContent?.includes("启动此上下文"))?.disabled).toBe(true);
  expect((fetch as any).mock.calls.every((call: any[]) => !call[1]?.method || call[1].method === "GET")).toBe(true);
});
