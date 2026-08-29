# A base may declare a volume through ONBUILD

**Status:** open, actionable
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
image-volumes`. Then it reddens as an uncovered path rather than as the base change it is.

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
rule spends. And whether `dockerfilevolumes.py`'s deliberate refusal to read `ONBUILD VOLUME` in a
Dockerfile here should stay: it is right for what that reader answers, and a file here that grew one
would then be a base whose downstream nothing records.

## Trail

- 2026-08-29: opened by the close of
  [R-473](473-a-built-row-is-recorded-where-it-could-be-derived.md), whose falsifying measurement
  is recorded in the [ADR-0011 addendum on why the built rows stay
  recorded](../../adr/ADR-0011-body-v1.md).
