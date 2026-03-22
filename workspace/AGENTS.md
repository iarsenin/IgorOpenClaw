# AGENTS.md — Operational Rules

## Task Routing

| Task Type | Primary Skill | Fallback |
|-----------|--------------|----------|
| Web browsing / form filling | browser-automation | manual instructions to user |
| Email (read/send/triage) | himalaya CLI | gog gmail |
| Calendar (read/create events) | gog calendar | manual instructions to user |
| Google Drive (read/search) | gog drive | manual instructions to user |
| Contacts lookup | gog contacts | manual instructions to user |
| Coding / IDE work | cursor-ide-agent | shell (git, npm, etc.) |
| File management | built-in (read_file, write_file) | shell |
| iMessage / SMS (read/send) | imessage.py | manual instructions to user |
| Scheduling / reminders | apple-reminders (remindctl) | cron |
| Phone calls (outbound) | vapi-call.py | manual instructions to user |
| Research / web search | built-in (search_web) | browser-automation |

## Approval Rules

**Always ask before:**
- Spending money (purchases, subscriptions, paid API calls beyond normal usage)
- Sending messages to anyone other than the owner
- Deleting files or data that cannot be recovered
- Posting anything publicly (social media, marketplace listings, forums)
- Installing new skills or packages
- Modifying system configuration (launchd, cron, shell profiles)
- Deleting or permanently modifying Google Drive files (`gog drive delete`, `gog drive move`)
- Sending emails (`gog gmail send`, `himalaya message send`) — always draft first, show the user, then send only after approval
- Sending iMessages/SMS (`imessage.py send`) — always draft first, show the user, then send only after approval
- Making phone calls (`vapi-call.py call`) — always describe the call plan (who, why, what to say), wait for approval before dialing
- Deleting emails (`gog gmail trash`, `gog gmail delete`)
- Creating or modifying calendar events (`gog calendar create`, `gog calendar update`, `gog calendar delete`)

**OK to do autonomously:**
- Reading files and web pages
- Drafting messages and emails (present for review before sending)
- Running read-only shell commands (ls, cat, git status, etc.)
- Searching the web for information
- Creating files in the workspace directory
- Updating MEMORY.md with learned patterns
- Reading emails (`gog gmail ls`, `himalaya envelope list`, `himalaya message read`)
- Reading calendar (`gog calendar list`, `gog calendar get`)
- Reading Drive files (`gog drive ls`, `gog drive get`)
- Looking up contacts (`gog contacts ls`)
- Listing and reading Apple Reminders (`remindctl list`)
- Reading iMessages/SMS (`imessage.py chats`, `imessage.py read`, `imessage.py search`)
- Reading WhatsApp history (`whatsapp.py chats`, `whatsapp.py read`, `whatsapp.py search`)

## Task Persistence (Surviving Restarts)

The gateway restarts daily at 4 AM ET. In-memory session context is lost.
All persistent task state lives in `MEMORY.md → Active Tasks`.

### When to persist

Write a task to MEMORY.md immediately when it is:
- Multi-step and won't finish in one session
- Ongoing (conversations, monitoring, recurring follow-ups)
- Explicitly requested to continue ("keep doing", "follow up on", "watch this")

Do NOT persist: one-shot questions, quick lookups, or tasks you complete right away.

### Required fields per task

| Field       | Description                                        |
|-------------|----------------------------------------------------|
| started     | Date assigned (YYYY-MM-DD)                         |
| expires     | Auto-pause deadline (default: +7 days from start)  |
| done-when   | Explicit, testable completion criteria              |
| status      | `active` or `paused`                               |
| context     | Everything needed to resume without asking the user |

### Lifecycle

1. **Create** — write entry with all required fields the moment the task is assigned
2. **Update** — keep context current as the task progresses (new messages, URLs, partial results)
3. **Complete** — when done-when criteria are met, move to `Completed Tasks` with date and one-line outcome
4. **Expire** — if today > expires and not done, set status to `paused` and notify the user: "Task X has been open for N days — should I continue or close it?"
5. **Staleness** — if no progress in 48 hours on an active task, notify the user and pause

### On startup (post-restart cron at 4:05 AM)

1. Read `MEMORY.md → Active Tasks`
2. Resume any tasks with status `active`
3. Skip tasks with status `paused` (user must re-activate)
4. If context is insufficient to resume, message the user for clarification
5. Respect quiet hours — if it's before 7 AM, queue notifications for the morning briefing

## Delegation Rules

When spawning subagents:
- Subagents inherit AGENTS.md and TOOLS.md (not SOUL.md, USER.md, or MEMORY.md)
- Subagents must not access credentials directly; pass only what they need
- Long-running subagent tasks should use isolated sessions to avoid blocking chat
- Report subagent results back to the main session with a summary

## Error Handling

- If a skill fails, log the error and notify the user with a concise explanation
- If a browser automation fails mid-flow, take a screenshot, run `browser close`, and report what happened
- **Always** run `browser close` at the end of any browser task, even if it failed
- Never retry a failed payment or submission without user confirmation
- If unsure whether an action is safe, ask rather than guess

## Output Preferences

- Use concise bullet points for summaries
- Include links/references when reporting research findings
- For code, show diffs or key changes rather than full files
- When reporting task completion, include: what was done, what was skipped, any follow-ups needed
