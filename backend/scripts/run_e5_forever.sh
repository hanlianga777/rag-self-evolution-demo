#!/usr/bin/env bash
# E5 运行器外层守护：网络瞬断时自动等待后从断点重启 run_e5_unattended.py。
# 只对 "Provider 调用失败" 且属于网络类瞬断的错误重试，其他错误（规则、身份、预算等）立即停。
# 运行器本身支持断点续跑：已落库的回答与判分直接沿用，不重复花钱；费用仍受 120b 账本 USD 3 上限约束。
# 用法（在仓库根目录）：nohup bash backend/scripts/run_e5_forever.sh >> backend/data/run_e5.log 2>&1 &
set -u

BACKEND="$(cd "$(dirname "$0")/.." && pwd)"
DATA="$BACKEND/data"
PROGRESS="${E5_PROGRESS_FILE:-$DATA/run_e5_progress.json}"
RUNNER_CMD="${E5_RUNNER_CMD:-python3 $BACKEND/scripts/run_e5_unattended.py}"
MAX_RESTARTS="${E5_MAX_RESTARTS:-8}"
BACKOFF=(${E5_BACKOFF:-60 120 240 480 600 600 600 600})
LOCK="$DATA/task120b/run_forever.lock"

mkdir -p "$(dirname "$LOCK")"
exec 9>"$LOCK"
if ! flock -n 9 2>/dev/null; then
  # macOS 默认没有 flock 命令时退化为 mkdir 锁
  if command -v flock >/dev/null 2>&1; then
    echo "[forever] 已有一个守护在运行，退出"; exit 0
  fi
  if ! mkdir "$LOCK.d" 2>/dev/null; then
    echo "[forever] 已有一个守护在运行（$LOCK.d 存在），退出"; exit 0
  fi
  trap 'rmdir "$LOCK.d" 2>/dev/null' EXIT
fi

progress_field() {
  python3 - "$PROGRESS" "$1" <<'PY'
import json, sys
try:
    data = json.load(open(sys.argv[1], encoding='utf-8'))
except Exception:
    print(''); sys.exit(0)
value = data.get(sys.argv[2])
print('' if value is None else value)
PY
}

is_transient() {
  local message="$1"
  [[ "$message" == *"Provider 调用失败"* ]] || return 1
  local pattern
  for pattern in "SSL" "EOF" "timed out" "timeout" "超时" "Connection reset" "connection reset" \
                 "Remote end closed" "RemoteDisconnected" "Connection aborted" "Temporary failure" \
                 "Name or service not known" "nodename nor servname" "传输异常" \
                 " 429" " 502" " 503" " 504" "status_code=429" "status_code=502" "status_code=503" "status_code=504"; do
    [[ "$message" == *"$pattern"* ]] && return 0
  done
  return 1
}

attempt=0
while true; do
  echo "[forever] $(date '+%m-%d %H:%M:%S') 启动运行器（连续瞬断计数 $attempt）"
  started=$(date +%s)
  $RUNNER_CMD
  code=$?
  # 本次跑了 10 分钟以上才断，说明期间有进展，连续瞬断计数清零
  if [ $(( $(date +%s) - started )) -ge "${E5_PROGRESS_RESET_SECONDS:-600}" ]; then attempt=0; fi
  status="$(progress_field status)"
  error="$(progress_field error)"
  echo "[forever] $(date '+%m-%d %H:%M:%S') 运行器退出 code=$code status=$status"
  if [ "$code" -eq 0 ]; then
    echo "[forever] 运行器正常结束（status=$status），守护退出"; exit 0
  fi
  if ! is_transient "$error"; then
    echo "[forever] 非网络瞬断错误，停止等待人工处理：$error"; exit 1
  fi
  if [ "$attempt" -ge "$MAX_RESTARTS" ]; then
    echo "[forever] 网络瞬断已重启 $MAX_RESTARTS 次仍失败，停止：$error"; exit 1
  fi
  wait_seconds="${BACKOFF[$attempt]:-600}"
  attempt=$((attempt + 1))
  echo "[forever] 网络瞬断：$error；$wait_seconds 秒后从断点重启"
  sleep "$wait_seconds"
done
