"""Fail when a non-test source file or a markdown file is over its line cap."""

import argparse
import sys
from collections.abc import Sequence
from fnmatch import fnmatch
from pathlib import Path
from typing import NamedTuple

import backlogindex
from treewalk import walk_files

DEFAULT_MAX_LINES = 300
DEFAULT_DOCUMENT_MAX_LINES = 250
SOURCE_SUFFIXES = frozenset({".py", ".rs", ".ts", ".tsx"})
MARKDOWN = ".md"
EXTRA_SKIPS = frozenset({"tests", "_generated"})
SKIPPED_FILE_PATTERNS = (
    "test_*.py",
    "*_test.py",
    "conftest.py",
    "*_test.rs",
    "*.test.ts",
    "*.test.tsx",
    "test-setup.ts",
)

SOURCE_KIND = "non-test source file"
DOCUMENT_KIND = "markdown file"

MIN_FILES = 1

GENERATED_BY_BACKLOG = "`just backlog` writes this index from the task files."


class UnreadableFileError(Exception):
    """A candidate file exists but cannot be read."""


class ExemptionError(Exception):
    """An exemption names a file that is absent, unreadable, or no longer generated."""


class Exemption(NamedTuple):
    """A markdown file left out of the cap, with the text that shows it is written by a tool."""

    path: str
    marker: str
    reason: str


EXEMPTIONS = (
    Exemption(
        path="docs/refinements/index.md", marker=backlogindex.BEGIN, reason=GENERATED_BY_BACKLOG
    ),
    Exemption(path="docs/host/index.md", marker=backlogindex.BEGIN, reason=GENERATED_BY_BACKLOG),
)


class Violation(NamedTuple):
    """A file whose total line count exceeds the cap that applies to it."""

    path: Path
    lines: int
    cap: int


class Tally(NamedTuple):
    """The files one rule measured after every exclusion, and their lines."""

    files: int
    lines: int

    def plus(self, lines: int) -> "Tally":
        """Return this tally with one more file of ``lines`` lines counted."""
        return Tally(files=self.files + 1, lines=self.lines + lines)


class Scan(NamedTuple):
    """What each rule measured in one walk, and the files over their cap."""

    sources: Tally
    documents: Tally
    violations: list[Violation]


def is_skipped_file(name: str) -> bool:
    """Return True when the file name matches a test-file naming pattern."""
    return any(fnmatch(name, pattern) for pattern in SKIPPED_FILE_PATTERNS)


def exempt_documents(root: Path, exemptions: Sequence[Exemption]) -> frozenset[Path]:
    """Return the markdown files left out of the cap, failing on one that is no longer generated."""
    covered: set[Path] = set()
    for item in exemptions:
        try:
            text = (root / item.path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as err:
            msg = f"the exemption for {item.path} names a file that cannot be read: {err}"
            raise ExemptionError(msg) from err
        if item.marker not in text:
            msg = (
                f"the exemption for {item.path} says {item.reason} but the file does not contain "
                f"{item.marker!r}"
            )
            raise ExemptionError(msg)
        covered.add(Path(item.path))
    return frozenset(covered)


def count_lines(path: Path) -> int:
    """Count every line in the file: code, comments, and blanks alike."""
    try:
        return len(path.read_bytes().splitlines())
    except OSError as err:
        msg = f"cannot read {path}: {err}"
        raise UnreadableFileError(msg) from err


def scan(root: Path, cap: int, document_cap: int = DEFAULT_DOCUMENT_MAX_LINES) -> Scan:
    """Walk ``root``, returning what each rule measured and the files longer than their cap."""
    violations: list[Violation] = []
    sources = documents = Tally(files=0, lines=0)
    exempt = exempt_documents(root, EXEMPTIONS)
    for path in walk_files(root, also_skip=EXTRA_SKIPS):
        relative = path.relative_to(root)
        document = relative.suffix == MARKDOWN and relative not in exempt
        if not document and (path.suffix not in SOURCE_SUFFIXES or is_skipped_file(path.name)):
            continue
        lines = count_lines(path)
        if document:
            documents = documents.plus(lines)
            limit = document_cap
        else:
            sources = sources.plus(lines)
            limit = cap
        if lines > limit:
            violations.append(Violation(path=relative, lines=lines, cap=limit))
    return Scan(sources=sources, documents=documents, violations=violations)


def main(argv: list[str] | None = None) -> int:
    """Run the check; print any violations and return the process exit code."""
    parser = argparse.ArgumentParser(
        description=(
            "Fail when a non-test .py/.rs/.ts/.tsx source file, or a markdown file, exceeds its "
            "line cap."
        ),
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(),
        help="directory tree to scan (default: current directory)",
    )
    parser.add_argument(
        "--max-lines",
        type=int,
        default=DEFAULT_MAX_LINES,
        help=f"maximum total lines per source file (default: {DEFAULT_MAX_LINES})",
    )
    parser.add_argument(
        "--document-max-lines",
        type=int,
        default=DEFAULT_DOCUMENT_MAX_LINES,
        help=f"maximum total lines per markdown file (default: {DEFAULT_DOCUMENT_MAX_LINES})",
    )
    args = parser.parse_args(argv)
    root: Path = args.root
    cap: int = args.max_lines
    document_cap: int = args.document_max_lines
    if not root.is_dir():
        print(f"linecap: root {root} is not a directory", file=sys.stderr)
        return 2
    try:
        scanned = scan(root, cap, document_cap)
    except (UnreadableFileError, ExemptionError) as err:
        print(f"linecap: {err}", file=sys.stderr)
        return 2
    for tally, kind in ((scanned.sources, SOURCE_KIND), (scanned.documents, DOCUMENT_KIND)):
        if tally.files < MIN_FILES:
            print(
                f"linecap: no {kind} under {root}; a scan that read nothing cannot fail",
                file=sys.stderr,
            )
            return 2
    for violation in scanned.violations:
        print(f"{violation.path}: {violation.lines} lines (cap {violation.cap})")
    if scanned.violations:
        return 1
    for tally, kind, limit in (
        (scanned.sources, SOURCE_KIND, cap),
        (scanned.documents, DOCUMENT_KIND, document_cap),
    ):
        print(
            f"linecap OK: {tally.files} {kind}(s) under {root} are within "
            f"{limit} lines, over {tally.lines} line(s) counted"
        )
    return 0


if __name__ == "__main__":  # pragma: no cover -- CLI entry point; main() is unit-tested
    sys.exit(main())
