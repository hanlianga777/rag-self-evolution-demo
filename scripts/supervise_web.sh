#!/usr/bin/env bash
set -euo pipefail

runner="$(cd "$(dirname "$0")" && pwd)/run_web_service.sh"
child_pid=""
stop() {
  [[ -n "$child_pid" ]] && kill -TERM "$child_pid" 2>/dev/null || true
  exit 0
}
trap stop EXIT INT TERM

while true; do
  "$runner" &
  child_pid=$!
  wait "$child_pid" || true
  child_pid=""
  sleep 5
done
