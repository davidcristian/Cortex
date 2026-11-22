"""Find each compose service given the card whose compiled kernels no mount would keep."""

import posixpath
import re
from collections.abc import Iterable
from pathlib import PurePosixPath
from typing import NamedTuple

from composeservices import ComposeFile
from composestarts import ComposeStartError, Started, read_starts

CACHE_VARIABLE = "CUDA_CACHE_PATH"

_CARD = re.compile(
    r"^[ \t]*(?:-[ \t]*)?(?:(?:driver|runtime):[ \t]*[\"']?nvidia[\"']?|gpus:[ \t]*\S.*)[ \t]*$"
)

_UNSET = (
    "service {service!r} is given the card and no compose file sets " + CACHE_VARIABLE + " for it; "
    "the card's library then writes the kernels it compiles under the home directory, in the "
    "container's own layer, and every new container compiles them again. Set it to a directory "
    "under a mount of the service."
)
_OUTSIDE = (
    "service {service!r} sets " + CACHE_VARIABLE + " to {value!r} and no compose file mounts "
    "anything at that directory or above it; the kernels the card's library compiles are then "
    "written to the container's own layer, and every new container compiles them again. Mount a "
    "volume that contains the directory."
)
_UNREAD = (
    "service {service!r} sets " + CACHE_VARIABLE + " to {value!r}, which is not an absolute "
    "container path written out, so it cannot be compared with the service's mounts. Write the "
    "path out."
)


class Source(NamedTuple):
    """One compose file: its name under the root, its text, and the services read from it."""

    name: str
    text: str
    found: ComposeFile


class Lost(NamedTuple):
    """One service whose kernels no mount keeps, or one file whose environments were not read."""

    path: str
    line: int
    detail: str


class Kept(NamedTuple):
    """How many services are given the card, and every fault about where their kernels go."""

    carded: int
    faults: tuple[Lost, ...]


def contains(target: str, path: str) -> bool:
    """Whether a mount at ``target`` holds the container path ``path``."""
    inner = PurePosixPath(posixpath.normpath(path))
    return PurePosixPath(target) in (inner, *inner.parents)


def _depth(line: str) -> int:
    """How far one line is indented."""
    return len(line) - len(line.lstrip())


def given_card(text: str, started: Started) -> bool:
    """Whether one service's body reserves an nvidia device, by any of the three compose forms."""
    lines = text.splitlines()
    depth = _depth(lines[started.line - 1])
    for line in lines[started.line :]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if _depth(line) <= depth:
            break
        if _CARD.match(line) is not None:
            return True
    return False


class _Stack(NamedTuple):
    """Every file read together: per service, what it mounts over, where it sets the variable
    with each value, and the first place it is given the card."""

    covered: dict[str, set[str]]
    written: dict[str, list[tuple[str, int, str]]]
    carded: dict[str, tuple[str, int]]
    refused: list[Lost]


def _read(sources: Iterable[Source]) -> _Stack:
    """Merge every service across the files, as compose merges the files it is given."""
    stack = _Stack({}, {}, {}, [])
    for source in sources:
        try:
            starts = read_starts(source.text)
        except ComposeStartError as err:
            stack.refused.append(Lost(source.name, 0, str(err)))
            continue
        for service in source.found.services:
            stack.covered.setdefault(service.name, set()).update(service.covered)
        for started in starts:
            stack.written.setdefault(started.service, []).extend(
                (source.name, started.line, value)
                for key, value in started.environment
                if key == CACHE_VARIABLE
            )
            if given_card(source.text, started):
                stack.carded.setdefault(started.service, (source.name, started.line))
    return stack


def kernel_caches(sources: Iterable[Source]) -> Kept:
    """Judge every service given the card, and every directory the variable is set to."""
    stack = _read(sources)
    faults = list(stack.refused)
    faults.extend(
        Lost(name, line, _UNSET.format(service=service))
        for service, (name, line) in stack.carded.items()
        if not stack.written.get(service)
    )
    for service, places in stack.written.items():
        targets = stack.covered.get(service, ())
        for name, line, value in places:
            if not value.startswith("/") or "$" in value:
                faults.append(Lost(name, line, _UNREAD.format(service=service, value=value)))
            elif not any(contains(target, value) for target in targets):
                faults.append(Lost(name, line, _OUTSIDE.format(service=service, value=value)))
    return Kept(len(stack.carded), tuple(faults))
