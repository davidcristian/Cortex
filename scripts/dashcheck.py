"""Repo gate: fail when a text file this repo owns uses a banned dash.

Prose here never uses an em dash. The rule is stylistic, so nothing but a gate keeps it:
prose is rewritten constantly and the dash returns by default. This scans every text
file, not just `.py`/`.rs`, because the rule covers docs and comments alike.

**The collection is the working tree minus what git ignores** (ADR-0026 dash-ban-collection
addendum). The working tree rather than the commit or the index, deliberately: a file staged
but not committed and a file an agent wrote a minute ago are both prose this repo is about to
own, and a gate reading `git ls-files` would go green on the document being written in front of
it. Minus what git ignores, because the walk used to read generated schemas, a coverage export
and the JSON blocks a live measurement leaves behind, where a banned dash is a red whose remedy
is deleting a file rather than rewriting a sentence. Git is asked once, for the paths it
ignores; a wholly ignored directory is pruned rather than descended. A root git cannot answer
about is a failure and not a quieter scan, because the collection would then be undefined and
the count printed below would be over nothing anybody named.

What counts as punctuation, and what deliberately does not:

- U+2014 EM DASH is always punctuation. Banned.
- U+2013 EN DASH is banned outright, spaced or not. It once survived in a range (a 2-4B
  model, 0.15-0.27 GB of VRAM), but the plain ASCII hyphen is the hand-typed form of a
  range, so nothing is lost by spelling it that way and the rule gets simpler.
- U+2212 MINUS SIGN is arithmetic and stays legal, so `-` is not forced on a subtraction.
- ASCII `--` is NOT flagged. It is this repo's inline-reason idiom
  (`# noqa: DTZ001 -- the naive value under test`, `# pragma: no cover -- reason`), which
  the escape-hatch rule effectively requires. Commit messages are stricter and ban it;
  `commitlint.py` owns that, because there the text is pure prose.

Escape hatch: put `dashcheck: allow` on the offending line with a reason, mirroring the
`# pragma: no cover -- reason` idiom. Only for a dash that carries meaning rather than
punctuating, e.g. an HTML entity test asserting `&#8212;` decodes to the literal
character.

The dashes are spelled as escapes below, not literals, so that this module and its own
tests pass the gate they implement.

**The success line states what the walk read**, text files and lines after the binary skip
rather than before, because "no text file uses a banned dash" is equally true of a tree the
scan never entered. The two numbers are a reading and nothing asserts them; the floor under
them is the assertion, reading no text file at all exiting 2 the way `composefiles.py`
already refuses an empty compose walk.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

ALLOW_PRAGMA = "dashcheck: allow"
EM_DASH = "\u2014"
EN_DASH = "\u2013"

# Pruned before git is consulted. `.git` is the one entry git does not call ignored, and it is
# the reason this list cannot become the ignore answer alone; the rest are trees this repo's own
# `.gitignore` covers too, kept here because `linecap.py` is held to this list and
# `backloganchors.py` reads it, so the three walks skip one set of names rather than three.
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

# The floor under the reading below, and the same one `linecap.py` carries: a walk that read a
# single text file has entered the tree, and a walk that read none cannot fail on anything. It
# now covers a second road to an empty collection, git ignoring everything under the root, which
# is the same fact about the walk arriving a different way.
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
    """Return every path under ``root`` that git ignores, as root-relative posix strings.

    Asked once for the whole walk rather than once per file. ``--directory`` collapses a wholly
    ignored directory into a single entry, which the walk prunes instead of descending, so a
    models directory holding gigabytes is never opened; a directory git ignores only part of is
    listed file by file. The trailing slash comes off so one set answers for files and
    directories alike, a path being one or the other and never both.

    Git's own hook variables are stripped for the reason `bindcheck.py` strips them: these gates
    run inside hooks, where git exports `GIT_DIR`, and that variable outranks the `-C` below.
    """
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    listing = ("ls-files", "--others", "--ignored", "--exclude-standard", "--directory", "-z")
    try:
        result = subprocess.run(  # noqa: S603 -- fixed argv, no shell
            ["git", "-C", str(root), *listing],  # noqa: S607 -- git resolves on PATH; a pinned path is not portable
            capture_output=True,
            check=False,
            env=env,
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
