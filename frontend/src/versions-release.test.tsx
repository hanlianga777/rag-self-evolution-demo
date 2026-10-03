// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { OperationProvider } from "./operation";
import { VersionsPage } from "./pages/VersionsPage";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
let root: ReturnType<typeof createRoot>;
afterEach(() => { if (root) act(() => root.unmount()); document.body.innerHTML = ""; sessionStorage.clear(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

it("offers one human release action after recommendation without posting before confirmation", async () => {
  const candidate = { id: "EXP-fixture-A", reasoning: { candidate_label: "A" }, release_state: { sandbox: true, qualified: true, recommended: true, round_complete: true, human_release: false } };
  vi.stubGlobal("fetch", vi.fn(async (url: string) => new Response(JSON.stringify(url.endsWith("/versions") ? [] : url.endsWith("/optimization") ? { candidates: [candidate] } : {}))));
  root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<OperationProvider restore={false}><VersionsPage data={{ versions: [], optimization: { candidates: [candidate] } }} /></OperationProvider>));
  const actions = document.querySelectorAll<HTMLButtonElement>(".release-actions button");
  expect(actions).toHaveLength(1);
  expect(actions[0].textContent).toContain("确认发布");
  expect(actions[0].disabled).toBe(false);
  await act(async () => actions[0].click());
  expect(document.querySelector(".confirm-dialog")?.textContent).toContain("Gate 3");
  expect(fetch).not.toHaveBeenCalled();
  await act(async () => document.querySelector<HTMLButtonElement>(".confirm-dialog .primary")!.click());
  expect(fetch).toHaveBeenCalledWith(expect.stringContaining("/api/candidates/EXP-fixture-A/publish"), expect.objectContaining({ method: "POST", body: JSON.stringify({ decision: "approved" }) }));
  expect(document.body.textContent).not.toContain("Candidate Approval");
  expect(document.body.textContent).not.toContain("Release Approval");
});

it("keeps other candidates in A/B/C/D order inside a Drawer and never offers an unqualified release", async () => {
  const candidates = ["C", "D", "B", "A"].map(label => ({ id: `EXP-${label}`, status: "evaluated", reasoning: { candidate_label: label }, release_state: { sandbox: true, qualified: label === "C", recommended: label === "C", round_complete: true } }));
  root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<OperationProvider restore={false}><VersionsPage data={{ versions: [], optimization: { candidates } }} /></OperationProvider>));
  expect(document.querySelector(".release-list")).toBeNull();
  expect(document.querySelectorAll(".release-actions button")).toHaveLength(1);
  await act(async () => [...document.querySelectorAll<HTMLButtonElement>("button")].find(node => node.textContent === "查看其他 Candidate")!.click());
  expect([...document.querySelectorAll(".candidate-release-row > strong")].map(node => node.textContent)).toEqual(["Candidate A", "Candidate B", "Candidate C", "Composite D"]);
  expect(document.querySelector(".drawer")?.textContent).toContain("不合格");
  expect(document.querySelectorAll(".drawer .release-actions button")).toHaveLength(0);
});

it("requires every saved release eligibility guard and a separate rollback confirmation", async () => {
  const state = { sandbox: true, qualified: true, recommended: true, round_complete: true, human_release: false };
  root = createRoot(document.body.appendChild(document.createElement("div")));
  for (const key of ["sandbox", "qualified", "recommended", "round_complete"] as const) {
    await act(async () => root.render(<OperationProvider restore={false}><VersionsPage data={{ versions: [], optimization: { candidates: [{ id: "C", release_state: { ...state, [key]: false } }] } }} /></OperationProvider>));
    expect([...document.querySelectorAll("button")].some(node => node.textContent === "确认发布")).toBe(false);
  }
  vi.stubGlobal("fetch", vi.fn(async (url: string) => new Response(JSON.stringify(url.endsWith("/versions") ? [] : url.endsWith("/optimization") ? {} : { id: "old" }))));
  await act(async () => root.render(<OperationProvider restore={false}><VersionsPage data={{ versions: [{ id: "new", status: "active" }, { id: "old", status: "archived" }] }} /></OperationProvider>));
  await act(async () => [...document.querySelectorAll<HTMLButtonElement>("button")].find(node => node.textContent === "回滚至此版本")!.click());
  expect(document.querySelector(".confirm-dialog")?.textContent).toContain("确认回滚 Production");
  expect(fetch).not.toHaveBeenCalled();
  await act(async () => document.querySelector<HTMLButtonElement>(".confirm-dialog .primary")!.click());
  expect(fetch).toHaveBeenCalledWith(expect.stringContaining("/api/versions/old/rollback"), expect.objectContaining({ method: "POST", body: JSON.stringify({ decision: "approved" }) }));
});
