#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
cd "$project_dir"

echo "[api] checking robot PDF index"
PYTHONPATH=backend python3 -m app.build_index --if-needed
exec python3 -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8010
