"""Repo gate: fail when a non-test source file exceeds the line cap (AGENTS.md gate 1).

The cap counts ALL lines -- code, comments, and blanks alike -- because it targets
cognitive load, not statement count. Test code and clearly marked generated-code
directories (`_generated`, ADR-0001 decision 7) are exempt.

The scan covers all three of the repo's gated toolchains: Python, Rust, and the overlay's
TypeScript (ADR-0011 line-cap addendum). It deliberately does not cover the stylesheet,
the markup, or `proto/body.proto`, which are not modules the cap's split-by-responsibility
remedy applies to; see that addendum for the argument and the repo-gates tasks in
docs/refinements/ for what stays unmeasured.

**The success line states what the walk read**, files and lines after the exclusions rather
than before, because "no file exceeds the cap" is equally true of a tree the scan never
entered. The two numbers are a reading and nothing asserts them. What IS asserted is the
floor under them: reading no source file at all exits 2, the way `composefiles.py` already
refuses an empty compose walk, since a scan that read nothing is the one failure a gate this
shape cannot report any other way.
"""

import argparse
import sys
from fnmatch import fnmatch
from pathlib import Path
from typing import NamedTuple

from skippeddirs import SKIPPED_DIRS as SHARED_SKIPS

DEFAULT_MAX_LINES = 300
SOURCE_SUFFIXES = frozenset({".py", ".rs", ".ts", ".tsx"})
# The trees no walk here enters, plus the two only this one skips: a 400-line test is not the
# cap's problem, and generated code is exempt from every quality gate. Neither is true of prose,
# which is why the dash ban and the anchor scan read the shared list without them.
SKIPPED_DIRS = SHARED_SKIPS | {"tests", "_generated"}
# One naming rule per toolchain, each matching what that toolchain's runner already calls a
# test: pytest's `test_*.py`/`*_test.py`/`conftest.py`, Rust's `tests/` plus `*_test.rs`, and
# Vitest's `src/**/*.test.{ts,tsx}` from `body/app/vite.config.ts` with `test-setup.ts`, its
# `setupFiles` entry and the TypeScript analog of `conftest.py`.
SKIPPED_FILE_PATTERNS = (
    "test_*.py",
    "*_test.py",
    "conftest.py",
    "*_test.rs",
    "*.test.ts",
    "*.test.tsx",
    "test-setup.ts",
)

# The floor under the reading below. One file is the whole of it: a walk that measured a single
# source file has entered the tree, and a walk that measured none cannot fail on anything.
MIN_FILES = 1


class UnreadableFileError(Exception):
    """A candidate source file exists but cannot be read."""


class Violation(NamedTuple):
    """A source file whose total line count exceeds the cap."""

    path: Path
    lines: int


class Scan(NamedTuple):
    """One walk: the collection the verdict is over, then the verdict.

    ``files`` and ``lines`` count what was measured after every exclusion, which is the only
    count worth printing; the number of files the walk enumerated says nothing about what the
    cap was applied to.
    """

    files: int
    lines: int
    violations: list[Violation]


def is_skipped_file(name: str) -> bool:
    """Return True when the file name matches a test-file naming pattern."""
    return any(fnmatch(name, pattern) for pattern in SKIPPED_FILE_PATTERNS)


def count_lines(path: Path) -> int:
    """Count every line in the file: code, comments, and blanks alike."""
    try:
        return len(path.read_bytes().splitlines())
    except OSError as err:
        msg = f"cannot read {path}: {err}"
        raise UnreadableFileError(msg) from err


def scan(root: Path, cap: int) -> Scan:
    """Walk ``root``, counting what it measures and returning the files longer than ``cap``."""
    violations: list[Violation] = []
    files = 0
    total = 0
    for directory, dirnames, filenames in root.walk():
        dirnames[:] = sorted(name for name in dirnames if name not in SKIPPED_DIRS)
        for name in sorted(filenames):
            if Path(name).suffix not in SOURCE_SUFFIXES or is_skipped_file(name):
                continue
            path = directory / name
            if not path.is_file():  # dangling symlink or other non-regular file
                continue
            lines = count_lines(path)
            files += 1
            total += lines
            if lines > cap:
                violations.append(Violation(path=path.relative_to(root), lines=lines))
    return Scan(files=files, lines=total, violations=violations)


def main(argv: list[str] | None = None) -> int:
    """Run the gate; print any violations and return the process exit code."""
    parser = argparse.ArgumentParser(
        description="Fail when a non-test .py/.rs/.ts/.tsx source file exceeds the line cap.",
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
        help=f"maximum total lines per file (default: {DEFAULT_MAX_LINES})",
    )
    args = parser.parse_args(argv)
    root: Path = args.root
    cap: int = args.max_lines
    if not root.is_dir():
        print(f"linecap: root {root} is not a directory", file=sys.stderr)
        return 2
    try:
        scanned = scan(root, cap)
    except UnreadableFileError as err:
        print(f"linecap: {err}", file=sys.stderr)
        return 2
    if scanned.files < MIN_FILES:
        print(
            f"linecap: no non-test source file under {root}; a scan that read nothing cannot fail",
            file=sys.stderr,
        )
        return 2
    for violation in scanned.violations:
        print(f"{violation.path}: {violation.lines} lines (cap {cap})")
    if scanned.violations:
        return 1
    print(
        f"linecap OK: {scanned.files} non-test source file(s) under {root} are within "
        f"{cap} lines, over {scanned.lines} line(s) counted"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover -- CLI entry point; main() is unit-tested
    sys.exit(main())
