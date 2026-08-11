r"""Every way one URL *separator character* may be spelled, behind the output guardrail (ADR-0015).

Split from ``urls.py`` (which owns the grammar these are composed into) at the line cap as the
eleventh addendum landed, the second such split after ``url_identity``. This module answers one
question: given a character a URL's punctuation is made of, what must the matcher accept in its
place? Three families stack, each landed by its own addendum and each **generated from a table
rather than listed**, so a mixed spelling cannot be the one nobody remembered:

1. The **glyph** and its twins: the fullwidth colon and solidus NFKC folds to ASCII (U+FF1A,
   U+FF0F), and the **backslash**, which a URL parser reads as a solidus inside a special scheme's
   authority and path alike; ADR-0015 eighth + tenth addenda.
2. An **HTML character reference** to any glyph HTML names (``&#58;``, ``&#x3a;``, ``&colon;``,
   zero-padded or semicolon-less), admitted because one rendering pass resolves it; ADR-0015 ninth
   addendum.
3. A **defanged** token, the one family that is a bracketed word rather than a respelling of the
   character (``[://]``, ``[:]``), in every bracket shape; ADR-0015 seventh addendum.

The dot joins the colon and the solidus here because the eleventh addendum's host anchor needs one:
a slashless authority is admitted only behind a host, and a host is a name whose labels a dot of
any of these readings separates. Spellings are held both as regex fragments (which the matcher
composes) and, where they are enumerable, as literal text (which the streaming hold-back
concatenates), so the two derive from one table and cannot drift. Pure state- and I/O-free.
"""

import re

from cortex_core.url_identity import LABEL_SEPARATORS

# The bracket vocabulary, shared by every bracketed token here and by the chunks `urls.py` builds
# from it, so the two cannot drift. The inner run excludes whitespace, prose/markup quoting, and
# every bracket, so a chunk cannot swallow a second one and the matcher stays linear (a closer-less
# run fails and backtracks linearly).
OPEN_BRACKET = r"[\[({]"
CLOSE_BRACKET = r"[\])}]"
CHUNK_INNER = r"[^\s<>\"'\[\](){}]"

# Every defang bracket shape is enumerated, not just `[...]`: the refanger always folded `(.)`/`{.}`
# as readily as `[.]`, but the separator tables listed only the square form, so `http(://)evil.com`
# and `http{://}evil.com` anchored *nothing* and were never matched at all. That asymmetry was a
# standing bypass in its own right, found while widening this position (ADR-0015 seventh addendum).
_BRACKETS = (("[", "]"), ("(", ")"), ("{", "}"))

# The colon and solidus a plain separator is built from, each in its ASCII form and its fullwidth
# twin (U+FF1A, U+FF0F), written as `\u` escapes so the source stays ASCII (the `_CONFUSABLES`
# convention). NFKC already folds both to ASCII in the *identity*, but the matcher runs before any
# normalization, so a fullwidth-separated URL anchored nothing, matched nothing, and was therefore
# redacted by neither mode (ADR-0015 eighth addendum). Every combination is generated from the two
# tables rather than listed, the `_BRACKETS` precedent, so a mixed spelling (an ASCII colon with a
# fullwidth solidus) cannot be the one nobody remembered.
#
# The **backslash** is a solidus here because a URL parser reads it as one: the URL Standard skips
# `/` and `\` alike in a special scheme's authority, so `https:\/\/evil.example` (the JSON-escaped
# spelling of a link, and the shape a regex literal writes) is not a rendering of the link but the
# link, which `_fold_special_slashes` folds on the identity side. It anchored nothing before, so
# both policies were blind to it (ADR-0015 tenth addendum). Its fullwidth twin U+FF3C stays out,
# measured: a parser refuses it, so unlike U+FF0F it has no reading to inherit.
#
# An ASCII form comes first in each table: those are the characters the entity references below
# spell, one per HTML name.
_COLONS = (":", "\uff1a")
_SOLIDI = ("/", "\\", "\uff0f")

# The dot's table is `LABEL_SEPARATORS`, the stops IDNA itself splits a host on, imported from the
# module whose fold reads them so the grammar and the identity cannot disagree about what a dot is.
# It is also the one position where a **percent** escape is a spelling, measured rather than
# assumed: a URL parser percent-decodes a *host*, so `https:evil%2eexample/pay` resolves to the
# plain link, while it refuses the stacked `%252e`, so exactly one level is a reading and no more.
# The colon and solidus positions still decline that family on the measurement that put them out,
# a parser throwing on `https%3A//evil.example`; the difference is that decoding a host happens
# inside a string already recognized as a URL, which is precisely what a separator's does not.
_DOTS = (*LABEL_SEPARATORS, "%2e")

# The HTML name of each separator character, for the named reference (`&colon;`, `&sol;`, `&bsol;`,
# `&period;`). Membership is also what says which characters carry references at all: HTML names
# exactly the ASCII ones, and a fullwidth or ideographic twin is reached through NFKC and the label
# fold in the identity rather than by spelling.
_ENTITY_NAMES = {":": "colon", "/": "sol", "\\": "bsol", ".": "period"}


def _entity_forms(char: str) -> tuple[str, ...]:
    """Every HTML character reference *one rendering pass* resolves to ``char`` (regex fragments).

    Generated from the codepoint rather than listed, so the whole family lands at once: decimal
    and hexadecimal, each with any leading zeros (``&#0058;``, ``&#x003a;``), each with the
    semicolon HTML makes optional, plus the named form (ADR-0015 ninth addendum). ``URL_RE`` is
    ``IGNORECASE``, which covers ``&#X3A;`` and the hex digits' case for free; the *named* form is
    case-sensitive to HTML, so it is scoped back to case-sensitive here and ``&COLON;`` (which
    ``html.unescape`` leaves standing, as no renderer resolves it) is not admitted. A semicolon-less
    reference ends the digit run, since ``&#58123`` is one five-digit reference and not a colon,
    which keeps the anchor's promise that every spelling it admits is one the identity folds.

    The semicolon-less branch refuses a following ``;`` as well as a following digit, and that
    second refusal is what stops one semicolon being spent twice. A ``;`` after the digits always
    terminates the reference, so the two readings are never both available to HTML; leaving both
    available to the regex let ``data&#58;the results`` backtrack into reading ``&#58`` as the
    separator and hand the ``;`` to ``_DATA_ANCHOR``'s ``[;,]``, redacting prose that the plain
    ``data:the results`` spelling is admitted nowhere near.
    """
    point = ord(char)
    return (
        rf"&#0*{point}(?:;|(?![0-9;]))",
        rf"&#x0*{point:x}(?:;|(?![0-9a-f;]))",
        rf"(?-i:&{_ENTITY_NAMES[char]};)",
    )


def _spellings(plain: tuple[str, ...]) -> str:
    """One separator position's alternation: its plain glyphs, then their entity references.

    References are generated for every glyph HTML names (the ASCII ones), not only the first, so
    the solidus position carries ``&bsol;`` and ``&#92;`` beside ``&sol;`` and ``&#47;``: one
    rendering pass turns those into a backslash, which a URL parser then reads as a solidus.
    """
    forms = tuple(f for g in plain if g in _ENTITY_NAMES for f in _entity_forms(g))
    return f"(?:{'|'.join((*(re.escape(g) for g in plain), *forms))})"


COLON_SPELLING = _spellings(_COLONS)
SOLIDUS_SPELLING = _spellings(_SOLIDI)
DOT_SPELLING = _spellings(_DOTS)

# The *defanged* separators, the one family that is a bracketed token rather than a respelling of
# the character. Held apart from the plain forms because the matcher composes the plain ones out of
# the per-character alternations above while the streaming hold-back needs them all as literal text.
DEFANGED_AUTHORITY_SEPS = tuple(
    f"{lo}{tok}{hi}{tail}" for lo, hi in _BRACKETS for tok, tail in (("://", ""), (":", "//"))
)
DEFANGED_OPAQUE_SEPS = tuple(f"{lo}:{hi}" for lo, hi in _BRACKETS)

# Every separator spelling as *literal text*, for the streaming hold-back's scheme prefixes. The
# entity forms are variable-length and so cannot be enumerated here, exactly as the encoded bracket
# chunk could not; `urls.py`'s `_OPEN_SEP_RE` carries both instead. The slashless authority the
# eleventh addendum admits needs no entry: its spellings are already prefixes of these.
AUTHORITY_SEPS = (
    *(f"{colon}{first}{second}" for colon in _COLONS for first in _SOLIDI for second in _SOLIDI),
    *DEFANGED_AUTHORITY_SEPS,
)
OPAQUE_SEPS = (*_COLONS, *DEFANGED_OPAQUE_SEPS)
