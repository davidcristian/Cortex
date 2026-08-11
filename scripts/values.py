"""What a value IS to `crosscheck.py`, and how the values at one constant's sites may stand.

Split out of the scan along a real seam rather than an arbitrary one: this module reduces a
declaration's right-hand side to something two languages can be compared on, and says whether a
set of readings holds; the scan finds the declarations in the tree and reports the ones that do
not. Nothing here reads a file, and nothing here knows where a value lives.

**Reduction, not text.** A value is compared after reduction, so one site may write ``6291456``
where another writes ``6 * 1024 * 1024``. Three forms reduce: a product of integer literals, a
plain double-quoted string, and a one-line ``frozenset`` of those strings, which is how this repo
spells an allow-list. Anything else is refused rather than guessed at, since a reducer that
guesses is a gate that agrees with itself.

**Relations.** Most couplings are equalities. ``ORDERED`` holds the sites to non-decreasing order,
for the bounds that must sit under one another rather than match. ``MEMBER`` holds every site but
the last inside the collection the last one declares, which is the shape of a value one tree
produces and another tree accepts a set of: the two are not equal, neither is under the other, and
the only true thing to say about them is that one is in the other. Both read the registry's own
order, which is why an entry lists the bound before its ceiling and the value before its set.
"""

import re
from itertools import pairwise

from couplings import Constant, Relation, Site

# The only comment marker a declaration's right-hand side may carry. Rust and TypeScript need
# none: their value is captured up to the terminating semicolon, so a trailing `//` never
# arrives here.
COMMENT_MARKER = "#"

INTEGER_PRODUCT = re.compile(r"^\d[\d_]*(?:\s*\*\s*\d[\d_]*)*$")

# The one collection syntax that reduces, and the prefix that dispatches to it. A `frozenset` of
# string literals on one line is what an allow-list looks like in this repo; a set literal is
# mutable and a multi-line spelling never reaches here, the declaration forms capturing one line.
# The members are read by the string form below, so a member that is not a plain double-quoted
# literal is refused with everything else this reducer will not guess at.
COLLECTION_PREFIX = "frozenset("
COLLECTION = re.compile(r"^frozenset\(\{(?P<members>.+)\}\)$")

type Value = str | int | frozenset[str]
type Reading = tuple[Site, Value]


class CrossCheckError(Exception):
    """A constant's value could not be established, or a mention of it could not be found."""


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
        msg = f"{text!r} is not a string, a collection of them, or a product of integers"
        raise CrossCheckError(msg)
    product = 1
    for factor in expression.split("*"):
        product *= int(factor.replace("_", ""))
    return product


def _collection_value(text: str) -> frozenset[str]:
    """Reduce a frozenset of string literals to its members, which a membership is decided on."""
    expression = text.partition(COMMENT_MARKER)[0].strip()
    written = COLLECTION.match(expression)
    if written is None:
        msg = f"{text!r} is not a one-line frozenset of string literals"
        raise CrossCheckError(msg)
    return frozenset(_string_value(member.strip()) for member in written["members"].split(","))


def parse_value(text: str) -> Value:
    """Reduce a declaration's right-hand side to a value two languages compare on."""
    stripped = text.strip()
    if stripped.startswith('"'):
        return _string_value(stripped)
    if stripped.startswith(COLLECTION_PREFIX):
        return _collection_value(stripped)
    return _integer_value(stripped)


def _member_fault(readings: list[Value], shown: str, generic: str) -> str | None:
    """A membership holds when every reading but the last is in the collection the last one is."""
    *produced, accepted = readings
    if not isinstance(accepted, frozenset):
        return (
            "a membership needs a collection at the last site, and that site declares a lone "
            f"value ({shown})"
        )
    return None if all(value in accepted for value in produced) else generic


def relation_fault(constant: Constant, values: list[Reading]) -> str | None:
    """The complaint about how the read values stand to each other, or None when they hold."""
    shown = ", ".join(f"{site.path}: {site.name} = {value!r}" for site, value in values)
    generic = f"sites are not {constant.relation.value} ({shown})"
    readings = [value for _, value in values]
    if constant.relation is Relation.EQUAL:
        return None if len(set(readings)) == 1 else generic
    if constant.relation is Relation.MEMBER:
        return _member_fault(readings, shown, generic)
    numbers = [value for value in readings if isinstance(value, int)]
    if len(numbers) < len(readings):
        return f"an ordering compares numbers, and a site here declares something else ({shown})"
    return None if all(lower <= upper for lower, upper in pairwise(numbers)) else generic
