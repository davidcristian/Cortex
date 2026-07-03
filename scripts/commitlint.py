"""Commit-subject style gate: the machine-checkable half of the AGENTS.md commit rules.

Runs as a commit-msg hook next to conventional-pre-commit: that hook validates the
Conventional-Commits structure and the allowed type list; this one enforces the subject
STYLE constraints AGENTS.md states. Those are a header <= 72 chars, lowercase subject, no trailing
period. (Imperative mood is not machine-checkable; it stays convention.) A header that is
not Conventional-Commits-shaped passes here silently: reporting that is the other hook's
job, and two errors for one mistake is noise. Stdlib only, because the hook must run under a
plain ``python3`` with no environment sync.
"""

import argparse
import re
import sys
from pathlib import Path

MAX_HEADER_LENGTH = 72

_HEADER = re.compile(r"^[a-z]+(?:\([^)]*\))?!?: (?P<subject>.+)$")
# Git-generated or rebase-tooling headers that are exempt from subject style.
_EXEMPT_PREFIXES = ("Merge ", "fixup! ", "squash! ", "amend! ")


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


def main(argv: list[str] | None = None) -> int:
    """Check one commit-message file; nonzero + stderr on violations."""
    parser = argparse.ArgumentParser(
        description="Enforce the AGENTS.md commit-subject style rules on a commit message.",
    )
    parser.add_argument("message_file", type=Path, help="path to the commit-message file")
    args = parser.parse_args(argv)
    message_file: Path = args.message_file
    text = message_file.read_text(encoding="utf-8")
    lines = [line for line in text.splitlines() if not line.startswith("#")]
    header = lines[0] if lines else ""
    problems = check_header(header)
    for problem in problems:
        print(f"commitlint: {problem}: {header!r}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":  # pragma: no cover -- CLI entry point; main() is unit-tested
    sys.exit(main())
