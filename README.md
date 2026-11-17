# IgorOpenClaw

A private WhatsApp service for one command:

```text
/sum https://example.com/episode
```

It resolves the URL, prefers an existing full transcript, otherwise downloads
and transcribes audio, creates a summary, replies in WhatsApp, and emails the
summary and full transcript. English and Russian source text are retained in
their original language. ASR and summaries can be wrong; this is not independent
fact checking or a guarantee of speaker identity.

The audio-editing command was retired on November 17, 2026. It is no longer
registered, installed by setup, or served by a background worker. Unknown and
retired commands receive `/sum` usage. Historical recordings, jobs, reports, and
private model evidence are preserved, not runnable product features.

## Reliability

Gemini is the default provider. OpenAI provides the configured fallback for
eligible primary failures and invalid completed summary JSON. Both chunk and
final summaries use structured output plus local field/type validation. One
provider switch is allowed; invalid output is discarded rather than repaired
or used as source. Safety blocks, unknown failures, and a failed fallback stop
the request. Full private responses and usage are saved before parsing.

Compressed audio is split by duration as well as size for OpenAI transcription.
Every chunk, including the final tail, must complete before the transcript is
used. Speaker tagging cannot change the original spoken-word sequence.
Short errors go to WhatsApp; detailed tracebacks stay in server logs. No transcript
means no transcript email. Failed email delivery is reported separately.

## Components

- `openclaw-plugins/sum-command/`: deterministic direct-chat command and reply.
- `scripts/transcribe-url.py`: URL, transcript, summary, and email pipeline.
- `scripts/sum_provider.py`: per-run routing, structured data checks, raw evidence.
- `config/openclaw.json.template`: fresh-install gateway configuration.
- `workspace/AGENTS.md`: narrow runtime behavior.
- `scripts/daily-restart.sh`: existing scheduled gateway restart.
- `tests/`: offline provider, audio-chunk, summary, command, and email regressions.

## Configuration

Copy `.env.example` to `.env`, set the provider/SMTP values, and restrict it to
mode 600. Never commit or print credentials. Relevant settings:

| Setting | Purpose |
| --- | --- |
| `GOOGLE_API_KEY` / `GEMINI_API_KEY` | Gemini provider credential. |
| `OPENAI_API_KEY` | OpenAI transcription and summary fallback. |
| `SUM_PROVIDER` | `gemini` (default) or explicit `openai`. |
| `SUM_OPENAI_FALLBACK` | `1` by default; `0` disables implicit fallback. |
| `SUM_OPENAI_TEXT_MODEL` | Existing text model, default `gpt-6-luna`. |
| `SUM_YTDLP_MODULE_DIR` | Optional tested isolated downloader package directory. |
| `SUM_EMAIL_TO` | Transcript destination; legacy `TRANSCRIBE_EMAIL_TO` also works. |
| `GMAIL_USER`, `GMAIL_APP_PASSWORD` | SMTP credentials for sending the package. |

Runtime prerequisites are Node 22+, OpenClaw, Python with `requirements.txt`,
FFmpeg/ffprobe, and yt-dlp for sources requiring download. A working provider key
and SMTP configuration are required for their respective stages. API usage is
not free; saved per-call usage is not itself an invoice or fixed job price.

`scripts/setup.sh` is a fresh-install tool that replaces generated configuration
and runtime workspace files. Do not rerun it to deploy a small update to an
existing server. Use a reviewed, targeted change and an idle gateway restart.
`scripts/uninstall.sh` removes the service; it is not a troubleshooting command.

## Private runtime state

Transcript scratch: `~/.openclaw/state/transcripts/`.
Provider evidence: `~/.openclaw/state/sum-provider-evidence/` (or
`SUM_PROVIDER_EVIDENCE_DIR`). Successful emailed runs remove their own scratch,
not their provider receipts. Historical `output/` evidence is private and ignored
by Git. Retiring audio editing does not erase past recordings or customer results.

## Checks and deployment

```bash
python3 -m unittest discover -s tests
node --test openclaw-plugins/sum-command/index.test.js tests/commands-integration.test.js
bash -n scripts/setup.sh scripts/daily-restart.sh scripts/uninstall.sh
git diff --check
```

Tests mock external sends and model responses; real local FFmpeg checks cover
audio segmentation. Run live provider smoke tests separately, with messaging and
email disabled unless the specific delivery is authorized. Preserve failed raw
responses and distinguish testing fees from production usage.

Before restarting, verify no transcript helper is running. Restart only the
gateway LaunchAgent, then check current WhatsApp connectivity and actual request
logs. Do not reset authentication, recreate sessions, change billing, or use the
daily restart's notification as a connectivity test.

The October output-limit repair is documented in
[the recovery notes](docs/sum-output-limit-recovery.md). Earlier audio-editing
documents under `docs/` are historical and do not describe active commands.
