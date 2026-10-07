// @vitest-environment jsdom
import { goldenFixture } from "./golden-test-fixture";
import { invalidateGolden } from "./goldenCache";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { SettingsPage } from "./pages/SettingsPage";
import { GovernancePage } from "./pages/GovernancePage";
let root: ReturnType<typeof createRoot>;
afterEach(async () => { if (root) await act(async () => root.unmount()); document.body.innerHTML = ""; vi.unstubAllGlobals(); });
it("saves and reloads an isolated Config Draft, removes inactive Alpha and discards without changing baseline", async () => {
  const config = { query_rewrite: false, hybrid_search: true, hybrid_alpha: 0.5 };
  const pipeline = { config, baseline_config: null, draft_identity: { current_baseline_id: null }, config_draft: null as any, search_space: { query_rewrite: { allowed: [true, false] }, hybrid_search: { allowed: [true, false] }, hybrid_alpha: { allowed: [0.3, 0.5, 0.7] } } };
  const posts: any[] = [];
  vi.stubGlobal("fetch", vi.fn(async (_url: string, init?: RequestInit) => {
    if (init?.method === "POST") { const body = JSON.parse(init.body as string); posts.push(body); pipeline.config_draft = body.config ? { config: body.config } : null; return new Response(JSON.stringify({ config_draft: pipeline.config_draft })); }
    return new Response(JSON.stringify(pipeline));
  }));
  root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<SettingsPage data={{}} />));
  await act(async () => document.querySelector<HTMLButtonElement>('[data-parameter="query_rewrite"] button')!.click());
  await act(async () => [...document.querySelectorAll<HTMLButtonElement>('[data-parameter="hybrid_search"] button')].find(button => button.textContent === "OFF")!.click());
  expect([...document.querySelectorAll<HTMLButtonElement>('[data-parameter="hybrid_alpha"] button')].every(button => button.disabled)).toBe(true);
  await act(async () => [...document.querySelectorAll<HTMLButtonElement>("button")].find(button => button.textContent === "保存 Config Draft")!.click());
  expect(posts[0]).toEqual({ identity: pipeline.draft_identity, config: { query_rewrite: true, hybrid_search: false } });
  expect(pipeline.config).toEqual(config);
  expect(document.body.textContent).toContain("Config Draft 已保存");
  await act(async () => root.unmount()); root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<SettingsPage data={{}} />));
  expect(document.querySelector('[data-parameter="query_rewrite"] button[aria-pressed="true"]')?.textContent).toBe("ON");
  await act(async () => [...document.querySelectorAll<HTMLButtonElement>("button")].find(button => button.textContent === "放弃修改")!.click());
  expect(posts[1].config).toBeNull();
  expect(pipeline.baseline_config).toBeNull();
});
it("confirms the actual anomaly count and requests only the anomaly scope", async () => {
  const base = { stage: "candidate", review_status: "human_review_pending", probe_status: "probe_passed", qc_status: "qc_passed", test_category: "positive", evidence: [] };
  const rows = [{ ...base, id: "pass", question: "Passed" }, { ...base, id: "fail", question: "Failed", qc_status: "qc_failed" }];
  const run = { id: "G1", status: "completed", profile: { expected_count: 2 }, question_ids: rows.map(row => row.id), artifacts: {} };
  const posts: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => { if (init?.method === "POST") posts.push(url); return new Response(JSON.stringify((url.includes("/candidates?") || /\/questions\/[^/]+$/.test(url)) ? goldenFixture(url, rows) : url.endsWith('/G1') ? run : [])); }));
  root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<GovernancePage data={{ dataset: rows, generationRuns: [run] }} />));
  await act(async () => [...document.querySelectorAll<HTMLButtonElement>("button")].find(button => button.textContent === "批量重跑异常项")!.click());
  expect(document.querySelector('.confirm-dialog')?.textContent).toContain('仅处理 1 道');
  expect(posts).toHaveLength(0);
  await act(async () => document.querySelector<HTMLButtonElement>('.confirm-dialog button.primary')!.click());
  expect(posts).toEqual([expect.stringContaining('/G1/rerun-quality?anomalies_only=true')]);
});
