"""Which scans `just check` runs, read from the two files that run them."""

import re
from pathlib import Path

JUSTFILE = Path("justfile")
WORKFLOW = Path(".github/workflows/ci.yml")
CHECK_RECIPE = "check"
JOB = "cross-tree"

HEADER = r"^{name}(?: [^:]*)?:$"
INVOKES = re.compile(r"^\s+just (check-[a-z-]+)$")
STEP = re.compile(r"^\s+- run: (.+?)\s*$")
RUNS = re.compile(r"^just (check-[a-z-]+)$")
MODULE = re.compile(r"uv run python ([a-z_]+\.py)")


class ScanReadError(Exception):
    """The scans cannot be read, or the two files that run them disagree about which they are."""


def _indent(line: str) -> int:
    """How far ``line`` is indented, which is what decides whether it is inside the block above."""
    return len(line) - len(line.lstrip())


def _block(text: str, header: re.Pattern[str], what: str) -> list[str]:
    """Return the lines written under the first line matching ``header``, raising when none are."""
    lines = text.splitlines()
    for number, line in enumerate(lines):
        if header.match(line) is None:
            continue
        depth = _indent(line)
        body: list[str] = []
        for below in lines[number + 1 :]:
            if below.strip() and _indent(below) <= depth:
                break
            body.append(below)
        return body
    msg = f"{what} is not there, so what the scans are cannot be read"
    raise ScanReadError(msg)


def recipe_body(text: str, recipe: str) -> list[str]:
    """Return the body of one justfile recipe, raising on a name the justfile does not have."""
    header = re.compile(HEADER.format(name=re.escape(recipe)))
    return _block(text, header, f"the {recipe!r} recipe")


def check_scans(text: str) -> list[str]:
    """Return the recipes `just check` runs first, before the per-tree checks."""
    found: list[str] = []
    for line in recipe_body(text, CHECK_RECIPE):
        invoked = INVOKES.match(line)
        if invoked is not None:
            found.append(invoked.group(1))
        elif found:
            break
    return found


def job_scans(text: str) -> list[str]:
    """Return the recipes CI's cross-tree job runs, raising on a step that runs anything else."""
    header = re.compile(rf"^  {re.escape(JOB)}:$")
    found: list[str] = []
    for line in _block(text, header, f"the {JOB!r} job"):
        step = STEP.match(line)
        if step is None:
            continue
        runs = RUNS.match(step.group(1))
        if runs is None:
            msg = (
                f"the {JOB!r} job runs {step.group(1)!r}, which is not one of `just check`'s own "
                f"check recipes; this job is the scans and nothing else"
            )
            raise ScanReadError(msg)
        found.append(runs.group(1))
    return found


def recipe_module(text: str, recipe: str) -> str:
    """Return the one module a recipe runs, since a recipe and a module are not the same word."""
    modules = {
        found.group(1) for line in recipe_body(text, recipe) for found in MODULE.finditer(line)
    }
    if len(modules) != 1:
        msg = (
            f"the {recipe!r} recipe runs {len(modules)} module(s), {sorted(modules)}, and a scan "
            f"is one module a recipe runs"
        )
        raise ScanReadError(msg)
    return modules.pop()


def _read(root: Path, name: Path) -> str:
    """Read one of the two files that run the scans, naming it when it is absent or is not text."""
    try:
        return (root / name).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as err:
        msg = f"cannot read {name.as_posix()}: {err}"
        raise ScanReadError(msg) from err


def scan_modules(root: Path) -> frozenset[str]:
    """Every module `just check` and CI both run as a cross-tree scan, raising when they differ."""
    justfile = _read(root, JUSTFILE)
    check, job = check_scans(justfile), job_scans(_read(root, WORKFLOW))
    if set(check) != set(job):
        msg = (
            f"{JUSTFILE.as_posix()} runs {sorted(check)} before the trees and "
            f"{WORKFLOW.as_posix()}'s {JOB!r} job runs {sorted(job)}; a scan is what both run, so "
            f"neither list is the answer while they disagree"
        )
        raise ScanReadError(msg)
    return frozenset(recipe_module(justfile, recipe) for recipe in check)
