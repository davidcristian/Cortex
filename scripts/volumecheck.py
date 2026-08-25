"""Repo gate: fail when an image a compose file names declares a volume the service leaves open.

A `VOLUME` in an image is a promise docker keeps whether or not a compose file mounts anything
there. Start a container with nothing at that path and docker makes an **anonymous** volume for
it, filled from the image, and the `docker compose down` that did not say `--volumes` leaves it on
the host under a generated name nobody chose and nothing later reads, one per start. It is the
same class of defect `bindcheck.py` guards, arriving from the other side of the mount: that one
watches a bind source materialize a directory inside the tree, this one watches an image's own
declaration materialize a volume beside it.

**The rule.** Every path an image declares must be covered, by the service that runs it, in the
same file, with a mount or a tmpfs at exactly that path. Exactly that path, because docker's
declaration is at a path and a mount over the parent leaves it standing. Which kind of cover is
none of the gate's business: a named volume is a deliberate durable store, a bind is the host's
own disk, and a tmpfs is how a container that writes nothing worth keeping gives the declaration
nothing to anonymise, which is what `docker-compose.imap-probe.yml` does for both of dovecot's.

**Per file, not per layered stack.** `just up` runs the base file alone, so a service whose
declared volume were covered only by an override really would leak, and the reader deliberately
does not merge (`composeservices.py` says so at greater length). A service naming neither an image
nor a build is a fragment of one defined elsewhere; it asks nothing here.

**The second rule, for the images this repo builds.** Three rows are images built from Dockerfiles
in this tree, and for those the record can move under the gate from inside the tree rather than
from a registry. So every path such a Dockerfile declares must appear in the row for the image
built from it, which is `dockerfilevolumes.py`'s question and runs on the mapping the walk already
reads from each service's `build:`. It is one-directional: a recorded path the Dockerfile does not
declare is inherited from a base image the record deliberately holds no row for.

**Where the answer comes from.** Docker's, recorded in `imagevolumes.py`, because `just check` runs
on a clean dev box and in CI where there is neither daemon nor image. `--rederive` is the other
half, hand-run behind `just image-volumes`: it pulls every image the compose files name, asks a
real docker what each declares, and reports each row that has drifted. The pull is not a
convenience: most of these references are moving tags, an inspect answers out of the local cache,
and reading the cache would confirm a month-old image under a name the registry has republished.
The images this repo builds are asked without one, having no registry to refresh from. It answers
that one question and not this one, so a leak found by the gate is reported by the gate.

**Fail closed** in three more directions than the rule itself, because a recorded fact only helps
while the record and the tree still describe each other. An image no row knows is an unasked
question, not a pass. A row no compose file names is a claim nothing can check. An image spelled
through a substitution cannot be keyed on at all, since the record is keyed on what a container
really runs. Add to those the walk's own floor, no compose file at all being `composefiles.py`'s
refusal, shared with `bindcheck.py` and `defaultcheck.py` so the three cannot drift apart about
which files exist, and a compose file the reader will not guess at being a fault rather than a
skip. A tree where nothing defines a service needs no floor of its own: every recorded row is
then unnamed, and the gate reddens a row at a time.

**The success line states what the walk read**: the declared paths it checked, the files, the
service definitions, the distinct images those definitions named, and the distinct Dockerfiles it
followed those builds to. Five numbers, none derivable from another, since one image is named by
several services, one Dockerfile builds two of the rows, and most images declare no path at all.
They are a reading and nothing asserts them.
"""

import argparse
import sys
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import NamedTuple

from composefiles import COMPOSE_STEMS, ComposeSearchError, compose_files
from composeservices import ComposeFile, ComposeServiceError, Service, read_services
from dockerfilevolumes import undeclared
from imagevolumes import IMAGE_VOLUMES, RECORD_PATH, Inspector, docker_volumes, report_drift

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
    "the record has a row for {reference!r}, which no compose file names; a row nothing names is a "
    "claim nothing can check. Drop the row, or name the image where it belongs."
)
_SUBSTITUTED = (
    "service {service!r} names its image as {reference!r}, and the record is keyed on the image a "
    "container really runs, which a substitution does not spell. Write the image out."
)
_UNPROJECTED = (
    "service {service!r} builds its image and names none, so compose runs it as "
    "`<project>-{service}`, and no base compose file pins one project name for that to resolve to."
)


class Fault(NamedTuple):
    """One image declaration nothing covers, one record row out of step, or one unreadable file."""

    path: str
    line: int
    detail: str


class Scan(NamedTuple):
    """One walk of the compose files: what it read, then what it could not account for.

    ``check_file`` returns one of these per file, so the whole walk is their sum, except for the
    stale rows, which only the whole walk can know about. ``declared`` counts per definition and
    not per image: two services running one image are two containers, and each gets its own
    anonymous volume. ``built`` is the subset of ``names`` a compose file builds here, which the
    gate itself has no use for and a re-derivation cannot do without: those are the references no
    registry can be asked to refresh. ``dockerfiles`` is what those builds were followed to, the
    files whose own declarations were read against the rows they build.
    """

    files: int
    definitions: int
    declared: int
    names: tuple[str, ...]
    built: tuple[str, ...]
    dockerfiles: tuple[str, ...]
    faults: list[Fault]


class Read(NamedTuple):
    """One compose file as the walk found it: what it declares, or why it could not be read."""

    path: Path
    name: str
    found: ComposeFile | None
    faults: list[Fault]


def read_file(root: Path, compose: Path) -> Read:
    """Read one compose file, turning every refusal into a fault on the file rather than a raise."""
    name = compose.relative_to(root).as_posix()
    try:
        found = read_services(compose.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ComposeServiceError) as err:
        return Read(path=compose, name=name, found=None, faults=[Fault(name, 0, str(err))])
    return Read(path=compose, name=name, found=found, faults=[])


def base_project(reads: Iterable[Read]) -> str | None:
    """The project name an override with none of its own inherits, taken from the base file.

    Compose runs a service that only builds under an image called `<project>-<service>`, so a row
    can only be keyed once the project is known, and an override does not pin one: it is layered
    onto the base and takes the base's. The base is the file compose reads when handed no `-f` at
    all, which is the one whose stem is bare (`composefiles.py` spells the two bare stems). Exactly
    one such file must pin a name. None and several are both an answer this gate will not guess at,
    and a build-only service then draws a fault of its own rather than a silently wrong row.
    """
    pinned = [
        read.found.project
        for read in reads
        if read.found is not None
        and read.found.project is not None
        and read.path.stem in COMPOSE_STEMS
    ]
    return pinned[0] if len(pinned) == 1 else None


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


def check_file(
    root: Path, read: Read, base: str | None, records: Mapping[str, tuple[str, ...]]
) -> Scan:
    """Return what one compose file offered the gate, and every declaration left open in it."""
    if read.found is None:
        return Scan(1, 0, 0, (), (), (), read.faults)
    project = read.found.project or base
    definitions = paths = 0
    names: list[str] = []
    built: list[str] = []
    dockerfiles: list[str] = []
    faults: list[Fault] = []
    for service in read.found.services:
        if not service.defines:
            continue  # a fragment layered onto the file that names the image; it asks nothing here
        definitions += 1
        if service.image is None and project is None:
            faults.append(Fault(read.name, service.line, _UNPROJECTED.format(service=service.name)))
            continue
        reference = service.image if service.image is not None else f"{project}-{service.name}"
        if "$" in reference:
            faults.append(
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
        paths += len(row)
        faults.extend(uncovered(read.name, service, reference, row))
        if service.build is not None:
            here = undeclared(root, read.path, service.build, reference, row)
            dockerfiles.extend(here.dockerfiles)
            faults.extend(Fault(read.name, service.line, detail) for detail in here.faults)
    return Scan(1, definitions, paths, tuple(names), tuple(built), tuple(dockerfiles), faults)


def check(root: Path, records: Mapping[str, tuple[str, ...]] = IMAGE_VOLUMES) -> Scan:
    """Check every compose file under ``root``, then every recorded row against what they named."""
    reads = [read_file(root, compose) for compose in compose_files(root)]
    scans = [check_file(root, read, base_project(reads), records) for read in reads]
    named = {name for scan in scans for name in scan.names}
    faults = [fault for scan in scans for fault in scan.faults]
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
        faults=faults,
    )


def main(argv: list[str] | None = None, inspect: Inspector = docker_volumes) -> int:
    """Run the gate; print any faults and return the process exit code."""
    parser = argparse.ArgumentParser(
        description="Fail when an image a compose file names declares a volume nothing covers.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(),
        help="repo root holding the compose files (default: current directory)",
    )
    parser.add_argument(
        "--rederive",
        action="store_true",
        help="ask a real docker instead, and report every recorded row that has drifted",
    )
    args = parser.parse_args(argv)
    given: Path = args.root
    rederiving: bool = args.rederive
    if not given.is_dir():
        print(f"volumecheck: root {given} is not a directory", file=sys.stderr)
        return 2
    try:
        scanned = check(given.resolve())
    except ComposeSearchError as err:
        print(f"volumecheck: {err}", file=sys.stderr)
        return 2
    if rederiving:
        return report_drift(scanned.names, scanned.built, IMAGE_VOLUMES, inspect)
    for fault in scanned.faults:
        print(f"{fault.path}:{fault.line}: {fault.detail}")
    if scanned.faults:
        print(
            f"\nvolumecheck: {len(scanned.faults)} image volume declaration(s) go uncovered or "
            f"unrecorded. Mount something at the path, or bring {RECORD_PATH} back in step with "
            "the tree by running `just image-volumes`.",
            file=sys.stderr,
        )
        return 1
    print(
        f"volumecheck OK: {scanned.declared} declared volume path(s) under {given} are covered, "
        f"over {scanned.files} compose file(s), {scanned.definitions} service definition(s) and "
        f"{len(scanned.names)} image(s), and {len(scanned.dockerfiles)} Dockerfile(s) here declare "
        "nothing their row does not carry"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover -- CLI entry point; main() is unit-tested
    sys.exit(main())
