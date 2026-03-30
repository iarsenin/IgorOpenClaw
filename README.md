# IgorOpenClaw

Version-controlled configuration and workspace for an always-on [OpenClaw](https://github.com/openclaw/openclaw) autonomous AI agent running on a Mac Mini M2.

## Purpose

This repository is the single source of truth for an OpenClaw agent that:

- Runs 24/7 as a macOS LaunchAgent daemon
- Accepts instructions via WhatsApp and executes tasks autonomously
- Uses **Google Gemini** (primary) and **OpenAI** (fallback) as LLM providers
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
- **LLMs via API** — no local models (hardware too constrained); Gemini as primary, OpenAI as fallback
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
│   ├── MEMORY.template.md ← Tracked template for local runtime memory file
│   ├── MEMORY.md          ← Local-only runtime state (git-ignored)
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

Current repo default models:
- Primary: `google/gemini-2.5-pro`
- Fallback: `openai/gpt-5.4-mini`

`setup.sh` also injects all API keys and environment variables from `.env` into the LaunchAgent plist so they are available to the gateway process and cron scripts. This is critical — running `openclaw doctor --fix` will reinstall the plist and wipe these injected variables. Always re-run `bash scripts/setup.sh` after `doctor --fix`.

After editing the template or `.env`, re-run setup:

```bash
bash scripts/setup.sh    # re-injects config, env vars, and restarts gateway
```

Agent workspace files (`workspace/*.md`) take effect on the next agent turn without a restart.

`workspace/MEMORY.md` is intentionally local-only (git-ignored) because it contains fast-changing operational state and personal context. The repository tracks `workspace/MEMORY.template.md`; `scripts/setup.sh` initializes `workspace/MEMORY.md` from that template when missing.

## Troubleshooting

### WhatsApp creds restore loop (health check ALERT)

If `python3 scripts/system-health-check.py` reports *WhatsApp creds.json restore loop in the last 2h*, the gateway is repeatedly fixing a broken session file — that is a **live** problem, not a stale log. The check exits **1** in that case; it exits **0** when there is no output.

**Recovery (do in order):**

1. **One gateway only** — `pgrep -fl "dist/index.js gateway"` should show a single main process. If you see duplicates, unload extras: `launchctl unload ~/Library/LaunchAgents/ai.openclaw.gateway.plist`, then `launchctl load …` once.
2. **Re-pair WhatsApp** — `openclaw channels add --channel whatsapp` and complete QR / linking on the Mac (session must finish successfully).
3. **Restart gateway** — `openclaw gateway restart` (or `bash scripts/setup.sh` if you also need plist env vars).
4. **Re-check** — wait a few minutes, then run `python3 scripts/system-health-check.py` again. After restores stop, the rolling **2h** window will clear; you need fewer than 5 restore lines in that window for silence.

Also ensure **disk space** is healthy and avoid putting `~/.openclaw/credentials` under iCloud/Desktop sync (can corrupt JSON mid-write).

### Other

- **`No pages available in the connected browser`** — managed Chrome has no tab yet; use `browser navigate` first (see `workspace/TOOLS.md`). The post-restart cron warms the browser with `about:blank` after the daily 4 AM gateway restart.
- **Cron updates not taking effect** — newer OpenClaw releases may keep a writable live copy at `~/.openclaw/cron/jobs.json` (not a symlink). Re-run `bash scripts/setup.sh` to re-seed from repo config, then verify with `openclaw cron list` or apply direct runtime edits with `openclaw cron edit`.

### API keys suddenly "not set" in cron reports

Symptom examples:
- `OpenAI: OPENAI_ADMIN_KEY not set`
- `Vapi: VAPI_API_KEY not set`
- morning brief shows missing `GOG_KEYRING_PASSWORD`

Root cause is usually incomplete `.env` combined with a daemon reinstall/restart path (`openclaw doctor --fix` or setup), so LaunchAgent starts without those vars.

Verify quickly:

```bash
rg '^(OPENAI_ADMIN_KEY|VAPI_API_KEY|GOG_KEYRING_PASSWORD)=' .env
launchctl print gui/$(id -u)/ai.openclaw.gateway | rg 'OPENAI_ADMIN_KEY|VAPI_API_KEY|GOG_KEYRING_PASSWORD'
```

Fix:

1. Add missing keys to `.env` (`OPENAI_ADMIN_KEY`, `VAPI_API_KEY`, `GOG_KEYRING_PASSWORD`).
2. Re-run setup: `bash scripts/setup.sh`
3. Re-check daemon env with `launchctl print ...`
4. Test immediately: `openclaw cron run api-spend-check`

`scripts/setup.sh` now attempts to recover these keys from an existing LaunchAgent plist when `.env` is incomplete and prints a warning if critical vars are still missing. It cannot recover keys that are absent from both `.env` and plist.

### Runtime/config version mismatch ("written by newer OpenClaw")

If logs show `Config was last written by a newer OpenClaw (...)`, your global CLI/runtime was downgraded relative to your config.

Verify:

```bash
openclaw --version
npm show openclaw version
```

Fix:

```bash
npm install -g openclaw@latest
bash scripts/setup.sh
openclaw gateway restart
openclaw gateway status
```

### Clawd not responding (LiveSessionModelSwitchError)

Symptom examples:
- `Gateway agent failed; falling back to embedded: ... LiveSessionModelSwitchError`
- cron jobs erroring after model changes with mixed provider/model traces

This usually means stale live sessions are pinned to an old model while defaults changed.

Fast recovery:

```bash
# 1. Wipe ALL session state — this is the nuclear fix
rm -f ~/.openclaw/agents/main/sessions/sessions.json
rm -f ~/.openclaw/agents/main/sessions/*.jsonl

# 2. Apply model object atomically (avoid partial primary/fallback updates)
openclaw config set agents.defaults.model '{"primary":"google/gemini-2.5-pro","fallbacks":["openai/gpt-5.4-mini"]}' --strict-json

# 3. Restart and verify
openclaw gateway restart
openclaw gateway status
openclaw agent --agent main --message "Reply with OK only." --json
```

If sessions are not wiped, accumulated conversation history can exceed model context windows (especially gpt-5.4-mini at 391K), causing "input exceeds context window" errors every time.

### Cron jobs reporting "error" but messages delivered (false positive)

Cron jobs that explicitly send WhatsApp via the agent's `message` tool may report a "Delivering to WhatsApp requires target" error in the cron status even though the actual message was delivered. This happens because the cron delivery layer also tries to send the agent's final response text, which fails in isolated sessions with no originating channel.

Fix: Disable announce delivery for all cron jobs:

```bash
for job in $(openclaw cron list --json | python3 -c "import sys,json; [print(j['id']) for j in json.loads(sys.stdin.read())]"); do
  openclaw cron edit "$job" --no-deliver
done
openclaw gateway restart
```

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
