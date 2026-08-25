"""What a Dockerfile in this tree declares a VOLUME at, and each one its recorded row lacks."""

import json
import os
import re
from pathlib import Path
from typing import NamedTuple, cast

from composeservices import Build
from composetargets import normalize
from imagevolumes import RECORD_PATH

# The instruction this reader is looking for, matched case-insensitively the way docker matches it.
INSTRUCTION = "VOLUME"

# What ends a line that continues onto the next, in the default escape character. A file choosing
# another one is refused below rather than read under the wrong rule.
CONTINUES = "\\"

# What opens a JSON container, which is how the array spelling of the instruction begins. Both are
# dispatched to the array reader, because an object where an array belongs is a shape to refuse
# with the reason rather than to hand to the path splitter and refuse for the wrong one.
JSON_OPENERS = ("[", "{")

_ESCAPE = re.compile(r"^#[ \t]*escape[ \t]*=", re.IGNORECASE)

_UNDECLARED = (
    "{dockerfile} declares VOLUME {path!r}, and the row for {reference!r} in "
    + RECORD_PATH
    + " does not carry it; every container of that image then takes an anonymous volume there "
    "while the record says the image declares nothing. Rebuild the image, run `just "
    "image-volumes` to record what it now declares, and mount something at the path."
)
_NOWHERE = (
    "the image {reference!r} is built from {context!r}, where no {dockerfile} lands under either "
    "project directory compose can pick; the row for it in " + RECORD_PATH + " then describes an "
    "image nothing here builds. Point the build stanza at the file that builds it."
)
_UNRESOLVED = (
    "the image {reference!r} is built from {written!r}, which carries a substitution only a build "
    "can resolve, so nothing here can read what that file declares. Write the path out."
)
_UNREADABLE = "{dockerfile} builds {reference!r} and could not be read: {detail}"


class DockerfileError(Exception):
    """A Dockerfile carries a shape this reader will not guess at."""


class Reading(NamedTuple):
    """One build stanza followed: the Dockerfiles it reached, and every path no row carries."""

    dockerfiles: tuple[str, ...]
    faults: tuple[str, ...]


def _logical(text: str) -> list[tuple[int, str]]:
    """The file's instructions, comments dropped and continuation lines joined onto their first."""
    joined: list[tuple[int, str]] = []
    carry = ""
    start = 0
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not joined and _ESCAPE.match(line):
            msg = f"line {number}: an escape directive changes what a continuation means"
            raise DockerfileError(msg)
        if not line or line.startswith("#"):
            continue
        if not carry:
            start = number
        if line.endswith(CONTINUES):
            carry += line[:-1]
            continue
        joined.append((start, carry + line))
        carry = ""
    if carry:
        joined.append((start, carry))
    return joined


def _array(number: int, argument: str) -> list[str]:
    """The paths a JSON-array VOLUME names, refused whole when it is not an array of paths."""
    try:
        loaded: object = json.loads(argument)
    except json.JSONDecodeError as err:
        msg = f"line {number}: VOLUME {argument!r} is not a JSON array: {err}"
        raise DockerfileError(msg) from err
    if not isinstance(loaded, list):
        msg = f"line {number}: VOLUME {argument!r} is not a JSON array"
        raise DockerfileError(msg)
    written: list[str] = []
    for item in cast("list[object]", loaded):
        if not isinstance(item, str):
            msg = f"line {number}: VOLUME {argument!r} names {item!r}, which is not a path"
            raise DockerfileError(msg)
        written.append(item)
    return written


def _paths(number: int, argument: str) -> list[str]:
    """The container paths one VOLUME instruction names, in either spelling docker accepts."""
    if "$" in argument:
        msg = f"line {number}: VOLUME {argument!r} carries an expansion only a build can resolve"
        raise DockerfileError(msg)
    written = _array(number, argument) if argument.startswith(JSON_OPENERS) else argument.split()
    if not written:
        msg = f"line {number}: VOLUME names no path"
        raise DockerfileError(msg)
    for path in written:
        if not path.startswith("/"):
            msg = f"line {number}: VOLUME path {path!r} is not an absolute container path"
            raise DockerfileError(msg)
    return [normalize(path) for path in written]


def read_volumes(text: str) -> tuple[str, ...]:
    """Every container path one Dockerfile declares a VOLUME at, in the order it writes them."""
    found: list[str] = []
    for number, line in _logical(text):
        head, _, argument = line.partition(" ")
        if head.upper() != INSTRUCTION:
            continue
        found.extend(_paths(number, argument.strip()))
    return tuple(found)


def landings(root: Path, compose: Path, build: Build) -> list[Path]:
    """Every place the Dockerfile a service builds from lands, over both project directories."""
    projects = [root] if compose.parent == root else [root, compose.parent]
    found: list[Path] = []
    for project in projects:
        landed = Path(os.path.normpath(project / build.context / build.dockerfile))
        if landed.is_file() and landed not in found:
            found.append(landed)
    return found


def undeclared(
    root: Path, compose: Path, build: Build, reference: str, recorded: tuple[str, ...]
) -> Reading:
    """Every path the Dockerfile behind ``reference`` declares that its recorded row lacks."""
    if "$" in build.context or "$" in build.dockerfile:
        written = f"{build.context}/{build.dockerfile}"
        return Reading((), (_UNRESOLVED.format(reference=reference, written=written),))
    found = landings(root, compose, build)
    if not found:
        detail = _NOWHERE.format(
            reference=reference, context=build.context, dockerfile=build.dockerfile
        )
        return Reading((), (detail,))
    carried = {normalize(path) for path in recorded}
    read: list[str] = []
    faults: list[str] = []
    for path in found:
        name = Path(os.path.relpath(path, root)).as_posix()
        read.append(name)
        try:
            paths = read_volumes(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, DockerfileError) as err:
            faults.append(_UNREADABLE.format(dockerfile=name, reference=reference, detail=err))
            continue
        faults.extend(
            _UNDECLARED.format(dockerfile=name, path=path_here, reference=reference)
            for path_here in paths
            if path_here not in carried
        )
    return Reading(tuple(read), tuple(faults))
