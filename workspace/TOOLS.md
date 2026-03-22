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
- **Gateway shell:** Prefer **`python3`** (not `python`) and **`grep`** — **`rg` (ripgrep) is often missing** from the daemon PATH and will fail (`command not found: rg`).

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

### Mandatory sequence

1. `browser navigate` / open tab (only if needed)
2. Do your work (act, extract, screenshot, etc.)
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

## iMessage / SMS — via scripts/imessage.py

Read and send iMessages and SMS texts via the Messages.app database and AppleScript.
Requires Full Disk Access granted to the node binary.

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

Read WhatsApp chat history from OpenClaw gateway logs. Covers messages
from the past 7 days by default (adjustable with `--days`).

### Commands

```bash
REPO=~/Library/CloudStorage/GoogleDrive-igor.arsenin@gmail.com/My\ Drive/git/IgorOpenClaw

# List recent WhatsApp chats
python3 "$REPO/scripts/whatsapp.py" chats --limit 20

# Read messages with a specific contact
python3 "$REPO/scripts/whatsapp.py" read "+19176997436" --limit 20

# Search WhatsApp messages
python3 "$REPO/scripts/whatsapp.py" search "meeting tomorrow" --limit 10
```

### Rules
- **Reading is autonomous** — "check my WhatsApp", "what did X say" can be done without asking
- **Sending ALWAYS requires explicit user approval** — use the built-in `send_message` tool (see WhatsApp Messaging section below) only after showing draft and getting confirmation
- Only covers messages since the gateway started logging (not full WhatsApp history)
- "Check my messages" = iMessage/SMS; "Check my WhatsApp" = this tool
- "Check all my messages" = iMessage/SMS + WhatsApp + email

## WhatsApp Messaging — send_message tool (CRITICAL FORMAT)

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

1. Clawd receives a task requiring a phone call (e.g. "call the plumber")
2. Clawd drafts a call plan: who, why, what to say — **and asks about callback-number authorization** — presents to user for approval
3. On approval, Clawd runs `vapi-call.py call <number> <instructions>` (instructions include task goals **and** the YES/NO callback lines)
4. The script POSTs to Vapi API with `assistantOverrides` containing the task + voicemail rules
5. Vapi places the call via Riley, who follows her system prompt + task instructions
6. After the call ends, Clawd runs `vapi-call.py status <call_id>` to retrieve:
   - Transcript (full conversation)
   - Structured report (summary, outcome, follow-ups)
   - Recording URL
7. Clawd summarizes the result for the user

### Polling for call results

After `vapi-call.py call` returns, the call is **async** — Riley is talking while
Clawd waits. Do NOT immediately run `status`; the call hasn't finished yet.

1. Wait **30 seconds** after initiating the call
2. Run `vapi-call.py status <call_id>`
3. If status is still `in-progress` or `ringing`, wait **60 seconds** and check again
4. Repeat until status is `ended` (most calls end within 1–5 minutes)
5. Once ended, read the transcript and structured report

If the user is in a live chat, tell them: "Call is in progress — I'll share the
transcript when it's done." Then poll in the background.

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

**You MUST include ALL relevant details in the task_instructions.** Be specific:

BAD:  `"Call about the fridge repair"`
GOOD: `"Call ABC Appliance Repair to schedule a fridge repair estimate. The fridge is a Samsung French Door, model RF28R7351SR, it stopped cooling yesterday. Igor is available Tuesday or Friday afternoon. Ask for a free in-home estimate. If they quote a price for the visit, note it but don't commit.\nOwner authorizes leaving callback number: YES\nCallback to provide: +19179752041"`

Include: business name, what's needed, relevant details (model numbers, dates,
prior conversations), Igor's constraints, what outcome you want, **and** the
callback YES/NO lines after Igor approves.

### How inbound calls work

1. Someone dials +1 (917) 962-8631
2. Vapi routes the call to Riley (assigned as inbound assistant in Vapi dashboard)
3. Riley answers: "Hello, this is Riley, Igor Arsenin's assistant. How can I help you?"
4. Riley takes a message: asks who's calling, what it's about, callback number, urgency
5. Riley blocks spam/telemarketers
6. Every 30 minutes, the `inbound-call-check` cron job runs `vapi-call.py inbound-check`
7. If new inbound calls are found, Clawd sends Igor a WhatsApp summary
8. Seen calls are tracked in `.vapi-seen-calls` (git-ignored) to avoid duplicate alerts

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
| `OPENAI_ADMIN_KEY` | Org-level admin key (Usage+Billing **Read** only) — used by `api-spend-check` cron to fetch daily OpenAI costs. Create at [platform.openai.com/settings/organization/api-keys](https://platform.openai.com/settings/organization/api-keys); restrict scopes to Usage=Read, Billing=Read. |
| Cursor token | Not a `.env` var — read at runtime from `~/Library/Application Support/Cursor/User/globalStorage/state.vscdb` key `cursorAuth/accessToken` (refreshed automatically when Cursor is open). Used by `api-spend-check` to fetch plan status and request counts from `api2.cursor.sh`. |

### Troubleshooting

- **SSL errors:** macOS Python 3.10 may lack certificates. The script auto-falls back to unverified SSL. Install `certifi` (`pip3 install certifi`) for proper verification.
- **403 / Cloudflare errors:** The script uses `User-Agent: OpenClaw/1.0` to avoid blocks. If Vapi changes their WAF rules, update the User-Agent header.
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
