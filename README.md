# IgorOpenClaw

Version-controlled configuration and workspace for an always-on [OpenClaw](https://github.com/openclaw/openclaw) autonomous AI agent running on a Mac Mini M2.

## Purpose

This repository is the single source of truth for an OpenClaw agent that:

- Runs 24/7 as a macOS LaunchAgent daemon
- Accepts instructions via WhatsApp and executes tasks autonomously
- Uses **OpenAI** (primary) and **Google Gemini** (fallback) as LLM providers
- Automates browser interactions, email, file management, and coding workflows
- Integrates with Cursor IDE for autonomous coding and research

The agent acts on its owner's behalf — browsing the web, managing email, running shell commands, and orchestrating multi-step workflows — while requiring explicit approval before irreversible actions.

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
                                                       └──────────┘
```

- **Mac Mini M2** (8 GB RAM, Apple Silicon) — runs the agent natively
- **OpenClaw Gateway** — always-on daemon managed by launchd
- **LLMs via API** — no local models (hardware too constrained); OpenAI as primary, Gemini as fallback
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
│   └── cron/
│       └── jobs.json      ← Scheduled task definitions
├── workspace/             ← OpenClaw agent workspace files (symlinked to ~/.openclaw/workspace/)
│   ├── AGENTS.md          ← Operational rules, task routing, delegation
│   ├── SOUL.md            ← Agent personality and communication style
│   ├── USER.md            ← User context (timezone, preferences, accounts)
│   ├── TOOLS.md           ← Available tools and environment notes
│   ├── MEMORY.md          ← Agent-maintained learned patterns
│   └── HEARTBEAT.md       ← Proactive scheduled tasks
└── scripts/
    ├── setup.sh           ← One-command bootstrap (symlinks, dirs, daemon install)
    └── uninstall.sh       ← Teardown (remove symlinks, stop daemon)
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

# 4. Run the setup script (symlinks config, installs daemon)
bash scripts/setup.sh

# 5. Verify
openclaw gateway status
```

For the full step-by-step walkthrough, see [SETUP_GUIDE.md](SETUP_GUIDE.md).

## Configuration

Configuration lives in `config/openclaw.json.template`. The auth token uses a `__OPENCLAW_AUTH_TOKEN__` placeholder — `scripts/setup.sh` copies the template to `~/.openclaw/openclaw.json` and injects the real token from `.env`. After editing the template, re-run setup and restart:

```bash
openclaw gateway restart
```

Agent workspace files (`workspace/*.md`) take effect on the next agent turn without a restart.

## Security

- Gateway binds to `127.0.0.1` only (never exposed to the network)
- Authentication token required for all gateway access (injected from `.env`, never committed)
- Config uses a template system — `config/openclaw.json.template` has a placeholder; real token is injected at setup time
- All secrets in `.env` (git-ignored, `chmod 600`)
- Comprehensive action logging enabled
- Agent requires user approval before irreversible actions (purchases, deletions, public posts)
- See the Security Hardening section in [SETUP_GUIDE.md](SETUP_GUIDE.md) for the full checklist
