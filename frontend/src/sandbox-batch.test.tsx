// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { OperationProvider, useOperation } from "./operation";

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
let root: ReturnType<typeof createRoot>;
afterEach(() => { if (root) act(() => root.unmount()); vi.useRealTimers(); vi.unstubAllGlobals(); document.body.innerHTML = ""; });
async function mount() {
  function Harness() { const o = useOperation(); return <button onClick={() => void o.runCandidateBatch({ experimentId: "EXP", baselineId: "E1", round: 1, candidateIds: ["A", "B", "C"] }).catch(() => {})}>执行本轮</button>; }
  root = createRoot(document.body.appendChild(document.createElement("div"))); await act(async () => root.render(<OperationProvider restore={false}><Harness /></OperationProvider>));
}

it("serializes only generated candidates, keeps failure and ignores a repeated click", async () => {
  vi.useFakeTimers(); const posted: string[] = [], states: Record<string, string> = { A: "generated", B: "generated", C: "evaluated" };
  const fetcher = vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith("workspace")) return new Response(JSON.stringify({ current_baseline_id: "E1" }));
    if (url.endsWith("/experiments/EXP")) return new Response(JSON.stringify({ id: "EXP", baseline_run_id: "E1", evaluation_budget: { used: posted.length, max: 12, reserved_for_d: 1 }, result: {}, candidates: Object.entries(states).map(([id, status]) => ({ id, status, reasoning: { round: 1, candidate_label: id } })) }));
    if (init?.method === "POST") { const id = url.split("/").at(-2)!; posted.push(id); states[id] = "running"; return new Response(JSON.stringify({ id: `RUN-${id}` })); }
    const id = url.split("RUN-")[1]; states[id] = id === "A" ? "failed" : "evaluated";
    return new Response(JSON.stringify({ id: `RUN-${id}`, status: id === "A" ? "failed" : "completed", error_message: id === "A" ? "Stub failed" : undefined, cases: [] }));
  }); vi.stubGlobal("fetch", fetcher); await mount();
  await act(async () => { document.querySelector("button")!.click(); document.querySelector("button")!.click(); });
  await act(async () => { await vi.advanceTimersByTimeAsync(2500); });
  expect(posted).toEqual(["A", "B"]);
  expect(states).toEqual({ A: "failed", B: "evaluated", C: "evaluated" });
  expect(document.body.textContent).toContain("运行失败");
  expect(fetcher.mock.calls.filter(([, init]) => init?.method === "POST").every(([url]) => url.includes("/candidates/"))).toBe(true);
});

it.each(["identity", "gate2", "budget"])("stops before a paid start when %s blocks it", async reason => {
  const fetcher = vi.fn(async (url: string) => new Response(JSON.stringify(url.endsWith("workspace") ? { current_baseline_id: reason === "identity" ? "E2" : "E1" } : { id: "EXP", baseline_run_id: "E1", evaluation_budget: { used: reason === "budget" ? 11 : 0, max: 12, reserved_for_d: 1 }, result: reason === "gate2" ? { report_confirmation: {} } : {}, candidates: [{ id: "A", status: "generated", reasoning: { round: 1, candidate_label: "A" } }] })));
  vi.stubGlobal("fetch", fetcher); await mount(); await act(async () => document.querySelector("button")!.click());
  expect(fetcher.mock.calls.every(call => (call as any)[1]?.method !== "POST")).toBe(true);
  expect(document.body.textContent).toContain("运行失败");
});

it("requires another explicit click after a server interruption", async () => {
  const posted: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith("workspace")) return new Response(JSON.stringify({ current_baseline_id: "E1" }));
    if (url.endsWith("/experiments/EXP")) return new Response(JSON.stringify({ baseline_run_id: "E1", evaluation_budget: { used: posted.length, max: 12, reserved_for_d: 1 }, result: {}, candidates: ["A", "B", "C"].map(id => ({ id, status: id === "A" && posted.length ? "failed" : "generated", reasoning: { round: 1, candidate_label: id }, result: id === "A" && posted.length ? { interrupted: true } : {} })) }));
    if (init?.method === "POST") { const id = url.split("/").at(-2)!; posted.push(id); return new Response(JSON.stringify({ id: `RUN-${id}` })); }
    return new Response(JSON.stringify({ status: "failed", error_message: "Worker interrupted" }));
  }));
  await mount(); await act(async () => document.querySelector("button")!.click());
  expect(posted).toEqual(["A"]);
  expect(document.body.textContent).toContain("重启");
});
