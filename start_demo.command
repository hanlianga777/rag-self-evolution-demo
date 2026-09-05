#!/bin/bash
cd "$(dirname "$0")"

if lsof -nP -iTCP:8010 -sTCP:LISTEN >/dev/null 2>&1 && lsof -nP -iTCP:5174 -sTCP:LISTEN >/dev/null 2>&1; then
  open "http://127.0.0.1:5174"
  exit 0
fi

./start.sh &
launcher_pid=$!
for _ in {1..20}; do
  curl -fsS http://127.0.0.1:5174 >/dev/null 2>&1 && { open "http://127.0.0.1:5174"; break; }
  sleep 1
done
wait "$launcher_pid"
