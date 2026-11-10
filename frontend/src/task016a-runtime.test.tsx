// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { PricePauseNotice, RuntimeSettings, pricePauseText } from "./components/RuntimeSettings";
import { OperationProvider, elapsedText, evaluationTitle } from "./operation";
import { EvaluationPage } from "./pages/EvaluationPage";
import { EvolutionPage } from "./pages/EvolutionPage";
import { displayText } from "./display";

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
let root: ReturnType<typeof createRoot>;
afterEach(() => { act(() => root?.unmount()); document.body.innerHTML = ""; vi.useRealTimers(); vi.unstubAllGlobals(); });
const response = (value: unknown) => Promise.resolve(new Response(JSON.stringify(value)));
async function mount(node: any) { root = createRoot(document.body.appendChild(document.createElement("div"))); await act(async () => root.render(node)); }
async function click(text: string) { await act(async () => [...document.querySelectorAll<HTMLButtonElement>("button")].find(button => button.textContent === text)!.click()); }
const pause = { paused: true, resume_at_toronto: "23:00", resume_at: "2026-11-04T04:00:00Z" };

it("refreshes saved pause state after the worker automatically resumes without a POST", async () => {
  vi.useFakeTimers();
  let reads = 0;
  const fetcher = vi.fn((_url:string,_init?:RequestInit) => response({off_peak_only:true,peak_now:reads++ === 0,active_pauses:reads===1 ? [{task_label:"Candidate A",price_pause:pause,target:{evaluation_id:"offline"}}] : []}));
  vi.stubGlobal("fetch",fetcher);
  await mount(<RuntimeSettings />);
  expect(document.body.textContent).toContain("已暂停，稍后自动继续");
  await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
  expect(document.body.textContent).not.toContain("已暂停，稍后自动继续");
  expect(fetcher).toHaveBeenCalledTimes(2);
  expect(fetcher.mock.calls.every(args => !args[1]?.method || args[1].method === "GET")).toBe(true);
});

it("loads and saves the shared off-peak setting with a high-price explanation", async () => {
  const fetcher = vi.fn((url: string, init?: RequestInit) => response(init?.method ? { off_peak_only: JSON.parse(String(init.body)).off_peak_only, peak_now: true } : { off_peak_only: true, peak_now: true, resume_at_toronto: "23:00" }));
  vi.stubGlobal("fetch", fetcher);
  await mount(<RuntimeSettings />);
  const input = [...document.querySelectorAll<HTMLInputElement>("input")].find(input=>input.closest("label")?.textContent?.includes("只在平价时段运行"))!;
  expect(input.checked).toBe(true);
  expect(input.disabled).toBe(false);
  expect(document.body.textContent).toContain("23:00，多伦多时间");
  await act(async () => input.click());
  expect(fetcher.mock.calls[1][0]).toContain("/api/runtime-settings");
  expect(JSON.parse(String(fetcher.mock.calls[1][1]?.body))).toEqual({ off_peak_only: false });
  expect(input.checked).toBe(false);
  expect(document.body.textContent).toContain("高峰时段运行会按高峰价计费");
});

it("requires the task-specific peak-price acknowledgement before a temporary override", async () => {
  const fetcher = vi.fn(() => response({ status: "running" })), changed = vi.fn();
  vi.stubGlobal("fetch", fetcher);
  await mount(<PricePauseNotice pause={pause} experimentId="EXP-private" onChanged={changed} />);
  expect(document.body.textContent).toContain("已暂停，稍后自动继续");
  expect(document.body.textContent).not.toContain("EXP-private");
  await click("立即运行");
  expect(fetcher).not.toHaveBeenCalled();
  expect(document.body.textContent).toContain("立即运行本任务将产生模型费用");
  await click("确认立即运行本任务");
  expect(JSON.parse(String((fetcher.mock.calls as any)[0][1].body))).toEqual({ experiment_id: "EXP-private", acknowledge_peak_price: true });
  expect(changed).toHaveBeenCalledOnce();
});

it("preserves the pause and explains a failed override without claiming the task resumed", async () => {
  const changed = vi.fn();
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ detail: "任务未获授权" }), { status: 409 })));
  await mount(<PricePauseNotice pause={pause} evaluationId="EVAL-private" onChanged={changed} />);
  await click("立即运行"); await click("确认立即运行本任务");
  expect(document.querySelector("[role=alert]")?.textContent).toContain("任务未获授权");
  expect(changed).not.toHaveBeenCalled();
  expect(document.body.textContent).toContain("已暂停，稍后自动继续");
});

it("restores friendly operation names, saved counts and the price pause after a reload", async () => {
  vi.useFakeTimers(); vi.setSystemTime(new Date("2026-11-04T02:32:05Z"));
  const run: any = { id: "EVAL-private", status: "running", created_at: "2026-11-04T02:30:00Z", config: { candidate_id: "EXP-private-R1-A" }, result: { completed: 7, total: 50, price_pause: pause } };
  vi.stubGlobal("fetch", vi.fn((url: string) => response(url.includes("/api/evaluations?") ? [run] : url.includes("/api/governance") ? [] : run)));
  await mount(<OperationProvider><span>页面</span></OperationProvider>);
  const console = document.querySelector(".ui-run")!;
  expect(console.querySelector(".ui-run-title")?.textContent).toBe("Candidate A");
  expect(console.textContent).toContain("2 分 5 秒");
  expect(console.textContent).toContain("稍后自动继续");
  expect(console.textContent).not.toMatch(/EXP-|EVAL-|Worker 未确认/);
  await act(async () => vi.advanceTimersByTimeAsync(1000));
  expect(console.textContent).toContain("7 / 50");
  run.result.price_pause = { paused: false };
  await act(async () => vi.advanceTimersByTimeAsync(1000));
  expect(console.textContent).toContain("正在运行 Golden Case");
  expect(console.textContent).not.toContain("已暂停，稍后自动继续");
});

it("shows a neutral pause on Baseline without exposing the internal schedule", async () => {
  const run = { id: "EVAL-private", status: "running", result: { completed: 7, total: 50, price_pause: pause } };
  vi.stubGlobal("fetch", vi.fn((url: string) => response(url.includes("preflight") ? { can_start: false } : run)));
  await mount(<EvaluationPage data={{ evaluation: run, badCases: [] }} />);
  expect(document.querySelector(".price-pause-notice")?.textContent).toContain("已暂停，稍后自动继续");
  expect(pricePauseText({ paused: true, resume_at: "2026-11-04T04:00:00Z" })).toBe("已暂停，稍后自动继续");
});

it("shows scheduled D as queued and keeps configuration identifiers inside technical details", async () => {
  vi.useFakeTimers();
  const experiment = { id: "EXP-private", candidates: [], result: { report_confirmation: { winner_id: "a" }, composite_schedule: { status: "scheduled", price_pause: pause }, processing_progress: { verified_configuration_id: "CONFIG-private", fixed_question_ids: ["Q01"], remaining_question_ids: ["Q02"] } } };
  vi.stubGlobal("fetch", vi.fn((url: string) => response(url.includes("/api/experiments") ? experiment : { search_space: {} })));
  await mount(<EvolutionPage data={{ evaluation: { id: "baseline", status: "completed" }, optimization: experiment }} />);
  expect(document.querySelector(".price-pause-notice")?.textContent).toContain("已暂停，稍后自动继续");
  const planning = document.querySelector('.route-planning')!;
  expect(planning.textContent).toContain("修复 1 题");
  expect(planning.textContent).toContain("已有经完整评测验证的 Candidate");
  expect(document.body.textContent).not.toContain("CONFIG-private");
  await click("进化路线");
  expect(document.body.textContent).toContain("Candidate D · 排队中");
  await click("回归与推荐");
  expect([...document.querySelectorAll("button")].some(button => button.textContent === "生成智能组合建议")).toBe(false);
});

it("keeps resumed operation language and elapsed units understandable", () => {
  expect(elapsedText(125900)).toBe("2 分 5 秒");
  expect(evaluationTitle({ config: { candidate_id: "opaque" } })).toBe("Candidate · Sandbox 试跑");
  expect(evaluationTitle({ config: { run_target: "answer_replay" } })).toBe("历史回答判分回放");
  expect(displayText("needs_human_review")).toBe("待确认");
});

it("shows all paused batch tasks by business name and forwards their exact override target", async () => {
  const tasks = [
    { task_label: "Golden 出题与质检", target: { generation_id: "GGEN-private" } },
    { task_label: "候选题修订", target: { revision_id: "REV-private" } },
    { task_label: "判分校准", target: { evaluation_id: "EVAL-private", calibration_group: "safety" } },
    { task_label: "批量语义诊断", target: { evaluation_id: "EVAL-private", diagnostic_id: "DIAG-private" } },
  ];
  const fetcher = vi.fn((_url: string, init?: RequestInit) => response(init?.method ? {} : { off_peak_only: true, active_pauses: tasks.map(task => ({ ...task, price_pause: pause })) }));
  vi.stubGlobal("fetch", fetcher);
  await mount(<RuntimeSettings />);
  expect([...document.querySelectorAll("h3")].map(node => node.textContent)).toEqual(tasks.map(task => task.task_label));
  expect(document.body.textContent).not.toMatch(/GGEN-private|REV-private|EVAL-private|DIAG-private|safety/);
  for (const task of tasks) {
    const section = [...document.querySelectorAll("section")].find(node => node.querySelector("h3")?.textContent === task.task_label)!;
    await act(async () => [...section.querySelectorAll<HTMLButtonElement>("button")].find(button => button.textContent === "立即运行")!.click());
    await act(async () => [...document.querySelectorAll<HTMLButtonElement>(".confirm-dialog button")].find(button => button.textContent === "确认立即运行本任务")!.click());
    const lastPost = fetcher.mock.calls.filter(([, init]) => init?.method === "POST").at(-1)!;
    expect(lastPost[0]).toContain("/api/runtime-settings/run-now");
    expect(JSON.parse(String(lastPost[1]?.body))).toEqual({ ...task.target, acknowledge_peak_price: true });
  }
});

it("keeps internal price diagnostics out of the business pause notice", async () => {
  const message = "价格快照暂不可用，任务已暂停；待价格信息恢复后继续。";
  expect(pricePauseText({ paused: true, message })).toBe("已暂停，稍后自动继续");
  await mount(<PricePauseNotice pause={{ paused: true, message }} target={{ generation_id: "GGEN-private" }} />);
  expect(document.querySelector(".price-pause-notice")?.textContent).toContain("已暂停，稍后自动继续");
  expect(document.body.textContent).not.toContain(message);
  expect(document.body.textContent).not.toContain("预计 未知");
});
