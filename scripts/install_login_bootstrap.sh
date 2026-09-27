#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
agents_dir="$HOME/Library/LaunchAgents"
label="com.zhanghaohan.rag-evolution.login"
plist="$agents_dir/$label.plist"
domain="gui/$(id -u)"

mkdir -p "$agents_dir"
expected="$(cat <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$label</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/open</string><string>-g</string><string>-a</string><string>Terminal</string>
    <string>$project_dir/scripts/login_start.command</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
</dict>
</plist>
EOF
)"
if [[ -f "$plist" ]] && printf '%s\n' "$expected" | cmp -s - "$plist" && launchctl print "$domain/$label" >/dev/null 2>&1; then
  exit 0
fi
for stale_label in com.zhanghaohan.rag-evolution.api com.zhanghaohan.rag-evolution.web "$label"; do
  launchctl print "$domain/$stale_label" >/dev/null 2>&1 && launchctl bootout "$domain/$stale_label"
done
printf '%s\n' "$expected" > "$plist"
plutil -lint "$plist" >/dev/null
launchctl bootstrap "$domain" "$plist"
