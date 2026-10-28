# `/sum` output-limit recovery — October 27, 2026

## Incident and cause

The latest customer `/sum` failed during Gemini transcription, not at the
WhatsApp connection, download, authentication, or quota layer. The actual saved
HTTP 200 response ended with `MAX_TOKENS`: 65,536 generated tokens for a
1,591.382938-second recording. The helper grouped token exhaustion together
with blocked/incomplete responses and raised a terminal error. Consequently
the already-configured OpenAI fallback never ran.

The original failed response and recording remain unchanged in private local
state. No historical failed job, delivery receipt, or provider usage is erased.

## Fix

- Explicit, unblocked Gemini `MAX_TOKENS` discards the partial text and latches
  Gemini off for the rest of that run. A text-only request switches to the
  existing OpenAI text route. An audio request instead uses the actual cached
  recording through the audio-transcription endpoint; it never sends a Gemini
  file URI or partial transcript to a text model.
- Gemini generation now has a 16,384-token output cap instead of the model's
  implicit 65,536-token maximum. This bounds runaway output, not total job fees.
- OpenAI audio fallback checks **duration as well as file size**. It splits long
  inputs into fresh, ordered, at-most-three-minute MP3 chunks, verifies their
  aggregate duration including the final tail, and submits each once. A small
  compressed file can still be a long recording. Every chunk must succeed
  before the helper accepts any assembled transcript.
- A returned OpenAI transcription output-token count at or above 2,000 is
  rejected as potentially truncated. Blank or invalid text and provider failures
  stop subsequent requests. No successful prefix is emailed as a full transcript.
- Explicit safety/recitation blocks, unknown finish reasons, malformed responses,
  disabled fallback, missing credentials, and OpenAI failures retain their stop
  behavior. This is not a retry loop or a way around a safety block.
- WhatsApp receives a short error status when a run fails. Detailed helper stderr
  remains in the server log rather than being echoed into the chat.

There is no model migration, key rotation, billing/configuration change, or new
background worker. The standalone `/sum` transcript, summary, and email contract
and separate `/shrink` routing are retained. Pre-existing unrelated local work
is not part of this fix.

## Validation scope

Tests cover the saved response's exact failure class, a once-only provider switch,
partial-text exclusion, actual audio rather than file-reference fallback, strict
safety holds, opt-out/missing-key behavior, ordered chunk completion, lost-tail
rejection, token-limit/empty-chunk rejection, and the full transcript/summary/
mocked-email package. Real FFmpeg tests exercise a compressed six-minute input
and its short final tail. No external requests occur in offline regression tests.

The actual saved production response was also replayed locally with both HTTP
calls mocked. It selected the fallback without modifying the old evidence.

A separate bounded live smoke reuses the actual cached 26-minute recording,
replays only the old Gemini failure **decision offline**, and permits at most
nine real OpenAI audio calls plus speaker-label and summary requests. Fresh raw
responses and usage are saved privately under
`output/shrink/sum-output-limit-recovery-20261028/`. No fake Google call is logged
as a fresh billed request. WhatsApp and email delivery are disabled; URL download
and actual email delivery are not retested by that smoke.

Chunk coverage and a successful package are plumbing checks, not a guarantee of
ASR word accuracy, speaker identity, independent fact checking, or manual acoustic
approval. Normal new customer requests can run after activation; this release
does not automatically resend the historical failed request.

Provider limits checked against the
[Gemini finish-reason reference](https://ai.google.dev/api/generate-content#FinishReason),
[OpenAI transcription model documentation](https://developers.openai.com/api/docs/models/gpt-4o-mini-transcribe),
and [file-transcription guide](https://developers.openai.com/api/docs/guides/speech-to-text).
Current response evidence, not model names or scores alone, determines the result.

## Observed results

The live cached-recording smoke completed successfully: all 11 fresh requests
returned HTTP 200 with usage recorded, producing a 27,090-character transcript
and 3,736-character summary. The nine transcription responses used 571–716
output tokens each, below the truncation tripwire. Speaker-labeling preserved
the exact transcript word sequence. No WhatsApp message or email was sent, and
no source-fidelity or personal-listening approval is asserted.

Working-tree regression passed **310 Python tests and 34 JavaScript tests**.
Python network access was blocked; external sends were mocked. This broader
suite includes pre-existing local development that is not part of this patch.
The release is limited to the Sum provider/helper, its command's public error
status, their tests, and this document. Clean-archive checks and activation are
recorded below only after they are observed.

The exact staged release was separately extracted into a fresh archive and
passed **137 Python tests and 23 JavaScript tests (160 total)**, including the
existing committed Sum/Shrink regressions, with no dependence on the unrelated
uncommitted native-pipeline code. Configured credential values were absent from
all six staged files. Only this documentation changed after the archive test.

After confirming no active Sum request or queued/running/locked Shrink job, the
gateway was restarted and reached ready at 22:33:51 EDT on October 27 (PID
56335). WhatsApp then reported configured, linked, running, connected, and
`lastError: null`. Startup removed zero media files. No customer message or
historical result was resent. Production billing and credentials are unchanged;
all 11 new live calls belong to the isolated **testing** evidence, not a customer
production run. Usage is retained per call; no invoice or fixed per-job price is
claimed.
