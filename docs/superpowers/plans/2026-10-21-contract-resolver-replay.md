# Contract / Resolver / Judge-only Replay implementation plan

Goal: implement Owner's attached first-stage contract offline; never execute production paid tasks.
Spec: Owner's 2026-10-21 attached “评测合同、自动归因与 Medium50 收口统一实施”, current SPEC overrides updated together.
Architecture: keep EvaluationRunner and Diagnostic; separate source-bound Scope evidence from Final Fact evidence; resolve full frozen norms; persist independent semantic evidence; create ordinary baseline runs seeded only with verified historical execution checkpoints.
Stack: existing Python stdlib, SQLite, React; no new dependency, Agent or search parameter.

- [x] Write failing scope/norm/resolver/replay tests. All app imports use isolated DB/index/env.
- [x] evaluation_contract / ai_service / providers: strict Canonical heading-to-Final binding, scope_support/check_type, bumped Prompt/Parser/Matcher/input versions. No title in content; Fact support stays body-only.
- [x] resolve frozen IDs to complete Canonical norms; keep original summaries; remove new Revision's [:160]. Validate all saved norms, not just one question.
- [x] Diagnostic resolver: source-validated required facts, semantic stage/answer coverage (not model root labels), explicit unresolved state, whole-run/config/case/corpus hashes, separate persistence and explicit authorized semantic endpoint. GETs never call Provider.
- [x] Replay: per-question eligibility for saved answers/three stages/config/generation/request/source identity, 49 case executions + failed checkpoint; reject incomplete records without generating. Seed new baseline's checkpoints in one transaction; reuse normal retry/persistence/gates/current-baseline guards, preserve replay no-generation guard on resume/recovery.
- [x] Small existing Baseline UI addition: readonly eligibility and explicit paid confirmation, new Identity, no old-run resume; no automatic POST.
- [x] Q27 offline extension proposal only, leave parameter domain and correct capability block unchanged.
- [x] Relevant/full backend, frontend/build, real 50 eligibility and immutable history checks; update SPEC/changelog/README/architecture/report; commit and push exact scope. Stop after offline stage, give next-stage call/cost preflight.
