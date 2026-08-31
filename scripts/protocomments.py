r"""One seam comment in both of its spellings: as the proto writes it, as prost re-spells it.

Split out of `stubcheck.py`, which owns the rule; this module owns only the reading and the
normalization that lets the two spellings be compared at all. It is a line reader rather than a
protobuf parse, because these gates are stdlib-only (`pyproject.toml` in this directory), and it
raises on a shape it was not taught rather than walking past it.

**Where the proto body starts.** Everything up to and including the `syntax = ` line is the file
header. A comment there attaches to no declaration, so protoc records it against nothing and
prost copies it nowhere; reading it would report phantom misses on a tree that is perfectly in
sync. A file carrying no `syntax = ` line at all is refused rather than read whole, because the
reader would then have no way to tell that header from the body.

**What a comment is.** The text after the first `//` that is not inside a string literal, whether
the line carries code before it (`optional float level = 1; // clamped to [0.0, 1.0]`) or nothing
at all. The string rule is why this is a scan and not a `split("//")`: a `https://` inside a proto
option would otherwise be read as the start of a comment, and the real comment it truncated would
go unchecked. A `/*` block comment raises rather than being skipped, for the reason
`composemounts.py` raises on a shape it was not taught: prost copies those too, in a form this
reader does not parse, so walking past one would leave its text unchecked.

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

**How many copies a comment comes out as**, which is what `service` records. Tonic writes every
service into two modules, a client and a server, and documents both from the one declaration, so
a comment the proto attaches to a `service` block arrives in the stub **twice** and every other
comment arrives once. That count is the whole difference between asking whether the stub still
says a thing anywhere and asking whether it still says it in both places, which is what a reader
opening either module actually reads. A comment belongs to a service when it stands inside the
block or in the unbroken run of comment lines directly above the `service` line; a blank line
between the run and the declaration detaches it, and a detached comment is claimed for nothing,
since claiming one copy too many would fail on a tree that is perfectly in sync.
"""

import re
from typing import NamedTuple

# The declaration that ends the file header. The line itself is header too: a trailing comment on
# it would attach to the syntax statement, which generates no item for prost to document.
SYNTAX = "syntax = "

# The declaration tonic documents twice, and how many copies of its comments the stub then holds.
SERVICE = "service "
COPIES = 2

# What a doc comment looks like in the generated stub, and what a rule line reduces to.
DOC = "///"
RULE = "---"

# What opens a string literal in proto, inside which a `//` punctuates nothing.
QUOTES = ('"', "'")

_HEADING = re.compile(r"^#+[ \t]*")


class ProtoReadError(Exception):
    """A proto file this reader cannot read: no syntax line, or a block comment."""


class Comment(NamedTuple):
    """One comment in the proto body: where it sits, what it says, and how it comes out.

    ``service`` says the stub holds ``COPIES`` of it rather than one. It defaults to false because
    that is the claim every comment starts with and only a `service` block above or around it
    changes.
    """

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
    """Return every comment in the proto body, in file order, raising on a file with no body.

    The walk carries two things past each line: how deep in braces it is, so a comment inside a
    `service` block is known for one, and the unbroken run of comment-only lines it has just
    passed, so the banner above a `service` line can be claimed once that line arrives. Any line
    carrying code ends the run, and so does a blank one, which is how protoc detaches a comment.
    """
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
    """Reduce one comment to the form both of its spellings share."""
    plain = _HEADING.sub("", text.replace(r"\[", "[").replace(r"\]", "]").strip())
    if plain and set(plain) == {"-"}:
        return RULE
    return plain
