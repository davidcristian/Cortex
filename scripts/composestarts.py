"""Read what each service in a compose file is started with, and the environment it is given.

`subagentservers.py` owns the question of which of those services serve subagents; this module
owns only the reading, and it knows nothing about any of them. It is the third reader over this
file format and it asks what neither of the other two does. `composemounts.py` reads a mount's
source, `composeservices.py` reads a mount's target and the image or build behind it, and both
step over `command:` and `environment:` because a volume gate has no question for either. Those
two keys are the whole of this one: an argv is what a server's behaviour is decided by, and an
environment block is where a stack writes down which servers it dials.

**Two keys, and a service that declares neither is still reported.** Every override here re-opens
`brain:` to add environment and a dependency and runs the base file's container, so a service with
no command is the normal shape rather than an edge, and its environment is exactly where the
wiring lives. A command of ``None`` therefore means the service says nothing about its own argv,
which is a different answer from an empty command and is worth telling apart.

**A block scalar is one value written over the lines under it**, and both keys here carry one:
`docker-compose.tools.yml` folds a shell line into a command item, and
`docker-compose.subagents-roster.yml` folds a JSON object into an environment value. They are one
shape with one difference, which is what the value ends up being part of, so they are read by one
pair of methods and closed at the first line no deeper than the opener.

Like every compose reader beside it, it is a line walk rather than a YAML parse, these gates being
stdlib-only (`pyproject.toml` in this directory), and it stays honest about that by refusing every
shape it was not taught: a command that is neither an inline list nor a block of items, an inline
or list-form environment, an inline service body, and a line indented under no service are each
raised, never stepped over. A reader that walked quietly past the one server a new override adds
would be a gate that cannot fail.
"""

import json
import re
from typing import NamedTuple, cast

from composetargets import FLOW_OPENERS, KEY

# The two service keys this reader takes an answer from, and the block that collects them.
COMMAND_KEY = "command"
ENVIRONMENT_KEY = "environment"
BLOCK_KEYS = frozenset({COMMAND_KEY, ENVIRONMENT_KEY})
SERVICES_KEY = "services"

# What opens a block scalar, which is one value written over the lines under its own opener. What
# opens a flow collection, which is the inline `["a", "b"]` spelling of a command, is
# `composetargets.FLOW_OPENERS`, the same pair its own reader refuses a mount written in.
BLOCK_SCALARS = ("|", ">")

_ITEM = re.compile(r"^[ \t]*-[ \t]*(?P<rest>.*)$")


class ComposeStartError(Exception):
    """A compose file carries a shape this reader will not guess at."""


class Started(NamedTuple):
    """One service as one file writes it: the argv it starts with, and the environment it gets.

    ``command`` is None when the service declares no command of its own, which is not the same
    answer as an empty one: an override re-opening a service says nothing about its argv, and the
    container it will run is the base file's.
    """

    service: str
    line: int
    command: tuple[str, ...] | None
    environment: tuple[tuple[str, str], ...]


def _flow_items(number: int, written: str) -> list[str]:
    """Read a command written as an inline list, which is JSON in every spelling this tree has."""
    try:
        loaded: object = json.loads(written)
    except json.JSONDecodeError as err:
        msg = f"line {number}: command {written!r} is not an inline list this reader can read"
        raise ComposeStartError(msg) from err
    if not isinstance(loaded, list):
        msg = f"line {number}: command {written!r} is not a list"
        raise ComposeStartError(msg)
    items = cast("list[object]", loaded)
    if not all(isinstance(item, str) for item in items):
        msg = f"line {number}: command {written!r} lists something that is not a string"
        raise ComposeStartError(msg)
    return [str(item) for item in items]


def unquote(text: str) -> str:
    """Drop one layer of matching quotes, which is how a scalar spells a word with spaces in."""
    stripped = text.strip()
    for quote in ('"', "'"):
        if len(stripped) > 1 and stripped.startswith(quote) and stripped.endswith(quote):
            return stripped[1:-1]
    return stripped


class _Reader:
    """The walk's state: which service we are inside, which of its blocks, and which value."""

    def __init__(self) -> None:
        self.started: list[Started] = []
        self.name = ""
        self.line = 0
        self.command: list[str] = []
        self.commanded = False
        self.environment: list[tuple[str, str]] = []
        self.in_services = False
        self.service_indent = -1
        self.key_indent = -1
        self.key = ""
        self.folding = False
        self.fold_key = ""
        self.folded: list[str] = []
        self.fold_indent = -1

    def open_fold(self, key: str, depth: int) -> None:
        """Begin a block scalar. ``key`` names the environment entry, and is empty for an item."""
        self.folding, self.fold_key, self.folded, self.fold_indent = True, key, [], depth

    def close_fold(self) -> None:
        """Finish a block scalar, which ends at the first line no deeper than its own opener."""
        if self.folding:
            written = " ".join(self.folded)
            if self.fold_key:
                self.environment.append((self.fold_key, written))
            else:
                self.command.append(written)
        self.folding, self.fold_key, self.folded, self.fold_indent = False, "", [], -1

    def close_service(self) -> None:
        """Finish the service being read, if it was ever named, and forget where its keys were."""
        self.close_fold()
        if self.name:
            command = tuple(self.command) if self.commanded else None
            self.started.append(Started(self.name, self.line, command, tuple(self.environment)))
        self.name, self.line = "", 0
        self.command, self.commanded, self.environment = [], False, []
        self.key_indent, self.key = -1, ""

    def top(self, number: int, body: str) -> None:
        """Read one top-level key, which is only ever asked whether it opens the services."""
        self.close_service()
        pair = KEY.match(body)
        if pair is None:
            msg = f"line {number}: {body!r} is not a top-level key"
            raise ComposeStartError(msg)
        self.in_services = pair.group("key") == SERVICES_KEY
        self.service_indent = -1

    def start_service(self, number: int, body: str) -> None:
        """Begin one service, which is a key at the indent the services block opened at."""
        self.close_service()
        pair = KEY.match(body)
        if pair is None:
            msg = f"line {number}: {body!r} is not a service name"
            raise ComposeStartError(msg)
        value = (pair.group("value") or "").strip()
        if value and not value.startswith("#"):
            msg = f"line {number}: inline service body {value!r} is not supported"
            raise ComposeStartError(msg)
        self.name, self.line = pair.group("key"), number

    def service_key(self, number: int, body: str) -> None:
        """Read one key of the service being read, and remember which block follows it."""
        pair = KEY.match(body)
        if pair is None:
            msg = f"line {number}: {body!r} is not a service key"
            raise ComposeStartError(msg)
        key, value = pair.group("key"), (pair.group("value") or "").strip()
        self.key = key if key in BLOCK_KEYS else ""
        written = "" if value.startswith("#") else value
        if key == COMMAND_KEY:
            if written and not written.startswith(FLOW_OPENERS):
                msg = f"line {number}: command {written!r} is neither a list nor a block of items"
                raise ComposeStartError(msg)
            self.commanded = True
            self.command = _flow_items(number, written) if written else []
        elif key == ENVIRONMENT_KEY and written:
            msg = f"line {number}: inline environment {written!r} is not supported"
            raise ComposeStartError(msg)

    def command_item(self, number: int, body: str, depth: int) -> None:
        """Read one item of a command block, which is one word of what the service starts with."""
        item = _ITEM.match(body)
        if item is None:
            msg = f"line {number}: {body.strip()!r} is not an item of a command"
            raise ComposeStartError(msg)
        rest = item.group("rest")
        if rest.startswith(BLOCK_SCALARS):
            self.open_fold("", depth)
        else:
            self.command.append(unquote(rest))

    def environment_entry(self, number: int, body: str, depth: int) -> None:
        """Read one environment entry, which names a value or opens the block it folds over."""
        if _ITEM.match(body) is not None:
            msg = f"line {number}: an environment written as a list is not supported"
            raise ComposeStartError(msg)
        pair = KEY.match(body.strip())
        if pair is None:
            msg = f"line {number}: {body.strip()!r} is not an environment key"
            raise ComposeStartError(msg)
        key, value = pair.group("key"), (pair.group("value") or "").strip()
        if value.startswith(BLOCK_SCALARS):
            self.open_fold(key, depth)
        else:
            self.environment.append((key, unquote(value)))

    def inside(self, number: int, line: str, depth: int) -> None:
        """Read one line of a service body: a key of it, or part of the block under one."""
        if self.folding and depth > self.fold_indent:
            self.folded.append(line.strip())
            return
        self.close_fold()
        if self.key_indent < 0:
            self.key_indent = depth
        if depth == self.key_indent and _ITEM.match(line) is None:
            self.service_key(number, line.strip())
        elif self.key == COMMAND_KEY:
            self.command_item(number, line, depth)
        elif self.key == ENVIRONMENT_KEY:
            self.environment_entry(number, line, depth)

    def feed(self, number: int, line: str) -> None:
        """Offer one non-blank, non-comment line to the walk."""
        depth = len(line) - len(line.lstrip())
        if depth == 0:
            self.top(number, line.strip())
            return
        if not self.in_services:
            return  # the body of some other top-level block, which declares no service
        if self.service_indent < 0:
            self.service_indent = depth
        if depth < self.service_indent:
            msg = f"line {number}: {line.strip()!r} is indented under no service"
            raise ComposeStartError(msg)
        if depth == self.service_indent:
            self.start_service(number, line.strip())
        else:
            self.inside(number, line, depth)


def read_starts(text: str) -> tuple[Started, ...]:
    """Return every service one compose file writes, with its argv and its environment."""
    reader = _Reader()
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.rstrip()
        if line.strip() and not line.lstrip().startswith("#"):
            reader.feed(number, line)
    reader.close_service()
    return tuple(reader.started)
