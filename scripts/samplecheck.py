"""Repo gate: fail when a runbook prints a log line the brain would not print that way.

A runbook that shows a rendered log line is telling an operator what to expect on a stream while
somebody is waiting. Nothing held those samples to the calls that write them. A field the call site
stopped attaching left the sample printing something the code never emits; a field it started
attaching left the sample short of one, with every gate green either way, because a document is
text and the fields on a line are a dict two hundred files away (ADR-0009 sample-membership
addendum).

**What it holds, for every sample it finds.** The level the sample prints is the level the call
logs at, the logger it names is the module that owns that name, the message is one a call there
really writes, and the fields are exactly the ones that call attaches, in exactly the order the
formatter will print them. One comparison covers membership and order together, since the printed
order is name order and therefore a function of the key set alone.

**What it deliberately does not hold: values.** A sample's values are placeholders as often as
readings, and one runbook's captured `port=50051` is registered in the constant scan as a dated
reading rather than a coupling, on the argument that a captured line stays true after the default
it quotes moves. Holding values here would overturn that decision from a second gate. It would also
demand that a hand-written sample quote its placeholders the way the formatter quotes a value with
a space in it, which is a fiction the ADR already refused to teach a gate to expect.

**Found rather than registered.** There is no list of samples to keep current: the walk reads the
runbooks and every fenced line that looks like a rendered one is checked. A registry would leave a
new sample unheld until somebody remembered it, which is the same silence this gate closes. What
that costs is that a runbook quoting a line no brain module writes is a failure rather than a
skip, and that is the intended direction: fail closed, and register nothing.

**Runbooks and not every document.** An ADR's transcripts are evidence of a run on a day, recorded
beside the decision they justify, and this repo already holds that an addendum records what was
decided when it was decided. Holding a dated transcript to today's code would make a record of the
past a thing that must be edited to stay green, which is the opposite of what it is for. A runbook
is the other kind: instructions, in the present tense, opened while something is broken. So the
walk reads `docs/runbooks/` and the ADRs are declared evidence rather than contract.

**Fail closed.** An unreadable runbook tree, a brain whose loggers cannot be collected, and either
side of the comparison coming back empty are each a failure rather than a quiet pass: a gate over
no samples would report success forever.

**The success line states what the comparison was over**, samples and runbooks and the loggers they
were resolved against, because a verdict that would be equally true of a tree this walk never
entered has to say which tree it is over. It is a reading and nothing asserts it; the floors under
it are the assertion.
"""

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

    A module this reader cannot account for is reported here beside the samples rather than
    thrown, so one run names every disagreement instead of the first. A module it cannot READ is
    not: that is an input failure and it leaves by the same door an unreadable runbook does.
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
