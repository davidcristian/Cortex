r"""One seam comment in both of its spellings: as the proto writes it, as prost re-spells it.

Split out of `stubcheck.py`, which owns the rule; this module owns only the reading and the
normalization that lets the two spellings be compared at all. It is a line reader rather than a
protobuf parse, because these gates are stdlib-only (`pyproject.toml` in this directory), and it
stays honest about that by refusing what it does not know rather than walking past it.

**Where the proto body starts.** Everything up to and including the `syntax = ` line is the file
header. A comment there attaches to no declaration, so protoc records it against nothing and
prost copies it nowhere; reading it would report phantom misses on a tree that is perfectly in
sync. A file carrying no `syntax = ` line at all is refused rather than read whole, because the
reader would then have no way to tell that header from the body.

**What a comment is.** The text after the first `//` that is not inside a string literal, whether
the line carries code before it (`optional float level = 1; // clamped to [0.0, 1.0]`) or nothing
at all. The string rule is why this is a scan and not a `split("//")`: a `https://` inside a proto
option would otherwise be read as the start of a comment, and the real comment it truncated would
go unchecked. A `/*` block comment is refused, never skipped, for the reason `composemounts.py`
refuses a shape it has not met: prost copies those too, in a form this reader does not know, and a
reader that quietly walked past one is a gate that cannot fail on what it skipped.

**How prost re-spells a comment on its way into `///`**, which is the whole of `normalize`. Three
things happen to it, each mechanical:

1. `[` and `]` come out escaped as `\[` and `\]`, so rustdoc does not read `clamped to
   [0.0, 1.0]` as an intra-doc link.
2. A block markdown reads as a setext heading comes out as an ATX one: a service banner written
   between two rule lines, `// BodyService is hosted by the body (host-native).`, arrives as
   `/// ## BodyService is hosted by the body (host-native).`.
3. A rule line of any length collapses to `/// ---`.

So the comparison is over normalized text: those escapes undone, leading `#` markers dropped, and
a line of nothing but dashes reduced to one token. The same function runs over both sides on
purpose. A normalization that ran on one side only would be a rule about which file the text came
out of rather than about what the text says, and the proto is free to write either spelling.
"""

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
