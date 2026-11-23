"""Read the named volumes a compose file declares in its top-level `volumes:` block."""

from typing import NamedTuple

from composetargets import KEY

VOLUMES_KEY = "volumes"

# The only keys that leave a volume on docker's own disk; a driver, its options or an external
# volume can keep it in memory, and a key this reader does not know is treated the same way.
PLAIN_KEYS = frozenset({"name", "labels"})


class Declared(NamedTuple):
    """One named volume as one file declares it, and whether it sets only the plain keys."""

    name: str
    line: int
    plain: bool


class _Walk:
    """Where the walk is: inside the block or not, and the entry and indents it has reached."""

    def __init__(self) -> None:
        self.inside = False
        self.entry_indent = -1
        self.key_indent = -1
        self.found: list[Declared] = []

    def top(self, body: str) -> None:
        """Enter the block at a bare `volumes:` key, and leave it at any other top-level key."""
        pair = KEY.match(body)
        value = (pair.group("value") or "").strip() if pair is not None else ""
        written = bool(value) and not value.startswith("#")
        self.inside = pair is not None and pair.group("key") == VOLUMES_KEY and not written
        self.entry_indent = -1

    def entry(self, number: int, body: str) -> None:
        """Start one declaration, which is plain only when nothing follows its name inline; a
        line that is not a key ends the block, so nothing after it is declared."""
        self.key_indent = -1
        pair = KEY.match(body)
        if pair is None:
            self.inside = False
            return
        value = (pair.group("value") or "").strip()
        plain = not value or value.startswith("#")
        self.found.append(Declared(pair.group("key"), number, plain))

    def key(self, body: str, depth: int) -> None:
        """Read one line under a declaration; a key other than a plain one makes it not plain."""
        if self.key_indent < 0:
            self.key_indent = depth
        if depth > self.key_indent:
            return
        pair = KEY.match(body)
        if pair is None or pair.group("key") not in PLAIN_KEYS:
            self.found[-1] = self.found[-1]._replace(plain=False)

    def feed(self, number: int, line: str) -> None:
        """Offer one non-blank, non-comment line to the walk."""
        depth = len(line) - len(line.lstrip())
        if depth == 0:
            self.top(line.strip())
        elif self.inside:
            if self.entry_indent < 0:
                self.entry_indent = depth
            if depth <= self.entry_indent:
                self.entry(number, line.strip())
            else:
                self.key(line.strip(), depth)


def read_volumes(text: str) -> tuple[Declared, ...]:
    """Return every named volume the file's top-level `volumes:` block declares."""
    walk = _Walk()
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.rstrip()
        if line.strip() and not line.lstrip().startswith("#"):
            walk.feed(number, line)
    return tuple(walk.found)
