"""Find each compose service given the card whose compiled kernels no mount would keep."""

import posixpath
import re
from collections.abc import Iterable
from pathlib import PurePosixPath
from typing import NamedTuple

from composeservices import ComposeFile
from composestarts import ComposeStartError, Started, read_starts
from composevolumes import read_volumes

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
_TEMPORARY = (
    "service {service!r} sets " + CACHE_VARIABLE + " to {value!r} and the mount over it at "
    "{target!r} is not a named volume or a bind in every compose file; a new container gets "
    "any other mount empty, a tmpfs or a volume with no source among them, and compiles the "
    "card's kernels again. Mount a named volume or a bind there."
)
_DRIVEN = (
    "service {service!r} sets " + CACHE_VARIABLE + " to {value!r} and the named volume "
    "{volume!r} over it at {target!r} is declared in no top-level volumes block, or a file "
    "declares it with a key other than name or labels; a driver, its options or an external "
    "volume can keep it in memory, which a new container gets empty, and the card's kernels are "
    "compiled again. Declare it with no driver, driver_opts or external key."
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
    """Every file read together: per service, what it mounts, which mounts a new container gets
    empty or a named volume holds, where it sets the variable and is first given the card."""

    covered: dict[str, set[str]]
    temporary: dict[str, set[str]]
    named: dict[str, set[tuple[str, str]]]
    plain: dict[str, bool]
    written: dict[str, list[tuple[str, int, str]]]
    carded: dict[str, tuple[str, int]]
    refused: list[Lost]


def _read(sources: Iterable[Source]) -> _Stack:
    """Merge every service across the files, as compose merges the files it is given."""
    stack = _Stack({}, {}, {}, {}, {}, {}, [])
    for source in sources:
        try:
            starts = read_starts(source.text)
        except ComposeStartError as err:
            stack.refused.append(Lost(source.name, 0, str(err)))
            continue
        for declared in read_volumes(source.text):
            stack.plain[declared.name] = stack.plain.get(declared.name, True) and declared.plain
        for service in source.found.services:
            stack.covered.setdefault(service.name, set()).update(service.covered)
            stack.temporary.setdefault(service.name, set()).update(service.temporary)
            stack.named.setdefault(service.name, set()).update(service.named)
        for started in starts:
            stack.written.setdefault(started.service, []).extend(
                (source.name, started.line, value)
                for key, value in started.environment
                if key == CACHE_VARIABLE
            )
            if given_card(source.text, started):
                stack.carded.setdefault(started.service, (source.name, started.line))
    return stack


def _over(targets: Iterable[str], path: str) -> str | None:
    """The deepest of ``targets`` that holds ``path``, which is the mount a write there reaches."""
    holding = [target for target in targets if contains(target, path)]
    return max(holding, key=lambda target: len(PurePosixPath(target).parts), default=None)


def _judge(stack: _Stack, service: str, value: str) -> list[str]:
    """Every reason one written value leaves the kernels in no mount that outlives a container."""
    if not value.startswith("/") or "$" in value:
        return [_UNREAD.format(service=service, value=value)]
    over = _over(stack.covered.get(service, set()), value)
    if over is None:
        return [_OUTSIDE.format(service=service, value=value)]
    if over in stack.temporary.get(service, set()):
        return [_TEMPORARY.format(service=service, value=value, target=over)]
    return [
        _DRIVEN.format(service=service, value=value, volume=volume, target=over)
        for volume in sorted(v for t, v in stack.named.get(service, set()) if t == over)
        if not stack.plain.get(volume, False)
    ]


def kernel_caches(sources: Iterable[Source]) -> Kept:
    """Judge every service given the card: a plain named volume or a bind must hold its
    directory, because a new container gets a tmpfs or a volume in memory empty."""
    stack = _read(sources)
    faults = list(stack.refused)
    faults.extend(
        Lost(name, line, _UNSET.format(service=service))
        for service, (name, line) in stack.carded.items()
        if not stack.written.get(service)
    )
    faults.extend(
        Lost(name, line, detail)
        for service, places in stack.written.items()
        for name, line, value in places
        for detail in _judge(stack, service, value)
    )
    return Kept(len(stack.carded), tuple(faults))
