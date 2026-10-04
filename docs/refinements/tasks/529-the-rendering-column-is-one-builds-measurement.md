# The rendering column is one build's measurement, and an engine bump reopens every row of it

**Status:** open, actionable
**Area:** inference
**Origin:** [ADR-0050](../../adr/ADR-0050-live-probe-records.md)
**Verified:** 2026-10-04

Every row of the lineup section's rendering column stands on a sample the reader published, and
every one was drawn on one build. The rule the column states, that a template rendering the thought
already closed honours the switch under a `response_format` and one leaving it open does not, is a
reading of that build's handlers rather than a theorem. Nothing in the tree runs the measurement
that would say when it stops being true. The session that read the nine rows was a scratch shell
loop: start a fixed llama-server on one pick off the mount with neither reasoning flag, wait on
`/health`, run the probe with `CORTEX_THINKING_MODEL` naming the pick and `CORTEX_THINKING_REPEATS=5`,
stop the server, publish the sample, and move to the next pick. It served nine picks in about 26
minutes on the 24 GB card, the three rows the lineup section places at `-ngl 0` among them, and it
is recorded nowhere but in the session that used it. The column has twelve rows since
2026-09-26, when Qwen3.8-27B was read on the same build at the deep tier's argv, which has no
reasoning flag by default, so a re-run draws twelve picks.

Re-running the lineup on a new build and publishing every row through `just switch-tail` is what
closes it. The cheaper half is a `just switch-lineup` recipe holding the loop above. The recipe
drives `docker run` of the fixed image per pick and not the model-host sidecar: that sidecar's
control API takes a logical id and nothing else, its roster is whatever `CORTEX_MODEL_FILE_*`
variables it booted with, it runs only on the card, and its subagent tier's argv has the
reasoning-off pair, where every row of this measurement is served with neither reasoning flag. Every
sample the re-run writes has the context size the server reported, so only `-ngl` is typed by hand.
That loop now exists as `measurements/sitting-2026-10-04/drivers/529sw.sh`, run end to end on CPU.

## The row owed on b11312

The stack's engine is now `b11312-0c1e57098` (History, 2026-10-04), so the column is owed again. Row
`529sw` of the card run of 2026-10-04 draws it: a driver row of 2400 s queued after `607edp` and
before `607sa`. Per pick it runs `/app/llama-server` from the `cortex-model-host` image at `-ngl 99
--ctx-size 8192 --parallel 1 --jinja --cache-ram 0` on `127.0.0.1:8091`, then the probe from the
run's frozen tree at `CORTEX_THINKING_REPEATS=5`, then `scripts/switchtail.py` over every sample
under `measurements/sitting-2026-10-04/529/`. The price is the spacing of the 2026-09-02 samples'
write times, from about a minute for a pick under 5 GB to six for the 31B, about 1980 s for twelve,
plus a fifth for the card's throttled clock. What each result decides, written before the draw:

- **The reader agrees on every pick.** The column holds on `b11312`. The readings record the build
  and the twelve counts, this task waits for the next build, and the recipe stays its open half.
- **The reader exits 1 on a pick**: a closed tail that deliberates, an open tail that holds on all
  five draws, or a tail of another form. The readings record that row beside its `b10680` row, and
  no ADR prose changes until the same pick is drawn again at five draws a cell on `b11312` and on
  the cached `b10680` `:server-cuda` image at the same argv, which splits the build from the day.
  The E4B matters most: its open tail deliberated on 14 of 15 draws over three builds, and 0 of 5
  would be a handler that reads `enable_thinking`, the break this task names. Nothing shipped
  changes either way, since the subagent tier's pair ends the thought whatever the template says.
- **A null result** is a pick with no sample, from a failed load or a control that did not
  deliberate on all five draws: that row stays owed on `b11312`. A skipped or failed row leaves
  all twelve owed, and this task stays actionable.

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
