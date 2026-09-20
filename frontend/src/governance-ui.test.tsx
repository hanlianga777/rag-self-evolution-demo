// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { KnowledgePage } from "./pages/KnowledgePage";

afterEach(() => { document.body.innerHTML = ""; vi.restoreAllMocks(); });

it("shows a pending candidate and writes an approval through the governance API", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ stage: "golden" }), { status: 200 })));
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => { root.render(<KnowledgePage data={{ documents: [], dataset: [{ id: "GGC-001", question: "测试题", test_category: "positive", review_status: "human_review_pending", probe_status: "probe_pending", stage: "candidate", evidence: [] }] }} />); });

  expect(document.body.textContent).toContain("候选题库");
  await act(async () => { [...document.querySelectorAll("button")].find(button => button.textContent === "候选题库")!.click(); });
  expect(document.body.textContent).toContain("批准为 Golden");
});
