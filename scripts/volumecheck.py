"""Fail when a path a compose service must cover is one it mounts nothing over."""

import argparse
import sys
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import NamedTuple

from composefiles import ComposeSearchError, base_project, compose_files, refused_summary
from composeservices import ComposeFile, ComposeServiceError, Service, read_services
from dockerfilevolumes import undeclared
from imagedrift import Inspector, docker_volumes, report_drift
from imagevolumes import IMAGE_VOLUMES, RECORD_PATH, Row
from kernelcache import CACHE_VARIABLE, Source, kernel_caches

_UNCOVERED = (
    "service {service!r} runs {reference!r}, which declares VOLUME {path!r}, and mounts nothing "
    "there; docker gives the container an anonymous volume at that path and a `down` without "
    "--volumes leaves it on the host. Mount something at it, a tmpfs where the container writes "
    "nothing worth keeping."
)
_UNRECORDED = (
    "service {service!r} runs {reference!r}, which " + RECORD_PATH + " has no row for; an "
    "unrecorded image is an unasked question. Run `just image-volumes` to record what it declares."
)
_STALE = (
    "the record has a row for {reference!r}, which nothing here names, neither a compose service "
    "nor a Dockerfile these builds stand on; a row nothing names is a claim nothing can check. "
    "Drop the row, or name the image where it belongs."
)
_SUBSTITUTED = (
    "service {service!r} names its image as {reference!r}, and the record is keyed on the image a "
    "container really runs, which a substitution does not name. Write the image out."
)
_UNPROJECTED = (
    "service {service!r} builds its image and names none, so compose runs it as "
    "`<project>-{service}`, and no base compose file sets one project name for that to resolve to."
)


class Fault(NamedTuple):
    """One declared volume nothing covers, one stale record row, or one unreadable compose file."""

    path: str
    line: int
    detail: str


class Scan(NamedTuple):
    """What one walk of the compose files read, and what it could not account for."""

    files: int
    definitions: int
    declared: int
    names: tuple[str, ...]
    built: tuple[str, ...]
    dockerfiles: tuple[str, ...]
    findings: list[Fault]
    refused: tuple[Fault, ...] = ()
    unasked: tuple[Fault, ...] = ()
    carded: int = 0
    uncached: tuple[Fault, ...] = ()

    @property
    def faults(self) -> list[Fault]:
        """Every fault, unreadable files first, in the order `main` prints them."""
        return [*self.refused, *self.unasked, *self.findings, *self.uncached]


class Read(NamedTuple):
    """One compose file as the walk found it: what it declares, or why it could not be read."""

    path: Path
    name: str
    found: ComposeFile | None
    faults: list[Fault]
    text: str = ""


def read_file(root: Path, compose: Path) -> Read:
    """Read one compose file, turning every refusal into a fault on the file rather than a raise."""
    name = compose.relative_to(root).as_posix()
    try:
        text = compose.read_text(encoding="utf-8")
        found = read_services(text)
    except (OSError, UnicodeDecodeError, ComposeServiceError) as err:
        return Read(path=compose, name=name, found=None, faults=[Fault(name, 0, str(err))])
    return Read(path=compose, name=name, found=found, faults=[], text=text)


def uncovered(name: str, service: Service, reference: str, declared: Iterable[str]) -> list[Fault]:
    """Every path this image declares that the service running it mounts nothing at."""
    return [
        Fault(
            name,
            service.line,
            _UNCOVERED.format(service=service.name, reference=reference, path=path),
        )
        for path in declared
        if path not in service.covered
    ]


def check_file(root: Path, read: Read, base: str | None, records: Mapping[str, Row]) -> Scan:
    """Return what one compose file was read for, and every declared volume left uncovered."""
    if read.found is None:
        return Scan(1, 0, 0, (), (), (), [], tuple(read.faults))
    project = read.found.project or base
    definitions = paths = 0
    names: list[str] = []
    built: list[str] = []
    dockerfiles: list[str] = []
    faults: list[Fault] = []
    unasked: list[Fault] = []
    for service in read.found.services:
        if not service.defines:
            continue
        definitions += 1
        if service.image is None and project is None:
            unasked.append(
                Fault(read.name, service.line, _UNPROJECTED.format(service=service.name))
            )
            continue
        reference = service.image if service.image is not None else f"{project}-{service.name}"
        if "$" in reference:
            unasked.append(
                Fault(
                    read.name,
                    service.line,
                    _SUBSTITUTED.format(service=service.name, reference=reference),
                )
            )
            continue
        names.append(reference)
        if service.build is not None:
            built.append(reference)
        row = records.get(reference)
        if row is None:
            faults.append(
                Fault(
                    read.name,
                    service.line,
                    _UNRECORDED.format(service=service.name, reference=reference),
                )
            )
            continue
        paths += len(row.volumes)
        faults.extend(uncovered(read.name, service, reference, row.volumes))
        if service.build is not None:
            here = undeclared(root, read.path, service.build, reference, row.volumes, records)
            dockerfiles.extend(here.dockerfiles)
            names.extend(here.bases)
            faults.extend(Fault(read.name, service.line, detail) for detail in here.faults)
            unasked.extend(Fault(read.name, service.line, detail) for detail in here.unasked)
    walked = (tuple(names), tuple(built), tuple(dockerfiles))
    return Scan(1, definitions, paths, *walked, faults, unasked=tuple(unasked))


def check(root: Path, records: Mapping[str, Row] = IMAGE_VOLUMES) -> Scan:
    """Check every compose file under ``root``, then every recorded row against what they named."""
    reads = [read_file(root, compose) for compose in compose_files(root)]
    base = base_project(
        (read.path, read.found.project if read.found is not None else None) for read in reads
    )
    scans = [check_file(root, read, base, records) for read in reads]
    kept = kernel_caches(
        Source(read.name, read.text, read.found) for read in reads if read.found is not None
    )
    named = {name for scan in scans for name in scan.names}
    faults = [fault for scan in scans for fault in scan.findings]
    faults.extend(
        Fault(RECORD_PATH, 0, _STALE.format(reference=reference))
        for reference in sorted(records)
        if reference not in named
    )
    return Scan(
        files=len(scans),
        definitions=sum(scan.definitions for scan in scans),
        declared=sum(scan.declared for scan in scans),
        names=tuple(sorted(named)),
        built=tuple(sorted({name for scan in scans for name in scan.built})),
        dockerfiles=tuple(sorted({name for scan in scans for name in scan.dockerfiles})),
        findings=faults,
        refused=tuple(fault for scan in scans for fault in scan.refused),
        unasked=tuple(fault for scan in scans for fault in scan.unasked),
        carded=kept.carded,
        uncached=tuple(Fault(*lost) for lost in kept.faults),
    )


def main(argv: list[str] | None = None, inspect: Inspector = docker_volumes) -> int:
    """Run the check; print any faults and return the process exit code."""
    parser = argparse.ArgumentParser(
        description="Fail when a path a compose service must cover has no mount over it.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(),
        help="repo root holding the compose files (default: current directory)",
    )
    parser.add_argument(
        "--recompute",
        action="store_true",
        help="ask a real docker instead, and report every recorded row that has drifted",
    )
    args = parser.parse_args(argv)
    given: Path = args.root
    recomputing: bool = args.recompute
    if not given.is_dir():
        print(f"volumecheck: root {given} is not a directory", file=sys.stderr)
        return 2
    try:
        scanned = check(given.resolve())
    except ComposeSearchError as err:
        print(f"volumecheck: {err}", file=sys.stderr)
        return 2
    if recomputing:
        return report_drift(scanned.names, scanned.built, IMAGE_VOLUMES, inspect)
    for fault in scanned.faults:
        print(f"{fault.path}:{fault.line}: {fault.detail}")
    if scanned.refused:
        unread = "no service in them was checked"
        print(refused_summary("volumecheck", len(scanned.refused), unread), file=sys.stderr)
    if scanned.unasked:
        print(
            f"\nvolumecheck: {len(scanned.unasked)} image(s) could not be asked what they declare, "
            "because the image a service runs could not be named or the Dockerfile that builds it "
            "could not be read, so nothing was compared with the record. Write the name or the "
            "path out, as each one's own fault says.",
            file=sys.stderr,
        )
    if scanned.findings:
        print(
            f"\nvolumecheck: {len(scanned.findings)} image volume declaration(s) go uncovered or "
            f"unrecorded. Mount something at the path, or bring {RECORD_PATH} back in step with "
            "the tree by running `just image-volumes`.",
            file=sys.stderr,
        )
    if scanned.uncached:
        print(
            f"\nvolumecheck: {len(scanned.uncached)} problem(s) with where a service given the "
            f"card writes its compiled kernels. Set {CACHE_VARIABLE} for the service to a "
            "directory under a named volume or a bind, with the path written out.",
            file=sys.stderr,
        )
    if scanned.faults:
        return 1
    print(
        f"volumecheck OK: {scanned.declared} declared volume path(s) under {given} are covered, "
        f"over {scanned.files} compose file(s), {scanned.definitions} service definition(s) and "
        f"{len(scanned.names)} image(s) counting the bases those builds stand on, and "
        f"{len(scanned.dockerfiles)} Dockerfile(s) here declare and inherit nothing their row "
        f"does not contain, triggers included; {scanned.carded} service(s) given the card set "
        f"{CACHE_VARIABLE} to a directory under a mount"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover -- CLI entry point; main() is unit-tested
    sys.exit(main())
