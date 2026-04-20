# TOOLS.md — Available Tools & Environment

## Environment

- **OS:** macOS (Apple Silicon / ARM64)
- **Shell:** zsh
- **Node.js:** 24.15.0 (Homebrew preferred; `scripts/setup.sh` targets `/opt/homebrew/opt/node@24/bin/node`)
- **OpenClaw:** 2026.4.15
- **OpenClaw config:** `~/.openclaw/openclaw.json` — copied from `config/openclaw.json.template` by `scripts/setup.sh`
- **OpenClaw workspace:** `~/.openclaw/workspace/` — symlinked from repo `workspace/`
- **Cron jobs:** `~/.openclaw/cron/jobs.json` — writable live store seeded from repo `config/cron/jobs.json`
- **Gateway shell:** Use `python3` (NOT `python`). Use `grep` (NOT `rg`). Both `python` and `rg` are NOT in the daemon PATH.
- **Upgrade rule:** After `openclaw update`, `openclaw doctor --fix`, or `openclaw gateway install`, re-run `bash "$OPENCLAW_REPO/scripts/setup.sh"` to restore daemon env vars, the linked `/transcribe` plugin, and the live cron store
- **Workspace file paths:** Use just `MEMORY.md`, `AGENTS.md`, etc. — never prefix with `workspace/`.
- **Repo path:** The env var `$OPENCLAW_REPO` is pre-set in the daemon. Use it for ALL script calls:

```bash
python3 "$OPENCLAW_REPO/scripts/SCRIPT_NAME" [args]
```

**NEVER** hard-code or re-define the repo path. Always use `$OPENCLAW_REPO`.

## Interaction with Igor (quick replies)

Prefer **yes/no** or **multiple choice** (A/B/C) questions when possible. Full rules: `AGENTS.md`.

## Bundled Skills (ready)

- **healthcheck** — Security hardening and risk auditing
- **openai-image-gen** — Batch-generate images via OpenAI Images API
- **openai-whisper-api** — Transcribe audio via OpenAI Whisper API
- **weather** — Weather via wttr.in or Open-Meteo (no API key)
- **skill-creator** — Create/edit/audit agent skills
- **node-connect** — Diagnose OpenClaw connection failures
- **`/transcribe` plugin command** — Deterministic transcript pipeline for media URLs

## Bundled Skills (need CLI dependencies)

- **gog** (Google Workspace) — Gmail, Calendar, Drive, Contacts. Auth: file-based keyring (`GOG_KEYRING_PASSWORD` in plist).
- **coding-agent** — Delegate coding tasks to Codex/Claude Code
- **github** — GitHub operations via `gh` CLI
- **gemini** — Gemini CLI for Q&A, summaries
- **peekaboo** — Capture and automate macOS UI
- **apple-notes / apple-reminders** — Apple Notes and Reminders via CLI

## Email Access — via email-search.py

**DO NOT use the browser for email. DO NOT call `himalaya` directly.**

Igor has TWO accounts (gmail: igor.arsenin@gmail.com, yahoo: arsenin@yahoo.com) used **interchangeably**.

### Search (both accounts by default)

```bash
python3 "$OPENCLAW_REPO/scripts/email-search.py" search --from acme
python3 "$OPENCLAW_REPO/scripts/email-search.py" search --from acme --after 2025-10-01
python3 "$OPENCLAW_REPO/scripts/email-search.py" search --subject invoice
python3 "$OPENCLAW_REPO/scripts/email-search.py" search --body "payment due" --after 2025-06-01
python3 "$OPENCLAW_REPO/scripts/email-search.py" search --to someone --folder sent
python3 "$OPENCLAW_REPO/scripts/email-search.py" search --from acme --folder all
python3 "$OPENCLAW_REPO/scripts/email-search.py" search --from acme --account yahoo
```

Flags: `--from`, `--to`, `--subject`, `--body`, `--after YYYY-MM-DD`, `--before YYYY-MM-DD`
Folder: `--folder inbox` (default), `sent`, `all`, `drafts`, `trash`
  - Yahoo `all` searches Inbox+Sent+Draft+Trash and prints IDs as `<Folder>:<ID>`; pass that same ID to `read --account yahoo --id ...`
Account: `--account both` (default), `gmail`, `yahoo`

**Broaden if zero results:** try `--folder all`, then `--body`/`--subject` keyword, then each account separately. Medical portals often use noreply domains different from the brand name.

### Read a specific email

```bash
python3 "$OPENCLAW_REPO/scripts/email-search.py" read --account gmail --id 25176
python3 "$OPENCLAW_REPO/scripts/email-search.py" read --account yahoo --id 395956
```

### Reply (himalaya only for replies)

```bash
himalaya message reply --account gmail <ID>
himalaya message reply --account yahoo <ID>
```

ALWAYS draft first, show user, send only after approval.

### Rules
- **Any email search = ALWAYS search BOTH accounts** (`--account both` is the default). Narrow only when Igor says "check my Gmail/Yahoo".
- When replying, use the account that received the original email.
- NEVER send without showing the draft first.
- Yahoo rate-limit: if unavailable, script prints a note and returns Gmail results. Do NOT retry Yahoo more than once per 30 min.

## Media Transcription — `/transcribe` plugin + transcribe-url.py

Slash command syntax from Igor:

```text
/transcribe <URL>
```

The linked OpenClaw plugin runs the helper directly, bypassing the chat model (`api.on("before_dispatch", ...)`). For new slash commands: implement as an OpenClaw plugin, not skill-only; `api.registerCommand()` alone is not enough for WhatsApp.

Underlying helper:

```bash
python3 "$OPENCLAW_REPO/scripts/transcribe-url.py" run "<URL>" --email-to "igor.arsenin@gmail.com" --json
```

Behavior:
- Checks access first; if direct access fails, tries alternate public retrieval paths
- Prefers canonical publisher feeds and existing full transcripts over re-transcribing
- Checks provider transcript endpoints exposed by podcast feeds before downloading audio
- Relabels generic transcript speakers like `Speaker 1` when hosts/guests identify themselves clearly
- Falls back to audio download + transcription when needed
- Formats the WhatsApp reply as a concise title plus 3-5 bullets instead of one dense paragraph
- Sends email only when a **full transcript** was actually obtained
- If transcript is impossible, still send a concise WhatsApp summary/status, but **do not send email**

Dependencies:
- `yt-dlp` strongly recommended for YouTube and many embedded media pages
- `ffmpeg` strongly recommended for audio format conversion before transcription

## Browser Rules

**Always `browser close` when done.** Use `ref` from `browser snapshot`, NOT CSS selectors. Exception: after the daily restart, leave the intentional shared `about:blank` warm-up tab open.

**Cold start:** If you see `No pages available in the connected browser`, the managed Chrome has no tab yet. Run `browser navigate` to your target URL (or `about:blank` first) before `browser snapshot` — never snapshot first on a fresh session. The post-restart warm-up intentionally leaves one blank tab open so later sessions can attach cleanly.

**`refs=aria` is NOT supported.** The managed Chrome debug profile does not have Playwright `_snapshotForAI` support. Never pass `refs: "aria"` to `browser snapshot` — it will error. Use default refs mode (omit the refs parameter entirely).

1. `browser navigate` to page
2. `browser snapshot` to get refs (e.g. `e123`)
3. `browser act` with `ref: "e123"` + `action` (both required)
4. `browser close` when done (mandatory — success, failure, or timeout)

Cron jobs using browser must end with `browser close`. **chrono24.com** blocks non-browser requests.

If a site shows a human-verification / anti-bot interstitial such as Chrono24's "Verify you are human", do not try to automate or click through it. Leave the managed browser open for Igor to solve manually, report that the task is blocked on verification, and resume normal browser cleanup only after the real page is accessible again.

## Apple Contacts — via contacts.py

```bash
python3 "$OPENCLAW_REPO/scripts/contacts.py" search "Neil Tancre"
python3 "$OPENCLAW_REPO/scripts/contacts.py" search "850-490"
python3 "$OPENCLAW_REPO/scripts/contacts.py" get "Neil Tancre"
python3 "$OPENCLAW_REPO/scripts/contacts.py" list --limit 50
```

Reading is autonomous. **Preferred first step** for finding phone numbers or emails.

## iMessage / SMS — via imessage.py

**Apple Messages does NOT connect to the gateway.** Only WhatsApp wakes Clawd. Cron `sms-reply-monitor` polls every 2h.

```bash
python3 "$OPENCLAW_REPO/scripts/imessage.py" chats --limit 20
python3 "$OPENCLAW_REPO/scripts/imessage.py" read "+19176997436" --limit 15
python3 "$OPENCLAW_REPO/scripts/imessage.py" search "dinner tomorrow" --limit 10
python3 "$OPENCLAW_REPO/scripts/imessage.py" send "+19176997436" "Got it, thanks!"
```

Reading is autonomous. Sending ALWAYS requires approval. "Check my messages" = iMessage/SMS.

## WhatsApp History — via whatsapp.py

Reads **Clawd-Igor bridge messages** only (past 7 days). Does NOT access Igor's chats with other people.

**Contact lookup chain:**
1. `python3 "$OPENCLAW_REPO/scripts/contacts.py" search "Name"`
2. `gog contacts ls --query "Name"`
3. `python3 "$OPENCLAW_REPO/scripts/imessage.py" search "Name"`
4. `python3 "$OPENCLAW_REPO/scripts/email-search.py" search --from name`
5. Ask Igor

```bash
python3 "$OPENCLAW_REPO/scripts/whatsapp.py" chats --limit 20
python3 "$OPENCLAW_REPO/scripts/whatsapp.py" read "+19176997436" --limit 20
python3 "$OPENCLAW_REPO/scripts/whatsapp.py" search "meeting tomorrow" --limit 10
```

## WhatsApp Messaging — send_message tool

Built-in `send_message` is **send-only**. Target MUST be **E.164** with `+` (e.g. `+19176997436`). Names or missing `+` will fail. For groups, use JID.

## Phone Calls — via vapi-call.py

Voice agent "Riley" makes/receives calls. Cost: ~11 cents/minute.

```bash
python3 "$OPENCLAW_REPO/scripts/vapi-call.py" call "+12125551234" "Schedule repair. Ask for free estimate."
python3 "$OPENCLAW_REPO/scripts/vapi-call.py" status <call_id>
python3 "$OPENCLAW_REPO/scripts/vapi-call.py" list --limit 10
python3 "$OPENCLAW_REPO/scripts/vapi-call.py" inbound-check
```

### Callback authorization (required before dialing)

Ask Igor: *"May Riley leave your callback number?"* Encode verbatim in task instructions:
- `Owner authorizes leaving callback number: YES` + `Callback to provide: +19179752041`
- Or: `Owner authorizes leaving callback number: NO`

### Outbound call flow

1. Draft call plan + ask about callback -> get user approval
2. `vapi-call.py call <number> <instructions>` (include goals + YES/NO lines)
3. Async: wait 30s, poll `status <call_id>` every 60s until `ended`
4. Read transcript + report, summarize for user

### Riley has NO shared context

Include ALL context in task_instructions (business name, numbers, dates, constraints). Riley knows nothing else.

### Rules
- Outbound calls ALWAYS require explicit user approval
- Inbound checking is autonomous (cron `inbound-call-check` every 30 min)
- Never call during quiet hours (11 PM - 7 AM ET) unless asked
- Riley cannot commit to payments or final decisions

## Built-in Tools

- execute_shell, read_file, write_file, search_web, send_message, cron

### Exec call rules — CRITICAL

**`$OPENCLAW_REPO` IS set** in the daemon env. Always: `python3 "$OPENCLAW_REPO/scripts/name.py" args`. If exec fails, **report the error and stop** — never try workarounds.

**NEVER pass `host`, `security`, or `ask` in exec calls.** Gateway defaults are correct (`host: "gateway"`, `security: "full"`, `ask: "off"`). Overriding breaks cron: `host: "auto"` → rejected; `security: "allowlist"` → denied; `ask: "on-miss"` → cron can't wait.

**Compound commands are BLOCKED.** Single direct commands only — no `sleep N;`, no `&&`, no `$(...)`, no multi-line. One command per exec call.

**NEVER read or edit script files.** Scripts at `$OPENCLAW_REPO/scripts/` are opaque — run them, never inspect or patch them. They are outside the workspace sandbox. If a script fails, report the error; do not attempt to fix the source.

## Safety Levels

- **low:** run without confirmation
- **medium:** log, run if within AGENTS.md autonomous rules
- **high:** always ask user first
