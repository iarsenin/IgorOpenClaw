#!/usr/bin/env bash
set -euo pipefail

# IgorOpenClaw — Setup Script
# Copies config template, symlinks workspace, seeds live cron state, installs daemon.
# Run from the repo root: bash scripts/setup.sh

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OPENCLAW_DIR="$HOME/.openclaw"
WORKSPACE_DIR="$OPENCLAW_DIR/workspace"
STATE_DIR="$OPENCLAW_DIR/state"
CRON_DIR="$OPENCLAW_DIR/cron"
PLIST="$HOME/Library/LaunchAgents/ai.openclaw.gateway.plist"
DAILY_RESTART_PLIST="$HOME/Library/LaunchAgents/ai.openclaw.daily-restart.plist"
SCRIPTS_DIR="$OPENCLAW_DIR/scripts"
LOG_DIR="$OPENCLAW_DIR/logs"
TRANSCRIBE_PLUGIN="$REPO_DIR/openclaw-plugins/transcribe-command"
PREFERRED_SYSTEM_PATH="/opt/homebrew/opt/node@24/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

if [ -x "/opt/homebrew/bin/openclaw" ]; then
    OPENCLAW_BIN="/opt/homebrew/bin/openclaw"
elif command -v openclaw &>/dev/null; then
    OPENCLAW_BIN="$(command -v openclaw)"
else
    OPENCLAW_BIN=""
fi

if [ -x "/opt/homebrew/opt/node@24/bin/node" ]; then
    NODE_BIN="/opt/homebrew/opt/node@24/bin/node"
elif [ -x "/opt/homebrew/bin/node" ]; then
    NODE_BIN="/opt/homebrew/bin/node"
elif command -v node &>/dev/null; then
    NODE_BIN="$(command -v node)"
else
    NODE_BIN=""
fi

export PATH="$PREFERRED_SYSTEM_PATH:$PATH"

echo "=== IgorOpenClaw Setup ==="
echo "Repo: $REPO_DIR"
echo "OpenClaw dir: $OPENCLAW_DIR"
echo ""

# --- Check prerequisites ---
if [ -z "$NODE_BIN" ] || [ ! -x "$NODE_BIN" ]; then
    echo "ERROR: Node.js not found. Install it first:"
    echo "  brew install node@22"
    exit 1
fi

NODE_VERSION=$("$NODE_BIN" -v | sed 's/v//' | cut -d. -f1)
if [ "$NODE_VERSION" -lt 22 ]; then
    echo "ERROR: Node.js 22+ required. Found: $("$NODE_BIN" -v)"
    echo "  brew install node@22"
    exit 1
fi

if [ -z "$OPENCLAW_BIN" ] || [ ! -x "$OPENCLAW_BIN" ]; then
    echo "ERROR: OpenClaw not found. Install it first:"
    echo "  npm install -g openclaw@latest"
    exit 1
fi

if ! command -v yt-dlp &>/dev/null; then
    echo "WARNING: yt-dlp not found. /transcribe will be weaker on YouTube and embedded media."
fi

if ! command -v ffmpeg &>/dev/null; then
    echo "WARNING: ffmpeg not found. /transcribe may fail to convert some media formats."
fi

if ! python3 - <<'PY' &>/dev/null
import requests, bs4
PY
then
    echo "Installing Python helpers for /transcribe (requests, beautifulsoup4)..."
    python3 -m pip install --user --break-system-packages requests beautifulsoup4
fi

install_transcribe_plugin() {
    if [ ! -d "$TRANSCRIBE_PLUGIN" ]; then
        echo "WARNING: $TRANSCRIBE_PLUGIN not found. /transcribe will fall back to model mediation."
        return
    fi

    if "$OPENCLAW_BIN" plugins inspect transcribe-command >/dev/null 2>&1; then
        echo "Refreshing transcribe-command plugin..."
        "$OPENCLAW_BIN" plugins uninstall transcribe-command >/dev/null 2>&1 || true
    fi

    # OpenClaw 2026.4+ blocks local plugins that use child_process by default.
    # This repo's /transcribe command is a reviewed local plugin that launches
    # the deterministic transcript helper intentionally, so setup installs it
    # with the documented break-glass override.
    "$OPENCLAW_BIN" plugins install --dangerously-force-unsafe-install --link "$TRANSCRIBE_PLUGIN"
    echo "Installed linked plugin: transcribe-command"
}

seed_cron_store() {
    local repo_jobs="$REPO_DIR/config/cron/jobs.json"
    local live_jobs="$CRON_DIR/jobs.json"

    if [ ! -f "$repo_jobs" ]; then
        return
    fi

    python3 - <<'PY' "$repo_jobs" "$live_jobs"
import json
import pathlib
import sys
import time

repo_path = pathlib.Path(sys.argv[1])
live_path = pathlib.Path(sys.argv[2])
now = int(time.time() * 1000)

repo = json.loads(repo_path.read_text())
live = None
if live_path.exists():
    try:
        live = json.loads(live_path.read_text())
    except Exception:
        live = None

existing_jobs = {}
if isinstance(live, dict):
    for job in live.get("jobs", []):
        if isinstance(job, dict) and isinstance(job.get("id"), str):
            existing_jobs[job["id"]] = job

seeded_jobs = []
for job in repo.get("jobs", []):
    current = existing_jobs.get(job["id"], {})
    seeded = dict(job)
    seeded["createdAtMs"] = current.get("createdAtMs", now)
    seeded["updatedAtMs"] = now
    state = current.get("state")
    if not isinstance(state, dict):
        state = job.get("state") if isinstance(job.get("state"), dict) else {}
    seeded["state"] = state
    seeded_jobs.append(seeded)

payload = {"version": int(repo.get("version", 1)), "jobs": seeded_jobs}
live_path.parent.mkdir(parents=True, exist_ok=True)
tmp_path = live_path.with_suffix(live_path.suffix + f".{now}.tmp")
tmp_path.write_text(json.dumps(payload, indent=2) + "\n")
tmp_path.replace(live_path)
PY

    echo "Seeded live cron store: $live_jobs"
}

preserve_live_model() {
    local source_config="$1"
    local target_config="$2"

    if [ -z "$source_config" ] || [ ! -f "$source_config" ] || [ ! -f "$target_config" ]; then
        return
    fi

    python3 - <<'PY' "$source_config" "$target_config"
import json
import pathlib
import sys

source = pathlib.Path(sys.argv[1])
target = pathlib.Path(sys.argv[2])
try:
    previous = json.loads(source.read_text())
    current = json.loads(target.read_text())
    previous_model = previous.get("agents", {}).get("defaults", {}).get("model")
    if previous_model is not None:
        current.setdefault("agents", {}).setdefault("defaults", {})["model"] = previous_model
        target.write_text(json.dumps(current, indent=2) + "\n")
except Exception:
    pass
PY

    echo "Preserved live agents.defaults.model from existing config"
}

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
EXISTING_CONFIG_BACKUP=""
if [ ! -f "$TEMPLATE" ]; then
    echo "ERROR: config/openclaw.json.template not found"
    exit 1
fi
if [ -e "$TARGET_CONFIG" ]; then
    BACKUP="$TARGET_CONFIG.backup.$(date +%s)"
    echo "Backing up existing config to $BACKUP"
    cp "$TARGET_CONFIG" "$BACKUP"
    EXISTING_CONFIG_BACKUP="$BACKUP"
fi
cp "$TEMPLATE" "$TARGET_CONFIG"
if [ -n "${OPENCLAW_AUTH_TOKEN:-}" ]; then
    sed -i '' "s|__OPENCLAW_AUTH_TOKEN__|$OPENCLAW_AUTH_TOKEN|g" "$TARGET_CONFIG"
    echo "Generated: openclaw.json (token injected from .env)"
else
    echo "WARNING: OPENCLAW_AUTH_TOKEN not set in .env — token placeholder left in config"
fi
preserve_live_model "$EXISTING_CONFIG_BACKUP" "$TARGET_CONFIG"
chmod 600 "$TARGET_CONFIG"

# --- Symlink workspace ---
if [ -e "$WORKSPACE_DIR" ] && [ ! -L "$WORKSPACE_DIR" ]; then
    BACKUP="$WORKSPACE_DIR.backup.$(date +%s)"
    echo "Backing up existing workspace to $BACKUP"
    mv "$WORKSPACE_DIR" "$BACKUP"
fi
ln -sfn "$REPO_DIR/workspace" "$WORKSPACE_DIR"
echo "Linked: workspace/ -> $WORKSPACE_DIR"

# --- Runtime state lives on local disk, not Google Drive -------------------
# Google Drive File Stream throws EDEADLK when many small writes hit a synced
# file, and needlessly syncs gigabytes of transient audio/transcripts. Keep
# everything mutable under ~/.openclaw/state/ and symlink from workspace/.
mkdir -p "$STATE_DIR/transcripts" "$STATE_DIR/memory"

# MEMORY.md — agent writes this every turn.
MEMORY_TEMPLATE="$REPO_DIR/workspace/MEMORY.template.md"
MEMORY_STATE="$STATE_DIR/MEMORY.md"
MEMORY_LINK="$REPO_DIR/workspace/MEMORY.md"
if [ -f "$MEMORY_LINK" ] && [ ! -L "$MEMORY_LINK" ]; then
    mv "$MEMORY_LINK" "$MEMORY_STATE"
    echo "Migrated workspace/MEMORY.md → $MEMORY_STATE"
fi
if [ ! -f "$MEMORY_STATE" ] && [ -f "$MEMORY_TEMPLATE" ]; then
    cp "$MEMORY_TEMPLATE" "$MEMORY_STATE"
    echo "Initialized $MEMORY_STATE from template"
fi
if [ ! -L "$MEMORY_LINK" ]; then
    ln -sfn "$MEMORY_STATE" "$MEMORY_LINK"
fi

# auth-profiles.json — OAuth tokens, rotated frequently.
AUTH_STATE="$STATE_DIR/auth-profiles.json"
AUTH_LINK="$REPO_DIR/workspace/auth-profiles.json"
if [ -f "$AUTH_LINK" ] && [ ! -L "$AUTH_LINK" ]; then
    mv "$AUTH_LINK" "$AUTH_STATE"
    chmod 600 "$AUTH_STATE"
    echo "Migrated workspace/auth-profiles.json → $AUTH_STATE"
fi
if [ ! -L "$AUTH_LINK" ] && [ -f "$AUTH_STATE" ]; then
    ln -sfn "$AUTH_STATE" "$AUTH_LINK"
fi

# workspace/memory/ — dated snapshots + task-history.md + .dreams/.
MEMORY_DIR_STATE="$STATE_DIR/memory"
MEMORY_DIR_LINK="$REPO_DIR/workspace/memory"
if [ -d "$MEMORY_DIR_LINK" ] && [ ! -L "$MEMORY_DIR_LINK" ]; then
    # Merge any leftover files into local state, then replace with symlink.
    cp -Rn "$MEMORY_DIR_LINK/." "$MEMORY_DIR_STATE/" 2>/dev/null || true
    rm -rf "$MEMORY_DIR_LINK"
    echo "Migrated workspace/memory/ → $MEMORY_DIR_STATE"
fi
if [ ! -L "$MEMORY_DIR_LINK" ]; then
    ln -sfn "$MEMORY_DIR_STATE" "$MEMORY_DIR_LINK"
fi
# ---------------------------------------------------------------------------

# --- Seed live cron store from repo template ---
if [ -L "$CRON_DIR/jobs.json" ]; then
    rm "$CRON_DIR/jobs.json"
fi
seed_cron_store

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
if ! "$OPENCLAW_BIN" gateway status &>/dev/null; then
    echo "Installing the OpenClaw daemon..."
    "$OPENCLAW_BIN" gateway install
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

# --- Install deterministic /transcribe plugin command ---
# Keep this after config generation/recovery because plugin install writes to
# ~/.openclaw/openclaw.json and earlier setup steps can overwrite that file.
install_transcribe_plugin
preserve_live_model "$EXISTING_CONFIG_BACKUP" "$TARGET_CONFIG"

# --- Inject API keys into LaunchAgent plist (BEFORE starting gateway) ---
if [ -f "$PLIST" ] && [ -f "$REPO_DIR/.env" ]; then
    echo "Injecting API keys into LaunchAgent plist..."
    /usr/libexec/PlistBuddy -c "Delete :EnvironmentVariables:PATH" "$PLIST" 2>/dev/null || true
    /usr/libexec/PlistBuddy -c "Add :EnvironmentVariables:PATH string '$PREFERRED_SYSTEM_PATH'" "$PLIST"
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

# --- Re-assert workspace link and re-seed live cron store after install/restart ---
ln -sfn "$REPO_DIR/workspace" "$WORKSPACE_DIR"
seed_cron_store
echo "Verified workspace symlink and live cron store"

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "  1. Edit .env with your real API keys (if not done)"
echo "  2. Update config/openclaw.json.template (WhatsApp allowlist etc.), then re-run this script"
echo "  3. Run: openclaw channels add --channel whatsapp"
echo "  4. Verify: openclaw gateway status"
echo "  5. Open dashboard: openclaw dashboard"
