#!/usr/bin/env bash
set -euo pipefail

# IgorOpenClaw - /sum setup.
# Run from anywhere: bash /path/to/IgorOpenClaw/scripts/setup.sh

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OPENCLAW_DIR="$HOME/.openclaw"
WORKSPACE_DIR="$OPENCLAW_DIR/workspace"
STATE_DIR="$OPENCLAW_DIR/state"
CRON_DIR="$OPENCLAW_DIR/cron"
SCRIPTS_DIR="$OPENCLAW_DIR/scripts"
LOG_DIR="$OPENCLAW_DIR/logs"
PLIST="$HOME/Library/LaunchAgents/ai.openclaw.gateway.plist"
DAILY_RESTART_PLIST="$HOME/Library/LaunchAgents/ai.openclaw.daily-restart.plist"
SUM_PLUGIN="$REPO_DIR/openclaw-plugins/sum-command"
PREFERRED_PATH="/opt/homebrew/opt/node@24/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
WHATSAPP_NPM_CACHE="$OPENCLAW_DIR/npm-cache"

export PATH="$PREFERRED_PATH:$PATH"

if [ -x "/opt/homebrew/bin/openclaw" ]; then
    OPENCLAW_BIN="/opt/homebrew/bin/openclaw"
elif command -v openclaw >/dev/null 2>&1; then
    OPENCLAW_BIN="$(command -v openclaw)"
else
    OPENCLAW_BIN=""
fi

if [ -x "/opt/homebrew/opt/node@24/bin/node" ]; then
    NODE_BIN="/opt/homebrew/opt/node@24/bin/node"
elif [ -x "/opt/homebrew/bin/node" ]; then
    NODE_BIN="/opt/homebrew/bin/node"
elif command -v node >/dev/null 2>&1; then
    NODE_BIN="$(command -v node)"
else
    NODE_BIN=""
fi

echo "=== IgorOpenClaw /sum setup ==="
echo "Repo: $REPO_DIR"
echo "OpenClaw dir: $OPENCLAW_DIR"
echo ""

if [ -z "$NODE_BIN" ] || [ ! -x "$NODE_BIN" ]; then
    echo "ERROR: Node.js 22+ is required."
    echo "Install Node 24 with: brew install node@24"
    exit 1
fi

NODE_MAJOR="$("$NODE_BIN" -v | sed 's/^v//' | cut -d. -f1)"
if [ "$NODE_MAJOR" -lt 22 ]; then
    echo "ERROR: Node.js 22+ is required. Found: $("$NODE_BIN" -v)"
    exit 1
fi

if [ -z "$OPENCLAW_BIN" ] || [ ! -x "$OPENCLAW_BIN" ]; then
    echo "ERROR: OpenClaw CLI not found."
    echo "Install it with: npm install -g openclaw@latest"
    exit 1
fi

if [ -f "$REPO_DIR/.env" ]; then
    set -a
    source "$REPO_DIR/.env"
    set +a
    echo "Loaded .env"
else
    echo "WARNING: .env not found. Copy .env.example to .env and fill in real values."
fi

if ! python3 - <<'PY' >/dev/null 2>&1
import requests, bs4
PY
then
    echo "Installing Python helpers for /sum..."
    python3 -m pip install --user --break-system-packages -r "$REPO_DIR/requirements.txt"
fi

for REQUIRED_BIN in ffmpeg ffprobe; do
    if ! command -v "$REQUIRED_BIN" >/dev/null 2>&1; then
        echo "ERROR: $REQUIRED_BIN is required for /sum audio transcription. Install ffmpeg with Homebrew."
        exit 1
    fi
done
for OPTIONAL_BIN in yt-dlp; do
    if ! command -v "$OPTIONAL_BIN" >/dev/null 2>&1; then
        echo "WARNING: $OPTIONAL_BIN not found. /sum may be weaker without it."
    fi
done

mkdir -p "$OPENCLAW_DIR" "$CRON_DIR" "$SCRIPTS_DIR" "$LOG_DIR" "$STATE_DIR/transcripts" "$HOME/Library/LaunchAgents"

TEMPLATE="$REPO_DIR/config/openclaw.json.template"
TARGET_CONFIG="$OPENCLAW_DIR/openclaw.json"
if [ ! -f "$TEMPLATE" ]; then
    echo "ERROR: missing config template: $TEMPLATE"
    exit 1
fi

if [ -e "$TARGET_CONFIG" ]; then
    BACKUP="$TARGET_CONFIG.backup.$(date +%s)"
    cp "$TARGET_CONFIG" "$BACKUP"
    echo "Backed up existing config: $BACKUP"
fi

if "$OPENCLAW_BIN" plugins inspect transcribe-command >/dev/null 2>&1; then
    "$OPENCLAW_BIN" plugins uninstall transcribe-command --force >/dev/null 2>&1 || true
fi
if "$OPENCLAW_BIN" plugins inspect sum-command >/dev/null 2>&1; then
    "$OPENCLAW_BIN" plugins uninstall sum-command --force >/dev/null 2>&1 || true
fi

cp "$TEMPLATE" "$TARGET_CONFIG"
sed -i '' "s|__SUM_PLUGIN_PATH__|$SUM_PLUGIN|g" "$TARGET_CONFIG"
if [ -n "${OPENCLAW_AUTH_TOKEN:-}" ]; then
    sed -i '' "s|__OPENCLAW_AUTH_TOKEN__|$OPENCLAW_AUTH_TOKEN|g" "$TARGET_CONFIG"
else
    echo "WARNING: OPENCLAW_AUTH_TOKEN is unset; token placeholder remains in generated config."
fi
chmod 600 "$TARGET_CONFIG"
echo "Generated: $TARGET_CONFIG"

if ! "$OPENCLAW_BIN" plugins inspect whatsapp >/dev/null 2>&1; then
    echo "Installing WhatsApp transport plugin..."
    NPM_CONFIG_CACHE="$WHATSAPP_NPM_CACHE" "$OPENCLAW_BIN" plugins install clawhub:@openclaw/whatsapp
else
    echo "WhatsApp transport plugin already installed"
fi

if [ -L "$WORKSPACE_DIR" ]; then
    rm "$WORKSPACE_DIR"
fi
mkdir -p "$WORKSPACE_DIR"
find "$WORKSPACE_DIR" -mindepth 1 -maxdepth 1 ! -name "AGENTS.md" -exec rm -rf {} + 2>/dev/null || true
cp "$REPO_DIR/workspace/AGENTS.md" "$WORKSPACE_DIR/AGENTS.md"
chmod 600 "$WORKSPACE_DIR/AGENTS.md"
echo "Prepared runtime workspace: $WORKSPACE_DIR"

if [ -f "$REPO_DIR/config/cron/jobs.json" ]; then
    cp "$REPO_DIR/config/cron/jobs.json" "$CRON_DIR/jobs.json"
    chmod 600 "$CRON_DIR/jobs.json"
    echo "Seeded empty cron store: $CRON_DIR/jobs.json"
fi

cp "$REPO_DIR/scripts/daily-restart.sh" "$SCRIPTS_DIR/daily-restart.sh"
chmod +x "$SCRIPTS_DIR/daily-restart.sh"
echo "Copied daily restart script into local OpenClaw state"

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
    <string>$PREFERRED_PATH</string>
    <key>OPENCLAW_REPO</key>
    <string>$REPO_DIR</string>
  </dict>
  <key>StandardOutPath</key>
  <string>$LOG_DIR/daily-restart.launchd.out.log</string>
  <key>StandardErrorPath</key>
  <string>$LOG_DIR/daily-restart.launchd.err.log</string>
</dict>
</plist>
EOF
chmod 644 "$DAILY_RESTART_PLIST"
launchctl unload "$DAILY_RESTART_PLIST" >/dev/null 2>&1 || true
launchctl load "$DAILY_RESTART_PLIST"
echo "Installed daily restart LaunchAgent"

if [ ! -f "$PLIST" ]; then
    echo "Installing OpenClaw gateway LaunchAgent..."
    "$OPENCLAW_BIN" gateway install
fi

if [ ! -f "$PLIST" ]; then
    echo "ERROR: gateway LaunchAgent was not created: $PLIST"
    exit 1
fi

ensure_env_dict() {
    /usr/libexec/PlistBuddy -c "Print :EnvironmentVariables" "$PLIST" >/dev/null 2>&1 \
        || /usr/libexec/PlistBuddy -c "Add :EnvironmentVariables dict" "$PLIST"
}

plist_set_env() {
    local key="$1"
    local value="$2"
    if [ -n "$value" ]; then
        /usr/libexec/PlistBuddy -c "Add :EnvironmentVariables:$key string $value" "$PLIST"
    fi
}

/usr/libexec/PlistBuddy -c "Delete :EnvironmentVariables" "$PLIST" >/dev/null 2>&1 || true
ensure_env_dict

plist_set_env PATH "$PREFERRED_PATH"
plist_set_env OPENCLAW_REPO "$REPO_DIR"
plist_set_env OPENAI_API_KEY "${OPENAI_API_KEY:-}"
plist_set_env GOOGLE_API_KEY "${GOOGLE_API_KEY:-}"
plist_set_env GEMINI_API_KEY "${GEMINI_API_KEY:-}"
plist_set_env GMAIL_USER "${GMAIL_USER:-}"
plist_set_env GMAIL_APP_PASSWORD "${GMAIL_APP_PASSWORD:-}"
SUM_EMAIL="${SUM_EMAIL_TO:-${TRANSCRIBE_EMAIL_TO:-igor.arsenin@gmail.com}}"
plist_set_env SUM_EMAIL_TO "$SUM_EMAIL"
plist_set_env OPENCLAW_NOTIFY_TARGET "${OPENCLAW_NOTIFY_TARGET:-+19179752041}"
plist_set_env PYTHON3_PATH "${PYTHON3_PATH:-}"
plist_set_env TZ "${TZ:-America/New_York}"
echo "Injected command environment into gateway LaunchAgent"

"$OPENCLAW_BIN" plugins install --dangerously-force-unsafe-install --link "$SUM_PLUGIN"
echo "Installed linked plugin: sum-command"

echo "Restarting OpenClaw gateway..."
launchctl unload "$PLIST" >/dev/null 2>&1 || true
sleep 2
launchctl load "$PLIST"

echo ""
echo "Setup complete. Command: /sum <URL>"
