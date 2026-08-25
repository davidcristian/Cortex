"""What each image a compose file names declares as a VOLUME, recorded here so a gate can ask."""

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
    """Ask ``inspect`` about every image, and report each row that no longer says what it says."""
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
