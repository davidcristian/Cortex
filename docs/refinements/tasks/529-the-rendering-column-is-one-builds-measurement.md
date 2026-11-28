# The rendering column is one build's measurement, and an engine bump reopens every row of it

**Status:** open, waiting for its trigger
**Area:** inference
**Trigger:** an engine bump under this stack, meaning the GPU runbook's `docker image inspect`
label command reporting a llama.cpp build other than b12375 for `cortex-model-host` (the three GPU
tiers) or other than b10680 for the cached `server` tag (both CPU subagent overrides). Nothing fixes
a digest, so a pull or a rebuild is the bump.
**Origin:** [ADR-0050](../../adr/ADR-0050-live-probe-records.md)
**Verified:** 2026-11-28

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

Drawn 2026-10-07 on `b11429 d81235049`, image `sha256:246f5bf127e4`, under the same three rules.
The E4B row was read from its `-ngl 0` sample, as on `b11312`, and its `-ngl 99` sample was
recorded and decided nothing. Eleven picks repeated their `b11312` rows. The E4B was a null at both
placements, its plain control deliberating on 4 and 3 of 5. The 20 draw row then had three rules,
written before its draw: all 20 on `b11429` reads the row; all 20 on `b10680` and 16 or fewer on
`b11429` means the build lowered the plain control's rate, so its plain cell is unmeasured by this
prompt, the row is read from its constrained cells and a task is filed for a question the control
deliberates on every time; any other result is a null. It read 16 of 20 on `b11429` and 17 of 20 on
the cached `b10680` image, a null, so the bill question does not make the E4B deliberate on every
draw on either build. The probe now sends the E4B's file a knights and knaves question, chosen by a
screen and a replication written down before their draws
([ADR-0050](../../adr/ADR-0050-live-probe-records.md) decision 1). Its row's rules, also written
before the draw: both controls at 20 of 20 with the reader agreeing reads the row; a reader exit of
1 records the row beside its `b11312` row and draws it again on the cached `b10680` image; any other
result is a null. Drawn with it at 20 draws a cell, both controls deliberated on 20 of 20 and the
reader agreed, so all twelve rows are read on `b11429`
([thinking-switch readings](../../readings/thinking-switch.md#the-lineups-switched-tails)).

## The column on b11552

Drawn 2026-10-16 on `b11552 23b0202a1`, image `sha256:c3f02610f5af`, by the recipe's loop from a
`git archive` copy, with the main tree's brain venv and the copy's sources first on `PYTHONPATH`,
the E4B at `-ngl 0` on CPU cores 12 to 23 with its own question. Every probe exited 0, the reader
agreed on all twelve samples and every pick repeated its `b11429` row, so the column held on
`b11552`. Samples under `measurements/sitting-2026-10-16/529/`.

## The column on b11913

The model host image was rebuilt on 2026-10-28 and reads `b11913 7aca0d2ea`, image
`sha256:2f5f67ffb095`. `just switch-lineup --cpuset 12-23` draws the twelve picks on it from the
main tree, with the stack's model host container stopped so the card is free: the E4B at `-ngl 0`
on CPU cores 12 to 23 with its knights and knaves question, the rest at `-ngl 99`, five draws a
cell. The E4B row is read from that `-ngl 0` sample alone, as on `b11552`, and no `-ngl 99` draw
stands in for it. What each result decides, written before the draw:

- **Every probe exits 0, the reader agrees on every pick, and every tail and switched count repeats
  its `b11552` row.** The column holds on `b11913`. The readings record the build and the twelve
  rows, and this task waits for the next build.
- **The reader exits 1 on a pick, or it agrees on a pick whose tail or a switched count differs
  from its `b11552` row.** The readings record that row beside its `b11552` row, and no ADR prose
  changes until the same pick is drawn again at five draws a cell on `b11913` and on the cached
  `b10680` `:server-cuda` image at the same argv. That row stays owed and the task stays actionable.
- **A null** is a pick with no sample, from a failed load, or a control that did not deliberate on
  all five draws: that row stays owed on `b11913`, and the task stays actionable.

**Drawn 2026-10-28**, the recipe exiting 0, every probe exiting 0 and the reader agreeing on all
twelve samples ([thinking-switch readings](../../readings/thinking-switch.md#the-lineups-switched-tails)).
Every control deliberated on 5 of 5, and every pick rendered both prompts byte for byte as on
`b11552` and repeated its four counts, so under the first rule the column holds on `b11913` and this
task waits for the next build. Samples under `measurements/sitting-2026-10-28/529/`.

## The column on b12375

The model host image reads `b12375 9d25e0014`, image `sha256:42102cf3b896`. The cached
`:server-cuda` tag now reads `b12169 3ed7284f2`, and `b10680` is cached only as the CPU `:server`
image. Every file the recipe names changed on the mount on 2026-11-16, the gemma ones with new chat
templates ([R-1238](1238-the-lineups-readings-were-drawn-on-files-the-mount-no-longer-holds.md)),
so a row that moves on `b12375` cannot say whether the build or the file moved it. Two rows are not
drawn. The Qwen3.6-27B file is gone and `scripts/switchlineup.py` no longer names it, so that row
stays on `b11913`. The gemma-4-31B file held whole needed 18,621 MiB of the card at 6K of context
with a 16-bit cache in the baseline's fit check of 2026-11-17, over the 18,177 MiB a model may hold
beside the user's apps ([model baseline](../../readings/model-baseline.md)), so the recipe's `-ngl
99 --ctx-size 8192` is not loaded for it and that row stays owed
([R-1383](1383-the-lineup-recipe-serves-gemma-4-31b-whole-and-the-card-cannot-hold-it.md)).

`just switch-lineup --cpuset 12-23` with one `--only` per pick draws the other ten from the main
tree with no model host running: the E4B at `-ngl 0` on CPU cores 12 to 23 with its knights and
knaves question, the rest at `-ngl 99`, five draws a cell. A card watch removes the server when the
card holds more than 18,177 MiB above the other apps' reading at the start. What each result
decides, written before the draw:

- **Every probe exits 0, the reader agrees on every pick, and every tail and switched count repeats
  its `b11913` row.** The ten rows hold on `b12375` on the files the mount holds. The readings record
  the build, the files and the ten rows, R-1238's switched tails line closes for those ten entries,
  and this task waits for the next build with the gemma-4-31B row owed.
- **The reader exits 1 on a pick, or it agrees on a pick whose tail or a switched count differs from
  its `b11913` row.** The readings record that row beside its `b11913` row, and no ADR prose changes
  until the same pick is drawn again at five draws a cell on `b12375` and on the cached `b12169`
  `:server-cuda` image at the same argv. That row stays owed, R-1238's line stays open for that
  entry, and the task stays actionable.
- **A null** is a pick with no sample, from a failed load or the card watch, or a control that did
  not deliberate on all five draws, which the reader refuses: that row stays owed on `b12375`, and
  the task stays actionable.

**Drawn 2026-11-28**, the recipe exiting 0, every probe exiting 0 and the reader agreeing on all ten
samples ([thinking-switch readings](../../readings/thinking-switch.md#the-lineups-switched-tails)).
Every control deliberated on 5 of 5, and every pick rendered both prompts byte for byte as on
`b11913` and repeated its four counts, so under the first rule the ten rows hold on `b12375` on the
files the mount holds, R-1238's switched tails line closes for those ten entries, and this task
waits for the next build with the gemma-4-31B row owed through R-1383. The card watch removed
nothing, the largest peak being 16,175 MiB above the other apps' reading. Samples under
`~/.cache/cortex-run/2026-11-28/s1/529/`.

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
- 2026-10-28: the trigger fired and the column was drawn on the new build. The runbook's label
  command reads `b11913 7aca0d2ea` on `cortex-model-host`, an image built on 2026-10-28 under the
  compose project `cortexn9`, while the cached `:server-cuda` and `:server` tags still read `b10680
  d7bd3bfca`. Drawn with `just switch-lineup`, the E4B at `-ngl 0` on CPU cores 12 to 23, every
  probe exited 0 and the reader agreed on all twelve samples, each repeating its `b11552` row, so
  all twelve rows hold on `b11913` and the task waits for the next build again.
- 2026-11-27: the trigger fired. The runbook's label command reads `b12375 9d25e0014` on
  `cortex-model-host`, while the cached `:server` tag still reads `b10680`, so all twelve rows are
  owed on `b12375` through `just switch-lineup`, whose draw also gives
  [R-1238](1238-the-lineups-readings-were-drawn-on-files-the-mount-no-longer-holds.md) its switched
  tails on the files the mount holds. The trigger line is gone and the task is actionable.
- 2026-11-28: drawn on `b12375` with `just switch-lineup`. The ten picks drawn repeat their `b11913`
  rows byte for byte, so the task waits for the next build. The Qwen3.6-27B file is gone from the
  mount, and the gemma-4-31B pick was not loaded, since its file does not fit the card whole at the
  recipe's argv: filed as
  [R-1383](1383-the-lineup-recipe-serves-gemma-4-31b-whole-and-the-card-cannot-hold-it.md).
