"""Repo gate: fail when one compose variable carries two different defaults."""

import argparse
import sys
from collections import defaultdict
from pathlib import Path
from typing import NamedTuple

from composedefaults import Substitution, SubstitutionReadError, read_substitutions
from composefiles import ComposeSearchError, compose_files
from values import CrossCheckError, parse_value, whole_spelling

# How many times a variable has to be written before there is anything to compare. A lone spend
# has no sibling to disagree with, whatever its default reduces to.
MIN_SPENDS = 2


class Spend(NamedTuple):
    """One place one variable is written: the compose file, and the substitution as read."""

    path: str
    substitution: Substitution

    def __str__(self) -> str:
        """`path:line ${NAME:-value}`, which is how a fault names the places that disagree."""
        return f"{self.path}:{self.substitution.line} {self.substitution.written}"


class Fault(NamedTuple):
    """One variable whose spends disagree, or one compose file the scan could not read."""

    subject: str
    detail: str


class Walk(NamedTuple):
    """What the compose files under a root spend, and which of those files would not read."""

    files: int
    groups: dict[str, list[Spend]]
    faults: list[Fault]


class Scan(NamedTuple):
    """One walk: the collection the verdict is over, then the verdict."""

    files: int
    variables: int
    compared: int
    faults: list[Fault]


def same_value(arguments: list[str]) -> bool:
    """Whether several default texts are one value once a whole-number spelling is allowed."""
    if len(set(arguments)) == 1:
        return True
    spellings: set[str] = set()
    for text in arguments:
        try:
            spellings.add(whole_spelling(parse_value(text)))
        except CrossCheckError:
            return False
    return len(spellings) == 1


def one_line_hint(spends: list[Spend]) -> str:
    """The remedy for a group naming one `path:line` twice, or nothing to add."""
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
    """The complaint about one variable's several spends, or None when they hold together."""
    shown = ", ".join(str(spend) for spend in spends)
    operators = {spend.substitution.operator for spend in spends}
    if len(operators) > 1:
        return Fault(
            subject=name,
            detail=(
                f"is spelled {len(spends)} times with {len(operators)} different fallback "
                f"operators, so one spend falls back where another does not ({shown})"
            ),
        )
    if not spends[0].substitution.carries_value:
        return None
    if same_value([spend.substitution.argument for spend in spends]):
        return None
    return Fault(
        subject=name,
        detail=(
            f"is spelled {len(spends)} times and does not carry one default, so the stack takes "
            f"whichever spend it happens to read ({shown}){one_line_hint(spends)}"
        ),
    )


def _read(root: Path, compose: Path, groups: dict[str, list[Spend]]) -> Fault | None:
    """File one compose file's substitutions under their names, or say why it could not be read."""
    name = compose.relative_to(root).as_posix()
    try:
        found = read_substitutions(compose.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, SubstitutionReadError) as err:
        return Fault(subject=name, detail=str(err))
    for substitution in found:
        groups[substitution.name].append(Spend(path=name, substitution=substitution))
    return None


def group(root: Path) -> Walk:
    """Every variable the compose files under ``root`` spend, and the files that would not read."""
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
    """Return what the walk read under ``root``, and every variable whose spends do not agree."""
    walk = group(root)
    faults = list(walk.faults)
    compared = 0
    for name, spends in sorted(walk.groups.items()):
        if len(spends) < MIN_SPENDS:
            continue
        compared += 1
        fault = disagreement(name, spends)
        if fault is not None:
            faults.append(fault)
    return Scan(files=walk.files, variables=len(walk.groups), compared=compared, faults=faults)


def main(argv: list[str] | None = None) -> int:
    """Run the gate; print any faults and return the process exit code."""
    parser = argparse.ArgumentParser(
        description="Fail when one compose variable carries two different defaults.",
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
    faults = scanned.faults
    for fault in faults:
        print(f"{fault.subject}: {fault.detail}")
    if faults:
        print(
            f"\ndefaultcheck: {len(faults)} compose variable(s) do not carry one default. "
            "Give every spend of one variable the same default, re-spelled only where the far "
            "side's own syntax cannot take it as written.",
            file=sys.stderr,
        )
        return 1
    print(
        f"defaultcheck OK: {scanned.compared} variable(s) spelled twice or more under {given} "
        f"carry one value, over {scanned.files} compose file(s) and {scanned.variables} "
        f"variable(s) read"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover -- CLI entry point; main() is unit-tested
    sys.exit(main())
