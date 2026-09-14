#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
log_dir="$project_dir/.demo-logs"
restart="${RAG_RESTART:-0}"

listener_pid() {
  local port="$1" pids
  pids="$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null | sort -u)"
  [[ "$(printf '%s\n' "$pids" | sed '/^$/d' | wc -l | tr -d ' ')" == "1" ]] || return 1
  printf '%s\n' "$pids"
}

started_at() { LC_ALL=C ps -p "$1" -o lstart= 2>/dev/null | sed 's/^[[:space:]]*//;s/[[:space:]]*$//'; }

record_is_running() {
  local record="$1" pid started actual_started
  [[ -f "$record" ]] || return 1
  IFS='|' read -r pid started < "$record" || return 1
  actual_started="$(started_at "$pid")"
  kill -0 "$pid" 2>/dev/null && [[ -n "$started" && "$started" == "$actual_started" ]]
}

wait_for_stop() {
  local pid="$1"
  for _ in {1..30}; do kill -0 "$pid" 2>/dev/null || return 0; sleep 0.2; done
  return 1
}

start_service() {
  local name="$1" port="$2" runner="$3" record="$log_dir/$1.pid" listener pid
  if record_is_running "$record"; then
    if [[ "$restart" != "1" ]]; then return; fi
    IFS='|' read -r pid _ < "$record"
    kill -TERM "$pid"
    wait_for_stop "$pid" || { echo "[$name] recorded supervisor did not stop" >&2; exit 1; }
  fi

  listener="$(listener_pid "$port" 2>/dev/null || true)"
  if [[ -n "$listener" ]]; then
    echo "[$name] refusing to replace unknown listener on port $port (PID $listener)" >&2
    ps -p "$listener" -o command= >&2 || true
    exit 1
  fi
  rm -f "$record"
  nohup "$runner" >"$log_dir/$name.log" 2>"$log_dir/$name.error.log" < /dev/null &
  pid=$!
  printf '%s|%s\n' "$pid" "$(started_at "$pid")" > "$record"
}

mkdir -p "$log_dir"
start_service api 8010 "$project_dir/scripts/supervise_api.sh"
start_service web 5174 "$project_dir/scripts/supervise_web.sh"
