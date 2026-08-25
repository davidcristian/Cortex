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

**How it was measured.** Once per image named by a compose file under `docker/`, on 2026-08-25,
with the same format string `docker_volumes` below spends, which is `INSPECT_FORMAT`:

    docker image inspect --format "$INSPECT_FORMAT" <image>

Two of the eight answer with a path. The other six declare nothing, and a row saying so is worth
as much as a row saying otherwise: it is what lets the gate tell an image whose silence was
measured from one nobody has asked about yet.

**The three built rows are named the way compose names them.** A service that only builds runs an
image compose tags `<project>-<service>`, which is why `cortex-brain` and `cortex-mcp-email` are
spelled here and why `docker inspect cortex-brain-1` is the container beside them in the runbooks.
`cortex-model-host` is the same name written out, its compose service naming the tag itself
because a second Dockerfile in one context needs one. No row exists for the base images those
three are built from, `python:3.12-slim-trixie` and `ghcr.io/ggml-org/llama.cpp:server-cuda`,
because no compose file names either: whatever they declare is already inherited into the built
image, which is the thing a container actually runs and the thing measured above.
"""

import subprocess
from collections.abc import Callable, Iterable, Mapping

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
}

# Where a row is edited, named here so the gate reporting a stale or missing one can say where to
# go. It is this module's own path from the repo root, which is the one place the table lives.
RECORD_PATH = "scripts/imagevolumes.py"

# One path per line, which is the only shape `docker_volumes` has to parse back.
INSPECT_FORMAT = "{{range $path, $_ := .Config.Volumes}}{{$path}}\n{{end}}"

# How a rederivation asks about one image. The fake in the tests satisfies the same signature,
# which is what keeps the comparison below testable without a daemon.
Inspector = Callable[[str], tuple[str, ...]]


class InspectError(Exception):
    """Docker could not be asked what an image declares, so no row can be compared against it."""


def render(paths: Iterable[str]) -> str:
    """The paths as a report should show them, an image declaring none saying so in words."""
    written = ", ".join(paths)
    return written or "nothing"


def docker_volumes(reference: str) -> tuple[str, ...]:  # pragma: no cover -- needs a real docker
    """Ask the local docker what one image declares, which only a machine holding it can do.

    The thin adapter, and the only part of this module a coverage gate cannot reach. Everything
    that decides anything is in `rederive`, which takes any inspector and is tested against a fake.
    """
    try:
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
) -> list[str]:
    """Ask ``inspect`` about every image, and report each row that no longer says what it says.

    Both directions are asked, over the union of what the compose files name and what the record
    holds, because a row that has gone stale and an image nobody recorded are the same drift
    arriving from opposite sides. An image docker cannot answer about is reported rather than
    skipped: a rederivation that quietly left a row unverified would confirm the record it was run
    to doubt.
    """
    report: list[str] = []
    for reference in sorted({*references, *records}):
        recorded = records.get(reference)
        try:
            found = inspect(reference)
        except InspectError as err:
            report.append(f"{reference}: {err}")
            continue
        if recorded is None:
            report.append(f"{reference}: docker says {render(found)}, and the record has no row")
        elif tuple(sorted(recorded)) != found:
            report.append(f"{reference}: recorded {render(recorded)}, docker says {render(found)}")
    return report
