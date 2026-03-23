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
| WhatsApp history (read) | whatsapp.py | gateway logs manually |
| WhatsApp (send) | built-in send_message tool | manual instructions to user |
| Scheduling / reminders | apple-reminders (remindctl) | cron |
| Phone calls (outbound) | vapi-call.py | manual instructions to user |
| Research / web search | built-in (search_web) | browser-automation |

## Questions to the user (decisions & missing info)

When you need **additional information or a decision** from Igor, **default to formats he can answer quickly** on WhatsApp:

1. **Yes / no** when that fits — state the default or assumption, then ask clearly (e.g. *"Proceed with the Tuesday slot? **y/n**"*).
2. **Multiple choice** when there are a few distinct options — label them (**A / B / C** or **1 / 2 / 3**) and ask him to reply with the letter/number.

**Do not force** y/n or multiple choice when it would be awkward or misleading, for example:

- He must supply **free-form text** (a name, address, custom wording, creative copy).
- **Brainstorming** or open exploration is the point.
- A **nuanced tradeoff** needs a short explanation first — give that, then you may add *"If you want the default I suggested, reply **y**."*

**Examples**

| Avoid (open-ended) | Prefer |
|--------------------|--------|
| "What should I do next?" | "Next step: **A)** call them **B)** email **C)** pause — reply A/B/C" |
| "Does this work for you?" | "Use this subject line? **y/n**" |
| "How do you want to handle it?" | "**1)** reschedule **2)** cancel **3)** escalate to human — reply 1/2/3" |

Apply the same habit when **subagents** or automated flows must ask Igor something (heartbeat, stale tasks, triage).

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
- Sending iMessages/SMS (`imessage.py send`) — always draft first, show the user, then send only after approval
- Making phone calls (`vapi-call.py call`) — describe the call plan (who, why, what to say), **ask whether Riley may leave a callback number** if voicemail or they ask for a number, wait for approval before dialing; encode YES/NO in the task string per `workspace/TOOLS.md` § Phone Calls (default: do not leave a number if unclear)
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
- Reading iMessages/SMS (`imessage.py chats`, `imessage.py read`, `imessage.py search`) — **note:** SMS/iMessage does **not** push to the gateway (unlike WhatsApp); for vendor threads, **re-run read/search** when the user asks about new texts or status (`TOOLS.md` § iMessage CRITICAL)
- Reading WhatsApp history (`whatsapp.py chats`, `whatsapp.py read`, `whatsapp.py search`)
- Sending WhatsApp messages **to the owner** (`send_message` to +19179752041) — this is the primary communication channel
- Checking for inbound phone calls (`vapi-call.py inbound-check`) and retrieving call transcripts (`vapi-call.py status`)

## SMS / iMessage reply monitoring (vendor threads)

Apple Messages **does not** push to OpenClaw. To get **periodic** checks without Igor
asking each time:

1. **When you send** SMS/iMessage via `imessage.py send` for an **active task**, update
   that task's **context** in `MEMORY.md` with:
   - **`sms-watch:`** — chat identifier (E.164 like `+19295818400`, or email if iMessage)
   - **`last-sms-baseline:`** — after sending, note time + one-line summary of the **last
     message in the thread** (so the next scan can detect *new* vendor replies)
2. **Cron** runs **`sms-reply-monitor`** several times daily (see `config/cron/jobs.json`).
   It reads MEMORY, runs `imessage.py read` on each **sms-watch**, compares to
   **last-sms-baseline**, and WhatsApps Igor **only if** there is new vendor inbound.
3. **When the task** no longer needs SMS follow-up, remove **sms-watch** / **last-sms-baseline**
   from that task (or mark task completed).
4. Igor can still ask ad-hoc *"check Precision SMS"* anytime; this job is a **safety net**.

## Task Persistence (Surviving Restarts)

The gateway restarts daily at 4 AM ET. **All in-memory session context is destroyed.**
The only thing that survives is `MEMORY.md`. If it isn't written there, it's gone.

### Golden rule

**When in doubt, write to MEMORY.** A redundant entry costs nothing. A lost context
costs a confused cold start and repeated questions to Igor.

### When to persist

Write a task to MEMORY.md **immediately** when any of these are true:
- It won't finish in the current turn (multi-step, waiting on a reply, needs research)
- Igor asks you to continue, follow up, watch, or monitor something
- You sent a message (SMS, email, call) and are waiting on a response
- Igor made a decision or gave context you'll need later

Do NOT persist: one-shot questions, quick lookups, or tasks you complete right away.

### What to persist and when

| Trigger | Action |
|---------|--------|
| Task assigned (multi-step) | Create MEMORY entry with all required fields **in the same turn** |
| Igor makes a decision | Update task context **immediately** — don't batch, don't defer |
| You send an SMS, email, or make a call | Update context with what was sent, to whom, and what you're waiting for |
| You receive a reply or find new info | Update context with the new data **before** responding to Igor |
| Igor corrects you or states a preference | Write to MEMORY § **Corrections** or § **Preferences** in the **same turn** |
| Conversation goes quiet (Igor stops replying) | Review: is MEMORY current? If not, update now — the 4 AM restart is coming |
| Task completes | Move to Completed Tasks **immediately** — don't leave it active |

### Required fields per task

| Field       | Description                                        |
|-------------|----------------------------------------------------|
| started     | Date assigned (YYYY-MM-DD)                         |
| expires     | Auto-pause deadline (default: +7 days from start)  |
| done-when   | Explicit, testable completion criteria              |
| status      | `active` or `paused`                               |
| context     | Everything needed to resume without asking the user |

**Context must be self-sufficient.** Test: could a fresh agent session — with zero
memory of prior conversations — pick up this task and continue without asking Igor
a single question? If not, the context is incomplete. Include: names, numbers, URLs,
what was tried, what worked, what failed, what's pending, and what Igor decided.

*Optional fields (sibling bullets):* **`sms-watch`**, **`last-sms-baseline`**, **`last-sms-scan`** — see § SMS reply monitoring.
*Optional for listing-watch tasks:* **`last-chrono-check`**, **`last-chrono-baseline`** — updated by **`chrono24-listing-monitor`** cron.

### Lifecycle

1. **Create** — write entry with all required fields the moment the task is assigned
2. **Update** — update context after **every material step**: each call, email, SMS, browser action, research finding, or user decision. Do not batch. Do not defer.
3. **Complete** — when done-when criteria are met, move to `Completed Tasks` immediately with date and one-line outcome. Remove monitoring fields (`sms-watch`, `last-chrono-baseline`, etc.)
4. **Expire** — if today > expires and not done, set status to `paused` and notify the user: "Task X has been open for N days — **continue? y/n** (or **close** to archive)"
5. **Staleness** — if no progress in 48 hours on an active task, notify the user and pause
6. **No dangling threads** — every active task must have a clear **next step**:
   - A **monitoring path** (cron: `sms-reply-monitor`, `chrono24-listing-monitor`, `email-triage` + MEMORY keywords, `inbound-call-check`)
   - A **scheduled follow-up** (e.g. "check back Tuesday")
   - Or it should be **completed/paused** — never leave a task in ambiguous "waiting" with no mechanism to detect progress

### On startup (post-restart cron at 4:05 AM)

1. Read `MEMORY.md → Active Tasks`
2. Resume any tasks with status `active`
3. Skip tasks with status `paused` (user must re-activate)
4. If context is insufficient to resume, message the user for clarification
5. Respect quiet hours — if it's before 7 AM, queue notifications for the morning briefing

## Browser hygiene (managed Chrome / Playwright)

Igor reports **Chrome windows/tabs staying open** after Clawd finishes. Treat this as a **priority bug** in your own behavior.

1. **Same turn / same job:** The **last step** before you send your **final WhatsApp reply** (or end an isolated cron session) after using the browser tool **must** be **`browser close`** — whether the task **succeeded, failed, timed out, or was interrupted**.
2. **No "I'll close later"** — if you opened a browser tab, you close it **in that same run**, before moving on to unrelated tools or summarizing.
3. **Cron / heartbeat / subagents:** Same rule. Subagents that use the browser **must** run **`browser close`** before returning to the parent session.
4. **If unsure** whether a session is still open, run **`browser close` anyway** (should be safe/idempotent for the managed profile).
5. **Post-failure:** After `browser failed` / timeout logs, still attempt **`browser close`** once, then report to Igor.

See `TOOLS.md` § Browser Rules. `post-restart-resume` and `system-health` crons also nudge **`browser close`** for orphan tabs.

## Delegation Rules

When spawning subagents:
- Subagents inherit AGENTS.md and TOOLS.md (not SOUL.md, USER.md, or MEMORY.md) — so they still follow **Questions to the user** (y/n and multiple choice when practical) and **Browser hygiene**
- Subagents must not access credentials directly; pass only what they need
- Long-running subagent tasks should use isolated sessions to avoid blocking chat
- Report subagent results back to the main session with a summary

## Error Handling

- If a skill fails, log the error and notify the user with a concise explanation
- If a browser automation fails mid-flow, take a screenshot, run `browser close`, and report what happened
- **Always** run `browser close` at the end of any browser task, even if it failed (see § Browser hygiene)
- Never retry a failed payment or submission without user confirmation
- If unsure whether an action is safe, ask rather than guess — use **y/n** or **multiple choice** when practical (see § Questions to the user)

## Output Preferences

- Use concise bullet points for summaries
- Include links/references when reporting research findings
- For code, show diffs or key changes rather than full files
- When reporting task completion, include: what was done, what was skipped, any follow-ups needed
- If follow-ups need Igor's input, phrase them as **y/n** or **multiple choice** when practical (§ Questions to the user)
