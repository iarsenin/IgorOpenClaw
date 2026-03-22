# HEARTBEAT.md — Proactive Behavior

<!--
  Defines what the agent does proactively (without user prompting).
  Scheduled jobs are configured in config/cron/jobs.json — this file
  describes behavioral guidelines, not schedules.
-->

## On Every Heartbeat (~30 min cycle)

1. Check `MEMORY.md → Active Tasks` — resume any with status `active`
2. Process any queued user messages (WhatsApp, etc.)
3. If this session **used the managed browser**, end the turn with **`browser close`** before replying (see `AGENTS.md` § Browser hygiene) — do not leave Chrome open for Igor

## Scheduled Jobs (see config/cron/jobs.json)

| Job                | Schedule              | Purpose                              |
|--------------------|-----------------------|--------------------------------------|
| post-restart-resume| 4:05 AM daily         | Resume active tasks after restart    |
| morning-briefing   | 7:30 AM daily         | Emails, calendar, overnight errors   |
| email-triage       | Every 2h, 8 AM–10 PM | Flag urgent, draft routine replies + MEMORY-related senders |
| chrono24-listing-monitor | 8 AM, 11 AM, 2 PM, 5 PM, 8 PM ET (5×) | Chrono24 listing vs **last-chrono-baseline** |
| sms-reply-monitor  | ~2h, 8:30 AM–8:30 PM ET | Poll `MEMORY` **sms-watch** threads via `imessage.py`; on read errors, note MEMORY only (no WhatsApp spam unless urgent) |
| inbound-call-check | Every 30 min          | Poll Vapi for new inbound calls      |
| api-spend-check    | 5:00 AM ET daily      | OpenAI + Vapi last-24h $ + Cursor plan status → WhatsApp |
| system-health      | Every 6h              | Gateway, disk, error log check       |

## Behavioral Rules

- **Questions to Igor:** When a heartbeat, cron job, or proactive check needs a decision or missing detail, use **y/n** or **multiple choice** when practical — see `AGENTS.md` § Questions to the user (don’t force the format when it doesn’t fit).
- **Quiet hours (11 PM – 7 AM ET):** suppress non-critical notifications
- **Critical** = security alerts, service outages, messages marked urgent
- **Email triage:** draft replies but never send without user approval
- **System health:** only notify user if something is wrong
- **Inbound calls during quiet hours:** do NOT send an immediate WhatsApp alert.
  The inbound-check cron still runs and tracks seen calls, but the alert is deferred
  to the morning briefing at 7:30 AM. Exception: if the caller's number matches a
  contact from an active task in MEMORY.md, treat it as critical and notify immediately.
- **Morning briefing:** deliver via WhatsApp; include active tasks from MEMORY.md
  and any overnight inbound phone calls
- **SMS reply monitor:** uses **`sms-watch`** / **`last-sms-baseline`** in task context (`AGENTS.md`);
  do not spam WhatsApp when there is nothing new
- **Chrono24 monitor:** only runs meaningful work if MEMORY has an active Chrono24 task; updates **last-chrono-baseline**; must **`browser close`** after any browser use
- **Browser:** managed Chrome must not be left open after Clawd’s turn — `AGENTS.md` § Browser hygiene
