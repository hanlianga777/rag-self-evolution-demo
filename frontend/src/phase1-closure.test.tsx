// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { CustomSelect, TruncatedText } from "./components/Primitives";
import { ExperimentPage } from "./pages/ExperimentPage";

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
let root: ReturnType<typeof createRoot>;
afterEach(() => { if (root) act(() => root.unmount()); document.body.innerHTML = ""; vi.restoreAllMocks(); vi.useRealTimers(); sessionStorage.clear(); vi.unstubAllGlobals(); });
it("closes Select on outside pointer without requiring focus transfer", async () => {
  root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<CustomSelect ariaLabel="Candidate" value="a" options={[{ value: "a", label: "A" }]} onChange={() => {}} />));
  await act(async () => (document.querySelector('[role="combobox"]') as HTMLElement).click());
  await act(async () => document.body.dispatchEvent(new Event("pointerdown", { bubbles: true })));
  expect(document.querySelector('[role="listbox"]')).toBeNull();
});
it("long text never duplicates through persistent inline expansion", async () => {
  root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<TruncatedText>完整原因</TruncatedText>));
  expect(document.querySelector("details")).toBeNull();
  expect(document.querySelector(".ui-clamp")?.textContent).toBe("完整原因");
  expect(document.querySelector('[tabindex="0"]')).toBeNull();
});
it("shows saved parameter diff before any provider call and restores question", async () => {
  vi.stubGlobal("fetch", vi.fn());
  const data = { evaluation: { id: "eval", config: { prompt_strategy: "Grounded" } }, versions: [{ id: "p1", status: "active", provenance: "published", previous_version_id: "baseline-v1", config: { prompt_strategy: "Abstention" } }, { id: "baseline-v1", provenance: "bootstrap", config: { prompt_strategy: "Grounded" } }] };
  root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<ExperimentPage data={data} onOpenCitation={() => {}} />));
  expect(document.body.textContent).toContain("有据生成");
  expect(document.body.textContent).toContain("谨慎拒答");
  expect(document.body.textContent).not.toContain("上一 线上版本");
  const textarea = document.querySelector("textarea")!;
  await act(async () => { Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")!.set!.call(textarea, "保留的问题"); textarea.dispatchEvent(new Event("input", { bubbles: true })); });
  await act(async () => root.unmount());
  root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<ExperimentPage data={data} onOpenCitation={() => {}} />));
  expect(document.querySelector("textarea")!.value).toBe("保留的问题");
  expect(fetch).not.toHaveBeenCalled();
});
it("ignores a corrupt cached answer and blocks comparison without a valid formal Baseline", async () => {
  sessionStorage.setItem("rag-qa-compare", JSON.stringify({ version: 1, state: { left: { result: { answer: 42 } }, question: [] } }));
  vi.stubGlobal("fetch", vi.fn());
  const data = { evaluation: { config: { prompt_strategy: "Grounded" } }, optimization: { candidates: [{ id: "c", config: { prompt_strategy: "Abstention" }, reasoning: { candidate_label: "C" }, result: { qualification: { qualified: true } } }] }, versions: [{ id: "p", status: "active", provenance: "published", config: { prompt_strategy: "Abstention" }, snapshot: { candidate_id: "c" } }] };
  root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<ExperimentPage data={data} onOpenCitation={() => {}} />));
  expect(document.querySelector("textarea")).toBeNull();
  expect(document.querySelector(".experiment-results")).toBeNull();
  expect(document.querySelector(".empty-state")?.textContent).toContain("还没有可用于对比的有效 Baseline");
  expect(document.querySelector('a[href="#evaluation"]')).not.toBeNull();
  expect(fetch).not.toHaveBeenCalled();
});
it("opens long text on focus, permits scrolling when pinned and closes on Escape", async () => {
  root = createRoot(document.body.appendChild(document.createElement("div")));
  vi.useFakeTimers();
  vi.spyOn(Element.prototype,"scrollHeight","get").mockReturnValue(100);
  vi.spyOn(Element.prototype,"clientHeight","get").mockReturnValue(20);
  await act(async () => root.render(<TruncatedText>完整长文说明</TruncatedText>));
  const target = document.querySelector('[tabindex="0"]') as HTMLElement;
  Object.defineProperty(target,"scrollHeight",{value:100});
  Object.defineProperty(target,"clientHeight",{value:20});
  await act(async () => {target.focus();vi.advanceTimersByTime(1);});
  expect(document.querySelector('[role="tooltip"]')?.textContent).toContain("完整长文说明");
  await act(async () => target.click());
  await act(async () => document.querySelector('[role="tooltip"]')!.dispatchEvent(new Event("scroll",{bubbles:true})));
  expect(document.querySelector('[role="tooltip"]')).not.toBeNull();
  await act(async () => document.dispatchEvent(new KeyboardEvent("keydown",{key:"Escape"})));
  await act(async () => target.blur());
  expect(document.querySelector('[role="tooltip"]')).toBeNull();
});
