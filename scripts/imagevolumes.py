"""What each image a compose file names declares as a VOLUME, recorded here so a gate can ask.

A `VOLUME` in an image is a promise docker keeps whether or not a compose file mounts anything
there. A container started with nothing at that path gets an **anonymous** volume, filled from the
image and left on the host by the `docker compose down` that did not say `--volumes`, under a
generated name nobody chose and nothing later reads. One per start. The probe stack already met
this once and answered it, `docker-compose.imap-probe.yml` mounting a tmpfs over both of dovecot's
declarations, and it answered it by one act of remembering rather than by anything that checks.
This record is what lets something check.

**Why the fact is recorded rather than read.** The question is docker's to answer, and `just
check` has to run on a clean dev box and in CI, where there is no daemon and no image pulled. A
gate that shelled out to `docker image inspect` would be unrunnable there, and one recipe is
already deliberately outside the single gate for needing system libraries; nothing else may join
it. So the out-of-reach fact is brought into the tree instead: the table below is the answer
docker gave, `volumecheck.py` compares it against what the compose files mount, and `just
image-volumes` asks docker again and reports every row that has since drifted. That is the shape
`docs/refinements/index.md` already has, a recorded artifact with a gate over it and a recipe that
regenerates it. The asking is `imagedrift.py`, which is where the format each row was measured
with lives, and it is a file of its own because a record and the daemon call that re-derives it
are two jobs, one of which never runs where the other one does.

**Each row has two dimensions, because a base declares a volume in two ways.** `Config.Volumes` is
what an image declares about itself; `Config.OnBuild` is what it declares about whatever is built
`FROM` it. A base carrying `ONBUILD VOLUME /x` has an empty `Config.Volumes` of its own, the build
of anything standing on it fires the trigger and declares `/x`, and the instruction clears in the
child, so nothing in the built image records where the path came from (measured against docker
29.7.2 on 2026-08-30, under BuildKit and under `DOCKER_BUILDKIT=0` alike; docker writes the trigger
down verbatim, cased as the file wrote it and with any continuation already joined). Both
dimensions are asked in one `docker image inspect`, which is what keeps a row from half-existing:
an image is measured or it is not, and which images are recorded is one fact spelled once.

**The trigger dimension is recorded raw**, one whole instruction per entry as docker hands it over,
rather than the paths those entries resolve to. What docker says is the fact this file exists to
hold, and a path is a reading of it: a reading taken once, on the machine that ran the recipe,
could not be checked by the gate everyone runs, and it would leave `just image-volumes` comparing a
real image against a derivation rather than against a second reading of the same image.
`dockerfilevolumes.py` spends the entries instead, with the reader it already has for a `VOLUME`
argument, and a trigger nobody here can read is a fault on every run rather than a silence recorded
once.

Two of the ten answer with a path. The other eight declare nothing, and a row saying so is worth
as much as a row saying otherwise: it is what lets the gate tell an image whose silence was
measured from one nobody has asked about yet.

**The three built rows are named the way compose names them.** A service that only builds runs an
image compose tags `<project>-<service>`, which is why `cortex-brain` and `cortex-mcp-email` are
spelled here and why `docker inspect cortex-brain-1` is the container beside them in the runbooks.
`cortex-model-host` is the same name written out, its compose service naming the tag itself
because a second Dockerfile in one context needs one.

**The two base rows exist because a built row cannot be re-derived.** A built row is asked without
a pull, having no registry to be refreshed from, so its answer is whatever the machine running the
recipe last built, and a build inherits whatever its base declared on the day it ran. This record
used to hold no row for `python:3.12-slim-trixie` or `ghcr.io/ggml-org/llama.cpp:server-cuda` on
the grounds that no compose file names either and that what they declare is already inherited into
the image a container really runs. The first half is still true and the second was the mistake:
inherited into the image this machine last built, which is not the image the next build produces.
Both are moving tags, so they are recorded and pulled like every other registry reference, and
`dockerfilebases.py` holds each built row to carrying what its base's row carries, in both
dimensions: what the base declares, and what its triggers would declare on the next build. A base
republished with a new `VOLUME`, or with a new `ONBUILD VOLUME`, then reddens the gate on the next
re-derivation instead of waiting for somebody to rebuild. The bases of the *builder* stages get no
row for the reason the old paragraph gave about all of them: a builder stage's declarations were
measured not to reach the built image at all, so no container ever runs them.

**The three built rows are recorded and not derived**, which is the step a reader takes straight
out of the paragraph above and is answered on a measurement rather than on taste. With a base row
beside each Dockerfile, what a built image declares looks computable: the union of what the file
declares and what its base's row carries. That union is a floor under the answer and never a
ceiling, which was measured rather than argued, and reading the trigger dimension raises the floor
without turning it into a ceiling. It closes the one way past it that the measurement found; what
the record has to survive is a base gaining a mechanism nobody here enumerated, and an enumeration
believed complete is the shape of claim this one already falsified once. A derived row would be
computed from sources that can all say nothing while every container of the image takes an
anonymous volume, which is the leak this file exists to prevent, arriving through the gate rather
than past it. A row read off a real built image carries whatever produced the declaration,
enumerated here or not. That is also why the rules over these rows are one-directional: a built row
is *supposed* to be able to carry more than the tree can read.
"""

from typing import NamedTuple


class Row(NamedTuple):
    """One image as docker answered about it: what it declares, and what it declares for a child.

    ``volumes`` is `Config.Volumes`, sorted, and is what a container of this image gets an
    anonymous volume at. ``onbuild`` is `Config.OnBuild` in docker's own order, one raw
    instruction per entry, and is what the build of anything standing `FROM` this image would
    declare. Both are the empty tuple for the image that carries neither, which is a measured
    answer and not a missing one.
    """

    volumes: tuple[str, ...]
    onbuild: tuple[str, ...]


# The answer docker gave, image reference to what it declares of its own and what its triggers
# would declare in a child. An empty tuple is a measured answer and not a missing one, in either
# dimension. Regenerate with `just image-volumes`.
IMAGE_VOLUMES: dict[str, Row] = {
    # The probe's dovecot, whose two declarations the probe file already mounts a tmpfs over.
    "dovecot/dovecot:2.3.21": Row(("/etc/dovecot", "/srv/mail"), ()),
    # Postgres' data directory, declared by the image whether or not the service is a database:
    # the memory stack runs this image twice, once as the server and once as the pg_dump sidecar.
    "pgvector/pgvector:pg16": Row(("/var/lib/postgresql/data",), ()),
    "ghcr.io/ggml-org/llama.cpp:server": Row((), ()),
    "node:22-bookworm-slim": Row((), ()),
    "redis:8-alpine": Row((), ()),
    "cortex-brain": Row((), ()),
    "cortex-mcp-email": Row((), ()),
    "cortex-model-host": Row((), ()),
    # The two bases the rows above are built on, named by a Dockerfile here rather than by a
    # compose file, and pulled on every re-derivation because a built row cannot be. Every row
    # above was re-derived in both dimensions on 2026-08-30, the day the trigger dimension was
    # added; the paths in them were first measured on 2026-08-25, and the two rows here on
    # 2026-08-28.
    "python:3.12-slim-trixie": Row((), ()),
    "ghcr.io/ggml-org/llama.cpp:server-cuda": Row((), ()),
}

# Where a row is edited, named here so the gate reporting a stale or missing one can say where to
# go. It is this module's own path from the repo root, which is the one place the table lives.
RECORD_PATH = "scripts/imagevolumes.py"
