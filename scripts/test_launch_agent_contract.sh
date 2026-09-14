#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

api_runner="$root/scripts/run_api_service.sh"
web_runner="$root/scripts/run_web_service.sh"
starter="$root/scripts/start_detached_services.sh"
api_supervisor="$root/scripts/supervise_api.sh"
web_supervisor="$root/scripts/supervise_web.sh"
installer="$root/scripts/install_login_bootstrap.sh"

[[ -x "$api_runner" ]] || fail "API launchd runner is missing or not executable"
[[ -x "$web_runner" ]] || fail "web launchd runner is missing or not executable"
[[ -x "$starter" ]] || fail "detached service starter is missing or not executable"
[[ -x "$api_supervisor" ]] || fail "API supervisor is missing or not executable"
[[ -x "$web_supervisor" ]] || fail "web supervisor is missing or not executable"
[[ -x "$installer" ]] || fail "login LaunchAgent installer is missing or not executable"

grep -Fq 'app.build_index --if-needed' "$api_runner" || fail "API runner does not preserve the incremental index check"
grep -Fq 'exec python3 -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8010' "$api_runner" || fail "API runner is not an exec-owned loopback uvicorn process"
grep -Fq 'exec ./node_modules/.bin/vite --host 127.0.0.1 --port 5174 --strictPort' "$web_runner" || fail "web runner is not an exec-owned strict loopback Vite process"

grep -Fq 'LC_ALL=C ps -p "$1" -o lstart=' "$starter" || fail "recorded supervisor timestamps are locale-dependent"
grep -Fq 'while true' "$api_supervisor" || fail "API does not restart after an unexpected exit"
grep -Fq 'while true' "$web_supervisor" || fail "web does not restart after an unexpected exit"
grep -Fq 'nohup "$runner"' "$starter" || fail "services are not detached from the Finder terminal"
grep -Fq 'RAG_RESTART' "$starter" || fail "Finder refresh cannot restart recorded services"
grep -Fq 'RAG_RESTART=1' "$root/scripts/login_start.command" || fail "login bootstrap does not refresh recorded services"
if grep -Fq 'start_detached_services.sh' "$root/start_demo.command"; then fail "Finder launcher bypasses the login bootstrap and can race it"; fi
grep -Fq 'com.zhanghaohan.rag-evolution.login' "$installer" || fail "login LaunchAgent label is missing"
grep -Fq '<string>Terminal</string>' "$installer" || fail "login LaunchAgent must retain Documents permission via Terminal"
grep -Fq '<key>RunAtLoad</key>' "$installer" || fail "LaunchAgents do not start at login"
grep -Fq 'launchctl bootstrap' "$installer" || fail "installer does not register user LaunchAgents"
grep -Fq 'launchctl bootout' "$installer" || fail "installer does not reload only its own LaunchAgents"

pass "LaunchAgent runners and installer preserve the local runtime contract"
