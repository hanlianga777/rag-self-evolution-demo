# Medium50 Golden Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking. User explicitly authorizes autonomous execution without ordinary stage confirmation.

**Goal:** Build a genuinely valid Medium50 and freeze through the existing delegated transaction only when every quality and quota condition is satisfied.

**Architecture:** Business questions are saved before PDF matching. Reuse existing generation, Hard Validation, Audit, Probe, QC, owner delegation and accounting; create a new Plan/Run only after independent complexity feasibility is established. Old identities and results remain read-only.

**Tech Stack:** Existing Python/SQLite/NumPy/FAISS and installed PDF tools; no new dependency.

**Spec:** `docs/superpowers/specs/2026-10-15-medium50-golden-closure-design.md`; user task SHA is preserved in the private authorization file.

## Global Constraints

50 questions, Positive20/Ablation10/Negative20, nine Topics, real difficulty10/25/15, existing Negative6/5/5/2/1/1 mapping. No weaker QC/Gate/Judge, no production Prompt/Pipeline/model changes. No Baseline/Agent/Sandbox/Regression/Gate2/Production. No duplicate successful Provider request; Unknown retained, no old retry grant reused.

### Task 1: Diagnose and verify feasibility before paid generation

Files: the design above and private `output/playwright/medium50-golden-closure-20261015/` artifacts.

- [x] Read current live rows, actual attention reasons and ten-dimension failures; preserve SQLite Backup API snapshot and original asset SHAs.
- [x] Trace planner, generator, validator, business audit and delegated freeze callers; write concrete causes with source paths.
- [x] Independently persist first KIRA/B2 business designs before reading PDF; inspect all157 PDF pages and actual Childs.
- [x] Cross-review claimed complex candidates against original PDF and user rubric, preserving disagreements.
- [x] Verify the fresh independently authored36 designs without changing their saved questions; resolve actual difficulty, evidence, negative boundary and duplicate intent.
- [x] Decide whether at least15 distinct complex intents have independent support. If insufficient, enumerate actual support and unresolved evidence; do not construct unsupported Complex Slots or pay for a mechanically repeated50 generation.

### Task 2: Align actual quality checks where the diagnosis proves a gap

Files: `backend/app/business_golden.py`, `backend/app/ai_service.py`, `backend/app/delegated_review.py`; corresponding existing unittest modules; current SPEC/changelog/README in the same final commit.

- [x] Before changing source, add minimal isolated regressions: an audit returning allTrue with observed Basic for targetComplex must not be accepted as difficulty-consistent; a new-contract owner review with wrong independent distribution or absent business checklist/actor/time must be refused. Existing contracts remain unchanged.
- [x] Run the added checks and confirm they fail for the diagnosed reasons. Use separate DB, .env, Corpus/index paths before importing app.
- [x] Add one shared business difficulty rubric to design/verification/audit input. Bind the audit target to the frozen Slot, and conservatively mark diversity false on explicit observed/target or current-label/target mismatch; retain actual observation and reason.
- [x] Under the new Plan quality contract only, validate independent business CHECKS, actor/time, actual difficulty perSlot and global10/25/15 before existing delegated approval; preserve all prior authorization/PDF/P0/P1/currentHash checks.
- [x] Run affected isolated regression modules and review the diff. Do not add a new generic workflow framework.

### Task 3: Execute a new Plan/Run only after feasibility passes

**Blocked by the actual prerequisite:** three bounded pools contain106 designs/versions, but only3 new plus2 prior independently supported complex directions; no proof of15 valid distinct complex intents. No new formal Plan/Run or paid generation was started. The unchecked execution below was not performed and is not claimed complete.

Files: independent versioned Plan and new scoped delegation/accounting private artifacts; minimal task-specific runner using existing methods if needed.

- [ ] Build the complete planned50 with feasible intents first, then material/Topic mapping; prefer independently supported existing questions, clone with traceable source identity rather than editing historical rows. Recompute Plan ID/version and all50 slots before starting generation, respecting the fixed Profile and Negative counts.
- [ ] Validate all allocations and corpus identity offline; bind the new direct authorization source, newRun/Plan/Corpus and review scope. Back up before writes.
- [ ] Run actual verification and governance serially with durable checkpoints and exact successful-response reuse. A changed identity receives current quality records; a failed design retains the failure and switches direction based on the cause. Do not retry an Unknown without an exact valid grant.
- [ ] Have a different reviewer check every current question against original PDFs and all15 user criteria, including verified Source quotes, time, currentHash and actual difficulty; P1 acceptance includes the exact current Probe/QC and substantive disposition.
- [ ] If every invariant passes, call existing `review_owner_delegated_batch` and verify the resulting Snapshot, not direct SQLite state updates. Otherwise preserve the real blocker and never manufacture a Snapshot.

### Task 4: Honest acceptance and repository delivery

Files: `docs/MEDIUM50_GOLDEN_FINAL_ACCEPTANCE.md`, current SPEC/changelog/README and scoped code/tests.

- [x] Report all50 current questions with real results, actual versus target difficulty, full source references, retained/replaced identities, failed feasibility pool and current review basis/time. Distinguish feasibility evidence from Provider acceptance.
- [x] Report actual Snapshot/Gate status or exact unmet prerequisites; if feasibility fails before a newRun, explicitly report that rather than implying a completed new dataset.
- [x] Recheck original PDFs/index/Corpus and all old database identities unchanged; report Provider usage/cost/cache/Unknown honestly.
- [x] Run appropriate isolated tests, diff check, and read-only UI verification. Repository delivery is the final operation: code and SPEC are committed together; the actual commit/push and clean synchronized HEAD receipt is recorded after execution in the acceptance handoff and private git-receipt.json.

Final verification:114 related isolated checks pass. Full624 against a temporary immutable knowledge-bundle copy:623 pass, one pre-existing API rejection-message assertion independently reproduced on unmodified17e1903. Review fixes bind the actual destination Plan and latest Business Audit timestamp. No Provider acceptance is claimed.
