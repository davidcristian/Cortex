"""Every roster this repo has written down, as one tuple.

A **roster** is a list of names a document keeps for a set that really exists in the tree. It is
prose with a purpose: each entry says what its member proves or is for, and that sentence is the
reason the list is written by hand and must go on being written by hand. What is held here is the
narrower claim underneath the prose, that the names are the set: every member named, and every
name a member. The sentences are free.

`rostercheck.py` is all of the logic and this is all of the data, the split `crosscheck.py` and
its registry already use. A roster arrives as one entry below plus, when its set is a new kind, a
reader in `rostermembers.py`; the scan never learns which document or which shape it is reading.

What an entry declares:

- **label**, what the roster is, printed with any fault so a reader knows which list moved;
- **document**, the page it is written on;
- **opens** and **closes**, the two phrases bounding the passage it occupies. Neither may be a
  member's name, or the roster would be its own far side;
- **written**, how a name is spelled in that passage, bulleted, in a code span matching a pattern,
  or bare;
- **subject**, what a member IS, as a fault should name it;
- **why**, the reason the two sides must agree, printed with any fault, exactly as a registered
  constant prints why its places must;
- **members**, the reader answering for the real set;
- **refers_to**, optional, a set whose names this passage may carry without them being its
  members. One paragraph holding two rosters names the members of each, and it also refers to the
  siblings: the sentence about the modules with no CLI says whose reader each one is, and the name
  it says it with belongs to the other half. A name claimed by the sibling is a reference here
  rather than an entry, and every other name is still held both ways, so a module that gains a
  command line and stays in the second sentence is a red in the first for being a member nobody
  named.

Every roster here was written by hand and held by nothing, and the first of them was found
describing a suite that had moved on twice: it opened by saying two checks and then described
four, while the file carried seven, through several passes that each added a check and left the
sentence alone. The other two were current on the day this landed and had been kept that way by
hand, and they were already in different orders, which is harmless in itself and is also the
evidence that nobody was comparing them to anything.
"""

import re
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

import rostermembers
from rosternames import Bare, Bulleted, Spelled, Written

# How a member is spelled where a roster runs as a sentence rather than as a list. A module is a
# bare file name, so a code span carrying a path or a flag beside one is not a member; a part is
# the tuple name the registry joins, which no other code span in that passage is shaped like.
MODULE = re.compile(r"[a-z_]+\.py")
PART = re.compile(r"[A-Z][A-Z_]*_COUPLINGS")

# The sentence dividing the gate tree's contract in two. It is one phrase and it bounds two
# rosters, closing the one over the modules a shell can run and opening the one over the rest.
NO_CLI = "**The rest have no CLI of their own**"

# Why the same three sentences are written down three times below. The list of cross-tree scans is
# spelled in more places than any other set here, and the copies are not one kind of thing: four of
# them carry a tally or a run of descriptions and are left alone, since a document's numbers are its
# own business and a roster written in descriptions has no names to hold. These three spell the
# names, and one of them was found short two scans while this was being registered.
SCANS = (
    "a reader learns from this list which gates run on every change, and a scan missing from it "
    "is a gate they do not know exists"
)


class Roster(NamedTuple):
    """One list of names a document keeps for a set the tree really holds."""

    label: str
    document: Path
    opens: str
    closes: str
    written: Written
    subject: str
    why: str
    members: Callable[[Path], frozenset[str]]
    refers_to: Callable[[Path], frozenset[str]] | None = None


ROSTERS: tuple[Roster, ...] = (
    Roster(
        label="the live seam checks",
        document=Path("docs/modules/body-rpc.md"),
        opens="**Live checks**",
        closes="Being ignored, they never run in CI",
        written=Bulleted(),
        subject="an ignored test in body/crates/rpc/tests/live.rs",
        why=(
            "the live suite is the one suite no gate runs, so this roster is the whole "
            "description of it a reader gets without opening the file, and it is what decides "
            "whether they run it at all"
        ),
        members=rostermembers.live_seam_checks,
    ),
    Roster(
        label="the modules this tree runs from a shell",
        document=Path("docs/modules/repo-gates.md"),
        opens="**Public contract**",
        closes=NO_CLI,
        written=Spelled(pattern=MODULE),
        subject="a module in scripts/ with a command line of its own",
        why=(
            "this sentence is where a reader learns which modules can be run and which are read "
            "by another, so a module in the wrong half of it is described as something it is not"
        ),
        members=rostermembers.cli_gate_modules,
    ),
    Roster(
        label="the modules this tree only reads",
        document=Path("docs/modules/repo-gates.md"),
        opens=NO_CLI,
        closes="implements AGENTS.md gate 1",
        written=Spelled(pattern=MODULE),
        subject="a module in scripts/ with no command line",
        why=(
            "this contract promises a future agent can work on the tree without reading it, "
            "which it can only keep while every module in the tree is named on the page and "
            "named in the half of the sentence that is true of it"
        ),
        members=rostermembers.library_gate_modules,
        refers_to=rostermembers.cli_gate_modules,
    ),
    Roster(
        label="the cross-tree scans in the engineering contract",
        document=Path("AGENTS.md"),
        opens="**the cross-tree scans**",
        closes="runs unconditionally, in CI too",
        written=Spelled(pattern=MODULE),
        subject="a cross-tree scan the gate and CI both run",
        why=SCANS,
        members=rostermembers.cross_tree_scans,
    ),
    Roster(
        label="the cross-tree scans in the workflow's own comment",
        document=Path(".github/workflows/ci.yml"),
        opens="# The cross-tree scans are repo-wide and exempt from the path filter",
        closes="  cross-tree:",
        written=Bare(pattern=MODULE),
        subject="a cross-tree scan the gate and CI both run",
        why=(
            "this comment says why each scan is exempt from the path filter, which is the "
            "argument for the job below it, and it is read beside the steps it explains"
        ),
        members=rostermembers.cross_tree_scans,
    ),
    Roster(
        label="the cross-tree scans in the documentation index",
        document=Path("docs/index.md"),
        opens="whose **cross-tree scans** are",
        closes="**Beside them**",
        written=Spelled(pattern=MODULE),
        subject="a cross-tree scan the gate and CI both run",
        why=SCANS,
        members=rostermembers.cross_tree_scans,
    ),
    Roster(
        label="the gate tree in the repo map",
        document=Path("AGENTS.md"),
        opens="scripts/          repo gates",
        closes=".github/          GPU-less CI running",
        written=Bare(pattern=MODULE),
        subject="a module in scripts/",
        why=(
            "this map is what the contract every agent here reads says the tree contains, and a "
            "module missing from it is a module the next agent works around rather than with"
        ),
        members=rostermembers.gate_modules,
    ),
    Roster(
        label="the registry's parts",
        document=Path("docs/modules/repo-gates.md"),
        opens="`crosscheck.CONSTANTS` is",
        closes="Each part is named for its subject",
        written=Spelled(pattern=PART),
        subject="a tuple crosscheck.CONSTANTS is joined from",
        why=(
            "this is the second copy of a list registry.py's own docstring already carries, and "
            "a part that lands unnamed here leaves the document describing the registry that "
            "existed before it"
        ),
        members=rostermembers.registry_tuples,
    ),
)
