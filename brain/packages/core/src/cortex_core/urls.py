r"""The URL *grammar* behind the output guardrail's laundering defense (ADR-0015)."""

import re

from cortex_core.url_identity import SPECIAL_SCHEMES, normalize_url
from cortex_core.url_spellings import (
    AUTHORITY_SEPS,
    CHUNK_INNER,
    CLOSE_BRACKET,
    COLON_SPELLING,
    DEFANGED_AUTHORITY_SEPS,
    DEFANGED_OPAQUE_SEPS,
    DOT_SPELLING,
    OPAQUE_SEPS,
    OPEN_BRACKET,
    SOLIDUS_SPELLING,
)

_AUTHORITY_WORDS = (*SPECIAL_SCHEMES, "hxxps", "hxxp")
_OPAQUE_WORDS = ("mailto", "tel")

_NON_URL = r"\s<>\"'\)\]\}"

# A character that may belong to a URL body. A bracket `_DEFANG_CHUNK` is matched atomically ahead
# of this, so a defang token's closing bracket does not end the match early.
_URL_CHAR = rf"[^{_NON_URL}]"

# A character that may belong to an *authority*: a body character that is not one of the three
# delimiters ending it, the backslash included since a special scheme's parser reads that as one.
_HOST_CHAR = rf"[^{_NON_URL}/?#\\]"

_HOST_ANCHOR = rf"(?={_HOST_CHAR}*{DOT_SPELLING}{_HOST_CHAR}|\[{CHUNK_INNER}*:{CHUNK_INNER}*\])"

_OPAQUE_SEP_RE = "|".join((COLON_SPELLING, *(re.escape(s) for s in DEFANGED_OPAQUE_SEPS)))
_AUTHORITY_SEP_RE = "|".join(
    (
        rf"{COLON_SPELLING}{SOLIDUS_SPELLING}{{2}}",
        *(re.escape(s) for s in DEFANGED_AUTHORITY_SEPS),
        rf"(?:{_OPAQUE_SEP_RE}){SOLIDUS_SPELLING}?{_HOST_ANCHOR}",
    )
)

_DEFANG_CHUNK = rf"{OPEN_BRACKET}{CHUNK_INNER}+{CLOSE_BRACKET}"

_ENCODED_SEP_CHUNK = rf"{OPEN_BRACKET}{CHUNK_INNER}*[&%]{CHUNK_INNER}*{CLOSE_BRACKET}"


def _family(words: tuple[str, ...], seps: str) -> str:
    """A regex alternation: any of ``words``, then that family's ``seps`` or an encoded chunk."""
    return rf"(?:{'|'.join(words)})(?:{seps}|{_ENCODED_SEP_CHUNK})"


_DATA_ANCHOR = r"(?=[\w.+-]+/|[;,])"
_DATA_SCHEME = rf"{_family(('data',), _OPAQUE_SEP_RE)}{_DATA_ANCHOR}"


# A clickable link, plain or defanged, anchored at a word boundary (so `sftp://` / `hotel:` are not
# partial-matched) and matched liberally to the first character that cannot belong to one. Defanged,
# encoded, and fullwidth forms are reduced to a canonical identity by `normalize_url`.
URL_RE = re.compile(
    rf"\b(?:{_family(_AUTHORITY_WORDS, _AUTHORITY_SEP_RE)}|{_family(_OPAQUE_WORDS, _OPAQUE_SEP_RE)}"
    rf"|{_DATA_SCHEME})"
    rf"(?:{_DEFANG_CHUNK}|{_URL_CHAR})+",
    re.IGNORECASE,
)

# Every scheme word, for the hold-back's open-chunk check below. Derived from the same tables as
# `URL_RE`, so the two cannot drift.
_SCHEME_WORDS = _AUTHORITY_WORDS + _OPAQUE_WORDS + ("data",)

_SCHEME_PREFIXES = (
    tuple(w + s for w in _AUTHORITY_WORDS for s in AUTHORITY_SEPS)
    + tuple(w + s for w in _OPAQUE_WORDS for s in OPAQUE_SEPS)
    + tuple("data" + s for s in OPAQUE_SEPS)
)

# The longest string that is a prefix of a scheme+separator but not yet a URL match
# ("https://" needs one more character to match URL_RE). It is the stream filter's hold-back bound.
_LONGEST_OPEN_PREFIX = max(len(prefix) for prefix in _SCHEME_PREFIXES)

_UNFINISHED_ENTITY = r"&[#0-9a-z]*"

_OPEN_SEP_RE = re.compile(
    rf"\b(?:{'|'.join(_SCHEME_WORDS)})"
    rf"(?:{OPEN_BRACKET}{CHUNK_INNER}*"
    rf"|(?:{_OPAQUE_SEP_RE}){SOLIDUS_SPELLING}?{_HOST_CHAR}*"
    rf"|(?:{COLON_SPELLING}|{SOLIDUS_SPELLING})*(?:{_UNFINISHED_ENTITY})?)\Z",
    re.IGNORECASE,
)


def extract_urls(text: str) -> frozenset[str]:
    """Every clickable URL in ``text`` (any listed scheme), normalized for identity comparison."""
    return frozenset(normalize_url(match.group()) for match in URL_RE.finditer(text))


def held_from(buf: str) -> int:
    """The index from which ``buf`` may still be growing a URL. Everything before is final."""
    last = None
    for match in URL_RE.finditer(buf):
        last = match
    if last is not None and last.end() == len(buf):
        return last.start()
    open_sep = _OPEN_SEP_RE.search(buf)
    if open_sep is not None:
        return open_sep.start()
    lower = buf.lower()
    for size in range(min(len(buf), _LONGEST_OPEN_PREFIX), 0, -1):
        suffix = lower[-size:]
        if any(prefix.startswith(suffix) for prefix in _SCHEME_PREFIXES):
            return len(buf) - size
    return len(buf)
