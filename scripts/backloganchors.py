"""Which anchors a document offers, and every pointer in the repo aimed at one.

A markdown link has two halves and they rot for different reasons. The path rots when a
file moves, and `backlogcheck.py` has held it to resolving since the layout landed. The
**fragment** rots when a heading stops being rendered, which is what renaming an area, or
closing and moving the last task out of one, does: the roll call simply stops emitting that
`### <area>` line while every `index.md#<area>` pointer keeps resolving, and the reader
lands at the top of a long index with no idea which part was meant. A heading renamed in a
decision record strands its pointers exactly the same way, and a sweeping edit renames them
in bulk.

Four decisions make the second half checkable for about the cost of the first:

- **The anchors of a backlog index come from the index the gate is about to require on
  disk**, which is the hand-written halves spliced around the freshly rendered block, never
  the committed file. A stale index is its own reported problem, and validating fragments
  against the headings of a document nobody intends to keep would answer the wrong question.
  Every other document answers with the headings it carries on disk, there being nothing
  else it is about to become.
- **Both halves of an index offer anchors.** The generated roll call renders one heading
  per area or sitting, and the prose around it carries headings people cite too, so the set
  is every heading in that spliced document rather than only the ones a renderer emits.
- **Every markdown file under the root is a source.** Most pointers at a backlog index live
  in decision records and runbooks, which are exactly the readers a rename strands, so
  restricting the scan to the backlog's own files would leave the majority of them
  unguarded.
- **A target is judged when it is a document this same scan reads**, and reported when it
  is markdown and is not. One list decides both halves, so a tree that is vendored, built or
  otherwise not this repo's prose is invisible here in both directions, and the gate never
  asserts what a file it does not maintain renders. A target whose name is not markdown
  carries no headings at all: `body.proto#L42` is a line anchor, a scheme this gate knows
  nothing about, so it is outside the question rather than an unanswered one.

The slug rule is the one GitHub renders with: lowercase, drop every character that is not a
word character, a space or a hyphen, then spaces to hyphens, with a repeated heading
numbered from its second occurrence on. A `#` inside a fenced block is not a heading.
"""

import re
from collections.abc import Mapping
from pathlib import Path
from typing import NamedTuple

LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
HEADING = re.compile(r"^#{1,6} +(\S.*?) *$")
FENCE = re.compile(r"^\s*(?:```|~~~)")
DROPPED = re.compile(r"[^\w \-]")
ELSEWHERE = ("http://", "https://", "mailto:")
MARKDOWN = ".md"

# What a pointer at markdown outside the scan's own reach is told. Failing closed here is
# the whole reason the widening is safe: the alternative, skipping whatever the scan cannot
# answer for, is how the one stale anchor already in this tree survived every gate.
UNREAD = (
    "aims at a document this scan does not read, so nothing here can say which headings it "
    "offers: it is missing, outside the tree, or inside a vendored or built one"
)

# The vendored and built trees, skipped so the scan reads the repo's own prose and not a
# dependency's. This is the list `dashcheck.py` walks with rather than the line cap's,
# for the reason that gate gives: prose in a test or a generated tree is still prose, and a
# pointer written there rots exactly like one written in a decision record.
SKIPPED_DIRS = frozenset(
    {
        ".git",
        ".venv",
        ".claude",
        "target",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        "dist",
        "coverage",
    }
)


class Index(NamedTuple):
    """One backlog index: the name a problem calls it by, and the anchors it will render.

    ``anchors`` is None when this run could not work out what the index renders, in which
    case nothing aimed at it is judged and the run is already failing on the reason.
    """

    name: str
    anchors: frozenset[str] | None


class Document(NamedTuple):
    """One markdown file the scan read: what a problem calls it, and the anchors it offers."""

    name: str
    anchors: frozenset[str]


class Target(NamedTuple):
    """One link that stays in the repo: where it is written, and what it aims at."""

    line: int
    path: str
    fragment: str


def local_targets(text: str) -> list[Target]:
    """Return every markdown link in ``text`` that stays in the repo, with its line."""
    targets: list[Target] = []
    for match in LINK.finditer(text):
        target = match.group(1)
        if target.startswith(ELSEWHERE):
            continue
        path, _, fragment = target.partition("#")
        if path or fragment:
            line = text.count("\n", 0, match.start()) + 1
            targets.append(Target(line=line, path=path, fragment=fragment))
    return targets


def local_links(text: str) -> list[str]:
    """Return every relative link target in ``text`` that names a file, fragments stripped."""
    return [target.path for target in local_targets(text) if target.path]


def slug(heading: str) -> str:
    """Return the anchor a markdown renderer gives the text of ``heading``."""
    return DROPPED.sub("", heading.lower()).replace(" ", "-")


def anchors(text: str) -> frozenset[str]:
    """Return every anchor the document ``text`` offers a link."""
    offered: set[str] = set()
    seen: dict[str, int] = {}
    fenced = False
    for line in text.splitlines():
        if FENCE.match(line):
            fenced = not fenced
            continue
        found = None if fenced else HEADING.match(line)
        if found is None:
            continue
        base = slug(found.group(1))
        repeat = seen.get(base, 0)
        offered.add(base if repeat == 0 else f"{base}-{repeat}")
        seen[base] = repeat + 1
    return frozenset(offered)


def markdown_files(root: Path) -> list[Path]:
    """Return every markdown file under ``root``, in walk order, vendored trees skipped."""
    found: list[Path] = []
    for directory, dirnames, filenames in root.walk():
        dirnames[:] = sorted(name for name in dirnames if name not in SKIPPED_DIRS)
        found.extend(
            directory / name
            for name in sorted(filenames)
            if name.endswith(MARKDOWN) and (directory / name).is_file()
        )
    return found


def check(root: Path, indexes: Mapping[Path, Index]) -> list[str]:
    """Return one problem per fragment aimed at a heading its target does not offer."""
    problems: list[str] = []
    sources: list[tuple[Path, str]] = []
    documents: dict[Path, Document] = {}
    for path in markdown_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as err:
            problems.append(f"{path.relative_to(root)}: cannot be read: {err}")
            continue
        sources.append((path, text))
        name = path.relative_to(root).as_posix()
        documents[path.resolve()] = Document(name=name, anchors=anchors(text))
    for path, text in sources:
        problems.extend(_faults(root, path, text, indexes, documents))
    return problems


def _faults(
    root: Path,
    path: Path,
    text: str,
    indexes: Mapping[Path, Index],
    documents: Mapping[Path, Document],
) -> list[str]:
    """Return one problem per pointer in ``path`` aimed at an anchor its target lacks."""
    problems: list[str] = []
    for target in local_targets(text):
        if not target.fragment:
            continue
        # An empty path is a pointer into the document it is written in, which matters
        # because an index links to its own hand-written sections.
        aimed = (path.parent / target.path).resolve() if target.path else path.resolve()
        fault = _fault(aimed, target.fragment, indexes, documents)
        if fault is not None:
            where = f"{path.relative_to(root)}:{target.line}"
            problems.append(f"{where}: pointer '{target.path}#{target.fragment}' {fault}")
    return problems


def _fault(
    aimed: Path,
    fragment: str,
    indexes: Mapping[Path, Index],
    documents: Mapping[Path, Document],
) -> str | None:
    """Return what is wrong with one pointer's fragment, or None when nothing is."""
    index = indexes.get(aimed)
    if index is not None:
        if index.anchors is None or fragment in index.anchors:
            return None
        return f"aims at a heading {index.name} does not render"
    if aimed.suffix != MARKDOWN:
        return None
    document = documents.get(aimed)
    if document is None:
        return UNREAD
    if fragment in document.anchors:
        return None
    return f"aims at a heading {document.name} does not offer"
