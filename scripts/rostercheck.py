"""Repo gate: fail when a document's roster stops naming the set it describes."""

import argparse
import sys
from pathlib import Path
from typing import NamedTuple

import rosternames
from rostermembers import MemberError
from rosternames import PassageError
from rosters import ROSTERS, Roster

# A gate over no roster at all would report success forever, which is the one thing every scan
# here refuses. The per-roster floors are `rostermembers.py`'s.
MIN_ROSTERS = 1


class RosterCheckError(Exception):
    """A document or a set a roster describes could not be read, so nothing can be compared."""


class Fault(NamedTuple):
    """One roster that does not name the set it describes, and what is wrong with it."""

    document: str
    label: str
    detail: str


class Scan(NamedTuple):
    """One comparison: what it was over, then what it could not account for."""

    rosters: int
    documents: int
    members: int
    faults: list[Fault]


def _read(root: Path, document: Path) -> str:
    """Read one document a roster is written on, naming it when it is absent or is not text."""
    try:
        return (root / document).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as err:
        msg = f"cannot read {document.as_posix()}: {err}"
        raise RosterCheckError(msg) from err


def _fault(roster: Roster, detail: str) -> Fault:
    """One fault against ``roster``, carrying the reason its two sides have to agree."""
    return Fault(
        document=roster.document.as_posix(), label=roster.label, detail=f"{detail}; {roster.why}"
    )


def check_one(root: Path, roster: Roster) -> tuple[frozenset[str], list[Fault]]:
    """Compare one roster with the set it describes; return that set and every fault."""
    text = _read(root, roster.document)
    try:
        members = roster.members(root)
        aside = frozenset[str]() if roster.refers_to is None else roster.refers_to(root)
    except MemberError as err:
        raise RosterCheckError(str(err)) from err
    try:
        written = rosternames.names(
            rosternames.passage(text, roster.opens, roster.closes), roster.written
        )
    except PassageError as err:
        return members, [_fault(roster, str(err))]
    named = frozenset(written)
    faults = [
        _fault(roster, f"{name} is {roster.subject} and the roster does not name it")
        for name in sorted(members - named)
    ]
    faults.extend(
        _fault(roster, f"the roster names {name}, which is not {roster.subject}")
        for name in sorted(named - members - aside)
    )
    return members, faults


def check(root: Path, rosters: tuple[Roster, ...] | None = None) -> Scan:
    """Compare every registered roster with the set it describes, in registry order."""
    registry = ROSTERS if rosters is None else rosters
    if len(registry) < MIN_ROSTERS:
        msg = "no roster is registered, and a scan over nothing cannot fail"
        raise RosterCheckError(msg)
    faults: list[Fault] = []
    counted = 0
    for roster in registry:
        members, found = check_one(root, roster)
        counted += len(members)
        faults.extend(found)
    return Scan(
        rosters=len(registry),
        documents=len({roster.document for roster in registry}),
        members=counted,
        faults=faults,
    )


def main(argv: list[str] | None = None) -> int:
    """Run the gate; print any faults and return the process exit code."""
    parser = argparse.ArgumentParser(
        description="Fail when a document's roster stops naming the set it describes.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(),
        help="repo root holding the documents and the trees they describe (default: .)",
    )
    args = parser.parse_args(argv)
    given: Path = args.root
    if not given.is_dir():
        print(f"rostercheck: root {given} is not a directory", file=sys.stderr)
        return 2
    try:
        scanned = check(given)
    except RosterCheckError as err:
        print(f"rostercheck: {err}", file=sys.stderr)
        return 2
    for fault in scanned.faults:
        print(f"{fault.document}: {fault.label}: {fault.detail}")
    if scanned.faults:
        print(
            f"\nrostercheck: {len(scanned.faults)} roster problem(s). A roster names the set it "
            "describes and says whatever it likes about each member, so add the sentence the new "
            "member deserves, or strike the one whose member is gone.",
            file=sys.stderr,
        )
        return 1
    print(
        f"rostercheck OK: {scanned.rosters} roster(s) in {scanned.documents} document(s) under "
        f"{given} name exactly the {scanned.members} member(s) they describe"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover -- CLI entry point; main() is unit-tested
    sys.exit(main())
