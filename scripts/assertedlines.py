"""The rendered log lines a package's own suite asserts whole, read off the suite's source."""

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
