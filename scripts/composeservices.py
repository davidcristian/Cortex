"""Read what each service in a compose file runs, and which container paths it already covers."""

import re
from typing import NamedTuple

from composemounts import strip_quotes
from composetargets import FLOW_OPENERS, KEY, ComposeServiceError, Targets

COVERING_KEYS = frozenset({"volumes", "tmpfs"})

IMAGE_KEY = "image"
BUILD_KEY = "build"

CONTEXT_KEY = "context"
DOCKERFILE_KEY = "dockerfile"
DEFAULT_DOCKERFILE = "Dockerfile"

PROJECT_KEY = "name"

_ITEM = re.compile(r"^(?P<indent>[ \t]*)-[ \t]*(?P<rest>.*)$")
_ANCHOR = re.compile(r"^&(?P<anchor>[\w.-]+)[ \t]+(?P<value>.+)$")


class Build(NamedTuple):
    """Where a service's image is built: the context directory, and the Dockerfile inside it."""

    context: str
    dockerfile: str


class Service(NamedTuple):
    """One service as one file writes it: what it runs, and the container paths it covers."""

    name: str
    line: int
    image: str | None
    build: Build | None
    covered: tuple[str, ...]

    @property
    def builds(self) -> bool:
        """Whether this service builds its image here, rather than pulling a named one."""
        return self.build is not None

    @property
    def defines(self) -> bool:
        """Whether this service says what it runs, rather than layering onto one that does."""
        return self.image is not None or self.builds


class ComposeFile(NamedTuple):
    """One compose file: the project name it sets, if it sets one, and the services it writes."""

    project: str | None
    services: tuple[Service, ...]


class _Draft:
    """One service being filled in as the walk goes down it."""

    def __init__(self, name: str, line: int) -> None:
        self.name = name
        self.line = line
        self.image: str | None = None
        self.builds = False
        self.build_line = 0
        self.context: str | None = None
        self.dockerfile = DEFAULT_DOCKERFILE
        self.covered: list[str] = []

    def done(self) -> Service:
        """The finished service, with its covered paths frozen in the order they were written."""
        build = None
        if self.builds:
            if self.context is None:
                msg = f"line {self.build_line}: build names no context"
                raise ComposeServiceError(msg)
            build = Build(self.context, self.dockerfile)
        return Service(self.name, self.line, self.image, build, tuple(self.covered))


class _Reader:
    """The walk's state: which service we are inside, which of its keys, and which mount entry."""

    def __init__(self) -> None:
        self.project: str | None = None
        self.targets = Targets()
        self.services: list[Service] = []
        self.draft = _Draft("", 0)
        self.in_services = False
        self.service_indent = -1
        self.key_indent = -1
        self.list_key = ""
        self.in_build = False
        self.build_indent = -1

    def close_service(self) -> None:
        """Finish the service being built, if it was ever named, and forget where its keys were."""
        self.targets.close()
        if self.draft.name:
            self.services.append(self.draft.done())
        self.draft = _Draft("", 0)
        self.key_indent = -1
        self.list_key = ""
        self.in_build, self.build_indent = False, -1

    def top(self, number: int, body: str) -> None:
        """Read one top-level key: the project name, a scalar anchor, or the services block."""
        self.close_service()
        pair = KEY.match(body)
        if pair is None:
            msg = f"line {number}: {body!r} is not a top-level key"
            raise ComposeServiceError(msg)
        key, value = pair.group("key"), (pair.group("value") or "").strip()
        self.in_services = key == "services"
        self.service_indent = -1
        anchor = _ANCHOR.match(value)
        if anchor is not None:
            self.targets.anchors[anchor.group("anchor")] = strip_quotes(anchor.group("value"))
        elif key == PROJECT_KEY and value:
            self.project = strip_quotes(value)

    def start_service(self, number: int, body: str) -> None:
        """Begin one service, which is a key at the indent the services block opened at."""
        self.close_service()
        pair = KEY.match(body)
        if pair is None:
            msg = f"line {number}: {body!r} is not a service name"
            raise ComposeServiceError(msg)
        value = (pair.group("value") or "").strip()
        if value and not value.startswith("#"):
            msg = f"line {number}: inline service body {value!r} is not supported"
            raise ComposeServiceError(msg)
        self.draft = _Draft(pair.group("key"), number)

    def start_build(self, number: int, value: str) -> None:
        """Open the `build:` stanza, which names its context inline or in the block under it."""
        written = "" if value.startswith("#") else value
        if written.startswith(FLOW_OPENERS):
            msg = f"line {number}: inline build {written!r} is not supported; use the block form"
            raise ComposeServiceError(msg)
        self.draft.builds, self.draft.build_line = True, number
        self.draft.context = strip_quotes(written) or None
        self.in_build = not written

    def build_field(self, number: int, body: str, depth: int) -> None:
        """Read one key of the `build:` block: where its context is, and which Dockerfile in it."""
        if self.build_indent < 0:
            self.build_indent = depth
        if depth > self.build_indent:
            return
        pair = KEY.match(body)
        if pair is None:
            msg = f"line {number}: {body!r} is not a build key"
            raise ComposeServiceError(msg)
        key, value = pair.group("key"), strip_quotes((pair.group("value") or "").strip())
        if not value:
            return
        if key == CONTEXT_KEY:
            self.draft.context = value
        elif key == DOCKERFILE_KEY:
            self.draft.dockerfile = value

    def service_key(self, number: int, body: str) -> None:
        """Read one key of the service being built, and remember whether a list follows it."""
        self.targets.close()
        self.in_build, self.build_indent = False, -1
        pair = KEY.match(body)
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
            self.start_build(number, value)

    def inside(self, number: int, line: str, depth: int) -> None:
        """Read one line of a service body, which is a key of it or part of a list under one."""
        if self.key_indent < 0:
            self.key_indent = depth
        item = _ITEM.match(line)
        if depth == self.key_indent and item is None:
            self.service_key(number, line.strip())
        elif self.in_build:
            self.build_field(number, line.strip(), depth)
        elif not self.list_key:
            return
        elif item is None:
            self.targets.field(number, line.strip())
        else:
            entry = item.group("rest").strip()
            self.targets.start(number, entry, self.draft.covered, whole=self.list_key == "tmpfs")

    def feed(self, number: int, line: str) -> None:
        """Offer one non-blank, non-comment line to the walk."""
        depth = len(line) - len(line.lstrip())
        if depth == 0:
            self.top(number, line.strip())
            return
        if not self.in_services:
            return
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
    """Return what one compose file declares: the project it sets, and every service in it."""
    reader = _Reader()
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.rstrip()
        if line.strip() and not line.lstrip().startswith("#"):
            reader.feed(number, line)
    reader.close_service()
    return ComposeFile(project=reader.project, services=tuple(reader.services))
