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
- **written**, how a name is spelled in that passage, bulleted or matching a pattern;
- **subject**, what a member IS, as a fault should name it;
- **why**, the reason the two sides must agree, printed with any fault, exactly as a registered
  constant prints why its places must;
- **members**, the reader answering for the real set.

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
from rosternames import Bulleted, Spelled, Written

# How a member is spelled where a roster runs as a sentence rather than as a list. A module is a
# bare file name, so a code span carrying a path or a flag beside one is not a member; a part is
# the tuple name the registry joins, which no other code span in that passage is shaped like.
MODULE = re.compile(r"[a-z_]+\.py")
PART = re.compile(r"[A-Z][A-Z_]*_COUPLINGS")


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
        label="the modules this tree is a contract for",
        document=Path("docs/modules/repo-gates.md"),
        opens="**Public contract**",
        closes="implements AGENTS.md gate 1",
        written=Spelled(pattern=MODULE),
        subject="a module in scripts/",
        why=(
            "this contract promises a future agent can work on the tree without reading it, "
            "which it can only keep while every module in the tree is named on the page"
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
