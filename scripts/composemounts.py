"""Read the bind mounts a compose file declares, raising on every entry it cannot classify.

Split out of `bindcheck.py`, which owns the rule; this module owns only the reading. It is a line
reader rather than a YAML parse, because these gates are stdlib-only (`pyproject.toml` in this
directory), and it raises on anything outside the shapes it was taught: an inline
`volumes: [...]`, a mount with no `type`, an unlisted type, and a short-syntax entry carrying an
expansion. Each raises rather than being skipped, because a reader that walked past the one mount a
new override adds would leave the gate unable to fail.

The one YAML rule it leans on is that a mapping needs a space after its colon. That is exactly
what tells `type: bind` (a mapping, so the long syntax) from `redis-data:/data` (a scalar, so
the short one), and it is why `_MAPPING` requires the space.

The second YAML rule it has to know is that a sequence may be written **flush**, its items at the
indent of the key they belong to rather than under it. Compose accepts both, so a block that
closed at the first line no deeper than its key would walk past every mount of a flush
`volumes:` and read zero of them, silently. A block therefore closes on a line shallower than
its key, or on one at the key's own indent that is not a list item.
"""

import re
from typing import NamedTuple

# Long-syntax mount types that name something other than a path on the host, so nothing of
# theirs can land in the tree. An unlisted type is a fault, never a skip.
NON_BIND_TYPES = frozenset({"volume", "tmpfs", "npipe", "cluster", "image"})

# What makes a short-syntax source a path at all rather than a named volume.
PATH_PREFIXES = (".", "/", "~")

# What opens a flow collection, which is YAML's inline `{key: value}` / `[a, b]` spelling. A
# long-syntax entry written that way (`- {type: bind, source: ./x, target: /y}`) reaches the
# short-syntax reader, where its first field would pass for a named volume, so it is refused here
# rather than read as one. The same refusal covers a flow sequence.
FLOW_OPENERS = ("{", "[")

_VOLUMES = re.compile(r"^(?P<indent>[ \t]*)volumes:(?P<rest>.*)$")
_ITEM = re.compile(r"^(?P<indent>[ \t]*)-[ \t]*(?P<rest>.*)$")
_MAPPING = re.compile(r"^(?P<key>[A-Za-z_][\w.-]*):(?:[ \t]+(?P<value>.*))?$")


class ComposeReadError(Exception):
    """A compose file carries a mount entry this reader cannot classify."""


class Mount(NamedTuple):
    """One bind mount: the line its entry starts on and the source expression as written."""

    line: int
    source: str


def strip_quotes(text: str) -> str:
    """Drop one layer of matching quotes, which is how compose spells an expansion."""
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
        msg = f"line {line}: short-syntax mount {item!r} carries an expansion; use the long form"
        raise ComposeReadError(msg)
    source, separator, _ = text.partition(":")
    if not separator:
        msg = f"line {line}: mount entry {item!r} is not source:target"
        raise ComposeReadError(msg)
    if not source.startswith(PATH_PREFIXES):
        return None  # a named volume, which never touches the working tree
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
        """Enter a service's `volumes:` list. A top-level one declares named volumes; ignore it."""
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
        # A flush sequence puts its items at the key's own indent, so only a line that is not an
        # item closes the block there; anything shallower closes it either way.
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
