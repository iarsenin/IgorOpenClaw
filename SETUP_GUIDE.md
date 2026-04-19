# OpenClaw Setup Guide — Mac Mini M2

> **What this document is:** A complete, step-by-step guide to installing and
> configuring OpenClaw as an always-on autonomous AI agent on a Mac Mini M2
> (Apple Silicon, 8 GB RAM). This document is self-contained — you can paste it
> into a Gemini or ChatGPT session and ask for help if you get stuck on any step.

> **What OpenClaw is:** An open-source (MIT licensed) personal AI assistant that
> runs locally on your machine 24/7. It can browse the web, manage email, run
> shell commands, automate browser interactions, and integrate with messaging
> apps (WhatsApp, Telegram, etc.). It uses cloud LLM APIs (OpenAI, Gemini) for
> intelligence — no local model running needed.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Install OpenClaw](#2-install-openclaw)
3. [API Keys Setup](#3-api-keys-setup)
4. [Initial Onboarding](#4-initial-onboarding)
5. [Configuration](#5-configuration)
6. [WhatsApp Setup](#6-whatsapp-setup)
7. [Security Hardening](#7-security-hardening)
8. [Install Core Skills](#8-install-core-skills)
9. [Verify Everything Works](#9-verify-everything-works)
10. [Project Outline: Browser-Based Marketplace Automation](#10-project-outline-browser-based-marketplace-automation)
11. [Project Outline: Autonomous Research & Coding via Cursor](#11-project-outline-autonomous-research--coding-via-cursor)
12. [Troubleshooting](#12-troubleshooting)

---

## 1. Prerequisites

### 1.1 Verify your system

Open Terminal and confirm:

```bash
# Check macOS version (need 12 Monterey or later)
sw_vers

# Check chip (should show arm64 for Apple Silicon)
uname -m
```

Your Mac Mini M2 meets all requirements: Apple Silicon, 8 GB RAM, macOS.

### 1.2 Install Homebrew (if not already installed)

```bash
# Check if Homebrew is installed
brew --version

# If not installed, run:
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

On Apple Silicon, Homebrew installs to `/opt/homebrew`. If you just installed it, follow the instructions it prints to add it to your PATH.

### 1.3 Install Node.js 22+

OpenClaw requires Node.js 22 or later (Node 24 recommended).

```bash
# Install Node.js 22
brew install node@22

# Add to PATH (Apple Silicon Homebrew path)
echo 'export PATH="/opt/homebrew/opt/node@22/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc

# Verify
node -v   # Should show v22.x.x or higher
npm -v    # Should show 10.x.x or higher
```

### 1.4 Install Git (if not already present)

```bash
git --version
# If not installed, macOS will prompt you to install Xcode Command Line Tools
```

---

## 2. Install OpenClaw

```bash
npm install -g openclaw@latest
```

If you get build errors related to `sharp`:

```bash
SHARP_IGNORE_GLOBAL_LIBVIPS=1 npm install -g openclaw@latest
```

Verify the installation:

```bash
openclaw --version
```

You should see something like `2026.3.x`.

---

## 3. API Keys Setup

You need API keys for two LLM providers. These are **separate from any consumer subscriptions** (e.g., Gemini Ultra or ChatGPT Plus do NOT include API access).

### 3.1 OpenAI API Key

1. Go to https://platform.openai.com/api-keys
2. Click "Create new secret key"
3. Copy the key (starts with `sk-`)
4. Make sure you have billing set up at https://platform.openai.com/settings/organization/billing/overview

### 3.2 Google Gemini API Key

1. Go to https://aistudio.google.com/
2. Click "Get API Key" → "Create API key"
3. Copy the key (starts with `AIza`)
4. To enable paid tier (higher rate limits), link a billing account:
   - Go to https://ai.google.dev/gemini-api/docs/billing
   - Follow instructions to link a Google Cloud billing account

### 3.3 Store API Keys

**Option A: Using the IgorOpenClaw repo (recommended)**

If you've cloned the IgorOpenClaw configuration repo:

```bash
cd ~/Library/CloudStorage/GoogleDrive-igor.arsenin@gmail.com/My\ Drive/git/IgorOpenClaw

# Copy the template
cp .env.example .env
chmod 600 .env

# Edit with your real keys
nano .env
```

Fill in your actual values:
```
OPENAI_API_KEY=sk-your-actual-key-here
# Admin key for daily spend reporting (Usage+Billing Read only)
# Create at: platform.openai.com/settings/organization/api-keys
OPENAI_ADMIN_KEY=sk-admin-your-actual-admin-key
# Use ONE Google-family key alias in the runtime if possible.
# If both are set, setup prefers GOOGLE_API_KEY for the LaunchAgent.
GEMINI_API_KEY=AIza-your-actual-key-here
OPENCLAW_AUTH_TOKEN=<generate one — see step 3.4>
GMAIL_USER=your_email@gmail.com
GMAIL_APP_PASSWORD=your-actual-app-password
ALPHA_VANTAGE_KEY=your-actual-key
TZ=America/New_York
```

Then load them into your shell:

```bash
# Add to .zshrc so they load on every terminal session
echo 'set -a; source ~/Library/CloudStorage/GoogleDrive-igor.arsenin@gmail.com/My\ Drive/git/IgorOpenClaw/.env; set +a' >> ~/.zshrc
source ~/.zshrc
```

**Option B: Direct environment variables**

If not using the repo, add directly to `~/.zshrc`:

```bash
echo 'export OPENAI_API_KEY="sk-your-key-here"' >> ~/.zshrc
echo 'export GEMINI_API_KEY="AIza-your-key-here"' >> ~/.zshrc
source ~/.zshrc
```

### 3.4 Generate a Gateway Auth Token

Generate a strong random token for gateway authentication:

```bash
openssl rand -hex 32
```

Copy the output and paste it as the `OPENCLAW_AUTH_TOKEN` value in your `.env` file.

---

## 4. Initial Onboarding

### 4.1 Using the IgorOpenClaw repo setup script (recommended)

If you have the repo cloned with your `.env` filled in:

```bash
cd ~/Library/CloudStorage/GoogleDrive-igor.arsenin@gmail.com/My\ Drive/git/IgorOpenClaw
bash scripts/setup.sh
```

This script:
- Verifies Node.js and OpenClaw are installed
- Creates `~/.openclaw/` directory
- **Copies** `config/openclaw.json.template` → `~/.openclaw/openclaw.json` (injects `OPENCLAW_AUTH_TOKEN` from `.env` — **not** a symlink; git-ignored live config)
- Symlinks `workspace/` → `~/.openclaw/workspace/`
- Symlinks `config/cron/jobs.json` → `~/.openclaw/cron/jobs.json`
- Loads your `.env` variables
- Installs the launchd daemon (runs OpenClaw on startup)

### 4.2 Manual onboarding (without the repo)

```bash
mkdir -p ~/openclaw
cd ~/openclaw
openclaw onboard --install-daemon
```

The interactive wizard will ask you to:
1. Choose an LLM provider (select OpenAI, enter your API key)
2. Set the workspace directory
3. Configure the gateway (port, bind address)
4. Optionally connect messaging channels
5. Install the background daemon

---

## 5. Configuration

The live gateway config is **`~/.openclaw/openclaw.json`** (generated from **`config/openclaw.json.template`** by `setup.sh`). The repo may also contain a local `config/openclaw.json` for editing — keep it in sync with the template if you use both.

### 5.1 Key configuration sections

The IgorOpenClaw template includes:

- **Identity**: Agent named "Clawd"
- **Models**: OpenAI `gpt-5.4-mini` as primary, Google `gemini-2.5-pro` as fallback
- **DM session isolation**: `session.dmScope = "per-account-channel-peer"` so WhatsApp conversations stay separate per sender/account
- **Gateway**: Bound to localhost (mode: local), port 18789, token auth enabled
- **WhatsApp**: Enabled with `allowFrom` phone number restriction, groups disabled
- **Logging**: Logs written to `/tmp/openclaw/openclaw-YYYY-MM-DD.log` (rotated daily)

### 5.2 Customize the config

**Durable path:** edit `config/openclaw.json.template`, then re-run `bash scripts/setup.sh` to regenerate `~/.openclaw/openclaw.json`.

**Quick path:** edit `~/.openclaw/openclaw.json` directly, then:

```bash
openclaw gateway restart
```

**Important:** Replace `"+1XXXXXXXXXX"` in the `channels.whatsapp.allowFrom` array with your actual phone number.

### 5.3 Update models

To change which models are used:

```json5
agent: {
  model: {
    primary: "openai/gpt-5.4-mini",       // current default in this repo
    fallbacks: ["google/gemini-2.5-pro"], // or "google/gemini-2.5-flash" for cheaper
  },
},
```

List available models:

```bash
openclaw models list
```

### 5.4 Workspace instructions (how Clawd behaves)

The `workspace/` directory (symlinked to `~/.openclaw/workspace/`) holds markdown
files the agent reads every turn — **no gateway restart** needed after edits.

Key files: `AGENTS.md` (rules), `SOUL.md` (tone), `USER.md` (owner context),
`TOOLS.md` (tools), `MEMORY.md` (persistent tasks), `HEARTBEAT.md` (proactive behavior).

`workspace/MEMORY.md` is local-only runtime state (git-ignored). The repo tracks
`workspace/MEMORY.template.md`, and `bash scripts/setup.sh` auto-creates
`workspace/MEMORY.md` from that template when missing.

**Question style:** When the agent needs a **decision or missing detail** from you,
it should **prefer yes/no or multiple-choice** (A/B/C or 1/2/3) when that fits your
reply on WhatsApp — not open-ended questions. It should **not** force that format
when only a free-form answer makes sense. See `workspace/AGENTS.md` § **Questions to the user**.

---

## 6. WhatsApp Setup

OpenClaw connects to WhatsApp via a web bridge (similar to WhatsApp Web).

### 6.1 Add WhatsApp channel

```bash
openclaw channels add --channel whatsapp
```

This will display a QR code in the terminal.

### 6.2 Scan the QR code

1. Open WhatsApp on your phone
2. Go to **Settings → Linked Devices → Link a Device**
3. Scan the QR code displayed in the terminal

### 6.3 Secure the channel

Make sure your config has `allowFrom` set to your phone number:

```json5
channels: {
  whatsapp: {
    enabled: true,
    allowFrom: ["+1XXXXXXXXXX"],  // Your actual phone number
    groupPolicy: "disabled",  // groups off — allowFrom list only
  },
},
```

This ensures only messages from the numbers in `allowFrom` are processed. Groups are disabled by default in this repo.

### 6.4 Test it

Send a message to yourself (or to the WhatsApp number associated with the bridge) and verify the agent responds.

---

## 7. Security Hardening

OpenClaw has significant system access. These steps reduce the attack surface.

### 7.1 Gateway binding (CRITICAL)

Already configured in `config/openclaw.json.template` (copied to `~/.openclaw/openclaw.json` by setup):

```json5
gateway: {
  host: "127.0.0.1",  // NEVER change this to 0.0.0.0
  port: 18789,
},
```

This means the gateway is only accessible from your Mac itself, not from the network.

### 7.2 Authentication token

Already configured via `OPENCLAW_AUTH_TOKEN` in `.env`. Verify it's set:

```bash
echo $OPENCLAW_AUTH_TOKEN
# Should print your 64-character hex token
```

### 7.3 File permissions

```bash
# Restrict .env to owner-only read
chmod 600 ~/Library/CloudStorage/GoogleDrive-igor.arsenin@gmail.com/My\ Drive/git/IgorOpenClaw/.env

# Restrict OpenClaw directory
chmod 700 ~/.openclaw
```

### 7.4 macOS firewall

Enable the built-in firewall to block unsolicited inbound connections:

1. **System Settings → Network → Firewall → Turn On**
2. Click **Options** and enable **"Block all incoming connections"** (or selectively block)

This prevents external access even if the gateway binding is accidentally changed.

### 7.5 Audit logging

OpenClaw logs to `/tmp/openclaw/openclaw-YYYY-MM-DD.log` (rotated daily). Check logs with:

```bash
# Today's log
tail -50 /tmp/openclaw/openclaw-$(date +%Y-%m-%d).log

# List recent log files
ls -lt /tmp/openclaw/openclaw-*.log | head -5
```

Logging verbosity is controlled by OpenClaw defaults. Refer to `openclaw --help` for current options.

### 7.6 Skill vetting

Before installing any skill from ClawHub:

1. Read the skill's source code on GitHub
2. Check the author's reputation and contributor count
3. Look for any file system access, network calls, or credential handling
4. Prefer official skills from the `openclaw/skills` organization

```bash
# List installed skills
openclaw skills list

# Get info about a skill before installing
openclaw skills info <skill-name>
```

### 7.7 API key billing alerts

Set up billing alerts to detect unauthorized usage:

- **OpenAI**: https://platform.openai.com/settings/organization/billing/overview → Set monthly budget
- **Google AI**: https://console.cloud.google.com/billing → Set budget alerts

### 7.8 Optional: Separate macOS user

For maximum isolation, create a dedicated macOS user account for OpenClaw:

1. System Settings → Users & Groups → Add User
2. Create a standard (non-admin) user named e.g. "openclaw"
3. Run the OpenClaw daemon under that user
4. Grant only the specific file/folder access the agent needs

This is optional but recommended if you plan to give the agent broad file system access.

---

## 8. Install Core Skills

### 8.1 Browser automation

```bash
# Install the skill
openclaw skills install browser-automation

# Install the browser engine
npx playwright install chromium
```

### 8.2 Email (Gmail)

```bash
openclaw skills install gmail
openclaw skills install send-email
```

The Gmail skill uses OAuth or SMTP. For SMTP, your `GMAIL_USER` and `GMAIL_APP_PASSWORD` from `.env` are used.

To create a Gmail App Password:
1. Go to https://myaccount.google.com/apppasswords
2. Select "Mail" and "Mac" (or "Other")
3. Copy the 16-character password into your `.env`

### 8.3 Cursor IDE agent

```bash
openclaw skills install cursor-ide-agent
```

This requires the Cursor CLI to be on your PATH. In Cursor:
1. Open Command Palette (Cmd+Shift+P)
2. Search "Install 'cursor' command in PATH"
3. Run it

Verify:

```bash
cursor --version
```

### 8.4 Verify installed skills

```bash
openclaw skills list
```

### 8.5 Phone Calls (Vapi AI)

OpenClaw can make and receive phone calls via [Vapi.ai](https://vapi.ai), a
turnkey AI voice platform. Vapi handles telephony, speech-to-text, text-to-speech,
and conversational flow. OpenClaw controls it via REST API.

#### 8.5.1 Create a Vapi account

1. Go to https://dashboard.vapi.ai and sign up (select **Developer** user type)
2. From the dashboard, go to **Organization Settings → API Keys**
3. Copy your **Private API Key** (a UUID like `ebe62f22-...`)

#### 8.5.2 Create an assistant

1. Go to **Assistants → Create Assistant**
2. Configure:
   - **Model provider:** OpenAI (managed by Vapi — uses their API key, not yours)
   - **Model:** gpt-4o (Vapi manages this — uses their API key, not yours; ~0.6s latency)
   - **First Message Mode:** Assistant speaks first
   - **First Message:** `Hi, I'm calling on behalf of Igor Arsenin. How are you?`
   - **System Prompt:** A comprehensive prompt covering outbound task execution,
     inbound message-taking, negotiation boundaries, and spam blocking.
     Merge the **Outbound voicemail & callback** section from
     `config/riley-voice-behavior.md` into the system prompt. See
     `workspace/TOOLS.md § Phone Calls` for architecture and Clawd rules.
   - **Max tokens:** 500, **Temperature:** 0.5
   - **Transcriber:** Deepgram, English. Add custom keywords: your name, contacts, brands.
   - **Voice:** Elliot (or any preferred voice)
   - **Structured Output:** One field called `callReport` (string) for post-call summaries
3. Publish the assistant and copy the **Assistant ID** from the URL

#### 8.5.3 Get a phone number

1. In Vapi dashboard, go to **Phone Numbers → Buy a Number**
2. Choose a US area code (e.g. 917 for New York)
3. Configure the phone number:
   - **Label:** "Igor's Assistant"
   - **Inbound Assistant:** select your assistant (e.g. "Riley")
   - **Fallback Destination:** your personal cell number (transfers if AI is unavailable)
4. Copy the **Phone Number ID** (a UUID)

#### 8.5.4 Add credentials to .env

Add these four lines to your `.env` file:

```
VAPI_API_KEY=your-vapi-private-api-key
VAPI_ASSISTANT_ID=your-vapi-assistant-id
VAPI_PHONE_NUMBER_ID=your-vapi-phone-number-id
VAPI_PHONE_NUMBER=+19179628631
```

#### 8.5.5 Add to launchd plist

The OpenClaw daemon needs these env vars too. Add them to the launchd plist:

```bash
PLIST=~/Library/LaunchAgents/ai.openclaw.gateway.plist

/usr/libexec/PlistBuddy -c "Add :EnvironmentVariables:VAPI_API_KEY string YOUR_KEY" "$PLIST"
/usr/libexec/PlistBuddy -c "Add :EnvironmentVariables:VAPI_ASSISTANT_ID string YOUR_ID" "$PLIST"
/usr/libexec/PlistBuddy -c "Add :EnvironmentVariables:VAPI_PHONE_NUMBER_ID string YOUR_ID" "$PLIST"
/usr/libexec/PlistBuddy -c "Add :EnvironmentVariables:VAPI_PHONE_NUMBER string +19179628631" "$PLIST"

# Reload the daemon to pick up new env vars
launchctl unload "$PLIST"
sleep 2
launchctl load "$PLIST"
```

#### 8.5.6 Test

```bash
REPO=~/Library/CloudStorage/GoogleDrive-igor.arsenin@gmail.com/My\ Drive/git/IgorOpenClaw

# Verify API connectivity
python3 "$REPO/scripts/vapi-call.py" list --limit 5

# Make a test call to your own phone
python3 "$REPO/scripts/vapi-call.py" call "+1YOURNUMBER" "This is a test call. Confirm you are Riley and say goodbye."

# After the call, check the transcript
python3 "$REPO/scripts/vapi-call.py" status <call_id>
```

#### 8.5.7 How it works (for future maintainers)

```
Outbound:  Clawd → vapi-call.py → POST api.vapi.ai/call → Riley → recipient
Inbound:   caller → +19179628631 → Vapi → Riley answers, takes message
Polling:   cron (every 30 min) → vapi-call.py inbound-check → WhatsApp alert to Igor
```

- `scripts/vapi-call.py` is a standalone Python script (no pip dependencies)
- Riley's base system prompt is edited in Vapi; canonical voicemail/callback text is in `config/riley-voice-behavior.md`, and the same outbound voicemail rules are injected on every outbound call via `assistantOverrides`
- Inbound calls are tracked in `.vapi-seen-calls` (git-ignored) to avoid duplicate alerts
- The `inbound-call-check` cron job in `config/cron/jobs.json` runs every 30 minutes
- Outbound calls use `assistantOverrides` to inject task-specific instructions per call
- Cost is ~$0.11/minute (Vapi's rate for their managed model + telephony + TTS/STT)

---

## 9. Verify Everything Works

Run through this checklist:

```bash
# 1. Gateway is running
openclaw gateway status
# Expected: "Gateway is running on 127.0.0.1:18789"

# 2. Models are configured
openclaw models list
# Expected: shows openai/gpt-5.4-mini and google/gemini-2.5-pro

# 3. Skills are installed
openclaw skills list
# Expected: browser-automation, himalaya (email), gog (Google Workspace),
#           cursor-ide-agent, apple-reminders, and others (see TOOLS.md for full list)

# 4. Cron jobs are loaded
openclaw cron list
# Expected: post-restart-resume, morning-briefing, api-spend-check, email-triage,
#           chrono24-listing-monitor, sms-reply-monitor, inbound-call-check, system-health

# 5. Open the dashboard
openclaw dashboard
# Opens a web UI in your browser

# 6. Test via WhatsApp
# Send "Hello" to the agent via WhatsApp
# Expected: agent responds with a greeting
```

If everything passes, your OpenClaw agent is live and running 24/7.

---

## 10. Project Outline: Browser-Based Marketplace Automation

This is a rough architectural outline for using OpenClaw to automate listing and selling items on online marketplaces (e.g., watches on Chrono24, electronics on eBay, etc.).

### Skill chain
- browser-automation + gmail + whatsapp channel

### Workflow
1. **Initiate via WhatsApp**: Tell the agent what you want to sell, with details (item, condition, price, photos)
2. **Agent navigates the marketplace**: Uses browser automation to go to the listing form
3. **Fill and preview**: Agent fills in fields, uploads photos, takes a screenshot of the draft listing
4. **Send for approval**: Agent sends the screenshot back to you via WhatsApp
5. **Submit on approval**: You reply "approve" and the agent submits the listing
6. **Monitor**: Agent sets up a cron job to periodically check for buyer messages, price changes, or listing status updates
7. **Alert**: Agent notifies you via WhatsApp when there's buyer interest or the item sells

### Key challenges to solve
- **Bot detection**: Many marketplaces detect Playwright; need stealth mode and possibly human-like delays
- **CAPTCHA**: May need a CAPTCHA-solving service or manual intervention
- **Session management**: Keep marketplace login sessions alive across browser restarts
- **Photo handling**: Agent needs access to photo files on disk or a shared folder
- **API alternative**: If the marketplace offers a seller API (XML/JSON feed), that's far more reliable than browser scraping

### What to build
- A custom OpenClaw skill that wraps the browser-automation skill with marketplace-specific logic
- Cron job templates for monitoring active listings
- Approval flow that pauses automation until user confirms via WhatsApp

---

## 11. Project Outline: Autonomous Research & Coding via Cursor

This is a rough architectural outline for using OpenClaw to autonomously research ideas, write code, and iterate using multiple LLMs and Cursor IDE.

### Skill chain
- cursor-ide-agent + multi-model routing + cron/heartbeat

### Workflow
1. **Describe an idea**: Via WhatsApp or direct chat, give the agent a rough concept
2. **Multi-model research**: Agent queries OpenAI with the idea, then sends OpenAI's response to Gemini for critique, then synthesizes both perspectives
3. **Refined proposal**: Agent produces a structured proposal and sends it to you for review
4. **Scaffolding**: On approval, agent uses cursor-ide-agent (CLI mode) to create the project structure and write initial code
5. **Cross-model review**: Agent sends the code to a different LLM for review (e.g., Gemini reviews OpenAI-generated code, or vice versa)
6. **Iterate**: Agent fixes issues flagged by the reviewer, re-runs tests, and continues until quality threshold is met
7. **Deliver**: Agent commits to a git branch and notifies you with a summary of what was built

### Key components
- **Multi-model routing**: Configure `~/.openclaw/openclaw.json` (from `config/openclaw.json.template`) with both OpenAI and Gemini providers; use the agent's model-switching capabilities to route different phases to different models
- **cursor-ide-agent skill**: Path 1 (CLI) for fast non-interactive coding, Path 2 (Node/IDE) for features like diagnostics and test running
- **Cron jobs**: For long-running research that continues overnight
- **autonomy-windowed skill**: Restrict autonomous actions to safe hours (e.g., 8 AM–8 PM) to prevent runaway loops at night

### Key challenges to solve
- **Context management**: LLMs have finite context windows; need a strategy for summarizing and passing context between models
- **Loop prevention**: Set a maximum number of review iterations (e.g., 3) to prevent infinite improve-review cycles
- **Cost control**: Multi-model workflows can get expensive; set billing alerts and per-session token budgets
- **Cursor CLI access**: Ensure the OpenClaw daemon process can invoke `cursor` CLI; may need PATH configuration in the launchd plist
- **Git workflow**: Define branch naming conventions and commit message standards for agent-created code

### What to build
- A custom OpenClaw skill that orchestrates the multi-model research dialog
- A Cursor integration skill that handles the code-write-review-iterate loop
- Templates for different research/coding project types
- Budget and iteration limit configurations

---

## 12. Troubleshooting

### OpenClaw won't start

```bash
# Check if Node.js is available
node -v

# Check if the daemon is installed
launchctl list | grep openclaw

# Try starting manually
openclaw gateway start

# Check logs for errors
tail -100 /tmp/openclaw/openclaw-$(date +%Y-%m-%d).log
```

### Gateway port already in use

```bash
# Find what's using port 18789
lsof -i :18789

# Kill the stale process
kill -9 <PID>

# Restart
openclaw gateway restart
```

### WhatsApp disconnected

WhatsApp web sessions can expire. Re-link:

```bash
openclaw channels add --channel whatsapp
# Scan the new QR code
```

### API key errors

```bash
# Verify keys are loaded
echo $OPENAI_API_KEY
echo $GEMINI_API_KEY

# Test OpenAI directly
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY" | head -20
```

### Skills not working

```bash
# Reinstall a skill
openclaw skills uninstall browser-automation
openclaw skills install browser-automation

# For browser automation, ensure Chromium is installed
npx playwright install chromium
```

### Managed Chrome windows stay open after Clawd finishes

Clawd should **`browser close`** in the **same turn** after any managed browser use (see `workspace/AGENTS.md` § Browser hygiene and `workspace/TOOLS.md` § Browser Rules). Isolated crons that use the browser also end with **`browser close`**; **`post-restart-resume`** and **`system-health`** try **`browser close`** once to clear orphans.

**If windows are still left open:** message Clawd (WhatsApp) with *“run browser close now”*; or restart the gateway after an isolated session; the **daily 4 AM ET** restart also recycles the debug Chrome profile. If it keeps happening, check `~/.openclaw/logs/gateway.log` for browser timeouts — the model may be skipping the close step.

### Daemon crashes on restart (known macOS issue)

If the gateway fails to restart via `openclaw gateway restart`, try:

```bash
# Manual restart sequence
openclaw gateway stop
sleep 2
openclaw gateway start
```

This avoids a known launchd race condition where the old process hasn't fully released the port before the new one tries to bind.

### Config changes not taking effect

```bash
# Verify config exists (copy from template — not a symlink)
ls -la ~/.openclaw/openclaw.json

# Restart after config changes
openclaw gateway restart
```

---

## Quick Reference

| Command | Purpose |
|---------|---------|
| `openclaw gateway status` | Check if gateway is running |
| `openclaw gateway restart` | Restart after config changes |
| `openclaw gateway stop` | Stop the daemon |
| `openclaw dashboard` | Open web dashboard |
| `openclaw logs --tail 50` | View recent logs |
| `openclaw models list` | List configured models |
| `openclaw skills list` | List installed skills |
| `openclaw skills install <name>` | Install a skill |
| `openclaw cron list` | List scheduled jobs |
| `openclaw channels add --channel whatsapp` | Set up WhatsApp |
| `openclaw configure` | Re-run configuration wizard |
