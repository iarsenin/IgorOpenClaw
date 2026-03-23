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
- **context:** Resume existing Chrono24 private-sale workflow for watchId 45455036. Listing edit link: https://www.chrono24.com/user/modify-offer.htm?watchId=45455036. Watch: Montblanc TimeWalker TwinFly Chronograph Automatic, ref 109134, 2017, 43mm steel, silver dial, brown leather strap, MB 25.07, sapphire, 100m, box/manual/quality certificate, New York NY, US shipping only. Mechanical disclosure must clearly state watch runs but may stop overnight if not worn; watchmaker said otherwise good and likely needs mainspring replacement. Decision floor is $1900 net; do not accept/counter/commit without Igor approval. Live status checked 2026-03-22: listings page shows Inactive + 'We are setting up your private seller account.' No Chrono24 messages yet. No requests/sales yet. Current ask shown: $2,590. Draft notes already include the power-reserve disclosure and US-only shipping. Potential data-quality issues on edit form: condition appears as Mint though target phrasing is 'very good'; seller-name field may show 'null null' in the form, but the 'I do not want my name displayed in the listing' option is checked; latest manual re-check on 2026-03-22 showed sellerName reverted/displayed again as 'null null' in the form, so prior attempted edit did not persist. Location accuracy should be re-verified on the next edit session before submitting further changes.
- **last-chrono-check:** 2026-03-22 7:35 PM ET — manual restart check on manage-listing page
- **last-chrono-baseline:** 2026-03-22 7:39 PM ET — manage-listing page loads; hideSellerData checkbox is checked ('I do not want my name displayed in the listing'); sellerName field still shows 'null null' in the form; price still $2,590 USD; no buyer activity surfaced on this check
- **Monitoring:** Repo cron job **`chrono24-listing-monitor`** (`config/cron/jobs.json`) — 5× daily; WhatsApp only on activation, buyer activity, action-required items, or material status change; **must `browser close`** after any browser use.

### Sub-Zero 700TC ice maker service - NYC
- **started:** 2026-03-22
- **expires:** 2026-03-29
- **done-when:** Igor approves a provider + next step (e.g. visit) or explicitly pauses/closes the search; quotes/options surfaced for any vendor reply; no open questions on **sms-watch** threads without a **last-sms-baseline** update or WhatsApp ping; repair **authorized** only after Igor approval
- **status:** active
- **context:** New task: Sub-Zero 700TC refrigerator from circa 2002, ice maker stopped working, needs servicing. Address/service area: 154 W 18 St Apt 7D, New York, NY 10011. Contact email: arsenin@yahoo.com. User wants reputable provider, avoid gouging, wants web investigation of reasonable price in NYC to use as guide, and wants negotiation for free estimate. Best visit days are Tuesdays and Fridays. Do not commit to final quote. Research completed 2026-03-22: current preferred candidate is Certified Refrigeration LLC (independent specialist, 1-800-200-2306). L&J Appliance Service removed from shortlist per Igor after stale-website concern and multiple bounced email addresses. Replacement backup candidate: Precision Appliance Services Inc (serves Manhattan/Chelsea, Sub-Zero specialist, phones 718-266-2545 / 929-271-4964). Price benchmark to use in negotiation: diagnostic/service call roughly $90-$150, ideally credited or free; likely repair total roughly $300-$600 for simpler icemaker issues, $600-$1000+ for icemaker assembly/control board level work. Approved outreach sent 2026-03-22: Certified Refrigeration website form submitted successfully with Igor contact details and request for free/credited estimate, written quote before work, and Tuesday/Friday availability. L&J initial email to service@landjappliance.co bounced; fallback emails to Eddie@LandJappliance.com and Mike@LandJappliance.com also bounced with 550 5.1.1 no such user, so L&J is no longer an active option. Need to monitor replies and present quotes/options to Igor before any appointment or repair authorization. Igor approved replacement backup outreach to Precision Appliance Services on 2026-03-22. Agent attempt via Workiz inquiry form failed with 'Captcha validation failed Please try again.' Igor then submitted the Precision inquiry manually. Precision replied by SMS on 2026-03-22 from +1 929-581-8400: they service Tuesdays and Thursdays only; service/diagnostic charge is $225 + tax, credited toward repair; written estimate requires Igor approval before repair; next offered slot is Tuesday 8-11 AM; they say average all-in repair for a Sub-Zero no-ice complaint is $600-$800 from a reputable local NYC service company. On 2026-03-22, with Igor's approval, sent SMS asking whether there is a cash discount and asking them to confirm the $225 + tax service charge is fully credited toward repair. On 2026-03-22, with Igor's approval, accepted Precision's Tuesday 8-11 AM service-call window by SMS and asked them to send confirmation details by text, while stating no repair work should be done without Igor's approval after diagnosis. If Certified Refrigeration or any other vendor replies after this, decline politely and simply state that service has already been arranged elsewhere; do not reveal additional details. Need to monitor for Precision confirmation and present any appointment details/options to Igor before any repair authorization.
- **sms-watch:** `+19295818400` (Precision Appliance — awaiting service-call confirmation text)
- **last-sms-baseline:** 2026-03-22 6:44 PM ET — latest thread message is our outbound acceptance/confirmation request for Tuesday 8-11 AM service window; no newer inbound seen on restart check
- **last-sms-scan:** 2026-03-22 7:34 PM ET — manual restart check; no newer inbound detected

### Shelly / Affordable Dermatology appointment
- **started:** 2026-03-22
- **expires:** 2026-03-29
- **done-when:** a Tuesday 5:30 PM dermatology appointment within about the next month is booked or clearly unavailable, and Igor has the outcome plus any follow-up details
- **status:** active
- **context:** User asked Clawd to contact Shelly at Affordable Dermatology and book a 45-minute appointment. Contact lookup in Contacts found likely historical card under Shane / Electrolysis with numbers +1 917-600-0960 and (212) 633-1503; user instructed to use Shane number but call her Shelly. Outbound Vapi call to +1 917-600-0960 reached Shelly/voicemail-like flow; caller said to leave name and number or text this number and she would call right back. Agent could not complete booking on call. With Igor approval, sent follow-up text to +1 917-600-0960 requesting a 45-minute Tuesday 5:30 PM appointment, any Tuesday within the next month, and asking her to text back with an available date or call Igor. Need to monitor for reply and present any proposed slot/status to Igor before confirming anything else.
- **sms-watch:** `+19176000960` (Shelly / Shane contact — awaiting reply to appointment text)
- **last-sms-baseline:** 2026-03-22 4:08 PM ET — latest thread message is our outbound text requesting a Tuesday 5:30 PM appointment; no reply seen on restart check

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
