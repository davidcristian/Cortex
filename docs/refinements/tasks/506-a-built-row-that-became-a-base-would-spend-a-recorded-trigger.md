# A built row that became a base would be checked against a recorded trigger

**Status:** open, waiting for a consumer
**Area:** repo-checks
**Trigger:** a Dockerfile in this tree is built `FROM` an image this repo builds
**Origin:** [ADR-0067](../../adr/ADR-0067-image-volume-record.md)
**Verified:** 2026-09-19

A base's row now has two dimensions, and the second is read by the rule comparing a built row with
what its base would declare into it. Every base that dimension is read from is a pulled reference
today, `python:3.12-slim-trixie` and `ghcr.io/ggml-org/llama.cpp:server-cuda`, so it is refreshed on
every `just image-volumes` and cannot move from inside the tree.

That stops being true the day a Dockerfile here is built `FROM` an image this repo builds. Add
`ONBUILD VOLUME /x` to `brain/Dockerfile` and a second file built `FROM cortex-brain`, and the check
reads `cortex-brain`'s recorded triggers, which come from whatever the machine running the recipe
last built and say nothing, while the next build of the downstream image really would declare `/x`.
It is the same hole `dockerfilevolumes.py` closes for the `VOLUME` dimension, in the dimension that
reader deliberately does not read.

Closing it needs a second reading rather than a wider one, since reading an `ONBUILD VOLUME` into
`read_volumes` would make the existing rule demand a path in the row for an image that truly
declares none. Either read a Dockerfile's own `ONBUILD VOLUME` separately and compare it with the
recorded trigger dimension of the row it builds, one-directionally like every other rule here, or
refuse the configuration: a build stanza whose base is an image this walk also builds is a base
whose row cannot be refreshed, and saying so is a two-line failure.

## History

- 2026-08-30: opened by the close of
  [R-493](493-a-base-may-declare-a-volume-through-onbuild.md), which recorded what a base's
  `ONBUILD` would declare and left the tree's own side of that dimension unread.
- 2026-09-13: checked again, and the trigger has not fired. The tree has two Dockerfiles,
  `brain/Dockerfile` and `brain/Dockerfile.modelhost`, and their four `FROM` lines name
  `ghcr.io/astral-sh/uv:0.11-python3.12-trixie-slim`, `python:3.12-slim-trixie` and
  `ghcr.io/ggml-org/llama.cpp:server-cuda` twice. Every one is a pulled reference, and the two final
  stages, which are the ones `dockerfilebases.read_base` reads, are still the two images this entry
  names. The compose stack builds `cortex-brain` and `cortex-model-host` and nothing is built on
  either.
- 2026-09-19: checked again, and the trigger has not fired. The same two Dockerfiles have the same
  four `FROM` lines, every one a pulled reference, and neither file has an `ONBUILD`. The compose
  files build the brain image in two services, `docker/docker-compose.yml` and
  `docker/docker-compose.email.yml`, both from `./brain`, and the model host from
  `brain/Dockerfile.modelhost` as `cortex-model-host`; every `image:` elsewhere is a pulled
  reference. The two failures the entry relies on are still in `scripts/dockerfilevolumes.py`, and
  `read_volumes` still returns nothing for an `ONBUILD VOLUME` line.
