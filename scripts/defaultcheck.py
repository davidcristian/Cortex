"""Fail when one compose variable has two different defaults."""

import argparse
import sys
from collections import defaultdict
from pathlib import Path
from typing import NamedTuple

from composedefaults import Substitution, SubstitutionReadError, read_substitutions
from composefiles import ComposeSearchError, compose_files, refused_summary
from values import CrossCheckError, parse_value, whole_form

MIN_SPENDS = 2


class Spend(NamedTuple):
    """One place a compose file writes one variable: the file, and the substitution as read."""

    path: str
    substitution: Substitution

    def __str__(self) -> str:
        """`path:line ${NAME:-value}`, the form a fault prints for each place that disagrees."""
        return f"{self.path}:{self.substitution.line} {self.substitution.written}"


class Fault(NamedTuple):
    """One variable whose defaults disagree, or one compose file the scan could not read."""

    subject: str
    detail: str


class Walk(NamedTuple):
    """Every variable the compose files under a root write, and the files that would not read."""

    files: int
    groups: dict[str, list[Spend]]
    faults: list[Fault]


class Scan(NamedTuple):
    """What one walk read, and the two kinds of fault it found."""

    files: int
    variables: int
    compared: int
    refused: list[Fault]
    disagreements: list[Fault]

    @property
    def faults(self) -> list[Fault]:
        """Every fault, unreadable files first, in the order `main` prints them."""
        return self.refused + self.disagreements


def same_value(arguments: list[str]) -> bool:
    """Whether several default texts are the same value when `8.0` and `8` count as one."""
    if len(set(arguments)) == 1:
        return True
    forms: set[str] = set()
    for text in arguments:
        try:
            forms.add(whole_form(parse_value(text)))
        except CrossCheckError:
            return False
    return len(forms) == 1


def one_line_hint(spends: list[Spend]) -> str:
    """The suggested fix when a group names one `path:line` twice, or nothing to add."""
    places = [(spend.path, spend.substitution.line) for spend in spends]
    repeated = sorted({place for place in places if places.count(place) > 1})
    if not repeated:
        return ""
    shared = ", ".join(f"{path}:{line}" for path, line in repeated)
    return (
        f"; more than one of those spends is on {shared}, which is what a note written after a "
        "value looks like to this reader, so if one of them is a comment, move it above the line "
        "it annotates"
    )


def disagreement(name: str, spends: list[Spend]) -> Fault | None:
    """What is wrong with one variable's several defaults, or None when they agree."""
    shown = ", ".join(str(spend) for spend in spends)
    operators = {spend.substitution.operator for spend in spends}
    if len(operators) > 1:
        return Fault(
            subject=name,
            detail=(
                f"is written {len(spends)} times with {len(operators)} different fallback "
                f"operators, so one spend falls back where another does not ({shown})"
            ),
        )
    if not spends[0].substitution.has_value:
        return None
    if same_value([spend.substitution.argument for spend in spends]):
        return None
    return Fault(
        subject=name,
        detail=(
            f"is written {len(spends)} times and does not have one default, so the stack takes "
            f"whichever spend it happens to read ({shown}){one_line_hint(spends)}"
        ),
    )


def _read(root: Path, compose: Path, groups: dict[str, list[Spend]]) -> Fault | None:
    """Group one compose file's substitutions by variable name, or say why it would not read."""
    name = compose.relative_to(root).as_posix()
    try:
        found = read_substitutions(compose.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, SubstitutionReadError) as err:
        return Fault(subject=name, detail=str(err))
    for substitution in found:
        groups[substitution.name].append(Spend(path=name, substitution=substitution))
    return None


def group(root: Path) -> Walk:
    """Every variable the compose files under ``root`` write, and the files that would not read."""
    groups: dict[str, list[Spend]] = defaultdict(list)
    faults: list[Fault] = []
    files = 0
    for compose in compose_files(root):
        files += 1
        fault = _read(root, compose, groups)
        if fault is not None:
            faults.append(fault)
    return Walk(files=files, groups=dict(groups), faults=faults)


def check(root: Path) -> Scan:
    """Return what the walk read under ``root``, and every variable whose defaults disagree."""
    walk = group(root)
    disagreements: list[Fault] = []
    compared = 0
    for name, spends in sorted(walk.groups.items()):
        if len(spends) < MIN_SPENDS:
            continue
        compared += 1
        fault = disagreement(name, spends)
        if fault is not None:
            disagreements.append(fault)
    return Scan(
        files=walk.files,
        variables=len(walk.groups),
        compared=compared,
        refused=walk.faults,
        disagreements=disagreements,
    )


def main(argv: list[str] | None = None) -> int:
    """Run the check; print any faults and return the process exit code."""
    parser = argparse.ArgumentParser(
        description="Fail when one compose variable has two different defaults.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(),
        help="repo root holding the compose files (default: current directory)",
    )
    args = parser.parse_args(argv)
    given: Path = args.root
    if not given.is_dir():
        print(f"defaultcheck: root {given} is not a directory", file=sys.stderr)
        return 2
    try:
        scanned = check(given.resolve())
    except ComposeSearchError as err:
        print(f"defaultcheck: {err}", file=sys.stderr)
        return 2
    for fault in scanned.faults:
        print(f"{fault.subject}: {fault.detail}")
    if scanned.refused:
        unread = "no spend in them was compared"
        print(refused_summary("defaultcheck", len(scanned.refused), unread), file=sys.stderr)
    if scanned.disagreements:
        print(
            f"\ndefaultcheck: {len(scanned.disagreements)} compose variable(s) do not have one "
            "default. Give every spend of one variable the same default, rewritten only where "
            "the far side's own syntax cannot take it as written.",
            file=sys.stderr,
        )
    if scanned.faults:
        return 1
    print(
        f"defaultcheck OK: {scanned.compared} variable(s) written twice or more under {given} "
        f"have one value, over {scanned.files} compose file(s) and {scanned.variables} "
        f"variable(s) read"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover -- CLI entry point; main() is unit-tested
    sys.exit(main())
