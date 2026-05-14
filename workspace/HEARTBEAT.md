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

Only 3 jobs are currently **enabled**. The rest remain defined for fast re-enable.

| Job                      | ET Schedule         | Enabled | Purpose                                               |
|--------------------------|---------------------|---------|-------------------------------------------------------|
| post-restart-resume      | 4:05 AM daily       | yes     | Resume active tasks after restart; warm browser       |
| api-spend-check          | 5:00 AM daily       | yes     | Yesterday's OpenAI + Vapi $ + Cursor plan → WhatsApp  |
| morning-briefing         | 7:30 AM daily       | yes     | Calendar + active tasks from MEMORY → WhatsApp        |
| email-triage             | 8, 11, 14, 17, 20   | no      | (disabled — flagged urgent emails / MEMORY-task senders) |
| chrono24-listing-monitor | 8, 11, 14, 17, 20   | no      | (disabled — listing vs `last-chrono-baseline`)         |
| sms-reply-monitor        | 8:30, 11:30, …      | no      | (disabled — poll MEMORY `sms-watch` threads)           |
| system-health            | 4, 8, 12, 16, 20    | no      | (disabled — gateway/disk/error log)                    |
| inbound-call-check       | every 30 min        | no      | (disabled — poll Vapi for new inbound calls)           |

## Behavioral Rules

- **Quiet hours (11 PM – 7 AM ET):** suppress non-critical notifications. Findings from enabled jobs defer to morning briefing.
- **Critical** = security alerts, service outages, messages marked urgent. Send immediately even in quiet hours.
- **Morning briefing:** deliver via WhatsApp; include calendar + active tasks from MEMORY.md.
- **Inbound calls:** while `inbound-call-check` cron is disabled, Igor must explicitly ask (`vapi-call.py inbound-check`) to surface new calls. The outbound `call` watcher still delivers proactive summaries.
- **Disabled jobs:** behavior described above for `email-triage`, `chrono24-listing-monitor`, `sms-reply-monitor`, `system-health` only activates if Igor re-enables them in `config/cron/jobs.json`.
- **Browser:** managed Chrome must not be left open after Clawd's turn (see `AGENTS.md` § Browser hygiene).
