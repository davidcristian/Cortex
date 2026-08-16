"""Which anchors a backlog index offers, and every pointer in the repo aimed at one."""

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
    """One backlog index: the name a problem calls it by, and the anchors it offers."""

    name: str
    anchors: frozenset[str]


def local_targets(text: str) -> list[tuple[str, str]]:
    """Return every markdown link in ``text`` that stays in the repo, as (path, fragment)."""
    targets: list[tuple[str, str]] = []
    for target in LINK.findall(text):
        if target.startswith(ELSEWHERE):
            continue
        path, _, fragment = target.partition("#")
        if path or fragment:
            targets.append((path, fragment))
    return targets


def local_links(text: str) -> list[str]:
    """Return every relative link target in ``text`` that names a file, fragments stripped."""
    return [path for path, _ in local_targets(text) if path]


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
    """Return one problem per fragment aimed at a heading a backlog index does not render."""
    problems: list[str] = []
    for path in markdown_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as err:
            problems.append(f"{path.relative_to(root)}: cannot be read: {err}")
            continue
        problems.extend(_faults(root, path, text, indexes))
    return problems


def _faults(root: Path, path: Path, text: str, indexes: Mapping[Path, Index]) -> list[str]:
    """Return one problem per pointer in ``path`` aimed at an anchor its index lacks."""
    problems: list[str] = []
    for target, fragment in local_targets(text):
        if not fragment:
            continue
        # An empty path is a pointer into the document it is written in, which matters
        # because an index links to its own hand-written sections.
        aimed = (path.parent / target).resolve() if target else path.resolve()
        index = indexes.get(aimed)
        if index is None or fragment in index.anchors:
            continue
        problems.append(
            f"{path.relative_to(root)}: pointer '{target}#{fragment}' aims at a heading "
            f"{index.name} does not render"
        )
    return problems
