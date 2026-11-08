// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { StageStepper } from "./components/Primitives";
import { DataTable } from "./components/DataTable";

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
let root: ReturnType<typeof createRoot>;
afterEach(() => { act(() => root?.unmount()); document.body.innerHTML = ""; vi.restoreAllMocks(); vi.useRealTimers(); });
async function mount(node: React.ReactNode) { root = createRoot(document.body.appendChild(document.createElement("div"))); await act(async () => root.render(node)); }
it("keeps stage navigation available as a keyboard accessible button", async () => {
  const select = vi.fn();
  await mount(<StageStepper ariaLabel="实验进度" compact steps={[{label:"Sandbox",state:"current",detail:"运行中 7/50",onSelect:select}]} />);
  const button = document.querySelector(".stage-stepper button") as HTMLButtonElement;
  expect(button?.textContent).toContain("运行中 7/50");
  await act(async () => button.click());
  expect(select).toHaveBeenCalledOnce();
});
it("clips table prose to two lines while preserving actions and full hover text", async () => {
  const open = vi.fn(), text = "已保存的完整问题与证据正文".repeat(30);
  vi.useFakeTimers();
  vi.spyOn(Element.prototype,"scrollHeight","get").mockReturnValue(100);
  vi.spyOn(Element.prototype,"clientHeight","get").mockReturnValue(40);
  await mount(<div className="table-scroll"><DataTable><thead><tr><th>问题</th><th>操作</th></tr></thead><tbody><tr><td>{text}</td><td><button onClick={open}>查看</button><button>重试</button></td></tr></tbody></DataTable></div>);
  const prose = document.querySelector("td .ui-clamp") as HTMLElement;
  expect(prose.textContent).toBe(text);
  expect(prose.style.webkitLineClamp).toBe("2");
  await act(async () => prose.dispatchEvent(new MouseEvent("mouseover",{bubbles:true})));
  await act(async () => vi.advanceTimersByTime(300));
  expect(document.querySelector('[role="tooltip"]')?.textContent).toBe(text);
  await act(async () => (document.querySelector("td button") as HTMLButtonElement).click());
  expect(open).toHaveBeenCalledOnce();
  expect(document.querySelectorAll("td button")).toHaveLength(2);
});
