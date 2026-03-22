#!/usr/bin/env bash
set -euo pipefail

# IgorOpenClaw — Uninstall Script
# Removes symlinks and stops the daemon. Does NOT delete the repo or .env.
# Run from the repo root: bash scripts/uninstall.sh

OPENCLAW_DIR="$HOME/.openclaw"

echo "=== IgorOpenClaw Uninstall ==="
echo ""

# --- Stop daemon ---
if command -v openclaw &>/dev/null; then
    echo "Stopping OpenClaw gateway..."
    openclaw gateway stop 2>/dev/null || true
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
echo "The OpenClaw installation and your .env are still on disk."
echo "To fully remove OpenClaw: npm uninstall -g openclaw"
echo "To remove config dir: rm -rf ~/.openclaw"
