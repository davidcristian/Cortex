"""Which anchors a document offers, and every pointer in the repo aimed at one."""

import re
from collections.abc import Mapping
from pathlib import Path
from typing import NamedTuple

from headingshapes import headings
from headingshapes import problems as shape_problems
from treewalk import walk_files

LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
DROPPED = re.compile(r"[^\w \-]")
ELSEWHERE = ("http://", "https://", "mailto:")
MARKDOWN = ".md"

# What a pointer at markdown outside the scan's own reach is told. Failing closed is what makes
# reading every markdown file safe: skipping whatever the scan cannot answer for is how the one
# stale anchor already in this tree survived every gate.
UNREAD = (
    "aims at a document this scan does not read, so nothing here can say which headings it "
    "offers: it is missing, outside the tree, or inside a vendored or built one"
)


class Index(NamedTuple):
    """One backlog index: the name a problem calls it by, and the anchors it will render.

    ``anchors`` is None when this run could not work out what the index renders, in which case
    nothing aimed at it is judged and the run is already failing on that reason.
    """

    name: str
    anchors: frozenset[str] | None


class Document(NamedTuple):
    """One markdown file the scan read: what a problem calls it, and the anchors it offers.

    ``anchors`` is None when the file carries a heading this rule cannot slug, in which
    case nothing aimed at it is judged and the run is already failing on that heading.
    """

    name: str
    anchors: frozenset[str] | None


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
    for _, heading in headings(text):
        base = slug(heading)
        repeat = seen.get(base, 0)
        offered.add(base if repeat == 0 else f"{base}-{repeat}")
        seen[base] = repeat + 1
    return frozenset(offered)


def markdown_files(root: Path) -> list[Path]:
    """Return every markdown file under ``root``, in walk order, vendored trees skipped."""
    return [path for path in walk_files(root) if path.suffix == MARKDOWN]


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
        refused = shape_problems(name, text)
        problems.extend(refused)
        documents[path.resolve()] = Document(name=name, anchors=None if refused else anchors(text))
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
    if document.anchors is None or fragment in document.anchors:
        return None
    return f"aims at a heading {document.name} does not offer"
