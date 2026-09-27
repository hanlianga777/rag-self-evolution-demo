// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { OverviewPage } from "./pages/OverviewPage";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
afterEach(() => { vi.unstubAllGlobals(); document.body.innerHTML = ""; });

it("keeps independent architecture images across a remount", async () => {
  const saved: Record<string, string | null> = { business: null, technical: null };
  vi.stubGlobal("fetch", vi.fn(async (url: string, options?: RequestInit) => {
    const slot = url.includes("/business") ? "business" : "technical";
    if (options?.method === "PUT") saved[slot] = `/api/overview/architecture/${slot}/image?v=1`;
    if (options?.method === "DELETE") saved[slot] = null;
    return new Response(JSON.stringify({ image_url: saved[slot] }), { status: 200 });
  }));
  const container = document.body.appendChild(document.createElement("div"));
  let root = createRoot(container);
  const show = () => <OverviewPage data={{}} navigate={() => {}} />;
  await act(async () => root.render(show()));
  await act(async () => [...document.querySelectorAll("button")].find(button => button.textContent === "业务架构")!.click());
  const file = new File(["\x89PNG"], "business.png", { type: "image/png" });
  const input = document.querySelector<HTMLInputElement>('input[type="file"]')!;
  Object.defineProperty(input, "files", { value: [file], configurable: true });
  await act(async () => input.dispatchEvent(new Event("change", { bubbles: true })));
  expect(document.querySelector<HTMLImageElement>(".architecture-image-area img")?.alt).toBe("业务架构");
  await act(async () => root.unmount());
  root = createRoot(container);
  await act(async () => root.render(show()));
  await act(async () => [...document.querySelectorAll("button")].find(button => button.textContent === "业务架构")!.click());
  expect(document.querySelector(".architecture-image-area img")).not.toBeNull();
  await act(async () => [...document.querySelectorAll("button")].find(button => button.textContent === "技术架构")!.click());
  expect(document.querySelector(".architecture-image-area img")).toBeNull();
  await act(async () => root.unmount());
});
