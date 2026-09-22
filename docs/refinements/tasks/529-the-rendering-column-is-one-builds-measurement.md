# The rendering column is one build's measurement, and an engine bump reopens every row of it

**Status:** open, waiting for its trigger
**Area:** inference
**Trigger:** an engine bump under this stack, meaning the cached image compose starts for the
`server-cuda` tag (the model-host base in `brain/Dockerfile.modelhost`) or the `server` tag (both
subagents overrides) reporting a llama.cpp build other than b10680 on the GPU runbook's
`docker image inspect` label command. Nothing fixes a digest, so a pull is the bump. The column is a
property of one build's chat handlers, and a handler that started reading `enable_thinking` in its
reasoning rule would break it with nothing reporting the break.
**Origin:** [ADR-0050](../../adr/ADR-0050-live-probe-records.md)
**Verified:** 2026-09-19

Every row of the lineup section's rendering column stands on a sample the reader published, and
every one was drawn on one build. The rule the column states, that a template rendering the thought
already closed honours the switch under a `response_format` and one leaving it open does not, is a
reading of that build's handlers rather than a theorem. Nothing in the tree runs the measurement
that would say when it stops being true. The session that read the nine rows was a scratch shell
loop: start a fixed llama-server on one pick off the mount with neither reasoning flag, wait on
`/health`, run the probe with `CORTEX_THINKING_MODEL` naming the pick and `CORTEX_THINKING_REPEATS=5`,
stop the server, publish the sample, and move to the next pick. It served nine picks in about 26
minutes on the 24 GB card, the three rows the lineup section places at `-ngl 0` among them, and it
is recorded nowhere but in the session that used it.

Re-running the lineup on a new build and publishing every row through `just switch-tail` is what
closes it. The cheaper half is a `just switch-lineup` recipe holding the loop above. The recipe
drives `docker run` of the fixed image per pick and not the model-host sidecar: that sidecar's
control API takes a logical id and nothing else, its roster is whatever `CORTEX_MODEL_FILE_*`
variables it booted with, it runs only on the card, and its subagent tier's argv has the
reasoning-off pair, where every row of this measurement is served with neither reasoning flag. Every
sample the re-run writes has the context size the server reported, so only `-ngl` is typed by hand.

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
