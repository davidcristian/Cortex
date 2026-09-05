"""Repo gate: fail when a runbook prints a log line the brain would not print that way.

A runbook that shows a rendered log line is telling an operator what to expect on a stream while
somebody is waiting, and nothing held those samples to the calls that write them. A field the call
site stopped attaching left the sample printing something the code never emits; a field it started
attaching left the sample short of one, with every gate green either way, because a document is
text and the fields on a line are a dict two hundred files away (ADR-0009 sample-membership
addendum).

For every sample it finds: the level the sample prints is the level the call logs at, the logger it
names is the module that owns that name, the message is one a call there really writes, and the
fields are exactly the ones that call attaches, in exactly the order the formatter will print them.
One comparison covers membership and order together, since the printed order is name order and
therefore a function of the key set alone.

One shape of call has no field list the source can give: a mapping bound, grown by condition and
only then handed over, which is how the tool audit writes its line. The code reader refuses that
call rather than choosing a branch, and a sample of it is held instead to the sink's own suite,
which asserts whole rendered lines against the shipped formatter (`assertedlines.py`). The sample
passes when some line that suite asserts whole prints the same level, logger, message and fields;
the level is still compared against the call first, since the call is read that far. A line the
suite proves is one the code prints under that test's conditions, and the assertion moves the day
the sink does, so the chain from the runbook to the code is unbroken; what stays in prose is which
condition a sample stands for (ADR-0009 proven-line addendum).

Values are deliberately not held. A sample's values are placeholders as often as readings, and one
runbook's captured `port=50051` is registered in the constant scan as a dated reading rather than a
coupling, on the argument that a captured line stays true after the default it quotes moves.
Holding values here would overturn that decision from a second gate, and it would demand that a
hand-written sample quote its placeholders the way the formatter quotes a value with a space in it.

Samples are found rather than registered: the walk reads the runbooks and checks every fenced line
that looks like a rendered one. A registry would leave a new sample unheld until somebody
remembered it. What that costs is that a runbook quoting a line no brain module writes fails rather
than being skipped, which is the intended direction.

Only runbooks are read. An ADR's transcripts are evidence of a run on a day, recorded beside the
decision they justify, and this repo already holds that an addendum records what was decided when
it was decided. Holding a dated transcript to today's code would make a record of the past
something that has to be edited to stay green. A runbook is the other kind: instructions, in the
present tense, opened while something is broken.

The whole brain is read, not only the modules a sample names. Both sides of a line are collected
before any sample is looked at, the loggers the brain declares and the messages it logs, and each
collection carries a rule of its own about a word written twice in one module, once for a logger
name and once for a message. Those rules are about a module rather than about a document, so
running them here is what gives them the tree: a doubled name is refused the day it is written
rather than the day a runbook happens to quote that line.

An unreadable runbook tree, a brain whose loggers or messages cannot be collected, and either side
of the comparison coming back empty each fail rather than passing quietly, since a gate over no
samples would report success forever. The success line states what the comparison was over, samples
and runbooks and the loggers and messages they were resolved against, because a verdict that would
be equally true of a tree this walk never entered has to say which tree it is over.
"""

import argparse
import sys
from pathlib import Path
from typing import NamedTuple

from assertedlines import AssertedLineError, proven, suite_of
from logcalls import LogCallError, UnreadFieldsError, logged, messages
from loggernames import loggers
from logsamples import Sample, samples
from skippeddirs import SKIPPED_DIRS

# Where the documents that instruct an operator live. The one tree whose log samples are read as
# a claim about what the code prints today, argued in the module docstring.
RUNBOOKS = Path("docs/runbooks")

# The floors under the reading in the success line: a side that came back empty has read nothing,
# and a comparison over nothing cannot fail.
MIN_SAMPLES = 1
MIN_LOGGERS = 1
MIN_MESSAGES = 1

# What a fault says in place of a field list that is empty, a bare pair of quotes being the one
# rendering a reader cannot tell from a formatting slip.
NO_FIELDS = "no fields"

# What a fault says when the sink's suite asserts no line of the sample's message whole, in place
# of an empty list of what it does assert.
NO_LINES = "none"


class SampleCheckError(Exception):
    """An input could not be walked, or one side of the comparison came back empty."""


class Miss(NamedTuple):
    """One documented sample that does not say what the call site it quotes would print."""

    doc: str
    line: int
    detail: str


class Verdict(NamedTuple):
    """What one sample was held to, and how it differs from that when it does.

    ``proven`` is True when the sample was held to a line the sink's own suite asserts whole,
    the call's field list being one the source cannot give.
    """

    detail: str | None
    proven: bool


class Scan(NamedTuple):
    """One comparison: what it was over, then what it could not account for.

    ``proven`` counts the samples held to a suite's assertion rather than to the call.
    """

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
    return sorted(
        found
        for found in tree.rglob("*.md")
        if not SKIPPED_DIRS & set(found.relative_to(tree).parts)
    )


def listed(fields: tuple[str, ...]) -> str:
    """A field list as a fault should read it, with the empty one said in words."""
    return ", ".join(fields) if fields else NO_FIELDS


def _proven(root: Path, module: str, sample: Sample, unread: UnreadFieldsError) -> str | None:
    """How ``sample`` differs from every line the sink's own suite asserts whole, or None.

    Reached only when the code reader refused the call's field list. The level was read off the
    call before that and is compared first; the fields are compared against each line the suite
    asserts whole under the sample's logger and message. A suite that cannot be walked raises,
    the way a module that cannot be read does.
    """
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


def disagreement(root: Path, names: dict[str, str], sample: Sample) -> Verdict:
    """What ``sample`` was held to, and how it differs from that, with no detail when it agrees.

    A module this reader cannot account for is reported here beside the samples rather than
    raised, so one run names every disagreement instead of only the first. A module it cannot READ
    is an input failure and raises, the way an unreadable runbook does.
    """
    module = names.get(sample.logger)
    if module is None:
        detail = f"names the logger {sample.logger!r}, which no module under the brain declares"
        return Verdict(detail=detail, proven=False)
    try:
        call = logged(_read(root / module, module), sample.message, module)
    except UnreadFieldsError as unread:
        return Verdict(detail=_proven(root, module, sample, unread), proven=True)
    except LogCallError as err:
        return Verdict(detail=str(err), proven=False)
    if call.level != sample.level:
        detail = f"prints {sample.level} where {module}:{call.line} logs at {call.level}"
        return Verdict(detail=detail, proven=False)
    if call.fields != sample.fields:
        detail = (
            f"prints {listed(sample.fields)} where {module}:{call.line} attaches "
            f"{listed(call.fields)}"
        )
        return Verdict(detail=detail, proven=False)
    return Verdict(detail=None, proven=False)


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
            verdict = disagreement(root, names, sample)
            if verdict.proven:
                held += 1
            if verdict.detail is not None:
                misses.append(Miss(doc=shown, line=sample.line, detail=verdict.detail))
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
        f"resolved against {scanned.loggers} logger(s) the brain declares and the "
        f"{scanned.messages} message(s) it logs, {scanned.proven} of the samples held to a line "
        "the sink's own suite asserts whole"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover -- CLI entry point; main() is unit-tested
    sys.exit(main())
