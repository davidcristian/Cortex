# A VOLUME added to a Dockerfile here moves the same record, from inside the tree

**Status:** landed 2026-08-26
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

**Why it was left.** The close it came out of was about the registry half, and this half needs a
new reader: `VOLUME` in a Dockerfile takes both a JSON array and a plain list, its argument can be
a build argument or an environment variable, and this repo's readers raise on shapes they do not
recognize rather than ignoring them. It also needs the map from a Dockerfile to the image row it
builds, which is written today in the compose files' `build:` stanzas and nowhere the record can
see.

**What would close it.** The check is one-directional and that is what makes it cheap: every
`VOLUME` path a repo Dockerfile declares must appear in the row for the image built from it, while
a recorded path that Dockerfile does not declare is fine, being inherited from the base image the
record deliberately holds no row for. It is the ADR-0011 tier-two answer applied a second time, a
cheaper question the tree can already answer, and it runs with no daemon. Decide whether the
mapping is read from each compose service's `build:` stanza, which is where it really lives, or
recorded beside the row, which is one more thing to keep in step.

## Trail

- 2026-08-25: opened by the close of
  [R-433](433-a-mutable-image-tag-moves-under-the-recorded-answer.md).
- 2026-08-25: re-derived and left open, having run out of session rather than out of argument.
  Every claim above holds at HEAD: neither `brain/Dockerfile` nor `brain/Dockerfile.modelhost`
  carries a `VOLUME`, the three built rows are still empty tuples, and `scripts/volumecheck.py`
  stands at 299 of the 300 line cap. The warning about that cap is understated in the way that
  decides the bill. The mapping this entry prefers, read from each compose service's `build:`
  stanza, cannot be read at all today: `composeservices.py` sets `Service.builds` to a bare `True`
  when it meets the key and never looks inside the stanza, so the long form's `context:` and
  `dockerfile:` arrive as service keys it does not recognize and are ignored with nothing
  reported. There
  is no Dockerfile path on `Service` to map a row to. Reading both forms and carrying them
  through grows a file that is itself at 296 lines, so the preferred option is two splits plus a
  new Dockerfile reader plus the tests both need, rather than the one split named above. The
  alternative, recording the Dockerfile beside the row, buys its cheapness by writing the same
  fact in a second place, which is the shape `crosscheck.py` exists to catch and would then have
  to hold.
- **2026-08-26, closed.** Landed as a second rule inside `volumecheck.py`, argued in the ADR-0011
  addendum on holding the record to the Dockerfiles this tree builds from: every `VOLUME` path a
  Dockerfile here declares must appear in the row for the image built from it, one-directional, so
  a recorded path the file does not declare stays fine as a base image's inheritance. The mapping
  is read from each compose service's `build:` stanza, which is the option this entry preferred,
  and the alternative is declined for the reason the entry was opened: writing `brain/Dockerfile`
  beside `cortex-brain` in the record spells one fact twice with nothing deriving it to compare, so
  a repointed `build:` would leave the record naming a file that builds nothing, with nothing
  reporting it. The cost
  estimate above held. `composeservices.py` could not answer the question at all and now carries
  `Service.build` in both spellings, raising on a build key it does not recognize instead of
  stepping over the block form's two keys with nothing reported; the mount-entry half moved to `composetargets.py` to
  make room under the line cap, and `report_drift` moved from `volumecheck.py` to
  `imagevolumes.py`, where every name it touches already lived. `dockerfilevolumes.py` is the new
  reader and the rule over it, resolving a relative context against both project directories
  compose can pick, exactly as the bind gate does. **Nine mutants over the three suites the change
  is measured by, all nine killed**, tabled in that addendum, and the live proof is in it too: a
  `VOLUME /var/cache/thing` appended to `brain/Dockerfile` makes both rows that file builds fail.
  One residue filed, the last way a built row can still be wrong: those three references are asked
  without a pull by design, so the answer is whatever this machine last built, and what a
  republished base contributes goes unseen between builds
  ([R-443](443-a-built-rows-answer-comes-from-whatever-this-machine-last-built.md)).
