# Original-audio deployment and regression record

Date: October 9, 2026 (America/New_York).

## Scope

The user authorized finishing the original-audio pivot, testing `/sum`, pushing
the implementation to GitHub, documenting the work and restarting the server.
This does not restart the completed benchmark or reset its cost ledger.

Changed production entry point: `/shrink` queues `scripts/shrink_original.py`.
The installer keeps `ai.openclaw.shrink-worker` but changes its program to that
new worker. Its queue is isolated from `~/.openclaw/state/shrink`. The active
gateway already links both plugins from this repository, so there is no need
to replace gateway configuration or run the broad setup/reset script.

The existing `/sum` implementation is included unchanged as a deployment
dependency because it was present locally but not tracked in the repository's
current commit. It retains its existing transcript helper, summary, email
destination handling and bounded empty-output retry behavior. Its source hash
before and after this work is:

```text
openclaw-plugins/sum-command/index.js
32928b3aee9968951f0446724d450ae29d0b51bef373daa92e541842c0b3940a

scripts/transcribe-url.py (existing local file, not edited in this change)
c3c0b6b3968cc6effa2da503d42f0b4be36bad9a3034c6920a9cf91baee89fd5
```

The shared transcript helper already had uncommitted downloader/email changes
before this request. They are preserved, not attributed to this pivot or staged
with it. The original-audio worker uses only the helper's existing media resolver
and acquisition interfaces, also available in the committed helper. Unrelated
configuration, workspace cleanups and deletions remain outside this commit.

## Tests and limitations

Before changes: 88 Python tests and 13 JavaScript command tests passed.

New tests cover exact schema types, uncertain/issue-bearing report rejection,
all-cut/protected-ID coverage, source annotations, protected and overlapping
speech, neighboring-word margins, pause smoothing, reduction ceiling, source-
only chronological rendering, complete-stage hash binding, interrupted/failed
attempt latches, quota/network single attempts, legacy-job isolation, delivery
preflight, original-input preservation and end-to-end cached reuse.

FFmpeg tests perform real local rendering/encoding/decoding and byte-check
retained PCM outside declared crossfades. Their tones and mocked model reports
test pipeline mechanics, not speech fidelity or model quality. Integration tests
register both plugins in either order and confirm `/sum` still invokes
`transcribe-url.py run --email-to ... --json`, not the new worker. No real SMTP
email, WhatsApp message, media download or paid model request is part of testing.

Final local validation: **108 Python tests and 17 JavaScript command/integration
tests passed**, including 20 new original-audio tests. Syntax compilation and
`git diff --check` also passed. The unchanged `/sum` plugin hash was checked
again after programming; the helper and its existing tests were not edited.

A clean `git archive` of implementation commit `8920a6b`, extracted into a fresh
temporary directory, independently passed **31 committed Python tests and the
same 17 command/integration tests**. The larger working-tree count includes
uncommitted historical research tests; it is not presented as the release's
committed test count. The clean check confirms no dependency on those files.

The new renderer also reproduced the saved real interview pilot's eight retained
intervals from the original recording: cut-only 524.884 seconds, 1.08× output
486.4472916667 seconds. It verified the complete retained PCM outside crossfades
and left the source unchanged. This was a temporary local test with no provider
requests or publication, not a new semantic/audio acceptance claim.

## Restart verification

At approximately 10:28 AM America/New_York on October 9:

- Both legacy and new queues were empty before switching the worker.
- `python3 scripts/install-shrink-worker.py` installed the new original-audio
  program under the existing LaunchAgent label. New worker PID: 43724.
- `openclaw gateway restart` replaced gateway PID 55907 with PID 43797.
- Gateway status: running on loopback port 18789, connectivity probe OK.
- WhatsApp probe: enabled, configured, linked, running, connected, healthy.
- Both `sum-command` and `shrink-command` were loaded. The latter's inspected
  description explicitly says original-voice editing and no speech synthesis.
- No credentials, provider configuration, channel allowlist, cron schedule,
  sessions or workspace state were reset. The broad setup script was not run.
- No paid API request, SMTP email, WhatsApp test message or benchmark retry was
  initiated. The benchmark guard remains $12.5007865 across 210 incremental rows;
  its heartbeat remains paused. Local compute cost is unknown.

PID values are historical observations, not future health promises. A successful
probe is service health, not end-to-end validation of an untested future episode.
The next real `/shrink` request still has to pass its own automatic review gates.

## Git scope

The release contains the new worker, editorial contract, routing/plugin files,
worker installer, dependencies, regression tests and these documentation files.
The existing `/sum` plugin is included as an unchanged runtime dependency. Only
the new current-workflow notice is staged from the already-modified README.
Other pre-existing README edits, setup/config/workspace changes, deletions,
untracked historical synthetic research and all private outputs are excluded.
No branch force-push, repository reset or deletion is required.
