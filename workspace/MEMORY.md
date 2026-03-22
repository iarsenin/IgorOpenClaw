# MEMORY.md — Agent Persistent State

<!--
  Maintained by the agent. NEVER share with subagents or in group chats.
  Max recommended size: 10,000 characters. Prune oldest completed tasks
  and outdated entries when approaching the limit.
-->

## Active Tasks

<!--
  One entry per task. Required fields per entry:

  ### <short-title>
  - **started:** YYYY-MM-DD
  - **expires:** YYYY-MM-DD (default: 7 days from start)
  - **done-when:** explicit completion criteria
  - **status:** active | paused
  - **context:** everything needed to resume (numbers, URLs, history, etc.)

  Rules (see AGENTS.md § Task Persistence for full details):
  - Write new tasks here IMMEDIATELY when assigned
  - Move to Completed Tasks when done-when is met
  - If expired and not done, set status to paused and notify user
-->

### Chrono24 private sale - Montblanc TimeWalker TwinFly
- **started:** 2026-03-22
- **expires:** 2026-03-29
- **done-when:** listing is live or otherwise resolved, buyer messages/offers are monitored on request, and any material listing changes or deal terms are approved by Igor before action
- **status:** active
- **context:** Resume existing Chrono24 private-sale workflow for watchId 45455036. Listing edit link: https://www.chrono24.com/user/modify-offer.htm?watchId=45455036. Watch: Montblanc TimeWalker TwinFly Chronograph Automatic, ref 109134, 2017, 43mm steel, silver dial, brown leather strap, MB 25.07, sapphire, 100m, box/manual/quality certificate, New York NY, US shipping only. Mechanical disclosure must clearly state watch runs but may stop overnight if not worn; watchmaker said otherwise good and likely needs mainspring replacement. Decision floor is $1900 net; do not accept/counter/commit without Igor approval. Live status checked 2026-03-22: listings page shows Inactive + 'We are setting up your private seller account.' No Chrono24 messages yet. No requests/sales yet. Current ask shown: $2,590. Draft notes already include the power-reserve disclosure and US-only shipping. Potential data-quality issues on edit form: condition appears as Mint though target phrasing is 'very good'; location state is set to Alabama while desired location is New York, NY; seller name field rendered as 'null null'. Recurring monitor cron created 2026-03-22: job id e66c4887-635e-4fd6-a1cd-4244cf66b493, every 3 hours, announce only on activation, buyer activity, action-required items, or material status changes.

## Completed Tasks

<!--
  Archive of finished tasks. Keep the last 20 entries.
  Format: date completed | title | outcome (1 line)
-->

(No completed tasks yet.)

## Preferences

(No entries yet — the agent will populate this as it learns.)

## Patterns

(No entries yet.)

## Corrections

(Record times Igor corrected the agent, and what the right answer was.)
