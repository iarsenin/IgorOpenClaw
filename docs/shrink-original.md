# /shrink: edit the original recording

Current status (October 10, 2026): automatic `/shrink` processing is paused for
reliability repairs. It returns a maintenance message without creating or
charging a job. `/sum <URL>` remains available. One separately reviewed episode
has been delivered, but the replacement pipeline is not enabled as the queue
worker. See the [repair and validation record](shrink-reliability-repair.md).

The workflow below describes the original-voice editing design, not a claim
that the general command has completed release acceptance. It makes a
chronological listening edit without rewriting or resynthesizing the episode.

The worker downloads the recording, makes a 24kHz mono PCM navigation master,
and obtains timestamped ASR in complete, contiguous ten-minute blocks. ASR is
fallible navigation; it is not word truth or a precise acoustic clock. The
original download, PCM, ASR, proposed cuts, reports and usage remain private.

## Editing and review

1. One editorial request reads the complete navigation and proposes explained word-ID
   cuts, optional wordless hesitation cuts, and a protected-material ledger.
2. Local validation rejects unknown/duplicate IDs, overlap with protected words,
   overlapping retained speech, unsafe neighboring-word margins, cross-block
   cuts, more than 256 joins, and removal exceeding 35% of the recording. The
   reduction ceiling is not a target. Pause cuts leave at least half a second
   of the original gap and never remove annotated words.
3. An independent critic compares the whole retained text and whole source for
   narrative continuity, questions, speaker positions, examples, jokes,
   qualifications and mechanisms. Every cut and protected ID must be covered.
4. Ordinary listening reviews the complete original block containing each cut.
   It checks actual expendable content, affected voices, syllable boundaries,
   hesitation/turn-taking and prospective joins. It must not resolve ambiguous
   speech from grammar, titles or another processed input.
5. FFmpeg joins only chronological source intervals, using 12ms crossfades and
   gentle pitch-preserving 1.08× tempo. The renderer checks exact frame counts
   and byte-identical retained PCM outside declared crossfades. It adds 0.5s
   digital-tail silence to drain the tempo filter. No loudness normalization,
   denoising, cloning or generated replacement speech is applied.
6. The full AAC archive must decode successfully. Every actual outgoing Opus
   part is independently listened to in full, including all voices and joins.
   Any issue, uncertainty, incomplete report or missing coverage stops sending.
   Reviews are model judgments, not personal human listening or proof that all
   future defects will be detected. The local continuous AAC has technical
   decode checks; the independent listening gate covers the outgoing Opus files.
7. Only reviewed, hash-bound files go to the requesting direct WhatsApp chat.
   Every part is preflighted before the first send. An uncertain delivery receipt
   blocks resending, rather than guessing whether a message was delivered.

The complete editorial contract is [shrink-original.md](../config/shrink-original.md).
The independent text gate has its own [stage-specific contract](../config/shrink-text-review.md),
so it does not pretend to perform the separate physical-audio review.
It protects the speaker's claim, not its independent factual truth. This is an
abridgment, not fact checking. It retains meaningful pauses and uncertain
passages; it does not globally delete filler tokens or low-amplitude sound.
Outgoing parts are at most ten minutes and below 14MiB. Part boundaries may
interrupt an utterance; actual-part listening must reject unnatural edges.
There is no automatic repair or boundary retry loop in this first release.

## Failure and resume behavior

The new private queue is `~/.openclaw/state/shrink-original`, separate from the
old synthetic queue. The LaunchAgent label remains `ai.openclaw.shrink-worker`,
but its program is now `scripts/shrink_original.py worker-loop`. It never scans
or resumes old synthetic or benchmark jobs. The completed benchmark heartbeat
remains paused.

Each exact provider stage is persisted as started before its work. Raw model
responses are saved before parsing. A matching completed stage can be reused
only when its result hash, recording, code, contract and models agree. Started,
failed, interrupted, malformed or changed stages stay held. There is no
schema-repair retry, blind regeneration or hourly retry scheduler.
With `OPENAI_API_KEY` present, an actual Gemini availability/access HTTP failure
(401, 403, 404, 408, 429, 500, 502, 503 or 504) permits one switch to OpenAI. The
switch is saved for all remaining stages: Gemini is not tried again in that job.
Other errors, ambiguous transport failures, invalid schemas, truncated reports,
fidelity issues and listening uncertainty do **not** trigger fallback. Each exact
OpenAI request also has a started/received/failed receipt and never replays.
An OpenAI 429 stops all further requests in the job. Gemini 429 stops all Gemini
requests except upload cleanup; the explicitly enabled OpenAI route may continue.
Both primary failures and fallback attempts are retained, including unknown usage.
Structured provider wait advice is recorded as supplied, never invented.
The worker returns a failure notice and does not publish rejected audio.

The command launcher selects a Python interpreter with `requests` and
`beautifulsoup4`, using the same resolver as `/sum`. Each launch saves private
started/queued/failed receipts under
`~/.openclaw/state/shrink-launch-evidence/` (`SHRINK_LAUNCH_LOG_DIR` overrides it).
Failures retain exit code, signal and full redacted stdout/stderr. The chat gets
only a diagnostic ID, never a raw traceback or credentials. A failed or ambiguous
launch is not automatically repeated. `python3 scripts/shrink_original.py
enqueue-check` tests production queue locking and atomic IO without creating a
runnable job, calling a provider or sending a message.

To retry after a diagnosed failure, explicitly create a new job/directory. Do not
delete old attempts to reset a retry counter. Successful delivery receipts are
reused; a crash between sending and saving completion leaves delivery uncertain.

## Configuration and operation

Requires Python with `requests` and `beautifulsoup4`, FFmpeg/FFprobe with AAC and
libopus, and a working public-media downloader. Existing `/sum` download/RSS
routines are imported read-only; its summary and email entry points are not run.
There are no global dependency upgrades in this deployment.

| Variable | Default / purpose |
| --- | --- |
| `GOOGLE_API_KEY` or `GEMINI_API_KEY` | Existing Gemini credential |
| `SHRINK_EDIT_MODEL` | `gemini-3.1-pro-preview` |
| `SHRINK_TRANSCRIBE_MODEL` | `gemini-3.5-transcribe` |
| `SHRINK_AUDIO_REVIEW_MODEL` | `gemini-3.8-flash` |
| `SHRINK_FIDELITY_REVIEW_MODEL` | `gemini-3.6-flash` |
| `OPENAI_API_KEY` | Existing OpenAI credential, reused without copying into reports |
| `SHRINK_OPENAI_FALLBACK` | `1`; set `0` to disable the availability-only switch |
| `SHRINK_PROVIDER` | `gemini`; `openai` explicitly selects OpenAI for a new job |
| `SHRINK_OPENAI_TEXT_MODEL` | `gpt-6-luna`, separate editor and critic requests, reasoning `none` |
| `SHRINK_OPENAI_AUDIO_MODEL` | `gpt-audio-1.5`, actual audio input, text-only report |
| `SHRINK_OPENAI_LANGUAGE` | `en`; ISO language code, or `auto` to omit the Whisper language hint |
| `SHRINK_ORIGINAL_TEMPO` | `1.08`, queue worker; allowed range 1.0–1.15 |
| `SHRINK_ORIGINAL_STATE_DIR` | Optional isolated queue override |
| `SHRINK_MAX_JOBS` | `2`, queued/running job ceiling |
| `SHRINK_WORKER_MODE` | `launchd` in the installed service |

Legacy `SHRINK_RATIO`, TTS model, stock voice and synthesis-concurrency settings
do not affect this worker. Input duration is bounded to ten seconds–six hours.
Long recordings can exceed model context/output or quota; they fail held rather
than truncating the source or delivering a partial episode. No universal 50%
compression or cost-per-hour promise is made. Provider usage is recorded in
each job's `usage.jsonl`; missing usage is unknown, not free. Local compute and
actual invoiced charges are not measured.

### Why these OpenAI models

[`gpt-6-luna`](https://developers.openai.com/api/docs/models/gpt-6-luna) is the
efficient focused-task text model. The editor and critic remain separate calls;
both return a forced report tool call that is validated locally. Audio-only API
fields are not sent to this text model. Text-only reports cannot certify sound.

[`gpt-audio-1.5`](https://developers.openai.com/api/docs/models/gpt-audio-1.5)
is the current audio model. Reviews receive the unchanged physical WAV and
request only text; no speech is generated. The cheaper audio-mini snapshot was
tested and rejected for this job: its actual reports had invalid coverage IDs
and unreliable boundary descriptions. It is not silently retried with a stronger
model in production. This selection followed inspection of those saved failures.
A configuration error never silently changes the model or loosens the rules.

OpenAI ASR uses `whisper-1`, because the needed [word-timestamp capability](https://developers.openai.com/api/docs/guides/speech-to-text#timestamps)
is not supplied by the cheaper ordinary transcription models. Whisper does not
provide speaker diarization: its speaker labels stay unknown, not a guessed
primary speaker. Every physical voice remains in the source waveform, and
actual-audio gates must check affected voices and overlaps. Returned words must
cover the exact ASR text; no guessed words, translation or timestamp repair is
inserted. English is explicit by default after a short English test was
incorrectly autodetected as Welsh. Other languages require the corresponding
configuration, or deliberate `auto` selection.

Ten-minute 24kHz PCM WAVs can exceed the transcription API's
[25 MB upload limit](https://developers.openai.com/api/docs/guides/speech-to-text).
Oversized ASR inputs are therefore packed as supported lossless FLAC. A full
decode must match every original PCM sample, format and frame before upload;
the original and actual listening inputs are not changed or resampled. The
packing receipt is mechanical integrity evidence, not lexical or sound approval.
Literal empty, clock-valid Whisper timestamp records are preserved in raw
evidence but do not become invented words. All nonempty words must still cover
the exact full ASR text; unknown or malformed clock/word data remains held.
Finite in-range word intervals may overlap. Their reported values and exact text
order are retained, not sorted or retimed. Cut envelopes cover all selected
intervals and continue to reject overlap with retained speech and unsafe margins.

Long-episode planning and complete text comparisons use lossless column encoding
instead of repeating JSON keys per word. The final sound review is independently
audio-only: it receives the actual outgoing encode decoded to WAV, its part
interval and listening instructions, not expected words, speaker identities or
an earlier verdict. Complete navigation, retained-word context and ID bindings
remain saved for the separate text/history audit; they are not sent to the final
listener. No source word, timestamp or acceptance rule is softened to fit.

The OpenAI final listener returns ordinary text in six strictly framed sections
(coverage, verdict, issues, uncertainties and the two audible boundary phrases).
Its audio model supports text output and function calling, but does not promise
Structured Outputs. Parsing preserves each issue/uncertainty block verbatim;
incomplete coverage, unexpected/missing sections, refusal, truncation or an
instruction echoed as speech blocks publication. It neither repairs a malformed
old JSON tool call nor asks a text-only model to invent acoustic approval.
Any saved failed request stays held. Passing short tests is not proof that a
full episode will pass listening, and a valid negative review is not a startup
or configuration failure.

Current [published pricing](https://developers.openai.com/api/docs/pricing) is
$0.10/M input and $0.50/M output tokens for this text model, $32/M audio-input
tokens for audio-1.5, and $0.006/input minute for Whisper. These are list rates,
not a total cost estimate or invoice. Failed primary/fallback calls, cached-token
details, unknown usage, local compute and hosting must not be discarded.
`/sum` now has its own OpenAI text fallback for summary and speaker-text stages,
in addition to its existing OpenAI transcription path. An eligible Gemini failure
latches Google off for that run; subsequent text requests use GPT rather than
retrying the same cap. This does not relax `/shrink`'s fidelity/listening gates.

Install/restart the worker on the existing configured Mac without running the
broad setup script or resetting gateway credentials, sessions or workspace:

```bash
python3 scripts/install-shrink-worker.py
openclaw gateway restart
launchctl list | rg ai.openclaw
openclaw gateway status
openclaw channels status --probe
```

Both command plugins must already be enabled and linked from this checkout. A
new deployment must install/enable `openclaw-plugins/sum-command` and
`openclaw-plugins/shrink-command`; preserve existing gateway/WhatsApp configuration.
Runtime files are not intended for Git: keep `output/shrink/`, `.runtime/`, `.env`
and `~/.openclaw/` out of commits. Never publish transcripts, recordings, raw
responses, upload endpoints or credentials with code.

Local run without WhatsApp delivery (provider calls are real unless mocked):

```bash
python3 scripts/shrink_original.py run 'https://example.com/episode.mp3' \
  --output output/shrink/original-example --tempo 1.08
```

`--local-audio /absolute/recording.wav` supplies an offline input recording but
does not disable provider editing/listening. `--target` explicitly enables sending.
The tests below use mock provider reports and actual local FFmpeg, with no paid
API, SMTP email or WhatsApp messages:

```bash
python3 -m unittest discover -s tests
node --test openclaw-plugins/sum-command/index.test.js \
  openclaw-plugins/shrink-command/index.test.js tests/commands-integration.test.js
```

## Why this replaced synthesis

The fixed eight-case bounded benchmark ended with eight reviewed source-
verification failures and no accepted narration. It did not show that Kokoro
cannot work or that the inputs are acoustically unresolvable. The final tracked
guard was $12.5007865/$20, including uncertainty reserves; it is not an invoice.
The original-voice interview pilot shortened ten minutes to 8:45 with cuts, or
8:06 at 1.08×. Its technical checks passed; full listening acceptance was not
claimed. The production code follows that simpler approach rather than replaying
failed phonetic/schema-ordering or synthetic-voice experiments.

The old `scripts/shrink_audio.py`, speaker/cast helpers and trial outputs may
remain in the working tree as historical research. They are not the command or
LaunchAgent entry point. Old synthetic documentation is historical, not the
current deployment contract. See [deployment validation](shrink-original-deployment.md).
The later OpenAI fallback and short-fixture results are documented in
[OpenAI fallback validation](shrink-openai-validation.md).
