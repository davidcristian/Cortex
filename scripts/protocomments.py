r"""One proto comment in both forms: as the proto writes it, and as prost rewrites it."""

import re
from typing import NamedTuple

# The line that ends the file header. It is header too: a comment trailing it would attach to
# the syntax statement, which generates no item for prost to document.
SYNTAX = "syntax = "

SERVICE = "service "
COPIES = 2

DOC = "///"
RULE = "---"

QUOTES = ('"', "'")

_HEADING = re.compile(r"^#+[ \t]*")


class ProtoReadError(Exception):
    """A proto file this reader cannot read: no syntax line, or a block comment."""


class Comment(NamedTuple):
    """One comment in the proto body: where it sits, what it says, and how it comes out."""

    line: int
    text: str
    leading: bool
    service: bool = False


def split_comment(number: int, line: str) -> tuple[str, str | None]:
    """Return the code on one line and the comment after its first unquoted `//`, if any."""
    quote = ""
    index = 0
    while index < len(line):
        char = line[index]
        if quote:
            if char == "\\":
                index += 1
            elif char == quote:
                quote = ""
        elif char in QUOTES:
            quote = char
        elif line.startswith("//", index):
            return line[:index], line[index + 2 :]
        elif line.startswith("/*", index):
            msg = f"line {number}: block comment in {line.strip()!r}; this reader reads only //"
            raise ProtoReadError(msg)
        index += 1
    return line, None


def proto_comments(text: str) -> list[Comment]:
    """Return every comment in the proto body, in file order, raising on a file with no body."""
    rows: list[tuple[int, str, bool]] = []
    claimed: set[int] = set()
    started = False
    depth = 0
    inside = False
    run: list[int] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not started:
            started = line.startswith(SYNTAX)
            continue
        code, comment = split_comment(number, line)
        bare = code.strip()
        opens = depth == 0 and bare.startswith(SERVICE)
        if comment is not None:
            rows.append((number, comment, not bare))
            if inside or opens:
                claimed.add(len(rows) - 1)
        if not bare:
            run = [*run, len(rows) - 1] if comment is not None else []
            continue
        if opens:
            claimed.update(run)
        depth += bare.count("{") - bare.count("}")
        inside = (inside or opens) and depth > 0
        run = []
    if not started:
        msg = f"no {SYNTAX!r} line, so the file header cannot be told from the body"
        raise ProtoReadError(msg)
    return [
        Comment(line=number, text=said, leading=leading, service=index in claimed)
        for index, (number, said, leading) in enumerate(rows)
    ]


def rust_docs(text: str) -> list[str]:
    """Return what every `///` line of a generated stub says, in file order."""
    return [
        stripped[len(DOC) :]
        for stripped in (line.strip() for line in text.splitlines())
        if stripped.startswith(DOC)
    ]


def normalize(text: str) -> str:
    """Reduce one comment to the form both versions share."""
    plain = _HEADING.sub("", text.replace(r"\[", "[").replace(r"\]", "]").strip())
    if plain and set(plain) == {"-"}:
        return RULE
    return plain
