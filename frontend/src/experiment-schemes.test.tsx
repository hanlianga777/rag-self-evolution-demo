// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { ExperimentPage } from "./pages/ExperimentPage";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
afterEach(() => { document.body.innerHTML = ""; vi.unstubAllGlobals(); });

it("compares previous and current production after release and reads saved Bad Case evidence", async () => {
  const fetcher = vi.fn(async (input: RequestInfo | URL) => new Response(JSON.stringify({ cases: [{ question_id: "Q-1", model_answer: "已保存答案" }] }), { status: 200 }));
  vi.stubGlobal("fetch", fetcher);
  const data = {
    evaluation: { id: "EVAL-1" },
    badCases: [{ id: "BAD-1", run_id: "EVAL-1", question_id: "Q-1", result: { question: "固定问题" } }],
    versions: [
      { id: "production-1", status: "active", provenance: "published", previous_version_id: "baseline-v1", evaluation_run_id: "EVAL-C" },
      { id: "baseline-v1", status: "superseded", provenance: "bootstrap" },
    ],
  };
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<ExperimentPage data={data} onOpenCitation={() => {}} />));
  expect((document.querySelector('select[aria-label="Scheme A"]') as HTMLSelectElement).value).toBe("baseline-v1");
  expect((document.querySelector('select[aria-label="Scheme B"]') as HTMLSelectElement).value).toBe("production-1");
  await act(async () => (document.querySelector(".fixed-case-control button") as HTMLButtonElement).click());
  expect(document.body.textContent).toContain("已保存答案");
  expect(fetcher.mock.calls.map(([url]) => String(url))).toEqual(expect.arrayContaining([expect.stringContaining("/api/evaluations/EVAL-1"), expect.stringContaining("/api/evaluations/EVAL-C")]));
  await act(async () => root.unmount());
});

it("defaults to Baseline and a qualified Candidate before release", async () => {
  const data = { evaluation: { id: "EVAL-1" }, optimization: { candidates: [{ id: "C-1", reasoning: { candidate_label: "C" }, result: { qualification: { qualified: true } } }] }, versions: [{ id: "baseline-v1", status: "active", provenance: "bootstrap" }] };
  const root = createRoot(document.body.appendChild(document.createElement("div")));
  await act(async () => root.render(<ExperimentPage data={data} onOpenCitation={() => {}} />));
  expect((document.querySelector('select[aria-label="Scheme A"]') as HTMLSelectElement).value).toBe("baseline");
  expect((document.querySelector('select[aria-label="Scheme B"]') as HTMLSelectElement).value).toBe("C-1");
  await act(async () => root.unmount());
});
