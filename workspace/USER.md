# USER.md — User Context

## Owner

- **Name:** Igor Arsenin
- **Location:** New York, NY 10011 (Chelsea)
- **Timezone:** America/New_York
- **Best days for in-person visits:** Tuesday and Friday (works from home)

## Contact Info

| Channel | Identifier | Notes |
|---------|-----------|-------|
| Personal phone | +19179752041 | Igor's main cell; WhatsApp primary channel to Clawd |
| Apple Messages (SMS/iMessage) | same number / iMessage IDs | **Not** pushed to OpenClaw — Clawd only sees these when running `imessage.py` or when Igor pastes into WhatsApp |
| Secondary WhatsApp | +19176997436 | Also on allowlist |
| Gmail | igor.arsenin@gmail.com | Primary email |
| Yahoo | arsenin@yahoo.com | Secondary email |
| Vapi (AI phone) | +19179628631 | Outbound/inbound via Riley voice agent |

## Tools & Subscriptions

- **Cursor Pro** — IDE for coding; agent can be invoked via cursor-ide-agent skill
- **Google Gemini Ultra** — paid consumer subscription (web/app access only, NOT API)
- **OpenAI API** — paid, key in .env
- **Google Gemini API** — paid, key in .env (separate from Ultra subscription)
- **Alpha Vantage** — financial data API, key in .env
- **Gmail** — IMAP/SMTP access via app password in .env (himalaya CLI)
- **Yahoo** — IMAP/SMTP access via app password in .env (himalaya CLI); rate-limit sensitive
- **Vapi AI** — phone call platform; private API key in .env; voice agent "Riley"
- **iMessage/SMS** — read via chat.db, send via AppleScript (requires Full Disk Access for python3 binary)
- **WhatsApp** — real-time send/receive via OpenClaw gateway bridge; history via log parsing

## Hardware

- **Mac Mini M2** — Apple Silicon, 8 GB RAM, macOS Sequoia 15.7.4
- Constraint: cannot run local LLMs effectively; all inference via API

## Communication Preferences

- Primary channel to the agent: **WhatsApp** (to +19179752041) — this is what wakes Clawd in real time
- **SMS / iMessage (Messages.app):** used for many vendors and contacts; Clawd does **not** receive these automatically (see `TOOLS.md` § iMessage / SMS)
- Prefers bullet-point summaries over long prose
- When the agent needs a **decision or missing detail**, prefers **yes/no** or **multiple-choice** questions over open-ended questions when the topic allows (see `AGENTS.md` § Questions to the user — agent should not force the format when it does not fit)
- Wants explicit confirmation prompts before any action that costs money or is irreversible
- Timezone-aware: avoid sending non-urgent notifications between 11 PM and 7 AM ET
- "Check my email" = both Gmail and Yahoo
- "Check my messages" = iMessage/SMS only
- "Check all my messages" = iMessage/SMS + WhatsApp + email

## Working Style

- Tends to brainstorm ideas and then delegate refinement to the agent
- Values multi-perspective analysis (e.g., asking two different LLMs to critique each other)
- Expects the agent to proactively suggest improvements or flag issues
