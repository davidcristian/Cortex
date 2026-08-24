"""Repo gate: fail when a text file this repo owns uses a banned dash."""

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

from gitenv import git_env

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

MIN_FILES = 1


class UnreadableFileError(Exception):
    """A candidate file exists but cannot be read."""


class IgnoreQueryError(Exception):
    """Git could not say what it ignores under the root, so the collection is undefined."""


class Violation(NamedTuple):
    """One line using a banned dash."""

    path: Path
    line: int
    kind: str
    text: str


class Scan(NamedTuple):
    """One walk: the collection the verdict is over, then the verdict.

    ``files`` and ``lines`` count the text that was read, so a binary file the walk skipped is
    in neither. The rule is per line, which is why the lines are counted as well as the files.
    """

    files: int
    lines: int
    violations: list[Violation]


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
    """Return the banned dash kind in ``line``, or None when it is clean."""
    if ALLOW_PRAGMA in line:
        return None
    if EM_DASH in line:
        return "em dash"
    if EN_DASH in line:
        return "en dash"
    return None


def scan_text(path: Path, text: str) -> list[Violation]:
    """Return every banned-dash violation in ``text``."""
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


def ignored_paths(root: Path) -> frozenset[str]:
    """Return every path under ``root`` that git ignores, as root-relative posix strings."""
    listing = ("ls-files", "--others", "--ignored", "--exclude-standard", "--directory", "-z")
    try:
        result = subprocess.run(  # noqa: S603 -- fixed argv, no shell
            ["git", "-C", str(root), *listing],  # noqa: S607 -- git resolves on PATH; a pinned path is not portable
            capture_output=True,
            check=False,
            env=git_env(),
        )
    except OSError as err:
        msg = f"cannot run git: {err}"
        raise IgnoreQueryError(msg) from err
    if result.returncode != 0:
        detail = result.stderr.decode(errors="replace").strip()
        msg = f"git cannot say what {root} ignores: {detail}"
        raise IgnoreQueryError(msg)
    entries = result.stdout.split(b"\0")
    return frozenset(os.fsdecode(entry).rstrip("/") for entry in entries if entry)


def scan(root: Path) -> Scan:
    """Walk ``root`` minus what git ignores, counting the text read and every violation."""
    ignored = ignored_paths(root)
    violations: list[Violation] = []
    files = 0
    lines = 0
    for directory, dirnames, filenames in root.walk():
        here = directory.relative_to(root)
        dirnames[:] = sorted(
            name
            for name in dirnames
            if name not in SKIPPED_DIRS and (here / name).as_posix() not in ignored
        )
        for name in sorted(filenames):
            relative = here / name
            if relative.as_posix() in ignored:
                continue
            path = directory / name
            if not path.is_file():  # dangling symlink or other non-regular file
                continue
            text = read_text(path)
            if text is None:
                continue
            files += 1
            lines += len(text.splitlines())
            violations.extend(scan_text(relative, text))
    return Scan(files=files, lines=lines, violations=violations)


def main(argv: list[str] | None = None) -> int:
    """Run the gate; print any violations and return the process exit code."""
    parser = argparse.ArgumentParser(
        description="Fail when a text file uses a banned dash.",
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
        scanned = scan(root)
    except (UnreadableFileError, IgnoreQueryError) as err:
        print(f"dashcheck: {err}", file=sys.stderr)
        return 2
    if scanned.files < MIN_FILES:
        print(
            f"dashcheck: no text file under {root}; a scan that read nothing cannot fail",
            file=sys.stderr,
        )
        return 2
    violations = scanned.violations
    for violation in violations:
        print(f"{violation.path}:{violation.line}: {violation.kind}: {violation.text}")
    if violations:
        print(
            f"\ndashcheck: {len(violations)} line(s) use a banned dash. "
            f"For punctuation, restructure the sentence rather than swapping in another "
            f"mark; a range takes a plain hyphen. If the dash carries meaning, add "
            f"'{ALLOW_PRAGMA}' with a reason.",
            file=sys.stderr,
        )
        return 1
    print(
        f"dashcheck OK: {scanned.files} text file(s) under {root} use no banned dash, "
        f"over {scanned.lines} line(s) read"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover -- CLI entry point; main() is unit-tested
    sys.exit(main())
