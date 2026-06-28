"""Repo gate: fail when a non-test source file exceeds the line cap (AGENTS.md gate 1).

The cap counts ALL lines -- code, comments, and blanks alike -- because it targets
cognitive load, not statement count. Test code and clearly marked generated-code
directories (`_generated`, ADR-0001 decision 7) are exempt.
"""

import argparse
import sys
from fnmatch import fnmatch
from pathlib import Path
from typing import NamedTuple

DEFAULT_MAX_LINES = 300
SOURCE_SUFFIXES = frozenset({".py", ".rs"})
SKIPPED_DIRS = frozenset(
    {
        ".git",
        ".venv",
        "target",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        "tests",
        "_generated",
    }
)
SKIPPED_FILE_PATTERNS = ("test_*.py", "*_test.py", "conftest.py", "*_test.rs")


class Violation(NamedTuple):
    """A source file whose total line count exceeds the cap."""

    path: Path
    lines: int


def is_skipped_file(name: str) -> bool:
    """Return True when the file name matches a test-file naming pattern."""
    return any(fnmatch(name, pattern) for pattern in SKIPPED_FILE_PATTERNS)


def count_lines(path: Path) -> int:
    """Count every line in the file: code, comments, and blanks alike."""
    return len(path.read_bytes().splitlines())


def scan(root: Path, cap: int) -> list[Violation]:
    """Walk ``root`` and return every non-exempt source file longer than ``cap`` lines."""
    violations: list[Violation] = []
    for directory, dirnames, filenames in root.walk():
        dirnames[:] = sorted(name for name in dirnames if name not in SKIPPED_DIRS)
        for name in sorted(filenames):
            if Path(name).suffix not in SOURCE_SUFFIXES or is_skipped_file(name):
                continue
            path = directory / name
            lines = count_lines(path)
            if lines > cap:
                violations.append(Violation(path=path.relative_to(root), lines=lines))
    return violations


def main(argv: list[str] | None = None) -> int:
    """Run the gate; print any violations and return the process exit code."""
    parser = argparse.ArgumentParser(
        description="Fail when a non-test .py/.rs source file exceeds the line cap.",
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
    violations = scan(root, cap)
    for violation in violations:
        print(f"{violation.path}: {violation.lines} lines (cap {cap})")
    if violations:
        return 1
    print(f"linecap OK: no non-test source file under {root} exceeds {cap} lines")
    return 0


if __name__ == "__main__":  # pragma: no cover -- CLI entry point; main() is unit-tested
    sys.exit(main())
