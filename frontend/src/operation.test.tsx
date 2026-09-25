// @vitest-environment jsdom
import { act, useState } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { OperationProvider, useOperation } from "./operation";
import { Drawer } from "./components/Dialog";
import { SettingsPage } from "./pages/SettingsPage";

// React's DOM act() needs this flag when tests dispatch real button clicks.
(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
afterEach(() => { document.body.innerHTML = ""; vi.restoreAllMocks(); vi.unstubAllGlobals(); });

it("keeps the operation controls inside an open modal drawer", async () => {
  function Harness() {
    const operation = useOperation();
    const [open, setOpen] = useState(false);
    return <><button onClick={() => setOpen(true)}>打开审核</button><Drawer open={open} onOpenChange={setOpen} title="候选题审核"><button onClick={() => operation.fail(operation.start("局部修订"), new Error("校验失败"))}>触发失败</button></Drawer></>;
  }
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<OperationProvider restore={false}><Harness /></OperationProvider>));
  await act(async () => document.querySelector<HTMLButtonElement>("button")!.click());
  await act(async () => [...document.querySelectorAll<HTMLButtonElement>("button")].find(button => button.textContent === "触发失败")!.click());
  const dialog = document.querySelector("[role=dialog]")!;
  expect(dialog.contains(document.querySelector(".operation-console"))).toBe(true);
  await act(async () => document.querySelector<HTMLButtonElement>("[aria-label='查看错误详情']")!.click());
  expect(dialog.textContent).toContain("Operation ID");
  await act(async () => document.querySelector<HTMLButtonElement>("[aria-label='关闭运行状态']")!.click());
  expect(document.querySelector(".operation-console")).toBeNull();
  expect(document.querySelector("[role=dialog]")).not.toBeNull();
  await act(async () => root.unmount());
});

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
  expect(document.body.textContent).toContain("SQLite detail");
  await act(async () => document.querySelector<HTMLButtonElement>("button[aria-label='查看错误详情']")!.click());
  expect(document.body.textContent).toContain("SQLite detail");
  await act(async () => root.unmount());
});

it("keeps Generation out of the shared bar while restoring persisted evaluation progress", async () => {
  const running = { id: "GGEN-1", status: "generating", artifacts: { hard_validation: { progress: { stage: "generating", completed_slots: 8, total_slots: 20, slot: "Q08", attempt: 1 } } } };
  vi.stubGlobal("fetch", vi.fn((url: string) => Promise.resolve(new Response(JSON.stringify(url.endsWith("generation-runs") ? [running] : url.endsWith("evaluations") ? [] : running), { status: 200 }))));
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => { root.render(<OperationProvider><span>页面</span></OperationProvider>); });
  expect(document.querySelector(".operation-console")).toBeNull();
  await act(async () => root.unmount());
});

it("uses persisted evaluation cases for progress while short operations complete", async () => {
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
  await act(async () => await new Promise(resolve => setTimeout(resolve, 3200)));
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
  expect(document.querySelector(".operation-stack")).not.toBeNull();
  expect(document.body.textContent).not.toMatch(/思考过程|推理链|已完成 50%/);
  await act(async () => root.unmount());
});

it("shows up to three concurrent operations and closing one does not stop its tracking", async () => {
  let settle!: () => void;
  function Harness() {
    const operation = useOperation();
    settle = () => operation.succeed("first");
    return <button onClick={() => ["first", "second", "third", "fourth"].forEach(id => operation.start(id, { id }))}>开始</button>;
  }
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<OperationProvider restore={false}><Harness /></OperationProvider>));
  await act(async () => document.querySelector("button")!.click());
  expect(document.querySelectorAll(".operation-console")).toHaveLength(3);
  await act(async () => document.querySelector<HTMLButtonElement>("[aria-label='关闭运行状态']")!.click());
  expect(document.querySelectorAll(".operation-console")).toHaveLength(3);
  expect(document.querySelector(".operation-stack")?.textContent).not.toContain("second");
  await act(async () => settle());
  expect(document.querySelector(".operation-stack")?.textContent).toContain("✓ 完成");
  await act(async () => root.unmount());
});

it("keeps polling a persisted evaluation after its running bar is closed", async () => {
  const evaluation = { id: "EVAL-live", status: "running", dataset_snapshot_json: JSON.stringify({ question_ids: ["Q1"] }), cases: [] };
  const fetcher = vi.fn((url: string) => Promise.resolve(new Response(JSON.stringify(url.endsWith("/api/evaluations") ? [evaluation] : evaluation), { status: 200 })));
  vi.stubGlobal("fetch", fetcher);
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<OperationProvider><span>页面</span></OperationProvider>));
  await act(async () => document.querySelector<HTMLButtonElement>("[aria-label='关闭运行状态']")!.click());
  const before = fetcher.mock.calls.length;
  await act(async () => await new Promise(resolve => setTimeout(resolve, 1150)));
  expect(document.querySelector(".operation-stack")).toBeNull();
  expect(fetcher.mock.calls.length).toBeGreaterThan(before);
  await act(async () => root.unmount());
});

it("stops the elapsed clock when a short operation completes", async () => {
  let finish!: () => void;
  function Harness() { const operation = useOperation(); return <button onClick={() => { const id = operation.start("短任务"); finish = () => operation.succeed(id); }}>开始</button>; }
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<OperationProvider restore={false}><Harness /></OperationProvider>));
  await act(async () => document.querySelector("button")!.click());
  await act(async () => await new Promise(resolve => setTimeout(resolve, 250)));
  await act(async () => finish());
  const completed = document.querySelector(".operation-console")?.textContent;
  await act(async () => await new Promise(resolve => setTimeout(resolve, 300)));
  expect(document.querySelector(".operation-console")?.textContent).toBe(completed);
  await act(async () => root.unmount());
});

it("reopens a dismissed running bar if that operation later fails", async () => {
  let fail!: () => void;
  function Harness() { const operation = useOperation(); return <button onClick={() => { const id = operation.start("后台任务"); fail = () => operation.fail(id, new Error("失败详情")); }}>开始</button>; }
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<OperationProvider restore={false}><Harness /></OperationProvider>));
  await act(async () => document.querySelector("button")!.click());
  await act(async () => document.querySelector<HTMLButtonElement>("[aria-label='关闭运行状态']")!.click());
  expect(document.querySelector(".operation-stack")).toBeNull();
  await act(async () => fail());
  expect(document.querySelector(".operation-console[role=alert]")?.textContent).toContain("运行失败");
  await act(async () => root.unmount());
});

it("shows the persisted QC stage without an invented percentage for one Revision", async () => {
  const run = { id: "REV-q15", status: "qc", stage: "qc", question_ids: ["Q15"], progress: { current: 1, total: 1 } };
  vi.stubGlobal("fetch", vi.fn((url: string) => Promise.resolve(new Response(JSON.stringify(url.endsWith("/api/evaluations") ? [] : url.endsWith("/api/governance/revisions") ? [run] : run), { status: 200 }))));
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<OperationProvider><span>页面</span></OperationProvider>));
  await act(async () => await new Promise(resolve => setTimeout(resolve, 1100)));
  const card = document.querySelector(".operation-console")!;
  expect(card.textContent).toContain("QC");
  expect(card.textContent).not.toMatch(/\d+%/);
  expect(card.textContent).not.toContain("1 / 1");
  expect(card.querySelector("progress:not([value])")).not.toBeNull();
  await act(async () => root.unmount());
});

it("uses real counts for paired Revision and exposes failed details before removing its card", async () => {
  let run: any = { id: "REV-pair", status: "qc", stage: "qc", question_ids: ["Q1", "Q9"], progress: { current: 1, total: 2 } };
  vi.stubGlobal("fetch", vi.fn((url: string) => Promise.resolve(new Response(JSON.stringify(url.endsWith("/api/evaluations") ? [] : url.endsWith("/api/governance/revisions") ? [run] : run), { status: 200 }))));
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<OperationProvider><span>页面</span></OperationProvider>));
  await act(async () => await new Promise(resolve => setTimeout(resolve, 1100)));
  expect(document.querySelector(".operation-console")?.textContent).toContain("1 / 2");
  run = { ...run, status: "failed_quality", failed_stage: "qc", error: "DeepSeek 请求超时，请重试", error_detail: "The read operation timed out", runtime_attempts: [{ stage: "qc", attempt: 2, model: "deepseek-test" }] };
  await act(async () => await new Promise(resolve => setTimeout(resolve, 1100)));
  const card = document.querySelector(".operation-console[role=alert]")!;
  expect(card.textContent).toContain("DeepSeek 请求超时，请重试");
  const detail = card.querySelector<HTMLButtonElement>("[aria-label='查看错误详情']")!;
  await act(async () => detail.click());
  expect(detail.getAttribute("aria-expanded")).toBe("true");
  expect(card.textContent).toContain("The read operation timed out");
  expect(card.textContent).toContain("REV-pair");
  await act(async () => card.querySelector<HTMLButtonElement>("[aria-label='关闭运行状态']")!.click());
  expect(document.querySelector(".operation-console[role=alert]")).toBeNull();
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
