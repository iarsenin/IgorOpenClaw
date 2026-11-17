#!/usr/bin/env bash
set -euo pipefail

# IgorOpenClaw - Uninstall Script
# Removes generated local state and stops the daemon. Does NOT delete the repo or .env.
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
    openclaw plugins uninstall sum-command --force 2>/dev/null || true
    openclaw plugins uninstall transcribe-command --force 2>/dev/null || true
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

# --- Remove runtime workspace / generated cron store ---
if [ -L "$OPENCLAW_DIR/workspace" ]; then
    rm "$OPENCLAW_DIR/workspace"
    echo "Removed workspace symlink: $OPENCLAW_DIR/workspace"
elif [ -d "$OPENCLAW_DIR/workspace" ]; then
    rm -rf "$OPENCLAW_DIR/workspace"
    echo "Removed runtime workspace: $OPENCLAW_DIR/workspace"
fi
if [ -e "$OPENCLAW_DIR/cron/jobs.json" ]; then
    rm -f "$OPENCLAW_DIR/cron/jobs.json"
    echo "Removed live cron store: $OPENCLAW_DIR/cron/jobs.json"
fi
if [ -e "$OPENCLAW_DIR/scripts/daily-restart.sh" ]; then
    rm -f "$OPENCLAW_DIR/scripts/daily-restart.sh"
    echo "Removed copied restart script: $OPENCLAW_DIR/scripts/daily-restart.sh"
fi

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
