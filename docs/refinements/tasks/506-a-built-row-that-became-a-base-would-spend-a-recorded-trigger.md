# A built row that became a base would spend a recorded trigger

**Status:** open, dead until a consumer
**Area:** repo-gates
**Trigger:** a Dockerfile in this tree stands `FROM` an image this repo builds
**Origin:** [ADR-0011](../../adr/ADR-0011-body-v1.md)

Opened 2026-08-30 by the close of
[R-493](493-a-base-may-declare-a-volume-through-onbuild.md), which decided that
`dockerfilevolumes.read_volumes` goes on refusing `ONBUILD VOLUME` in a Dockerfile here and named
this as what that decision leaves open.

A base's row now carries two dimensions, and the second is spent by the rule holding a built row to
what its base would declare into it. Every base that dimension is read from is a pulled reference
today, `python:3.12-slim-trixie` and `ghcr.io/ggml-org/llama.cpp:server-cuda`, so it is refreshed on
every `just image-volumes` and cannot move from inside the tree.

That stops being true the day a Dockerfile here stands `FROM` an image this repo builds. Add
`ONBUILD VOLUME /x` to `brain/Dockerfile` and a second file standing `FROM cortex-brain`, and the
gate reads `cortex-brain`'s recorded triggers, which answer from whatever the machine running the
recipe last built and say nothing, while the next build of the downstream image really would
declare `/x`. It is exactly the hole `dockerfilevolumes.py` exists to close for the `VOLUME`
dimension, in the dimension that reader deliberately does not read, and the reason it costs nothing
today is that no file here stands on an image this repo builds.

**Why it was left.** The refusal it comes out of is right and is not the thing to change: reading
an `ONBUILD VOLUME` into `read_volumes` would make the existing rule demand a path in the row for
an image that truly declares none. Closing this needs a second reading rather than a widened one,
and a second reading nothing in this tree can exercise is a rule written for a shape nobody has
yet.

**What would close it.** Either read a Dockerfile's own `ONBUILD VOLUME` into a reading of its own
and hold it to the recorded trigger dimension of the row it builds, one-directionally like every
other rule here, or refuse the configuration instead: a build stanza whose base is an image this
walk also builds is a base whose row cannot be refreshed, and saying so is a fault of two lines.
Whichever way it goes, the deciding evidence is whether a Dockerfile here has become a base for
another one, which is what the trigger on this entry watches for.

## Trail

- 2026-08-30: opened by the close of
  [R-493](493-a-base-may-declare-a-volume-through-onbuild.md), which recorded what a base's
  `ONBUILD` would declare and left the tree's own side of that dimension unread.
