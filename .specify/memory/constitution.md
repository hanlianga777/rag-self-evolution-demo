# RAG Evolution Constitution

## Core Principles

### I. Specification Before Business Change
Business logic, product rules, data structures, page flows, RAG behavior, and system architecture
MUST begin with a reviewed Spec Kit feature flow. A natural-language request alone MUST NOT trigger
an implementation. The exception is a small, confirmed bug using the documented bug workflow.

### II. Evidence and Data Integrity
The Demo MUST preserve traceability to approved PDF evidence and report only actual retrieval,
Probe, QC, evaluation, model, and version states. Fabricated scores, citations, provider results,
or candidate outcomes are prohibited. Existing corpus and Demo data change only through an
approved, scoped specification.

### III. Minimal, Compatible Changes
Changes MUST be limited to the approved task and preserve existing public behavior unless the Spec
explicitly authorizes a compatibility change. Reuse the existing React, FastAPI, SQLite, BGE, and
FAISS stack; do not add Docker, Kubernetes, or unrelated dependencies without explicit approval.

### IV. Evidence-Based Verification
Every implementation MUST identify focused verification before code changes and run the relevant
tests, build, or runtime checks afterwards. Tests MUST isolate or preserve local Demo data; a check
that mutates the production-like SQLite state requires explicit scope and reporting.

### V. Auditable Delivery
Each completed change MUST record its Spec Kit artifacts, verification evidence, scoped Git diff,
commit, and push result. Reviewers MUST reject work that exceeds its approved Spec, silently
changes data, or leaves an unverified failure unresolved.

## RAG and Runtime Boundaries

The four official PDFs, local OCR, BGE vectors, FAISS index, and auditable Golden Dataset workflow
remain the source of truth. DeepSeek is called only by explicit user actions and failures remain
visible rather than simulated. The application is a local Demo: production deployment, multi-agent
orchestration, and complex infrastructure are outside its default scope.

## Development Workflow

For a business change, use: discuss requirements → `$speckit-specify` → `$speckit-clarify` →
`$speckit-plan` → `$speckit-tasks` → `$speckit-analyze` → `$speckit-implement` → relevant tests
and build checks → `$speckit-converge` → Git commit and push. `clarify`, `checklist`, and `analyze`
are required whenever ambiguity, quality criteria, or cross-artifact consistency could affect the
outcome.

For a small confirmed bug, use `$speckit-bug-assess` → `$speckit-bug-fix` →
`$speckit-bug-test`. The assessment and verification reports stay under `.specify/bugs/<slug>/`.

## Governance

This constitution governs project changes together with explicit user requirements and repository
documentation; the higher-priority instruction wins when they conflict. Amendments require a
documented rationale, version update, and review in the same commit. Use semantic versioning:
MAJOR for incompatible principle changes, MINOR for added or materially expanded principles, and
PATCH for clarifications. Every implementation review MUST confirm compliance with this document
and the approved Spec Kit artifacts.

**Version**: 1.0.0 | **Ratified**: 2026-09-21 | **Last Amended**: 2026-09-21
