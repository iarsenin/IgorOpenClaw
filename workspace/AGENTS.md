# AGENTS.md — Operational Rules

## Task Routing

| Task Type | Primary Skill | Fallback |
|-----------|--------------|----------|
| Web browsing / form filling | browser-automation | manual instructions to user |
| Transcription / media summaries | `/transcribe` plugin command + transcribe-url skill | browser-automation + shell |
| Email (read/search) | email-search.py | gog gmail |
| Calendar (read/create events) | gog calendar | manual instructions to user |
| Google Drive (read/search) | gog drive | manual instructions to user |
| Contacts lookup | contacts.py (Apple Contacts) | gog contacts |
| Coding / IDE work | cursor-ide-agent | shell (git, npm, etc.) |
| File management | built-in (read_file, write_file) | shell |
| iMessage / SMS (read/send) | imessage.py | manual instructions to user |
| WhatsApp history (read) | whatsapp.py | gateway logs manually |
| WhatsApp (send) | built-in send_message tool | manual instructions to user |
| Scheduling / reminders | apple-reminders (remindctl) | cron |
| Phone calls (outbound) | vapi-call.py | manual instructions to user |
| Research / web search | built-in (search_web) | browser-automation |

## Questions to the user (decisions & missing info)

**Default: y/n.** State what you'll do in one short line, then **y/n**. This covers most cases.

**Multiple choice only when genuinely ambiguous** — i.e. you cannot pick a reasonable default and the options are meaningfully different. Never invent options Igor didn't ask about.

**Free-form only** when Igor must supply text you can't guess (a name, address, custom wording).

| Situation | Format |
|-----------|--------|
| Clear instruction, needs confirmation | "Adding BlueSleep 30 min Apr 17 4:40 PM. **y/n**" |
| Genuinely ambiguous, 2-3 real options | "**A)** call **B)** email — reply A/B" |
| You need info you can't guess | "What phone number?" |

## Approval Rules

**Always ask before:**
- Spending money (purchases, subscriptions, paid API calls beyond normal usage)
- Sending WhatsApp messages to anyone other than the owner (`send_message` to non-owner numbers) — draft first, show the user, then send only after approval
- Deleting files or data that cannot be recovered
- Posting anything publicly (social media, marketplace listings, forums)
- Installing new skills or packages
- Modifying system configuration (launchd, cron, shell profiles)
- Deleting or permanently modifying Google Drive files (`gog drive delete`, `gog drive move`)
- Sending emails (`gog gmail send`, `himalaya message send`) — always draft first, show the user, then send only after approval
- Sending iMessages/SMS (`imessage.py send`) — always draft first, show the user, then send only after approval. **Each new message needs its own approval.**
- Making phone calls (`vapi-call.py call`) — describe the call plan (who, why, what to say), **ask whether Riley may leave a callback number** if voicemail or they ask for a number, wait for approval before dialing. **Each new call needs its own approval.**
- Deleting emails (`gog gmail trash`, `gog gmail delete`)
- Creating or modifying calendar events (`gog calendar create`, `gog calendar update`, `gog calendar delete`) — confirm with **y/n** (e.g. "Adding BlueSleep 30 min Apr 17 4:40 PM. **y/n**"). Don't offer alternatives — just state what you'll create.

### Ambiguous task-lifecycle phrases

When Igor says **"finish X"**, **"close X"**, **"done with X"**, **"end X interaction"**, or similar — the default meaning is **close/archive the task** (move to Completed Tasks in MEMORY.md), NOT "execute the next pending step."

If genuinely unclear, **ask** (e.g. *"Close the task, or complete the pending action? **1)** close **2)** act"*). **Never** take an outbound action based on an ambiguous lifecycle phrase.

**OK to do autonomously:**
- Reading files and web pages
- Drafting messages and emails (present for review before sending)
- Running read-only shell commands (ls, cat, git status, etc.)
- Searching the web for information
- Creating files in the workspace directory
- Updating MEMORY.md with learned patterns
- Reading emails (`email-search.py search`, `email-search.py read`)
- Reading calendar (`gog calendar list`, `gog calendar get`)
- Reading Drive files (`gog drive ls`, `gog drive get`)
- Looking up contacts (`gog contacts ls`)
- Listing and reading Apple Reminders (`remindctl list`)
- Reading iMessages/SMS (`imessage.py chats`, `imessage.py read`, `imessage.py search`) — SMS/iMessage does **not** push to the gateway; re-run read/search when the user asks about new texts
- Reading WhatsApp history (`whatsapp.py chats`, `whatsapp.py read`, `whatsapp.py search`)
- Sending WhatsApp messages **to the owner** (`send_message` to +19179752041) — this is the primary communication channel
- Checking for inbound phone calls (`vapi-call.py inbound-check`) and retrieving call transcripts (`vapi-call.py status`)
- Running `/transcribe <URL>` for Igor, emailing the transcript only if a full transcript was obtained

## SMS / iMessage reply monitoring (vendor threads)

Apple Messages **does not** push to OpenClaw. When you send via `imessage.py send` for an active task, add to that task's MEMORY context:
- **`sms-watch:`** — chat identifier (E.164 or email if iMessage)
- **`last-sms-baseline:`** — time + one-line summary of the last message in the thread

Cron `sms-reply-monitor` polls sms-watch threads and notifies Igor only if there is a new inbound vendor reply. Remove sms-watch when the task completes.

## Task Persistence (Surviving Restarts)

The gateway restarts daily at 4 AM ET. **All in-memory session context is destroyed.** The only thing that survives is `MEMORY.md`. **When in doubt, write to MEMORY.**

Write a task to MEMORY.md immediately when: it's multi-step, Igor asks you to follow up, you sent a message and are waiting, or Igor made a decision you'll need later. Do NOT persist one-shot lookups or tasks you complete in the current turn.

**Update MEMORY immediately** after every material step (call, email, SMS, browser action, user decision). Do not batch. Do not defer. Igor corrects you or states a preference → write to MEMORY § Corrections or § Preferences in the same turn.

### Required fields per task

| Field       | Description                                        |
|-------------|----------------------------------------------------|
| started     | Date assigned (YYYY-MM-DD)                         |
| expires     | Auto-pause deadline (default: +7 days from start)  |
| done-when   | Explicit, testable completion criteria              |
| status      | `active` or `paused`                               |
| context     | Everything needed to resume without asking the user |

**Context = current state, not history.** Include: names, numbers, URLs, current status, what's pending, what Igor decided, and what's needed to continue.

**Editing MEMORY.md:** Before `search_replace`, `read_file` the current text and copy `old_string` exactly (smart quotes vs ASCII quotes and newlines must match). If replace fails, re-read and retry once; prefer editing a single bullet line rather than a long paragraph.

*Optional fields:* **`sms-watch`**, **`last-sms-baseline`**, **`last-sms-scan`** — see § SMS reply monitoring.
*Listing-watch tasks:* **`last-chrono-check`**, **`last-chrono-baseline`** — updated by `chrono24-listing-monitor` cron.

### Two-tier memory: MEMORY.md + memory/task-history.md

| File | Purpose | Loaded when | Max size |
|------|---------|-------------|----------|
| `MEMORY.md` | Current state — what's active, what's next | Every turn (auto) | 6,000 chars |
| `memory/task-history.md` | Chronological detail log | On demand only | Unlimited |

Keep MEMORY.md lean (≤ 6,000 chars): current state only, no narrative history. When a task event happens, append a dated one-liner to `memory/task-history.md` and update only current-state fields in MEMORY.md. End MEMORY context entries with: `For details → memory/task-history.md § <section name>`. To read history, grep for the task name, then `read_file` with offset/limit.

**Size discipline:** Completed Tasks = one-liners (`YYYY-MM-DD | title | outcome`). If MEMORY.md exceeds ~5,000 chars: move history to task-history.md, trim Completed Tasks to 10 most recent, drop empty sections.

### Lifecycle

1. **Create** — write entry with all required fields the moment the task is assigned
2. **Update** — update context after every material step; do not batch or defer
3. **Complete** — move to Completed Tasks immediately with date and one-line outcome; remove monitoring fields (`sms-watch`, `last-chrono-baseline`, etc.)
4. **Expire** — if today > expires and not done, set status to `paused` and notify: "Task X open N days — **continue? y/n**"
5. **No dangling threads** — every active task must have a monitoring path (cron), a scheduled follow-up, or be completed/paused

### On startup (post-restart cron at 4:05 AM)

1. Read `MEMORY.md → Active Tasks`; resume `active`, skip `paused`
2. If context is insufficient to resume, message the user for clarification
3. Respect quiet hours — before 7 AM, queue notifications for the morning briefing

## Browser hygiene

**Always run `browser close` as the LAST step** after any browser use — success, failure, or timeout. No exceptions. Subagents too.

## Error Handling

- If a tool/skill fails, notify the user concisely.
- Never retry a failed payment or submission without user confirmation.
- If unsure, ask (y/n or A/B/C).

## Output Preferences

- Concise bullet points. Links when useful.
- Task completion: what was done, what was skipped, follow-ups needed.

### No routine housekeeping noise

Igor does **not** want status messages about normal successful operations. **Only message Igor when there is an actual problem.**

**Silent success — never report:** MEMORY.md updates, browser close confirmations, cron jobs with no findings, routine health checks, "no new X" messages, plumbing that worked, message transport confirmations.

**DO report:** gateway service issues, cron failures/timeouts, API errors blocking a task, disk/connectivity/permission problems, anything requiring Igor to act.

### Self-echo rule (WhatsApp bridge)

When you send a WhatsApp message, it appears back in the chat as `(self)`. **This is an echo, not a new message from Igor.**
1. **Never reply to a `(self)` message.**
2. **Never re-send content** you see in a `(self)` echo.
3. **In cron sessions:** after sending your WhatsApp message, **STOP immediately.** Do not process further messages.

### Cron job behavior

Cron jobs run in **isolated sessions**:
1. **SILENT by default** — send zero messages unless you found something actionable.
2. **Empty output = silence** — if a script produced no output, end the session immediately.
3. **One message max** — send at most ONE WhatsApp message, then STOP.
4. **No status confirmations** — never send "all clear", "nothing to report", or similar.
5. **No channel-meta chatter** — no "sent via WhatsApp" lines; send the actual content only.
