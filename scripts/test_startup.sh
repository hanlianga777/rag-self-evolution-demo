#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
export TEST_PROJECT="$tmp/测试项目" TEST_STATE="$tmp/state" TEST_OPEN="$tmp/opened" HOME="$tmp/home"
mkdir -p "$TEST_PROJECT/scripts" "$TEST_PROJECT/frontend" "$TEST_STATE" "$tmp/bin" "$HOME"
cp "$root/start_demo.command" "$TEST_PROJECT/"
cp "$root/scripts/"{start_detached_services.sh,install_login_bootstrap.sh,login_start.command} "$TEST_PROJECT/scripts/"
cat > "$TEST_PROJECT/scripts/supervise_api.sh" <<'EOF'
#!/usr/bin/env bash
touch "$TEST_STATE/api"
EOF
cat > "$TEST_PROJECT/scripts/supervise_web.sh" <<'EOF'
#!/usr/bin/env bash
touch "$TEST_STATE/web"
EOF
chmod +x "$TEST_PROJECT/scripts/"*.sh "$TEST_PROJECT/scripts/login_start.command"

cat > "$tmp/bin/lsof" <<'EOF'
#!/usr/bin/env bash
case "$*" in
  *-tiTCP:8010*) [[ -e "$TEST_STATE/api" || -e "$TEST_STATE/unknown-api" ]] && echo 101 || : ;;
  *-tiTCP:5174*) [[ -e "$TEST_STATE/web" ]] && echo 202 || : ;;
  *'-p 101'*'-d cwd'*) printf 'p101\nfcwd\nn%s\n' "$([[ -e "$TEST_STATE/unknown-api" ]] && echo /tmp/other || echo "$TEST_PROJECT")" ;;
  *'-p 202'*'-d cwd'*) printf 'p202\nfcwd\nn%s/frontend\n' "$TEST_PROJECT" ;;
esac
EOF
cat > "$tmp/bin/ps" <<'EOF'
#!/usr/bin/env bash
case "$*" in
  *'lstart='*) echo 'Sun Sep 27 12:25:25 2026' ;;
  *'command='*)
    case "$*" in
      *'-p 101'*) [[ -e "$TEST_STATE/unknown-api" ]] && echo '/usr/bin/other --port 8010' || echo 'python3 -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8010' ;;
      *'-p 202'*) echo 'node ./node_modules/.bin/vite --host 127.0.0.1 --port 5174 --strictPort' ;;
    esac ;;
esac
EOF
cat > "$tmp/bin/curl" <<'EOF'
#!/usr/bin/env bash
case "$*" in
  *8010*) [[ -e "$TEST_STATE/api" ]] ;;
  *5174*) [[ -e "$TEST_STATE/web" ]] ;;
  *) exit 1 ;;
esac
EOF
cat > "$tmp/bin/open" <<'EOF'
#!/usr/bin/env bash
echo "$*" >> "$TEST_OPEN"
EOF
cat > "$tmp/bin/launchctl" <<'EOF'
#!/usr/bin/env bash
case "$1" in
  print) [[ -e "$TEST_STATE/agent" ]] ;;
  bootout) rm -f "$TEST_STATE/agent" ;;
  bootstrap) touch "$TEST_STATE/agent"; echo bootstrap >> "$TEST_STATE/agent-operations" ;;
esac
EOF
cat > "$tmp/bin/plutil" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
chmod +x "$tmp/bin/"*
export PATH="$tmp/bin:$PATH"

check() { [[ "$1" == "$2" ]] || { echo "FAIL: $3 ($1 != $2)" >&2; exit 1; }; }
wait_state() { for _ in {1..20}; do [[ -e "$TEST_STATE/$1" ]] && return 0; sleep 0.1; done; return 1; }
reset_state() { rm -f "$TEST_STATE"/* "$TEST_OPEN" "$TEST_PROJECT/.demo-logs/"*.pid; }
starter="$TEST_PROJECT/scripts/start_detached_services.sh"

"$starter"
wait_state api || { echo 'FAIL: A API did not start' >&2; exit 1; }
wait_state web || { echo 'FAIL: A Web did not start' >&2; exit 1; }
reset_state; touch "$TEST_STATE/api"
"$starter"
wait_state web || { echo 'FAIL: B Web did not start' >&2; exit 1; }
reset_state; touch "$TEST_STATE/web"
"$starter"
wait_state api || { echo 'FAIL: C API did not start' >&2; exit 1; }
reset_state; touch "$TEST_STATE/api" "$TEST_STATE/web"
"$starter"
check "$(test ! -e "$TEST_PROJECT/.demo-logs/api.pid" && echo yes)" yes 'D API was restarted'
reset_state; touch "$TEST_STATE/unknown-api"
if "$starter" >"$tmp/unknown.out" 2>&1; then echo 'FAIL: E unknown listener accepted' >&2; exit 1; fi
grep -q 'PID.*101' "$tmp/unknown.out"
grep -q '/tmp/other' "$tmp/unknown.out"
wait_state web || { echo 'FAIL: E Web was not handled independently' >&2; exit 1; }
reset_state; touch "$TEST_STATE/api" "$TEST_STATE/web"
printf '99999|Sun Sep 27 12:25:25 2026\n' > "$TEST_PROJECT/.demo-logs/api.pid"
"$starter"
check "$(test -e "$TEST_PROJECT/.demo-logs/api.pid" && echo yes)" yes 'F stale record was unexpectedly removed'
"$TEST_PROJECT/start_demo.command"
check "$(cat "$TEST_OPEN")" 'http://127.0.0.1:5174' 'G browser did not open after readiness'
"$TEST_PROJECT/start_demo.command"
check "$(wc -l < "$TEST_STATE/agent-operations" | tr -d ' ')" 1 'G LaunchAgent was bootstrapped twice'
check "$(wc -l < "$TEST_OPEN" | tr -d ' ')" 2 'G browser was not opened on second click'
reset_state; touch "$TEST_STATE/unknown-api"
if "$TEST_PROJECT/start_demo.command" >"$tmp/blocked.out" 2>&1; then echo 'FAIL: browser opened with an unknown listener' >&2; exit 1; fi
check "$(test ! -e "$TEST_OPEN" && echo yes)" yes 'browser opened before both services were confirmed'
grep -q 'api 8010: Not Ready' "$tmp/blocked.out"
grep -q 'web 5174:' "$tmp/blocked.out"
echo 'PASS: startup scenarios A-G'
