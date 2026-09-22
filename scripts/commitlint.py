"""Check one commit message against the style rules in AGENTS.md a machine can read."""

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

import bannedwords
from gitenv import git_env
from markdownfences import Fences

MAX_HEADER_LENGTH = 72

MAX_BODY_WIDTH = 72

MAX_BODY_WORDS = 50

_HEADER = re.compile(r"^[a-z]+(?:\([^)]*\))?!?: (?P<subject>.+)$")
_EXEMPT_PREFIXES = ("Merge ", "fixup! ", "squash! ", "amend! ")

_DASHES = (
    (re.compile("\u2014"), "an em dash"),
    (re.compile("\u2013"), "an en dash"),
    (re.compile(r"\S\s+--\s"), "a spaced ASCII --"),
)

_VOLATILE = (
    (re.compile(r"\bslices?\s*[0-9]", re.IGNORECASE), "slice number"),
    (re.compile(r"\bADR[-\s]?[0-9]", re.IGNORECASE), "decision-record number"),
    (re.compile(r"\broadmap\b", re.IGNORECASE), "roadmap reference"),
    (re.compile(r"\bassumption\s*[0-9]", re.IGNORECASE), "numbered assumption"),
    (re.compile(r"\bincrement\s*[0-9]", re.IGNORECASE), "numbered increment"),
    # `gate 100%` is a coverage figure rather than a pointer into the list of checks.
    (re.compile(r"\bgate\s*[0-9](?!00%)", re.IGNORECASE), "numbered `gate`"),
    (re.compile(r"\bdecision\s*[0-9]", re.IGNORECASE), "numbered decision"),
    (re.compile(r"\baudit\s*[0-9]", re.IGNORECASE), "numbered audit"),
)

_HEX = re.compile(r"\b[0-9a-f]{7,40}\b")

_PROMPT = re.compile(r"^\s*\$ \S")


def check_header(header: str) -> list[str]:
    """Return the style violations in one commit header (empty = clean)."""
    if header.startswith(_EXEMPT_PREFIXES):
        return []
    match = _HEADER.match(header)
    if match is None:
        return []
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
    try:
        result = subprocess.run(  # noqa: S603 -- fixed argv, no shell; token is [0-9a-f]+
            ["git", "-C", str(repo), "cat-file", "-e", f"{token}^{{commit}}"],  # noqa: S607 -- git resolves on PATH; an absolute path is not portable
            capture_output=True,
            check=False,
            env=git_env(),
        )
    except OSError:
        return False
    return result.returncode == 0


def too_wide(line: str) -> bool:
    """Whether ``line`` is past the wrap **and** could have been wrapped."""
    if len(line) <= MAX_BODY_WIDTH:
        return False
    words = line.split()
    return len(words) > 1 and max(len(word) for word in words) <= MAX_BODY_WIDTH


def is_pasted_command(line: str) -> bool:
    """Whether ``line`` is a terminal paste the author marked with a shell prompt."""
    return _PROMPT.match(line) is not None


class Line(NamedTuple):
    """One message line, paired with whether it is a paste rather than the author's prose."""

    number: int
    text: str
    pasted: bool


def classify_lines(lines: list[str]) -> tuple[list[Line], int | None]:
    """Pair every line with its kind, and report the line an unclosed fence was opened on."""
    classified: list[Line] = []
    opened_at: int | None = None
    fences = Fences()
    for number, text in enumerate(lines, start=1):
        if number == 1:
            classified.append(Line(number, text, pasted=False))
        elif fences.bounds(text):
            opened_at = number if fences.inside else None
            classified.append(Line(number, text, pasted=True))
        else:
            pasted = opened_at is not None or is_pasted_command(text)
            classified.append(Line(number, text, pasted=pasted))
    return classified, opened_at


def wrap_problems(classified: list[Line], opened_at: int | None) -> list[str]:
    """Return the wrap violations below the header, and an unclosed fence if one is left open."""
    problems = [
        f"line {line.number} is {len(line.text)} chars; "
        f"AGENTS.md wraps the body at {MAX_BODY_WIDTH}"
        for line in classified
        if line.number > 1 and not line.pasted and too_wide(line.text)
    ]
    if opened_at is not None:
        problems.append(
            f"line {opened_at} opens a code fence nothing closes; "
            "an open fence would exempt the rest of the message from the wrap"
        )
    return problems


def check_widths(lines: list[str]) -> list[str]:
    """Return the wrap violations in a message, classifying its lines first."""
    classified, opened_at = classify_lines(lines)
    return wrap_problems(classified, opened_at)


def length_problems(classified: list[Line]) -> list[str]:
    """Return a violation when the body's own words are over the cap; a paste counts as none."""
    words = sum(len(line.text.split()) for line in classified[1:] if not line.pasted)
    if words <= MAX_BODY_WORDS:
        return []
    return [f"body is {words} words; AGENTS.md caps it at {MAX_BODY_WORDS}"]


def check_body_lines(lines: list[str], repo: Path) -> list[str]:
    """Return the length, width, dash, volatile-reference and dangling-hash violations."""
    classified, opened_at = classify_lines(lines)
    problems: list[str] = wrap_problems(classified, opened_at)
    problems.extend(length_problems(classified))
    for number, text, pasted in classified:
        if not pasted:
            problems.extend(
                f"line {number} uses {label}; restructure the sentence"
                for pattern, label in _DASHES
                if pattern.search(text)
            )
        for pattern, label in _VOLATILE:
            match = pattern.search(text)
            if match is not None:
                problems.append(
                    f"line {number} cites a {label} ({match.group(0)!r}); describe the substance"
                )
        problems.extend(
            f"line {number} cites commit {token!r}; a rewrite invalidates it"
            for token in _HEX.findall(text)
            if commit_exists(token, repo)
        )
    return problems


def check_words(lines: list[str], rules: Path) -> list[str]:
    """Return the banned words used outside a paste, read from the table in ``rules``."""
    try:
        table = bannedwords.read_table(rules)
    except bannedwords.TableError as err:
        return [f"{err}; that table is what the banned-word rule reads"]
    pattern = bannedwords.compile_words(table.words)
    classified, _ = classify_lines(lines)
    prose = [(line.number, line.text) for line in classified if not line.pasted]
    return [
        f'line {hit.line} uses the banned word "{hit.word}"; AGENTS.md gives a plain replacement'
        for run in bannedwords.runs(prose)
        for hit in bannedwords.find_words(run, pattern)
    ]


def main(argv: list[str] | None = None) -> int:
    """Check one commit-message file; nonzero + stderr on violations."""
    parser = argparse.ArgumentParser(
        description="Enforce the AGENTS.md commit-message style rules on a commit message.",
    )
    parser.add_argument("message_file", type=Path, help="path to the commit-message file")
    parser.add_argument(
        "--rules",
        type=Path,
        default=bannedwords.RULES,
        help=f"the AGENTS.md whose table lists the banned words (default: {bannedwords.RULES})",
    )
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
        problems.extend(check_words(lines, args.rules))
    for problem in problems:
        print(f"commitlint: {problem}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":  # pragma: no cover -- CLI entry point; main() is unit-tested
    sys.exit(main())
