"""Read what each service in a compose file runs, and which container paths it already covers.

Split out of `volumecheck.py`, which owns the rule, exactly as `composemounts.py` is split out of
`bindcheck.py` and `composedefaults.py` out of `defaultcheck.py`: this module owns only the
reading. `composemounts.py` cannot answer here, and the difference is worth stating, because two
readers over one file format look like a duplication until you see what each is asked. That one
reads a mount's **source**, the host path a bind would materialize, and drops every entry that
names no host path at all. This one reads a mount's **target**, the container path something is
mounted at, and a named volume, a tmpfs and a bind cover a declared path equally well, so none of
them may be dropped. It also reads two keys that one has no reason to look at, `image:` and
`tmpfs:`, and it groups everything by the service it belongs to.

It is a line reader rather than a YAML parse, for the reason its two siblings are: these gates are
stdlib-only (`pyproject.toml` in this directory). It stays honest about that the same way, by
refusing every shape it was not taught rather than walking past it. An inline list, a mount with
no target, a short entry carrying an expansion, a relative target and an alias naming nothing are
each raised, because a reader that quietly skipped the one mount a new override adds is a gate
that cannot fail.

**Anchors are resolved, because this tree writes one.** `docker-compose.imap-probe.yml` names its
mail root once, as `x-mail-root: &mail-root "/srv/mail"`, and spends it as `*mail-root` inside the
`tmpfs:` list. A reader that took the alias for a path would report the probe leaking the very
volume it mounts a tmpfs over, which would be a false red on the one file in the tree that already
got this right. Only a scalar anchor is recorded, and an alias naming nothing recorded is refused
rather than guessed at.

**A service naming neither an image nor a build is a fragment, not a definition.** Every override
here re-opens `brain:` to add environment and a dependency, and the container it will run is the
base file's. Such a service is reported with no image and no build, and the rule above it asks it
nothing, the question belonging where the image is named. That is also why the rule is per file
rather than per layered stack: `just up` runs the base file alone, so a base service whose
declared volume were covered only by an override really would leak, and a reader that merged the
files first could not say so.
"""

import re
from typing import NamedTuple

from composemounts import strip_quotes

# The two service keys that cover a container path. `volumes:` mounts something at a target, of
# whatever type; `tmpfs:` names the path directly. Both leave docker's own volume declaration
# nothing to anonymise, which is the only question this reader is feeding.
COVERING_KEYS = frozenset({"volumes", "tmpfs"})

# The service keys that say what a service runs, rather than what it mounts.
IMAGE_KEY = "image"
BUILD_KEY = "build"

# What opens a flow collection, which is YAML's inline `{key: value}` / `[a, b]` spelling. A mount
# written that way would reach the scalar reader below and pass for a path, so it is refused here
# instead. `composemounts.py` refuses the same shape for the same reason.
FLOW_OPENERS = ("{", "[")

# The top-level key that pins the compose project name, which is half of the image name a service
# that only builds ends up running under.
PROJECT_KEY = "name"

_KEY = re.compile(r"^(?P<key>[A-Za-z_][\w.-]*):(?:[ \t]+(?P<value>.*))?$")
_ITEM = re.compile(r"^(?P<indent>[ \t]*)-[ \t]*(?P<rest>.*)$")
_ANCHOR = re.compile(r"^&(?P<anchor>[\w.-]+)[ \t]+(?P<value>.+)$")
_ALIAS = re.compile(r"^\*(?P<anchor>[\w.-]+)$")


class ComposeServiceError(Exception):
    """A compose file carries a shape this reader will not guess at."""


class Service(NamedTuple):
    """One service as one file writes it: what it runs, and the container paths it covers."""

    name: str
    line: int
    image: str | None
    builds: bool
    covered: tuple[str, ...]

    @property
    def defines(self) -> bool:
        """Whether this service says what it runs, rather than layering onto one that does."""
        return self.image is not None or self.builds


class ComposeFile(NamedTuple):
    """One compose file: the project name it pins, if it pins one, and the services it writes."""

    project: str | None
    services: tuple[Service, ...]


def normalize(path: str) -> str:
    """Drop the trailing slash a target may carry, so one container path has one spelling."""
    trimmed = path.rstrip("/")
    return trimmed or "/"


class _Draft:
    """One service being filled in as the walk goes down it."""

    def __init__(self, name: str, line: int) -> None:
        self.name = name
        self.line = line
        self.image: str | None = None
        self.builds = False
        self.covered: list[str] = []

    def done(self) -> Service:
        """The finished service, with its covered paths frozen in the order they were written."""
        return Service(self.name, self.line, self.image, self.builds, tuple(self.covered))


class _Reader:
    """The walk's state: which service we are inside, which of its keys, and which mount entry.

    ``draft`` is never None. A nameless draft is the placeholder between services, discarded
    rather than reported, which keeps every path the walk records with a service to belong to and
    spares the reader a branch that no compose file could ever reach.
    """

    def __init__(self) -> None:
        self.project: str | None = None
        self.anchors: dict[str, str] = {}
        self.services: list[Service] = []
        self.draft = _Draft("", 0)
        self.in_services = False
        self.service_indent = -1
        self.key_indent = -1
        self.list_key = ""
        self.entry: dict[str, str] | None = None
        self.entry_line = 0
        self.entry_sink: list[str] | None = None

    def resolve(self, number: int, text: str) -> str:
        """Turn one written path into the container path it means, following an alias to it."""
        written = strip_quotes(text)
        alias = _ALIAS.match(written)
        if alias is not None:
            anchored = self.anchors.get(alias.group("anchor"))
            if anchored is None:
                msg = f"line {number}: alias {written!r} names no anchor this reader recorded"
                raise ComposeServiceError(msg)
            written = strip_quotes(anchored)
        if not written.startswith("/"):
            msg = f"line {number}: {text!r} is not an absolute container path"
            raise ComposeServiceError(msg)
        return normalize(written)

    def close_entry(self) -> None:
        """Finish the long-syntax mount entry being built, and record the path it covers."""
        fields, sink, line = self.entry, self.entry_sink, self.entry_line
        if fields is None or sink is None:
            return
        self.entry, self.entry_sink = None, None
        target = fields.get("target")
        if target is None:
            msg = f"line {line}: mount entry declares no target"
            raise ComposeServiceError(msg)
        sink.append(self.resolve(line, target))

    def close_service(self) -> None:
        """Finish the service being built, if it was ever named, and forget where its keys were."""
        self.close_entry()
        if self.draft.name:
            self.services.append(self.draft.done())
        self.draft = _Draft("", 0)
        self.key_indent = -1
        self.list_key = ""

    def top(self, number: int, body: str) -> None:
        """Read one top-level key: the project name, a scalar anchor, or the services block."""
        self.close_service()
        pair = _KEY.match(body)
        if pair is None:
            msg = f"line {number}: {body!r} is not a top-level key"
            raise ComposeServiceError(msg)
        key, value = pair.group("key"), (pair.group("value") or "").strip()
        self.in_services = key == "services"
        self.service_indent = -1
        anchor = _ANCHOR.match(value)
        if anchor is not None:
            self.anchors[anchor.group("anchor")] = strip_quotes(anchor.group("value"))
        elif key == PROJECT_KEY and value:
            self.project = strip_quotes(value)

    def start_service(self, number: int, body: str) -> None:
        """Begin one service, which is a key at the indent the services block opened at."""
        self.close_service()
        pair = _KEY.match(body)
        if pair is None:
            msg = f"line {number}: {body!r} is not a service name"
            raise ComposeServiceError(msg)
        value = (pair.group("value") or "").strip()
        if value and not value.startswith("#"):
            msg = f"line {number}: inline service body {value!r} is not supported"
            raise ComposeServiceError(msg)
        self.draft = _Draft(pair.group("key"), number)

    def service_key(self, number: int, body: str) -> None:
        """Read one key of the service being built, and remember whether a list follows it."""
        self.close_entry()
        pair = _KEY.match(body)
        if pair is None:
            msg = f"line {number}: {body!r} is not a service key"
            raise ComposeServiceError(msg)
        key, value = pair.group("key"), (pair.group("value") or "").strip()
        self.list_key = key if key in COVERING_KEYS else ""
        if self.list_key and value and not value.startswith("#"):
            msg = f"line {number}: inline {key} list {value!r} is not supported"
            raise ComposeServiceError(msg)
        if key == IMAGE_KEY:
            if not value:
                msg = f"line {number}: image key names nothing"
                raise ComposeServiceError(msg)
            self.draft.image = strip_quotes(value)
        elif key == BUILD_KEY:
            self.draft.builds = True

    def short_target(self, number: int, entry: str) -> str:
        """The container path a short-syntax mount names, its second colon-separated field."""
        text = strip_quotes(entry)
        if "$" in text:
            msg = f"line {number}: short mount {entry!r} carries an expansion; use the long form"
            raise ComposeServiceError(msg)
        parts = text.split(":")
        if len(parts) < 2:  # noqa: PLR2004 -- source and target are the two fields a mount needs
            msg = f"line {number}: mount entry {entry!r} is not source:target"
            raise ComposeServiceError(msg)
        return self.resolve(number, parts[1])

    def start_item(self, number: int, entry: str) -> None:
        """Begin one list entry: a whole path under `tmpfs:`, and a mount under `volumes:`."""
        self.close_entry()
        if entry.startswith(FLOW_OPENERS):
            msg = f"line {number}: flow-style entry {entry!r} is not supported; use the block form"
            raise ComposeServiceError(msg)
        if self.list_key == "tmpfs":
            self.draft.covered.append(self.resolve(number, entry))
            return
        pair = _KEY.match(entry) if entry else None
        if entry and pair is None:
            self.draft.covered.append(self.short_target(number, entry))
            return
        self.entry, self.entry_line, self.entry_sink = {}, number, self.draft.covered
        if pair is not None:
            self.add_field(number, entry)

    def add_field(self, number: int, body: str) -> None:
        """Record one `key: value` of the long-syntax mount entry being built."""
        pair = _KEY.match(body)
        if pair is None or self.entry is None:
            msg = f"line {number}: {body!r} is not a mount key"
            raise ComposeServiceError(msg)
        self.entry[pair.group("key")] = strip_quotes(pair.group("value") or "")

    def inside(self, number: int, line: str, depth: int) -> None:
        """Read one line of a service body, which is a key of it or part of a list under one."""
        if self.key_indent < 0:
            self.key_indent = depth
        item = _ITEM.match(line)
        if depth == self.key_indent and item is None:
            self.service_key(number, line.strip())
        elif not self.list_key:
            return  # inside some other key's block, which covers no path and names no image
        elif item is None:
            self.add_field(number, line.strip())
        else:
            self.start_item(number, item.group("rest").strip())

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
            raise ComposeServiceError(msg)
        if depth == self.service_indent:
            self.start_service(number, line.strip())
        else:
            self.inside(number, line, depth)


def read_services(text: str) -> ComposeFile:
    """Return what one compose file declares: the project it pins, and every service it writes."""
    reader = _Reader()
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.rstrip()
        if line.strip() and not line.lstrip().startswith("#"):
            reader.feed(number, line)
    reader.close_service()
    return ComposeFile(project=reader.project, services=tuple(reader.services))
