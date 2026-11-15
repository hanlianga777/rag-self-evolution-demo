#!/bin/bash
set -euo pipefail
exec python3 "$(cd "$(dirname "$0")" && pwd)/compare_old_ui.py" "${1:-start}"
