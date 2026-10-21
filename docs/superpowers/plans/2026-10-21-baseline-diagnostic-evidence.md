# Baseline diagnostic evidence implementation plan

**Goal:** Derive trustworthy diagnosis and legal interventions from immutable saved FAIL evidence, without changing evaluation identity or history.
**Approved scope:** Owner's 2026-10-21 implementation request and the two Medium50 audit reports.
**Approach:** Keep the current diagnostic entry points. Validate independent offline review records against the exact persisted Case, frozen Snapshot, Canonical Corpus and whole-stage digests. Review records carry necessary facts, source/applicability and equivalence evidence, never expected roots. Missing reviews stay blocked; no lexical absence is promoted to semantic absence. Existing Judge-only diagnostics remain available under strict quote/scope checks.

- [x] Add failing regression tests for partial Final coverage, Critical/Safety, order-independent root selection, missing/invalid review provenance and the 10 saved FAILs.
- [x] Implement the bounded independent evidence validator and derived stage findings; preserve raw Judge fields and report exact blockers.
- [x] Validate Ranking context interventions using saved candidates and the unchanged parameter domain; allow zero viable proposals, including Q27.
- [x] Keep business FAILs visible in the existing list, retaining technical details in the Drawer and five typical phenomena.
- [x] Sync current SPEC, changelog and related documentation; no architecture topology change.
- [x] Run isolated relevant backend tests, saved-record readonly verification, frontend tests/build; verify history/Corpus/identity checksums, then commit scoped files and push origin/main.
