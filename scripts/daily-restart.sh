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

# --- Temp/state cleanup -----------------------------------------------------
# Transcribe scratch: abandoned workdirs (failed runs where email never sent).
# Successful runs self-delete after emailing; anything left is >1 day stale.
TRANSCRIPTS_DIR="$HOME/.openclaw/state/transcripts"
if [ -d "$TRANSCRIPTS_DIR" ]; then
    find "$TRANSCRIPTS_DIR" -mindepth 1 -maxdepth 1 -type d -mtime +1 \
        -exec rm -rf {} + 2>> "$LOG" || true
    echo "$(date '+%Y-%m-%d %H:%M:%S') [daily-restart] swept transcripts older than 1 day" >> "$LOG"
fi

# Gateway logs: keep 7 days for debugging, prune older rotations.
GATEWAY_LOG_DIR="/tmp/openclaw"
if [ -d "$GATEWAY_LOG_DIR" ]; then
    find "$GATEWAY_LOG_DIR" -maxdepth 1 -type f -name 'openclaw-*.log*' -mtime +7 \
        -exec rm -f {} + 2>> "$LOG" || true
    echo "$(date '+%Y-%m-%d %H:%M:%S') [daily-restart] pruned gateway logs older than 7 days" >> "$LOG"
fi

# Own restart log: keep it from growing forever (>5MB → truncate to last 2000 lines).
if [ -f "$LOG" ] && [ "$(wc -c < "$LOG" 2>/dev/null || echo 0)" -gt 5242880 ]; then
    tail -n 2000 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
fi
# ---------------------------------------------------------------------------

if [ -x "$RESET_SESSIONS" ]; then
    python3 "$RESET_SESSIONS" >> "$LOG" 2>&1 || true
fi

launchctl unload "$PLIST" 2>> "$LOG" || true
sleep 3
launchctl load "$PLIST" 2>> "$LOG"

sleep 5
openclaw gateway status 2>> "$LOG" | head -1 >> "$LOG"
echo "$(date '+%Y-%m-%d %H:%M:%S') [daily-restart] done" >> "$LOG"
