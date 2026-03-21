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

## Email Access

**DO NOT use the browser tool for Gmail.** The browser bridge is unreliable.
Use IMAP/SMTP instead — credentials are available as environment variables:
- `GMAIL_USER` — Gmail address
- `GMAIL_APP_PASSWORD` — Gmail app-specific password
Use shell commands with `curl` or the `gog` CLI to access email.
If `gog` is not installed, use Python's `imaplib`/`smtplib` via a shell one-liner.

## Browser Tool Limitations

The built-in browser tool requires Chrome with remote debugging. It is fragile.
**Do NOT suggest the Browser Relay extension** — it is not installed and adds
unnecessary complexity. For web tasks, prefer `search_web` or `curl`. If you
truly need browser automation, use the `browser-automation` Playwright skill.

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
