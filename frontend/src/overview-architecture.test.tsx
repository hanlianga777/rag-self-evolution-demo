// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { OverviewPage } from "./pages/OverviewPage";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
afterEach(() => { vi.unstubAllGlobals(); document.body.innerHTML = ""; });

it("renders inline architecture without reference upload or developer disclosures", async () => {
  const fetch = vi.fn(); vi.stubGlobal("fetch", fetch);
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<OverviewPage data={{}} navigate={() => {}} />));
  await act(async () => [...document.querySelectorAll("button")].find(button => button.textContent === "业务架构")!.click());
  expect(document.querySelector('.knowledge-diagrams')?.textContent).toContain("唯一 Main Agent");
  expect(document.body.textContent).not.toContain("已保存参考图");
  expect(document.querySelector('input[type="file"]')).toBeNull();
  await act(async () => [...document.querySelectorAll("button")].find(button => button.textContent === "技术架构")!.click());
  expect(document.querySelectorAll('svg[role="img"]')).toHaveLength(1);
  expect(document.body.textContent).toContain("Parent Expand");
  expect(document.body.textContent).toContain("Small Cluster Protection");
  expect(fetch).not.toHaveBeenCalled();
  const ids = [...document.querySelectorAll('svg [id]')].map(node => node.id);
  expect(new Set(ids).size).toBe(ids.length);
  await act(async () => root.unmount());
});
