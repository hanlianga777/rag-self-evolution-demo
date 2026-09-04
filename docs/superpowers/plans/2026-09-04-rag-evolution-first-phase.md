# RAG Evolution First Phase Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a locally runnable, public-ready RAG evaluation and self-evolution demo with a fully clickable Mock workflow.

**Architecture:** A React SPA renders the product UI and calls a FastAPI API. Python's SQLite-backed seed repository owns all demo facts and experiment state; the API returns stable read models and drives the replay experiment state machine. Real provider work remains behind backend adapters and is never required in Mock mode.

**Tech Stack:** React, TypeScript, Vite, Tailwind CSS, shadcn-style primitives, Lucide, Recharts, FastAPI, SQLite, Python stdlib unittest.

**Spec:** `docs/superpowers/specs/2026-09-04-rag-evolution-design.md`

## Global Constraints

- Desktop-first Light SaaS interface for 1440x900 and usable at 1280x720.
- No Docker, Redis, Kafka, microservices, real DeepSeek calls, AutoRAG dependency, or secrets in Git.
- Mock mode must present all data through the FastAPI API, never through scattered React fixtures.
- Sandbox means logical configuration isolation, not container isolation.
- Use only one optimization agent model with tool-shaped backend service methods.

---

### Task 1: Repository foundation and backend data contract

**Files:**
- Create: `.gitignore`, `.env.example`, `backend/app/main.py`, `backend/app/seed.py`, `backend/tests/test_api.py`

**Interfaces:**
- Produces: `GET /api/overview`, `GET /api/documents`, `GET /api/dataset`, `GET /api/evaluation`, `GET /api/bad-cases`, `GET /api/optimization`, `GET /api/versions`, `GET /api/readiness`.

- [ ] Define the failing API tests for seed consistency and Candidate B recommendation.
- [ ] Implement one SQLite seed repository and FastAPI read routes.
- [ ] Run `PYTHONPATH=backend python3 -m unittest discover -s backend/tests -v`.

### Task 2: Experiment, version, and preview mutations

**Files:**
- Create: `backend/app/services.py`
- Modify: `backend/app/main.py`
- Modify: `backend/tests/test_api.py`

**Interfaces:**
- Produces: `POST /api/experiments/run`, `GET /api/experiments/{id}`, `POST /api/versions/{id}/activate`, `POST /api/preview`.
- Experiment statuses are `queued`, `running`, `evaluating`, and `completed`.

- [ ] Add failing tests that start a replay, retrieve a progressing run, activate a version, and compare the fixed air-conditioner query.
- [ ] Implement the minimal time-based replay service and logical SLA gate.
- [ ] Re-run the backend suite.

### Task 3: React shell and API client

**Files:**
- Create: `frontend/` Vite project files, `frontend/src/api.ts`, `frontend/src/types.ts`, `frontend/src/App.tsx`

**Interfaces:**
- Consumes all API routes from Tasks 1-2.
- Produces route navigation and a shared API/error/loading boundary.

- [ ] Scaffold strict TypeScript and Tailwind-compatible build configuration.
- [ ] Implement the sidebar, workspace header, Mock-mode badge, preview entry, route state, and request client.
- [ ] Run `npm run build` in `frontend/`.

### Task 4: Product pages and interaction loop

**Files:**
- Create: focused page and component modules in `frontend/src/pages/` and `frontend/src/components/`

**Interfaces:**
- Consumes API read models and experiment mutation routes.
- Produces all required Overview, Knowledge & Dataset, Evaluation, Evolution Lab, Versions, Settings, and Preview interactions.

- [ ] Implement Overview KPI/pipeline/charts/runs; document and dataset tabs with document detail.
- [ ] Implement evaluation metrics, filters, bad-case drawer, and Optimize This Run navigation.
- [ ] Implement structured agent timeline, A/B/C cards, polling experiment replay, results/SLA/regression state, version diff/activation, and Before/After preview.
- [ ] Re-run the frontend production build.

### Task 5: Operational and handoff artifacts

**Files:**
- Create: `start.sh`, `README.md`, `ARCHITECTURE.md`, `PROJECT_CONTEXT.md`, `DECISIONS.md`, `TODO.md`, `CODEX_HANDOFF.md`, `CHANGELOG.md`, `THIRD_PARTY_NOTICES.md`

- [ ] Document setup, demonstration flow, Mock versus planned capability, AutoRAG reference, and logical sandbox limit.
- [ ] Verify one-command startup, API smoke checks, browser flow, responsive layout, and clean browser console.
- [ ] Initialize Git, commit scoped work, create/push `hanlianga777/rag-self-evolution-demo` publicly when credentials are available, and confirm synchronization.

