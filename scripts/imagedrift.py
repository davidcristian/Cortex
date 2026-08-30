"""How docker is asked what an image declares, and every recorded row that has stopped agreeing."""

import json
import subprocess
import sys
from collections.abc import Iterable, Mapping
from typing import Protocol, cast

from imagevolumes import RECORD_PATH, Row

# Two lines, one JSON document each: what the image declares, then the triggers it fires in a
# child. JSON keeps a trigger's arbitrary text, a newline included, on the one line `parse`
# reads it back off.
INSPECT_FORMAT = "{{json .Config.Volumes}}\n{{json .Config.OnBuild}}"

INSPECT_LINES = 2


class Inspector(Protocol):
    """How this check asks docker about one image, and whether to refresh it from its registry."""

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
    """Ask docker what one image declares, refreshing it from its registry first when it has one."""
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
    """Every dimension of one row docker no longer agrees with, each reported on its own."""
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
    """Ask ``inspect`` about every image, and report each row docker no longer agrees with."""
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
    """Ask a real docker about the record, print every row that has drifted, and exit on it."""
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
