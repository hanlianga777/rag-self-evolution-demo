# Decisions

## Independent implementation over AutoRAG fork

AutoRAG’s original Python RAG AutoML capability is located in `legacy/`, while the root project now focuses on AutoRAG 2.0. This Demo uses neither as a dependency: a direct integration would add a large evaluation stack before any real runtime exists. The legacy project remains a documented conceptual reference.

## One agent and logical sandbox

The UI represents one structured Optimization Agent with tool-shaped steps, not a chat transcript or multi-agent system. Sandbox means independent candidate configuration snapshots and evaluation runs; it is not a production container boundary.

## Mock-first API

All display data crosses the FastAPI API, so the React UI does not own business fixtures. Real RAG, judging, and provider adapters can later replace the deterministic backend service.
