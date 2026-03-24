# TOOLS.md — Available Tools & Environment

## Environment

- **OS:** macOS (Apple Silicon / ARM64)
- **Shell:** zsh
- **Node.js:** 22.22.1 (via nvm at ~/.nvm/versions/node/v22.22.1/)
- **OpenClaw:** 2026.3.13
- **OpenClaw config:** `~/.openclaw/openclaw.json` — **copied** from `config/openclaw.json.template` by `scripts/setup.sh` (token injected from `.env`; file is git-ignored — **not** a symlink)
- **OpenClaw workspace:** `~/.openclaw/workspace/` — **symlinked** from repo `workspace/`
- **Cron jobs:** `~/.openclaw/cron/jobs.json` — **symlinked** from repo `config/cron/jobs.json`
- **Repo location:** ~/Library/CloudStorage/GoogleDrive-igor.arsenin@gmail.com/My Drive/git/IgorOpenClaw
- **Gateway shell:** Use **`python3`** — **`python` is NOT in the daemon PATH** and will fail (`command not found: python`). Use **`grep`** — **`rg` (ripgrep) is NOT in the daemon PATH** and will fail (`command not found: rg`).

## Interaction with Igor (quick replies)

When you need a **decision or extra information** from Igor, **prefer**:

- **Yes / no** questions when that fits.
- **Multiple choice** (options labeled **A/B/C** or **1/2/3**) when there are a few clear paths.

Do **not** force this when only an open-ended answer is appropriate. Full rules and examples: `workspace/AGENTS.md` § **Questions to the user**; style note in `workspace/SOUL.md` § Communication Style.

## Bundled Skills (ready)

### healthcheck
- Host security hardening and risk-tolerance auditing
- Firewall/SSH/update hardening, periodic security checks

### openai-image-gen
- Batch-generate images via OpenAI Images API

### openai-whisper-api
- Transcribe audio via OpenAI Whisper API

### weather
- Current weather and forecasts via wttr.in or Open-Meteo
- No API key needed

### skill-creator
- Create, edit, improve, or audit agent skills

### node-connect
- Diagnose OpenClaw node connection and pairing failures

## Bundled Skills (need CLI dependencies — install as needed)

### gog (Google Workspace)
- Gmail, Calendar, Drive, Contacts, Sheets, Docs via CLI
- Requires: gog CLI tool
- **Auth:** OAuth tokens stored in file-based keyring (not macOS Keychain — avoids popup prompts). The daemon has `GOG_KEYRING_PASSWORD` injected via the LaunchAgent plist. If gog auth fails, re-run `scripts/setup.sh` to ensure the env var is current.

### coding-agent
- Delegate coding tasks to Codex, Claude Code, or Pi agents
- Requires: codex or claude CLI binary

### github
- GitHub operations via `gh` CLI: issues, PRs, CI runs, code review
- Requires: gh CLI (`brew install gh`)

### gemini
- Gemini CLI for one-shot Q&A, summaries, generation
- Requires: gemini CLI tool

### peekaboo
- Capture and automate macOS UI
- Requires: peekaboo CLI

### apple-notes / apple-reminders
- Manage Apple Notes and Reminders via CLI
- Requires: memo / remindctl CLI tools

## ClawHub Skills (install via `npx clawhub install <name>`)

### browser-automation
- Web browsing, form filling, data extraction via Playwright
- STATUS: flagged suspicious by VirusTotal — review source code before installing
- Install: `npx clawhub install browser-automation --force` (only after review)

## Email Access — himalaya (IMAP/SMTP)

**DO NOT use the browser tool for email.** Use the `himalaya` CLI instead.

Igor has TWO email accounts. When he says "check my email" (without specifying),
**always check BOTH accounts** and present a single combined summary, grouped by
account. When replying or following up on a specific email, use the correct account.

### Accounts

| Account | Command flag | Address |
|---------|-------------|---------|
| Gmail (default) | `--account gmail` or omit | igor.arsenin@gmail.com |
| Yahoo | `--account yahoo` | arsenin@yahoo.com |

### Common commands

```bash
# List recent emails — BOTH accounts
himalaya envelope list --account gmail --page-size 10
himalaya envelope list --account yahoo --page-size 10

# Read a specific email
himalaya message read --account gmail <ID>
himalaya message read --account yahoo <ID>

# Search
himalaya envelope list --account gmail --query "from:someone@example.com"

# Reply (ALWAYS draft first, show user, send only after approval)
himalaya message reply --account gmail <ID>
himalaya message reply --account yahoo <ID>
```

### Rules
- "Check my email" = check BOTH accounts, aggregate results
- "Check my Gmail" = only Gmail
- "Check my Yahoo" = only Yahoo
- When replying, use the account that received the original email
- NEVER send without showing the draft to the user first

### Yahoo rate-limit protection
Yahoo blocks IMAP after too many rapid connections. Follow these rules:
- **If Yahoo returns "Server error" or "UNAVAILABLE":** do NOT retry immediately.
  Report the Gmail results, note "Yahoo is temporarily unavailable", and skip it.
- **Never retry Yahoo more than once per 30 minutes** after a failure.
- **Do not run multiple Yahoo connections in parallel** (e.g. list + search simultaneously).
- If Yahoo fails on a scheduled triage, skip it silently — it will recover on the next cycle.

## Browser Rules

**Always run `browser close` when done with a browser task.** Igor still sees
**Chrome windows left open** if you skip this — treat **`browser close` as part
of “done,”** not optional cleanup.

### Browser tool API

The browser tool uses **`ref` from snapshot**, NOT CSS selectors. Workflow:
1. `browser navigate` to the page
2. `browser snapshot` to get the page state with element **refs** (e.g. `e123`)
3. `browser act` with `ref: "e123"` to interact with elements

**Do NOT** use CSS selectors — the tool will error with *"'selector' is not supported. Use 'ref' from snapshot instead."*

### Mandatory sequence

1. `browser navigate` / open tab (only if needed)
2. Do your work (`snapshot` → `act` with refs, extract, screenshot, etc.)
3. **`browser close` — last command before** your final user-visible reply (WhatsApp) **or** before ending an isolated cron session
4. If step 2 **errors or times out**, still run step 3, **then** explain the failure

### Rules

- **No exceptions:** success, failure, timeout, user changes topic mid-flow — if you **opened** the browser this run, **close** it this run.
- **Cron jobs** that touch the browser (e.g. Chrono24 monitor) must end with **`browser close`**.
- **`post-restart-resume`** and **`system-health`** prompts also tell you to run **`browser close`** when clearing orphans — do it.

The built-in browser tool requires Chrome with remote debugging. It is fragile.
**Do NOT suggest the Browser Relay extension** — it is not installed and adds
unnecessary complexity. For web tasks, prefer `search_web` or `curl`. If you
truly need browser automation, use the `browser-automation` Playwright skill.

### Sites that block non-browser requests (must use browser tool)

- **chrono24.com** — Cloudflare returns HTTP 403 to `web_fetch` and `curl`. Always use `browser navigate` for Chrono24 pages.

## iMessage / SMS — via scripts/imessage.py

Read and send iMessages and SMS texts via the Messages.app database and AppleScript.
Requires Full Disk Access granted to the **python3 binary** (not node) — `imessage.py` is invoked via `python3`. Grant in: System Settings → Privacy & Security → Full Disk Access.

### CRITICAL: Not the same as WhatsApp (no live push to Clawd)

**Apple Messages (SMS / iMessage)** does **not** connect to the OpenClaw gateway.
Only **WhatsApp** messages to the bridge wake the agent in real time.

- Texts that appear **only** in the Messages app (e.g. vendor SMS like Precision)
  are **invisible** to Clawd until it runs `imessage.py` (or you **paste** the text
  into **WhatsApp**).
- **New replies** in an SMS thread after a one-off read are **not** notified —
  ask again (e.g. *“re-read the Precision SMS thread”*) or forward key lines on WhatsApp.
- For **active** tasks waiting on SMS vendors, Clawd should **re-check** `imessage.py read`
  when the user asks for status or after explicit “check Messages for X” instructions.
- **Automatic polling:** cron job **`sms-reply-monitor`** (see `config/cron/jobs.json`, ~every 2h
  8:30 AM–8:30 PM ET) reads `MEMORY.md` for **`sms-watch`** entries, runs `imessage.py read`,
  and WhatsApps Igor only when there is **new vendor inbound** since **`last-sms-baseline`**.
  When Clawd **sends** vendor SMS, it must set/update those fields per `AGENTS.md` § SMS reply monitoring.

### Commands

```bash
REPO=~/Library/CloudStorage/GoogleDrive-igor.arsenin@gmail.com/My\ Drive/git/IgorOpenClaw

# List recent chats (sorted by last activity)
python3 "$REPO/scripts/imessage.py" chats --limit 20

# Read last N messages from a contact (use E.164 number or email)
python3 "$REPO/scripts/imessage.py" read "+19176997436" --limit 15

# Search all messages by text
python3 "$REPO/scripts/imessage.py" search "dinner tomorrow" --limit 10

# Send a message (iMessage preferred, falls back to SMS)
python3 "$REPO/scripts/imessage.py" send "+19176997436" "Got it, thanks!"
```

### Rules
- **Reading is autonomous** — "check my texts", "read messages from X" can be done without asking
- **Sending ALWAYS requires explicit user approval** — draft the message, show it, wait for confirmation
- "Check my messages" = check iMessage/SMS (this tool), NOT WhatsApp or email
- "Check all my messages" = check iMessage/SMS + WhatsApp + email
- Use E.164 format for phone numbers (e.g. `+19176997436`)

## WhatsApp Message History — via scripts/whatsapp.py

Read **Clawd ↔ Igor bridge messages** from OpenClaw gateway logs. Covers the
past 7 days by default (adjustable with `--days`).

### CRITICAL LIMITATION

`whatsapp.py` **only reads the bridge channel** (Igor's self-messages to/from
Clawd on +19179752041). It does **NOT** have access to Igor's actual WhatsApp
conversations with other people.

**Do NOT use `whatsapp.py` to:**
- Look up someone's WhatsApp number
- Read Igor's chats with third parties
- Search for a contact name in WhatsApp

**To find a contact's phone number,** use (in order):
1. `gog contacts ls --query "Name"` — Google Contacts
2. `himalaya envelope list --query "from:name"` — search email for their number
3. `python3 "$REPO/scripts/imessage.py" search "Name"` — search iMessage/SMS
4. Ask Igor — he can share the contact card via WhatsApp

### Commands

```bash
REPO=~/Library/CloudStorage/GoogleDrive-igor.arsenin@gmail.com/My\ Drive/git/IgorOpenClaw

# List recent bridge chats (Igor ↔ Clawd only)
python3 "$REPO/scripts/whatsapp.py" chats --limit 20

# Read bridge messages
python3 "$REPO/scripts/whatsapp.py" read "+19176997436" --limit 20

# Search bridge message text
python3 "$REPO/scripts/whatsapp.py" search "meeting tomorrow" --limit 10
```

### Rules
- **Reading is autonomous** — "check my WhatsApp", "what did X say" can be done without asking
- **Sending ALWAYS requires explicit user approval** — use the built-in `send_message` tool (see WhatsApp Messaging section below) only after showing draft and getting confirmation
- Only covers **bridge** messages since the gateway started logging — NOT Igor's conversations with other contacts
- "Check my messages" = iMessage/SMS; "Check my WhatsApp" = this tool
- "Check all my messages" = iMessage/SMS + WhatsApp + email

## WhatsApp Messaging — send_message tool (CRITICAL FORMAT)

The built-in `send_message` tool is **send-only**. It does NOT support `read` or other actions — attempting `message action read` will error with *"Message action read not supported for channel whatsapp."* To **read** WhatsApp history, use `whatsapp.py` (see above).

To **send** WhatsApp messages, use the built-in `send_message` tool (NOT a script).
The `target` MUST be in **E.164 format** — the full phone number WITH the `+` prefix.

Examples of CORRECT targets:
- `+19176997436`
- `+19179752041`

Examples of WRONG targets (will fail with "requires target <E.164|group JID>"):
- `19176997436` (missing `+`)
- `Arturas Vaitaitis` (name, not a number)
- `@arturas` (not a phone number)

For group messages, use the WhatsApp group JID (e.g. `120363012345@g.us`).

If a user asks you to message someone by name, ask for their phone number first.
You CANNOT browse the WhatsApp chat list or contacts — this is a bridge limitation.

## Phone Calls — via Vapi AI (scripts/vapi-call.py)

Make and receive phone calls using a Vapi AI voice agent named "Riley."
For outbound calls, Clawd provides task-specific instructions per call;
Vapi handles the live conversation and returns a transcript + structured report.
Inbound calls are answered by Riley automatically (takes a message for Igor).

### Architecture

```
Outbound:  Clawd → vapi-call.py → Vapi REST API → Riley (voice agent) → recipient
Inbound:   caller → +19179628631 → Vapi → Riley answers, takes message
Polling:   cron (every 30 min) → vapi-call.py inbound-check → WhatsApp alert
```

- **Vapi account:** dashboard.vapi.ai (Igor's account)
- **Assistant name:** Riley (ID in env var `VAPI_ASSISTANT_ID`)
- **Phone number:** +1 (917) 962-8631 (ID in env var `VAPI_PHONE_NUMBER_ID`)
- **Fallback destination:** +19179752041 (Igor's cell — transfers if Riley is unavailable)
- **Model:** OpenAI gpt-4o (managed by Vapi, not our API key)
- **Cost:** ~11 cents/minute
- **System prompt:** Base prompt is edited in Vapi (dashboard or PATCH). **Canonical snippets** for voicemail + callback policy live in `config/riley-voice-behavior.md`. Every outbound call also injects the same voicemail rules via `assistantOverrides` in `vapi-call.py`.

### Commands

```bash
REPO=~/Library/CloudStorage/GoogleDrive-igor.arsenin@gmail.com/My\ Drive/git/IgorOpenClaw

# Make an outbound call (ALWAYS requires user approval first)
python3 "$REPO/scripts/vapi-call.py" call "+12125551234" "Schedule a fridge repair estimate for Tuesday. Ask for a free estimate."

# Check call status and get transcript
python3 "$REPO/scripts/vapi-call.py" status <call_id>

# List recent calls
python3 "$REPO/scripts/vapi-call.py" list --limit 10

# Check for new inbound calls (used by cron job, can also run manually)
python3 "$REPO/scripts/vapi-call.py" inbound-check
```

### Callback authorization (required before dialing)

Riley may only speak a callback number on voicemail (or when appropriate) if Igor
has **explicitly** authorized it for that call.

1. When you draft the call plan for approval, **ask**: e.g. *“If this goes to
   voicemail or they ask for a number, may Riley leave your callback number
   (+19179752041), or should she end without giving a number?”*
2. Encode the decision **verbatim** in the task string passed to `vapi-call.py`:

**Authorized** (use Igor’s cell or another number he specifies):

```text
Owner authorizes leaving callback number: YES
Callback to provide: +19179752041
```

**Not authorized** (include this line; or omit the YES block entirely):

```text
Owner authorizes leaving callback number: NO
```

Optional: Igor may prefer return calls to the Vapi line — then use
`Callback to provide: +19179628631` with the same YES line.

The script appends voicemail rules that **parse these exact lines**; do not
rephrase them.

### Voicemail behavior (Riley)

On voicemail: **very short** message — Riley’s name, one sentence purpose, then
the callback number **only if** YES + `Callback to provide:` are in the task.
Otherwise no digits. See `config/riley-voice-behavior.md` for full wording.

### How outbound calls work

1. Draft call plan (who, why, what to say) + ask about callback-number authorization → get user approval
2. Run `vapi-call.py call <number> <instructions>` (include task goals **and** YES/NO callback lines)
3. Call is **async** — wait 30s, then poll `vapi-call.py status <call_id>` every 60s until `ended`
4. Once ended, read transcript + structured report and summarize for the user

Tell the user: "Call is in progress — I'll share the transcript when it's done."

### CRITICAL: Riley is a separate AI with NO shared context

Riley is a standalone Vapi voice agent. She does NOT have access to:
- Clawd's conversation history or chat context
- MEMORY.md, TOOLS.md, or any workspace files
- Any prior calls or their transcripts
- The user's recent messages or requests

Riley only knows:
- Her base system prompt (Igor's name, location 10011, availability Tue/Fri,
  negotiation rules, spam handling)
- The `task_instructions` string you pass in the call command

**Include ALL relevant context in task_instructions:** business name, what's needed, model numbers, dates, Igor's constraints, desired outcome, and the callback YES/NO lines. Riley has no other context.

### How inbound calls work

1. Caller dials +19179628631 → Vapi routes to Riley → Riley takes message + blocks spam
2. Every 30 min: `inbound-call-check` cron runs `vapi-call.py inbound-check`
3. New calls → WhatsApp summary to Igor; seen calls tracked in `.vapi-seen-calls`

### Rules
- **Outbound calls ALWAYS require explicit user approval** — describe who you're calling, why, and what you'll say. Wait for confirmation.
- **Inbound call checking is autonomous** — the cron job runs automatically
- After any call, retrieve the transcript and structured report, then summarize for the user
- Never make calls during quiet hours (11 PM – 7 AM ET) unless explicitly asked
- Riley cannot commit to payments or final decisions — she defers to Igor
- Cost is ~11 cents/minute — mention this if the user asks about a long call
- If a call fails or goes to voicemail, report the outcome and ask about next steps

### Environment variables (in .env and launchd plist)

| Variable | Purpose |
|----------|---------|
| `VAPI_API_KEY` | Private API key for Vapi REST API |
| `VAPI_ASSISTANT_ID` | Riley assistant ID |
| `VAPI_PHONE_NUMBER_ID` | Vapi phone number ID (+19179628631) |
| `VAPI_PHONE_NUMBER` | The actual phone number (for display) |
| `OPENAI_ADMIN_KEY` | Org-level admin key (Usage+Billing Read only) — `api-spend-check` cron. Create at platform.openai.com/settings/organization/api-keys; scopes: Usage=Read, Billing=Read. |
| Cursor token | Runtime only — from `~/Library/Application Support/Cursor/User/globalStorage/state.vscdb` (`cursorAuth/accessToken`). `api-spend-check` plan status only; usage-based charges not in API → check cursor.com/settings. |

### Troubleshooting

- **SSL errors:** macOS Python may lack bundled certificates. Scripts use `certifi` when available, falling back to the macOS system keychain. Install `certifi` (`pip3 install certifi`) if you see SSL verification failures.
- **403 / Cloudflare errors:** `vapi-call.py` uses `User-Agent: OpenClaw/1.0`; `api-spend-check.py` uses a browser User-Agent for Vapi (Cloudflare can block non-browser UAs on GET endpoints). If calls start failing with 403, try updating the User-Agent header.
- **Call not connecting:** Check `vapi-call.py status <call_id>` for `endedReason`. Common: `customer-did-not-answer`, `customer-busy`.
- **Changing Riley's behavior:** Merge `config/riley-voice-behavior.md` into the assistant system prompt (Vapi dashboard or PATCH `/assistant/{VAPI_ASSISTANT_ID}`). Outbound voicemail rules are also injected per call by `vapi-call.py`.

## Built-in Tools

- execute_shell — run shell commands (safety: medium)
- read_file / write_file — filesystem access (safety: low)
- search_web — web search (safety: low)
- send_message — send via configured channels (safety: medium)
- cron — schedule tasks (safety: medium)

## Safety Levels

- **low:** can run without confirmation
- **medium:** log the action, run if within AGENTS.md autonomous rules
- **high:** always ask user before executing
