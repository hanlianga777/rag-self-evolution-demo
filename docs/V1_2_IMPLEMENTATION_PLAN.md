# V1.2 implementation ledger

Baseline: `93486f23db4bb4711bba332dd0063b330838af47`. User-authorized V1.2 plan is the scope. Ponytail full. Real user database is read-only; backup and all tests use `/tmp/rag-v12.bVmzUQ/`.

## Global constraints

No new dependencies, tables, agents or top-level pages. Retain 11 evaluation gates. Keep real data and previews unchanged. Real model smoke only after deterministic/fixture/copy tests. One isolated real main lifecycle, no repeated quality chasing.

## Task 1: Corpus and coverage

Dynamic document/index catalogs; no four-document runtime constraint. Minimum metadata document_id/chunk_id/chunk_text. Embedding topic clustering with existing FAISS/NumPy and 8/4/8 quota; prefer unused chunks. Reliable structured Aggregation/Bridge/Fact only when source supports them. Independent Ablation; no forced source Positive or pair generation prompts. One automatic targeted fix maximum. Tests on 1/2/4/6/10 documents and arbitrary identifiers.

## Task 2: Governance

Remove pair/equal-answer/equal-evidence/lexical-similarity gates. Retain deterministic anchor/structure and strict Negative gate. Retrieval miss P1, not numeric approval failure. QC severity not 85 cutoff; explicit human P0 acceptance cannot waive deterministic/Fake Negative/count errors. Approve/Edit/Replace; active slot replacement and history; Gate 1 atomic confirm plus immutable version. Existing audits and optimistic concurrency retained.

## Task 3: Tuning and release

Actual prior sandbox feedback; common evaluator; 12 reserved execution slots including D. Gate 2 completed attempts + at least one qualified winner. D merges proven nonconflicting diffs, stores provenance, fully reevaluates; no improvement falls back to winner. Gate 3 single atomic human publish.

## Task 4: UI and integration

Seven pages retained, simplified review, QC acceptance reason, automatic Golden version at Gate 1; A/B/C report confirmation, D and fallback; Monitoring auxiliary. Reuse operation state/API/Drawer. Tests and controlled browser checks.

## Task 5: Verification and delivery

Full backend/frontend/fixture/build/startup/diff checks, portability, existing DB copy, one real isolated main lifecycle; documents/diagram synchronization; final review, commit/push/main synchronization. Report A–G with limitations and actual evidence.

## Preflight interfaces

| Tasks | Shared contract | Resolution |
|---|---|---|
| 1 / 2 | AiService output → governance persistence | Keep question/evidence fields; optional relation metadata only |
| 2 / 4 | approval and active slots → UI | server-derived eligibility, no UI-only gate removal |
| 3 / 4 | report/D/release → UI | server authoritative state and gate reasons |
| 1–4 / 5 | tests/documents/runtime | no live default-db imports; isolation env before import |

Status: implementation and deterministic/Fixture verification complete; isolated real lifecycle blocked at Golden quality. See V1_2_VERIFICATION.md for exact evidence and limitations.
