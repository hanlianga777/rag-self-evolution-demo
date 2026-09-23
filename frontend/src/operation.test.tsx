// @vitest-environment jsdom
import { act, useState } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { OperationProvider, useOperation } from "./operation";
import { SettingsPage } from "./pages/SettingsPage";

// React's DOM act() needs this flag when tests dispatch real button clicks.
(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
afterEach(() => { document.body.innerHTML = ""; vi.restoreAllMocks(); vi.unstubAllGlobals(); });

it("shows an actual pending action and keeps its failure until dismissed", async () => {
  let reject!: (reason: Error) => void;
  const pending = new Promise<void>((_, fail) => { reject = fail; });
  function Harness() { const operation = useOperation(); return <button onClick={() => void operation.run("保存人工判定", () => pending).catch(() => {})}>执行</button>; }
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => { root.render(<OperationProvider restore={false}><Harness /></OperationProvider>); });
  await act(async () => { document.querySelector("button")!.click(); });
  expect(document.body.textContent).toContain("保存人工判定");
  expect(document.querySelector("[role=status]")?.textContent).toContain("运行中");
  await act(async () => reject(new Error("SQLite detail")));
  expect(document.querySelector("[role=alert]")?.textContent).toContain("运行失败");
  expect(document.body.textContent).not.toContain("SQLite detail");
  await act(async () => document.querySelector<HTMLButtonElement>("button[aria-label='查看错误详情']")!.click());
  expect(document.body.textContent).toContain("SQLite detail");
  await act(async () => root.unmount());
});

it("restores persisted Generation progress after mounting", async () => {
  const running = { id: "GGEN-1", status: "generating", artifacts: { hard_validation: { progress: { stage: "generating", completed_slots: 8, total_slots: 20, slot: "Q08", attempt: 1 } } } };
  vi.stubGlobal("fetch", vi.fn((url: string) => Promise.resolve(new Response(JSON.stringify(url.endsWith("generation-runs") ? [running] : url.endsWith("evaluations") ? [] : running), { status: 200 }))));
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => { root.render(<OperationProvider><span>页面</span></OperationProvider>); });
  expect(document.body.textContent).toContain("Q08");
  expect(document.body.textContent).toContain("8 / 20");
  expect(document.body.textContent).toContain("40%");
  await act(async () => root.unmount());
});

it("uses persisted evaluation cases for progress and falls back to the long run", async () => {
  const evaluation = { id: "EVAL-1", status: "running", dataset_snapshot_json: JSON.stringify({ question_ids: ["Q1", "Q2", "Q3"] }), cases: [{ question_id: "Q1" }] };
  vi.stubGlobal("fetch", vi.fn((url: string) => Promise.resolve(new Response(JSON.stringify(url.endsWith("/api/evaluations") ? [evaluation] : url.endsWith("EVAL-1") ? evaluation : []), { status: 200 }))));
  let finish!: () => void;
  function Harness() { const operation = useOperation(); finish = () => operation.succeed(operation.start("短操作")); return <button onClick={finish}>执行短操作</button>; }
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<OperationProvider><Harness /></OperationProvider>));
  await act(async () => await new Promise(resolve => setTimeout(resolve, 1100)));
  expect(document.body.textContent).toContain("1 / 3");
  await act(async () => document.querySelector("button")!.click());
  expect(document.body.textContent).toContain("✓ 完成");
  await act(async () => await new Promise(resolve => setTimeout(resolve, 760)));
  expect(document.body.textContent).toContain("1 / 3");
  await act(async () => root.unmount());
});

it("keeps a running operation visible while navigating without exposing reasoning", async () => {
  const pending = new Promise<void>(() => {});
  function Harness() {
    const operation = useOperation();
    const [page, setPage] = useState("概览");
    return <><span>{page}</span><button onClick={() => void operation.run("验证 Provider", () => pending)}>验证</button><button onClick={() => setPage("知识库")}>知识库</button></>;
  }
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<OperationProvider restore={false}><Harness /></OperationProvider>));
  await act(async () => document.querySelectorAll("button")[0].click());
  await act(async () => document.querySelectorAll("button")[1].click());
  expect(document.body.textContent).toContain("知识库");
  expect(document.body.textContent).toContain("验证 Provider");
  expect(document.querySelector(".operation-console progress:not([value])")).not.toBeNull();
  expect(document.body.textContent).not.toMatch(/思考过程|推理链|已完成 50%/);
  await act(async () => root.unmount());
});

it("does not report a failed Provider probe as a successful operation", async () => {
  vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(new Response(JSON.stringify({ mode: "live", status: "Unavailable", probe: "failed", last_probe: { reason: "连接失败" } }), { status: 200 }))));
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<OperationProvider restore={false}><SettingsPage data={{ readiness: { mode: "live", status: "Configured (Unverified)" } }} /></OperationProvider>));
  await act(async () => document.querySelector<HTMLButtonElement>(".settings-page button.secondary")!.click());
  expect(document.querySelector(".operation-console[role=alert]")?.textContent).toContain("运行失败");
  expect(document.body.textContent).toContain("验证失败：连接失败");
  await act(async () => root.unmount());
});
