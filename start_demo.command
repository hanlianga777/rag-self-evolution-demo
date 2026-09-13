#!/bin/bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$PROJECT_DIR/.demo-logs"
URL="http://127.0.0.1:5174"

if [[ "${DEMO_BACKGROUND_WORKER:-}" != "1" ]]; then
  mkdir -p "$LOG_DIR"
  nohup env DEMO_BACKGROUND_WORKER=1 "$PROJECT_DIR/start_demo.command" >"$LOG_DIR/launcher.log" 2>&1 < /dev/null &
  exit 0
fi

cd "$PROJECT_DIR"
if lsof -nP -iTCP:8010 -sTCP:LISTEN >/dev/null 2>&1 && lsof -nP -iTCP:5174 -sTCP:LISTEN >/dev/null 2>&1; then
  open "$URL"
  exit 0
fi

./start.sh &
launcher_pid=$!
trap 'kill "$launcher_pid" 2>/dev/null || true' EXIT INT TERM
for _ in {1..60}; do
  curl -fsS "$URL" >/dev/null 2>&1 && { open "$URL"; break; }
  sleep 1
done
wait "$launcher_pid"
