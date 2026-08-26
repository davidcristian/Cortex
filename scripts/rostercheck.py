"""Repo gate: fail when a document's roster stops naming the set it describes.

A module contract that lists the checks in a suite, or the modules in a directory, is describing
something the tree really holds, and nothing held the description to it. The failure is quiet in
both directions: a member added and the roster left alone, so a reader is told a smaller set
exists than does, which is the direction observed here twice before this was written; and a name
kept after the thing it named was renamed, so a reader is sent looking for something that is gone.
Every other gate stays green through both, because a document is text and the set it describes is
a directory listing or a run of attributes in another tree.

**What it holds is membership and naming, and nothing else.** Every member of the real set is
named in the roster, and every name in the roster is a member. The sentence beside each name is
free to say whatever it likes, at whatever length, in whatever order, because that sentence is
what a roster is FOR: a generated list would say what the names are and could never say what any
of them proves. A gate that forced this prose into a table would destroy the thing it protects.

**Counts are deliberately not held**, and a roster that carried one lost it instead. A tally
restated by hand beside a list is the half that drifts first, and it is the half a reader can
recount in a second from the list itself. This continues the standing decision that a document
describing a registry is not a far side of its numbers, and it draws the line the other way for
names: a name list goes stale exactly when a member is added, which is when it should redden.

**Where a roster begins and ends is data**, two phrases the document already carries, because
holding one section of a document is not the same question as holding the document. Several
rosters here share one page, one sentence closes one of them and opens the next, and a rule that
read whole pages would let a name missing from one list pass on the strength of the other.

**A name a sibling roster owns is a reference rather than an entry.** A paragraph split into two
rosters says whose reader each module is, and it says it with the other half's names, so requiring
every name to be a member would make ordinary prose a fault. A roster may declare the set whose
names it is allowed to carry that way, and nothing else is let through: a module that gains a
command line and stays in the wrong half is still a member the other half does not name.

**Both empty sides are a failure rather than a pass.** A suite whose ignores are all gone, a
directory that moved, a phrase that stopped appearing: each is either an input failure or a
reported fault, never a quiet agreement between two nothings.

**The success line states the collection the verdict is over**, rosters, documents and members
after every exclusion, because a verdict that would be equally true of a page this scan never read
has to say which pages it read. It is a reading and nothing asserts it; the floors are the
assertion.
"""

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
    """Compare one roster with the set it describes; return that set and every fault.

    A passage that cannot be found is reported here rather than thrown, so one run names every
    roster that moved instead of the first. A document or a set that cannot be READ is not: that
    is an input failure and it leaves by its own door.
    """
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
