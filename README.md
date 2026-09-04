# RAG Evolution

> Evaluation-driven RAG Optimization Platform

RAG Evolution is an interview-ready local Demo for an enterprise campus-operations knowledge assistant. It shows the full product story: knowledge and Golden Dataset → baseline evaluation → bad case evidence → structured optimization diagnosis → A/B/C sandbox experiments → full-dataset regression → SLA-gated recommendation.

## Why this is not a normal RAG Demo

The product does not present a single answer as success. It makes evaluation evidence, bad cases, candidate configurations, quality/latency trade-offs, and the complete 40-question regression visible in one auditable loop.

## Implemented

- Five core product pages: Overview, Knowledge & Dataset, Evaluation, Evolution Lab, and Versions.
- Settings and a Preview Before/After comparison drawer.
- FastAPI Mock API backed by one SQLite seed source: 12 documents, 438 chunks, 40 Golden Dataset questions, 8 bad cases, and consistent A/B/C results.
- Replayable sandbox experiment UI with queued, running, evaluating, and completed states.
- SLA gates that recommend Candidate B only after the full regression passes.

## Mock and planned capability

This phase is **Demo Mock Mode**. No DeepSeek call, RAG retrieval, LLM judge, or production deployment is claimed or performed. The backend API and provider boundaries are ready to replace deterministic fixtures with real services later.

Sandbox means logical configuration isolation plus independent evaluation; it is not a Docker/container sandbox.

## Local setup

Prerequisites: Python 3.10+, Node.js 20+, npm.

```bash
./start.sh
```

Open [http://127.0.0.1:5174](http://127.0.0.1:5174). The FastAPI API docs are at [http://127.0.0.1:8010/docs](http://127.0.0.1:8010/docs).

Manual startup:

```bash
python3 -m pip install -r backend/requirements.txt
PYTHONPATH=backend python3 -m uvicorn app.main:app --port 8010
cd frontend && npm install && npm run dev
```

## Demo flow

1. Start at Overview and inspect Baseline 72.4, eight bad cases, and the evolution pipeline.
2. Open Evaluation, select “我工位空调坏了咋整？”, and inspect the retrieval evidence.
3. Select **Optimize This Run**, review the structured single-agent diagnosis and candidates.
4. Select **Run Experiments** and observe the replayed sandbox run.
5. Confirm Candidate B is recommended only after 40/40 regression and all SLA gates pass.
6. Open Preview to compare the baseline refusal with Candidate B’s grounded answer.

## Optional future DeepSeek configuration

Copy `.env.example` to `.env` and configure `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL`, and `DEEPSEEK_MODEL` only when real provider integration is intentionally implemented. Never commit `.env`.

## AutoRAG reference

AutoRAG legacy was reviewed as a technical reference for dataset, evaluation, pipeline, and experiment concepts. This project does not fork, package, or copy AutoRAG source. See `THIRD_PARTY_NOTICES.md` and `DECISIONS.md`.

## Roadmap

Replace Mock services with an actual corpus/index, RAG runtime, provider adapters, and measured evaluation execution while preserving the existing API/UI contracts.
