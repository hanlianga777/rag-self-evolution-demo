# Independent Experiment Preview Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the experiment page render independent, real-timed baseline and candidate responses without losing its state during same-session navigation.

**Architecture:** The backend exposes one independently timed JSON endpoint per Pipeline while retaining the current combined preview contract. The experiment page sends both requests concurrently and keeps each column's lifecycle separate; `App` preserves the page instance by moving keyed, always-mounted wrappers after visible content.

**Tech Stack:** FastAPI, Python `unittest`, React 18, TypeScript, Vitest, CSS Grid.

**Spec:** `docs/superpowers/specs/2026-09-15-independent-experiment-preview-design.md`

## Global Constraints

- Do not change PDF corpus, retrieval ranking, provider configuration, Citation shape, or the existing `POST /api/preview` response contract.
- Do not add SSE, polling, dependencies, or persistence across a browser refresh.
- Every displayed Pipeline elapsed time comes from that Pipeline endpoint's actual `latency_ms`; do not stage or fabricate completion.
- New paid-work routes use the existing `PreviewRequest` and `require_trusted_origin` dependency.
- Keep only the question, independent run state, responses, citations, and parameters alive during unrefreshed navigation.

---

## File Structure

- `backend/app/ai_service.py` owns independent baseline/candidate response construction and compatibility composition.
- `backend/app/main.py` exposes trusted independent preview routes without changing the existing route.
- `backend/tests/test_api.py` proves API shape, validation and trusted-origin behavior.
- `frontend/src/types.ts` defines the flat independent Pipeline response.
- `frontend/src/pages/ExperimentPage.tsx` owns concurrent run state and per-column rendering.
- `frontend/src/App.tsx` owns keyed page mounting order so visible content remains first and experiment state survives navigation.
- `frontend/src/styles.css` contains the small layout and typography refinements.
- `frontend/src/trust-ux.test.tsx` proves independent completion and session-lifetime page state.
- `README.md` documents the new explicit preview routes and their timing boundary.

### Task 1: Independent preview API contract

**Files:**
- Modify: `backend/app/ai_service.py:39-90`
- Modify: `backend/app/main.py:96-99`
- Test: `backend/tests/test_api.py:84-113, 124-132`

**Interfaces:**
- Consumes: `PreviewRequest.question`, `AiService.retriever.search`, `DeepSeekProvider.complete`.
- Produces: `AiService.baseline_preview(question: str) -> dict`, `AiService.candidate_preview(question: str) -> dict`, `POST /api/preview/baseline`, and `POST /api/preview/candidate`.

- [ ] **Step 1: Write the failing API tests**

```python
def test_independent_preview_routes_return_flat_pipeline_results(self):
    baseline = self.client.post("/api/preview/baseline", json={"question": "B2遥控器低电量时如何充电？"}).json()
    candidate = self.client.post("/api/preview/candidate", json={"question": "B2遥控器低电量时如何充电？"}).json()

    self.assertEqual(baseline["pipeline"], "baseline")
    self.assertEqual(baseline["version"], "v1.0")
    self.assertIsInstance(baseline["latency_ms"], int)
    self.assertEqual(candidate["pipeline"], "candidate_b")
    self.assertEqual(candidate["evidence"][0]["chunk_id"], "B2-REMOTE-CHUNK-0005")
    self.assertIsInstance(candidate["latency_ms"], int)
```

Add each new route to the existing validation loop and trusted-origin route matrix. For mock results, assert a non-negative integer latency instead of `None`.

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `python -m unittest backend.tests.test_api.DemoApiTests.test_independent_preview_routes_return_flat_pipeline_results -v`

Expected: FAIL because the two paths return 404.

- [ ] **Step 3: Add the smallest independent service methods and routes**

```python
def baseline_preview(self, question: str) -> dict:
    started_at = time.perf_counter()
    baseline = self._preview_compatibility(question)["baseline"]
    return {"pipeline": "baseline", "question": question, **baseline,
            "latency_ms": round((time.perf_counter() - started_at) * 1000)}

def candidate_preview(self, question: str) -> dict:
    started_at = time.perf_counter()
    # Reuse the existing retrieval, LIVE generation and Mock fallback branches.
    # Every return includes the elapsed latency_ms calculated from started_at.
```

Add FastAPI handlers:

```python
@app.post("/api/preview/baseline", dependencies=[Depends(require_trusted_origin)])
def preview_baseline(payload: PreviewRequest):
    return ai_service.baseline_preview(payload.question)

@app.post("/api/preview/candidate", dependencies=[Depends(require_trusted_origin)])
def preview_candidate(payload: PreviewRequest):
    return ai_service.candidate_preview(payload.question)
```

Rewrite `preview(question)` as a compatibility composer whose output preserves its current nested `baseline` and `candidate_b` fields exactly. It calls the two service methods but does not expose their new `pipeline` fields in the legacy response.

- [ ] **Step 4: Run backend API tests to verify the contract passes**

Run: `python -m unittest backend.tests.test_api -v`

Expected: PASS, including existing preview validation, mock evidence, and origin tests.

- [ ] **Step 5: Commit the API contract**

```bash
git add backend/app/ai_service.py backend/app/main.py backend/tests/test_api.py
git commit -m "feat: add independent preview routes"
```

### Task 2: Independent experiment run state and preserved page instance

**Files:**
- Modify: `frontend/src/types.ts:15-29`
- Modify: `frontend/src/pages/ExperimentPage.tsx:1-30`
- Modify: `frontend/src/App.tsx:28-35`
- Test: `frontend/src/trust-ux.test.tsx:53-110, 144-190`

**Interfaces:**
- Consumes: `POST /api/preview/baseline` and `POST /api/preview/candidate` from Task 1.
- Produces: `PipelinePreview`, independent `baseline`/`candidate` state, and an always-mounted keyed `ExperimentPage` wrapper.

- [ ] **Step 1: Write failing independent-completion and navigation tests**

```tsx
it("renders a completed baseline while the candidate remains thinking", async () => {
  const resolveBaseline = deferred<PipelinePreview>();
  const resolveCandidate = deferred<PipelinePreview>();
  post = path => path.endsWith("/baseline") ? resolveBaseline.promise : resolveCandidate.promise;
  await render(<App />); await click("问答试验"); await setExperimentQuestion("B2遥控器低电量时如何充电？"); await click("发送");

  await act(async () => { resolveBaseline.resolve(baselinePreview); await Promise.resolve(); });
  expect(content()).toContain("基线示例回答已移除");
  expect(document.querySelectorAll(".experiment-thinking")).toHaveLength(1);
  expect(document.querySelector(".experiment-results")?.textContent).toContain("12 ms");
});

it("keeps an experiment result after navigation without refresh", async () => {
  post = path => path.endsWith("/baseline") ? baselinePreview : candidatePreview;
  await render(<App />); await click("问答试验"); await setExperimentQuestion("B2遥控器低电量时如何充电？"); await click("发送");
  await click("概览"); await click("问答试验");

  expect((document.querySelector('[aria-label="试验问题"]') as HTMLTextAreaElement).value).toBe("B2遥控器低电量时如何充电？");
  expect(content()).toContain("B2-REMOTE-CHUNK-0005");
});
```

Also extend the initial-state test to require two sibling `.run-parameters` elements before submission, and update fixtures with flat `baselinePreview` and `candidatePreview` objects.

- [ ] **Step 2: Run the focused frontend test to verify it fails**

Run: `npm test -- --run src/trust-ux.test.tsx`

Expected: FAIL because the page calls only `/api/preview`, removes parameters before a result, and unmounts during navigation.

- [ ] **Step 3: Add typed independent state and concurrent requests**

```ts
export type PipelinePreview = {
  pipeline: "baseline" | "candidate_b";
  question: string;
  version: string;
  answer: string;
  latency_ms: number;
  mode?: "live" | "mock";
  model?: string | null;
  fallback_reason?: string | null;
  sources?: string[];
  evidence?: Citation[];
};
```

In `ExperimentPage`, replace the shared `result` with two independent state records. On submission, set both to `thinking`, retain the question, and start both `postJson<PipelinePreview>` calls without `Promise.all`. Each `.then` sets only its own result; each `.catch` sets only its own error. Use returned `latency_ms` in the completed card. Keep `Answer` mounted only for its completed column so its existing 18 ms character cadence begins immediately.

Render parameter cards for `idle`, `thinking`, `complete`, and `error`; idle values are `等待提问` / `未运行`, while completed fields come only from that Pipeline response.

In `App`, render keyed wrapper nodes for Assistant and Experiment after the visible page when hidden, and place the active wrapper first. Keep the wrappers keyed as `assistant` and `experiment` so their component instances survive sibling reordering.

- [ ] **Step 4: Run the focused frontend test to verify it passes**

Run: `npm test -- --run src/trust-ux.test.tsx`

Expected: PASS with independent completion, error isolation, initial parameter cards, and no-refresh navigation retention.

- [ ] **Step 5: Commit independent state preservation**

```bash
git add frontend/src/types.ts frontend/src/pages/ExperimentPage.tsx frontend/src/App.tsx frontend/src/trust-ux.test.tsx
git commit -m "feat: preserve independent experiment previews"
```

### Task 3: Compact presentation refinements and API documentation

**Files:**
- Modify: `frontend/src/styles.css:144-172, 265-277`
- Modify: `README.md:27-31`
- Test: `frontend/src/trust-ux.test.tsx:53-110`

**Interfaces:**
- Consumes: `PipelinePreview` and card classes from Task 2.
- Produces: matching placeholder color, content-width citation links, compact parameter cards, and documented routes.

- [ ] **Step 1: Write the failing DOM assertions**

```tsx
expect(document.querySelectorAll(".experiment-results > .run-parameters")).toHaveLength(2);
expect(document.querySelector(".chat-composer input")?.getAttribute("placeholder")).toBe("请输入你的问题…");
expect(document.querySelector(".evidence-list .document-link")).not.toBeNull();
```

Update the stylesheet assertions only through visible class behavior: pipeline selects remain native `<select>` controls, and citation buttons remain clickable after the layout changes.

- [ ] **Step 2: Run the frontend test to verify it fails for the initial card shape**

Run: `npm test -- --run src/trust-ux.test.tsx`

Expected: FAIL until Task 2 has rendered both initial parameter cards.

- [ ] **Step 3: Apply the smallest CSS and README changes**

```css
.chat-composer input::placeholder { color: #8a96a4; }
.pipeline-selector select { font-weight: 700; }
.evidence-list .document-link { justify-self: start; }
.run-parameters { justify-self: center; width: 66.667%; }
```

Keep parameter gaps compact and retain a desktop answer-first grid. Add the two independent preview routes and their actual-timing semantics to the README's preview description.

- [ ] **Step 4: Run presentation regression tests and production build**

Run: `npm test && npm run build`

Expected: PASS with no TypeScript errors.

- [ ] **Step 5: Commit presentation and documentation**

```bash
git add frontend/src/styles.css frontend/src/trust-ux.test.tsx README.md
git commit -m "fix: compact experiment preview presentation"
```

### Task 4: End-to-end verification and delivery

**Files:**
- Modify: none
- Test: `backend/tests/test_api.py`, `frontend/src/trust-ux.test.tsx`

**Interfaces:**
- Consumes: all prior tasks.
- Produces: verified `main` branch and remote synchronization.

- [ ] **Step 1: Run the complete backend suite**

Run: `python -m unittest discover -s backend/tests -v`

Expected: PASS, including the independent endpoint contract and trusted-origin boundary.

- [ ] **Step 2: Run the complete frontend suite and production build**

Run: `cd frontend && npm test && npm run build`

Expected: PASS with zero test failures and a successful Vite build.

- [ ] **Step 3: Check the final diff and browser behavior**

Run: `git diff origin/main...HEAD --check && git status --short --branch`

Browser checks at desktop width:

1. Submit a question; confirm both cards begin thinking.
2. Confirm the first completed card starts typing while the other card continues thinking.
3. Confirm each completed card displays only its returned `latency_ms`.
4. Navigate away and back without refresh; confirm question, answers, citations and parameters remain.
5. Confirm a citation underlines only its text and opens the document inspector.

- [ ] **Step 4: Push the verified commits**

```bash
git push origin main
git status --short --branch
```

Expected: `main...origin/main` with no uncommitted files.
