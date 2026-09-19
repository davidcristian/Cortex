# A mutable image tag can move under the recorded answer and nothing notices

**Status:** done 2026-08-25
**Area:** repo-checks
**Origin:** [ADR-0067](../../adr/ADR-0067-image-volume-record.md)

`volumecheck.py` reads `scripts/imagevolumes.py`, a record of the volume paths each image declares,
because CI has no docker daemon and no images. The record is keyed on the image reference a compose
file writes, which makes a version change self-correcting: change `dovecot/dovecot:2.3.21` to a
later tag and the key stops matching, the check reports an unrecorded image, and whoever changed it
has to run `just image-volumes`.

The bad case is a mutable tag. `ghcr.io/ggml-org/llama.cpp:server` is republished under one name by
design, and so are `node:22-bookworm-slim`, `redis:8-alpine`, `pgvector/pgvector:pg16` and
`python:3.12-slim` to a lesser degree: the publisher can push a new image under the same name, and
if that image adds a `VOLUME`, every compose file naming the tag starts collecting an anonymous
volume while the recorded answer, the key it is filed under, and every check here stay exactly as
they were. The record is only as fresh as the last hand-run recomputation.

Three candidate answers: record the resolved digest beside the tag, which needs a docker call and
is therefore the same problem one level down; a scheduled workflow running `just image-volumes` on
a timer, which costs a second job and a runner that can pull large images; or naming every image
by digest, which makes the class impossible and means constant churn on files that read cleanly
today.

## History

- 2026-08-25: opened by the close of
  [R-425](425-nothing-notices-an-image-volume-nobody-mounts.md), which recorded what each fixed
  image declares so a check with no docker could read it.
- 2026-08-25: closed. All three candidate answers declined, and a defect found while measuring them
  fixed instead, argued in ADR-0067 decisions 5 and 6. The entry understated the exposure. It read
  as "the record is only as fresh as the last recomputation", and the recomputation could not see a
  moved tag at all: `docker image inspect` answers out of the local cache and never reaches a
  registry, so `just image-volumes` on a box holding a month-old copy of a moving tag confirmed the
  record against the month-old image. The recipe now pulls every reference it did not build before
  asking what it declares, reports a pull it cannot do rather than answering from the cache, and
  asks the three images this repo builds without one, the walk handing over the set it already read
  from each service's `build:`. The digest column is declined as the same problem one level down
  plus churn on events the record does not care about, the scheduled run as a weekly
  multi-gigabyte pull into a job nobody watches, and naming every image by digest as unreadable compose files
  bought against a rare defect whose symptom is clutter. Eight mutants over the check's own 46
  tests, seven killed by the suite and the eighth live, beside an accidental live proof: the first
  live run could not pull at all on this host and reported five failed pulls instead of five cache
  answers, and with the pull removed the same shell passes. What stays open, named on the recipe:
  between two runs, a republished tag can still add a declared path and nothing here reports it.
  One residue filed, the same record moving from inside the tree instead: three of its rows are
  images built from Dockerfiles here, and a `VOLUME` added to one of those would leave the row
  saying the image declares nothing
  ([R-437](437-a-volume-added-to-a-dockerfile-here-moves-the-same-record.md)).
