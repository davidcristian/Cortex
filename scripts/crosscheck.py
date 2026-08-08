"""Repo gate: fail when one value spelled in two trees stops agreeing with itself."""

import argparse
import re
import sys
from itertools import pairwise
from pathlib import Path
from typing import NamedTuple

from couplings import CONSTANTS, PLACEHOLDER, Constant, Mention, Relation, Site

# The only comment marker a declaration's right-hand side may carry. Rust and TypeScript need
# none: their value is captured up to the terminating semicolon, so a trailing `//` never
# arrives here.
COMMENT_MARKER = "#"

INTEGER_PRODUCT = re.compile(r"^\d[\d_]*(?:\s*\*\s*\d[\d_]*)*$")

# A registry entry naming one place would agree with itself forever, which is the gate that
# cannot fail this scan was written to remove. Two is therefore the floor, not a formality, and
# it counts mentions: a lone declaration plus one place that spends it is a real coupling.
MIN_PLACES = 2

DECLARATIONS = {
    ".py": r"^{name}(?:\s*:[^=\n]*)?\s*=(?P<value>[^\n]*)$",
    ".rs": (
        r"^[ \t]*(?:pub(?:\([^)]*\))?[ \t]+)?(?:const|static)[ \t]+{name}"
        r"[ \t]*:[^=\n]*=(?P<value>[^;\n]*);"
    ),
    ".ts": r"^(?:export[ \t]+)?const[ \t]+{name}(?:[ \t]*:[^=\n]*)?[ \t]*=(?P<value>[^;\n]*);",
}


class CrossCheckError(Exception):
    """A constant's value could not be established, or a mention of it could not be found."""


class Fault(NamedTuple):
    """One constant that is not tied: a place that cannot be read, or places that disagree."""

    label: str
    detail: str


def _string_value(text: str) -> str:
    """Read one double-quoted literal, tolerating only a trailing comment after it."""
    end = text.find('"', 1)
    if end < 0:
        msg = f"unterminated string literal in {text!r}"
        raise CrossCheckError(msg)
    literal = text[1:end]
    if "\\" in literal:
        msg = f"escapes are not decoded, so {text!r} cannot be compared"
        raise CrossCheckError(msg)
    trailer = text[end + 1 :].strip()
    if trailer and not trailer.startswith(COMMENT_MARKER):
        msg = f"{text!r} is more than one string literal"
        raise CrossCheckError(msg)
    return literal


def _integer_value(text: str) -> int:
    """Reduce a product of integer literals, so `6 * 1024 * 1024` compares as 6291456."""
    expression = text.partition(COMMENT_MARKER)[0].strip()
    if not INTEGER_PRODUCT.match(expression):
        msg = f"{text!r} is neither a string literal nor a product of integers"
        raise CrossCheckError(msg)
    product = 1
    for factor in expression.split("*"):
        product *= int(factor.replace("_", ""))
    return product


def parse_value(text: str) -> str | int:
    """Reduce a declaration's right-hand side to a value two languages compare on."""
    stripped = text.strip()
    if stripped.startswith('"'):
        return _string_value(stripped)
    return _integer_value(stripped)


def _read(root: Path, path: str) -> str:
    """Return one registered file's text, or raise when it cannot be read."""
    try:
        return (root / path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as err:
        msg = f"cannot read {path}: {err}"
        raise CrossCheckError(msg) from err


def read_value(root: Path, site: Site) -> str | int:
    """Return the value ``site`` declares under ``root``, or raise when it cannot be read."""
    template = DECLARATIONS.get(Path(site.path).suffix)
    if template is None:
        msg = f"no declaration syntax is known for {site.path}"
        raise CrossCheckError(msg)
    text = _read(root, site.path)
    pattern = re.compile(template.replace("{name}", re.escape(site.name)), re.MULTILINE)
    found: list[str] = pattern.findall(text)
    if not found:
        msg = f"{site.path} declares no {site.name}"
        raise CrossCheckError(msg)
    if len(found) > 1:
        msg = f"{site.path} declares {site.name} {len(found)} times"
        raise CrossCheckError(msg)
    return parse_value(found[0])


def check_mention(root: Path, mention: Mention, value: str | int) -> None:
    """Raise unless the file spends ``value`` in the shape the mention names."""
    if PLACEHOLDER not in mention.template:
        msg = f"mention {mention.template!r} carries no {PLACEHOLDER}, so it ties nothing"
        raise CrossCheckError(msg)
    needle = mention.template.replace(PLACEHOLDER, str(value))
    if needle not in _read(root, mention.path):
        msg = f"{mention.path} does not spell {needle!r}"
        raise CrossCheckError(msg)


def registry_fault(constant: Constant) -> str | None:
    """The complaint about how a registry entry is written, or None when it can tie anything."""
    if not constant.sites:
        return "names no declaring site, so nothing establishes its value"
    if len(constant.sites) + len(constant.mentions) < MIN_PLACES:
        return "names fewer than two places, so it compares nothing"
    if constant.relation is not Relation.EQUAL and constant.mentions:
        return f"is {constant.relation.value}, so it has no one value a mention could spell"
    return None


def relation_fault(constant: Constant, values: list[tuple[Site, str | int]]) -> str | None:
    """The complaint about how the read values stand to each other, or None when they hold."""
    numbers = [value for _, value in values if isinstance(value, int)]
    shown = ", ".join(f"{site.path}: {site.name} = {value!r}" for site, value in values)
    if constant.relation is Relation.EQUAL:
        if len({value for _, value in values}) == 1:
            return None
    elif len(numbers) < len(values):
        return f"an ordering compares numbers, and a site here declares a string ({shown})"
    elif all(lower <= upper for lower, upper in pairwise(numbers)):
        return None
    return f"sites are not {constant.relation.value} ({shown})"


def check_constant(root: Path, constant: Constant) -> list[Fault]:
    """Return every fault for one constant: unreadable places first, then how they relate."""
    written = registry_fault(constant)
    if written is not None:
        return [Fault(label=constant.label, detail=written)]
    values: list[tuple[Site, str | int]] = []
    faults: list[Fault] = []
    for site in constant.sites:
        try:
            values.append((site, read_value(root, site)))
        except CrossCheckError as err:
            faults.append(Fault(label=constant.label, detail=str(err)))
    if faults:
        return faults
    detail = relation_fault(constant, values)
    if detail is not None:
        return [Fault(label=constant.label, detail=f"{detail}; {constant.why}")]
    for mention in constant.mentions:
        try:
            check_mention(root, mention, values[0][1])
        except CrossCheckError as err:
            faults.append(Fault(label=constant.label, detail=f"{err}; {constant.why}"))
    return faults


def check(root: Path, constants: tuple[Constant, ...] | None = None) -> list[Fault]:
    """Check every registered constant under ``root``, in registry order."""
    registry = CONSTANTS if constants is None else constants
    return [fault for constant in registry for fault in check_constant(root, constant)]


def main(argv: list[str] | None = None) -> int:
    """Run the gate; print any faults and return the process exit code."""
    parser = argparse.ArgumentParser(
        description="Fail when a constant spelled in two trees stops agreeing with itself.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(),
        help="repo root holding the declaring trees (default: current directory)",
    )
    args = parser.parse_args(argv)
    root: Path = args.root
    if not root.is_dir():
        print(f"crosscheck: root {root} is not a directory", file=sys.stderr)
        return 2
    faults = check(root)
    for fault in faults:
        print(f"{fault.label}: {fault.detail}")
    if faults:
        print(
            f"\ncrosscheck: {len(faults)} cross-tree constant(s) are not tied. Change every "
            "place together, or update the registry in couplings.py if one of them moved.",
            file=sys.stderr,
        )
        return 1
    print(f"crosscheck OK: {len(CONSTANTS)} cross-tree constant(s) under {root} agree")
    return 0


if __name__ == "__main__":  # pragma: no cover -- CLI entry point; main() is unit-tested
    sys.exit(main())
