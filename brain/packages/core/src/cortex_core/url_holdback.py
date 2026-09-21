r"""What may still be growing into a URL at a buffer's end, behind the output guardrail."""

import re

from cortex_core.url_identity import DOT_WORD
from cortex_core.url_removals import REMOVED, REMOVED_RUN, permeable, strip_removed
from cortex_core.url_separators import (
    AUTHORITY_SEPS,
    CHUNK_INNER,
    CLOSE_BRACKET,
    COLON_SPELLING,
    DOT_TOKENS,
    GAP_WHITESPACE,
    OPAQUE_SEPS,
    OPEN_BRACKET,
    SOLIDUS_SPELLING,
)
from cortex_core.urls import (
    ARRIVING_AUTHORITY,
    AUTHORITY_WORDS,
    HOST_CHAR,
    OPAQUE_SEP_RE,
    OPAQUE_WORDS,
    SPLIT_GAP,
    SPLIT_LABEL,
    URL_RE,
)

_SCHEME_WORDS = AUTHORITY_WORDS + OPAQUE_WORDS + ("data",)

_SCHEME_PREFIXES = (
    tuple(w + s for w in AUTHORITY_WORDS for s in AUTHORITY_SEPS)
    + tuple(w + s for w in OPAQUE_WORDS for s in OPAQUE_SEPS)
    + tuple("data" + s for s in OPAQUE_SEPS)
)

_LONGEST_OPEN_PREFIX = max(len(prefix) for prefix in _SCHEME_PREFIXES)

_UNFINISHED_ENTITY = r"&[#0-9a-z]*"

_OPEN_SEP_RE = re.compile(
    rf"\b(?:{'|'.join(permeable(word) for word in _SCHEME_WORDS)}){REMOVED_RUN}"
    rf"(?:{OPEN_BRACKET}{CHUNK_INNER}*"
    rf"|(?:{OPAQUE_SEP_RE}){SOLIDUS_SPELLING}?{HOST_CHAR}*"
    rf"|(?:{COLON_SPELLING}|{SOLIDUS_SPELLING})*(?:{_UNFINISHED_ENTITY})?)\Z",
    re.IGNORECASE,
)


def _prefixes(token: str) -> str:
    """Every prefix of ``token``, the empty one and the whole included, as one regex fragment."""
    return "".join(f"(?:{re.escape(char)}{REMOVED_RUN}" for char in token) + ")?" * len(token)


_ARRIVING_GAP = (
    rf"{GAP_WHITESPACE}+(?:{'|'.join(_prefixes(token) for token in DOT_TOKENS)}"
    rf"|{_UNFINISHED_ENTITY}|{OPEN_BRACKET}(?:{_prefixes(DOT_WORD)}|\.)?{CLOSE_BRACKET}?)"
    rf"{GAP_WHITESPACE}*"
)

# A whitespace-split host still arriving at the buffer's end (`hxxp://evil `, `... evil dot `).
# The labels so far must be dotless, because only a dotless host can still grow a gap, which is
# what keeps this off an ordinary link followed by a space.
_ARRIVING_SPLIT_HOST = re.compile(
    rf"\b{ARRIVING_AUTHORITY}{SPLIT_LABEL}(?:{SPLIT_GAP})*{_ARRIVING_GAP}\Z", re.IGNORECASE
)


def held_from(buf: str) -> int:
    """The index from which ``buf`` may still be growing a URL; everything before it is final."""
    last = None
    for match in URL_RE.finditer(buf):
        last = match
    if last is not None and last.end() == len(buf):
        return last.start()
    open_gap = _ARRIVING_SPLIT_HOST.search(buf)
    if open_gap is not None:
        return open_gap.start()
    open_sep = _OPEN_SEP_RE.search(buf)
    if open_sep is not None:
        return open_sep.start()
    open_prefix = _open_prefix(buf)
    return len(buf) if open_prefix is None else open_prefix


def _open_prefix(buf: str) -> int | None:
    """Where the longest suffix of ``buf`` that is a prefix of a scheme opening starts, or None."""
    # The window is counted in the characters that survive the removal drop, because a URL parser
    # drops them before it reads the scheme: `ht<TAB>t` is the same three characters of `http://`
    # as `htt`, and a run of tabs must not push the opening out of reach of the scan.
    size = seen = 0
    while size < len(buf) and seen < _LONGEST_OPEN_PREFIX:
        size += 1
        seen += buf[-size] not in REMOVED
    lower = buf.lower()
    for length in range(size, 0, -1):
        suffix = strip_removed(lower[-length:])
        if suffix and any(prefix.startswith(suffix) for prefix in _SCHEME_PREFIXES):
            return len(buf) - length
    return None
