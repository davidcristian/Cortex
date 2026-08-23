"""Repo gate: fail when one compose variable carries two different defaults.

A compose default that no tree declares is not a coupling and `crosscheck.py` deliberately does
not read one: that scan compares a declaration against the places restating it, and here there is
no declaration to read. What the same survey found is a defect of a different shape, and it is
this one. `${CORTEX_PG_PASSWORD:-cortex}` is written three times in one override, once as the
server's own password and twice as a client's; `${CORTEX_MODELS_DIR:-./models}` is written in four
files that mount one host directory read-only. Nothing holds those spends to each other. One of
them drifting is a stack that fails at run time in a way no static check reports: Postgres
refusing its own clients, or one service reading models out of a directory the others do not.

**The rule is not that all spellings are identical**, and the counterexample was already in the
tree before this gate was: `${CORTEX_SUBAGENTS_MEM_BUDGET_GB:-8.0}` sits in an environment block
while `${CORTEX_SUBAGENTS_MEM_BUDGET_GB:-8}g` sits in two container limits, deliberately, because
docker reads `8.0g` as a size and refuses it. So the rule is that one variable's several defaults
must be the same **value**, compared through the whole-number spelling `values.py` already
derives for that same pair. A textual comparison would call the tree's one deliberate re-spelling
a fault on the day it landed.

**The operator is part of the answer.** Two spends must fall back the same way as well as to the
same value: `${V:-x}` and `${V-x}` disagree about a variable set to the empty string, and
`${V:?}` beside `${V:-x}` is one file demanding what another quietly supplies. So a group's
operators must match, and only then are the values compared, and only for the operators whose
argument is a value at all (`composedefaults.VALUE_OPERATORS`); two `:?` spends wording their
message differently have not drifted.

**Why here and not in `crosscheck.py`.** That scan is registry-driven: every question it asks
starts from a hand-written entry naming a declaring site, and its documented subject is a value
some tree declares against the places restating it. This question has no registry and no
declaration. It is discovered by walking the compose files, and its far sides are each other.
Folding it in would give one scan two entry points and make its stated subject false, which the
repo's own description of its gates would then have to stop saying. It sits beside `bindcheck.py`
instead, the other gate that walks every compose file and fails closed on finding none; the walk
itself is `composefiles.py`, shared so the two gates cannot drift apart about which files exist.

**Fail closed**, the same way both siblings do. No compose file at all, a file that cannot be
read or decoded, and a `$` form the reader was not taught are each a failure rather than a quiet
pass. A default this gate cannot reduce is only a failure when its group already disagrees
textually, since a value nobody re-spells needs no reduction to be compared.

**The success line states what the walk read**: compose files, the variables they spend, and how
many of those were compared at all, that last being the collection the verdict is really over,
since a variable spelled once is never compared. It is a reading and nothing asserts it. The
floor is `composefiles.py`'s and already here; the deeper counts get none, a tree whose variables
are each spelled once being a legitimate one to find nothing wrong with.
"""

import argparse
import sys
from collections import defaultdict
from pathlib import Path
from typing import NamedTuple

from composedefaults import Substitution, SubstitutionReadError, read_substitutions
from composefiles import ComposeSearchError, compose_files
from values import CrossCheckError, parse_value, whole_spelling

# How many times a variable has to be written before there is anything to compare. A lone
# spend has no sibling to disagree with, whatever its default reduces to or refuses to.
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
    """One walk: the collection the verdict is over, then the verdict.

    ``compared`` is the number of variables with a sibling to disagree with, and it is the one
    the success line leads on: the other two say how far the walk reached, this one says how much
    of what it reached the rule had anything to say about.
    """

    files: int
    variables: int
    compared: int
    faults: list[Fault]


def same_value(arguments: list[str]) -> bool:
    """Whether several default texts are one value once a whole-number spelling is allowed.

    Identical text is one value with nothing to reduce, which is every group in the tree but the
    subagent memory budget. Anything else is reduced and re-spelled whole, so `8.0` and `8` agree
    and `8.5` beside `8` does not, the fraction being lost rather than zero. A text the reducer
    refuses (a path, a hostname, an empty default beside a filled one) cannot be shown equal to a
    text it does not match, so it disagrees.
    """
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
    """The remedy for a group naming one `path:line` twice, or nothing to add.

    Naming the same place twice is everything a reader is given about the commonest way to get
    here: `composedefaults.py` reads a note written after a value as a second spend of the variable
    it names, deliberately, so a stale note beside a live default is two spends that disagree. The
    condition is a REPEATED place and not one shared by the whole group, which is the correction
    measured on the tree: planting a note beside the model directory reddens a group of five spends
    across four files, only two of which are that line. The hint has to be true of what was read
    rather than of what is guessed, and no `#` was looked for: one variable really can be spelled
    twice on one line with no comment in sight, `"${V:-a}/in:${V:-b}"` being one value spending one
    variable twice. So the sentence names the line the two share and offers the note as the likely
    reading rather than as a finding.
    """
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
