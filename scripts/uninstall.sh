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

# --- Remove symlinks (only if they are symlinks, not real files) ---
for LINK in "$OPENCLAW_DIR/openclaw.json" "$OPENCLAW_DIR/workspace" "$OPENCLAW_DIR/cron/jobs.json"; do
    if [ -L "$LINK" ]; then
        rm "$LINK"
        echo "Removed symlink: $LINK"
    fi
done

echo ""
echo "=== Uninstall Complete ==="
echo ""
echo "The OpenClaw installation and your .env are still on disk."
echo "To fully remove OpenClaw: npm uninstall -g openclaw"
echo "To remove config dir: rm -rf ~/.openclaw"
