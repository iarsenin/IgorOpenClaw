#!/usr/bin/env bash
set -euo pipefail

# IgorOpenClaw — Uninstall Script
# Removes symlinks and stops the daemon. Does NOT delete the repo or .env.
# Run from the repo root: bash scripts/uninstall.sh

OPENCLAW_DIR="$HOME/.openclaw"

echo "=== IgorOpenClaw Uninstall ==="
echo ""

# --- Stop daemon and unload LaunchAgent ---
PLIST="$HOME/Library/LaunchAgents/ai.openclaw.gateway.plist"
DAILY_RESTART_PLIST="$HOME/Library/LaunchAgents/ai.openclaw.daily-restart.plist"
if command -v openclaw &>/dev/null; then
    echo "Stopping OpenClaw gateway..."
    openclaw gateway stop 2>/dev/null || true
fi
if [ -f "$PLIST" ]; then
    launchctl unload "$PLIST" 2>/dev/null || true
    rm -f "$PLIST"
    echo "Removed LaunchAgent: $PLIST"
fi
if [ -f "$DAILY_RESTART_PLIST" ]; then
    launchctl unload "$DAILY_RESTART_PLIST" 2>/dev/null || true
    rm -f "$DAILY_RESTART_PLIST"
    echo "Removed LaunchAgent: $DAILY_RESTART_PLIST"
fi

# --- Remove symlinks ---
for LINK in "$OPENCLAW_DIR/workspace" "$OPENCLAW_DIR/cron/jobs.json"; do
    if [ -L "$LINK" ]; then
        rm "$LINK"
        echo "Removed symlink: $LINK"
    fi
done

# --- Remove generated config (created by setup.sh cp, not a symlink) ---
if [ -f "$OPENCLAW_DIR/openclaw.json" ] && [ ! -L "$OPENCLAW_DIR/openclaw.json" ]; then
    rm "$OPENCLAW_DIR/openclaw.json"
    echo "Removed generated config: $OPENCLAW_DIR/openclaw.json"
fi

echo ""
echo "=== Uninstall Complete ==="
echo ""
echo "The OpenClaw npm package and your .env are still on disk."
echo "To fully remove OpenClaw: npm uninstall -g openclaw"
echo "To remove config dir:     rm -rf ~/.openclaw"
