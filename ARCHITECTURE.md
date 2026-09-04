# Architecture

## Runtime

React/Vite presents the workspace. FastAPI owns the data boundary. SQLite stores the seed JSON and provides a simple local persistence boundary. `start.sh` runs both processes without Docker.

## Data flow

`SeedStore → FastAPI routes → frontend API client → product pages`

The experiment route creates an in-memory replay run. Polling maps elapsed time to queued, running, evaluating, then completed. It never changes the active production configuration. Version activation changes only the Demo selection.

## Provider boundary

The current API exposes readiness and Mock responses. A later implementation can add RAG Answer, LLM Judge, and Optimization Agent adapters behind the existing backend routes. UI components must not call a provider directly.

## Evaluation and recommendation

The baseline evaluates all 40 Golden Dataset records. Candidate B is recommended because it has the best qualifying result: quality, safety, latency, and 40/40 regression all pass with no new regressions. Candidate A fails latency; Candidate C fails quality.
