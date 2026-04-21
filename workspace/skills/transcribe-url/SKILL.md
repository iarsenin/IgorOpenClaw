---
name: transcribe-url
description: Use when Igor sends `/transcribe <URL>` or asks for a full transcript from a YouTube video, podcast episode, webinar, interview, or hosted audio/video page. Prefer an existing full transcript first, otherwise acquire audio and transcribe it cost-effectively. Reply with a concise WhatsApp summary in 3-5 bullets, and email Igor the detailed summary plus full transcript only when a full transcript was actually obtained.
allowed-tools: Bash
user-invocable: false
---

# Transcribe URL

This skill supports the deterministic `/transcribe <URL>` plugin command and also covers non-command requests for media transcripts.

Important boundary:
- This skill documents the transcript workflow.
- The live `/transcribe <URL>` command itself is owned by the repo plugin in `openclaw-plugins/transcribe-command/`.
- Do not try to replace that command contract with a skill-only implementation; WhatsApp slash commands need the plugin `before_dispatch` path.

```text
/transcribe <URL>
```

The command itself counts as approval to email the transcript package to Igor's
primary email address.

## Primary Command

Run:

```bash
python3 "$OPENCLAW_REPO/scripts/transcribe-url.py" run "<URL>" --email-to "igor.arsenin@gmail.com" --json
```

## What The Helper Does

The helper script:
1. Checks whether the URL is directly accessible.
2. Tries alternate public access paths when the page itself is awkward or blocked
   (for example canonical podcast RSS feeds, publisher transcript endpoints,
   RSS/audio enclosures, or `yt-dlp` extractor access).
3. Looks for an existing full transcript first, preferring publisher/feed
   transcripts over fresh transcription.
4. Falls back to audio download + transcription only when needed.
5. Uses the cheapest viable path:
   - existing transcript
   - canonical provider transcript APIs exposed by the feed/page
   - Gemini audio transcription when compatible
   - OpenAI audio transcription as fallback
6. Tags speakers: cleans up `Speaker 1` labels into real names, and for
   untagged transcripts runs a Gemini text-only post-pass that splits the
   transcript into per-speaker paragraphs (`Ezra Klein: ...`) using
   contextual cues + metadata. Falls back to the unlabeled transcript if
   the model output looks broken.
7. Builds:
   - `whatsapp_summary`
   - `detailed_summary`
   - transcript artifact file
   - email send status

## Response Rules

After running the helper:

1. Parse the JSON result.
2. Reply to Igor with `whatsapp_summary`.
3. If `transcript_available` is true:
   - mention that the detailed summary + transcript were emailed only if `email_sent` is true
   - if email failed, say that clearly
4. If `transcript_available` is false:
   - do **not** send or draft any email
   - explain briefly that no full transcript could be obtained
5. Keep the chat reply concise. Do not dump the full transcript into WhatsApp.
6. Do **not** ask Igor whether he wants a summary or full text. `/transcribe` already implies:
   - send the concise 3-5 bullet WhatsApp summary now
   - send the full transcript by email if available

## Rules

- Prefer the helper script over ad hoc browser/manual transcription logic.
- Do not treat show notes, summaries, or timelines as a transcript.
- The result must be a **full transcript** before email is allowed.
- If a source is blocked by anti-bot or paywall and no alternate public access is
  found, send only the concise WhatsApp summary/status.
- Do not create a MEMORY task unless manual follow-up is required.

## Debugging

For quick dry runs while debugging:

```bash
python3 "$OPENCLAW_REPO/scripts/transcribe-url.py" run "<URL>" --skip-email --json
```
