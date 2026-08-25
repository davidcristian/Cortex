# A mutable image tag can move under the recorded answer and nothing notices

**Status:** landed 2026-08-25
**Area:** repo-gates
**Origin:** [ADR-0011](../../adr/ADR-0011-body-v1.md)

Opened 2026-08-25 by the close of
[R-425](425-nothing-notices-an-image-volume-nobody-mounts.md), which recorded what each pinned
image declares so a gate with no docker could read it.

`volumecheck.py` reads `scripts/imagevolumes.py`, a record of the volume paths each image
declares, because CI has no docker daemon and no images. The record is keyed on the image
reference a compose file writes, which makes a version bump self-healing: change
`dovecot/dovecot:2.3.21` to a later tag and the key stops matching, the gate reports an
unrecorded image, and whoever bumped it has to run `just image-volumes`. That is the good case
and it needs nothing further.

The bad case is a **mutable tag**. `ghcr.io/ggml-org/llama.cpp:server` is a moving target by
design, and so are `node:22-bookworm-slim`, `redis:8-alpine`, `pgvector/pgvector:pg16` and
`python:3.12-slim` to a lesser degree: the publisher can push a new image under the same name,
and if that image adds a `VOLUME`, every compose file naming the tag starts collecting an
anonymous volume while the recorded answer, the key it is filed under, and every gate here stay
exactly as they were. The record is only as fresh as the last hand-run re-derivation, and nothing
makes anyone run it on a day when no file in this repo changed.

**Why it was left.** The close it came out of was about asking the question at all, and this is
about how long an answer stays true. It also has more than one shape and they are not obviously
ranked. Recording the resolved digest beside the tag would make a moved tag visible, but only to
something that can resolve a digest, which is a docker call and therefore the same problem one
level down. A scheduled workflow that runs `just image-volumes` on a timer would catch it without
touching the gate, at the cost of a second scheduled job and a CI runner that can pull these
images, some of which are large. Pinning every image by digest would make the whole class
impossible and would also mean dependabot-style churn on files that currently read cleanly.

**What would close it.** Pick one of those three and argue it against the others, or argue that
the exposure does not justify any of them: a publisher adding a `VOLUME` to an existing tag is
rare, the symptom is clutter rather than data loss, and the re-derivation recipe already exists
for anyone who suspects it. If the answer is the scheduled run, note that `shuffle.yml` is the
precedent for a weekly workflow here that gates nothing, and that this one would need to report
somewhere a human reads rather than only reddening a job nobody watches.

## Trail

- **2026-08-25, closed.** All three framed answers declined, and a defect found while measuring
  them landed instead, argued in the ADR-0011 addendum on asking the registry. **The entry
  understated the exposure.** It read as "the record is only as fresh as the last re-derivation",
  and the re-derivation could not see a moved tag at all: `docker image inspect` answers out of the
  local cache and never reaches a registry, so `just image-volumes` on a box holding a month-old
  copy of a moving tag confirmed the record against the month-old image. The recipe now pulls every
  reference it did not build before asking what it declares, reports a pull it cannot do rather
  than answering from the cache, and asks the three images this repo builds without one, the walk
  handing over the set it already read from each service's `build:`. The digest column is declined
  as the same problem one level down plus churn on events the record does not care about, the
  scheduled run as a weekly multi-gigabyte pull into a job nobody watches, and digest pinning as
  unreadable compose files bought against a rare defect whose symptom is clutter. **Eight mutants
  over the gate's own 46 tests, seven killed by the suite and the eighth live**, tabled in that
  addendum, along with the accidental live proof: the first live run could not pull at all on this
  host and reported five failed pulls instead of five cache answers, and with the pull removed the
  same shell goes green. What stays open, named on the recipe: between two runs, a republished tag
  can still add a declared path and nothing here will know. One residue filed, the same record
  moving under the gate from inside the tree instead: three of its rows are images built from
  Dockerfiles here, and a `VOLUME` added to one of those would leave the row saying the image
  declares nothing
  ([R-437](437-a-volume-added-to-a-dockerfile-here-moves-the-same-record.md)).
