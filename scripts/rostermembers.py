"""What the tree really holds, for every roster a document writes down."""

import re
from collections.abc import Iterable
from fnmatch import fnmatchcase
from pathlib import Path

import scanrecipes
from scanrecipes import ScanReadError

LIVE_SEAM = Path("body/crates/rpc/tests/live.rs")
GATES = Path("scripts")
PACKAGES = Path("brain/packages")
CRATES = Path("body/crates")

MODULES = "*.py"
PARTS = "*couplings.py"
COUPLINGS = "couplings"
TUPLE = "_COUPLINGS"

IGNORED = re.compile(r"^\s*#\[ignore\b")
FUNCTION = re.compile(r"^\s*(?:pub +)?(?:async +)?fn +([A-Za-z_][A-Za-z0-9_]*)")

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


def _listed(root: Path, tree: Path) -> list[Path]:
    """Return what one directory a roster is written about holds, in a fixed order."""
    found = root / tree
    if not found.is_dir():
        msg = f"{tree.as_posix()} is not a directory, so there is nothing to read"
        raise MemberError(msg)
    return sorted(found.iterdir())


def _filenames(root: Path, pattern: str) -> list[str]:
    """Return the file names under `scripts/` matching ``pattern``, in a fixed order."""
    return [path.name for path in _listed(root, GATES) if fnmatchcase(path.name, pattern)]


def _directories(root: Path, tree: Path) -> list[str]:
    """Return the names of the directories directly under ``tree``, in a fixed order."""
    return [path.name for path in _listed(root, tree) if path.is_dir()]


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
    """Every `#[ignore]`d test in the body's live transport suite."""
    return _floored(ignored_tests(_read(root, LIVE_SEAM)), f"the ignored tests in {LIVE_SEAM}")


def gate_modules(root: Path) -> frozenset[str]:
    """Every module in `scripts/`, which is the set that directory's module contract describes."""
    return _floored(_filenames(root, MODULES), f"the modules in {GATES}")


def _with_a_cli(root: Path, *, wanted: bool) -> list[str]:
    """The modules in `scripts/` that do, or do not, have a top-level main guard."""
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
    """Every module `just check` and CI both run as a cross-tree scan."""
    try:
        found = scanrecipes.scan_modules(root)
    except ScanReadError as err:
        raise MemberError(str(err)) from err
    return _floored(found, "the cross-tree scans `just check` runs")


def brain_packages(root: Path) -> frozenset[str]:
    """Every package in the brain's uv workspace, which is every directory under it."""
    return _floored(_directories(root, PACKAGES), f"the packages in {PACKAGES}")


def body_crates(root: Path) -> frozenset[str]:
    """Every crate in the body's cargo workspace, which is every directory under it."""
    return _floored(_directories(root, CRATES), f"the crates in {CRATES}")


def registry_tuples(root: Path) -> frozenset[str]:
    """Every tuple the constant registry is joined from, named by the convention it declares."""
    parts = [Path(name).stem for name in _filenames(root, PARTS) if Path(name).stem != COUPLINGS]
    return _floored(
        (part.removesuffix(COUPLINGS).upper() + TUPLE for part in parts),
        f"the registry parts in {GATES}",
    )
