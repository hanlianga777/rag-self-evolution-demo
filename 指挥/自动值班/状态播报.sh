#!/usr/bin/env bash
# Default: start a detached worker; --停止: stop it; --worker: internal loop.
set -u
export LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 LC_CTYPE=en_US.UTF-8
repo="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$repo" || exit 1
local_dir="$repo/本机快照"
pid_file="$local_dir/状态播报.pid"
script="$repo/指挥/自动值班/状态播报.sh"
status_file="指挥/运行状态.md"
mkdir -p "$local_dir"

running() {
  [[ -f "$pid_file" ]] || return 1
  local pid
  pid="$(cat "$pid_file")"
  [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null &&
    ps -p "$pid" -o command= | grep -F -- "$script --worker" >/dev/null
}

case "${1:-}" in
  --停止)
    if running; then
      pid="$(cat "$pid_file")"
      kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null
      echo "已发送停止指令：$pid"
    else
      rm -f "$pid_file"
      echo "播报进程未运行"
    fi
    exit 0 ;;
  --worker) ;;
  "")
    if running; then echo "播报进程已在运行：$(cat "$pid_file")"; exit 0; fi
    if command -v setsid >/dev/null 2>&1; then
      nohup setsid bash "$script" --worker </dev/null >>"$local_dir/状态播报.log" 2>&1 &
    else
      # macOS does not ship the setsid command; use the same POSIX system call.
      nohup python3 -c 'import os,sys; os.setsid(); os.execvp("bash", ["bash", *sys.argv[1:]])' "$script" --worker </dev/null >>"$local_dir/状态播报.log" 2>&1 &
    fi
    echo "播报进程启动中：$!"
    exit 0 ;;
  *) echo "用法：$0 [--停止]" >&2; exit 2 ;;
esac

if running; then exit 0; fi
echo $$ > "$pid_file"
trap 'rm -f "$pid_file"; exit 0' TERM INT
trap '[[ "$(cat "$pid_file" 2>/dev/null)" != "$$" ]] || rm -f "$pid_file"' EXIT

publish() {
  python3 "$repo/scripts/export_run_status.py" || return 0
  # Do not commit/pull while an index lock or a previous rebase is active.
  [[ ! -e .git/index.lock && ! -d .git/rebase-merge && ! -d .git/rebase-apply ]] || return 0
  if ! git ls-files --error-unmatch -- "$status_file" >/dev/null 2>&1 ||
     ! git diff --quiet HEAD -- "$status_file"; then
    git add -- "$status_file" || return 0
    git commit -m "运行状态：自动更新 (No SPEC Change)" -- "$status_file" || return 0
  fi
  git pull --rebase --autostash && git push
  return 0
}

while :; do
  publish || true
  sleep 1200 &
  wait $! || true
done
