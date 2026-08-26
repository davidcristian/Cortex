"""What the tree really holds, for every roster a document writes down.

The other half of the comparison next door. Each set here is read from the thing itself rather
than from any second list describing it, which is the whole point: a roster is held to the tree,
never to another sentence about the tree.

- **the live seam checks** are the `#[ignore]`d tests in the body's live suite. That suite is the
  one suite no gate runs, so a reader who never opens the file learns what is in it from a
  document, and the document is what decides whether they run it at all.
- **the gate modules** are the files in `scripts/`. The contract for this tree opens by naming
  every one of them and saying what each holds, which is what lets a future agent work here
  without reading the tree, and it is exactly that promise that goes stale the day a module lands.
- **the registry's parts** are the tuples `crosscheck.CONSTANTS` is joined from, named by the
  convention `registry.py` declares: a `<subject>couplings.py` holds a `<SUBJECT>_COUPLINGS`. The
  convention is asserted by the constant suite rather than assumed here, and `couplings.py` itself
  is the vocabulary every part is written in rather than a part, so it is not one of them.

**An empty set is a failure and not an empty pass.** A suite whose ignores were all deleted, a
directory that moved, a glob that stopped matching: each would leave a comparison that reports
success forever, so each leaves by the same door an unreadable file does.
"""

import re
from collections.abc import Iterable
from pathlib import Path

# The body's live suite, and the tree this repo's own gates live in.
LIVE_SEAM = Path("body/crates/rpc/tests/live.rs")
GATES = Path("scripts")

MODULES = "*.py"
PARTS = "*couplings.py"
# The word every part's file name ends with, which is also the whole name of the one
# `*couplings.py` that is not a part: the vocabulary every part is written in.
COUPLINGS = "couplings"
TUPLE = "_COUPLINGS"

# What marks a check ignored, and what names the function under it. The attribute is read from the
# start of a line, indentation aside, so a doc comment quoting one is not mistaken for one and a
# suite that groups its checks in a `mod` block still has them; the name is taken from the first
# function below it, since attributes stack in any order.
IGNORED = re.compile(r"^\s*#\[ignore\b")
FUNCTION = re.compile(r"^\s*(?:pub +)?(?:async +)?fn +([A-Za-z_][A-Za-z0-9_]*)")


class MemberError(Exception):
    """A set some roster describes cannot be read, or came back empty."""


def _floored(found: Iterable[str], what: str) -> frozenset[str]:
    """Return ``found`` as a set, refusing the empty one a comparison could never fail over."""
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
    """Return the name of the first function below line ``number``, or refuse to guess one."""
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


def registry_tuples(root: Path) -> frozenset[str]:
    """Every tuple the constant registry is joined from, named by the convention it declares."""
    parts = [Path(name).stem for name in _filenames(root, PARTS) if Path(name).stem != COUPLINGS]
    return _floored(
        (part.removesuffix(COUPLINGS).upper() + TUPLE for part in parts),
        f"the registry parts in {GATES}",
    )
