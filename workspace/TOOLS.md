# TOOLS.md — Available Tools & Environment

## Environment

- **OS:** macOS (Apple Silicon). **Shell:** zsh. **OpenClaw:** 2026.4.15. **Node:** 24.15.0.
- **Config:** `~/.openclaw/openclaw.json` (generated from `config/openclaw.json.template` by `scripts/setup.sh`).
- **Workspace:** `~/.openclaw/workspace/` (symlinked from repo `workspace/`). Reference workspace files by bare name (`MEMORY.md`), never prefix with `workspace/`.
- **Cron store:** `~/.openclaw/cron/jobs.json` (writable; seeded from repo `config/cron/jobs.json`).
- **Gateway shell PATH:** `python3` and `grep` only — `python` and `rg` are NOT available.
- **Repo path:** `$OPENCLAW_REPO` is pre-set in the daemon env. ALWAYS use it for scripts — never hard-code:

```bash
python3 "$OPENCLAW_REPO/scripts/SCRIPT_NAME" [args]
```

- **After `openclaw update`, `doctor --fix`, or `gateway install`:** re-run `bash "$OPENCLAW_REPO/scripts/setup.sh"` to restore daemon env, `/transcribe` plugin, and cron store.

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

**When to broaden the search:** If a `--from` search returns zero results, try:
1. `--folder all` (searches all folders, not just inbox)
2. `--body` or `--subject` with a keyword instead of sender
3. Both accounts explicitly: `--account gmail` then `--account yahoo`
Note: some senders (e.g. medical portals) use a noreply domain different from the brand name.

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

## Media Transcription — `/transcribe` plugin

Igor sends `/transcribe <URL>` via WhatsApp. The linked OpenClaw plugin runs the helper directly (bypasses the chat model):

```bash
python3 "$OPENCLAW_REPO/scripts/transcribe-url.py" run "<URL>" --email-to "igor.arsenin@gmail.com" --json
```

Behavior: prefers canonical feeds/existing transcripts, falls back to `yt-dlp` + `ffmpeg` + Whisper. Reply is title + 3-5 bullets. Email is sent **only when a full transcript was obtained**; otherwise WhatsApp summary only.

## Browser Rules

Flow: `browser navigate` → `browser snapshot` (get `ref` like `e123`) → `browser act` (ref + action, both required) → **`browser close` (mandatory, always)**.

- Use `ref` from snapshot, NOT CSS selectors. Do NOT pass `refs: "aria"` — not supported by this Chrome profile.
- **Cold start:** on `No pages available in the connected browser`, run `browser navigate` first (target URL or `about:blank`) before snapshotting. The post-restart warm-up leaves one `about:blank` tab open — don't close it.
- **chrono24.com** blocks non-browser requests (use browser, never `web_fetch`).
- **Anti-bot interstitial** (e.g. "Verify you are human"): do NOT automate. Leave browser open for Igor to solve manually, report blocked state, skip the usual `browser close`.

## Apple Contacts — via contacts.py

```bash
python3 "$OPENCLAW_REPO/scripts/contacts.py" search "Neil Tancre"
python3 "$OPENCLAW_REPO/scripts/contacts.py" search "Gitstein"
python3 "$OPENCLAW_REPO/scripts/contacts.py" search "850-490"
python3 "$OPENCLAW_REPO/scripts/contacts.py" get "Neil Tancre"
python3 "$OPENCLAW_REPO/scripts/contacts.py" list --limit 50
```

**Reading contacts is FULLY AUTONOMOUS** — never requires approval, never "blocked". If Igor mentions a person by name (for a call, email, SMS, etc.), the first thing you do is run `contacts.py search <name>` yourself. Only ask Igor for the number if the lookup chain (Apple Contacts → `gog contacts` → `imessage.py search` → `email-search.py`) all return nothing. Do NOT skip the lookup and ask for the number.

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

1. **Resolve the number yourself (autonomous)** — `contacts.py search <name>`, then `gog contacts ls`, then `imessage.py search`, then `email-search.py`. Only ask Igor for the number if all four return nothing. Never ask Igor for a number you haven't tried to look up.
2. Draft call plan + ask about callback → get user approval (one y/n line).
3. `vapi-call.py call <number> <instructions>` (include goals + YES/NO callback lines).
4. Async: wait 30s, poll `status <call_id>` every 60s until `ended`.
5. Read transcript + report, summarize for user.

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

- **NEVER pass `host`, `security`, or `ask` in exec calls.** Gateway defaults are correct (`host: "gateway"`, `security: "full"`, `ask: "off"`). Overriding breaks cron: `host: "auto"` → rejected; `security: "allowlist"` → denied; `ask: "on-miss"` → cron can't wait.
- **Compound commands are BLOCKED by exec preflight.** One command per call — no `sleep N;`, no `&&`, no `$(...)`, no multi-line scripts.
- **NEVER read or edit files under `scripts/`.** They live outside the workspace sandbox and are opaque — run them, never patch. If a script fails, report the error and stop; do not invent workarounds.
- **`$OPENCLAW_REPO` IS set** in the daemon env. Use it directly — never hard-code or reason that it isn't resolving.

## Safety Levels

- **low:** run without confirmation
- **medium:** log, run if within AGENTS.md autonomous rules
- **high:** always ask user first
