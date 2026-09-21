"""The container path a compose mount entry names, in every form compose accepts."""

import re

from composemounts import strip_quotes

FLOW_OPENERS = ("{", "[")

# A YAML mapping needs a space after its colon, which is what tells `type: bind` from the
# short-syntax scalar `redis-data:/data`.
KEY = re.compile(r"^(?P<key>[A-Za-z_][\w.-]*):(?:[ \t]+(?P<value>.*))?$")
_ALIAS = re.compile(r"^\*(?P<anchor>[\w.-]+)$")

_FIELDS = 2


class ComposeServiceError(Exception):
    """A compose file has a form this reader cannot read."""


def normalize(path: str) -> str:
    """Drop the trailing slash a target may have, so one container path is written one way."""
    trimmed = path.rstrip("/")
    return trimmed or "/"


class Targets:
    """The mount entry currently open, and every anchor a path in it may be written through."""

    def __init__(self) -> None:
        self.anchors: dict[str, str] = {}
        self.entry: dict[str, str] | None = None
        self.line = 0
        self.sink: list[str] | None = None

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

    def close(self) -> None:
        """Finish the long-syntax mount entry being built, and record the path it covers."""
        fields, sink, line = self.entry, self.sink, self.line
        if fields is None or sink is None:
            return
        self.entry, self.sink = None, None
        target = fields.get("target")
        if target is None:
            msg = f"line {line}: mount entry declares no target"
            raise ComposeServiceError(msg)
        sink.append(self.resolve(line, target))

    def short(self, number: int, entry: str) -> str:
        """The container path a short-syntax mount names, its second colon-separated field."""
        text = strip_quotes(entry)
        if "$" in text:
            msg = f"line {number}: short mount {entry!r} contains an expansion; use the long form"
            raise ComposeServiceError(msg)
        parts = text.split(":")
        if len(parts) < _FIELDS:
            msg = f"line {number}: mount entry {entry!r} is not source:target"
            raise ComposeServiceError(msg)
        return self.resolve(number, parts[1])

    def start(self, number: int, entry: str, sink: list[str], *, whole: bool) -> None:
        """Begin one list entry: a whole path under `tmpfs:`, and a mount under `volumes:`."""
        self.close()
        if entry.startswith(FLOW_OPENERS):
            msg = f"line {number}: flow-style entry {entry!r} is not supported; use the block form"
            raise ComposeServiceError(msg)
        if whole:
            sink.append(self.resolve(number, entry))
            return
        pair = KEY.match(entry) if entry else None
        if entry and pair is None:
            sink.append(self.short(number, entry))
            return
        self.entry, self.line, self.sink = {}, number, sink
        if pair is not None:
            self.field(number, entry)

    def field(self, number: int, body: str) -> None:
        """Record one `key: value` of the long-syntax mount entry being built."""
        pair = KEY.match(body)
        if pair is None or self.entry is None:
            msg = f"line {number}: {body!r} is not a mount key"
            raise ComposeServiceError(msg)
        self.entry[pair.group("key")] = strip_quotes(pair.group("value") or "")
