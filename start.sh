#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "$0")" && pwd)"
cd "$project_root"

if lsof -nP -iTCP:8010 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port 8010 is already in use. Stop the matching RAG Evolution process or set a different coordinated port pair."
  exit 1
fi
if lsof -nP -iTCP:5174 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port 5174 is already in use. Stop the matching RAG Evolution process or set a different coordinated port pair."
  exit 1
fi

if ! python3 -c 'import fastapi, uvicorn' >/dev/null 2>&1; then
  python3 -m pip install -r backend/requirements.txt
fi
if [ ! -d frontend/node_modules ]; then
  (cd frontend && npm install --cache .npm-cache)
fi

python3 -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8010 &
backend_pid=$!
cleanup() { kill "$backend_pid" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

echo "RAG Evolution API: http://127.0.0.1:8010/docs"
echo "RAG Evolution Demo: http://127.0.0.1:5174"
(cd frontend && npm run dev -- --host 127.0.0.1)
