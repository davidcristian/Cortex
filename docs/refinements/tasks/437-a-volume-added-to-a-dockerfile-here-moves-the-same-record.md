# A VOLUME added to a Dockerfile here moves the same record, from inside the tree

**Status:** open, actionable
**Area:** repo-gates
**Origin:** [ADR-0011](../../adr/ADR-0011-body-v1.md)

Opened 2026-08-25 by the close of
[R-433](433-a-mutable-image-tag-moves-under-the-recorded-answer.md), which made the re-derivation
ask the registry and then noticed that three of its eight rows have no registry at all.

`scripts/imagevolumes.py` records three built images, `cortex-brain`, `cortex-mcp-email` and
`cortex-model-host`, each with an empty tuple, and each of those is built from a Dockerfile in
this repo. R-433 was about a fact moving under the record from a registry the gate cannot reach.
This is the same record moving under the gate from a file the gate can read: add
`VOLUME /var/cache/thing` to `brain/Dockerfile` and the built image declares a path, every
container of it collects an anonymous volume, and the row goes on saying the image declares
nothing. `just check` stays green, and only a hand-run `just image-volumes` on a machine that has
rebuilt the image would notice.

Neither `brain/Dockerfile` nor `brain/Dockerfile.modelhost` carries a `VOLUME` today, which is
why nothing is currently wrong, and why the gap is a hole rather than a defect.

**Why it was left.** The close it came out of was about the registry half, and this half wants a
new reader: `VOLUME` in a Dockerfile takes both a JSON array and a plain list, its argument can be
a build argument or an environment variable, and this repo's readers refuse shapes they were not
taught rather than walking past them. It also needs the map from a Dockerfile to the image row it
builds, which is written today in the compose files' `build:` stanzas and nowhere the record can
see.

**What would close it.** The check is one-directional and that is what makes it cheap: every
`VOLUME` path a repo Dockerfile declares must appear in the row for the image built from it, while
a recorded path that Dockerfile does not declare is fine, being inherited from the base image the
record deliberately holds no row for. It is the ADR-0011 tier-two answer applied a second time, a
cheaper question the tree can already answer, and it runs with no daemon. Decide whether the
mapping is read from each compose service's `build:` stanza, which is where it really lives, or
recorded beside the row, which is one more thing to keep in step.
