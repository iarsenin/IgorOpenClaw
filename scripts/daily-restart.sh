#!/usr/bin/env bash
# Daily OpenClaw gateway restart — called by launchd at 4:00 AM ET
set -euo pipefail

export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"

LOG="$HOME/.openclaw/logs/daily-restart.log"

echo "$(date '+%Y-%m-%d %H:%M:%S') [daily-restart] stopping gateway…" >> "$LOG"
openclaw gateway stop  2>> "$LOG" || true
sleep 3

# Ensure the dedicated OpenClaw Chrome profile is running with remote debugging
pkill -f "user-data-dir=$HOME/.openclaw/chrome-profile" 2>/dev/null || true
sleep 1
mkdir -p "$HOME/.openclaw/chrome-profile"
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --remote-debugging-port=9222 \
  --user-data-dir="$HOME/.openclaw/chrome-profile" \
  --no-first-run --headless=new 2>>"$LOG" &
sleep 3
echo "$(date '+%Y-%m-%d %H:%M:%S') [daily-restart] chrome debug profile started" >> "$LOG"

echo "$(date '+%Y-%m-%d %H:%M:%S') [daily-restart] starting gateway…" >> "$LOG"
openclaw gateway start 2>> "$LOG"
echo "$(date '+%Y-%m-%d %H:%M:%S') [daily-restart] done" >> "$LOG"
