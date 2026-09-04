# RAG Evolution First Phase Design

## Product

RAG Evolution is an evaluation-driven RAG optimization Demo for an enterprise campus-operations knowledge assistant. It demonstrates a credible closed loop: seed knowledge and Golden Dataset, evaluate a baseline, inspect eight bad cases, run one structured optimization agent, compare candidates in a logical sandbox, rerun all forty questions, apply SLA gates, and recommend Candidate B.

## Scope

The first phase is a runnable desktop-focused demo, not a production RAG deployment. The UI comprises Overview, Knowledge & Dataset, Evaluation, Evolution Lab, Versions, Settings, and a Preview comparison dialog. It uses consistent seeded facts and a FastAPI Mock API.

## Architecture

React owns presentation and interaction only. FastAPI owns seed read models, experiment replay state, version activation, preview answers, and readiness. SQLite is the local persistence boundary. Provider adapters represent RAG answer, LLM judge, and optimizer roles but report Mock mode unless environment variables are later configured.

## Decisions

- Independent repository: AutoRAG legacy is a reference only; no source is copied and no dependency is installed.
- Single optimization agent: no multi-agent claim.
- Logical sandbox: candidate configuration snapshots run independently without Docker.
- Completed history plus replay: Overview remains interview-ready while Evolution Lab can visibly rerun A/B/C.
- Candidate B is recommended only after full 40/40 regression and all quality, safety, latency, and regression gates pass.

