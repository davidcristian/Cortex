# The rendering column is one build's sweep, and an engine bump reopens every row of it

**Status:** open, fix when it bites
**Area:** inference
**Trigger:** an engine bump under this stack, meaning the cached image compose starts for the
`server-cuda` tag (the model-host base in `brain/Dockerfile.modelhost`) or the `server` tag (both
subagents overrides) reporting a llama.cpp build other than b10680 on the GPU runbook's
`docker image inspect` label command. Nothing pins a digest, so a pull is the bump. The column is a
property of one build's chat handlers, and a handler that started gating its reasoning rule on
`enable_thinking` would break it with nothing reporting the break.
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)
**Verified:** 2026-09-19

Opened 2026-09-02 by the close of
[R-510](510-nine-rows-of-the-rendering-column-are-hand-read.md), which read every row of the
lineup section's rendering column back through `just switch-tail` on `b10680-d7bd3bfca`.

Every row of that column now stands on a sample the reader published, and every one of them was
drawn on one build. The rule the column carries, that a template rendering the thought already
closed holds the switch under a `response_format` and one leaving it open does not, is a reading
of that build's handlers rather than a theorem, which is what the reader exists to say the day it
stops being true. Nothing in the tree runs the sweep that would say so. The sitting that read the
nine rows was a scratch shell loop: start a pinned llama-server on one pick off the mount with
neither reasoning flag, wait on `/health`, run the probe with `CORTEX_THINKING_MODEL` naming the
pick and `CORTEX_THINKING_REPEATS=5`, stop the server, publish the sample, and move to the next
pick. It served nine picks in about 26 minutes on the 24 GB card, the three rows the lineup
section places at `-ngl 0` among them, after the CPU image had decoded the E2B at under two tokens
a second on the night; it is recorded nowhere but in the addendum that used it.

**Why it was left.** The sweep is a sitting and not a gate: it needs the card, the mount and
about an hour, and the rule it re-reads carries no shipped behaviour, since every bound that pairs
a cap with the switch also sends `trace_tokens=0` where the engine reads it. A committed driver
that serves eleven picks one at a time is a recipe with a lifecycle of its own, and it was not
worth writing against a build that had just been read.

**What would close it, when it bites.** Re-run the lineup on the new build and publish every row
through `just switch-tail`, then rewrite the column where a row moved. The cheaper half is a
`just switch-lineup` recipe holding the loop above, so the next bump re-reads the column in one
command rather than from a scratch file. The recipe drives `docker run` of the pinned image per
pick, as the loop did, and not the model-host sidecar: that sidecar's control API takes a logical
id and nothing else, its roster is whatever `CORTEX_MODEL_FILE_*` variables it booted with, it
runs only on the card, and its subagent tier's argv carries the reasoning-off pair, where every
row of this sweep is served with neither reasoning flag. The three rows the lineup section places
at `-ngl 0` are owed that placement in the re-run, on the `server` image, since the sitting that
opened this read them on the card. Every sample the re-run writes carries the context size the
server reported, so the `-c` half of each row's placement is read off the server and only `-ngl`
is typed by hand.

## Trail

- 2026-09-02: opened by the close of
  [R-510](510-nine-rows-of-the-rendering-column-are-hand-read.md), whose ADR-0005 lineup-tails
  addendum records the sweep and the build it read.

- 2026-09-02: the sample the sweep publishes now names the engine build and the model file the
  server reported on `GET /props`, by the close of
  [R-528](528-a-switch-sample-names-the-model-the-operator-typed-and-no-engine-build.md), so the
  next sweep copies the record's artifact and build columns off each report rather than off the
  loop's notes.

- 2026-09-04: re-derived and still open. The trigger has not fired here: both cached engine images
  report `build 10680, commit d7bd3bfca` on `llama-server --version`, the build every row of the
  column was read on. Nothing in the tree pins a digest, though, and both tags have already moved
  past those images, `server-cuda` from `sha256:952424b09abc` to `sha256:8557e3d273aa` and `server`
  from `sha256:db057ec90de0` to `sha256:3d05996b4956`, read from the registry without pulling. With
  no `pull_policy` set anywhere, compose keeps the cached images here and a machine holding none
  already starts a different build. The ADR-0005 engine-tag addendum records the comparison and the
  two commands that redo it.

- 2026-09-09: the trigger has still not fired, and the two readings behind that answer have both
  moved. The cached images are the same two digests, `sha256:952424b09abc` for `server-cuda` and
  `sha256:db057ec90de0` for `server`, and both still report `build 10680, commit d7bd3bfca`, but
  the tags now resolve to `sha256:a292d888ae50` and `sha256:8cbb24c55af0`, a second move past the
  pair the bullet above read. The other reading is a trap for whoever answers this next: the built
  `cortex-model-host` image on this host reports `build 10615, commit f280b2698`, older than the
  base tag it was built from, because it is two weeks old and nothing rebuilds it on its own. It
  is not a bump. `just up-gpu` passes `--build`, and the runtime stage of
  [brain/Dockerfile.modelhost](../../../brain/Dockerfile.modelhost) is the base image itself with
  a venv copied in, so the recipe starts whatever the cached base carries. Read the base, not the
  image built from it.

- 2026-09-13: the trigger has still not fired. `docker images` reports the same two cached digests
  the bullet above read, `sha256:952424b09abc` for `server-cuda` and `sha256:db057ec90de0` for
  `server`, so the stack still starts the build every row of the column was read on. The registry
  was not asked again: what the tags resolve to moves without this stack moving, and the reading
  that answers this entry is the digest compose starts.

- 2026-09-19: the trigger has still not fired, and the trigger and the remedy were both repaired.
  Both cached images are the digests the bullets above read, `sha256:952424b09abc` for
  `server-cuda` and `sha256:db057ec90de0` for `server`, and the runbook's label command reports
  `b10680 d7bd3bfca` on each; tonight's detached sitting logged the same `server-cuda` digest at
  its start. The trigger named a digest "pinned by" the overrides, which the 2026-09-04 reading
  had already shown nothing does, so it now names the reading that fires it. The remedy named the
  model-host sidecar as the obvious driver for a sweep recipe, and it cannot be one: its API takes
  a logical id with no path, argv or layer count (`cortex_model_manager/api.py`), and its subagent
  tier starts with `_SUBAGENT_TAIL` in `cortex_model_manager/config.py`, whose reasoning-off pair
  is exactly what the sweep's servers must not carry. The body's other claims hold against the
  lineup-tails addendum: nine rows in about 26 minutes, eleven in the column, three owed their
  `-ngl 0` placement. The sample's `n_ctx` field, landed 2026-09-15, is now named in the remedy.
