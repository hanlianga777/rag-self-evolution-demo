#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
RAG_RESTART=0 "$project_dir/scripts/start_detached_services.sh"
