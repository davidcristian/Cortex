# A built row's answer comes from whatever this machine last built

**Status:** landed 2026-08-28
**Area:** repo-gates
**Origin:** [ADR-0011](../../adr/ADR-0011-body-v1.md)

Opened 2026-08-26 by the close of
[R-437](437-a-volume-added-to-a-dockerfile-here-moves-the-same-record.md), which held the record to
every `VOLUME` a Dockerfile here declares and, in doing so, left exactly one way for a built row to
be wrong.

`rederive` in `scripts/imagevolumes.py` asks docker about every image, pulling first, except for
the three the compose files build here: those are asked with `pull=False`, because there is no
registry to refresh them from. What answers instead is `docker image inspect cortex-brain`, and
that reads whatever image this machine last tagged `cortex-brain`. If it was built a month ago
from a base image that has since been republished with a new `VOLUME`, the row is confirmed against
the month-old build and `just image-volumes` reports that the record agrees with docker.

That is the same defect [R-433](433-a-mutable-image-tag-moves-under-the-recorded-answer.md) found
and fixed for pulled references, arriving on the three references its fix deliberately exempted.
It is narrower than it was, because the Dockerfile check now covers everything those two files
declare themselves: what is left is only what a built image **inherits** from
`python:3.12-slim-trixie` or `ghcr.io/ggml-org/llama.cpp:server-cuda`, both of them moving tags
with no row of their own.

The absence case is already loud, and only the staleness case is silent: an image never built here
makes `docker image inspect` fail, and `rederive` reports the failure rather than skipping the row.

**Why it was left.** The close it came out of was about the tree's own declarations, and this is
about how a built answer is obtained. It also has more than one shape and they are not obviously
ranked. Building before inspecting would make the recipe honest at the cost of a CUDA image build
on any machine that runs it, which is minutes and gigabytes for a question whose answer is almost
always the same. Recording a row for each base image and requiring a built row to carry everything
its base declares would need no build at all, and it would move the freshness problem onto two more
pulled references, which the recipe already refreshes correctly. Refusing to answer for a built
image older than its Dockerfile would catch the local half and none of the base half.

**What would close it.** Pick one of those and argue it against the others, or argue that the
exposure does not justify any of them, in which case say so on the recipe: the instruction there
already names the day a pin moves, and it would gain the day a base is rebuilt. If the answer is
the base rows, note that `imagevolumes.py`'s docstring currently explains at length why no base has
a row, so that reasoning is what would have to be revised rather than merely extended.

## Trail

- 2026-08-26: opened by the close of
  [R-437](437-a-volume-added-to-a-dockerfile-here-moves-the-same-record.md).
- **2026-08-28, closed.** Landed as the base rows, argued in the ADR-0011 addendum on the bases the
  built rows stand on: `scripts/imagevolumes.py` now carries a row for `python:3.12-slim-trixie`
  and `ghcr.io/ggml-org/llama.cpp:server-cuda`, the recipe pulls them like every other registry
  reference, and `scripts/dockerfilebases.py` holds each built row to carrying what its base's row
  carries. Every claim above held at HEAD when re-derived. The exposure was measured before it was
  argued: both bases declare no `VOLUME` at all on 2026-08-28, which is a dated reading and not a
  property, while the staleness was live on this host, `cortex-mcp-email` carrying a build from
  2026-07-03 against a base republished 2026-08-25. Two docker measurements decide the shape: a
  declaration is inherited through `FROM`, and a `FROM ... AS builder` stage's reaches no built
  image, so what a built image declares is exactly the union of its own Dockerfile and its **last**
  stage's base, and the tree could already read the first half. Building before inspecting is
  declined as minutes and gigabytes for an answer two pulls already give, and as turning a
  verification into something that rebuilds what it verifies; refusing to answer for a build older
  than its Dockerfile is declined as aiming at the half already closed and as unreliable on a fresh
  clone, where every file is newer than every image; naming the residue on the recipe is declined
  on cost, the answer taken needing no build, no schedule and no daemon. The entry's warning was
  right: `imagevolumes.py`'s reasoning about why no base has a row was revised rather than extended,
  its premise being true and its conclusion not following. **Twelve mutants over the three suites
  the change is measured by, all twelve killed**, tabled in that addendum with the live proof
  beside it. One residue filed: the base rows are recorded where a built row could instead be
  derived from them
  ([R-473](473-a-built-row-is-recorded-where-it-could-be-derived.md)).
