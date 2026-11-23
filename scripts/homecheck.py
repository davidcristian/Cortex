"""Fail when a text file in this repo names a home directory that is not a placeholder."""

import argparse
import re
import sys
from pathlib import Path
from typing import NamedTuple

from dashcheck import IgnoreQueryError, UnreadableFileError, ignored_paths, read_text
from treewalk import walk_files

PLACEHOLDERS = frozenset({"cortex", "me", "nobody", "u", "user"})
HOME_PATH = re.compile(r"(?<![\w.-])/home/(\w[\w.-]*)(/?)")
SCRATCH_NAME = re.compile(r"(?<![\w-])-home-(\w+)-")

MIN_FILES = 1


class Violation(NamedTuple):
    """One line naming a home directory."""

    path: Path
    line: int
    name: str


class Scan(NamedTuple):
    """What one walk read, and every violation it found."""

    files: int
    violations: list[Violation]


def home_names(line: str) -> list[str]:
    """Return each home directory name in ``line`` that is not a placeholder."""
    names = [
        match.group(1)
        for match in HOME_PATH.finditer(line)
        if match.group(2) or "." not in match.group(1)
    ]
    names.extend(match.group(1) for match in SCRATCH_NAME.finditer(line))
    return [name for name in names if name not in PLACEHOLDERS]


def scan_text(path: Path, text: str) -> list[Violation]:
    """Return every line of ``text`` that names a home directory."""
    return [
        Violation(path=path, line=number, name=name)
        for number, line in enumerate(text.splitlines(), start=1)
        for name in home_names(line)
    ]


def scan(root: Path) -> Scan:
    """Walk ``root`` minus what git ignores, counting the text read and every violation."""
    ignored = ignored_paths(root)
    violations: list[Violation] = []
    files = 0
    for path in walk_files(root, enter=lambda inside: inside.as_posix() not in ignored):
        relative = path.relative_to(root)
        if relative.as_posix() in ignored:
            continue
        text = read_text(path)
        if text is None:
            continue
        files += 1
        violations.extend(scan_text(relative, text))
    return Scan(files=files, violations=violations)


def main(argv: list[str] | None = None) -> int:
    """Run the check; print any violations and return the process exit code."""
    parser = argparse.ArgumentParser(description="Fail when a text file names a home directory.")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(),
        help="directory tree to scan (default: current directory)",
    )
    args = parser.parse_args(argv)
    root: Path = args.root
    if not root.is_dir():
        print(f"homecheck: root {root} is not a directory", file=sys.stderr)
        return 2
    try:
        scanned = scan(root)
    except (UnreadableFileError, IgnoreQueryError) as err:
        print(f"homecheck: {err}", file=sys.stderr)
        return 2
    if scanned.files < MIN_FILES:
        print(
            f"homecheck: no text file under {root}; a scan that read nothing cannot fail",
            file=sys.stderr,
        )
        return 2
    for violation in scanned.violations:
        print(f"{violation.path}:{violation.line}: home directory {violation.name}")
    if scanned.violations:
        print(
            f"\nhomecheck: {len(scanned.violations)} home directory name(s) found. The repo "
            f"names no person: write /home/user, or name a scratch folder by its slot and date.",
            file=sys.stderr,
        )
        return 1
    print(f"homecheck OK: {scanned.files} text file(s) under {root} name no home directory")
    return 0


if __name__ == "__main__":  # pragma: no cover -- CLI entry point; main() is unit-tested
    sys.exit(main())
