"""The rendered log lines a package's own suite asserts whole, read off the suite's source.

`samplecheck.py`'s third reading, beside what a runbook claims (`logsamples.py`) and what a call
attaches (`logcalls.py` and `logfields.py`). It is consulted for one shape of call only: one whose
field list the code reader refuses, because the mapping handed to the call is grown after it is
bound and by condition, so no reading of the source says which fields one line carries. The tool
audit is that shape. What does say it is the sink's own suite, which builds a record, hands it to
the shipped formatter and asserts the whole rendered line back. A line asserted that way is one the
code prints under the conditions that test set up, and the assertion moves the day the sink does,
being an equality against the formatter's output rather than a restatement of the code (ADR-0009
proven-line addendum).

**Only an equality asserts a line.** A string is read when it is one side of ``assert x == "..."``
and in no other position. A containment check says the line carries that much and never that this
is the line: the tool audit's suite checks the head of a longer line with ``in`` to pin one field,
and reads a forged head of the trail back out of a value the same way, and either read as a whole
line would hold a runbook to a line the sink never prints. An ``in`` check, a name bound to a
string, and an f-string are each left unread, so a suite that asserts its lines through one of
them leaves the runbook sample unheld, which fails rather than passes.

**The line is anchored, and it is one line.** ``logsamples.SAMPLE`` is matched at the start of the
string rather than searched for, since what the formatter returned begins with the level, and a
string carrying a newline is not a line the formatter wrote, every value being escaped before it is
rendered.

**The sink's own suite, and no other.** The suite read is the ``tests`` directory beside the
``src`` the sink's module lives under. The orchestrator's logging suite asserts a whole
``cortex.tools.audit`` line too, written straight through the logger with one field to prove the
shipped level, and that is not a line the sink prints; a walk over every brain suite would have
held a runbook sample to it.
"""

import ast
from pathlib import Path
from typing import NamedTuple

from logcalls import SOURCE_DIR
from logsamples import SAMPLE, Sample, split_fields
from skippeddirs import SKIPPED_DIRS

# Where a package keeps the suite that proves its lines: beside the source directory rather than
# inside it, which is the convention `logcalls.modules` walks the other half of.
SUITE_DIR = "tests"

# The one comparison that asserts a whole line. A chain (`a == b == c`) is two comparisons and is
# left unread rather than split.
EQUALITY_OPS = 1


class AssertedLineError(Exception):
    """A suite could not be found or read, so no line in it can be read either."""


class Proven(NamedTuple):
    """One line a suite asserts whole: the file it stands in, and what the line renders."""

    suite: str
    sample: Sample


def suite_of(module: str) -> str:
    """The repo-relative tests directory beside the ``src`` that ``module`` lives under."""
    parts = Path(module).parts
    if SOURCE_DIR not in parts:
        msg = f"{module} is not under a {SOURCE_DIR} directory, so no suite stands beside it"
        raise AssertedLineError(msg)
    package = parts[: parts.index(SOURCE_DIR)]
    return Path(*package, SUITE_DIR).as_posix()


def _rendered(node: ast.expr) -> str | None:
    """The one-line string ``node`` is, or None when it is anything else."""
    if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
        return None
    return None if "\n" in node.value else node.value


def _equated(statement: ast.Assert) -> list[tuple[int, str]]:
    """Every one-line string that is one side of ``statement``'s equality, with its line."""
    test = statement.test
    if (
        not isinstance(test, ast.Compare)
        or len(test.ops) != EQUALITY_OPS
        or not isinstance(test.ops[0], ast.Eq)
    ):
        return []
    found: list[tuple[int, str]] = []
    for side in (test.left, test.comparators[0]):
        text = _rendered(side)
        if text is not None:
            found.append((side.lineno, text))
    return found


def asserted(source: str, shown: str) -> list[Sample]:
    """Every rendered line ``source`` asserts whole, read as what it claims to render."""
    try:
        tree = ast.parse(source)
    except SyntaxError as err:
        msg = f"cannot parse {shown}: {err}"
        raise AssertedLineError(msg) from err
    found: list[Sample] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assert):
            continue
        for line, text in _equated(node):
            printed = SAMPLE.match(text)
            if printed is None:
                continue
            message, fields = split_fields(printed["rest"])
            found.append(
                Sample(
                    line=line,
                    level=printed["level"],
                    logger=printed["logger"],
                    message=message,
                    fields=fields,
                )
            )
    return found


def proven(root: Path, module: str) -> list[Proven]:
    """Every line the suite beside ``module`` asserts whole, in a fixed order."""
    suite = suite_of(module)
    tree = root / suite
    if not tree.is_dir():
        msg = f"{suite} is not a directory, so nothing proves what {module} prints"
        raise AssertedLineError(msg)
    found: list[Proven] = []
    for path in sorted(tree.rglob("*.py")):
        if SKIPPED_DIRS & set(path.relative_to(tree).parts):
            continue
        shown = path.relative_to(root).as_posix()
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as err:
            msg = f"cannot read {shown}: {err}"
            raise AssertedLineError(msg) from err
        found.extend(Proven(suite=shown, sample=sample) for sample in asserted(source, shown))
    return found
