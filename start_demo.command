#!/bin/bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
URL="http://127.0.0.1:5174"

"$PROJECT_DIR/scripts/install_login_bootstrap.sh"
for _ in {1..60}; do
  curl -fsS http://127.0.0.1:8010/api/overview >/dev/null 2>&1 && curl -fsS "$URL" >/dev/null 2>&1 && {
    open "$URL"
    exit 0
  }
  sleep 1
done

echo "Demo did not become ready. See $PROJECT_DIR/.demo-logs/api.error.log and web.error.log" >&2
exit 1
