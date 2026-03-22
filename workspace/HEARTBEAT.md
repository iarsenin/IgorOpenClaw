# HEARTBEAT.md — Proactive Behavior

<!--
  Defines what the agent does proactively (without user prompting).
  Scheduled jobs are configured in config/cron/jobs.json — this file
  describes behavioral guidelines, not schedules.
-->

## On Every Heartbeat (~30 min cycle)

1. Check `MEMORY.md → Active Tasks` — resume any with status `active`
2. Process any queued user messages (WhatsApp, etc.)

## Scheduled Jobs (see config/cron/jobs.json)

| Job                | Schedule              | Purpose                              |
|--------------------|-----------------------|--------------------------------------|
| post-restart-resume| 4:05 AM daily         | Resume active tasks after restart    |
| morning-briefing   | 7:30 AM daily         | Emails, calendar, overnight errors   |
| email-triage       | Every 2h, 8 AM–10 PM | Flag urgent, draft routine replies   |
| inbound-call-check | Every 30 min          | Poll Vapi for new inbound calls      |
| system-health      | Every 6h              | Gateway, disk, error log check       |

## Behavioral Rules

- **Quiet hours (11 PM – 7 AM ET):** suppress non-critical notifications
- **Critical** = security alerts, service outages, messages marked urgent
- **Email triage:** draft replies but never send without user approval
- **System health:** only notify user if something is wrong
- **Morning briefing:** deliver via WhatsApp; include active tasks from MEMORY.md
