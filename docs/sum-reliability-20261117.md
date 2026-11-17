# Sum-only release — November 17, 2026

## Failure and repair

The 16:09 request reached a running server. Its second long-transcript summary
chunk returned Gemini HTTP 200 / `STOP`, but included unescaped quotes inside a
JSON string. Parsing failed before final synthesis or email. The existing
provider fallback only examined API availability/completion, not summary content.

Both chunk summaries and final summaries now request schema-constrained output
from the existing Gemini/OpenAI models. Application validation independently
requires exact fields, correct types, nonblank strings, and nonempty topic
arrays. Duplicate fields, non-finite JSON, oversized output, mixed prose, and
incorrect field types are rejected. No particular bullet count or subjective
prose quality is used as a retry trigger.

A completed, unblocked Gemini summary with invalid JSON/schema switches once to
OpenAI using the **original request and source**, never the malformed answer.
Gemini stays stopped for the rest of that run, including later chunks and final
synthesis. Invalid fallback output stops the run without quote repair, another
model variant, a local substitute, or an email containing a partial summary.
Safety/refusal and malformed provider envelopes remain separate terminal cases.
Raw responses and usage are saved before validation.

The live test also found that models may incorrectly report transcript
availability when final synthesis sees chunk summaries rather than the complete
source. The returned availability flag now comes from actual pipeline state,
not the model's guess. This changes known metadata, not transcript/summary words;
original model output remains in the raw receipt.

## Removed audio-editing feature

At the user's request, the production `/shrink` plugin, runtime/experiment
scripts, exclusive contracts, worker installer, and associated tests were
removed. Its idle LaunchAgent was unloaded and its plist removed from the active
LaunchAgents directory. Sum routing, setup, configuration template, environment
example, and current workspace instructions no longer register or advertise it.
Retired commands receive Sum usage, not an agent/worker fall-through.

Removed code, including previously untracked versions, is recoverable in the
private `~/.openclaw/retired-shrink-20261117.QoF92o/` archive. Historical reports,
customer job state, audio, raw responses, worker logs, and `output/shrink/` were
not deleted. Older audio-editing documents under `docs/` are historical, not
installation instructions. The private output/downloader ignore rules remain.

The shared downloader is retained. Its configuration is now
`SUM_YTDLP_MODULE_DIR`; the existing local setting was renamed without moving or
reinstalling the downloader. No credentials, provider models, or billing settings
were changed. Broad setup/uninstall scripts were not run on the live server.

## Tests and actual provider evidence

The Sum-only working tree passes **60 Python tests and 13 JavaScript tests**.
Offline Python tests block network access; command/email sends are mocked. Real
FFmpeg tests check compressed-audio splitting and the short final tail.

Coverage includes malformed first/later chunks and final synthesis, strict field
and JSON parsing, empty text versus malformed/thought-only envelopes, safety
holds, opt-out/missing-key behavior, one provider switch, failed fallback latches,
English/Russian quotes and negatives, source-word-preserving speaker labels,
long/short transcript packaging, no repeat ASR/download, email success/failure,
timeouts, and retired-command rejection. A separate review found and prompted a
regression test for the malformed-envelope/empty-text distinction.

Five live **testing** requests were made using the existing configuration:
two Gemini structured-summary requests and three OpenAI fallback requests. All
returned HTTP 200 with usage retained. The exact old malformed response was
replayed offline, without recording fake primary usage as a fresh paid request.
The complete saved 112,379-character source was used for two chunk summaries and
final synthesis, with zero new audio downloads or transcriptions.

The initial live-smoke assertion failed because of the model's incorrect
availability flag. That failed assertion and all responses are retained. After
the deterministic metadata repair, replay of those same completed responses
passed without new provider calls; a fresh final-version helper request also
passed. This is not a claim that the initial smoke passed unchanged.

Private evidence is under
`~/.openclaw/state/sum-release-tests/20261117-summary/`. It includes original
input hashes, the failure, recheck, fresh final-version result, and all new raw
responses/usage. No test email or WhatsApp message was sent. Test usage is
separate from customer production usage; no invoice or fixed per-job dollar
price is asserted. These are schema/routing/package checks, not independent
claim verification, personal acoustic listening, or a guarantee of ASR accuracy.

Provider request formats were checked against the official
[OpenAI structured-output guide](https://developers.openai.com/api/docs/guides/structured-outputs)
and [Gemini generation configuration](https://ai.google.dev/api/generate-content).

Clean-release and live activation checks follow only after they are observed.

## Observed release and activation

The staged release tree `de26ea0772b5ba7eb1724930373e23a4aa482665` was extracted
into a clean archive and passed **61 Python tests plus 13 JavaScript tests (74
total)**, with Python networking blocked. It includes one committed legacy test
absent from the dirty working tree. Shell syntax and staged whitespace checks
passed. No source/runtime code changed after that test; only this release note
was extended. Configured credential values were absent from staged files.

With no active command helper or retired-worker job, the gateway was stopped,
its configuration changed only to remove the exact retired plugin load/allow/
entry records, and its prior configuration backed up privately. A complete
semantic fingerprint verified that every unrelated setting was unchanged. The
current Sum-only workspace contract was installed without resetting sessions,
authentication, cron, or provider configuration.

The gateway reached ready at **16:28:48, November 17 (UTC−05:00)**, PID 16604.
It loaded `google`, `sum-command`, and `whatsapp`, with no retired audio plugin.
The WhatsApp probe reported configured, linked, running, connected, and
`lastError: null`. The retired worker service was absent and its LaunchAgent
plist remained in the private recovery archive. No test/customer result was
automatically sent or resent during activation.
