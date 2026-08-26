"""Repo gate: fail when a runbook prints a log line the brain would not print that way."""

import argparse
import sys
from pathlib import Path
from typing import NamedTuple

from logcalls import LogCallError, logged, loggers
from logsamples import Sample, samples
from skippeddirs import SKIPPED_DIRS

# Where the documents that instruct an operator live. The one tree whose log samples are read as
# a claim about what the code prints today, argued in the module docstring.
RUNBOOKS = Path("docs/runbooks")

# The floors under the reading in the success line, and the same floors `stubcheck.py` carries: a
# side that came back empty has read nothing, and a comparison over nothing cannot fail.
MIN_SAMPLES = 1
MIN_LOGGERS = 1

# What a fault says in place of a field list that is empty, a bare pair of quotes being the one
# rendering a reader cannot tell from a formatting slip.
NO_FIELDS = "no fields"


class SampleCheckError(Exception):
    """An input could not be walked, or one side of the comparison came back empty."""


class Miss(NamedTuple):
    """One documented sample that does not say what the call site it quotes would print."""

    doc: str
    line: int
    detail: str


class Scan(NamedTuple):
    """One comparison: what it was over, then what it could not account for."""

    docs: int
    samples: int
    loggers: int
    misses: list[Miss]


def _read(path: Path, shown: str) -> str:
    """Read one runbook, refusing one that is absent or is not text."""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as err:
        msg = f"cannot read {shown}: {err}"
        raise SampleCheckError(msg) from err


def runbooks(root: Path) -> list[Path]:
    """Every runbook under ``root``, in a fixed order so a fault reads the same way twice."""
    tree = root / RUNBOOKS
    if not tree.is_dir():
        msg = f"{RUNBOOKS.as_posix()} is not a directory, so there is nothing to read"
        raise SampleCheckError(msg)
    return sorted(
        found
        for found in tree.rglob("*.md")
        if not SKIPPED_DIRS & set(found.relative_to(tree).parts)
    )


def listed(fields: tuple[str, ...]) -> str:
    """A field list as a fault should read it, with the empty one said in words."""
    return ", ".join(fields) if fields else NO_FIELDS


def disagreement(root: Path, names: dict[str, str], sample: Sample) -> str | None:
    """How ``sample`` differs from the call it quotes, or None when it prints what that call does.
    """
    module = names.get(sample.logger)
    if module is None:
        return f"names the logger {sample.logger!r}, which no module under the brain declares"
    try:
        call = logged(_read(root / module, module), sample.message, module)
    except LogCallError as err:
        return str(err)
    if call.level != sample.level:
        return f"prints {sample.level} where {module}:{call.line} logs at {call.level}"
    if call.fields != sample.fields:
        return (
            f"prints {listed(sample.fields)} where {module}:{call.line} attaches "
            f"{listed(call.fields)}"
        )
    return None


def check(root: Path) -> Scan:
    """Compare every log sample the runbooks print against the call that would print it."""
    try:
        names = loggers(root)
    except LogCallError as err:
        raise SampleCheckError(str(err)) from err
    if len(names) < MIN_LOGGERS:
        msg = "the brain declares no logger; a comparison over nothing cannot fail"
        raise SampleCheckError(msg)
    docs = runbooks(root)
    misses: list[Miss] = []
    counted = 0
    for doc in docs:
        shown = doc.relative_to(root).as_posix()
        for sample in samples(_read(doc, shown)):
            counted += 1
            detail = disagreement(root, names, sample)
            if detail is not None:
                misses.append(Miss(doc=shown, line=sample.line, detail=detail))
    if counted < MIN_SAMPLES:
        msg = f"no log sample under {RUNBOOKS.as_posix()}; a comparison over nothing cannot fail"
        raise SampleCheckError(msg)
    return Scan(docs=len(docs), samples=counted, loggers=len(names), misses=misses)


def main(argv: list[str] | None = None) -> int:
    """Run the gate; print any misses and return the process exit code."""
    parser = argparse.ArgumentParser(
        description="Fail when a documented log sample prints fields its call site does not.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(),
        help="repo root holding the runbooks and the brain (default: current directory)",
    )
    args = parser.parse_args(argv)
    given: Path = args.root
    if not given.is_dir():
        print(f"samplecheck: root {given} is not a directory", file=sys.stderr)
        return 2
    try:
        scanned = check(given.resolve())
    except SampleCheckError as err:
        print(f"samplecheck: {err}", file=sys.stderr)
        return 2
    for miss in scanned.misses:
        print(f"{miss.doc}:{miss.line}: the sample {miss.detail}")
    if scanned.misses:
        print(
            f"\nsamplecheck: {len(scanned.misses)} documented log sample(s) do not say what the "
            "call site would print. Fields render in name order, so move the sample onto what "
            "the code attaches, or change the code and the sample together.",
            file=sys.stderr,
        )
        return 1
    print(
        f"samplecheck OK: {scanned.samples} log sample(s) under {given} in {scanned.docs} "
        f"runbook(s) print the level, logger, message and fields their call sites write, "
        f"resolved against {scanned.loggers} logger(s) the brain declares"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover -- CLI entry point; main() is unit-tested
    sys.exit(main())
