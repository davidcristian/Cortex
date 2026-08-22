"""What a value IS to `crosscheck.py`, and the spelling a mention may write one in.

Split out of the scan along a real seam rather than an arbitrary one: this module reduces a
declaration's right-hand side to something two languages can be compared on; the scan finds the
declarations in the tree and reports the ones that do not tie. Nothing here reads a file, and
nothing here knows where a value lives.

**Reduction, not text.** A value is compared after reduction, so one site may write ``6291456``
where another writes ``6 * 1024 * 1024``. Five forms reduce: a product of integer literals, which
may carry a leading minus; a plain double-quoted string; a one-line ``frozenset`` of those
strings, which is how this repo spells an allow-list; a decimal literal; and a boolean. Anything
else is refused rather than guessed at, since a reducer that guesses is a gate that agrees with
itself.

**A decimal reduces to its digits and not to a number**, which is the one place this module
deliberately stops short of arithmetic. ``5`` and ``5.0`` are the same number and different text,
and the text is the half a coupling needs: a mention renders the agreed value into its own
template and goes looking for the result, so a needle spelled ``5`` finds nothing in
``${CORTEX_BODY_CALL_TIMEOUT_S:-5.0}``. Reducing to a float would make those two one value, so a
site that dropped its point would keep agreeing while every place spending it went unfound. A
decimal therefore becomes ``Digits``, compared as the characters it is written with; an ordering
compares integers and refuses one rather than guessing how text sorts.

**A boolean reduces to its word and not to a truth value**, for that same reason and one more.
The same one is that the word is what a mention goes looking for. The extra one is Python's own:
``False`` is an ``int`` that equals ``0``, so a bare ``bool`` would tie to a site declaring zero
and would sort under an ordering that has no business over an answer with two values. A boolean
therefore becomes ``Truth``, and the two words it may be written with are Python's, that being
the only language a registered boolean is declared in. A second language's casing at a SITE would
be two texts for one answer, which is a disagreement this scan would report and nobody has; a far
side that writes another casing is reached by a spelling instead.

**Spellings.** Because the comparison is textual, a far side whose syntax cannot take the value as
the site writes it cannot be reached by rendering that text: docker parses `8g` as a size and
refuses `8.0g`, so a budget declared `8.0` is spelled `8` there, and YAML writes the answer Python
spells `False` as `false`. ``spell`` re-spells the agreed value for such a mention, deriving the
second spelling from the first rather than taking a second one on trust, and refusing any value it
would have to change to fit. It stays out of arithmetic exactly as the reducer does: a whole
spelling is the digits before the point, taken when the digits after it are zeros, and a fraction
that is not zero is a fault rather than a truncation.

**A re-spelling owes a witness only when it is lossy.** A whole spelling cannot see a site that
dropped its point, both spellings of one whole number rendering alike, so ``spelling_fault``
requires an entry that spells whole to hold the written form somewhere too, which is where that
drift is caught. A lowered one renders two answers as two words, so a site that flipped always
moves the needle and there is nothing left for a second reading to hold. ``Spelling.lossy`` is
which of the two a spelling is, and it is the question this rule turns on rather than whether the
mention re-spells at all.

**How a set of readings must then stand is `readings.py`.** That half left this file when the
boolean and the signed integer brought it to the cap, on the seam the first paragraph here had
been drawing all along.
"""

import re
from typing import NamedTuple

from couplings import PLACEHOLDER, Constant, Spelling

# The only comment marker a declaration's right-hand side may carry. Rust and TypeScript need
# none: their value is captured up to the terminating semicolon, so a trailing `//` never
# arrives here.
COMMENT_MARKER = "#"

# A product of integer literals, which may open with a minus. The sign is the whole expression's
# and never a factor's, since `2 * -3` is arithmetic nobody writes down here, and a leading `+` is
# refused with everything else this reducer will not guess at: `str(1)` is `1`, so a mention would
# render a needle the site's own `+1` does not spell.
INTEGER_PRODUCT = re.compile(r"^-?\d[\d_]*(?:\s*\*\s*\d[\d_]*)*$")

# The two words a boolean may be declared with, and the whole of that form. They are Python's own
# casing because Python declares every registered boolean; another language's are reached by
# `Spelling.LOWERED` at a mention rather than accepted at a site.
BOOLEANS = ("True", "False")

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


class Truth(NamedTuple):
    """A boolean literal, held as the word it is written with rather than as a truth value.

    Its own type for the reason ``Digits`` is, and for one Python adds: a `bool` IS an `int` here,
    so a bare `False` would compare equal to a site declaring `0` and would be sorted by an
    ordering that has no business over an answer with two values.
    """

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
    """A number with no fractional part, for a far side whose syntax carries none.

    An integer is already whole. A decimal gives up the digits behind its point when they are
    zeros, and is refused when they are not: `8.5` is a number docker's size suffix cannot spell,
    and truncating it here would tie that far side to `8` while the site went on declaring `8.5`,
    which is the drift this scan exists to report rather than to create.
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
    both languages hold. Folding a string would tie two literals differing in case alone, which is
    a comparison nobody wrote down, and folding a number changes nothing at all.
    """
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
    """The complaint about a lossy re-spelling with no faithful reading beside it, or None.

    A whole spelling is deliberately blind to a spelling change that leaves the number alone: `8`
    and `8.0` are one whole number, so the needle it renders is the same either way. That is the
    whole point of that second spelling and it must not become the entry's only reading, or a site
    that dropped its point would go unreported. So an entry that spells lossily has to carry a
    faithful reading as well, in a second site the sites compare textually against, or in a mention
    that renders the value in a spelling two declared values cannot share.
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
