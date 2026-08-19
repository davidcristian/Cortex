"""What a value IS to `crosscheck.py`, and how the values at one constant's sites may stand."""

import re
from itertools import pairwise
from typing import NamedTuple

from couplings import PLACEHOLDER, Constant, Relation, Site, Spelling

# The only comment marker a declaration's right-hand side may carry. Rust and TypeScript need
# none: their value is captured up to the terminating semicolon, so a trailing `//` never
# arrives here.
COMMENT_MARKER = "#"

INTEGER_PRODUCT = re.compile(r"^\d[\d_]*(?:\s*\*\s*\d[\d_]*)*$")

COLLECTION_PREFIX = "frozenset("
COLLECTION = re.compile(r"^frozenset\(\{(?P<members>.+)\}\)$")

DECIMAL_POINT = "."
DECIMAL = re.compile(r"^\d+(?:_\d+)*\.\d+(?:_\d+)*$")


class Digits(NamedTuple):
    """A decimal literal, held as the digits it is written with rather than as a number."""

    written: str

    def __repr__(self) -> str:
        """Render as the digits themselves, which is what a needle and a fault both want."""
        return self.written


type Value = str | int | frozenset[str] | Digits
type Reading = tuple[Site, Value]


class CrossCheckError(Exception):
    """A constant's value could not be established, or a mention of it could not be found."""


def _expression(text: str) -> str:
    """A right-hand side with any trailing comment cut off it, which no value form reads."""
    return text.partition(COMMENT_MARKER)[0].strip()


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
    expression = _expression(text)
    if not INTEGER_PRODUCT.match(expression):
        msg = f"{text!r} is not a string, a collection of them, a decimal, or a product of integers"
        raise CrossCheckError(msg)
    product = 1
    for factor in expression.split("*"):
        product *= int(factor.replace("_", ""))
    return product


def _decimal_value(text: str) -> Digits:
    """Reduce a decimal literal to the digits it is written with, trailing zero and all."""
    expression = _expression(text)
    if not DECIMAL.match(expression):
        msg = f"{text!r} is not a decimal literal, which is digits, one point, and digits"
        raise CrossCheckError(msg)
    return Digits(expression.replace("_", ""))


def _collection_value(text: str) -> frozenset[str]:
    """Reduce a frozenset of string literals to its members, which a membership is decided on."""
    expression = _expression(text)
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
    if DECIMAL_POINT in _expression(stripped):
        return _decimal_value(stripped)
    return _integer_value(stripped)


def _whole_spelling(value: Value) -> str:
    """A number with no fractional part, for a far side whose syntax carries none."""
    if isinstance(value, int):
        return str(value)
    if not isinstance(value, Digits):
        msg = f"a whole spelling needs a number, and this constant declares {value!r}"
        raise CrossCheckError(msg)
    whole, _, fraction = value.written.partition(DECIMAL_POINT)
    if fraction.strip("0"):
        msg = (
            f"{value.written} cannot be spelled whole, its fraction being lost rather than "
            "zero, so the far side would be tied to a number the site does not declare"
        )
        raise CrossCheckError(msg)
    return whole


def spell(value: Value, spelling: Spelling) -> str:
    """The text a mention writes ``value`` as, in the spelling that mention asks for."""
    return str(value) if spelling is Spelling.WRITTEN else _whole_spelling(value)


def spelling_fault(constant: Constant) -> str | None:
    """The complaint about a re-spelling with no written form beside it, or None when one is."""
    if all(mention.spelling is Spelling.WRITTEN for mention in constant.mentions):
        return None
    written = (
        mention.spelling is Spelling.WRITTEN and PLACEHOLDER in mention.template
        for mention in constant.mentions
    )
    if len(constant.sites) > 1 or any(written):
        return None
    return (
        "re-spells its one value everywhere it is spent, so nothing holds the spelling the site "
        "writes and a site that changed spelling alone would go unreported"
    )


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
        return f"an ordering compares integers, and a site here declares something else ({shown})"
    return None if all(lower <= upper for lower, upper in pairwise(numbers)) else generic
