"""How docker is asked what an image declares, and every recorded row that has stopped agreeing.

`imagevolumes.py` is the answer docker gave, written into the tree so `just check` can ask it with
no daemon. This module is the other half: the one call that asks a real docker, the shape its
answer has to have, and the comparison `just image-volumes` runs behind `volumecheck.py
--rederive`. The gate reads the record; this re-derives it, and the two are separate files because
they are two jobs, one of which never runs where the other one does.

How a row was measured: once per image this repo names, on the date beside its row, with the same
format string `docker_volumes` below spends, which is `INSPECT_FORMAT`:

    docker image inspect --format "$INSPECT_FORMAT" <image>

A re-derivation pulls first, which is what lets it see anything at all. `docker image
inspect` answers out of the local cache and never reaches a registry, so on a machine holding a
month-old copy of a moving tag it confirms a month-old image under a name the registry has since
republished. Half these references are moving tags by design, `ghcr.io/ggml-org/llama.cpp:server`
most of all, and the failure this record has to survive is exactly a publisher adding a `VOLUME`
to a tag nobody re-pinned. An inspect of the cache cannot see that, so `rederive` refreshes every
registry reference before asking about it, and a pull that fails is reported rather than answered
out of whatever the cache already held. The three images this repo builds are the exception,
having no registry to be refreshed from: their answer is the local build, which is what a
container here really runs.

Reading the answer back is not the adapter's job. `docker_volumes` runs the process and hands
its output to `parse`, which decides what a well-formed answer is, so the shape every row is
compared against lives in code a coverage gate reaches. An answer `parse` refuses is reported as a
row that could not be checked, never resolved to an empty one: an image whose reading failed and
an image declaring nothing are opposite answers.
"""

import json
import subprocess
import sys
from collections.abc import Iterable, Mapping
from typing import Protocol, cast

from imagevolumes import RECORD_PATH, Row

# Two lines, one JSON document each: what the image declares, then the triggers it fires in a
# child. JSON rather than a line per entry, because a trigger is arbitrary instruction text and
# JSON keeps whatever it contains, a newline included, on the one line `parse` reads it back off.
INSPECT_FORMAT = "{{json .Config.Volumes}}\n{{json .Config.OnBuild}}"

# What `INSPECT_FORMAT` prints, and the count `parse` refuses any other answer against.
INSPECT_LINES = 2


class Inspector(Protocol):
    """How a rederivation asks about one image, and whether to refresh it from its registry first.

    The fake in the tests satisfies the same signature, which is what keeps the comparison below
    testable without a daemon.
    """

    def __call__(self, reference: str, *, pull: bool) -> Row: ...


class InspectError(Exception):
    """Docker could not be asked what an image declares, so no row can be compared against it."""


def render(paths: Iterable[str]) -> str:
    """The paths as a report should show them, an image declaring none saying so in words."""
    written = ", ".join(paths)
    return written or "nothing"


def _document(written: str, dimension: str) -> object:
    """One line of docker's answer, read back as the JSON document the format printed there."""
    try:
        return json.loads(written)
    except json.JSONDecodeError as err:
        msg = f"docker's {dimension} is not the JSON the format asked for: {err}"
        raise InspectError(msg) from err


def parse(output: str) -> Row:
    """The two lines `INSPECT_FORMAT` prints, read back into the row they describe."""
    lines = output.splitlines()
    if len(lines) != INSPECT_LINES:
        msg = f"docker answered in {len(lines)} line(s) where the format prints {INSPECT_LINES}"
        raise InspectError(msg)
    declared = _document(lines[0], "Config.Volumes")
    triggers = _document(lines[1], "Config.OnBuild")
    if declared is not None and not isinstance(declared, dict):
        msg = f"docker's Config.Volumes is {declared!r}, which is not an object of paths"
        raise InspectError(msg)
    if triggers is not None and not isinstance(triggers, list):
        msg = f"docker's Config.OnBuild is {triggers!r}, which is not a list of instructions"
        raise InspectError(msg)
    entries = [] if triggers is None else cast("list[object]", triggers)
    for entry in entries:
        if not isinstance(entry, str):
            msg = f"docker's Config.OnBuild carries {entry!r}, which is not an instruction"
            raise InspectError(msg)
    paths = () if declared is None else tuple(sorted(cast("dict[str, object]", declared)))
    return Row(paths, tuple(cast("list[str]", entries)))


def docker_volumes(  # pragma: no cover -- needs a real docker
    reference: str, *, pull: bool
) -> Row:
    """Ask docker what one image declares, refreshing it from its registry first when it has one.

    The thin adapter, and the only part of this module a coverage gate cannot reach. Everything
    that decides anything is in `parse` and `rederive`, which take any output and any inspector and
    are tested against fakes. The pull is what makes the answer a fact about the registry rather
    than about this machine's cache, which the module docstring argues.
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
    return parse(result.stdout)


def _disagreements(reference: str, recorded: Row, found: Row) -> list[str]:
    """Every dimension of one row docker no longer agrees with, each reported on its own.

    The paths are compared as a set, since which paths an image declares is the question and the
    order a row lists them in is a tidiness. The triggers are compared as written: they fire in
    order, so two orders are two images, and the record holds what docker said rather than a
    reading of it.
    """
    report: list[str] = []
    if tuple(sorted(recorded.volumes)) != found.volumes:
        report.append(
            f"{reference}: recorded {render(recorded.volumes)}, docker says {render(found.volumes)}"
        )
    if recorded.onbuild != found.onbuild:
        report.append(
            f"{reference}: recorded ONBUILD {render(recorded.onbuild)}, docker says ONBUILD "
            f"{render(found.onbuild)}"
        )
    return report


def rederive(
    references: Iterable[str],
    records: Mapping[str, Row],
    inspect: Inspector,
    built: Iterable[str] = (),
) -> list[str]:
    """Ask ``inspect`` about every image, and report each row that no longer says what it says.

    Both directions are asked, over the union of what the compose files name and what the record
    holds, because a row that has gone stale and an image nobody recorded are the same drift
    arriving from opposite sides. An image docker cannot answer about is reported rather than
    skipped: a re-derivation that left a row unverified would confirm the record it was run to
    doubt. Asking a stale cache confirms it just as wrongly, which is why every reference outside
    ``built`` is refreshed before it is asked about.
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
            report.append(
                f"{reference}: docker says {render(found.volumes)} and ONBUILD "
                f"{render(found.onbuild)}, and the record has no row"
            )
            continue
        report.extend(_disagreements(reference, recorded, found))
    return report


def report_drift(
    names: Iterable[str],
    built: Iterable[str],
    records: Mapping[str, Row],
    inspect: Inspector,
) -> int:
    """Ask a real docker about the record, print every row that has drifted, and exit on it.

    The re-derivation's outer half, and it lives here rather than beside the rule it re-derives
    for: every name it touches is this module's or the record's, and the gate above it answers a
    different question.
    """
    references, local = list(names), list(built)
    report = rederive(references, records, inspect, local)
    for line in report:
        print(line)
    if report:
        print(
            f"\nvolumecheck: {len(report)} recorded reading(s) disagree with docker. Edit the "
            f"table in {RECORD_PATH} to what docker says, and cover any newly declared path in "
            "the compose file whose service runs that image.",
            file=sys.stderr,
        )
        return 1
    print(
        f"volumecheck: the record agrees with docker on all {len({*references, *records})} "
        f"image(s), in what each declares and in what each would declare for a child, "
        f"{len(local)} of them built here and the rest pulled before they were asked"
    )
    return 0
