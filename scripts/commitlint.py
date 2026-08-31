"""Commit-message style gate: the machine-checkable half of the AGENTS.md commit rules.

Runs as a commit-msg hook next to conventional-pre-commit: that hook validates the
Conventional-Commits structure and the allowed type list; this one enforces the STYLE
constraints AGENTS.md states. Those are a header <= 72 chars, lowercase subject, no trailing
period. (Imperative mood is not machine-checkable; it stays convention.) A header that is
not Conventional-Commits-shaped passes here silently: reporting that is the other hook's
job, and two errors for one mistake is noise. Stdlib only, because the hook must run under a
plain ``python3`` with no environment sync.

Beyond the header, the whole message must satisfy three rules that apply to the body too:

- **The body wraps at 72 columns.** A line past it that *could* have been wrapped is a
  violation. Three kinds could not be. One whose longest word alone is over the wrap (a URL,
  a path, a long identifier) has nowhere to break, so reporting it would ask for a rewrite no
  wrapping can make. A line inside a fenced block and a terminal paste marked with a ``$``
  prompt are exempt by their KIND rather than by their width, because a newline moved inside
  a command changes what it says, which is rewriting a message rather than checking it. A
  fence nobody closes is reported, since otherwise one stray fence would exempt the rest of
  the message. A ``BREAKING CHANGE:`` footer is none of the three: it is prose, and it wraps.

- **No dash as punctuation.** Em dash, spaced en dash, and spaced ASCII ``--`` are all
  banned, since a commit message is pure prose. Source files are laxer and keep ``--`` as
  the inline-reason idiom; ``dashcheck.py`` owns that side. A paste is exempt from this rule
  as well as from the wrap, because the ban is on a dash used as PUNCTUATION and verbatim
  text punctuates nothing: ``cargo llvm-cov -- --nocapture`` spells cargo's own argument
  separator, and the rule's remedy, restructuring the sentence, does not exist for words the
  author did not write.
- **No volatile references.** A message must still read correctly once the planning docs
  move on, so it may not cite a slice number, a decision-record number, the roadmap, or
  any numbered pointer into a mutable doc. Commit hashes are checked against the object
  database, so only a hash that actually resolves is reported: a rewrite invalidates it,
  and hex-looking strings that are not commits stay legal. **A paste is not exempt from
  either**, and that is the line the kind exemption stops at: this rule is about the message
  still reading correctly after the thing it points at moves, which does not care who typed
  the pointer, and its remedy survives a paste, since ``git show <sha>`` says what the paste
  meant while a reflowed command does not.
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

from gitenv import git_env

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

# A terminal paste the author marked with a shell prompt. This is the only UNFENCED paste the
# wrap steps over. A leading indent is not a second signal: every indented line in this repo's own
# history is prose (nested bullet continuations), so exempting an indent would unwrap ordinary
# sentences.
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
    # This runs as a commit-msg hook, where git exports GIT_DIR and it outranks the -C below.
    # `gitenv.py` carries that reason for every gate here that asks git anything; what stays
    # this module's own is the policy below, a git it cannot run leaving the commit unblocked.
    try:
        result = subprocess.run(  # noqa: S603 -- fixed argv, no shell; token is [0-9a-f]+
            ["git", "-C", str(repo), "cat-file", "-e", f"{token}^{{commit}}"],  # noqa: S607 -- git resolves on PATH; a pinned path is not portable
            capture_output=True,
            check=False,
            env=git_env(),
        )
    except OSError:  # git missing: cannot disprove the hash, so do not block the commit
        return False
    return result.returncode == 0


def too_wide(line: str) -> bool:
    """Whether ``line`` is past the wrap **and** could have been wrapped.

    A line whose longest word is itself over the limit (a URL, a path, a long identifier) has
    nowhere to break, so it is exempt: flagging it would demand a rewrite that does not exist.
    Everything else past the limit is prose that wanted a newline. This reads one line alone;
    the exemptions that depend on the line's kind are ``check_widths``'s, since they need the
    walk.
    """
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


class Line(NamedTuple):
    """One message line, paired with whether it is a paste rather than the author's prose."""

    number: int
    text: str
    pasted: bool


def classify_lines(lines: list[str]) -> tuple[list[Line], int | None]:
    """Pair every line with its kind, and report the line an unclosed fence was opened on.

    One walk answers for every rule that turns on a paste, because a fence is state no single
    line carries and two walks would be two chances to disagree about where a block ends.
    Line 1 is the header: it is prose by construction, since a subject cannot be a fence and
    carries its own rules in ``check_header``, so the toggle starts below it. A fence marker
    belongs to the block it delimits rather than to the prose around it, so it counts as a
    paste too, which is what keeps its info string (```bash) out of the prose rules.
    """
    classified: list[Line] = []
    opened_at: int | None = None
    for number, text in enumerate(lines, start=1):
        if number == 1:
            classified.append(Line(number, text, pasted=False))
        elif is_fence(text):
            opened_at = None if opened_at is not None else number
            classified.append(Line(number, text, pasted=True))
        else:
            pasted = opened_at is not None or is_pasted_command(text)
            classified.append(Line(number, text, pasted=pasted))
    return classified, opened_at


def wrap_problems(classified: list[Line], opened_at: int | None) -> list[str]:
    """Return the wrap violations below the header, and an unclosed fence if one is left open.

    A fenced block and a prompted paste say what they say because of where their newlines are,
    so the gate steps over them instead of asking for a reflow that would change their meaning.
    A fence nobody closes is a violation of its own: left unreported, one stray fence would exempt
    every line after it from the wrap.
    """
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


def check_body_lines(lines: list[str], repo: Path) -> list[str]:
    """Return the width, dash, volatile-reference, and dangling-hash violations in a message.

    The dash ban stops at a paste and the other two do not, which is the whole of the kind
    exemption's reach: a dash inside a paste is not punctuation the author chose, while a
    reference inside one goes stale on exactly the same rewrite as a reference outside it.
    """
    classified, opened_at = classify_lines(lines)
    problems: list[str] = wrap_problems(classified, opened_at)
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
