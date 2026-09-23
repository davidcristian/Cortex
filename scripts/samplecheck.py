"""Fail when a runbook shows a log line the brain would not print that way."""

import argparse
import sys
from pathlib import Path
from typing import NamedTuple

from assertedlines import AssertedLineError, proven, suite_of
from logcalls import LogCallError, UnreadFieldsError, logged, messages
from loggernames import loggers
from logsamples import Sample, samples
from treewalk import walk_files

RUNBOOKS = Path("docs/runbooks")
MARKDOWN = ".md"

MIN_SAMPLES = 1
MIN_LOGGERS = 1
MIN_MESSAGES = 1

NO_FIELDS = "no fields"

NO_LINES = "none"


class SampleCheckError(Exception):
    """An input could not be walked, or one side of the comparison came back empty."""


class Miss(NamedTuple):
    """One documented sample that differs from what the call site it quotes would print."""

    doc: str
    line: int
    detail: str


class Finding(NamedTuple):
    """What one sample was compared against, and how it differs from it."""

    detail: str | None
    proven: bool


class Scan(NamedTuple):
    """What one comparison read, and what it could not account for."""

    docs: int
    samples: int
    loggers: int
    messages: int
    proven: int
    misses: list[Miss]


def _read(path: Path, shown: str) -> str:
    """Read one runbook, raising when it is absent or is not text."""
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
    return sorted(found for found in walk_files(tree) if found.suffix == MARKDOWN)


def listed(fields: tuple[str, ...]) -> str:
    """A field list as a fault prints it, with the empty list written out in words."""
    return ", ".join(fields) if fields else NO_FIELDS


def _proven(root: Path, module: str, sample: Sample, unread: UnreadFieldsError) -> str | None:
    """How ``sample`` differs from every whole line the sink's own tests assert, or None."""
    if unread.level != sample.level:
        return f"prints {sample.level} where {module}:{unread.line} logs at {unread.level}"
    try:
        lines = proven(root, module)
    except AssertedLineError as err:
        raise SampleCheckError(str(err)) from err
    alike = [
        held.sample.fields
        for held in lines
        if (held.sample.logger, held.sample.message) == (sample.logger, sample.message)
    ]
    if sample.fields in alike:
        return None
    shown = "; ".join(listed(fields) for fields in alike) if alike else NO_LINES
    return (
        f"prints {listed(sample.fields)} where {unread.reason}, and no line under "
        f"{suite_of(module)} is asserted whole with those fields (asserted whole there: {shown})"
    )


def disagreement(root: Path, names: dict[str, str], sample: Sample) -> Finding:
    """What ``sample`` was compared against, and how it differs from it when it does."""
    module = names.get(sample.logger)
    if module is None:
        detail = f"names the logger {sample.logger!r}, which no module under the brain declares"
        return Finding(detail=detail, proven=False)
    try:
        call = logged(_read(root / module, module), sample.message, module)
    except UnreadFieldsError as unread:
        return Finding(detail=_proven(root, module, sample, unread), proven=True)
    except LogCallError as err:
        return Finding(detail=str(err), proven=False)
    if call.level != sample.level:
        detail = f"prints {sample.level} where {module}:{call.line} logs at {call.level}"
        return Finding(detail=detail, proven=False)
    if call.fields != sample.fields:
        detail = (
            f"prints {listed(sample.fields)} where {module}:{call.line} attaches "
            f"{listed(call.fields)}"
        )
        return Finding(detail=detail, proven=False)
    return Finding(detail=None, proven=False)


def check(root: Path) -> Scan:
    """Compare every log sample the runbooks print against the call that would print it."""
    try:
        names = loggers(root)
        written = messages(root)
    except LogCallError as err:
        raise SampleCheckError(str(err)) from err
    if len(names) < MIN_LOGGERS:
        msg = "the brain declares no logger; a comparison over nothing cannot fail"
        raise SampleCheckError(msg)
    lines = sum(len(found) for found in written.values())
    if lines < MIN_MESSAGES:
        msg = "the brain logs no message; a comparison over nothing cannot fail"
        raise SampleCheckError(msg)
    docs = runbooks(root)
    misses: list[Miss] = []
    counted = 0
    held = 0
    for doc in docs:
        shown = doc.relative_to(root).as_posix()
        for sample in samples(_read(doc, shown)):
            counted += 1
            finding = disagreement(root, names, sample)
            if finding.proven:
                held += 1
            if finding.detail is not None:
                misses.append(Miss(doc=shown, line=sample.line, detail=finding.detail))
    if counted < MIN_SAMPLES:
        msg = f"no log sample under {RUNBOOKS.as_posix()}; a comparison over nothing cannot fail"
        raise SampleCheckError(msg)
    return Scan(
        docs=len(docs),
        samples=counted,
        loggers=len(names),
        messages=lines,
        proven=held,
        misses=misses,
    )


def main(argv: list[str] | None = None) -> int:
    """Run the check; print any misses and return the process exit code."""
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
        f"resolved against {scanned.loggers} logger(s) the brain declares and the "
        f"{scanned.messages} message(s) it logs, {scanned.proven} of the samples held to a line "
        "the sink's own suite asserts whole"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover -- CLI entry point; main() is unit-tested
    sys.exit(main())
