// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { CustomSelect, ExpandableText } from "./components/Primitives";
import { ExperimentPage } from "./pages/ExperimentPage";

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
let root: ReturnType<typeof createRoot>;
afterEach(() => { if (root) act(() => root.unmount()); document.body.innerHTML = ""; sessionStorage.clear(); vi.unstubAllGlobals(); });
it("closes Select on outside pointer without requiring focus transfer", async () => {
  root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<CustomSelect ariaLabel="方案" value="a" options={[{ value: "a", label: "A" }]} onChange={() => {}} />));
  await act(async () => (document.querySelector('[role="combobox"]') as HTMLElement).click());
  await act(async () => document.body.dispatchEvent(new Event("pointerdown", { bubbles: true })));
  expect(document.querySelector('[role="listbox"]')).toBeNull();
});
it("long text never duplicates through persistent inline expansion", async () => {
  root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<ExpandableText label="原因">完整原因</ExpandableText>));
  expect(document.querySelector("details")).toBeNull();
  expect(document.querySelector('[tabindex="0"]')).not.toBeNull();
});
it("shows saved parameter diff before any provider call and restores question", async () => {
  vi.stubGlobal("fetch", vi.fn());
  const data = { evaluation: { id: "eval", config: { prompt_strategy: "Grounded" } }, versions: [{ id: "p1", status: "active", provenance: "published", previous_version_id: "baseline-v1", config: { prompt_strategy: "Abstention" } }, { id: "baseline-v1", provenance: "bootstrap", config: { prompt_strategy: "Grounded" } }] };
  root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<ExperimentPage data={data} onOpenCitation={() => {}} />));
  expect(document.body.textContent).toContain("Grounded");
  expect(document.body.textContent).toContain("Abstention");
  expect(document.body.textContent).not.toContain("上一 Production");
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
  expect(document.querySelector("textarea")!.value).toBe("");
  expect(document.querySelector('[aria-label="方案 A"]')).toBeNull();
  expect(document.querySelector('[aria-label="方案 B"]')).toBeNull();
  expect(document.querySelector(".error-notice")?.textContent).toContain("需要当前有效 Baseline");
  const textarea = document.querySelector("textarea")!;
  await act(async () => { Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")!.set!.call(textarea, "缺少正式基准仍不可运行"); textarea.dispatchEvent(new Event("input", { bubbles: true })); });
  expect((document.querySelector(".query-action button") as HTMLButtonElement).disabled).toBe(true);
  expect(fetch).not.toHaveBeenCalled();
});
it("opens long text on focus and clears its tooltip on blur", async () => {
  root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<ExpandableText label="原因">完整长文说明</ExpandableText>));
  const target = document.querySelector('[tabindex="0"]') as HTMLElement;
  await act(async () => target.focus());
  expect(document.querySelector('[role="tooltip"]')?.textContent).toContain("完整长文说明");
  await act(async () => target.blur());
  expect(document.querySelector('[role="tooltip"]')).toBeNull();
});
