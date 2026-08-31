"""What the tree really holds, for every roster a document writes down.

Each set here is read from the thing itself rather than from a second list describing it, so a
roster is held to the tree and never to another sentence about the tree.

- **the live seam checks** are the `#[ignore]`d tests in the body's live suite. No gate runs that
  suite, so a reader who never opens the file learns what is in it from a document.
- **the gate modules** are the files in `scripts/`. The contract for this tree names every one of
  them and says what each holds, and the repo map in AGENTS.md names the same set a second time in
  a fenced block of plain text, so both answers come from one reading of the directory.
- **the modules with a CLI** and **the ones without** are that same directory split by what decides
  which half of the contract's sentence a module belongs in: a module has a command line exactly
  when it carries an `if __name__ == "__main__":` guard at the top level.
- **the cross-tree scans** are the one set here that is not a directory listing. What makes a module
  one is that the single gate runs it before the trees and CI's `cross-tree` job runs it too, which
  `scanrecipes.py` reads out of the two files that run them.
- **the registry's parts** are the tuples `crosscheck.CONSTANTS` is joined from, named by the
  convention `registry.py` declares: a `<subject>couplings.py` holds a `<SUBJECT>_COUPLINGS`. The
  constant suite asserts that convention rather than this module assuming it, and `couplings.py` is
  the vocabulary every part is written in rather than a part, so it is not one of them.

An empty set raises. A suite whose ignores were all deleted, a directory that moved, or a glob that
stopped matching would otherwise leave a comparison that reports success forever.
"""

import re
from collections.abc import Iterable
from pathlib import Path

import scanrecipes
from scanrecipes import ScanReadError

# The body's live suite, and the tree this repo's own gates live in.
LIVE_SEAM = Path("body/crates/rpc/tests/live.rs")
GATES = Path("scripts")

MODULES = "*.py"
PARTS = "*couplings.py"
# The word every part's file name ends with, which is also the whole name of the one
# `*couplings.py` that is not a part: the vocabulary every part is written in.
COUPLINGS = "couplings"
TUPLE = "_COUPLINGS"

# What marks a check ignored, and what names the function under it. The attribute is matched from
# the start of a line, indentation aside, so a doc comment quoting one does not match and a suite
# that groups its checks in a `mod` block still has them; the name is taken from the first function
# below it, since attributes stack in any order.
IGNORED = re.compile(r"^\s*#\[ignore\b")
FUNCTION = re.compile(r"^\s*(?:pub +)?(?:async +)?fn +([A-Za-z_][A-Za-z0-9_]*)")

# What gives a module here a command line of its own. It is read at column zero, since a guard is
# a top-level statement and the same text inside a docstring or a nested function is neither one.
MAIN_GUARD = re.compile(r"^if __name__ == \"__main__\":", re.MULTILINE)


class MemberError(Exception):
    """A set some roster describes cannot be read, or came back empty."""


def _floored(found: Iterable[str], what: str) -> frozenset[str]:
    """Return ``found`` as a set, raising on the empty one, which no comparison could fail over."""
    members = frozenset(found)
    if not members:
        msg = f"{what} came back empty, and a comparison over nothing cannot fail"
        raise MemberError(msg)
    return members


def _read(root: Path, name: Path) -> str:
    """Read one file a roster is about, naming it when it is absent or is not text."""
    try:
        return (root / name).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as err:
        msg = f"cannot read {name.as_posix()}: {err}"
        raise MemberError(msg) from err


def _filenames(root: Path, pattern: str) -> list[str]:
    """Return the file names under `scripts/` matching ``pattern``, in a fixed order."""
    tree = root / GATES
    if not tree.is_dir():
        msg = f"{GATES.as_posix()} is not a directory, so there is nothing to read"
        raise MemberError(msg)
    return sorted(path.name for path in tree.glob(pattern))


def ignored_tests(text: str) -> list[str]:
    """Return the name of every `#[ignore]`d function in one Rust suite, in file order."""
    lines = text.splitlines()
    return [
        _named_after(lines, number)
        for number, line in enumerate(lines)
        if IGNORED.match(line) is not None
    ]


def _named_after(lines: list[str], number: int) -> str:
    """Return the name of the first function below line ``number``, raising when there is none."""
    for line in lines[number + 1 :]:
        found = FUNCTION.match(line)
        if found is not None:
            return found.group(1)
    msg = (
        f"the ignore on line {number + 1} sits above no function, so nothing names the check "
        f"it ignores"
    )
    raise MemberError(msg)


def live_seam_checks(root: Path) -> frozenset[str]:
    """Every `#[ignore]`d test in the body's live seam suite."""
    return _floored(ignored_tests(_read(root, LIVE_SEAM)), f"the ignored tests in {LIVE_SEAM}")


def gate_modules(root: Path) -> frozenset[str]:
    """Every module in `scripts/`, the tree its own module contract is a contract for."""
    return _floored(_filenames(root, MODULES), f"the modules in {GATES}")


def _with_a_cli(root: Path, *, wanted: bool) -> list[str]:
    """The modules in `scripts/` that do, or do not, carry a top-level main guard."""
    return [
        name
        for name in _filenames(root, MODULES)
        if (MAIN_GUARD.search(_read(root, GATES / name)) is not None) == wanted
    ]


def cli_gate_modules(root: Path) -> frozenset[str]:
    """Every module in `scripts/` with a command line of its own."""
    return _floored(_with_a_cli(root, wanted=True), f"the CLIs in {GATES}")


def library_gate_modules(root: Path) -> frozenset[str]:
    """Every module in `scripts/` that another module reads rather than a shell runs."""
    return _floored(_with_a_cli(root, wanted=False), f"the modules in {GATES} with no CLI")


def cross_tree_scans(root: Path) -> frozenset[str]:
    """Every module the single gate and CI both run as a cross-tree scan."""
    try:
        found = scanrecipes.scan_modules(root)
    except ScanReadError as err:
        raise MemberError(str(err)) from err
    return _floored(found, "the cross-tree scans the gate runs")


def registry_tuples(root: Path) -> frozenset[str]:
    """Every tuple the constant registry is joined from, named by the convention it declares."""
    parts = [Path(name).stem for name in _filenames(root, PARTS) if Path(name).stem != COUPLINGS]
    return _floored(
        (part.removesuffix(COUPLINGS).upper() + TUPLE for part in parts),
        f"the registry parts in {GATES}",
    )
