"""Read the bind mounts a compose file declares, raising on every entry it cannot classify."""

import re
from typing import NamedTuple

NON_BIND_TYPES = frozenset({"volume", "tmpfs", "npipe", "cluster", "image"})

PATH_PREFIXES = (".", "/", "~")

FLOW_OPENERS = ("{", "[")

_VOLUMES = re.compile(r"^(?P<indent>[ \t]*)volumes:(?P<rest>.*)$")
_ITEM = re.compile(r"^(?P<indent>[ \t]*)-[ \t]*(?P<rest>.*)$")
_MAPPING = re.compile(r"^(?P<key>[A-Za-z_][\w.-]*):(?:[ \t]+(?P<value>.*))?$")


class ComposeReadError(Exception):
    """A compose file has a mount entry this reader cannot classify."""


class Mount(NamedTuple):
    """One bind mount: the line its entry starts on and the source expression as written."""

    line: int
    source: str


def strip_quotes(text: str) -> str:
    """Drop one layer of matching quotes, which is how compose writes an expansion."""
    stripped = text.strip()
    for quote in ('"', "'"):
        if len(stripped) > 1 and stripped.startswith(quote) and stripped.endswith(quote):
            return stripped[1:-1]
    return stripped


def _long_mount(line: int, fields: dict[str, str]) -> Mount | None:
    """Turn one long-syntax entry into a bind mount, or None when it names no host path."""
    kind = fields.get("type")
    if kind is None:
        msg = f"line {line}: mount entry declares no type"
        raise ComposeReadError(msg)
    if kind in NON_BIND_TYPES:
        return None
    if kind != "bind":
        msg = f"line {line}: unknown mount type {kind!r}"
        raise ComposeReadError(msg)
    source = fields.get("source")
    if source is None:
        msg = f"line {line}: bind mount declares no source"
        raise ComposeReadError(msg)
    return Mount(line=line, source=source)


def _short_mount(line: int, item: str) -> Mount | None:
    """Turn one short-syntax entry into a bind mount, or None when it names a volume."""
    text = strip_quotes(item)
    if text.startswith(FLOW_OPENERS):
        msg = f"line {line}: flow-style mount entry {item!r} is not supported; use the block form"
        raise ComposeReadError(msg)
    if "$" in text:
        msg = f"line {line}: short-syntax mount {item!r} contains an expansion; use the long form"
        raise ComposeReadError(msg)
    source, separator, _ = text.partition(":")
    if not separator:
        msg = f"line {line}: mount entry {item!r} is not source:target"
        raise ComposeReadError(msg)
    if not source.startswith(PATH_PREFIXES):
        return None
    return Mount(line=line, source=source)


class _Reader:
    """The walk's state: which `volumes:` block we are inside and which entry we are building."""

    def __init__(self) -> None:
        self.mounts: list[Mount] = []
        self.indent = -1
        self.start = 0
        self.fields: dict[str, str] | None = None

    def close(self) -> None:
        """Finish the entry being built, if any, and record the mount it declared."""
        if self.fields is not None:
            mount = _long_mount(self.start, self.fields)
            self.fields = None
            if mount is not None:
                self.mounts.append(mount)

    def open_block(self, number: int, line: str) -> None:
        """Enter a service's `volumes:` list."""
        header = _VOLUMES.match(line)
        if header is None:
            return
        rest = header.group("rest").strip()
        if rest and not rest.startswith("#"):
            msg = f"line {number}: inline volumes list {rest!r} is not supported"
            raise ComposeReadError(msg)
        self.indent = len(header.group("indent")) or -1

    def start_item(self, number: int, entry: str) -> None:
        """Begin a list entry, taking the short syntax whole and the long syntax key by key."""
        self.close()
        pair = _MAPPING.match(entry) if entry else None
        if entry and pair is None:
            short = _short_mount(number, entry)
            if short is not None:
                self.mounts.append(short)
            return
        self.fields, self.start = {}, number
        if pair is not None:
            self.add_key(number, entry)

    def add_key(self, number: int, line: str) -> None:
        """Record one `key: value` of the entry being built."""
        pair = _MAPPING.match(line)
        if pair is None or self.fields is None:
            msg = f"line {number}: {line!r} is not a mount key"
            raise ComposeReadError(msg)
        self.fields[pair.group("key")] = strip_quotes(pair.group("value") or "")

    def feed(self, number: int, line: str) -> None:
        """Offer one non-blank, non-comment line to the walk."""
        depth = len(line) - len(line.lstrip())
        item = _ITEM.match(line)
        if self.indent >= 0 and (depth < self.indent or (depth == self.indent and item is None)):
            self.close()
            self.indent = -1
        if self.indent < 0:
            self.open_block(number, line)
            return
        if item is None:
            self.add_key(number, line.strip())
        else:
            self.start_item(number, item.group("rest").strip())


def read_mounts(text: str) -> list[Mount]:
    """Return every bind mount one compose file declares, in the order it declares them."""
    reader = _Reader()
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.rstrip()
        if line.strip() and not line.lstrip().startswith("#"):
            reader.feed(number, line)
    reader.close()
    return reader.mounts
