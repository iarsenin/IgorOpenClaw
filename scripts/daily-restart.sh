#!/usr/bin/env bash
# Daily OpenClaw gateway restart — called by launchd at 4:00 AM ET
set -euo pipefail

export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"

LOG="$HOME/.openclaw/logs/daily-restart.log"

echo "$(date '+%Y-%m-%d %H:%M:%S') [daily-restart] stopping gateway…" >> "$LOG"
openclaw gateway stop  2>> "$LOG" || true
sleep 3
echo "$(date '+%Y-%m-%d %H:%M:%S') [daily-restart] starting gateway…" >> "$LOG"
openclaw gateway start 2>> "$LOG"
echo "$(date '+%Y-%m-%d %H:%M:%S') [daily-restart] done" >> "$LOG"
