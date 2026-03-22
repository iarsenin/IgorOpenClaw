# TOOLS.md — Available Tools & Environment

## Environment

- **OS:** macOS (Apple Silicon / ARM64)
- **Shell:** zsh
- **Node.js:** 22.22.1 (via nvm at ~/.nvm/versions/node/v22.22.1/)
- **OpenClaw:** 2026.3.13
- **OpenClaw config:** ~/.openclaw/openclaw.json (symlinked from repo config/)
- **OpenClaw workspace:** ~/.openclaw/workspace/ (symlinked from repo workspace/)
- **Repo location:** ~/Library/CloudStorage/GoogleDrive-igor.arsenin@gmail.com/My Drive/git/IgorOpenClaw

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

**Always run `browser close` when done with a browser task.** Every browser
session must end with cleanup — no exceptions. Leaving tabs open wastes memory
and blocks the Chrome debug port for future tasks.

Pattern for every browser task:
1. `browser navigate <url>`
2. Do your work (act, extract, screenshot, etc.)
3. `browser close` — **mandatory final step**

The built-in browser tool requires Chrome with remote debugging. It is fragile.
**Do NOT suggest the Browser Relay extension** — it is not installed and adds
unnecessary complexity. For web tasks, prefer `search_web` or `curl`. If you
truly need browser automation, use the `browser-automation` Playwright skill.

## iMessage / SMS — via scripts/imessage.py

Read and send iMessages and SMS texts via the Messages.app database and AppleScript.
Requires Full Disk Access granted to the node binary.

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
- **Sending ALWAYS requires explicit user approval** — use `openclaw message send` only after showing draft
- Only covers messages since the gateway started logging (not full WhatsApp history)
- "Check my messages" = iMessage/SMS; "Check my WhatsApp" = this tool
- "Check all my messages" = iMessage/SMS + WhatsApp + email

## WhatsApp Messaging — CRITICAL FORMAT

When sending WhatsApp messages via the `send_message` tool, the `target` MUST be in
**E.164 format** — that means the full phone number WITH the `+` prefix.

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

Make outbound phone calls using Vapi AI voice agent. Clawd provides
task-specific instructions, Vapi handles the conversation, and returns
a transcript and structured report.

**Outbound number:** +1 (917) 962-8631

### Commands

```bash
REPO=~/Library/CloudStorage/GoogleDrive-igor.arsenin@gmail.com/My\ Drive/git/IgorOpenClaw

# Make a call (ALWAYS requires user approval first)
python3 "$REPO/scripts/vapi-call.py" call "+12125551234" "Schedule a fridge repair estimate for Tuesday. Ask for a free estimate."

# Check call status and get transcript
python3 "$REPO/scripts/vapi-call.py" status <call_id>

# List recent calls
python3 "$REPO/scripts/vapi-call.py" list --limit 10
```

### Rules
- **ALWAYS requires explicit user approval before dialing** — describe who you're calling, why, and what you'll say. Wait for confirmation.
- After the call, retrieve the transcript and structured report, then summarize for the user
- Never make calls during quiet hours (11 PM – 7 AM ET) unless explicitly asked
- The Vapi assistant cannot commit to payments or final decisions — it will defer to Igor
- Cost is ~11 cents/minute — mention this if the user asks about a long call
- If a call fails or goes to voicemail, report the outcome and ask about next steps

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
