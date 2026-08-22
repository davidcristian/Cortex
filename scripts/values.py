"""What a value IS to `crosscheck.py`, and the spelling a mention may write one in."""

import re
from typing import NamedTuple

from couplings import PLACEHOLDER, Constant, Spelling

# The only comment marker a declaration's right-hand side may carry. Rust and TypeScript need
# none: their value is captured up to the terminating semicolon, so a trailing `//` never
# arrives here.
COMMENT_MARKER = "#"

INTEGER_PRODUCT = re.compile(r"^-?\d[\d_]*(?:\s*\*\s*\d[\d_]*)*$")

# The two words a boolean may be declared with, and the whole of that form. They are Python's own
# casing because Python declares every registered boolean; another language's are reached by
# `Spelling.LOWERED` at a mention rather than accepted at a site.
BOOLEANS = ("True", "False")

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


class Truth(NamedTuple):
    """A boolean literal, held as the word it is written with rather than as a truth value."""

    written: str

    def __repr__(self) -> str:
        """Render as the word itself, which is what a needle and a fault both want."""
        return self.written


type Value = str | int | frozenset[str] | Digits | Truth


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
        msg = (
            f"{text!r} is not a string, a collection of them, a boolean, a decimal, or a "
            "product of integers"
        )
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
    expression = _expression(stripped)
    if expression in BOOLEANS:
        return Truth(expression)
    if DECIMAL_POINT in expression:
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


def _lowered_spelling(value: Value) -> str:
    """A boolean in the lower case the other language writes the same answer in."""
    if not isinstance(value, Truth):
        msg = f"a lowered spelling needs a boolean, and this constant declares {value!r}"
        raise CrossCheckError(msg)
    return value.written.lower()


def spell(value: Value, spelling: Spelling) -> str:
    """The text a mention writes ``value`` as, in the spelling that mention asks for."""
    if spelling is Spelling.WHOLE:
        return _whole_spelling(value)
    if spelling is Spelling.LOWERED:
        return _lowered_spelling(value)
    return str(value)


def spelling_fault(constant: Constant) -> str | None:
    """The complaint about a lossy re-spelling with no faithful reading beside it, or None."""
    if not any(mention.spelling.lossy for mention in constant.mentions):
        return None
    faithful = (
        not mention.spelling.lossy and PLACEHOLDER in mention.template
        for mention in constant.mentions
    )
    if len(constant.sites) > 1 or any(faithful):
        return None
    return (
        "re-spells its one value everywhere it is spent, so nothing holds the spelling the site "
        "writes and a site that changed spelling alone would go unreported"
    )
