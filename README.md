# IgorOpenClaw

> **STATUS: ACTIVE (restored 2026-04-18).** Gateway, LaunchAgents, cron, and the local `/transcribe` plugin are back in service.
> Keep `config/`, `workspace/`, and `scripts/` as the source of truth, then re-run `bash scripts/setup.sh` after runtime repairs or upgrades.

Version-controlled configuration and workspace for an always-on [OpenClaw](https://github.com/openclaw/openclaw) autonomous AI agent running on a Mac Mini M2.

## Purpose

This repository is the single source of truth for an OpenClaw agent that:

- Runs 24/7 as a macOS LaunchAgent daemon
- Accepts instructions via WhatsApp and executes tasks autonomously
- Uses **OpenAI** (primary) and **Google Gemini** (fallback) as LLM providers
- Automates browser interactions, email, iMessage/SMS, phone calls (Vapi AI), file management, and coding workflows
- Handles `/transcribe <URL>` requests with a deterministic OpenClaw plugin command backed by `scripts/transcribe-url.py`, canonical feed/provider transcript discovery, speaker-label cleanup, fallback transcription, a concise 3-5 bullet WhatsApp summary, and email delivery when a full transcript exists
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
│   ├── MEMORY.template.md ← Tracked template for local runtime memory file
│   ├── MEMORY.md          ← Local-only runtime state (git-ignored)
│   └── HEARTBEAT.md       ← Proactive behavior guidelines (references repo cron template)
└── scripts/
    ├── setup.sh           ← Bootstrap: copy config, symlink workspace, seed live cron store, daemon install
    ├── uninstall.sh       ← Teardown (remove workspace link/live cron store, stop daemon, remove LaunchAgent)
    ├── contacts.py        ← Apple Contacts lookup (searches all synced sources)
    ├── email-search.py    ← Email search wrapper (standard flags, searches both Gmail+Yahoo)
    ├── imessage.py        ← iMessage/SMS read & send helper (chat.db + AppleScript)
    ├── whatsapp.py        ← WhatsApp bridge message reader (parses gateway logs)
    ├── vapi-call.py       ← Outbound/inbound phone calls via Vapi AI voice agent
    ├── api-spend-check.py ← Daily API spend report (OpenAI, Vapi, Cursor status)
    ├── system-health-check.py ← Gateway/disk/error health check (silent when healthy)
    ├── transcribe-url.py  ← URL transcript + summary + email pipeline
    └── daily-restart.sh   ← Daily gateway restart via launchd (4 AM ET)

openclaw-plugins/
└── transcribe-command/
    ├── package.json       ← Declares the OpenClaw extension entrypoint
    ├── openclaw.plugin.json ← Optional metadata for plugin inspection/listing
    └── index.js           ← Deterministic `/transcribe` OpenClaw command plugin
```

## Slash Commands: Plugin vs Skill

For this repo, a live slash command such as `/transcribe <URL>` should be implemented as an
**OpenClaw plugin**, not as a skill-only workflow.

Why:
- **Skills** are prompt/runtime guidance for the agent after a message has already reached model dispatch.
- A skill can help the agent reason about a transcript request, but it does **not** guarantee that a WhatsApp slash command will be intercepted deterministically.
- For hard command behavior, the gateway needs a **plugin hook** that runs before model dispatch.

What works for WhatsApp:
- Put the command in `openclaw-plugins/<plugin-name>/`
- Include `package.json` with an `openclaw.extensions` entry pointing to `index.js`
- Keep `openclaw.plugin.json` for plugin metadata / inspection
- In `index.js`, export a plugin and use `api.on("before_dispatch", ...)`
- Match the wrapped inbound body format used by WhatsApp, not just a bare `/command ...`
- Return `{ handled: true, text: "..." }` to stop model dispatch and send the final reply directly
- Optionally also call `api.registerCommand(...)` for non-WhatsApp surfaces, but do **not** rely on `registerCommand()` alone for the WhatsApp path

What to avoid:
- Do **not** assume that adding a skill is enough for a live slash command
- Do **not** assume `api.registerCommand()` alone will catch WhatsApp `/...` messages
- Do **not** let a user-facing slash command depend on the model deciding whether to run shell steps

The `/transcribe` implementation in this repo is the reference pattern.

## Quick Start

```bash
# 1. Clone and enter the repo
git clone <this-repo-url>
cd IgorOpenClaw

# 2. Create your secrets file
cp .env.example .env
chmod 600 .env
# Edit .env with your real API keys

# 3. Install OpenClaw (requires Node.js 22+, Node 24 via Homebrew recommended)
npm install -g openclaw@latest

# 4. Run the setup script (generates ~/.openclaw/openclaw.json, symlinks workspace, seeds live cron store, installs daemon)
bash scripts/setup.sh

# 5. Verify
openclaw gateway status
```

For the full step-by-step walkthrough, see [SETUP_GUIDE.md](SETUP_GUIDE.md).

## Configuration

Configuration lives in `config/openclaw.json.template`. The auth token uses a `__OPENCLAW_AUTH_TOKEN__` placeholder — `scripts/setup.sh` copies the template to `~/.openclaw/openclaw.json` and injects the real token from `.env`.

Current repo default models:
- Primary: `openai/gpt-5.4-mini`
- Fallback: `google/gemini-2.5-pro`
- DM session scope: `per-account-channel-peer` (isolates WhatsApp DMs per sender/account)

`setup.sh` also injects all API keys and environment variables from `.env` into the LaunchAgent plist so they are available to the gateway process and cron scripts. This is critical — running `openclaw doctor --fix` will reinstall the plist and wipe these injected variables. Always re-run `bash scripts/setup.sh` after `doctor --fix`.

After editing the template or `.env`, re-run setup:

```bash
bash scripts/setup.sh    # re-injects config, env vars, and restarts gateway
```

Agent workspace files (`workspace/*.md`) take effect on the next agent turn without a restart.

`workspace/MEMORY.md` is intentionally local-only (git-ignored) because it contains fast-changing operational state and personal context. The repository tracks `workspace/MEMORY.template.md`; `scripts/setup.sh` initializes `workspace/MEMORY.md` from that template when missing.

## Upgrading OpenClaw

For this repo, the safest upgrade path is:

```bash
brew install node@24
export PATH="/opt/homebrew/opt/node@24/bin:/opt/homebrew/bin:$PATH"

openclaw update || npm install -g openclaw@latest
bash scripts/setup.sh
```

Why `setup.sh` matters after an upgrade:

- `openclaw gateway install` and `openclaw doctor --fix` can rewrite the LaunchAgent plist and wipe injected env vars like `OPENCLAW_REPO`, API keys, and keyring passwords
- OpenClaw 2026.4+ uses a writable live cron store at `~/.openclaw/cron/jobs.json`, so repo cron changes need to be re-seeded into that live file
- This repo depends on a linked local plugin at `openclaw-plugins/transcribe-command/`, and `setup.sh` re-installs it after config/gateway changes
- `setup.sh` also restores the daily restart LaunchAgent and preserves the current live model object when re-generating `~/.openclaw/openclaw.json`

Verify the upgrade:

```bash
openclaw --version
openclaw plugins inspect transcribe-command
openclaw cron list
openclaw channels list
```

If `openclaw gateway status` looks flaky right after the upgrade, trust the process/log checks above first, then retry the status command after the restart settles.

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

- **`No pages available in the connected browser`** — managed Chrome has no tab yet; use `browser navigate` first (see `workspace/TOOLS.md`). The post-restart cron now leaves one shared `about:blank` tab open after the daily 4 AM gateway restart so later browser actions have a page to attach to.
- **Cron updates not taking effect** — OpenClaw 2026.4+ keeps a writable live cron store at `~/.openclaw/cron/jobs.json` with runtime fields like `createdAtMs`, `updatedAtMs`, and job state. Re-run `bash scripts/setup.sh` to re-seed that live store from `config/cron/jobs.json`, then verify with `openclaw cron list` or apply direct runtime edits with `openclaw cron edit`.
- **`/transcribe` underperforms on media URLs** — install `yt-dlp` and `ffmpeg` locally. The helper can work without them in simpler cases, but YouTube/extractor/media-conversion fallbacks are much stronger with both installed.
- **`/transcribe` fails on missing Python modules** — re-run `bash scripts/setup.sh`; it now installs the required user-scoped Python helpers (`requests`, `beautifulsoup4`) for the Homebrew `python3` runtime.

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
# 1. Reset main-agent session state — archives old sessions and starts fresh
python3 scripts/reset-main-sessions.py

# 2. Apply model object atomically (avoid partial primary/fallback updates)
openclaw config set agents.defaults.model '{"primary":"openai/gpt-5.4-mini","fallbacks":["google/gemini-2.5-pro"]}' --strict-json

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

## Restoring Clawd

Complete checklist to bring the agent back online after the 2026-04-06 shutdown:

1. **Add OpenAI credits** — [platform.openai.com/settings/billing](https://platform.openai.com/settings/billing)
   Then restore the primary model in `config/openclaw.json.template`:
   ```
   primary: "openai/gpt-5.4-mini",
   fallbacks: ["google/gemini-2.5-pro"],
   ```

2. **Add Yahoo email credentials** to `.env` (currently missing):
   ```
   YAHOO_USER=arsenin@yahoo.com
   YAHOO_APP_PASSWORD=<yahoo-app-password>
   ```

3. **Run setup** to install LaunchAgents and start the gateway:
   ```bash
   bash scripts/setup.sh
   ```

4. **Re-pair WhatsApp** (session had 440 conflict at shutdown):
   - On iPhone: WhatsApp → Settings → Linked Devices → log out all devices
   - Then: `openclaw channels login --channel whatsapp`

5. **Verify**: `openclaw gateway status` and check WhatsApp delivers a test message.

See `SETUP_GUIDE.md` for the full detailed walkthrough.

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
