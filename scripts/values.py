"""Reduce a declaration's right-hand side to a value two languages can be compared on.

`crosscheck.py` finds the declarations in the tree and reports the ones that disagree; this module
says what each one reduces to and what text a mention writes it as. It reads no files.
`defaultcheck.py` calls `whole_spelling` too, `8.0` beside `8` being the same question there.

Six forms reduce: a product of integer literals, a double-quoted string, a parenthesized run of
those strings across several lines, which reduces to the one string Python joins them into, a
one-line `frozenset` of those strings, a decimal, and a boolean. Anything else raises
`CrossCheckError`, because a guessed reduction would report two values as equal that were never
compared. A decimal reduces to its digits and a boolean to its word rather than to a number or a
truth value, since the comparison is textual. The ADR-0029 cross-language-constant addendum argues
that, and the rule that a lossy re-spelling needs a faithful reading beside it. How a set of
readings must then stand is `readings.py`.
"""

import re
from typing import NamedTuple

from couplings import PLACEHOLDER, Constant, Spelling

# The only comment marker a declaration's right-hand side may carry. Rust and TypeScript need
# none: their value is captured up to the terminating semicolon, so a trailing `//` never
# arrives here.
COMMENT_MARKER = "#"

# A product of integer literals, which may open with a minus. The sign belongs to the whole
# expression and never to a factor, since `2 * -3` appears nowhere here. A leading `+` is refused
# because `str(1)` is `1`, so a mention would render a needle the site's own `+1` does not contain.
INTEGER_PRODUCT = re.compile(r"^-?\d[\d_]*(?:\s*\*\s*\d[\d_]*)*$")

# The two words a boolean may be declared with. They are Python's casing because Python declares
# every registered boolean; another language's casing is reached by `Spelling.LOWERED` at a
# mention rather than accepted at a site.
BOOLEANS = ("True", "False")

# The one collection syntax that reduces, and the prefix that dispatches to it. A `frozenset` of
# string literals on one line is how this repo writes an allow-list; a set literal is mutable, and
# a multi-line form never reaches here because the declaration syntaxes capture a single line.
# Members are read by the string form below, so a member that is not a plain double-quoted literal
# raises.
COLLECTION_PREFIX = "frozenset("
COLLECTION = re.compile(r"^frozenset\(\{(?P<members>.+)\}\)$")

# The one multi-line form that reduces, and the prefix that dispatches to it: a parenthesized run
# of double-quoted literals, one per line, which is how Python writes a sentence too long for one
# line and how the formatter leaves it. It reduces to the one string Python joins the run into, so
# a site written on three lines ties to a site written on four. The opening line carries the
# parenthesis and the closing line the other, each with at most a trailing comment; a line between
# them that is blank or only a comment is skipped, and every other one is read by the string form,
# so an f-string, a name or a single-quoted literal inside the run raises rather than being
# guessed at. Only the Python declaration syntax captures a run (`crosscheck.DECLARATIONS`); the
# other two capture a single line, up to its semicolon.
BLOCK_OPEN = "("
BLOCK_CLOSE = ")"

# The mark that dispatches to the decimal form, and the shape one may take: digits, one point,
# digits, with underscores grouping either run the way they group a product of integers. A leading
# or trailing point, an exponent, a sign, and a language's own type suffix all raise, since no
# coupling in this repo writes one.
DECIMAL_POINT = "."
DECIMAL = re.compile(r"^\d+(?:_\d+)*\.\d+(?:_\d+)*$")


class Digits(NamedTuple):
    """A decimal literal, held as the digits it is written with rather than as a number.

    Its own type rather than a bare ``str``, so a decimal never compares equal to a string literal
    with the same characters.
    """

    written: str

    def __repr__(self) -> str:
        """Render as the digits themselves, which is what a needle and a fault are built from."""
        return self.written


class Truth(NamedTuple):
    """A boolean literal, held as the word it is written with rather than as a truth value.

    Its own type for the reason ``Digits`` is, and because a Python `bool` is an `int`: a bare
    `False` would compare equal to a site declaring `0` and would sort under an ordering.
    """

    written: str

    def __repr__(self) -> str:
        """Render as the word itself, which is what a needle and a fault are built from."""
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


def whole_spelling(value: Value) -> str:
    """A number with no fractional part, for a far side whose syntax carries none.

    An integer is already whole. A decimal gives up the digits behind its point when they are
    zeros, and raises when they are not: docker's size suffix cannot write `8.5`, and truncating it
    here would tie that far side to `8` while the site went on declaring `8.5`.
    """
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
    """A boolean in the lower case the other language writes the same answer in.

    Only a boolean, because only a boolean's casing is one language's own spelling of an answer
    both languages hold. Folding a string would tie two literals differing in case alone.
    """
    if not isinstance(value, Truth):
        msg = f"a lowered spelling needs a boolean, and this constant declares {value!r}"
        raise CrossCheckError(msg)
    return value.written.lower()


def spell(value: Value, spelling: Spelling) -> str:
    """The text a mention writes ``value`` as, in the spelling that mention asks for."""
    if spelling is Spelling.WHOLE:
        return whole_spelling(value)
    if spelling is Spelling.LOWERED:
        return _lowered_spelling(value)
    return str(value)


def spelling_fault(constant: Constant) -> str | None:
    """The complaint about a lossy re-spelling with no faithful reading beside it, or None.

    A whole spelling renders `8` and `8.0` alike, so an entry whose mentions all spell whole would
    not report a site that dropped its point. Such an entry has to carry a faithful reading as
    well: a second site the sites are compared against textually, or a mention rendering the value
    in a spelling two declared values cannot share.
    """
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
