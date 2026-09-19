# A base may declare a volume through ONBUILD

**Status:** done 2026-08-30
**Area:** repo-checks
**Origin:** [ADR-0067](../../adr/ADR-0067-image-volume-record.md)

`scripts/imagevolumes.py` records one thing per image, the paths its `Config.Volumes` declares, and
`scripts/dockerfilebases.py` compares each built row with the row of the base its last stage stands
on. A base can have a volume declaration that neither of those sees. `ONBUILD VOLUME /x` in a base
leaves that base's own `Config.Volumes` empty, so its row here is the empty tuple, and it runs
during the build of anything built `FROM` it, so the built image declares `/x` while no
Dockerfile in this tree ever wrote a `VOLUME`. Measured on docker 29.7.2 on 2026-08-29, under
BuildKit and under `DOCKER_BUILDKIT=0` alike; the instruction clears in the child, so the built
image shows no trace of where the path came from.

Nothing today is wrong: neither `python:3.12-slim-trixie` nor
`ghcr.io/ggml-org/llama.cpp:server-cuda` has an `ONBUILD` at all, read the same day. Both are moving
tags, and a republish that adds `ONBUILD VOLUME` leaves every check passing until somebody rebuilds
and runs `just image-volumes` by hand, where it then fails as an uncovered path rather than as the
base change it is.

## History

- 2026-08-29: opened by the close of
  [R-473](473-a-built-row-is-recorded-where-it-could-be-derived.md), whose measurement found this
  while disproving the claim that entry rested on. The measurement is in
  [the image volume readings](../../readings/image-volumes.md).
- 2026-08-30: closed as [ADR-0067 decision 9](../../adr/ADR-0067-image-volume-record.md). The
  premise held when checked again against docker 29.7.2: a base with `ONBUILD VOLUME` answers `null`
  for its own `Config.Volumes`, repeats the instruction word for word in `Config.OnBuild`, and the
  image built `FROM` it declares the path and clears the trigger, under BuildKit and under
  `DOCKER_BUILDKIT=0` alike; both real bases and all ten rows still have no `ONBUILD` at all, pulled
  first. Each row now has two dimensions rather than a parallel mapping, because which images are
  recorded is one fact and two tables keyed on an image reference would state it twice, and because
  both dimensions are asked in one inspect, so a row cannot half-exist; the cost the entry named was
  paid, four modules and their tests seeing the new shape. The dimension is recorded raw, since the
  record holds what docker says and a resolved path is an interpretation of it.
  `dockerfilevolumes.py` still does not read `ONBUILD VOLUME` in a file here, now argued as a
  correctness requirement: reading one there would make the existing rule demand a path in a row
  that correctly lacks it. The record was recomputed with `just image-volumes` against a real
  daemon, which agrees with all ten rows in both dimensions. `imagedrift.py` split off under the
  line cap, taking the inspect call and the comparison report while `imagevolumes.py` stays the
  record. Thirteen mutants over the `scripts/` suite, all failing, and one of them passed first: a
  trigger pasted as the path it resolves to declared nothing, which is now refused. Opened by this
  close: [R-506](506-a-built-row-that-became-a-base-would-spend-a-recorded-trigger.md).
