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

## Production launcher repair and full-episode continuation

The subsequent user-reported `/shrink` failure occurred at the launcher, before
any job or provider attempt existed. Its Python stderr was discarded by the
plugin, and gateway stderr was configured as `/dev/null`; the exact original
exception therefore cannot be reconstructed honestly. Dependency-aware Python
selection is now shared with `/sum`. Redacted private launch receipts preserve
exit code, signal, stdout and stderr, while chat receives a diagnostic ID only.
The local gateway LaunchAgent now retains private stderr rather than discarding
it. No credentials or global Python packages were changed.

The new `enqueue-check` command exercised the **actual production queue**:
locking, exclusive probe creation, atomic JSON write/read and exact probe cleanup,
with zero provider requests and no runnable job. Then the actual OpenClaw plugin
loader/native command path, using the gateway's environment, successfully saved
the user's exact request as job `20261010-114130-01961acd` while its worker was
temporarily held. This is a real enqueue check, not merely a mocked queue receipt.

Full-length inspection exposed an additional integration limit: a 600-second
24kHz PCM WAV is larger than OpenAI's 25 MB transcription ceiling. The API
[reference supports FLAC](https://developers.openai.com/api/reference/resources/audio/subresources/transcriptions/methods/create),
so oversized inputs are losslessly packed and fully decoded for byte-identical
PCM verification before upload. No source change, resampling, lossy fallback or
clock shift is allowed. A real full ten-minute upload used 16,365,504 bytes and
Whisper returned HTTP200 with a 600-second response. Its three empty-text
timestamp entries caused the old parser to hold the attempt. The new parser
excludes only literal empty, finite/in-range metadata entries and still requires
the complete nonempty word sequence to cover the exact ASR text. Blank entries
are not evidence of speech absence. All 1,950 actual word records and the full
text remained unchanged in this response.

That failed job/raw/upload/usage history remains intact. A separately bound
continuation, `20261010-115812-1cb08bb6`, copied the same source bytes and reused
the completed first response after the pure adapter fix. It did not repeat the
first ASR call or the observed Google monthly-cap request. Its first-stage proof
binds the full parent request/packing receipts, raw hash, original PCM and
reparsed result; it claims no source or sound acceptance. Parent usage remains
owned by the parent, never counted twice or treated as free.

Prompt payloads now losslessly factor repeated navigation keys into named
columns. The source and retained text comparisons still receive every word,
ID, segment and local-speaker value; planning/cut listening keep unrounded times.
The final listener gets every retained word with local-speaker runs instead of
repeated per-word timing dictionaries. The full raw/navigation/ID data remains
saved, and all same-input listening, coverage and uncertainty gates are unchanged.
This addresses long-episode context size without truncating the transcript or
substituting a summary for it.

The local suite passed **151 Python tests and 21 JavaScript command tests**,
including real ten-minute lossless packing, preserved empty-metadata evidence,
missing-negative/bad-clock rejection, exact compact-view reconstruction, private
credential redaction and no launcher retry. The real user episode is 6,432.7866
seconds long; it is not one of the old fixed benchmark excerpts. It continues
under its own normal production gates. A running job is not accepted audio or
personal human listening, and no quality failure is overridden to finish it.

The continuation exposed one further metadata assumption: at adjacent words in
ASR block 5, the reported start decreased by about 20 ms while both intervals
were finite and inside the physical input. Word intervals may overlap; the
transcript's character order remains authoritative navigation order. The adapter
now preserves those literal values and text order without sorting, shifting or
clamping. A proposed cut uses the complete selected interval envelope and still
rejects any retained-speech overlap or unsafe neighbor margin. Range, character,
coverage, original-audio and final-listening gates remain strict.

Job `20261010-115812-1cb08bb6` is preserved as failed, with all six complete
ASR responses and usage. A further separately bound continuation,
`20261010-121221-1b9ac979`, reuses **all six** exact responses/input/packing proofs
and leaves their words and timestamps unchanged. Only the remaining source
blocks need new ASR requests. No failed or paid ASR request was blindly repeated.
The latest local checks passed **153 Python tests and 21 command tests**. Clean
release checks and the real episode's eventual outcome are recorded separately;
neither metadata adaptation implies sound or source approval.

### Final listening: format defect and held quality results

The full continuation completed all **11 source ASR blocks / 20,413 navigation
words**, the complete text comparison and the original-voice render. Its author
selected **zero semantic cuts and zero pause edits**. The resulting 1.08× version
is approximately 99.28 minutes versus the 107.21-minute original: tempo-only
compression, not a successfully abridged narrative. It has not been delivered.

Final listening exposed a report that echoed a system instruction as supposedly
heard speech and a subsequent malformed JSON tool call. The echo is now rejected
even when the model says `pass=true`. A separately history-bound audio-only
diagnosis kept the same outgoing physical bytes, without another download, ASR
or render. One report parsed and passed. Its next report was malformed **and**
contained adverse observations and uncertainty; no format correction could have
made that an accepted result. It latched all remaining peer requests. The parent
and diagnosis raw responses, failed attempts, original code archive and usage
ledgers remain intact. No audio was sent and no failed provider request replayed.

The final OpenAI interface now uses native plain text instead of best-effort JSON
function arguments. Six exact section headings, explicit complete coverage,
verdict and verbatim issues/uncertainties are parsed locally. Missing, duplicate,
unexpected or incomplete sections remain held; no JSON repair or extra
text-model acoustic adjudication runs. The
[audio model's documented capabilities](https://developers.openai.com/api/docs/models/gpt-audio-1.5)
include text output and function calling, not guaranteed Structured Outputs.

A fresh real short-recording release check returned HTTP200 with correctly framed
plain text. It reported a possible speaker-change/join issue, which the local
gate preserved and rejected. This confirms the live transport/parser/hold path,
**not** audio acceptance or personal listening. Its second fixture was not called
after that hold. Earlier two-fixture `/sum` and `/shrink` checks remain historical
evidence for their exact prior release, not approval of this changed listener.
Normal speaker changes can generate conservative listener findings; they are not
automatically waived or labelled acoustically unresolvable. This episode still
needs a justified quality outcome; the present release fixes startup and report
handling, not a guarantee that every episode will be accepted.

Latest working-tree regression checks: **161 Python tests + 21 JavaScript tests**,
with network disabled for the Python run. `/sum` implementation is unchanged;
only its existing pure environment/interpreter helpers are exported for reuse.
Both command registration orders, enqueue failures and `/sum` transcript/email
dispatch were rechecked. Runtime artifacts, private launch receipts, source
recordings and provider keys are excluded from the release.

The ordinary gateway restart utility regenerated its LaunchAgent with discarded
stderr. The final reload therefore uses the exact validated existing LaunchAgent
with private stderr restored, followed by a connectivity/WhatsApp probe. No
credentials, gateway sessions or global dependencies are reset. This local
service configuration is not a committed secret or a claim about the unrecoverable
original launcher exception.

A clean archive of staged tree `8e01cfe4b1a56664ee2e7cba8460800126b46889`
passed **87 committed Python tests and 21 JavaScript tests**, independently of
uncommitted research. The Python suite had network disabled. All eight staged
files were checked against configured credential values; no matches were found.
After the final reload, gateway PID 70861 and worker PID 71032 were observed.
Gateway connectivity and WhatsApp health were good, gateway private stderr had
no error text, worker stderr was empty and no queued/running shrink job remained.
The production `enqueue-check` succeeded again with zero provider requests.
Neither a held user job nor the held short listening test was automatically
requeued. The archive hash refers to the tested code tree before this final
documentation-only observation was appended.
