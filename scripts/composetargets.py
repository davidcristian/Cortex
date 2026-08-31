"""The container path a compose mount entry names, in every spelling compose accepts.

Split out of `composeservices.py`, which owns the walk over a file's services; this module owns
one question asked inside it, and it is exactly the question `composemounts.py` deliberately does
not ask. That reader takes a mount's **source**, the host path a bind would materialize, and drops
every entry naming none. This one takes a mount's **target**, and a named volume, a tmpfs and a
bind cover a declared path equally well, so none of them may be dropped.

Four spellings reach it and all four mean one path: the short `source:target[:mode]`, the long
block with a `target:` key, a whole path listed under `tmpfs:`, and any of those written through a
YAML anchor. **Anchors are resolved, because this tree writes one.**
`docker-compose.imap-probe.yml` names its mail root once, as `x-mail-root: &mail-root "/srv/mail"`,
and spends it as `*mail-root` inside the `tmpfs:` list. A reader that took the alias for a path
would report the probe leaking the very volume it mounts a tmpfs over, which would be a false red
on the one file in the tree that already got this right. Only a scalar anchor is recorded, and an
alias naming nothing recorded is refused rather than guessed at.

Like its siblings it is a line reader rather than a YAML parse, these gates being stdlib-only
(`pyproject.toml` in this directory), and it raises on every shape it was not taught rather than
walking past it: an inline list, a mount with no target, a short entry carrying an expansion, a
relative target, and an alias naming nothing. Each raises rather than being skipped, because a
reader that walked past the one mount a new override adds would leave the gate unable to fail.
"""

import re

from composemounts import strip_quotes

# What opens a flow collection, which is YAML's inline `{key: value}` / `[a, b]` spelling. A mount
# written that way would reach the scalar reader below and pass for a path, so it is refused here
# instead. `composemounts.py` refuses the same shape for the same reason.
FLOW_OPENERS = ("{", "[")

# One `key: value` line, in the one YAML rule these readers lean on: a mapping needs a space after
# its colon, which is what tells `type: bind` from the short-syntax scalar `redis-data:/data`.
# The walk above reads its own keys with it too, so both halves agree on what a key looks like.
KEY = re.compile(r"^(?P<key>[A-Za-z_][\w.-]*):(?:[ \t]+(?P<value>.*))?$")
_ALIAS = re.compile(r"^\*(?P<anchor>[\w.-]+)$")

# Source and target, the two fields a short-syntax mount needs before it names a container path.
_FIELDS = 2


class ComposeServiceError(Exception):
    """A compose file carries a shape this reader cannot read.

    One exception covers both halves of the reader, and it lives here because this half raises most
    of them: a caller catching `ComposeServiceError` should not have to work out which half it came
    from, and two names for one fault would be two things to keep in step.
    """


def normalize(path: str) -> str:
    """Drop the trailing slash a target may carry, so one container path has one spelling."""
    trimmed = path.rstrip("/")
    return trimmed or "/"


class Targets:
    """The mount entry currently open, and every anchor a path in it may be written through.

    ``anchors`` is filled by the walk above, from the scalar anchors a file writes at top level.
    Everything else is the long-syntax entry being built, which is closed by the next list item,
    by the next key, or by the file ending, whichever comes first.
    """

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
            msg = f"line {number}: short mount {entry!r} carries an expansion; use the long form"
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
