# A base may declare a volume through ONBUILD

**Status:** landed 2026-08-30
**Area:** repo-gates
**Origin:** [ADR-0011](../../adr/ADR-0011-body-v1.md)

Opened 2026-08-29 by the close of
[R-473](473-a-built-row-is-recorded-where-it-could-be-derived.md), whose measurement found this
while falsifying the claim that entry rested on.

`scripts/imagevolumes.py` records one thing per image, the paths its `Config.Volumes` declares, and
`scripts/dockerfilebases.py` holds each built row to the row of the base its last stage stands on.
A base can carry a volume declaration that neither of those sees. `ONBUILD VOLUME /x` in a base
leaves that base's own `Config.Volumes` empty, so its row here is the empty tuple, and it fires
during the build of anything standing `FROM` it, so the built image declares `/x` while no
Dockerfile in this tree ever wrote a `VOLUME`. Measured on docker 29.7.2 on 2026-08-29, under
BuildKit and under `DOCKER_BUILDKIT=0` alike; the instruction clears in the child, so the built
image carries no trace of where the path came from.

Nothing today is wrong: neither `python:3.12-slim-trixie` nor
`ghcr.io/ggml-org/llama.cpp:server-cuda` carries an `ONBUILD` at all, which was read the same day.
That is a dated reading and not a property, and it is the same shape of exposure the base rows were
added for. Both are moving tags. A republish that adds `ONBUILD VOLUME` leaves every gate green:
the base row is still empty and correct, the Dockerfile rule sees nothing, and the built row goes on
answering from whatever this machine last built, until somebody rebuilds and hand-runs `just
image-volumes`. Then it fails as an uncovered path rather than as the base change it is.

The built rows are recorded rather than derived precisely so a third source like this one lands in
the record instead of being reasoned away, so the record is right; what is missing is the rule that
would catch the base moving before a rebuild, which is the whole point of the base rows.

**What would close it.** Record what a base's `ONBUILD` would add, and hold the built row to it the
way `dockerfilebases.py` already holds it to the base's own declarations. That is a second
dimension on a row rather than a second table: `Config.OnBuild` is one more thing for the inspector
to ask about, its `VOLUME` entries parse with the reader `dockerfilevolumes.py` already has, and the
rule is the existing one-directional comparison over a second set. Weigh three things first.
Whether the row's shape should change or a parallel mapping is honest, given every consumer of
`IMAGE_VOLUMES` would see the new shape. Whether the record should hold the raw `ONBUILD` list or
only the volume paths it resolves to, since the first is what docker says and the second is what the
rule spends. And whether `dockerfilevolumes.py` should go on not reading `ONBUILD VOLUME` in a
Dockerfile here: it is right for what that reader answers, and a file here that grew one
would then be a base whose downstream nothing records.

## Trail

- 2026-08-29: opened by the close of
  [R-473](473-a-built-row-is-recorded-where-it-could-be-derived.md), whose falsifying measurement
  is recorded in the [ADR-0011 addendum on why the built rows stay
  recorded](../../adr/ADR-0011-body-v1.md).
- 2026-08-30: **landed** as the [ADR-0011 addendum on what a base declares for its
  children](../../adr/ADR-0011-body-v1.md). The premise held on re-derivation against docker 29.7.2:
  a base carrying `ONBUILD VOLUME` answers `null` for its own `Config.Volumes`, carries the
  instruction verbatim in `Config.OnBuild`, and the image built `FROM` it declares the path and
  clears the trigger, under BuildKit and under `DOCKER_BUILDKIT=0` alike; both real bases and all
  ten rows still carry no `ONBUILD` at all, pulled first. Each row now holds two dimensions rather
  than a parallel mapping, because which images are recorded is one fact and two tables keyed on
  an image reference would spell it twice with nothing deriving it to compare, and because both
  dimensions are asked in one inspect, so a row cannot half-exist; the cost the entry named was
  paid, four modules and their tests seeing the new shape. The dimension is recorded **raw**, since
  the record holds what docker says and a resolved path is a reading of it, one that would be taken
  once on the recorder's machine and would leave the recipe comparing an image against a
  derivation. `dockerfilevolumes.py` still does not read `ONBUILD VOLUME` in a file here, and that
  decision is now argued as a correctness requirement: reading one there would make the existing
  rule demand a path in a row that correctly lacks it. The record was re-derived with `just
  image-volumes` against a real daemon, which agrees with all ten rows in both dimensions.
  `imagedrift.py` split off under the line cap, holding the inspect call and the drift report while
  `imagevolumes.py` stays the record. Thirteen mutants over the `scripts/` suite, all failing, and one
  of them was green first: a trigger pasted as the path it resolves to declared nothing, which is
  now a refusal. Opened by this close:
  [R-506](506-a-built-row-that-became-a-base-would-spend-a-recorded-trigger.md).
