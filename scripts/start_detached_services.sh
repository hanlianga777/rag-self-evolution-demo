#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
log_dir="$project_dir/.demo-logs"
restart="${RAG_RESTART:-0}"

listener_pids() { lsof -tiTCP:"$1" -sTCP:LISTEN 2>/dev/null | sort -u || true; }
started_at() { LC_ALL=C ps -p "$1" -o lstart= 2>/dev/null | sed 's/^[[:space:]]*//;s/[[:space:]]*$//'; }
process_command() { ps -p "$1" -o command= 2>/dev/null || true; }
process_cwd() {
  local raw
  raw="$(lsof -a -p "$1" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p' | head -1)"
  printf '%b' "$raw"
}
healthy() {
  local url="http://127.0.0.1:$2"
  [[ "$1" == api ]] && url="$url/api/overview"
  curl -fsS --max-time 2 "$url" >/dev/null 2>&1
}
current_project_listener() {
  local name="$1" pid="$3" command cwd expected_dir
  command="$(process_command "$pid")"
  cwd="$(process_cwd "$pid")"
  expected_dir="$project_dir"
  [[ "$name" == web ]] && expected_dir="$project_dir/frontend"
  [[ "$cwd" == "$expected_dir" ]] || return 1
  if [[ "$name" == api ]]; then
    [[ "$command" == *'-m uvicorn app.main:app --app-dir backend'* && "$command" == *'--port 8010'* ]]
  else
    [[ "$command" == *'vite'* && "$command" == *'--port 5174'* ]]
  fi
}

record_is_running() {
  local record="$1" runner="$2" pid started actual_started
  [[ -f "$record" ]] || return 1
  IFS='|' read -r pid started < "$record" || return 1
  actual_started="$(started_at "$pid")"
  kill -0 "$pid" 2>/dev/null && [[ -n "$started" && "$started" == "$actual_started" && "$(process_command "$pid")" == *"$runner"* ]]
}

wait_for_stop() {
  local pid="$1"
  for _ in {1..30}; do kill -0 "$pid" 2>/dev/null || return 0; sleep 0.2; done
  return 1
}

wait_for_port_clear() {
  local port="$1"
  for _ in {1..30}; do [[ -z "$(listener_pids "$port")" ]] && return 0; sleep 0.2; done
  return 1
}

describe_listener() {
  local name="$1" port="$2" pid="$3"
  echo "[$name] port $port is occupied by an unknown or unhealthy process" >&2
  echo "PID: $pid" >&2
  echo "Command: $(process_command "$pid")" >&2
  echo "CWD: $(process_cwd "$pid")" >&2
  echo 'For safety this process was not terminated.' >&2
}

start_service() {
  local name="$1" port="$2" runner="$3" record="$log_dir/$1.pid" pids pid recorded
  pids="$(listener_pids "$port")"
  if [[ -n "$pids" ]]; then
    if [[ "$(printf '%s\n' "$pids" | wc -l | tr -d ' ')" != 1 ]]; then
      echo "[$name] multiple listeners on port $port: $pids; no process was terminated" >&2
      return 1
    fi
    pid="$pids"
    if ! current_project_listener "$name" "$port" "$pid"; then
      describe_listener "$name" "$port" "$pid"
      return 1
    fi
    for _ in {1..3}; do
      if [[ "$restart" != 1 ]] && healthy "$name" "$port"; then
        echo "[$name] current project service already healthy on port $port; reusing"
        return 0
      fi
      sleep 0.2
    done
    if [[ "$restart" != 1 ]]; then
      describe_listener "$name" "$port" "$pid"
      echo "[$name] set RAG_RESTART=1 to restart this confirmed project service" >&2
      return 1
    fi
    if record_is_running "$record" "$runner"; then
      IFS='|' read -r recorded _ < "$record"
      kill -TERM "$recorded"
      wait_for_stop "$recorded" || { echo "[$name] recorded supervisor did not stop after TERM" >&2; return 1; }
    else
      kill -TERM "$pid"
      wait_for_stop "$pid" || { echo "[$name] project listener did not stop after TERM" >&2; return 1; }
    fi
    wait_for_port_clear "$port" || { echo "[$name] port $port did not become free after TERM" >&2; return 1; }
  elif record_is_running "$record" "$runner"; then
    IFS='|' read -r recorded _ < "$record"
    for _ in {1..15}; do
      if healthy "$name" "$port"; then
        pids="$(listener_pids "$port")"
        if [[ "$pids" != *$'\n'* && -n "$pids" ]] && current_project_listener "$name" "$port" "$pids"; then
          echo "[$name] recorded service became ready; reusing"
          return 0
        fi
        echo "[$name] port $port became ready but is not a confirmed project listener" >&2
        return 1
      fi
      sleep 0.2
    done
    if [[ "$restart" != 1 ]]; then
      echo "[$name] recorded supervisor PID $recorded is running but port $port is not ready" >&2
      return 1
    fi
    kill -TERM "$recorded"
    wait_for_stop "$recorded" || { echo "[$name] recorded supervisor did not stop after TERM" >&2; return 1; }
  fi
  rm -f "$record"
  nohup "$runner" >"$log_dir/$name.log" 2>"$log_dir/$name.error.log" < /dev/null &
  pid=$!
  printf '%s|%s\n' "$pid" "$(started_at "$pid")" > "$record"
  echo "[$name] starting on port $port (supervisor PID $pid)"
}

mkdir -p "$log_dir"
failed=0
start_service api 8010 "$project_dir/scripts/supervise_api.sh" || failed=1
start_service web 5174 "$project_dir/scripts/supervise_web.sh" || failed=1
exit "$failed"
