# October 12 customer-request recovery

The 112.96-minute customer request stopped after six transcription blocks with
`ASR word text disagrees with its original character span`. The first mismatch
was the accented name Poincaré. The provider's offsets fit UTF-8-byte and
decomposed-Unicode counting, while the application treated them as Python
character indices. Both compatible conventions produce the same exact spans.

The adapter now accepts a different index convention only when every supplied
word matches the original transcript exactly and all derived spans agree.
It preserves the original response, words, timestamps and speaker labels. It
does not guess missing words, correct spelling or move speech. The saved six
blocks—9,730 words—passed this validation without additional provider requests.

Recovery can now reuse complete, verified Gemini as well as Whisper responses,
including the completed prefix of a failed job. The original failed job and its
usage stay intact. Only missing blocks are transcribed in a new job. Each reused
block has a receipt pointing to its original raw response and exact audio.

If a completed text or join review disputes a proposed cut, the job can make one
conservative recovery: retain all original speech, obtain a fresh complete text
review, and render the gentle tempo change. The rejected plan, report and render
remain in the history. Final source/output audio checks still apply before any
delivery; provider failures and ambiguous sends are not retried.

Offline validation passed 128 Python tests and 22 JavaScript tests, including
`/sum`, Unicode index conversion, verified response reuse and both conservative
recovery triggers. These tests exercise mechanics with mocked reports; they are
not a substitute for the actual episode run.

The actual recovery completed under the private
`output/shrink/reliability-unicode-recovery-20261012/` directory. Its six remaining
transcription blocks completed. The initial proposed cut was disputed, so the
recovery retained every original word and rendered 104.60 minutes at 1.08×.

A paired review then flagged words at a window boundary. For an edition with no
speech removals, exact word-position comparisons between sped-up windows are not
the preservation test: the program verifies every retained pre-tempo sample,
complete ordered delivery-frame ownership and the actual encode/decode. Each
complete outgoing part receives an independent intelligibility/playback review.
Editions that remove speech still require the source-relative comparisons and
every cut review. The uncut profile cannot approve an edition with a real cut.

One received PASS report used CRLF line endings. The parser previously rejected
that transport format. It now treats CRLF and LF as equivalent, without dropping
any issues or uncertainty. The already received response was interpreted offline;
it was not requested again. All earlier failures and raw responses are preserved.

All 11 complete outgoing files passed the playback reviews and publication
preflight and were sent to the original requesting WhatsApp chat, with 11 distinct
non-dry-run platform receipts. The delivered edition retains the advertising,
questions, examples and every other original passage; shortening comes from the
tempo change. This is model-assisted playback checking, not personal listening
or factual verification of the speakers' claims. No second full download,
transcription of the first hour, or audio render was needed during the final
delivery recovery.

## Deployment verification

Implementation commit `0bd8d4e` was pushed to `origin/main`. At 01:04 UTC on
October 13 (21:04 on October 12 in New York), the existing LaunchAgents were
restarted without regenerating their configuration. Gateway PID 7447 and worker
PID 7547 were running. Gateway RPC and configuration checks passed; WhatsApp was
configured, linked, running and connected, with no reported error.

The temporary maintenance marker was moved, with its original bytes, into the
queue's private `release-history/maintenance-20261012-before-unicode-fix.json`.
Production enqueue is enabled again. There were no queued or running production
jobs to resume. The queue's atomic IO check passed with zero provider requests.
The worker error log remained empty, and the gateway error log did not grow
during restart verification.

The gateway and worker plists, OpenClaw configuration and gateway environment
file retained their exact pre-restart SHA-256 hashes. Credentials and channel
settings were not rewritten. The `/sum` implementation was not changed; its
command and integration regression tests passed. All old failed jobs, raw
responses, rejected editions, usage and actual delivery receipts remain private
and unchanged. The successful customer recovery was not resent during deployment.

These are deployment observations, not a guarantee that every future episode
will pass. Uncertain audio, failed provider requests and ambiguous send receipts
still stop safely. A no-cut conservative result offers only the gentle speed-up,
not a promise of semantic abridgment.
