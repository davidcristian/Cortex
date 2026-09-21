r"""Every way one URL separator character may be written, behind the output guardrail."""

import re

from cortex_core.url_identity import DEFANG_DOT, DOT_WORD, LABEL_SEPARATORS
from cortex_core.url_removals import REMOVED_CHARS, permeable

OPEN_BRACKET = r"[\[({]"
CLOSE_BRACKET = r"[\])}]"
CHUNK_INNER = rf"(?:[^\s<>\"'\[\](){{}}]|{REMOVED_CHARS})"

_BRACKETS = (("[", "]"), ("(", ")"), ("{", "}"))

_COLONS = (":", "\uff1a")
_SOLIDI = ("/", "\\", "\uff0f")

_DOTS = (*LABEL_SEPARATORS, "%2e")

_ENTITY_NAMES = {":": "colon", "/": "sol", "\\": "bsol", ".": "period"}


def _entity_forms(char: str) -> tuple[str, ...]:
    """Every HTML character reference one rendering pass resolves to ``char`` (regex fragments)."""
    point = ord(char)
    # The semicolon-less branches refuse a following `;` as well as a following digit. HTML
    # always ends a reference at the `;`, so admitting both readings let `data&#58;the results`
    # match `&#58` and hand the `;` to the data anchor, redacting ordinary prose.
    return (
        rf"&#0*{point}(?:;|(?![0-9;]))",
        rf"&#x0*{point:x}(?:;|(?![0-9a-f;]))",
        rf"(?-i:&{_ENTITY_NAMES[char]};)",
    )


def _separator_forms(plain: tuple[str, ...]) -> str:
    """One separator position's alternation: its plain glyphs, then their entity references."""
    forms = tuple(f for g in plain if g in _ENTITY_NAMES for f in _entity_forms(g))
    return f"(?:{'|'.join((*(re.escape(g) for g in plain), *forms))})"


COLON_FORMS = _separator_forms(_COLONS)
SOLIDUS_FORMS = _separator_forms(_SOLIDI)
DOT_FORMS = _separator_forms(_DOTS)

# Every character NFKC folds to a space, so a host split by a no-break, thin or ideographic
# space reads exactly like one split by a plain space. A test regenerates this from the Unicode
# database, so a later version adding one fails there instead of opening a way through.
NFKC_SPACES = (
    "\u00a0\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u202f\u205f\u3000"
)
GAP_WHITESPACE = rf"[ \t{NFKC_SPACES}]"

SPACED_DOT = (
    rf"{GAP_WHITESPACE}+(?:{permeable(DOT_WORD)}|{DOT_FORMS}|{DEFANG_DOT}){GAP_WHITESPACE}+"
)

DOT_TOKENS = (DOT_WORD, *_DOTS)

DEFANGED_AUTHORITY_SEPS = tuple(
    f"{lo}{tok}{hi}{tail}" for lo, hi in _BRACKETS for tok, tail in (("://", ""), (":", "//"))
)
DEFANGED_OPAQUE_SEPS = tuple(f"{lo}:{hi}" for lo, hi in _BRACKETS)

AUTHORITY_SEPS = (
    *(f"{colon}{first}{second}" for colon in _COLONS for first in _SOLIDI for second in _SOLIDI),
    *DEFANGED_AUTHORITY_SEPS,
)
OPAQUE_SEPS = (*_COLONS, *DEFANGED_OPAQUE_SEPS)
