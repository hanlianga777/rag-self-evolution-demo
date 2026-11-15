#!/bin/bash
# 5174 = 上一版正式站；5175 = snapshot-032-ui-20261115 的 032 版只读参考。
# 只读导出 origin 快照引用到 ~/RAG归档/前端对照-032，API 经 8011 代理到 8010。
# 启动：bash scripts/start_compare_old_ui.sh；停止：加 stop。
set -euo pipefail
exec python3 "$(cd "$(dirname "$0")" && pwd)/compare_old_ui.py" "${1:-start}"
