# HEARTBEAT.md — Proactive Scheduled Tasks

<!--
  These tasks run on the agent's heartbeat cycle (default: every 30 minutes).
  Each task should be lightweight and non-destructive.
  Heavier tasks should be scheduled via cron with isolated sessions.
-->

## On Every Heartbeat

1. **Check for pending user messages** — process any queued WhatsApp messages
2. **Review cron job queue** — execute any due scheduled tasks

## Morning Briefing (daily, ~7:30 AM ET)

- Summarize overnight emails (unread count, any flagged urgent)
- List today's scheduled tasks and reminders
- Report any errors or failed jobs from overnight
- Deliver via WhatsApp

## Email Triage (every 2 hours, 8 AM–10 PM ET)

- Scan inbox for new messages
- Flag urgent emails (from known important contacts)
- Draft replies for routine messages (present for review, don't send)
- Archive obvious spam/newsletters if user has approved auto-archive rules

## System Health (every 6 hours)

- Check gateway status (`openclaw gateway status`)
- Verify disk space is adequate
- Report any skill errors from logs
- Only notify user if something is wrong

## Quiet Hours

- **11 PM – 7 AM ET**: suppress all non-critical notifications
- Critical = security alerts, service outages, or messages explicitly marked urgent
