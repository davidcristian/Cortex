# A VOLUME added to a Dockerfile here moves the same record, from inside the tree

**Status:** done 2026-08-26
**Area:** repo-checks
**Origin:** [ADR-0067](../../adr/ADR-0067-image-volume-record.md)

`scripts/imagevolumes.py` records three built images, `cortex-brain`, `cortex-mcp-email` and
`cortex-model-host`, each with an empty tuple, and each is built from a Dockerfile in this repo.
[R-433](433-a-mutable-image-tag-moves-under-the-recorded-answer.md) was about a fact moving under
the record from a registry the check cannot reach. This is the same record moving under the check
from a file the check can read: add `VOLUME /var/cache/thing` to `brain/Dockerfile` and the built
image declares a path, every container of it collects an anonymous volume, and the row goes on
saying the image declares nothing. `just check` still passes, and only a hand-run
`just image-volumes` on a machine that has rebuilt the image would notice.

Neither `brain/Dockerfile` nor `brain/Dockerfile.modelhost` has a `VOLUME` today, so this is a hole
rather than a defect.

The check is one-directional and that is what makes it cheap: every `VOLUME` path a repo Dockerfile
declares must appear in the row for the image built from it, while a recorded path that Dockerfile
does not declare is fine, being inherited from the base image the record deliberately has no row
for. It needs a new reader, since `VOLUME` takes both a JSON array and a plain list and its
argument can be a build argument, and it needs the map from a Dockerfile to the image row it
builds, which lives in the compose files' `build:` stanzas.

## History

- 2026-08-25: opened by the close of
  [R-433](433-a-mutable-image-tag-moves-under-the-recorded-answer.md), which made the recomputation
  ask the registry and then noticed that three of its eight rows have no registry at all.
- 2026-08-25: checked and left open, having run out of session rather than out of argument. Every
  claim above holds: neither Dockerfile has a `VOLUME`, the three built rows are still empty
  tuples, and `scripts/volumecheck.py` stands at 299 of the 300 line cap. The warning about that
  cap is understated. The mapping this entry prefers, read from each compose service's `build:`
  stanza, cannot be read at all today: `composeservices.py` sets `Service.builds` to a bare `True`
  when it meets the key and never looks inside the stanza, so the long form's `context:` and
  `dockerfile:` arrive as service keys it does not recognize and are ignored with nothing reported.
  There is no Dockerfile path on `Service` to map a row to. Reading both forms grows a file that is
  itself at 296 lines, so the preferred option is two splits plus a new Dockerfile reader plus the
  tests both need. The alternative, recording the Dockerfile beside the row, buys its cheapness by
  writing the same fact in a second place, which is what `crosscheck.py` exists to catch.
- 2026-08-26: closed as a second rule inside `volumecheck.py`, argued in ADR-0067 decision 7: every
  `VOLUME` path a Dockerfile here declares must appear in the row for the image built from it,
  one-directional. The mapping is read from each compose service's `build:` stanza, the option this
  entry preferred, and the alternative is declined for the reason the entry was opened: writing
  `brain/Dockerfile` beside `cortex-brain` in the record writes one fact twice with nothing
  deriving it to compare, so a repointed `build:` would leave the record naming a file that builds
  nothing. The cost estimate above held. `composeservices.py` now has `Service.build` in both
  forms, raising on a build key it does not recognize instead of stepping over the block form's two
  keys unreported; the mount-entry half moved to `composetargets.py` to make room under the line
  cap, and `report_drift` moved from `volumecheck.py` to `imagevolumes.py`, where every name it
  touches already lived. `dockerfilevolumes.py` is the new reader and the rule over it, resolving a
  relative context against both project directories compose can pick, exactly as the bind check
  does. Nine mutants over the three suites the change is measured by, all nine killed, and the live
  proof: a `VOLUME /var/cache/thing` appended to `brain/Dockerfile` makes both rows that file
  builds fail. One residue filed, the last way a built row can still be wrong: those three
  references are asked without a pull by design, so the answer is whatever this machine last built,
  and what a republished base contributes goes unseen between builds
  ([R-443](443-a-built-rows-answer-comes-from-whatever-this-machine-last-built.md)).
