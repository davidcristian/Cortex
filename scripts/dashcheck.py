"""Repo gate: fail when a tracked text file uses a dash as sentence punctuation."""

import argparse
import sys
from pathlib import Path
from typing import NamedTuple

ALLOW_PRAGMA = "dashcheck: allow"
EM_DASH = "\u2014"
EN_DASH = "\u2013"

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


class UnreadableFileError(Exception):
    """A candidate file exists but cannot be read."""


class Violation(NamedTuple):
    """One line using a dash as sentence punctuation."""

    path: Path
    line: int
    kind: str
    text: str


def is_binary(data: bytes) -> bool:
    """Return True for data that is not UTF-8 text (assets, images, compiled output)."""
    if b"\x00" in data:
        return True
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return True
    return False


def find_in_line(line: str) -> str | None:
    """Return the offending dash kind in ``line``, or None when it is clean."""
    if ALLOW_PRAGMA in line:
        return None
    if EM_DASH in line:
        return "em dash"
    if f" {EN_DASH} " in line:
        return "spaced en dash"
    return None


def scan_text(path: Path, text: str) -> list[Violation]:
    """Return every punctuating-dash violation in ``text``."""
    violations: list[Violation] = []
    for number, line in enumerate(text.splitlines(), start=1):
        kind = find_in_line(line)
        if kind is not None:
            violations.append(Violation(path=path, line=number, kind=kind, text=line.strip()))
    return violations


def read_text(path: Path) -> str | None:
    """Return the file's text, or None when it is binary. Raise if unreadable."""
    try:
        data = path.read_bytes()
    except OSError as err:
        msg = f"cannot read {path}: {err}"
        raise UnreadableFileError(msg) from err
    if is_binary(data):
        return None
    return data.decode("utf-8")


def scan(root: Path) -> list[Violation]:
    """Walk ``root`` and return every punctuating-dash violation in its text files."""
    violations: list[Violation] = []
    for directory, dirnames, filenames in root.walk():
        dirnames[:] = sorted(name for name in dirnames if name not in SKIPPED_DIRS)
        for name in sorted(filenames):
            path = directory / name
            if not path.is_file():  # dangling symlink or other non-regular file
                continue
            text = read_text(path)
            if text is None:
                continue
            violations.extend(scan_text(path.relative_to(root), text))
    return violations


def main(argv: list[str] | None = None) -> int:
    """Run the gate; print any violations and return the process exit code."""
    parser = argparse.ArgumentParser(
        description="Fail when a text file uses a dash as sentence punctuation.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(),
        help="directory tree to scan (default: current directory)",
    )
    args = parser.parse_args(argv)
    root: Path = args.root
    if not root.is_dir():
        print(f"dashcheck: root {root} is not a directory", file=sys.stderr)
        return 2
    try:
        violations = scan(root)
    except UnreadableFileError as err:
        print(f"dashcheck: {err}", file=sys.stderr)
        return 2
    for violation in violations:
        print(f"{violation.path}:{violation.line}: {violation.kind}: {violation.text}")
    if violations:
        print(
            f"\ndashcheck: {len(violations)} line(s) use a dash as punctuation. "
            f"Restructure the sentence; do not swap in another mark. "
            f"If the dash carries meaning, add '{ALLOW_PRAGMA}' with a reason.",
            file=sys.stderr,
        )
        return 1
    print(f"dashcheck OK: no text file under {root} uses a dash as punctuation")
    return 0


if __name__ == "__main__":  # pragma: no cover -- CLI entry point; main() is unit-tested
    sys.exit(main())
