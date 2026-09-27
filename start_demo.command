#!/bin/bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
URL="http://127.0.0.1:5174"

startup_error=0
"$PROJECT_DIR/scripts/start_detached_services.sh" || startup_error=1
if [[ "$startup_error" == 0 ]]; then
  "$PROJECT_DIR/scripts/install_login_bootstrap.sh" || startup_error=1
fi
if [[ "$startup_error" == 0 ]]; then
  for _ in {1..60}; do
    if curl -fsS --max-time 2 http://127.0.0.1:8010/api/overview >/dev/null 2>&1 && curl -fsS --max-time 2 "$URL" >/dev/null 2>&1; then
      if "$PROJECT_DIR/scripts/start_detached_services.sh"; then open "$URL"; exit 0; fi
      break
    fi
    sleep 1
  done
fi

echo 'Demo did not become ready.' >&2
for service in api web; do
  if [[ "$service" == api ]]; then port=8010; path=/api/overview; else port=5174; path=; fi
  if curl -fsS --max-time 2 "http://127.0.0.1:$port$path" >/dev/null 2>&1; then ready=Ready; else ready='Not Ready'; fi
  pids="$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null | sort -u || true)"
  echo "$service $port: $ready; listener PID: ${pids:-none}" >&2
  echo "Last 20 lines of $service.error.log:" >&2
  if [[ -f "$PROJECT_DIR/.demo-logs/$service.error.log" ]]; then tail -n 20 "$PROJECT_DIR/.demo-logs/$service.error.log" >&2; else echo '(no log)' >&2; fi
done
exit 1
