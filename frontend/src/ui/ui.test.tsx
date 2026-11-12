// @vitest-environment jsdom
import { act, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { ClampText, RunProgressPanel, StatTransition, StatusBadge, QuestionBadge, ParamChip, computeFloatPosition, formatDuration } from "./index";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

let root: Root;
let host: HTMLDivElement;
beforeEach(() => { vi.useFakeTimers(); host = document.body.appendChild(document.createElement("div")); root = createRoot(host); });
afterEach(async () => { await act(async () => root.unmount()); document.body.innerHTML = ""; vi.useRealTimers(); vi.restoreAllMocks(); });

const render = async (node: ReactNode) => { await act(async () => root.render(node)); };

/** jsdom 不做排版：用 scrollHeight / clientHeight 模拟"文字被截断"。 */
function fakeOverflow(overflow: boolean) {
  vi.spyOn(Element.prototype, "scrollHeight", "get").mockImplementation(function (this: Element) { return this.classList.contains("ui-clamp") && overflow ? 120 : 40; });
  vi.spyOn(Element.prototype, "clientHeight", "get").mockImplementation(function () { return 40; });
}

it("ClampText: not truncated → no hover popover, not focusable", async () => {
  fakeOverflow(false);
  await render(<ClampText text="短文本" lines={2} />);
  const clamp = host.querySelector(".ui-clamp") as HTMLElement;
  expect(clamp.dataset.truncated).toBe("false");
  expect(clamp.getAttribute("tabindex")).toBeNull();
  await act(async () => { clamp.dispatchEvent(new MouseEvent("mouseover", { bubbles: true })); vi.advanceTimersByTime(400); });
  expect(document.querySelector(".ui-float")).toBeNull();
});

it("ClampText: truncated → hover opens after delay, leave closes after grace", async () => {
  fakeOverflow(true);
  await render(<ClampText text={"很长的文字".repeat(40)} lines={2} />);
  const clamp = host.querySelector(".ui-clamp") as HTMLElement;
  expect(clamp.dataset.truncated).toBe("true");
  expect(clamp.style.webkitLineClamp).toBe("2");
  await act(async () => { clamp.dispatchEvent(new MouseEvent("mouseover", { bubbles: true })); vi.advanceTimersByTime(100); });
  expect(document.querySelector(".ui-float")).toBeNull();
  await act(async () => { vi.advanceTimersByTime(200); });
  expect(document.querySelector(".ui-float.dark")?.textContent).toContain("很长的文字");
  await act(async () => { clamp.dispatchEvent(new MouseEvent("mouseout", { bubbles: true })); vi.advanceTimersByTime(200); });
  expect(document.querySelector(".ui-float")).toBeNull();
});

it("ClampText: click pins, Escape closes; keyboard focus opens", async () => {
  fakeOverflow(true);
  await render(<ClampText text={"长".repeat(300)} lines={3} />);
  const clamp = host.querySelector(".ui-clamp") as HTMLElement;
  await act(async () => { clamp.click(); });
  expect(document.querySelector(".ui-float.pinned")).not.toBeNull();
  await act(async () => { clamp.dispatchEvent(new MouseEvent("mouseout", { bubbles: true })); vi.advanceTimersByTime(400); });
  expect(document.querySelector(".ui-float.pinned")).not.toBeNull();
  await act(async () => { document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" })); });
  expect(document.querySelector(".ui-float")).toBeNull();
  await act(async () => { clamp.focus(); vi.advanceTimersByTime(10); });
  expect(document.querySelector(".ui-float")).not.toBeNull();
});

it("StatTransition marks the better value and computes delta", async () => {
  await render(<><StatTransition from={44} to={48} delta deltaUnit="题" /><StatTransition from={42.2} to={36.7} unit="秒" better="lower" digits={1} delta /></>);
  const [a, b] = Array.from(host.querySelectorAll(".ui-transition"));
  expect(a.querySelector(".to")?.classList.contains("better")).toBe(true);
  expect(a.querySelector(".ui-delta")?.textContent).toBe("+4 题");
  expect(b.querySelector(".ui-delta")?.textContent).toBe("−5.5 秒");
  expect(b.querySelector(".ui-delta")?.classList.contains("good")).toBe(true);
});

it("StatusBadge keeps qualified green and recommended navy", async () => {
  await render(<><StatusBadge kind="qualified" /><StatusBadge kind="recommended" /><StatusBadge kind="failed" /></>);
  const badges = host.querySelectorAll(".ui-status");
  expect(badges[0].className).toContain("good");
  expect(badges[1].className).toContain("navy");
  expect(badges[2].className).toContain("bad");
});

it("QuestionBadge shows the question on hover and focus", async () => {
  await render(<QuestionBadge id="Q04" tone="fixed" question="KIRA B 50 准备停用三个月" />);
  const trigger = host.querySelector(".ui-hover-trigger") as HTMLElement;
  await act(async () => { trigger.dispatchEvent(new MouseEvent("mouseover", { bubbles: true })); vi.advanceTimersByTime(200); });
  expect(document.querySelector(".ui-float.dark")?.textContent).toContain("KIRA B 50");
});

it("ParamChip renders from → to and key marker", async () => {
  await render(<ParamChip label="Top-K" from={4} to={6} keyParam />);
  expect(host.textContent).toContain("Top-K 4 → 6本题关键");
});

it("RunProgressPanel: progress, button states, stop confirm, minimize", async () => {
  const onStop = vi.fn(), onContinue = vi.fn();
  await render(<RunProgressPanel title="Round 2 · Candidate A" status="running" current={41} total={50} elapsedMs={754000} onStop={onStop} onContinue={onContinue} />);
  expect(host.querySelector(".ui-run-progress")?.textContent).toContain("41 / 50 题");
  expect(host.querySelector(".ui-run-progress")?.textContent).toContain("82%");
  expect((host.querySelector(".ui-run-bar > i") as HTMLElement).style.width).toBe("82%");
  const [go, stop] = Array.from(host.querySelectorAll(".ui-run-actions button")) as HTMLButtonElement[];
  expect(go.disabled).toBe(true);
  expect(stop.disabled).toBe(false);
  expect(host.textContent).not.toMatch(/高峰|平价|Worker|EXP-/);
  await act(async () => stop.click());
  expect(host.querySelector(".ui-run-confirm")).not.toBeNull();
  await act(async () => (Array.from(host.querySelectorAll(".ui-run-confirm button")).find(b => b.textContent === "确认停止") as HTMLButtonElement).click());
  expect(onStop).toHaveBeenCalledTimes(1);
  await act(async () => (host.querySelector(".ui-run-min") as HTMLButtonElement).click());
  expect(host.querySelector(".ui-run-pill")?.textContent).toContain("41 / 50");
});

it("RunProgressPanel: waiting cannot continue; stopped can continue", async () => {
  const onContinue = vi.fn();
  await render(<RunProgressPanel title="Candidate D" status="waiting" current={10} total={50} onContinue={onContinue} onStop={() => {}} />);
  expect(host.textContent).toContain("等待中");
  expect(host.textContent).toContain("稍后自动继续");
  expect((host.querySelector(".ui-run-actions button.go") as HTMLButtonElement).disabled).toBe(true);
  await render(<RunProgressPanel title="Candidate D" status="stopped" current={10} total={50} onContinue={onContinue} onStop={() => {}} />);
  await act(async () => (host.querySelector(".ui-run-actions button.go") as HTMLButtonElement).click());
  expect(onContinue).toHaveBeenCalledTimes(1);
});

it("computeFloatPosition flips above and stays inside the viewport", () => {
  const anchor = { top: 700, bottom: 720, left: 1300, right: 1340, width: 40, height: 20, x: 1300, y: 700, toJSON() { return {}; } } as DOMRect;
  const pos = computeFloatPosition(anchor, { width: 400, height: 200 }, { width: 1440, height: 800 });
  expect(pos.placement).toBe("above");
  expect(pos.left).toBe(1440 - 12 - 400);
  expect(formatDuration(754000)).toBe("12 分 34 秒");
});
