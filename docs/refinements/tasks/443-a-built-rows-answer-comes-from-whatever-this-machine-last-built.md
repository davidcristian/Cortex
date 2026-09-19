# A built row's answer comes from whatever this machine last built

**Status:** done 2026-08-28
**Area:** repo-checks
**Origin:** [ADR-0067](../../adr/ADR-0067-image-volume-record.md)

`rederive` in `scripts/imagevolumes.py` asks docker about every image, pulling first, except for
the three the compose files build here: those are asked with `pull=False`, because there is no
registry to refresh them from. What answers instead is `docker image inspect cortex-brain`, and
that reads whatever image this machine last tagged `cortex-brain`. If it was built a month ago from
a base image that has since been republished with a new `VOLUME`, the row is confirmed against the
month-old build and `just image-volumes` reports that the record agrees with docker.

That is the same defect [R-433](433-a-mutable-image-tag-moves-under-the-recorded-answer.md) found
and fixed for pulled references, arriving on the three references its fix deliberately exempted. It
is narrower than it was, because the Dockerfile check now covers everything those two files declare
themselves: what is left is only what a built image inherits from `python:3.12-slim-trixie` or
`ghcr.io/ggml-org/llama.cpp:server-cuda`, both mutable tags with no row of their own. The absence
case is already reported: an image never built here makes `docker image inspect` fail, and
`rederive` reports the failure rather than skipping the row.

Three candidate answers. Build before inspecting, which is accurate at the cost of a CUDA image
build on any machine that runs the recipe. Record a row for each base image and require a built row
to contain everything its base declares, which needs no build and moves the freshness problem onto
two more pulled references the recipe already refreshes correctly. Or refuse to answer for a built
image older than its Dockerfile, which catches the local half and none of the base half.

## History

- 2026-08-26: opened by the close of
  [R-437](437-a-volume-added-to-a-dockerfile-here-moves-the-same-record.md), which compared the
  record with every `VOLUME` a Dockerfile here declares and left exactly one way for a built row to
  be wrong.
- 2026-08-28: closed as the base rows, argued in ADR-0067 decision 8:
  `scripts/imagevolumes.py` now has a row for `python:3.12-slim-trixie` and
  `ghcr.io/ggml-org/llama.cpp:server-cuda`, the recipe pulls them like every other registry
  reference, and `scripts/dockerfilebases.py` requires each built row to contain what its base's
  row contains. Every claim above held. The exposure was measured before it was argued: both bases
  declare no `VOLUME` at all on 2026-08-28, which is a dated reading and not a property, while the
  staleness was live on this host, `cortex-mcp-email` having a build from 2026-07-03 against a base
  republished 2026-08-25. Two docker measurements decide the shape: a declaration is inherited
  through `FROM`, and a `FROM ... AS builder` stage's reaches no built image, so what a built image
  declares is exactly the union of its own Dockerfile and its last stage's base, and the tree could
  already read the first half. Building before inspecting is declined as minutes and gigabytes for
  an answer two pulls already give, and as turning a verification into something that rebuilds what
  it verifies; refusing to answer for a build older than its Dockerfile is declined as aiming at
  the half already closed and as unreliable on a fresh clone; naming the residue on the recipe is
  declined on cost, the answer taken needing no build, no schedule and no daemon. The entry's
  warning was right: `imagevolumes.py`'s reasoning about why no base has a row was revised rather
  than extended, its premise being true and its conclusion not following. Twelve mutants over the
  three suites the change is measured by, all twelve killed, with a live proof beside them. One
  residue filed: the base rows are recorded where a built row could instead be derived from them
  ([R-473](473-a-built-row-is-recorded-where-it-could-be-derived.md)).
- 2026-08-29: one sentence above is retired by the close of that residue. The two measurements
  named here are still right, but they do not make the union exact: a base with `ONBUILD VOLUME`
  declares no volume of its own and still adds one to every image built `FROM` it, so what the tree
  can read is a minimum for a built row and never the whole of it. The base rows and the rule over
  them are unaffected, being one-directional; what changed is that the three built rows are now
  recorded on purpose rather than pending derivation. See
  [ADR-0067 decision 10](../../adr/ADR-0067-image-volume-record.md) and
  [R-493](493-a-base-may-declare-a-volume-through-onbuild.md).
