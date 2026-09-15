"""Every roster this repo has written down, as one tuple."""

import re
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

import rostermembers
from rosternames import Bare, Bulleted, Spelled, Written

# How a member is written where a roster runs as a sentence rather than as a list. A module is a
# bare file name, so a code span carrying a path or a flag beside one is not a member; a part is
# the tuple name the registry joins, which no other code span in that passage is shaped like.
MODULE = re.compile(r"[a-z_]+\.py")
PART = re.compile(r"[A-Z][A-Z_]*_COUPLINGS")

DIRECTORY = re.compile(r"[a-z][a-z_]*(?=[ \n]+\()")

# The sentence dividing the gate tree's contract in two. It is one phrase and it bounds two
# rosters, closing the one over the modules a shell can run and opening the one over the rest.
NO_CLI = "**The rest have no CLI of their own**"

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
        label="the brain's packages in the repo map",
        document=Path("AGENTS.md"),
        opens="  packages/",
        closes="body/             Rust/Tauri workspace",
        written=Bare(pattern=DIRECTORY),
        subject="a package under brain/packages/",
        why=(
            "this row is where a reader learns what the brain is made of before opening it, and "
            "a package missing from it is one the next agent writes around rather than into"
        ),
        members=rostermembers.brain_packages,
    ),
    Roster(
        label="the body's crates in the repo map",
        document=Path("AGENTS.md"),
        opens="  crates/",
        closes="  app/            React",
        written=Bare(pattern=DIRECTORY),
        subject="a crate under body/crates/",
        why=(
            "this row is where a reader learns what the body is made of before opening it, and "
            "a crate missing from it is one the next agent writes around rather than into"
        ),
        members=rostermembers.body_crates,
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
