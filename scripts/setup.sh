#!/usr/bin/env bash
set -euo pipefail

# IgorOpenClaw — Setup Script
# Copies config template, symlinks workspace + cron into ~/.openclaw/, installs daemon.
# Run from the repo root: bash scripts/setup.sh

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OPENCLAW_DIR="$HOME/.openclaw"
WORKSPACE_DIR="$OPENCLAW_DIR/workspace"
CRON_DIR="$OPENCLAW_DIR/cron"
PLIST="$HOME/Library/LaunchAgents/ai.openclaw.gateway.plist"
DAILY_RESTART_PLIST="$HOME/Library/LaunchAgents/ai.openclaw.daily-restart.plist"
SCRIPTS_DIR="$OPENCLAW_DIR/scripts"
LOG_DIR="$OPENCLAW_DIR/logs"

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

# --- Source .env early so token injection below works even without pre-exported vars ---
if [ -f "$REPO_DIR/.env" ]; then
    set -a
    source "$REPO_DIR/.env"
    set +a
    echo "Loaded environment variables from .env"
fi

# --- Recover critical env vars from existing LaunchAgent when .env is incomplete ---
if [ -f "$PLIST" ]; then
    for VAR in OPENAI_ADMIN_KEY VAPI_API_KEY GOG_KEYRING_PASSWORD VAPI_ASSISTANT_ID VAPI_PHONE_NUMBER_ID VAPI_PHONE_NUMBER; do
        if [ -z "${!VAR:-}" ]; then
            EXISTING=$(/usr/libexec/PlistBuddy -c "Print :EnvironmentVariables:$VAR" "$PLIST" 2>/dev/null || true)
            if [ -n "$EXISTING" ]; then
                export "$VAR=$EXISTING"
                echo "Recovered $VAR from existing LaunchAgent plist"
            fi
        fi
    done
fi

# --- Create directories ---
mkdir -p "$OPENCLAW_DIR"
mkdir -p "$CRON_DIR"
mkdir -p "$SCRIPTS_DIR"
mkdir -p "$LOG_DIR"
mkdir -p "$HOME/Library/LaunchAgents"

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

# --- Ensure local-only MEMORY.md exists ---
MEMORY_TEMPLATE="$REPO_DIR/workspace/MEMORY.template.md"
MEMORY_FILE="$REPO_DIR/workspace/MEMORY.md"
if [ ! -f "$MEMORY_FILE" ] && [ -f "$MEMORY_TEMPLATE" ]; then
    cp "$MEMORY_TEMPLATE" "$MEMORY_FILE"
    echo "Initialized local workspace/MEMORY.md from template"
fi

# --- Symlink cron jobs ---
if [ -f "$REPO_DIR/config/cron/jobs.json" ]; then
    ln -sfn "$REPO_DIR/config/cron/jobs.json" "$CRON_DIR/jobs.json"
    echo "Linked: config/cron/jobs.json -> $CRON_DIR/jobs.json"
fi

# --- Copy runtime scripts locally (Google Drive files have com.apple.provenance which blocks launchd) ---
for SCRIPT in daily-restart.sh reset-main-sessions.py; do
    if [ -f "$REPO_DIR/scripts/$SCRIPT" ]; then
        cp "$REPO_DIR/scripts/$SCRIPT" "$SCRIPTS_DIR/$SCRIPT"
        chmod +x "$SCRIPTS_DIR/$SCRIPT"
        echo "Copied: scripts/$SCRIPT -> $SCRIPTS_DIR/"
    fi
done

# --- Install daily restart LaunchAgent ---
if [ -x "$SCRIPTS_DIR/daily-restart.sh" ]; then
    cat > "$DAILY_RESTART_PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>ai.openclaw.daily-restart</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>$SCRIPTS_DIR/daily-restart.sh</string>
  </array>
  <key>RunAtLoad</key>
  <false/>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>4</integer>
    <key>Minute</key>
    <integer>0</integer>
  </dict>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
  </dict>
  <key>StandardOutPath</key>
  <string>$LOG_DIR/daily-restart.launchd.out.log</string>
  <key>StandardErrorPath</key>
  <string>$LOG_DIR/daily-restart.launchd.err.log</string>
</dict>
</plist>
EOF
    chmod 644 "$DAILY_RESTART_PLIST"
    launchctl unload "$DAILY_RESTART_PLIST" 2>/dev/null || true
    launchctl load "$DAILY_RESTART_PLIST"
    echo "Installed daily restart LaunchAgent: $DAILY_RESTART_PLIST"
fi

# --- Install daemon (creates plist if missing) ---
echo ""
echo "Checking daemon status..."
if ! openclaw gateway status &>/dev/null; then
    echo "Installing the OpenClaw daemon..."
    openclaw gateway install
fi

# --- Re-inject config if gateway install overwrote it ---
if [ -f "$OPENCLAW_DIR/openclaw.json" ]; then
    if [ -n "${OPENCLAW_AUTH_TOKEN:-}" ] && ! grep -qF "${OPENCLAW_AUTH_TOKEN}" "$OPENCLAW_DIR/openclaw.json" 2>/dev/null; then
        echo "Re-injecting config (gateway install may have overwritten it)..."
        cp "$TEMPLATE" "$TARGET_CONFIG"
        if [ -n "${OPENCLAW_AUTH_TOKEN:-}" ]; then
            sed -i '' "s|__OPENCLAW_AUTH_TOKEN__|$OPENCLAW_AUTH_TOKEN|g" "$TARGET_CONFIG"
        fi
        chmod 600 "$TARGET_CONFIG"
    fi
fi

# --- Inject API keys into LaunchAgent plist (BEFORE starting gateway) ---
if [ -f "$PLIST" ] && [ -f "$REPO_DIR/.env" ]; then
    echo "Injecting API keys into LaunchAgent plist..."
    /usr/libexec/PlistBuddy -c "Delete :EnvironmentVariables:OPENCLAW_REPO" "$PLIST" 2>/dev/null || true
    /usr/libexec/PlistBuddy -c "Add :EnvironmentVariables:OPENCLAW_REPO string '$REPO_DIR'" "$PLIST"

    MANAGED_ENV_VARS=(
        OPENAI_API_KEY
        OPENAI_ADMIN_KEY
        GOOGLE_API_KEY
        GEMINI_API_KEY
        GMAIL_USER
        GMAIL_APP_PASSWORD
        YAHOO_USER
        YAHOO_APP_PASSWORD
        ALPHA_VANTAGE_KEY
        HUGGING_FACE_TOKEN
        VAPI_API_KEY
        VAPI_ASSISTANT_ID
        VAPI_PHONE_NUMBER_ID
        VAPI_PHONE_NUMBER
        GOG_KEYRING_PASSWORD
        TZ
    )

    # Clear previously-managed vars first so removed keys do not linger forever
    # in the LaunchAgent plist and keep producing stale runtime warnings.
    for VAR in "${MANAGED_ENV_VARS[@]}"; do
        /usr/libexec/PlistBuddy -c "Delete :EnvironmentVariables:$VAR" "$PLIST" 2>/dev/null || true
    done

    if [ -n "${GOOGLE_API_KEY:-}" ] && [ -n "${GEMINI_API_KEY:-}" ]; then
        echo "NOTICE: Both GOOGLE_API_KEY and GEMINI_API_KEY are set; injecting GOOGLE_API_KEY only to avoid duplicate-provider warnings."
    fi

    for VAR in "${MANAGED_ENV_VARS[@]}"; do
        if [ "$VAR" = "GEMINI_API_KEY" ] && [ -n "${GOOGLE_API_KEY:-}" ]; then
            continue
        fi
        VAL="${!VAR:-}"
        if [ -n "$VAL" ]; then
            /usr/libexec/PlistBuddy -c "Add :EnvironmentVariables:$VAR string $VAL" "$PLIST"
        fi
    done
fi

# --- Preflight warnings for commonly-missed runtime keys ---
MISSING_CRITICAL=()
for VAR in OPENAI_ADMIN_KEY VAPI_API_KEY GOG_KEYRING_PASSWORD; do
    if ! /usr/libexec/PlistBuddy -c "Print :EnvironmentVariables:$VAR" "$PLIST" >/dev/null 2>&1; then
        MISSING_CRITICAL+=("$VAR")
    fi
done
if [ "${#MISSING_CRITICAL[@]}" -gt 0 ]; then
    echo "WARNING: Missing critical runtime env vars in LaunchAgent: ${MISSING_CRITICAL[*]}"
    echo "         Add them to .env and re-run: bash scripts/setup.sh"
fi

# --- (Re)start gateway with env vars already in plist ---
echo "Starting gateway..."
launchctl unload "$PLIST" 2>/dev/null || true
sleep 2
launchctl load "$PLIST"
sleep 3

# --- Re-assert symlinks in case gateway install/restart recreated concrete files ---
ln -sfn "$REPO_DIR/workspace" "$WORKSPACE_DIR"
ln -sfn "$REPO_DIR/config/cron/jobs.json" "$CRON_DIR/jobs.json"
echo "Verified symlinks: workspace and cron/jobs.json"

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "  1. Edit .env with your real API keys (if not done)"
echo "  2. Update config/openclaw.json.template (WhatsApp allowlist etc.), then re-run this script"
echo "  3. Run: openclaw channels add --channel whatsapp"
echo "  4. Verify: openclaw gateway status"
echo "  5. Open dashboard: openclaw dashboard"
