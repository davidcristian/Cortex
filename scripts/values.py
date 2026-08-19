"""What a value IS to `crosscheck.py`, and how the values at one constant's sites may stand.

Split out of the scan along a real seam rather than an arbitrary one: this module reduces a
declaration's right-hand side to something two languages can be compared on, and says whether a
set of readings holds; the scan finds the declarations in the tree and reports the ones that do
not. Nothing here reads a file, and nothing here knows where a value lives.

**Reduction, not text.** A value is compared after reduction, so one site may write ``6291456``
where another writes ``6 * 1024 * 1024``. Four forms reduce: a product of integer literals, a
plain double-quoted string, a one-line ``frozenset`` of those strings, which is how this repo
spells an allow-list, and a decimal literal. Anything else is refused rather than guessed at,
since a reducer that guesses is a gate that agrees with itself.

**A decimal reduces to its digits and not to a number**, which is the one place this module
deliberately stops short of arithmetic. ``5`` and ``5.0`` are the same number and different text,
and the text is the half a coupling needs: a mention renders the agreed value into its own
template and goes looking for the result, so a needle spelled ``5`` finds nothing in
``${CORTEX_BODY_CALL_TIMEOUT_S:-5.0}``. Reducing to a float would make those two one value, so a
site that dropped its point would keep agreeing while every place spending it went unfound. A
decimal therefore becomes ``Digits``, compared as the characters it is written with; an ordering
compares integers and refuses one rather than guessing how text sorts.

**Relations.** Most couplings are equalities. ``ORDERED`` holds the sites to non-decreasing order,
for the bounds that must sit under one another rather than match. ``MEMBER`` holds every site but
the last inside the collection the last one declares, which is the shape of a value one tree
produces and another tree accepts a set of: the two are not equal, neither is under the other, and
the only true thing to say about them is that one is in the other. Both read the registry's own
order, which is why an entry lists the bound before its ceiling and the value before its set.
"""

import re
from itertools import pairwise
from typing import NamedTuple

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

# The mark that dispatches to the decimal form, and the shape one may take: digits, one point,
# digits, with underscores grouping either run the way they group a product of integers. A leading
# or trailing point, an exponent, a sign, and a language's own type suffix are all refused with
# everything else this reducer will not guess at, no coupling in this repo spelling one.
DECIMAL_POINT = "."
DECIMAL = re.compile(r"^\d+(?:_\d+)*\.\d+(?:_\d+)*$")


class Digits(NamedTuple):
    """A decimal literal, held as the digits it is written with rather than as a number.

    Its own type rather than a bare ``str``, so a decimal never ties to a string literal that
    merely spells the same characters, and it renders as those digits wherever a needle or a
    fault is built out of it.
    """

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
