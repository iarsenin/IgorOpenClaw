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
- **context:** Resume existing Chrono24 private-sale workflow for watchId 45455036. Listing edit link: https://www.chrono24.com/user/modify-offer.htm?watchId=45455036. Public listing URL: https://www.chrono24.com/montblanc/timewalker-twinfly-chronograph--id45455036.htm. Watch: Montblanc TimeWalker TwinFly Chronograph Automatic, ref 109134, 2017, 43mm steel, silver dial, brown leather strap, MB 25.07, sapphire, 100m, box/manual/quality certificate, New York NY, US shipping only. Mechanical disclosure must clearly state watch runs but may stop overnight if not worn; watchmaker said otherwise good and likely needs mainspring replacement. Decision floor is $1900 net; do not accept/counter/commit without Igor approval. Live status checked 2026-03-22: listings page shows Inactive + 'We are setting up your private seller account.' No Chrono24 messages yet. No requests/sales yet. Current ask shown: $2,390. Draft notes already include the power-reserve disclosure and US-only shipping. Potential data-quality issues on edit form: condition appears as Mint though target phrasing is 'very good'; seller-name field may show 'null null' in the form, but the 'I do not want my name displayed in the listing' option is checked; latest manual re-check on 2026-03-22 showed sellerName reverted/displayed again as 'null null' in the form, so prior attempted edit did not persist. Location accuracy should be re-verified on the next edit session before submitting further changes. On 2026-03-23 11:00 AM ET cron check, the listing became live/public. Public page shows price $2,590 negotiable, condition Used (Very good), box/papers included, the power-reserve disclosure is present, and no Chrono24 messages or private-seller requests are present. Notable issue on the public listing: location is displayed as United States of America, Alabama, which does not match the intended New York, NY location and should be reviewed on the next edit pass. On 2026-03-24, per user request, contacted Chrono24 support via their web form (Order ID 2177231) to inquire why the ad may not be fully active or visible and to request it be approved. Later on 2026-03-24, a Chrono24 email reported: “Your listing is now online!” The listing is live and accessible, and escrow service is activated. On 2026-03-26, Igor instructed Clawd to lower the listing price from $2,590 to $2,390; the edit was submitted on the manage-listing page and Chrono24 confirmed: "Your changes were saved."
- **last-chrono-check:** 2026-03-27 5:00 PM ET — checked public listing page via browser; listing still shows live at $2,390 with Buy / Suggest a price / Contact seller visible and no buyer activity visible on the public page
- **last-chrono-baseline:** 2026-03-27 5:00 PM ET — listing remains Active/live at $2,390; public page shows Used (Very good), original box/papers included, Availability 'Item is in stock,' Buy / Suggest a price / Contact seller actions visible, no buyer activity visible on the public page; public location still displays United States of America, Alabama
- **Monitoring:** Repo cron job **`chrono24-listing-monitor`** (`config/cron/jobs.json`) — 5× daily; WhatsApp only on activation, buyer activity, action-required items, or material status change; **must `browser close`** after any browser use.

### Shelly / Affordable Dermatology appointment
- **started:** 2026-03-22
- **expires:** 2026-03-29
- **done-when:** a Tuesday 5:30 PM dermatology appointment within about the next month is booked or clearly unavailable, and Igor has the outcome plus any follow-up details
- **status:** active
- **context:** User asked Clawd to contact Shelly at Affordable Dermatology and book a 45-minute appointment. Contact lookup in Contacts found likely historical card under Shane / Electrolysis with numbers +1 917-600-0960 and (212) 633-1503; user instructed to use Shane number but call her Shelly. Outbound Vapi call to +1 917-600-0960 reached Shelly/voicemail-like flow; caller said to leave name and number or text this number and she would call right back. Agent could not complete booking on call. With Igor approval, sent follow-up text to +1 917-600-0960 requesting a 45-minute Tuesday 5:30 PM appointment, any Tuesday within the next month, and asking her to text back with an available date or call Igor. On 2026-03-23, Igor instructed Clawd to call Shelly back and explicitly authorized voicemail callback disclosure. New outbound Vapi callback initiated to +1 917-600-0960 (call id 019d1ac3-67ed-744c-bbd5-dc0c41580eed) with instructions to ask for a 45-minute dermatology appointment for Igor, prefer Tuesday 5:30 PM, accept other Tuesday late-afternoon/early-evening options within about the next month, mention prior follow-up text, and if no answer leave a short voicemail asking Shelly to text or call back. Callback authorization for this call: YES, provide +1 917-975-2041. On 2026-03-23 in the evening, Igor approved another follow-up call and voicemail callback disclosure. Outbound Vapi call placed to +1 917-600-0960 (call id 019d1d0e-e853-7000-86dd-ea2c142db440). Outcome: answering machine prompt invited a voicemail or text reply; Riley left a voicemail referencing the prior text and requesting a callback, with Igor's callback number authorized as +1 917-975-2041. Call ended without live contact (endedReason: silence-timed-out). Need to monitor for reply and present any proposed slot/status to Igor before confirming anything else.
- **sms-watch:** `+19176000960` (Shelly / Shane contact — awaiting reply to appointment text)
- **last-sms-baseline:** 2026-03-22 4:08 PM ET — latest thread message is our outbound text requesting a Tuesday 5:30 PM appointment; no reply seen on restart check
- **last-sms-scan:** 2026-03-27 4:30 PM ET — sms-reply-monitor checked Shelly/Shane thread; still no reply after our 2026-03-22 4:08 PM ET outbound appointment text


### Window cleaners - schedule when heat is off
- **started:** 2026-03-23
- **expires:** 2026-03-30
- **done-when:** window-cleaning contact path is preserved and Igor can easily trigger scheduling in a couple of weeks
- **status:** active
- **context:** Igor asked Clawd to find the window cleaners he uses every year from regular Messages and keep the info available for scheduling in a couple of weeks, after the heat is off and the windows are ready. Search of Messages did not find a direct cleaner phone number, but it did find the coordination thread at +1 646-279-3971. Relevant messages: on 2024-08-16 this contact texted, 'Hey. I also scheduled windows cleaning next Friday at 9am. Same guys. I’m not sure how much it is. I will leave 140 in cash on the kitchen table. Could you pay them from that?' On 2024-08-23 the same contact texted, 'Hey. A reminder that windows cleaners are coming at 9.' This suggests +1 646-279-3971 is the person who arranges the recurring window cleaners rather than the cleaner directly. On 2026-03-27, Igor clarified that the earlier outreach should have gone to the window cleaners rather than the prior coordinator/super. Contacts search found a contact named 'Window' with number +1 917-373-5697. Igor approved sending: 'Hi, I’d like to schedule window cleaning for 5 windows at 154 W 18 St, Apt 7D. Super Jesus will let you in. Could you let me know your availability and the quote?' Clawd attempted to send that message via `imessage.py`, but Messages.app returned an AppleScript error (`Can’t get chat id "SMS;-;+19173735697"`), so the message was NOT sent. imessage.py send now fixed to handle new threads via buddy-of-service fallback; Clawd should retry the send.
- **sms-watch:** `+16462793971` (prior coordinator for recurring window cleaners)
- **last-sms-baseline:** 2026-03-27 7:28 AM ET — new inbound from prior coordinator after misdirected outbound: "Hi Igor  , ok"
- **last-sms-scan:** 2026-03-27 4:30 PM ET — sms-reply-monitor checked prior coordinator thread; no newer inbound after the 2026-03-27 7:28 AM ET reply: "Hi Igor  , ok"


## Completed Tasks

<!--
  Archive of finished tasks. Keep the last 20 entries.
  Format: date completed | title | outcome (1 line)
-->

2026-03-27 | Neil Tancre birthday WhatsApp | Expired; WhatsApp send to third-party contacts not supported by OpenClaw platform.
2026-03-26 | Gringer matching Miele washer quote | Closed at Igor’s request; no further follow-up needed.
2026-03-26 | Nationwide Medical CPAP supplies issue | Closed at Igor’s request; no further follow-up needed.
2026-03-26 | Precision Appliance / Sub-Zero estimate follow-up | Closed at Igor’s request; ignore the new estimate email and do not reopen.
2026-03-24 | Sub-Zero 700TC ice maker service - NYC | Closed at Igor’s request; no further follow-up needed on Precision Appliance.
2026-03-23 | Juha book check-in call | Closed at Igor’s request; no further follow-up needed.
2026-03-23 | Jack Moody permission + desk call | Closed at Igor’s request; no further follow-up needed.

## Preferences

- 2026-03-25 | Do not report routine checks when there is nothing to report — only notify on material changes, errors, or items requiring user action.

(Agent will populate this section further as it learns.)

## Patterns

(No entries yet.)

## Corrections

- 2026-03-23 | "finish X interaction" means close/archive the task, NOT execute the next step. Clawd sent an iMessage to Jack Moody without approval after Igor said "finish Jack Moody interaction." Correct action: mark task completed in MEMORY.md. See AGENTS.md § Ambiguous task-lifecycle phrases.
- 2026-03-23 | whatsapp.py only reads bridge messages (Igor ↔ Clawd). It cannot see Igor's WhatsApp chats with other people or look up contacts. Use gog contacts, email search, or imessage.py search instead. See TOOLS.md § WhatsApp CRITICAL LIMITATION.
- 2026-03-24 | **DO NOT call `himalaya` directly for email search.** Use `python3 "$OPENCLAW_REPO/scripts/email-search.py"` wrapper instead. It has standard `--from`, `--subject`, `--after`, `--folder`, `--account` flags and searches BOTH gmail+yahoo by default. See TOOLS.md § Email Access.
- 2026-03-24 | **Always use `$OPENCLAW_REPO` for script paths.** This env var is pre-set in the daemon. Never hard-code or re-define the repo path. Example: `python3 "$OPENCLAW_REPO/scripts/vapi-call.py" call ...`
- 2026-03-26 | **Cron sessions: SILENT by default.** Do NOT send "no new calls", "all clear", "nothing to report", "no action", or any absence-of-activity message. If a script produced no output, STOP — send nothing. See AGENTS.md § Cron job behavior.
- 2026-03-27 | **Keep confirmations minimal.** When Igor asks to do something (calendar, SMS, call), confirm with a short y/n — state what you’ll do in one line, then **y/n**. Do not offer options, alternative durations, or multiple-choice unless Igor asked for them.
- 2026-03-26 | **Self-echo: `(self)` messages are your own echo.** Never reply to them, never re-send content from them. After sending ONE WhatsApp in a cron session, STOP. See AGENTS.md § Self-echo rule.
