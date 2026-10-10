# OpenAI fallback validation — October 10, 2026

The original-voice `/shrink` worker now has an availability-only OpenAI fallback.
Selected models are `whisper-1` for word timestamps, `gpt-6-luna` for separate
editorial and text-fidelity calls, and `gpt-audio-1.5` for actual-audio listening.
No replacement speech, cloning, source-word normalization or automatic
quality-failure retry was added. Configuration and primary-source model links
are in [the operating guide](shrink-original.md).

## Tests and model selection

Two fixed 45-second prefixes were taken from the existing interview-natural and
MIT/archive-natural recordings. The physical sources were checked against their
immutable receipts. These are smoke-test fixtures, not a new randomized cohort
or representative sample. Their boundaries can interrupt existing utterances.

1. Gemini's actual file-upload response was HTTP429 with an explicit **monthly
   spending cap** message. The worker saved it and switched to OpenAI without
   another Gemini request. This is not a claim about when that cap resets.
2. Whisper returned full timestamp navigation. Auto-detection incorrectly chose
   Welsh for the English interview. A separately recorded, English-bound request
   corrected that configuration; the old raw ASR remains unchanged. Production
   now explicitly requests English by default, configurable for other languages.
3. The first text request rejected the audio-only `modalities` field. That exact
   HTTP400 was preserved. The corrected request omits this field for the text
   model; it does not retry malformed or failed reports in production.
4. The critic initially conflated acoustic approval with its text-only task and
   placed routine limitations in its uncertainties. A separately hash-bound
   [text-comparison contract](../config/shrink-text-review.md) now defines that
   gate without asking it to certify sound. Genuine edit uncertainty still stops
   the pipeline; all physical-audio gates remain separate and strict.
5. The cheaper audio-mini snapshot was rejected after its actual responses
   supplied invalid IDs and unreliable ending descriptions. The current
   `gpt-audio-1.5` was tested once on each exact already-rendered outgoing file,
   without repeating transcription, editing or rendering. Both final reports
   satisfied the current schema, coverage and issue/uncertainty checks. Audio
   Chat's natural `stop` finish with exactly one complete valid function call is
   supported; truncation, refusal, extra/missing calls and audio output still fail.

The final text stages and final outgoing-audio gates passed for both fixtures.
Each 45-second source produced a 42.1114-second local output at 1.08×. The plans
chose **zero content/pause cuts**, so these fixtures test provider plumbing,
conservative retention, encoding and gentle tempo, not substantive live cut
selection. Real local cut/crossfade behavior is separately covered by the
FFmpeg regression tests. The AAC archives are technically decoded; listening
covered the actual outgoing Opus files decoded to WAV. No personal human
listening, exact-word acoustic proof, independent fact checking or full-episode
quality approval is claimed. Model boundary descriptions and partial source
utterances remain limitations, not inferred missing words or approved repairs.

Failed test requests, rejected reports and their usage remain private under
`output/shrink/short-audio-smoke-20261010/`. Diagnosed follow-up tests use new
named roots; started/failed attempts were not erased. Exact completed ASRs/plans
were reused with input and result hashes. All failed and exploratory calls count
toward test spending. Missing usage is unknown, not zero. No invoice, total-cost
upper bound or accepted-production-minute cost is asserted. The completed old
stress benchmark, paused watcher, baseline and ledger were not changed.

## `/sum` regression and service

The `/sum` plugin and helper bytes remained unchanged throughout this feature.
All 17 JavaScript command/integration tests, 13 existing transcript-helper tests
and 37 original-audio/fallback tests passed: **67 offline tests** in total. They
include strict issue/uncertainty holds, schema/coverage rejection, no quota retry,
one provider switch, exact saved-attempt latches, real local FFmpeg, and isolation
between the two commands. `git diff --check` passed for the changed tracked files.

The existing `/sum` OpenAI transcription path also processed both 45-second
fixtures through the real helper. For this isolated test only, Gemini keys were
set to empty in the test process; no production configuration was changed and
no Gemini quota call was repeated. Transcripts/packages passed, but **summaries
were unavailable**. This is not a full `/sum` success: its configured summary
stage still depends on Gemini and the observed monthly spending cap still blocks
that stage. No summary fallback was silently added to `/sum`.

Email and WhatsApp delivery were disabled for every live test. The private test
server bound only to localhost. A local Sum-test harness variable-name error
occurred before any API request, was documented, and was repaired in a distinct
test root. It was not a production helper failure.

With no queued/running `/shrink` jobs, the idle worker was restarted to load the
new code. The unchanged gateway PID was 61704 and its connectivity probe passed
on localhost:18789. The worker restart was checked again after the final
enqueue-only regression fix. No gateway
credentials, production billing, sessions, old jobs or completed benchmark
approvals were reset. These changes have not been committed or pushed by this
feature checkpoint; unrelated dirty-worktree changes are preserved. The following
release supersedes that checkpoint's `/sum` summary blocker and local-only status.

## Follow-up release: Gemini 3.6 and complete `/sum` fallback

Later on October 10 the user authorized migration, retesting, GitHub push and
server restart. Google confirms that `gemini-3.5-flash` now redirects to
[`gemini-3.6-flash`](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash).
The original-audio worker's critic now explicitly uses 3.6. The distinct
`gemini-3.5-transcribe` and 3.8 audio-listening settings are unchanged; historical
research and benchmark model bindings are not retrospectively rewritten.

`scripts/sum_provider.py` adds per-run availability-only routing for `/sum`.
Eligible primary HTTP failures latch Gemini off for the remaining run. Text
summarization and speaker-text stages use `gpt-6-luna` through the Responses API,
with low reasoning and no stored conversation. The existing
`gpt-4o-mini-transcribe` audio path remains. OpenAI-only operation also works when
Gemini is absent. An OpenAI HTTP/transport/incomplete failure stops subsequent
requests; request/schema errors or incomplete Gemini success do not trigger a
different model. Requests have no credential-bearing URL parameters.

Private raw response/usage evidence is saved outside the transcript scratch
directory, so successful email cleanup does not erase it. The location defaults
to `~/.openclaw/state/sum-provider-evidence/`, configurable with
`SUM_PROVIDER_EVIDENCE_DIR`. Only fresh provider-upload file IDs from that run
are cleaned up. `SUM_OPENAI_FALLBACK=0` disables fallback, and `SUM_PROVIDER=openai`
explicitly selects the OpenAI route. `SUM_OPENAI_TEXT_MODEL` defaults to
`gpt-6-luna`. No production credentials or billing limits were changed.

A live test used the same two fixed 45-second fixtures for **both commands**.
The first normal Gemini-first `/sum` request received the actual monthly-cap
HTTP429, then completed OpenAI transcription and a genuine GPT summary. Later
isolated tests explicitly selected OpenAI after that observed cap; they did not
repeat Google quota requests. Both `/sum` cases produced transcript packages
and summaries. Both `/shrink` cases completed fresh ASR, plan, text review, real
local encode and actual-outgoing-audio review. Each output was 42.1114 seconds;
no substantive or pause cuts were selected. Fifteen actual HTTP responses were
recorded, including the failed Google call. No email or WhatsApp was sent.

MAIN's source review found that the first Sum summary promoted an unverified
ASR-mentioned name into a speaker identity. The edit skill's attribution rules
influenced the repair: no name was corrected from external knowledge or another
transcription. The instruction now requires Unknown and neutral speaker wording
when supplied speaker labels/metadata do not establish identity. Two new summary
requests reused the exact complete transcripts and metadata, with no repeated
ASR. Both returned Unknown and retained the original warning/method context.
Speaker-tagging output must also preserve the exact spoken-token sequence;
length alone no longer permits omitted negatives or words. These are bounded
checks, not a guarantee of universal ASR, identity or claim-strength accuracy.

Final working-tree checks: **142 Python tests and 17 JavaScript tests passed**,
with network disabled in the offline Python suite. Syntax compilation and diff
whitespace checks passed. The `/sum` command plugin itself remains byte-identical;
its public command, email packaging and routing are unchanged. The previously
uncommitted isolated-downloader/email-destination compatibility changes in its
helper and their tests are included as reviewed, relevant dependencies.

Private live evidence is under `output/shrink/fallback-release-20261010/`,
including the preserved first summaries and separate attribution recheck. All
failed/exploratory requests remain counted; missing usage is unknown, not free.
No completed benchmark, baseline, heartbeat, synthetic render or old failed job
was resumed. Short-prefix tests are not representative YouTube sampling,
personal human listening or full-episode quality certification.

The release stages only runtime provider/contract changes, their tests, current
docs and narrow README/environment-template notices. Pre-existing unrelated
setup/config/workspace edits and deletions, legacy research, local `.env`, media
and raw responses are excluded. Clean-release and deployment checks are recorded
after the release is built; no claim of deployment precedes its observed status.

A clean archive of staged tree `c1693db7d2e075d2f884ad12e4280b8e66ab1042`
independently passed **68 committed Python tests and 17 command tests**, with
network disabled in the Python suite. The larger 142-test working-tree Python
count includes historical research that is not part of this release. The staged
files were checked for the configured secret values; no matches were found.

Release commit `2113ea5` was pushed to `origin/main`. With an empty shrink queue,
the gateway and worker were restarted; the observed gateway PID was 66013 and
worker PID 65953. Gateway connectivity passed on localhost:18789, and the
WhatsApp probe reported enabled, configured, linked, running, connected and
healthy. No test message was sent. A final configuration regression also checks
that opting out of implicit OpenAI fallback disables audio as well as text, while
explicit OpenAI mode remains available. Default-enabled live request shapes are
unchanged by this guard.

Final release tree `3b974296ab2303179f84ea69e9f49fecce612090` passed **70
committed Python tests and 17 JavaScript command tests** in a fresh archive.
The working tree passed **144 Python tests and 17 JavaScript tests**. Both clean
archives passed without uncommitted research, media, live credentials or network
access. The last update only honors the explicit fallback opt-out and records
these checks; it does not change the default-enabled live model requests.
