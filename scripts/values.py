"""What a value IS to `crosscheck.py`, and how the values at one constant's sites may stand."""

import re
from itertools import pairwise

from couplings import Constant, Relation, Site

# The only comment marker a declaration's right-hand side may carry. Rust and TypeScript need
# none: their value is captured up to the terminating semicolon, so a trailing `//` never
# arrives here.
COMMENT_MARKER = "#"

INTEGER_PRODUCT = re.compile(r"^\d[\d_]*(?:\s*\*\s*\d[\d_]*)*$")

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
