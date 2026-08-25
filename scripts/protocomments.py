r"""One seam comment in both of its spellings: as the proto writes it, as prost re-spells it."""

import re
from typing import NamedTuple

# The declaration that ends the file header. The line itself is header too: a trailing comment on
# it would attach to the syntax statement, which generates no item for prost to document.
SYNTAX = "syntax = "

# What a doc comment looks like in the generated stub, and what a rule line reduces to.
DOC = "///"
RULE = "---"

# What opens a string literal in proto, inside which a `//` punctuates nothing.
QUOTES = ('"', "'")

_HEADING = re.compile(r"^#+[ \t]*")


class ProtoReadError(Exception):
    """A proto file this reader will not guess at: no syntax line, or a block comment."""


class Comment(NamedTuple):
    """One comment in the proto body: where it sits, what it says, whether it stands alone."""

    line: int
    text: str
    leading: bool


def split_comment(number: int, line: str) -> tuple[str, str | None]:
    """Return the code on one line and the comment after its first unquoted `//`, if any."""
    quote = ""
    index = 0
    while index < len(line):
        char = line[index]
        if quote:
            if char == "\\":
                index += 1  # an escape inside a string, so the next character closes nothing
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
    """Return every comment in the proto body, in file order, refusing a file with no body."""
    found: list[Comment] = []
    started = False
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not started:
            started = line.startswith(SYNTAX)
            continue
        code, comment = split_comment(number, line)
        if comment is not None:
            found.append(Comment(line=number, text=comment, leading=not code.strip()))
    if not started:
        msg = f"no {SYNTAX!r} line, so the file header cannot be told from the body"
        raise ProtoReadError(msg)
    return found


def rust_docs(text: str) -> list[str]:
    """Return what every `///` line of a generated stub says, in file order."""
    return [
        stripped[len(DOC) :]
        for stripped in (line.strip() for line in text.splitlines())
        if stripped.startswith(DOC)
    ]


def normalize(text: str) -> str:
    """Reduce one comment to the form both of its spellings share."""
    plain = _HEADING.sub("", text.replace(r"\[", "[").replace(r"\]", "]").strip())
    if plain and set(plain) == {"-"}:
        return RULE
    return plain
