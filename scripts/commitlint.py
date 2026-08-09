"""Commit-message style gate: the machine-checkable half of the AGENTS.md commit rules."""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

MAX_HEADER_LENGTH = 72

# The width AGENTS.md wraps a commit body at. Same number as the header cap, checked separately
# because the header has its own message and reporting one mistake twice is noise.
MAX_BODY_WIDTH = 72

_HEADER = re.compile(r"^[a-z]+(?:\([^)]*\))?!?: (?P<subject>.+)$")
# Git-generated or rebase-tooling headers that are exempt from subject style.
_EXEMPT_PREFIXES = ("Merge ", "fixup! ", "squash! ", "amend! ")

# A dash used as punctuation. The en dash is banned outright (a range takes a plain
# hyphen); ``--flag`` and a leading ``--`` are not punctuation and stay legal.
_DASHES = (
    (re.compile("\u2014"), "an em dash"),
    (re.compile("\u2013"), "an en dash"),
    (re.compile(r"\S\s+--\s"), "a spaced ASCII --"),
)

# Numbered pointers into docs that get renumbered, restructured, or deleted.
_VOLATILE = (
    (re.compile(r"\bslices?\s*[0-9]", re.IGNORECASE), "slice number"),
    (re.compile(r"\bADR[-\s]?[0-9]", re.IGNORECASE), "decision-record number"),
    (re.compile(r"\broadmap\b", re.IGNORECASE), "roadmap reference"),
    (re.compile(r"\bassumption\s*[0-9]", re.IGNORECASE), "numbered assumption"),
    (re.compile(r"\bincrement\s*[0-9]", re.IGNORECASE), "numbered increment"),
    # "gate 100%" is a coverage figure, not a pointer into the gate list.
    (re.compile(r"\bgate\s*[0-9](?!00%)", re.IGNORECASE), "numbered gate"),
    (re.compile(r"\bdecision\s*[0-9]", re.IGNORECASE), "numbered decision"),
    (re.compile(r"\baudit\s*[0-9]", re.IGNORECASE), "numbered audit"),
)

_HEX = re.compile(r"\b[0-9a-f]{7,40}\b")

# A fenced block, spelled the way Markdown spells it, which is how every forge renders a
# commit body. Either fence character toggles, and an info string (```bash) is still a fence.
_FENCE = re.compile(r"^\s*(?:```|~~~)")

_PROMPT = re.compile(r"^\s*\$ \S")


def check_header(header: str) -> list[str]:
    """Return the style violations in one commit header (empty = clean)."""
    if header.startswith(_EXEMPT_PREFIXES):
        return []
    match = _HEADER.match(header)
    if match is None:
        return []  # not CC-shaped: conventional-pre-commit owns that error
    problems: list[str] = []
    if len(header) > MAX_HEADER_LENGTH:
        problems.append(
            f"header is {len(header)} chars; AGENTS.md caps the subject line at {MAX_HEADER_LENGTH}"
        )
    subject = match.group("subject")
    if subject[0].isupper():
        problems.append("subject must start lowercase")
    if subject.rstrip().endswith("."):
        problems.append("subject must not end with a period")
    return problems


def commit_exists(token: str, repo: Path) -> bool:
    """Return True when ``token`` resolves to a commit in ``repo``'s object database."""
    # This runs as a commit-msg hook, and git exports GIT_DIR to its hooks. That variable
    # outranks the -C below, so inheriting it would answer for whatever repository git is
    # mid-commit in rather than the ``repo`` asked about. Strip git's variables entirely.
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    try:
        result = subprocess.run(  # noqa: S603 -- fixed argv, no shell; token is [0-9a-f]+
            ["git", "-C", str(repo), "cat-file", "-e", f"{token}^{{commit}}"],  # noqa: S607 -- git resolves on PATH; a pinned path is not portable
            capture_output=True,
            check=False,
            env=env,
        )
    except OSError:  # git missing: cannot disprove the hash, so do not block the commit
        return False
    return result.returncode == 0


def too_wide(line: str) -> bool:
    """Whether ``line`` is past the wrap **and** could have been wrapped."""
    if len(line) <= MAX_BODY_WIDTH:
        return False
    words = line.split()
    return len(words) > 1 and max(len(word) for word in words) <= MAX_BODY_WIDTH


def is_fence(line: str) -> bool:
    """Whether ``line`` opens or closes a fenced block."""
    return _FENCE.match(line) is not None


def is_pasted_command(line: str) -> bool:
    """Whether ``line`` is a terminal paste the author marked with a shell prompt."""
    return _PROMPT.match(line) is not None


def check_widths(lines: list[str]) -> list[str]:
    """Return the wrap violations below the header, and an unclosed fence if one is left open."""
    problems: list[str] = []
    opened_at: int | None = None
    for number, line in enumerate(lines[1:], start=2):
        if is_fence(line):
            opened_at = None if opened_at is not None else number
        elif opened_at is None and not is_pasted_command(line) and too_wide(line):
            problems.append(
                f"line {number} is {len(line)} chars; AGENTS.md wraps the body at {MAX_BODY_WIDTH}"
            )
    if opened_at is not None:
        problems.append(
            f"line {opened_at} opens a code fence nothing closes; "
            "an open fence would exempt the rest of the message from the wrap"
        )
    return problems


def check_body_lines(lines: list[str], repo: Path) -> list[str]:
    """Return the width, dash, volatile-reference, and dangling-hash violations in a message."""
    problems: list[str] = check_widths(lines)
    for number, line in enumerate(lines, start=1):
        for pattern, label in _DASHES:
            if pattern.search(line):
                problems.append(f"line {number} uses {label}; restructure the sentence")
        for pattern, label in _VOLATILE:
            match = pattern.search(line)
            if match is not None:
                problems.append(
                    f"line {number} cites a {label} ({match.group(0)!r}); describe the substance"
                )
        problems.extend(
            f"line {number} cites commit {token!r}; a rewrite invalidates it"
            for token in _HEX.findall(line)
            if commit_exists(token, repo)
        )
    return problems


def main(argv: list[str] | None = None) -> int:
    """Check one commit-message file; nonzero + stderr on violations."""
    parser = argparse.ArgumentParser(
        description="Enforce the AGENTS.md commit-message style rules on a commit message.",
    )
    parser.add_argument("message_file", type=Path, help="path to the commit-message file")
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path(),
        help="repository to resolve commit hashes against (default: current directory)",
    )
    args = parser.parse_args(argv)
    message_file: Path = args.message_file
    repo: Path = args.repo
    text = message_file.read_text(encoding="utf-8")
    lines = [line for line in text.splitlines() if not line.startswith("#")]
    header = lines[0] if lines else ""
    problems = [f"{problem}: {header!r}" for problem in check_header(header)]
    if not header.startswith(_EXEMPT_PREFIXES):
        problems.extend(check_body_lines(lines, repo))
    for problem in problems:
        print(f"commitlint: {problem}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":  # pragma: no cover -- CLI entry point; main() is unit-tested
    sys.exit(main())
