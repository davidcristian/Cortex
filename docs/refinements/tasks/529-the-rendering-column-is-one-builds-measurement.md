# The rendering column is one build's measurement, and an engine bump reopens every row of it

**Status:** open, waiting for its trigger
**Area:** inference
**Trigger:** an engine bump under this stack, meaning the GPU runbook's `docker image inspect`
label command reporting a llama.cpp build other than b11552 for `cortex-model-host` (the three GPU
tiers) or other than b10680 for the cached `server` tag (both CPU subagent overrides). Nothing fixes
a digest, so a pull or a rebuild is the bump.
**Origin:** [ADR-0050](../../adr/ADR-0050-live-probe-records.md)
**Verified:** 2026-10-16

Every row of the lineup section's rendering column stands on a sample the reader published, and
every one was drawn on one build. The rule the column states, that a template rendering the thought
already closed honours the switch under a `response_format` and one leaving it open does not, is a
reading of that build's handlers rather than a theorem, so every engine bump owes the column
again. The column has twelve rows since 2026-09-26, when Qwen3.8-27B was read at the deep tier's
argv, which has no reasoning flag by default.

`just switch-lineup` (`scripts/switchlineup.py`, since 2026-10-07) draws the column on one engine
image: one llama-server per pick with neither reasoning flag, the E4B at `-ngl 0` and the rest at
`-ngl 99`, the probe at five draws a cell, and every sample through `switchtail.py`. It drives
`docker run` of the fixed image per pick and not the model-host sidecar: that sidecar's control API
takes a logical id and nothing else, its roster is whatever `CORTEX_MODEL_FILE_*` variables it
booted with, and its subagent tier's argv has the reasoning-off pair, where every row of this
measurement is served with neither reasoning flag. When the trigger fires, run the recipe on the new
build and record the twelve rows in the readings under the rules below.

## The column on b11312

Drawn on 2026-10-04 by row `529sw` of that day's card run, with
`measurements/sitting-2026-10-04/drivers/529sw.sh`: per pick `/app/llama-server` from
`cortex-model-host` at `-ngl 99 --ctx-size 8192 --parallel 1 --jinja --cache-ram 0`, the probe at
five draws a cell and `scripts/switchtail.py` over every sample, under the three rules the sections
below repeat. Eleven rows held. The E4B was a null twice at `-ngl 99`, its plain control
deliberating on 4 and 3 of 5, and read its `b10680` row on CPU cores 12 to 23 at `-ngl 0`, so all
twelve rows held on `b11312`
([thinking-switch readings](../../readings/thinking-switch.md#the-lineups-switched-tails)).

## The column on b11429

The model host image was rebuilt on 2026-10-06 and reads `b11429 d81235049`, image
`sha256:246f5bf127e4`; the `b11312` image is no longer cached. Row `529sw` of the card run of
2026-10-07 draws the twelve picks at `-ngl 99` with the 2026-10-04 driver and argv, then row
`529cpu` draws the E4B at `-ngl 0` on CPU cores 12 to 23. The E4B row is read from `529cpu`, as on
`b11312`; its `-ngl 99` sample is recorded and decides nothing. What each result decides, written
before the draw:

- **Every probe exits 0 and the reader agrees on every pick.** The column holds on `b11429`. The
  readings record the build and the twelve rows, and this task waits for the next build.
- **The reader exits 1 on a pick.** The readings record that row beside its `b11312` row, and no
  ADR prose changes until the same pick is drawn again at five draws a cell on `b11429` and on the
  cached `b10680` `:server-cuda` image at the same argv. That row stays owed and the task stays
  actionable.
- **A null** is a pick with no sample, from a failed load, or a control that did not deliberate on
  all five draws: that row stays owed on `b11429`, and the task stays actionable.

**Drawn 2026-10-07**, both rows exit 0 and the reader exiting 0 on all thirteen samples
([thinking-switch readings](../../readings/thinking-switch.md#the-lineups-switched-tails)). Eleven
picks agree with their `b11312` rows, so under the first rule the column holds on `b11429` for
them. The E4B is a null under the third at both placements: its plain control deliberated on 4 of
5 at `-ngl 99` and on 3 of 5 at `-ngl 0`, so its row stays owed on `b11429`. Nothing shipped
changes, and the task stays actionable.

**The next row, written before its draw.** The E4B's plain control has failed in four of five runs
on `b11312` and `b11429`, at both placements, and fired on all five in both `b10680` runs. Five
draws cannot tell a lower rate from chance. The row draws the E4B at `-ngl 99` at 20 draws a cell,
a copy of the 2026-10-07 driver with `CORTEX_THINKING_REPEATS=20`, on `cortex-model-host` and on
the cached `b10680` `:server-cuda` image at the same argv: about 10 minutes on the card.

- **The control deliberates on all 20 on `b11429`.** The probe reads the E4B row on `b11429`
  under the rules above, and all twelve rows are read on it.
- **It deliberates on all 20 on `b10680` and on 16 or fewer on `b11429`.** The build lowered the
  plain control's rate on this prompt. The readings record it, the E4B's plain cell is unmeasured
  by this prompt on `b11429`, its row is read from its constrained cells, which the reader judges,
  and a task is filed for a question the E4B's control deliberates on every time.
- **Any other result** is a null, and the row stays owed.

**Drawn 2026-10-07**, both rows exit 0 and the reader exiting 0 on both samples. The plain control
deliberated on 16 of 20 on `b11429` and on 17 of 20 on `b10680`, so neither the first rule nor the
second applies: under the third this is a null, and the E4B row stays owed on `b11429`. Its
constrained cells read control 20 of 20 on both images, switch 19 of 20 on `b11429` and 18 of 20 on
`b10680`, and its plain switch 0 of 20 on both. The two `b10680` runs that fired on five of five
were draws at a rate below one, so the build did not lower it: this question does not make the E4B
deliberate on every draw on either build. The probe now sends the E4B's file a question of its own,
chosen by a screen and a replication written down before their draws
([ADR-0050](../../adr/ADR-0050-live-probe-records.md) decision 1, thinking-switch readings), and
every other file the bill question, so the eleven rows read above stand. Nothing shipped changes.

**The next row, written before its draw.** The row draws the E4B with its own question at `-ngl 99`
and 20 draws a cell on `cortex-model-host`, on the build that image then reads, with
`measurements/sitting-2026-10-07b/drivers/529x20.sh`: `just switch-lineup` fixes five draws a cell
and serves the E4B at `-ngl 0`.

- **Both controls deliberate on all 20 and the reader agrees.** The E4B row is read on that build.
  On `b11429` all twelve rows are then read, and this task waits for the next build.
- **The reader exits 1.** The readings record that row beside its `b11312` row, it stays owed, and
  it is drawn again on the cached `b10680` `:server-cuda` image at the same argv.
- **Any other result** is a null, and the row stays owed.

**Drawn 2026-10-07**, exit 0, the probe sending the E4B's file its knights and knaves question.
Both controls deliberated on 20 of 20, the plain switch on 0 of 20 and the constrained switch on 20
of 20, and the reader agreed: an open tail that does nothing under a schema, the E4B's row as on
every earlier build. Under the first rule the E4B row is read on `b11429`, all twelve rows are read
on it, and this task waits for the next build with the recipe as its open half. The same plain
control read 20 of 20 at `-ngl 0` on CPU cores 12 to 23, where the recipe serves the E4B, so the
recipe needs no change. Samples under `measurements/sitting-2026-10-07c/529e4b20q/`, from the
`529x20.sh` copied there.

## The column on b11552

The model host image was rebuilt on 2026-10-12 and reads `b11552 23b0202a1`, image
`sha256:c3f02610f5af`. The recipe's loop, `switchlineup.py --cpuset 12-23`, draws the twelve
picks on it from a `git archive` copy of HEAD, the E4B at `-ngl 0` on CPU cores 12 to 23 with its
own question and the rest at `-ngl 99`, five draws a cell. What each result decides, written
before the draw:

- **Every probe exits 0 and the reader agrees on every pick.** The column holds on `b11552`. The
  readings record the build and the twelve rows, and this task waits for the next build.
- **The reader exits 1 on a pick.** The readings record that row beside its `b11429` row, and no
  ADR prose changes until the same pick is drawn again at five draws a cell on `b11552` and on the
  cached `b10680` `:server-cuda` image at the same argv. That row stays owed and the task stays
  actionable.
- **A null** is a pick with no sample, from a failed load, or a control that did not deliberate on
  all five draws: that row stays owed on `b11552`, and the task stays actionable.

**Drawn 2026-10-16**, the row exiting 0, every probe exiting 0 and the reader agreeing on all twelve
samples ([thinking-switch readings](../../readings/thinking-switch.md#the-lineups-switched-tails)).
Every control deliberated on 5 of 5 and every pick repeats its `b11429` row, tail and result alike,
the E4B's included, so under the first rule the column holds on `b11552` and this task waits for
the next build. The probe ran on the main tree's brain venv with the copy's sources first on
`PYTHONPATH`, as on every earlier run. Samples under `measurements/sitting-2026-10-16/529/`.

## History

- 2026-09-02: opened by the close of
  [R-510](510-nine-rows-of-the-rendering-column-are-hand-read.md), whose close recorded the
  measurement and the build it read (thinking-switch readings).
- 2026-09-02: the sample now names the engine build and the model file the server reported on
  `GET /props`, by the close of
  [R-528](528-a-switch-sample-names-the-model-the-operator-typed-and-no-engine-build.md), so the
  next run copies the record's artifact and build columns off each report.
- 2026-09-04: checked again and still open. Both cached engine images report `build 10680, commit
  d7bd3bfca` on `llama-server --version`, the build every row was read on. Nothing in the tree fixes
  a digest, though, and both tags have already moved past those images, `server-cuda` from
  `sha256:952424b09abc` to `sha256:8557e3d273aa` and `server` from `sha256:db057ec90de0` to
  `sha256:3d05996b4956`, read from the registry without pulling. With no `pull_policy` set anywhere,
  compose keeps the cached images here and a machine holding none already starts a different build.
  ADR-0005 decision 8 says how a reader establishes which build a tag names.
- 2026-09-09: the trigger has still not fired, and both readings behind that answer have moved. The
  cached images are the same two digests and both still report `build 10680, commit d7bd3bfca`, but
  the tags now resolve to `sha256:a292d888ae50` and `sha256:8cbb24c55af0`. The other reading is a
  trap for whoever answers this next: the built `cortex-model-host` image on this host reports
  `build 10615, commit f280b2698`, older than the base tag it was built from, because it is two
  weeks old and nothing rebuilds it on its own. It is not a bump. `just up-gpu` passes `--build`,
  and the runtime stage of
  [brain/Dockerfile.modelhost](../../../brain/Dockerfile.modelhost) is the base image itself with a
  venv copied in, so the recipe starts whatever the cached base has. Read the base, not the image
  built from it.
- 2026-09-13: the trigger has still not fired. `docker images` reports the same two cached digests,
  so the stack still starts the build every row was read on. The registry was not asked again: what
  the tags resolve to moves without this stack moving.
- 2026-09-19: the trigger has still not fired, and the trigger and the remedy were both repaired.
  Both cached images are the same digests, and the runbook's label command reports `b10680
  d7bd3bfca` on each. The trigger named a digest fixed by the overrides, which the 2026-09-04
  reading had already shown nothing does, so it now names the reading that fires it. The remedy
  named the model-host sidecar as the obvious driver for a recipe, and it cannot be one: its API
  takes a logical id with no path, argv or layer count (`cortex_model_manager/api.py`), and its
  subagent tier starts with `_SUBAGENT_TAIL` in `cortex_model_manager/config.py`, whose reasoning-off
  pair is exactly what these servers must not have. The body's other claims hold: nine rows in about
  26 minutes, eleven in the column, three owed their `-ngl 0` placement. The sample's `n_ctx` field,
  added 2026-09-15, is now named in the remedy.
- 2026-09-30: the trigger has still not fired. `docker images` lists the same two cached digests,
  `sha256:952424b09abc` for `server-cuda` and `sha256:db057ec90de0` for `server`, and the runbook's
  label command reads `b10680 d7bd3bfca` on each. The column grew to twelve rows on 2026-09-26, the
  Qwen3.8-27B row read on the same build, and the body now says so. The remedy still stands:
  `_SUBAGENT_TAIL` still has the reasoning-off pair, and the cortex and deep tiers still start with
  no reasoning flag unless a budget is set.
- 2026-10-04: the trigger fired. The GPU runbook's label command now reads `cortex-model-host`,
  which reports `b11312 0c1e57098` and was built 2026-10-02, while the cached `:server-cuda` and
  `:server` tags still read `b10680 d7bd3bfca`. So the stack's three GPU tiers start `b11312`, and
  only the CPU subagent overrides still start `b10680`. That also corrects the 2026-09-09 line: a
  `--build` did not take the cached base, and the inferred cause is that the build resolved the
  tag against the registry. The trigger line is gone and the task is actionable, with row `529sw`
  queued (section above). The driver's CPU run on the Qwen3.5-0.8B pick already read one row on
  `b11312`, recorded in the thinking-switch readings.
- 2026-10-04: `529sw` drawn and read: eleven picks hold on `b11312`, the reader agreeing on all
  twelve, and the E4B is a null twice over, its plain control deliberating on 4 and 3 of 5. Its row
  stays owed, with a row at `-ngl 0` on CPU cores 12 to 23 written next.
- 2026-10-04: the E4B row drawn on `b11312` at `-ngl 0`, its control firing on 5 of 5 and its row
  matching `b10680`, so all twelve rows hold on `b11312`. The task waits for the next build again,
  with the trigger naming both builds the stack starts.
- 2026-10-07: the trigger fired again. The runbook's label command reads `b11429 d81235049` on
  `cortex-model-host`, an image built on 2026-10-06 under the compose project `cortexs7`, while the
  cached `:server-cuda` and `:server` tags still read `b10680 d7bd3bfca`. So the three GPU tiers
  start `b11429`, and all twelve rows are owed on it under the rules above, the E4B at `-ngl 0` as
  on 2026-10-04. The registry's `:server-cuda` tag names `b11434` today, so a rebuild before the
  draw moves the engine again: read the label first and draw on the image as it stands. The
  trigger line is gone and the task is actionable.
- 2026-10-07: drawn on `b11429`. Eleven rows hold, the reader agreeing on all thirteen samples;
  the E4B is a null at both placements, its plain control deliberating on 4 and 3 of 5, so its row
  stays owed, with the next row written above. The recipe half is done: `just switch-lineup`
  (`scripts/switchlineup.py`) holds the loop, run live on one pick on `b11429`.
- 2026-10-07: the E4B drawn at 20 draws a cell on `b11429` and on the cached `b10680` image, its
  plain control deliberating on 16 and 17 of 20: a null under the third rule, so its row stays
  owed until the probe sends the E4B a question its control deliberates on every time, with the
  next row above.
- 2026-10-07: the probe now sends the E4B's file a knights and knaves question, whose plain control
  deliberated on 20 of 20 in a screen of four candidates and again in a separate run of the probe
  (thinking-switch readings). The E4B row drawn with it on `b11429` at 20 draws a cell read both
  controls 20 of 20 and the reader agreed, so all twelve rows are read on `b11429` and the task
  waits for the next build, with the trigger naming both builds the stack starts.
- 2026-10-16: the trigger fired and the column was drawn on the new build. The runbook's label
  command reads `b11552 23b0202a1` on `cortex-model-host`, an image built on 2026-10-12, while the
  cached `:server-cuda` and `:server` tags still read `b10680 d7bd3bfca`, and the registry's two
  tags name `b11669`. Drawn with the recipe's loop, the E4B at `-ngl 0` on CPU cores 12 to 23, every
  probe exited 0 and the reader agreed on all twelve samples, each repeating its `b11429` row, so
  all twelve rows hold on `b11552` and the task waits for the next build again, with the trigger
  naming both builds the stack starts.
