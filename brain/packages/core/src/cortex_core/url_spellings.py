r"""Every way one URL *separator character* may be spelled, behind the output guardrail (ADR-0015).
"""

import re

from cortex_core.url_identity import LABEL_SEPARATORS

OPEN_BRACKET = r"[\[({]"
CLOSE_BRACKET = r"[\])}]"
CHUNK_INNER = r"[^\s<>\"'\[\](){}]"

_BRACKETS = (("[", "]"), ("(", ")"), ("{", "}"))

_COLONS = (":", "\uff1a")
_SOLIDI = ("/", "\\", "\uff0f")

_DOTS = (*LABEL_SEPARATORS, "%2e")

_ENTITY_NAMES = {":": "colon", "/": "sol", "\\": "bsol", ".": "period"}


def _entity_forms(char: str) -> tuple[str, ...]:
    """Every HTML character reference *one rendering pass* resolves to ``char`` (regex fragments).
    """
    point = ord(char)
    return (
        rf"&#0*{point}(?:;|(?![0-9;]))",
        rf"&#x0*{point:x}(?:;|(?![0-9a-f;]))",
        rf"(?-i:&{_ENTITY_NAMES[char]};)",
    )


def _spellings(plain: tuple[str, ...]) -> str:
    """One separator position's alternation: its plain glyphs, then their entity references."""
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

AUTHORITY_SEPS = (
    *(f"{colon}{first}{second}" for colon in _COLONS for first in _SOLIDI for second in _SOLIDI),
    *DEFANGED_AUTHORITY_SEPS,
)
OPAQUE_SEPS = (*_COLONS, *DEFANGED_OPAQUE_SEPS)
