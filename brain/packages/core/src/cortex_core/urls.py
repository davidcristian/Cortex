r"""The URL *grammar* behind the output guardrail's laundering defense (ADR-0015)."""

import re

from cortex_core.url_identity import MAILTO_SCHEME, SPECIAL_SCHEMES, normalize_url
from cortex_core.url_removals import REMOVED_CHARS
from cortex_core.url_spellings import (
    CHUNK_INNER,
    CLOSE_BRACKET,
    COLON_SPELLING,
    DEFANGED_AUTHORITY_SEPS,
    DEFANGED_OPAQUE_SEPS,
    DOT_SPELLING,
    GAP_WHITESPACE,
    OPEN_BRACKET,
    SOLIDUS_SPELLING,
    SPACED_DOT,
)

AUTHORITY_WORDS = (*SPECIAL_SCHEMES, "hxxps", "hxxp")
OPAQUE_WORDS = (MAILTO_SCHEME, "tel")

_NON_URL = r"\s<>\"'\)\]\}"

_URL_CHAR = rf"(?:[^{_NON_URL}]|{REMOVED_CHARS})"

# A character that may belong to an *authority*: a body character that is not one of the three
# delimiters ending it, the backslash included since a special scheme's parser reads that as one.
HOST_CHAR = rf"[^{_NON_URL}/?#\\]"

# A label of a **whitespace-split** host: body characters carrying no dot in any reading. The
# absence is the whole point of the rule below, so it is spelled here rather than assumed.
SPLIT_LABEL = rf"(?:(?!{DOT_SPELLING}){HOST_CHAR})+"

# One gap and the label it separates from the last, which is the unit the split host repeats and
# the unit the host anchor below reads one of to know it is looking at a host at all.
SPLIT_GAP = rf"{SPACED_DOT}{SPLIT_LABEL}"

_SPLIT_HOST = rf"{SPLIT_LABEL}(?:{SPLIT_GAP})+"

_HOST_ANCHOR = (
    rf"(?={HOST_CHAR}*{DOT_SPELLING}{HOST_CHAR}"
    rf"|\[{CHUNK_INNER}*:{CHUNK_INNER}*\]"
    rf"|{SPLIT_LABEL}{SPLIT_GAP})"
)

_ARRIVING_HOST_ANCHOR = rf"(?={SPLIT_LABEL}{GAP_WHITESPACE})"

OPAQUE_SEP_RE = "|".join((COLON_SPELLING, *(re.escape(s) for s in DEFANGED_OPAQUE_SEPS)))


def _authority_sep(anchor: str) -> str:
    """An authority scheme's separator alternation, with ``anchor`` behind its slashless branch."""
    return "|".join(
        (
            rf"{COLON_SPELLING}{SOLIDUS_SPELLING}{{2}}",
            *(re.escape(s) for s in DEFANGED_AUTHORITY_SEPS),
            rf"(?:{OPAQUE_SEP_RE}){SOLIDUS_SPELLING}?{anchor}",
        )
    )


_DEFANG_CHUNK = rf"{OPEN_BRACKET}{CHUNK_INNER}+{CLOSE_BRACKET}"

_ENCODED_SEP_CHUNK = rf"{OPEN_BRACKET}{CHUNK_INNER}*[&%]{CHUNK_INNER}*{CLOSE_BRACKET}"


def _family(words: tuple[str, ...], seps: str) -> str:
    """A regex alternation: any of ``words``, then that family's ``seps`` or an encoded chunk."""
    return rf"(?:{'|'.join(words)})(?:{seps}|{_ENCODED_SEP_CHUNK})"


_DATA_ANCHOR = r"(?=[\w.+-]+/|[;,])"
_DATA_SCHEME = rf"{_family(('data',), OPAQUE_SEP_RE)}{_DATA_ANCHOR}"


_AUTHORITY = _family(AUTHORITY_WORDS, _authority_sep(_HOST_ANCHOR))
ARRIVING_AUTHORITY = _family(AUTHORITY_WORDS, _authority_sep(_ARRIVING_HOST_ANCHOR))
_SCHEME = rf"(?:{_AUTHORITY}|{_family(OPAQUE_WORDS, OPAQUE_SEP_RE)}|{_DATA_SCHEME})"
_BODY = rf"(?:{_DEFANG_CHUNK}|{_URL_CHAR})+"

URL_RE = re.compile(rf"\b(?:{_AUTHORITY}{_SPLIT_HOST}(?:{_BODY})?|{_SCHEME}{_BODY})", re.IGNORECASE)


def extract_urls(text: str) -> frozenset[str]:
    """Every clickable URL in ``text`` (any listed scheme), normalized for identity comparison."""
    return frozenset(normalize_url(match.group()) for match in URL_RE.finditer(text))
