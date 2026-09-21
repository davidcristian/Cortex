r"""The URL grammar behind the output guardrail's laundering defense."""

import re

from cortex_core.url_identity import MAILTO_SCHEME, SPECIAL_SCHEMES, normalize_url
from cortex_core.url_removals import REMOVED_CHARS, REMOVED_RUN, permeable
from cortex_core.url_separators import (
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

HOST_CHAR = rf"[^{_NON_URL}/?#\\]"

SPLIT_LABEL = rf"(?:(?!{DOT_SPELLING}){HOST_CHAR})+"

SPLIT_GAP = rf"{SPACED_DOT}{SPLIT_LABEL}"

# A host whose labels are separated by whitespace instead of a dot (`evil dot com`). It is a
# branch of `URL_RE` rather than one more alternative inside `_BODY`, where the repeated group
# re-entered at every position and read `http://example.com dot the file` as one host.
_SPLIT_HOST = rf"{SPLIT_LABEL}(?:{SPLIT_GAP})+"

_HOST_ANCHOR = (
    rf"(?={HOST_CHAR}*{DOT_SPELLING}{HOST_CHAR}"
    rf"|\[{CHUNK_INNER}*:{CHUNK_INNER}*\]"
    rf"|{SPLIT_LABEL}{SPLIT_GAP})"
)

_ARRIVING_HOST_ANCHOR = rf"(?={SPLIT_LABEL}{GAP_WHITESPACE})"

OPAQUE_SEP_RE = "|".join((COLON_SPELLING, *(permeable(s) for s in DEFANGED_OPAQUE_SEPS)))


def _authority_sep(anchor: str) -> str:
    """An authority scheme's separator alternation, with ``anchor`` behind its slashless branch."""
    return "|".join(
        (
            rf"{COLON_SPELLING}{REMOVED_RUN}{SOLIDUS_SPELLING}{REMOVED_RUN}{SOLIDUS_SPELLING}",
            *(permeable(s) for s in DEFANGED_AUTHORITY_SEPS),
            rf"(?:{OPAQUE_SEP_RE}){REMOVED_RUN}(?:{SOLIDUS_SPELLING}{REMOVED_RUN})?{anchor}",
        )
    )


_DEFANG_CHUNK = rf"{OPEN_BRACKET}{CHUNK_INNER}+{CLOSE_BRACKET}"

# A bracketed chunk at the separator position (`http[&#58;//]evil.com`). Its inner run must
# include an escape marker: without that, ordinary prose such as `http(s)-only` matches and
# strict mode redacts it out of this repo's own documents.
_ENCODED_SEP_CHUNK = rf"{OPEN_BRACKET}{CHUNK_INNER}*[&%]{CHUNK_INNER}*{CLOSE_BRACKET}"


def _family(words: tuple[str, ...], seps: str) -> str:
    """A regex alternation: any of ``words``, then that family's ``seps`` or an encoded chunk."""
    return (
        rf"(?:{'|'.join(permeable(word) for word in words)})"
        rf"{REMOVED_RUN}(?:{seps}|{_ENCODED_SEP_CHUNK})"
    )


# `data:` is admitted only when a MIME-type shape or the `,`/`;` that begins the payload follows
# the colon, so prose such as `data:the results` stays out. The lookahead consumes nothing.
_DATA_ANCHOR = rf"(?=(?:[\w.+-]|{REMOVED_CHARS})+/|[;,])"
_DATA_SCHEME = rf"{_family(('data',), OPAQUE_SEP_RE)}{_DATA_ANCHOR}"


_AUTHORITY = _family(AUTHORITY_WORDS, _authority_sep(_HOST_ANCHOR))
ARRIVING_AUTHORITY = _family(AUTHORITY_WORDS, _authority_sep(_ARRIVING_HOST_ANCHOR))
_SCHEME = rf"(?:{_AUTHORITY}|{_family(OPAQUE_WORDS, OPAQUE_SEP_RE)}|{_DATA_SCHEME})"
_BODY = rf"(?:{_DEFANG_CHUNK}|{_URL_CHAR})+"

URL_RE = re.compile(rf"\b(?:{_AUTHORITY}{_SPLIT_HOST}(?:{_BODY})?|{_SCHEME}{_BODY})", re.IGNORECASE)


def extract_urls(text: str) -> frozenset[str]:
    """Every clickable URL in ``text`` (any listed scheme), normalized for identity comparison."""
    return frozenset(normalize_url(match.group()) for match in URL_RE.finditer(text))
