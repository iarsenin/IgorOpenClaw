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
- **context:** Resume existing Chrono24 private-sale workflow for watchId 45455036. Listing edit link: https://www.chrono24.com/user/modify-offer.htm?watchId=45455036. Public listing URL: https://www.chrono24.com/montblanc/timewalker-twinfly-chronograph--id45455036.htm. Watch: Montblanc TimeWalker TwinFly Chronograph Automatic, ref 109134, 2017, 43mm steel, silver dial, brown leather strap, MB 25.07, sapphire, 100m, box/manual/quality certificate, New York NY, US shipping only. Mechanical disclosure must clearly state watch runs but may stop overnight if not worn; watchmaker said otherwise good and likely needs mainspring replacement. Decision floor is $1900 net; do not accept/counter/commit without Igor approval. Live status checked 2026-03-22: listings page shows Inactive + 'We are setting up your private seller account.' No Chrono24 messages yet. No requests/sales yet. Current ask shown: $2,590. Draft notes already include the power-reserve disclosure and US-only shipping. Potential data-quality issues on edit form: condition appears as Mint though target phrasing is 'very good'; seller-name field may show 'null null' in the form, but the 'I do not want my name displayed in the listing' option is checked; latest manual re-check on 2026-03-22 showed sellerName reverted/displayed again as 'null null' in the form, so prior attempted edit did not persist. Location accuracy should be re-verified on the next edit session before submitting further changes. On 2026-03-23 11:00 AM ET cron check, the listing became live/public. Public page shows price $2,590 negotiable, condition Used (Very good), box/papers included, the power-reserve disclosure is present, and no Chrono24 messages or private-seller requests are present. Notable issue on the public listing: location is displayed as United States of America, Alabama, which does not match the intended New York, NY location and should be reviewed on the next edit pass.
- **last-chrono-check:** 2026-03-23 8:01 PM ET — cron re-check on the public listing URL via browser; listing still loads publicly/live with no visible public-page changes from the prior baseline
- **last-chrono-baseline:** 2026-03-23 8:01 PM ET — listing remains Active/live publicly at $2,590; public page still shows condition Used (Very good), original box/papers, disclosure present, and location unexpectedly displayed as Alabama; no new buyer action visible from the public page
- **Monitoring:** Repo cron job **`chrono24-listing-monitor`** (`config/cron/jobs.json`) — 5× daily; WhatsApp only on activation, buyer activity, action-required items, or material status change; **must `browser close`** after any browser use.

### Sub-Zero 700TC ice maker service - NYC
- **started:** 2026-03-22
- **expires:** 2026-03-29
- **done-when:** Igor approves a provider + next step (e.g. visit) or explicitly pauses/closes the search; quotes/options surfaced for any vendor reply; no open questions on **sms-watch** threads without a **last-sms-baseline** update or WhatsApp ping; repair **authorized** only after Igor approval
- **status:** active
- **context:** New task: Sub-Zero 700TC refrigerator from circa 2002, ice maker stopped working, needs servicing. Address/service area: 154 W 18 St Apt 7D, New York, NY 10011. Contact email: arsenin@yahoo.com. User wants reputable provider, avoid gouging, wants web investigation of reasonable price in NYC to use as guide, and wants negotiation for free estimate. Best visit days are Tuesdays and Fridays. Do not commit to final quote. Research completed 2026-03-22: current preferred candidate is Certified Refrigeration LLC (independent specialist, 1-800-200-2306). L&J Appliance Service removed from shortlist per Igor after stale-website concern and multiple bounced email addresses. Replacement backup candidate: Precision Appliance Services Inc (serves Manhattan/Chelsea, Sub-Zero specialist, phones 718-266-2545 / 929-271-4964). Price benchmark to use in negotiation: diagnostic/service call roughly $90-$150, ideally credited or free; likely repair total roughly $300-$600 for simpler icemaker issues, $600-$1000+ for icemaker assembly/control board level work. Approved outreach sent 2026-03-22: Certified Refrigeration website form submitted successfully with Igor contact details and request for free/credited estimate, written quote before work, and Tuesday/Friday availability. L&J initial email to service@landjappliance.co bounced; fallback emails to Eddie@LandJappliance.com and Mike@LandJappliance.com also bounced with 550 5.1.1 no such user, so L&J is no longer an active option. Need to monitor replies and present quotes/options to Igor before any appointment or repair authorization. Igor approved replacement backup outreach to Precision Appliance Services on 2026-03-22. Agent attempt via Workiz inquiry form failed with 'Captcha validation failed Please try again.' Igor then submitted the Precision inquiry manually. Precision replied by SMS on 2026-03-22 from +1 929-581-8400: they service Tuesdays and Thursdays only; service/diagnostic charge is $225 + tax, credited toward repair; written estimate requires Igor approval before repair; next offered slot is Tuesday 8-11 AM; they say average all-in repair for a Sub-Zero no-ice complaint is $600-$800 from a reputable local NYC service company. On 2026-03-22, with Igor's approval, sent SMS asking whether there is a cash discount and asking them to confirm the $225 + tax service charge is fully credited toward repair. On 2026-03-22, with Igor's approval, accepted Precision's Tuesday 8-11 AM service-call window by SMS and asked them to send confirmation details by text, while stating no repair work should be done without Igor's approval after diagnosis. On 2026-03-23, Igor reported that Precision called him directly and confirmed the appointment. Appointment is now confirmed by phone; continue monitoring for any follow-up text/call details, reminders, reschedules, or estimate/repair updates. If Certified Refrigeration or any other vendor replies after this, decline politely and simply state that service has already been arranged elsewhere; do not reveal additional details. Present any diagnosis, quote, or repair recommendation to Igor before any authorization.
- **sms-watch:** `+19295818400` (Precision Appliance — awaiting service-call confirmation text)
- **last-sms-baseline:** 2026-03-23 9:07 AM ET — Precision sent a reminder text for Tue Mar 24 service at 154 W 18 St Apt 7D with tech John Telepan, plus a 24-hour cancellation / 50% non-refundable service-charge warning; we replied "Thanks."
- **last-sms-scan:** 2026-03-23 8:30 PM ET — sms-reply-monitor checked Precision thread; no new inbound since the 2026-03-23 9:06 AM ET reminder/confirmation text and our 9:07 AM ET acknowledgment

### Shelly / Affordable Dermatology appointment
- **started:** 2026-03-22
- **expires:** 2026-03-29
- **done-when:** a Tuesday 5:30 PM dermatology appointment within about the next month is booked or clearly unavailable, and Igor has the outcome plus any follow-up details
- **status:** active
- **context:** User asked Clawd to contact Shelly at Affordable Dermatology and book a 45-minute appointment. Contact lookup in Contacts found likely historical card under Shane / Electrolysis with numbers +1 917-600-0960 and (212) 633-1503; user instructed to use Shane number but call her Shelly. Outbound Vapi call to +1 917-600-0960 reached Shelly/voicemail-like flow; caller said to leave name and number or text this number and she would call right back. Agent could not complete booking on call. With Igor approval, sent follow-up text to +1 917-600-0960 requesting a 45-minute Tuesday 5:30 PM appointment, any Tuesday within the next month, and asking her to text back with an available date or call Igor. On 2026-03-23, Igor instructed Clawd to call Shelly back and explicitly authorized voicemail callback disclosure. New outbound Vapi callback initiated to +1 917-600-0960 (call id 019d1ac3-67ed-744c-bbd5-dc0c41580eed) with instructions to ask for a 45-minute dermatology appointment for Igor, prefer Tuesday 5:30 PM, accept other Tuesday late-afternoon/early-evening options within about the next month, mention prior follow-up text, and if no answer leave a short voicemail asking Shelly to text or call back. Callback authorization for this call: YES, provide +1 917-975-2041. On 2026-03-23 in the evening, Igor approved another follow-up call and voicemail callback disclosure. Outbound Vapi call placed to +1 917-600-0960 (call id 019d1d0e-e853-7000-86dd-ea2c142db440). Outcome: answering machine prompt invited a voicemail or text reply; Riley left a voicemail referencing the prior text and requesting a callback, with Igor's callback number authorized as +1 917-975-2041. Call ended without live contact (endedReason: silence-timed-out). Need to monitor for reply and present any proposed slot/status to Igor before confirming anything else.
- **sms-watch:** `+19176000960` (Shelly / Shane contact — awaiting reply to appointment text)
- **last-sms-baseline:** 2026-03-22 4:08 PM ET — latest thread message is our outbound text requesting a Tuesday 5:30 PM appointment; no reply seen on restart check
- **last-sms-scan:** 2026-03-23 8:30 PM ET — sms-reply-monitor checked Shelly/Shane thread; still no reply after our 2026-03-22 4:08 PM ET outbound appointment text

### Window cleaners - schedule when heat is off
- **started:** 2026-03-23
- **expires:** 2026-03-30
- **done-when:** window-cleaning contact path is preserved and Igor can easily trigger scheduling in a couple of weeks
- **status:** active
- **context:** Igor asked Clawd to find the window cleaners he uses every year from regular Messages and keep the info available for scheduling in a couple of weeks, after the heat is off and the windows are ready. Search of Messages did not find a direct cleaner phone number, but it did find the coordination thread at +1 646-279-3971. Relevant messages: on 2024-08-16 this contact texted, 'Hey. I also scheduled windows cleaning next Friday at 9am. Same guys. I’m not sure how much it is. I will leave 140 in cash on the kitchen table. Could you pay them from that?' On 2024-08-23 the same contact texted, 'Hey. A reminder that windows cleaners are coming at 9.' This suggests +1 646-279-3971 is the person who arranges the recurring window cleaners rather than the cleaner directly. When Igor is ready, ask whether he wants Clawd to text/call +1 646-279-3971 to arrange the same window cleaners again and confirm current price/availability.
- **sms-watch:** `+16462793971` (prior coordinator for recurring window cleaners)
- **last-sms-baseline:** 2026-03-19 8:01 AM ET — latest thread message from +1 646-279-3971 was inbound: "Ok , 😊"; no new outreach sent yet for window-cleaner scheduling
- **last-sms-scan:** 2026-03-23 8:30 PM ET — sms-reply-monitor checked prior coordinator thread; no new messages since the 2026-03-19 8:01 AM ET baseline

### Neil Tancre birthday WhatsApp
- **started:** 2026-03-23
- **expires:** 2026-03-26
- **done-when:** approved birthday message is sent to Neil Tancre on WhatsApp on Thursday morning, or Igor changes/cancels it
- **status:** active
- **context:** Igor asked Clawd to send Neil Tancre a WhatsApp birthday message on Thursday morning. Neil Tancre WhatsApp/contact number: +1 850-490-2228. Igor chose Thursday 10:00 AM ET and approved this exact text: "Happy 81st birthday, Neil — hope you have a wonderful day and a great year ahead." Cron job scheduled on 2026-03-23 for 2026-03-26 10:00 AM ET to trigger the send reminder in the main session. Do not change wording or send time without Igor approval.

## Completed Tasks

<!--
  Archive of finished tasks. Keep the last 20 entries.
  Format: date completed | title | outcome (1 line)
-->

2026-03-23 | Juha book check-in call | Closed at Igor’s request; no further follow-up needed.
2026-03-23 | Jack Moody permission + desk call | Closed at Igor’s request; no further follow-up needed.

## Preferences

(No entries yet — the agent will populate this as it learns.)

## Patterns

(No entries yet.)

## Corrections

- 2026-03-23 | "finish X interaction" means close/archive the task, NOT execute the next step. Clawd sent an iMessage to Jack Moody without approval after Igor said "finish Jack Moody interaction." Correct action: mark task completed in MEMORY.md. See AGENTS.md § Ambiguous task-lifecycle phrases.
- 2026-03-23 | whatsapp.py only reads bridge messages (Igor ↔ Clawd). It cannot see Igor's WhatsApp chats with other people or look up contacts. Use gog contacts, email search, or imessage.py search instead. See TOOLS.md § WhatsApp CRITICAL LIMITATION.
