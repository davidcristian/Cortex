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
regenerates it.

**How it was measured.** Once per image this repo names, on the date beside its row, with the same
format string `docker_volumes` below spends, which is `INSPECT_FORMAT`:

    docker image inspect --format "$INSPECT_FORMAT" <image>

**A re-derivation pulls first, and that is the whole reason it can see anything.** `docker image
inspect` answers out of the local cache and never reaches a registry, so on a machine holding a
month-old copy of a moving tag it confirms a month-old image under a name the registry has since
republished. Half these references are moving tags by design, `ghcr.io/ggml-org/llama.cpp:server`
most of all, and the failure this record has to survive is exactly a publisher adding a `VOLUME`
to a tag nobody re-pinned. An inspect of the cache cannot see that, so `rederive` refreshes every
registry reference before asking about it, and a pull that fails is reported rather than answered
from whatever was lying around. The three images this repo builds are the exception, having no
registry to be refreshed from: their answer is the local build, which is the thing a container
here really runs.

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
`dockerfilebases.py` holds each built row to carrying what its base's row carries. A base
republished with a new `VOLUME` then reddens the gate on the next re-derivation instead of waiting
for somebody to rebuild. The bases of the *builder* stages get no row for the reason the old
paragraph gave about all of them: a builder stage's declarations were measured not to reach the
built image at all, so no container ever runs them.

**The three built rows are recorded and not derived**, which is the step a reader takes straight
out of the paragraph above and is answered on a measurement rather than on taste. With a base row
beside each Dockerfile, what a built image declares looks computable: the union of what the file
declares and what its base's row carries. That union is a floor under the answer and never a
ceiling. A base whose only instruction is `ONBUILD VOLUME /probe/onbuild` declares no volume of its
own, so its row here would be the empty tuple both real bases carry today, and an image built
`FROM` it by a Dockerfile with no `VOLUME` instruction at all declares `/probe/onbuild` (measured
against docker 29.7.2 on 2026-08-29, under both builders, and the instruction clears in the child
so nothing there records that it was ever present). A derived row would be empty while every
container of that image takes an anonymous volume, which is the leak this file exists to prevent,
arriving through the gate rather than past it. A row read off a real built image carries whatever
produced the declaration, enumerated here or not. That is also why the two rules over these rows
are one-directional: a built row is *supposed* to be able to carry more than the tree can read.
"""

import subprocess
import sys
from collections.abc import Iterable, Mapping
from typing import Protocol

# The answer docker gave, image reference to the volume paths it declares, sorted. An empty tuple
# is a measured answer and not a missing one. Regenerate with `just image-volumes`.
IMAGE_VOLUMES: dict[str, tuple[str, ...]] = {
    # The probe's dovecot, whose two declarations the probe file already mounts a tmpfs over.
    "dovecot/dovecot:2.3.21": ("/etc/dovecot", "/srv/mail"),
    # Postgres' data directory, declared by the image whether or not the service is a database:
    # the memory stack runs this image twice, once as the server and once as the pg_dump sidecar.
    "pgvector/pgvector:pg16": ("/var/lib/postgresql/data",),
    "ghcr.io/ggml-org/llama.cpp:server": (),
    "node:22-bookworm-slim": (),
    "redis:8-alpine": (),
    "cortex-brain": (),
    "cortex-mcp-email": (),
    "cortex-model-host": (),
    # The two bases the rows above are built on, named by a Dockerfile here rather than by a
    # compose file, and pulled on every re-derivation because a built row cannot be. Measured
    # 2026-08-28; the eight rows above were measured 2026-08-25.
    "python:3.12-slim-trixie": (),
    "ghcr.io/ggml-org/llama.cpp:server-cuda": (),
}

# Where a row is edited, named here so the gate reporting a stale or missing one can say where to
# go. It is this module's own path from the repo root, which is the one place the table lives.
RECORD_PATH = "scripts/imagevolumes.py"

# One path per line, which is the only shape `docker_volumes` has to parse back.
INSPECT_FORMAT = "{{range $path, $_ := .Config.Volumes}}{{$path}}\n{{end}}"


class Inspector(Protocol):
    """How a rederivation asks about one image, and whether to refresh it from its registry first.

    The fake in the tests satisfies the same signature, which is what keeps the comparison below
    testable without a daemon.
    """

    def __call__(self, reference: str, *, pull: bool) -> tuple[str, ...]: ...


class InspectError(Exception):
    """Docker could not be asked what an image declares, so no row can be compared against it."""


def render(paths: Iterable[str]) -> str:
    """The paths as a report should show them, an image declaring none saying so in words."""
    written = ", ".join(paths)
    return written or "nothing"


def docker_volumes(  # pragma: no cover -- needs a real docker
    reference: str, *, pull: bool
) -> tuple[str, ...]:
    """Ask docker what one image declares, refreshing it from its registry first when it has one.

    The thin adapter, and the only part of this module a coverage gate cannot reach. Everything
    that decides anything is in `rederive`, which takes any inspector and is tested against a fake.
    The pull is what makes the answer a fact about the registry rather than about this machine's
    cache; the module docstring says why that is the difference between a re-derivation and a
    confirmation of whatever was already here.
    """
    try:
        if pull:
            fetched = subprocess.run(  # noqa: S603 -- fixed argv, no shell
                ["docker", "pull", "--quiet", reference],  # noqa: S607
                capture_output=True,
                check=False,
                text=True,
            )
            if fetched.returncode != 0:
                msg = f"docker pull failed: {fetched.stderr.strip()}"
                raise InspectError(msg)
        result = subprocess.run(  # noqa: S603 -- fixed argv, no shell
            ["docker", "image", "inspect", "--format", INSPECT_FORMAT, reference],  # noqa: S607
            capture_output=True,
            check=False,
            text=True,
        )
    except OSError as err:
        msg = f"cannot run docker: {err}"
        raise InspectError(msg) from err
    if result.returncode != 0:
        msg = f"docker image inspect failed: {result.stderr.strip()}"
        raise InspectError(msg)
    return tuple(sorted(line.strip() for line in result.stdout.splitlines() if line.strip()))


def rederive(
    references: Iterable[str],
    records: Mapping[str, tuple[str, ...]],
    inspect: Inspector,
    built: Iterable[str] = (),
) -> list[str]:
    """Ask ``inspect`` about every image, and report each row that no longer says what it says.

    Both directions are asked, over the union of what the compose files name and what the record
    holds, because a row that has gone stale and an image nobody recorded are the same drift
    arriving from opposite sides. An image docker cannot answer about is reported rather than
    skipped: a rederivation that quietly left a row unverified would confirm the record it was run
    to doubt, and asking a stale cache is the same confirmation wearing a green face, which is why
    every reference outside ``built`` is refreshed before it is asked about.
    """
    report: list[str] = []
    local = set(built)
    for reference in sorted({*references, *records}):
        recorded = records.get(reference)
        try:
            found = inspect(reference, pull=reference not in local)
        except InspectError as err:
            report.append(f"{reference}: {err}")
            continue
        if recorded is None:
            report.append(f"{reference}: docker says {render(found)}, and the record has no row")
        elif tuple(sorted(recorded)) != found:
            report.append(f"{reference}: recorded {render(recorded)}, docker says {render(found)}")
    return report


def report_drift(
    names: Iterable[str],
    built: Iterable[str],
    records: Mapping[str, tuple[str, ...]],
    inspect: Inspector,
) -> int:
    """Ask a real docker about the record, print every row that has drifted, and exit on it.

    The re-derivation's other half, and it lives beside the record rather than beside the rule it
    keeps honest: every name it touches is this module's, and the gate above it answers a
    different question entirely.
    """
    references, local = list(names), list(built)
    report = rederive(references, records, inspect, local)
    for line in report:
        print(line)
    if report:
        print(
            f"\nvolumecheck: {len(report)} recorded row(s) disagree with docker. Edit the table in "
            f"{RECORD_PATH} to what docker says, and cover any newly declared path in the compose "
            "file whose service runs that image.",
            file=sys.stderr,
        )
        return 1
    print(
        f"volumecheck: the record agrees with docker on all {len({*references, *records})} "
        f"image(s), {len(local)} of them built here and the rest pulled before they were asked"
    )
    return 0
