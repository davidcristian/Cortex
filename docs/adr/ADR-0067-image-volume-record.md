# ADR-0067: The image volume record, and where a check goes when its evidence is out of reach

**Status:** Accepted (2026-08-30)

## Context

An image that declares a `VOLUME` gets an anonymous volume on every start of a container that mounts
nothing at that path, and a `docker compose down` without `--volumes` leaves it on the host under a
generated name, one per start. Nothing in the tree asked which paths the version-locked images
declare. The probe image's two declared paths were each found by reading `docker image inspect` by
hand, months apart, each time after the leak had been happening on every start.

The check the repo wants needs evidence `just check` cannot reach: what an image declares is a fact
about a registry, answered only by a pull, and CI has neither a docker daemon nor the images. A
second check had the same shape at the same time: whether the committed gRPC stubs still match
`proto/body.proto` needs a codegen toolchain the committed-stub decision
([ADR-0003](ADR-0003-generated-stubs.md)) exists so nobody needs. The obvious move, a second
CI-scheduled recipe beside `check-shell`, would turn "one recipe is deliberately outside `just
check`" into a category ([ADR-0011](ADR-0011-body-v1.md)).

## Decision

### Where a check goes when its evidence is out of reach

1. **Three answers, tried in this order, and the exception list stays at one.** `check-shell` is
   outside `just check` because its toolchain cannot be assumed on a clean dev box. Missing
   evidence is a different problem with cheaper answers:
   1. **Bring the evidence into the tree.** Record the out-of-reach fact as a file, check the record
      against the tree it describes on every commit, and recompute it with a hand-run recipe that
      fails when the record has gone stale. The check then runs on a machine with no docker at all.
      The backlog index and `just backlog` are the same arrangement with task files where the daemon
      is. The cost is that a record can go stale between recomputations, so the recipe and the
      runbook say when to run it.
   2. **Ask a cheaper question the tree can already answer.** Measure which defects each candidate
      catches. The stub case turned on that: regenerating the Python stubs reproduces byte for byte
      and never notices a comment, while a comment is the one part of a skipped regeneration no
      compiler catches, so the check worth having is `stubcheck.py`'s text comparison
      ([ADR-0003](ADR-0003-generated-stubs.md)).
   3. **A hand-run recipe that checks nothing**, last, and only when neither of the above can be
      built. A check nobody is obliged to run gets run after the damage, as the probe's two leaks
      were.

### The record and the check

2. **`scripts/imagevolumes.py` records what each image declares**, as `IMAGE_VOLUMES`: one `Row` per
   image reference, holding `volumes` (its `Config.Volumes`) and `onbuild` (its `Config.OnBuild`,
   the raw trigger list), both measured by one `docker image inspect` with
   `imagedrift.INSPECT_FORMAT`. One row with two dimensions rather than two tables keyed the same
   way, since two tables would write which images are recorded twice and a row could half-exist.
3. **`scripts/volumecheck.py` requires every declared path to be covered.** Each path an image
   declares must be covered, by the service that runs it and in the same compose file, with a mount
   or a tmpfs at exactly that path; a mount over the parent leaves the declaration uncovered. The
   rule runs per file, because `just up` runs the base file alone. It also fails on an image no row
   knows, a base no row knows, a row nothing names, and an image written through a substitution.
   Compose files come from the shared list ([ADR-0063](ADR-0063-compose-checks.md)); a file the
   reader refuses is counted as a file, apart from the findings (ADR-0063 decision 1).
4. **The fix for a declared path nothing needs is a tmpfs at that path**, which leaves docker's
   declaration nothing to make anonymous. The first run of the check found `pg-backup` in
   `docker/docker-compose.memory.yml` collecting a volume at `/var/lib/postgresql/data` on every
   start of the memory stack, from the same `pgvector/pgvector:pg16` image as the server
   ([readings](../readings/image-volumes.md)); it takes the tmpfs the probe fixture already used for
   dovecot's two paths ([ADR-0057](ADR-0057-imap-probe-server.md)).

### Recomputing the record

5. **`just image-volumes` pulls before it asks.** `volumecheck.py --rederive` (`imagedrift.py`)
   pulls every image this repo does not build, then inspects it and reports each row that changed.
   `docker image inspect` answers out of the local cache, so without the pull a recomputation could
   only confirm whatever the machine held, including a month-old copy of a tag the registry had
   republished. A pull that fails is reported, never answered from the cache. The three images built
   here (`cortex-brain`, `cortex-mcp-email`, `cortex-model-host`) are inspected without a pull, and
   which references those are comes from reading each service's `build:`, not from the form of a
   name. Run it when a version is changed and on any day a moving tag may have been republished.
6. **A tag stays a tag.** Between two runs of the recipe a republished tag can add a declared path
   unseen; that is the price of a check that runs without docker, and the recipe and the runbook
   name it. Recording each digest beside its tag, a scheduled workflow running the recipe, and
   locking every image by digest are declined (see Alternatives).

### The built rows

7. **Every `VOLUME` a Dockerfile here declares must appear in the row for the image built from it**
   (`dockerfilevolumes.py`), so a declaration added to `brain/Dockerfile` fails `just check` on both
   rows that file builds. Which Dockerfile builds which row is read from each service's `build:`
   (both forms, a relative context resolved against both project directories compose can pick),
   never recorded beside the row, so a repointed `build:` cannot leave the record naming a file that
   builds nothing. A build reaching no Dockerfile is a fault. An `ONBUILD VOLUME` in a Dockerfile
   here is not read as that image's own declaration, since it declares nothing in the image itself,
   and reading it would fail a correct record.
8. **Each base a Dockerfile stands on has a row, and every path it declares must appear in the built
   row** (`dockerfilebases.py`). A built image inherits its last stage's base's declarations and
   nothing from earlier stages, so the reader finds the last `FROM`, follows a stage name back to
   its image, answers `scratch` as nothing, drops `--platform`, and refuses every other form. The
   base rows are ordinary pulled references, so a base republished with a new `VOLUME` fails the
   check after the next recomputation, without anyone rebuilding the built image first.
9. **A base declares for its children too.** Every path a base row's `onbuild` entries would declare
   must appear in the built row. The record holds the raw entries as docker stores them (as written,
   with continuations joined), and the check reads each as a one-line Dockerfile, so a trigger
   nobody here can read fails every `just check` rather than once on the machine that ran the
   recipe. A recorded entry that does not open with an instruction word is a fault, since a
   hand-pasted `/x` would otherwise read as declaring nothing.
10. **The three built rows stay recorded, and every rule over them runs one way.** The union of what
    a Dockerfile declares, what its base declares and what its base's triggers declare is a lower
    bound on what a built image declares, never an upper bound: `ONBUILD` was found as one way past
    the first two, and what the record has to survive is a mechanism nobody here has listed. A
    recorded row is a reading of a real image and includes whatever produced a declaration, so a
    recorded path no side declares is the one place a further source can appear, and a rule
    demanding equality would fail a correct record.

## Consequences

- `just check` asks what every compose service leaves uncovered on every commit, in CI too, with no
  docker involved; `just image-volumes` is the only step that needs a daemon.
- A republished tag, base or trigger moves its row on the next recomputation, and the check then
  fails until the image is re-recorded and the path is covered.
- A built row that became a base for another Dockerfile here would let the tree move that row's
  trigger dimension under the check; no file here stands on an image this repo builds
  ([R-506](../refinements/tasks/506-a-built-row-that-became-a-base-would-spend-a-recorded-trigger.md)).
- `imagevolumes.py` is the record and nothing else; the inspect call, the format and the change
  report live in `imagedrift.py`, which never runs where the check does.

## Alternatives rejected

- **A second recipe outside `just check`**: makes the one exception a category.
- **Regenerate-and-diff for the stubs**: catches nothing a compiler would not, and misses comments.
- **Recording each resolved digest**: seeing a moved digest needs docker, and an upstream rebuild
  moves it without moving a declared path, so the record would change for no change in meaning.
- **A scheduled workflow running the recipe**: pulls multi-gigabyte images weekly into a job nobody
  watches; the third answer of decision 1 by another name.
- **Locking every image by digest**: unreadable compose files and constant bumps, to close a rare
  event whose symptom is clutter rather than lost data.
- **Building before inspecting**: minutes and gigabytes per run, and a build failing for an
  unrelated reason would stop the record being checked.
- **Deriving the built rows**, with or without `ONBUILD` as a third source: sound only while the
  list of sources is complete, and it was proved incomplete once.
- **Refusing a built image older than its Dockerfile**: a fresh clone makes every image older.

## Related

- Code: `scripts/volumecheck.py`, `imagevolumes.py`, `imagedrift.py`, `dockerfilevolumes.py`,
  `dockerfilebases.py`, `composeservices.py`, `composetargets.py`; recipes `check-volumecheck` and
  `image-volumes`.
- [Readings: what images declare](../readings/image-volumes.md);
  [repo checks](../modules/repo-checks.md).
- [ADR-0063](ADR-0063-compose-checks.md) (the other compose checks and the shared file list),
  [ADR-0057](ADR-0057-imap-probe-server.md) (the probe's tmpfs cover),
  [ADR-0011](ADR-0011-body-v1.md) (the one recipe outside `just check`),
  [ADR-0003](ADR-0003-generated-stubs.md) (the stub comparison).
