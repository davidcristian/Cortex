"""Reduce a declaration's right-hand side to a value two languages can be compared on."""

import re
from typing import NamedTuple

from couplings import PLACEHOLDER, Constant, Form

COMMENT_MARKER = "#"

# A leading `+` is refused because `str(1)` is `1`, so a mention would render a search text the
# site's own `+1` does not contain.
INTEGER_PRODUCT = re.compile(r"^-?\d[\d_]*(?:\s*\*\s*\d[\d_]*)*$")

BOOLEANS = ("True", "False")

COLLECTION_PREFIX = "frozenset("
COLLECTION = re.compile(r"^frozenset\(\{(?P<members>.+)\}\)$")

BLOCK_OPEN = "("
BLOCK_CLOSE = ")"

DECIMAL_POINT = "."
DECIMAL = re.compile(r"^\d+(?:_\d+)*\.\d+(?:_\d+)*$")


class Digits(NamedTuple):
    """A decimal literal, kept as the digits it is written with rather than as a number."""

    written: str

    def __repr__(self) -> str:
        """Render as the digits themselves, which a search text and a fault are built from."""
        return self.written


class Truth(NamedTuple):
    """A boolean literal, kept as the word it is written with rather than as a truth value."""

    written: str

    def __repr__(self) -> str:
        """Render as the word itself, which a search text and a fault are built from."""
        return self.written


type Value = str | int | frozenset[str] | Digits | Truth


class CrossCheckError(Exception):
    """A constant's value could not be established, or a mention of it could not be found."""


def _expression(text: str) -> str:
    """A right-hand side with any trailing comment removed, no value form reading one."""
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


def _block_value(text: str) -> str:
    """Join a parenthesized run of double-quoted literals, one per line, as Python joins them."""
    lines = text.splitlines()
    if _expression(lines[0]) != BLOCK_OPEN or _expression(lines[-1]) != BLOCK_CLOSE:
        msg = f"{text!r} is not a parenthesized run of string literals, one per line"
        raise CrossCheckError(msg)
    members = [line.strip() for line in lines[1:-1] if _expression(line)]
    if not members:
        msg = f"{text!r} is a parenthesized run with no literal in it"
        raise CrossCheckError(msg)
    return "".join(_string_value(member) for member in members)


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
    if stripped.startswith(BLOCK_OPEN):
        return _block_value(stripped)
    if stripped.startswith(COLLECTION_PREFIX):
        return _collection_value(stripped)
    expression = _expression(stripped)
    if expression in BOOLEANS:
        return Truth(expression)
    if DECIMAL_POINT in expression:
        return _decimal_value(stripped)
    return _integer_value(stripped)


def whole_form(value: Value) -> str:
    """A number with no fractional part, for a far side whose syntax has none."""
    if isinstance(value, int):
        return str(value)
    if not isinstance(value, Digits):
        msg = f"a whole form needs a number, and this constant declares {value!r}"
        raise CrossCheckError(msg)
    whole, _, fraction = value.written.partition(DECIMAL_POINT)
    if fraction.strip("0"):
        msg = (
            f"{value.written} cannot be written whole, its fraction being lost rather than "
            "zero, so the far side would be tied to a number the site does not declare"
        )
        raise CrossCheckError(msg)
    return whole


def _lowered_form(value: Value) -> str:
    """A boolean in the lower case the other language writes the same answer in."""
    if not isinstance(value, Truth):
        msg = f"a lowered form needs a boolean, and this constant declares {value!r}"
        raise CrossCheckError(msg)
    return value.written.lower()


def in_form(value: Value, form: Form) -> str:
    """The text a mention writes ``value`` as, in the form that mention asks for."""
    if form is Form.WHOLE:
        return whole_form(value)
    if form is Form.LOWERED:
        return _lowered_form(value)
    return str(value)


def form_fault(constant: Constant) -> str | None:
    """What is wrong when a value is rewritten in a lossy form with no exact one beside it."""
    if not any(mention.form.lossy for mention in constant.mentions):
        return None
    faithful = (
        not mention.form.lossy and PLACEHOLDER in mention.template for mention in constant.mentions
    )
    if len(constant.sites) > 1 or any(faithful):
        return None
    return (
        "rewrites its one value everywhere it is spent, so nothing holds the form the site "
        "writes and a site that changed form alone would go unreported"
    )
