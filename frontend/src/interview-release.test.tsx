// @vitest-environment jsdom
import { act, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { OperationProvider } from "./operation";
import { VersionsPage } from "./pages/VersionsPage";
import { VerificationPage } from "./pages/VerificationPage";
import { AssistantPage } from "./pages/AssistantPage";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
let root: ReturnType<typeof createRoot>;
afterEach(() => { if (root) act(() => root.unmount()); document.body.innerHTML = ""; localStorage.clear(); sessionStorage.clear(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });
const render = async (node: ReactNode) => { root = createRoot(document.body.appendChild(document.createElement("div"))); await act(async () => root.render(<OperationProvider restore={false}>{node}</OperationProvider>)); };
const click = async (label: string) => { await act(async () => [...document.querySelectorAll<HTMLButtonElement>("button")].find(node => node.textContent === label)!.click()); };
const production = { id: "PROD-old-C", status: "active", provenance: "published", previous_version_id: "baseline-v1", config: { prompt_strategy: "Abstention", rerank: false }, snapshot: { candidate_id: "EXP-old-C", hard_gate_results: { passed_count: 11, total: 11 }, regression: { status: "PASS" }, evaluation_result: { qualification: { qualified: true } }, recommendation: { result: { recommended_candidate: "EXP-old-C", report_confirmation: { winner_id: "EXP-old-C" } } }, human_release: { decision: "approved", actor: "fixture-reviewer" } } };

it("centres the actual published snapshot while a newer recommendation remains unpublished", async () => {
  const candidate = { id: "EXP-new-A", reasoning: { candidate_label: "A" }, release_state: { sandbox: true, qualified: true, recommended: true, round_complete: true } };
  await render(<VersionsPage data={{ versions: [production, { id: "baseline-v1", status: "archived", config: { prompt_strategy: "Grounded", rerank: false } }], optimization: { candidates: [candidate], recommendation: { result: { recommended_candidate: candidate.id } } } }} />);
  expect(document.querySelector(".release-decision")?.textContent).toContain("Production 来源 Candidate C");
  expect(document.querySelector(".release-decision")?.textContent).toContain("11 / 11");
  expect(document.querySelector(".release-decision")?.textContent).toContain("Regression PASS");
  expect(document.querySelector(".release-decision")?.textContent).toContain("Gate 3 人工发布已确认");
  expect(document.querySelector(".unpublished-candidates")?.textContent).toContain("Candidate A");
  expect(document.querySelector(".unpublished-candidates")?.textContent).toContain("确认发布");
  expect(document.querySelector(".stage-stepper")).toBeNull();
  expect(document.querySelector(".release-checks")).toBeNull();
});

it("shows only changed parameters on the release main screen and opens full configuration in a Drawer", async () => {
  await render(<VersionsPage data={{ versions: [production, { id: "baseline-v1", status: "archived", config: { prompt_strategy: "Grounded", rerank: false } }] }} />);
  expect(document.querySelector(".release-decision")?.textContent).toContain("Grounded");
  expect(document.querySelector(".release-decision")?.textContent).toContain("Abstention");
  expect(document.querySelector(".release-decision")?.textContent).not.toContain("Rerank");
  expect(document.querySelector(".release-decision details")).toBeNull();
  await click("查看完整配置");
  expect(document.querySelector(".drawer")?.textContent).toContain("Rerank");
  expect(document.querySelector(".drawer pre")).toBeNull();
});

it("does not invent manual publication evidence for incomplete historical snapshots", async () => {
  await render(<VersionsPage data={{ versions: [{ ...production, snapshot: { candidate_id: "EXP-old-C" } }] }} />);
  expect(document.querySelector(".release-decision")?.textContent).not.toContain("Gate 3 人工发布已确认");
  expect(document.querySelector(".release-decision")?.textContent).toContain("发布审计未完整保存");
});

it("keeps answer telemetry and source IDs out of the chat until its audit Drawer opens", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ baseline: { answer: "实际完整回答", evidence: [], sources: [], version: "PROD-audit", config: { prompt_strategy: "Abstention" }, latency_ms: 130, input_tokens: 41, output_tokens: 12, source: { provider_id: "internal-provider", corpus_fingerprint: "internal-corpus" } }, model: "internal-model", mode: "live", latency_ms: 130 }))));
  await render(<AssistantPage productionVersion="PROD-audit" isReleased badCases={[]} onOpenBadCase={() => {}} onOpenCitation={() => {}} onOpenDocument={() => {}} />);
  await act(async () => document.querySelector<HTMLButtonElement>(".empty-chat button")!.click());
  expect(document.querySelector(".message-list")?.textContent).toContain("实际完整回答");
  expect(document.querySelector(".message-list")?.textContent).toContain("130 ms");
  for (const hidden of ["internal-provider", "internal-corpus", "internal-model", "未采集", "TTFT", "Judge"]) expect(document.querySelector(".message-list")?.textContent).not.toContain(hidden);
  await click("查看回答审计");
  expect(document.querySelector(".drawer")?.textContent).toContain("internal-model");
  expect(document.querySelector(".drawer")?.textContent).toContain("internal-provider");
  expect(document.querySelector(".drawer")?.textContent).toContain("Abstention");
});

it("orders verification tabs and reduces Monitoring to question, state, judgement and actions", async () => {
  const monitoring = { events: [{ id: "MON-internal", question: "新问题", answer: "实际回答", determinable: false, source: { production_version_id: "PROD-source" }, metrics: { latency_ms: 33 } }], triggers: [] };
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(monitoring))));
  await render(<VerificationPage data={{ monitoring }} onOpenCitation={() => {}} onOpenDocument={() => {}} />);
  expect([...document.querySelectorAll(".tabs > button")].map(node => node.textContent)).toEqual(["问答验证", "方案对比", "Monitoring"]);
  await click("Monitoring");
  expect([...document.querySelectorAll(".monitoring-table th")].map(node => node.textContent)).toEqual(["问题", "当前状态", "人工判断", "操作"]);
  expect(document.querySelector(".monitoring-table")?.textContent).not.toContain("33 ms");
  expect(document.querySelector(".stage-stepper")).toBeNull();
  await act(async () => document.querySelector<HTMLButtonElement>(".monitoring-table tbody .text-button")!.click());
  expect(document.querySelector(".drawer")?.textContent).toContain("PROD-source");
  expect(document.querySelector(".drawer")?.textContent).toContain("33 ms");
});

it("requires human judgement and confirmation before starting only the linked Monitoring context", async () => {
  let assessed = false, confirmed = false, started = false;
  const posts: { url: string; body: any }[] = [];
  const monitoring = () => ({ events: [{ id: "M1", question: "人工发现的问题", determinable: assessed, bad_case: assessed }], triggers: assessed ? [{ id: "T1", event_id: "M1", reason: "人工 Bad Case", status: confirmed ? "human_confirmed" : "pending_human_confirm", optimization_run_id: confirmed ? "EXP-same" : null }] : [] });
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === "POST") { posts.push({ url, body: JSON.parse(String(init.body)) }); if (url.endsWith("/assessment")) assessed = true; if (url.endsWith("/confirm")) confirmed = true; if (url.endsWith("/experiments/run")) started = true; }
    const value = url.endsWith("/monitoring") ? monitoring() : url.includes("/experiments/") ? { id: "EXP-same", baseline_run_id: "B1", status: started ? "completed" : "pending_agent", result: { round: started ? 1 : 0 }, candidates: started ? [{ id: "A" }] : [] } : {};
    return new Response(JSON.stringify(value));
  }));
  await render(<VerificationPage data={{ workspace: { current_baseline_id: "B1" }, monitoring: monitoring(), optimization: { id: "EXP-prior", candidates: [{ id: "prior-A" }] } }} onOpenCitation={() => {}} onOpenDocument={() => {}} />);
  await click("Monitoring");
  expect(posts).toHaveLength(0);
  await click("Bad Case");
  expect(posts[0]).toEqual({ url: expect.stringContaining("/api/monitoring/events/M1/assessment"), body: { bad_case: true, severity: "ordinary" } });
  await click("人工确认");
  expect(posts).toHaveLength(2);
  expect(posts[1].body).toEqual({ decision: "approved" });
  expect(document.querySelector(".monitoring-context")?.textContent).not.toContain("EXP-same");
  await click("启动此上下文 Agent · Round 1");
  expect(posts[2]).toEqual({ url: expect.stringContaining("/api/experiments/run"), body: { trigger_id: "T1" } });
  await click("查看 Trigger 上下文");
  expect(document.querySelector(".drawer")?.textContent).toContain("EXP-same");
  expect(document.querySelector(".drawer")?.textContent).not.toContain("EXP-prior");
});
