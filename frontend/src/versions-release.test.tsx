// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { OperationProvider } from "./operation";
import { VersionsPage } from "./pages/VersionsPage";

afterEach(() => { document.body.innerHTML = ""; vi.restoreAllMocks(); });

it("offers one human release action after recommendation and no old approvals", async () => {
  const candidate = { id: "EXP-fixture-A", release_state: { sandbox: true, qualified: true, recommended: true, round_complete: true, human_release: false } };
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<OperationProvider><VersionsPage data={{ versions: [], optimization: { candidates: [candidate] } }} /></OperationProvider>));
  const actions = document.querySelectorAll<HTMLButtonElement>(".release-actions button");
  expect(actions).toHaveLength(1);
  expect(actions[0].textContent).toContain("确认发布");
  expect(actions[0].disabled).toBe(false);
  expect(document.body.textContent).not.toContain("Candidate Approval");
  expect(document.body.textContent).not.toContain("Release Approval");
  await act(async () => root.unmount());
});
