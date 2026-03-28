# IgorOpenClaw

Version-controlled configuration and workspace for an always-on [OpenClaw](https://github.com/openclaw/openclaw) autonomous AI agent running on a Mac Mini M2.

## Purpose

This repository is the single source of truth for an OpenClaw agent that:

- Runs 24/7 as a macOS LaunchAgent daemon
- Accepts instructions via WhatsApp and executes tasks autonomously
- Uses **OpenAI** (primary) and **Google Gemini** (fallback) as LLM providers
- Automates browser interactions, email, iMessage/SMS, phone calls (Vapi AI), file management, and coding workflows
- Integrates with Cursor IDE for autonomous coding and research

The agent acts on its owner's behalf — browsing the web, managing email, running shell commands, and orchestrating multi-step workflows — while requiring explicit approval before irreversible actions. When it needs a decision or missing info from the owner, it **prefers yes/no or multiple-choice questions** when practical (see `workspace/AGENTS.md`).

## Architecture

```
┌─────────────┐     WhatsApp      ┌──────────────────┐
│  Phone /    │◄──────────────────►│  OpenClaw Gateway │
│  Any Device │                    │  (localhost:18789) │
└─────────────┘                    └────────┬─────────┘
                                            │
                          ┌─────────────────┼─────────────────┐
                          ▼                 ▼                 ▼
                    ┌──────────┐    ┌──────────────┐   ┌──────────┐
                    │  OpenAI  │    │ Google Gemini │   │  Skills  │
                    │   API    │    │     API       │   │ (browser,│
                    └──────────┘    └──────────────┘   │  email,  │
                                                       │  cursor) │
                    ┌──────────┐                       └──────────┘
                    │ Vapi AI  │ ← Phone calls
                    │(+1 917-  │   (outbound + inbound)
                    │ 962-8631)│
                    └──────────┘
```

- **Mac Mini M2** (8 GB RAM, Apple Silicon) — runs the agent natively
- **OpenClaw Gateway** — always-on daemon managed by launchd
- **LLMs via API** — no local models (hardware too constrained); OpenAI as primary, Gemini as fallback
- **Vapi AI** — outbound and inbound phone calls via AI voice agent "Riley" (+19179628631)
- **Skills (17 ready)** — browser automation, Gmail/Calendar/Drive (gog OAuth),
  email triage (himalaya IMAP), Apple Reminders, GitHub, coding-agent, and more

## Repository Layout

```
IgorOpenClaw/
├── README.md              ← You are here
├── SETUP_GUIDE.md         ← Full installation walkthrough (paste into Gemini for guided help)
├── .cursorrules           ← Instructions for Cursor AI agents editing this repo
├── .env.example           ← Template for secrets (copy to .env, never commit .env)
├── .gitignore
├── config/
│   ├── openclaw.json.template ← Config template (token injected from .env by setup.sh)
│   ├── riley-voice-behavior.md ← Vapi assistant voicemail + callback policy (merge into Riley prompt)
│   └── cron/
│       └── jobs.json      ← Scheduled task definitions
├── workspace/             ← OpenClaw agent workspace files (symlinked to ~/.openclaw/workspace/)
│   ├── AGENTS.md          ← Operational rules, task routing, delegation, question style (y/n, multiple choice)
│   ├── SOUL.md            ← Agent personality and communication style
│   ├── USER.md            ← User context (timezone, preferences, accounts)
│   ├── TOOLS.md           ← Available tools and environment notes
│   ├── MEMORY.md          ← Agent persistent state (active tasks, completed log, learned patterns)
│   └── HEARTBEAT.md       ← Proactive behavior guidelines (references cron/jobs.json)
└── scripts/
    ├── setup.sh           ← Bootstrap: copy config from template, symlink workspace+cron, daemon install
    ├── uninstall.sh       ← Teardown (remove symlinks, stop daemon, remove LaunchAgent)
    ├── contacts.py        ← Apple Contacts lookup (searches all synced sources)
    ├── email-search.py    ← Email search wrapper (standard flags, searches both Gmail+Yahoo)
    ├── imessage.py        ← iMessage/SMS read & send helper (chat.db + AppleScript)
    ├── whatsapp.py        ← WhatsApp bridge message reader (parses gateway logs)
    ├── vapi-call.py       ← Outbound/inbound phone calls via Vapi AI voice agent
    ├── api-spend-check.py ← Daily API spend report (OpenAI, Vapi, Cursor status)
    ├── system-health-check.py ← Gateway/disk/error health check (silent when healthy)
    └── daily-restart.sh   ← Daily gateway restart via launchd (4 AM ET)
```

## Quick Start

```bash
# 1. Clone and enter the repo
git clone <this-repo-url>
cd IgorOpenClaw

# 2. Create your secrets file
cp .env.example .env
chmod 600 .env
# Edit .env with your real API keys

# 3. Install OpenClaw (requires Node.js 22+)
npm install -g openclaw@latest

# 4. Run the setup script (generates ~/.openclaw/openclaw.json, symlinks workspace + cron, installs daemon)
bash scripts/setup.sh

# 5. Verify
openclaw gateway status
```

For the full step-by-step walkthrough, see [SETUP_GUIDE.md](SETUP_GUIDE.md).

## Configuration

Configuration lives in `config/openclaw.json.template`. The auth token uses a `__OPENCLAW_AUTH_TOKEN__` placeholder — `scripts/setup.sh` copies the template to `~/.openclaw/openclaw.json` and injects the real token from `.env`.

`setup.sh` also injects all API keys and environment variables from `.env` into the LaunchAgent plist so they are available to the gateway process and cron scripts. This is critical — running `openclaw doctor --fix` will reinstall the plist and wipe these injected variables. Always re-run `bash scripts/setup.sh` after `doctor --fix`.

After editing the template or `.env`, re-run setup:

```bash
bash scripts/setup.sh    # re-injects config, env vars, and restarts gateway
```

Agent workspace files (`workspace/*.md`) take effect on the next agent turn without a restart.

## Troubleshooting

- **`restored corrupted WhatsApp creds.json` repeating in `/tmp/openclaw/openclaw-*.log`** — the WhatsApp Web session file is unstable (often alongside `status 499` disconnects). Re-pair the channel: `openclaw channels add --channel whatsapp`, ensure a single gateway instance, and check disk space. `scripts/system-health-check.py` alerts only when several restores occur within the **last 2 hours** (so old log noise alone does not keep firing). The script exits **1** when it prints alerts, **0** when healthy.
- **`No pages available in the connected browser`** — managed Chrome has no tab yet; use `browser navigate` first (see `workspace/TOOLS.md`). The post-restart cron warms the browser with `about:blank` after the daily 4 AM gateway restart.

## Security

- Gateway binds to `127.0.0.1` only (never exposed to the network)
- Authentication token required for all gateway access (injected from `.env`, never committed)
- Config uses a template system — `config/openclaw.json.template` has a placeholder; real token is injected at setup time
- All secrets in `.env` (git-ignored, `chmod 600`)
- Comprehensive action logging enabled
- Agent requires user approval before irreversible actions (purchases, deletions, public posts)
- Browser sessions always cleaned up (`browser close`) to prevent resource leaks
- Ongoing tasks persisted to MEMORY.md with TTL (7-day default) and 48h staleness detection
- Phone calls require explicit user approval before dialing (including whether Riley may leave a callback number on voicemail); Riley never commits to payments
- Inbound calls answered by AI; messages relayed to owner via WhatsApp
- See the Security Hardening section in [SETUP_GUIDE.md](SETUP_GUIDE.md) for the full checklist
