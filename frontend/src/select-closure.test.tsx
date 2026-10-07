// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { CustomSelect } from "./components/Primitives";
let root: Root;
afterEach(async () => { if (root) await act(async () => root.unmount()); document.body.innerHTML = ""; });
it("closes a select inside a label without default label activation reopening it", async () => {
  const change = vi.fn(); root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<label><CustomSelect ariaLabel="Profile" value="a" options={[{ value: "a", label: "A" }, { value: "b", label: "B" }]} onChange={change} /></label>));
  const trigger = document.querySelector<HTMLButtonElement>('[role="combobox"]')!;
  for (const value of ["a", "b"]) {
    await act(async () => trigger.click());
    await act(async () => document.querySelector<HTMLElement>(`[data-value="${value}"]`)!.click());
    expect(document.querySelector('[role="listbox"]')).toBeNull();
    expect(document.activeElement).toBe(trigger);
    expect(change).toHaveBeenLastCalledWith(value);
  }
});
it("keeps one select open and closes on outside, Escape, blur and keyboard selection", async () => {
  root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<><CustomSelect ariaLabel="Pipeline" value="a" options={[{ value: "a", label: "A" }]} onChange={() => {}} /><CustomSelect ariaLabel="Pool filter" value="a" options={[{ value: "a", label: "A" }]} onChange={() => {}} /><input /></>));
  const triggers = [...document.querySelectorAll<HTMLButtonElement>('[role="combobox"]')];
  await act(async () => triggers[0].click()); await act(async () => triggers[1].click());
  expect(document.querySelectorAll('[role="listbox"]')).toHaveLength(1);
  expect(triggers[0].getAttribute("aria-expanded")).toBe("false");
  for (const key of ["Escape", "Enter", " "]) {
    if (!document.querySelector('[role="listbox"]')) await act(async () => triggers[1].click());
    await act(async () => triggers[1].dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true })));
    expect(document.querySelector('[role="listbox"]')).toBeNull();
  }
  await act(async () => triggers[0].click()); await act(async () => document.body.dispatchEvent(new Event("pointerdown", { bubbles: true })));
  expect(document.querySelector('[role="listbox"]')).toBeNull();
  await act(async () => { triggers[0].focus(); triggers[0].click(); }); await act(async () => document.querySelector("input")!.focus());
  expect(document.querySelector('[role="listbox"]')).toBeNull();
});
