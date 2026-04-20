# HEARTBEAT.md — Proactive Behavior

<!--
  Defines what the agent does proactively (without user prompting).
  Scheduled jobs are configured in config/cron/jobs.json — this file
  describes behavioral guidelines, not the canonical schedule.
-->

## On Every Heartbeat

1. Check `MEMORY.md → Active Tasks` — resume any with status `active`
2. Process any queued user messages (WhatsApp, etc.)
3. If this session used the managed browser, end the turn with `browser close` (see `AGENTS.md` § Browser hygiene)

## Scheduled Jobs (canonical source: config/cron/jobs.json)

| Job                      | ET Schedule                    | Purpose                                               |
|--------------------------|--------------------------------|-------------------------------------------------------|
| post-restart-resume      | 4:05 AM daily                  | Resume active tasks after restart; warm browser       |
| api-spend-check          | 5:00 AM daily                  | Yesterday's OpenAI + Vapi $ + Cursor plan → WhatsApp  |
| morning-briefing         | 7:30 AM daily                  | Emails + calendar + overnight calls + active tasks    |
| email-triage             | 8, 11, 14, 17, 20 (5×/day)     | Flag urgent emails + MEMORY-task senders              |
| chrono24-listing-monitor | 8, 11, 14, 17, 20 (5×/day)     | Listing vs `last-chrono-baseline`; `browser close`    |
| sms-reply-monitor        | 8:30, 11:30, 14:30, 17:30, 20:30 | Poll MEMORY `sms-watch` threads via `imessage.py`     |
| system-health            | 4, 8, 12, 16, 20 (5×/day)      | Gateway, disk, error log                              |
| inbound-call-check       | Every 30 min                   | Poll Vapi for new inbound calls                       |

## Behavioral Rules

- **Quiet hours (11 PM – 7 AM ET):** suppress non-critical notifications. Cron jobs still run; findings defer to morning briefing.
- **Critical** = security alerts, service outages, messages marked urgent. Send immediately even in quiet hours.
- **Email triage:** draft replies but never send without user approval.
- **System health:** only notify if something is wrong.
- **Inbound calls during quiet hours:** do NOT alert immediately. Track seen calls; surface in morning briefing. Exception: if the caller's number matches an active MEMORY task, treat as critical.
- **Morning briefing:** deliver via WhatsApp; include active tasks from MEMORY.md + overnight calls.
- **SMS reply monitor:** uses `sms-watch` / `last-sms-baseline` per task; don't spam WhatsApp when there's nothing new.
- **Chrono24 monitor:** only does real work if MEMORY has an active Chrono24 task; updates `last-chrono-baseline`; must `browser close` after any readable check.
- **Browser:** managed Chrome must not be left open after Clawd's turn (see `AGENTS.md` § Browser hygiene).
