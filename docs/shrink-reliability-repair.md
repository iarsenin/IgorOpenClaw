# Reliability repair — not a new production release

The original `/shrink` release had no successful full-episode delivery. Unit
tests and service health checks did not establish that the product worked.
Production processing is therefore paused with an explicit maintenance message;
`/sum` remains available. The new implementation is local and experimental, not
enabled as the queue worker and not pushed as a finished release.

## What is actually verified

The user's 107.21-minute episode has now produced a reviewed 99.25-minute edition
in its original voices. Three small nonsemantic restarted phrases were removed;
most shortening is the pitch-preserving 1.08× tempo. This is not a summary or a
large semantic abridgment. All 11 actual Opus parts were sent to the original
requesting WhatsApp target, with 11 distinct non-dry-run platform message IDs.
After delivery, the recipient replied “looks good” to the playback/appearance
check. This confirms the delivered result looked right to the recipient; it is
not evidence of complete personal listening or a word-by-word fidelity review.
The reply was recorded separately without changing acceptance or send receipts.

Before delivery, MAIN reviewed the complete episode navigation and protected
material, all actual-source proposal reports, the independent complete
source/retained-text report, actual join checks, all 31 complete source/output
audio-window reports and the known conflicts. Every part's exact encode was
decoded again and matched to its listened media; ordered frame ownership and
every retained pre-tempo sample outside the declared fades were verified. MAIN
acceptance binds the complete reports, source, result, media hashes and retained
navigation IDs. This is model-assisted fidelity review, not personal listening
or independent verification of the speakers' factual/medical claims.

The medical phrase discrepancy (“is in” versus source-ASR “isn't”) was checked
with separately blind original-source and actual-output audio readings. Both
heard the same complete “is in an animal model” phrase without uncertainty.
The archived ASR was not rewritten; it remains fallible navigation.

## Diagnosed defects and repairs

- A listener previously copied an instruction into its supposed heard speech.
  Instruction echoes remain rejected.
- Audio-model JSON formatting is not guaranteed. The reader now recognizes two
  exact, lossless encodings of the same six fields: framed text and valid
  six-string JSON. Missing, duplicate, unexpected or malformed fields are still
  held. No JSON repair, issue suppression or format-retry model is used.
- A text critic received 260,149 tokens because retained navigation was encoded
  inefficiently, and incorrectly demanded sound evidence from a text-only gate.
  Exact source/retained words, original IDs and local-speaker/segment metadata
  now fit in 98,489 input tokens. The independent critic uses GPT-6 Sol with low
  reasoning through Responses and strict output schema. Its live complete
  report covered all three cuts and all 41 protected ledger entries.
- A join test included “training effect” in its source context but began its
  output clip later. It falsely reported that phrase missing. Corresponding
  physical passages replaced the mismatched clip construction; all three actual
  final joins subsequently passed.
- Low energy alone allowed a delivery split inside “this is a speech.” A single
  diagnosed repair moved that boundary 5.41 seconds to the candidate pause after
  “It's called Personal Renewal.” Both affected files were re-encoded and
  reviewed. Twenty earlier windows were reused only after proving byte-identical
  actual source and output inputs and exact prompt/protocol/model bindings.
  Eleven new complete comparisons finished the case. No samples were lost,
  duplicated or reordered. New partitioning uses exact ASR punctuation/gap
  hints as navigation plus waveform search; hints are not word-onset or
  speech-absence proof.
- Completed exact source/transcription evidence is reusable across diagnosed
  repairs. All old raw responses, failed jobs and usage remain immutable and
  owned by their original ledgers; reuse is not a free-cost assertion.
- Delivery now verifies a real platform receipt, correct destination/channel
  and nonempty message ID. Zero exit status alone is insufficient. Ambiguous
  sends latch without automatic resending. Copied media filenames are unique.

## Release acceptance still open

Six predetermined natural-recording comparison repeats and two deliberately
damaged controls have the expected outcomes under the current lossless parser.
One old report-format failure remains archived and was interpreted offline with
zero additional provider requests, not reset or replayed.

The repaired full pipeline passed the short interview. The short archival
lecture is still held: its paired reviewer claimed a missing sentence remainder
at the recording's end. Separately blind original-source and actual-output end
checks both heard exactly “and then you know if you build,” without uncertainty.
The alleged remainder is unsupported by the actual source; the archived source
ASR also guessed extra ending words. The failed paired report remains immutable.
The exact blind source/output checks and complete conflict review are preserved
in the private repair directory; they are not used to secretly rewrite a failure
into a pass or alter its source transcript.
This needs a justified, general handling of original recording fragments and
unsupported reviewer findings. It is not a reason to release based on another
passing unit-test count or to rerun the failing report until it passes.

Current offline regression checks pass 181 Python tests and 22 JavaScript tests,
including `/sum` registration/dispatch and the maintenance stop before job/API
creation. Those counts are not a release certificate. The worker stays paused
until the remaining live acceptance checks and the actual deployed command path
are validated. No rejected test audio or private recording/report/key is put in
Git. The existing completed Huberman work and old fixed-cohort histories remain
unchanged.

## October 10 publication and restart scope

The user explicitly requested publishing the changes and restarting the server.
This publication contains the maintenance stop, lossless report reader, isolated
experimental source-relative pipeline and its tests, and this incident record.
It is not activation of the replacement worker. The experimental modules are
not registered as native commands or selected by the production queue. The
case-specific publisher still requires exact MAIN acceptance and actual send
receipts; it is not an unattended production delivery path.

The gateway is restarted using its existing LaunchAgent, preserving its private
error-log destination, credentials, channels and sessions. The general `/shrink`
worker remains unloaded and its maintenance marker remains present. `/sum`
continues to use its existing implementation. Unrelated local configuration,
workspace changes, historical research, private audio, reports and keys are
excluded from the commit. No episode is reprocessed or sent again by deployment.

Validation of the publication's clean staged tree passed **107 Python tests and
22 JavaScript command/integration tests**, with outbound sockets disabled for
Python regression tests. The 181-test working-tree count includes unrelated
historical research tests and is not the committed release count. Compilation,
JavaScript syntax and staged whitespace checks passed. A scan of staged content
against configured secrets found no matches. No provider request, email or
WhatsApp test send was part of deployment validation.

At 20:36 UTC (16:36 America/New_York) on October 10, the gateway restarted from
PID 73295 to PID 76666. Its connection probe and configuration audit passed;
WhatsApp was linked, running and connected with no reported error. No new
startup errors appeared in the inspected gateway logs. The exact gateway plist,
credential file, channel configuration and `/shrink` maintenance marker retained
their pre-restart hashes. The `/shrink` worker remained unloaded. These are
point-in-time service observations, not an end-to-end approval of the unresolved
replacement pipeline.
