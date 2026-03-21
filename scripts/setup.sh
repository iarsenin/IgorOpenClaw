#!/usr/bin/env bash
set -euo pipefail

# IgorOpenClaw — Setup Script
# Symlinks repo config and workspace into ~/.openclaw/ and installs the daemon.
# Run from the repo root: bash scripts/setup.sh

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OPENCLAW_DIR="$HOME/.openclaw"
WORKSPACE_DIR="$OPENCLAW_DIR/workspace"
CRON_DIR="$OPENCLAW_DIR/cron"

echo "=== IgorOpenClaw Setup ==="
echo "Repo: $REPO_DIR"
echo "OpenClaw dir: $OPENCLAW_DIR"
echo ""

# --- Check prerequisites ---
if ! command -v node &>/dev/null; then
    echo "ERROR: Node.js not found. Install it first:"
    echo "  brew install node@22"
    exit 1
fi

NODE_VERSION=$(node -v | sed 's/v//' | cut -d. -f1)
if [ "$NODE_VERSION" -lt 22 ]; then
    echo "ERROR: Node.js 22+ required. Found: $(node -v)"
    echo "  brew install node@22"
    exit 1
fi

if ! command -v openclaw &>/dev/null; then
    echo "ERROR: OpenClaw not found. Install it first:"
    echo "  npm install -g openclaw@latest"
    exit 1
fi

# --- Check .env exists ---
if [ ! -f "$REPO_DIR/.env" ]; then
    echo "WARNING: .env file not found."
    echo "  cp .env.example .env"
    echo "  Then edit .env with your real API keys."
    echo ""
fi

# --- Create directories ---
mkdir -p "$OPENCLAW_DIR"
mkdir -p "$CRON_DIR"

# --- Generate config from template (secrets injected from .env) ---
TEMPLATE="$REPO_DIR/config/openclaw.json.template"
TARGET_CONFIG="$OPENCLAW_DIR/openclaw.json"
if [ ! -f "$TEMPLATE" ]; then
    echo "ERROR: config/openclaw.json.template not found"
    exit 1
fi
if [ -e "$TARGET_CONFIG" ]; then
    BACKUP="$TARGET_CONFIG.backup.$(date +%s)"
    echo "Backing up existing config to $BACKUP"
    cp "$TARGET_CONFIG" "$BACKUP"
fi
cp "$TEMPLATE" "$TARGET_CONFIG"
if [ -n "${OPENCLAW_AUTH_TOKEN:-}" ]; then
    sed -i '' "s|__OPENCLAW_AUTH_TOKEN__|$OPENCLAW_AUTH_TOKEN|g" "$TARGET_CONFIG"
    echo "Generated: openclaw.json (token injected from .env)"
else
    echo "WARNING: OPENCLAW_AUTH_TOKEN not set in .env — token placeholder left in config"
fi
chmod 600 "$TARGET_CONFIG"

# --- Symlink workspace ---
if [ -e "$WORKSPACE_DIR" ] && [ ! -L "$WORKSPACE_DIR" ]; then
    BACKUP="$WORKSPACE_DIR.backup.$(date +%s)"
    echo "Backing up existing workspace to $BACKUP"
    mv "$WORKSPACE_DIR" "$BACKUP"
fi
ln -sfn "$REPO_DIR/workspace" "$WORKSPACE_DIR"
echo "Linked: workspace/ -> $WORKSPACE_DIR"

# --- Symlink cron jobs ---
if [ -f "$REPO_DIR/config/cron/jobs.json" ]; then
    ln -sfn "$REPO_DIR/config/cron/jobs.json" "$CRON_DIR/jobs.json"
    echo "Linked: config/cron/jobs.json -> $CRON_DIR/jobs.json"
fi

# --- Source .env into current shell ---
if [ -f "$REPO_DIR/.env" ]; then
    set -a
    source "$REPO_DIR/.env"
    set +a
    echo "Loaded environment variables from .env"
fi

# --- Install daemon if not already installed ---
echo ""
echo "Checking daemon status..."
if openclaw gateway status &>/dev/null; then
    echo "Gateway is already running. Restarting..."
    openclaw gateway restart
else
    echo "Installing and starting the OpenClaw daemon..."
    openclaw gateway install
fi

# --- Re-inject config if gateway install overwrote it ---
if [ -f "$OPENCLAW_DIR/openclaw.json" ]; then
    if ! grep -q "$OPENCLAW_AUTH_TOKEN" "$OPENCLAW_DIR/openclaw.json" 2>/dev/null; then
        echo "Re-injecting config (gateway install may have overwritten it)..."
        cp "$TEMPLATE" "$TARGET_CONFIG"
        if [ -n "${OPENCLAW_AUTH_TOKEN:-}" ]; then
            sed -i '' "s|__OPENCLAW_AUTH_TOKEN__|$OPENCLAW_AUTH_TOKEN|g" "$TARGET_CONFIG"
        fi
        chmod 600 "$TARGET_CONFIG"
    fi
fi

# --- Inject API keys into LaunchAgent plist ---
PLIST="$HOME/Library/LaunchAgents/ai.openclaw.gateway.plist"
if [ -f "$PLIST" ] && [ -f "$REPO_DIR/.env" ]; then
    echo "Injecting API keys into LaunchAgent plist..."
    for VAR in OPENAI_API_KEY GEMINI_API_KEY GMAIL_USER GMAIL_APP_PASSWORD ALPHA_VANTAGE_KEY TZ; do
        VAL="${!VAR}"
        if [ -n "$VAL" ]; then
            /usr/libexec/PlistBuddy -c "Delete :EnvironmentVariables:$VAR" "$PLIST" 2>/dev/null || true
            /usr/libexec/PlistBuddy -c "Add :EnvironmentVariables:$VAR string $VAL" "$PLIST"
        fi
    done
    echo "Reloading LaunchAgent..."
    launchctl unload "$PLIST" 2>/dev/null || true
    sleep 2
    launchctl load "$PLIST"
    sleep 3
fi

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "  1. Edit .env with your real API keys (if not done)"
echo "  2. Update config/openclaw.json with your WhatsApp number"
echo "  3. Run: openclaw channels add --channel whatsapp"
echo "  4. Verify: openclaw gateway status"
echo "  5. Open dashboard: openclaw dashboard"
