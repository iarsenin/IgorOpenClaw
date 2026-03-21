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

## Browser Tool Limitations

The built-in browser tool requires Chrome with remote debugging. It is fragile.
**Do NOT suggest the Browser Relay extension** — it is not installed and adds
unnecessary complexity. For web tasks, prefer `search_web` or `curl`. If you
truly need browser automation, use the `browser-automation` Playwright skill.

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
