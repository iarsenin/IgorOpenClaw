#!/usr/bin/env bash
# Daily OpenClaw gateway restart — called by launchd at 4:00 AM ET
set -euo pipefail

export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"

LOG="$HOME/.openclaw/logs/daily-restart.log"
PLIST="$HOME/Library/LaunchAgents/ai.openclaw.gateway.plist"
RESET_SESSIONS="$HOME/.openclaw/scripts/reset-main-sessions.py"
mkdir -p "$(dirname "$LOG")"

echo "$(date '+%Y-%m-%d %H:%M:%S') [daily-restart] restarting gateway..." >> "$LOG"

if [ -x "$RESET_SESSIONS" ]; then
    python3 "$RESET_SESSIONS" >> "$LOG" 2>&1 || true
fi

launchctl unload "$PLIST" 2>> "$LOG" || true
sleep 3
launchctl load "$PLIST" 2>> "$LOG"

sleep 5
openclaw gateway status 2>> "$LOG" | head -1 >> "$LOG"
echo "$(date '+%Y-%m-%d %H:%M:%S') [daily-restart] done" >> "$LOG"
