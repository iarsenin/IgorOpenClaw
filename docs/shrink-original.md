# /shrink: edit the original recording

The production `/shrink <public-media-URL>` command now makes a chronological
listening edit using the original voices. It does not rewrite and resynthesize
the episode. `/sum <URL>` remains the transcript, summary and email command.

The worker downloads the recording, makes a 24kHz mono PCM navigation master,
and obtains timestamped ASR in complete, contiguous ten-minute blocks. ASR is
fallible navigation; it is not word truth or a precise acoustic clock. The
original download, PCM, ASR, proposed cuts, reports and usage remain private.

## Editing and review

1. One Pro request reads the complete navigation and proposes explained word-ID
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
failed, interrupted, malformed or changed stages stay held. There is no provider
fallback, schema-repair retry, blind regeneration or hourly retry scheduler.
HTTP 429 latches further provider requests immediately; only upload cleanup is
allowed. Structured provider wait advice is recorded as supplied, never invented.
The worker returns a failure notice and does not publish rejected audio.

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
| `SHRINK_FIDELITY_REVIEW_MODEL` | `gemini-3.5-flash` |
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
does not disable Gemini editing/listening. `--target` explicitly enables sending.
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
