"""The URL *grammar* behind the output guardrail's laundering defense (ADR-0015)."""

import re

from cortex_core.url_identity import normalize_url

_AUTHORITY_WORDS = ("https", "http", "hxxps", "hxxp", "ftp")
_OPAQUE_WORDS = ("mailto", "tel")

_BRACKETS = (("[", "]"), ("(", ")"), ("{", "}"))

_COLONS = (":", "\uff1a")
_SOLIDI = ("/", "\uff0f")

# The HTML name of each separator character, for the named reference (`&colon;`, `&sol;`).
_ENTITY_NAMES = {":": "colon", "/": "sol"}


def _entity_forms(char: str) -> tuple[str, ...]:
    """Every HTML character reference *one rendering pass* resolves to ``char`` (regex fragments).
    """
    point = ord(char)
    return (
        rf"&#0*{point}(?:;|(?![0-9]))",
        rf"&#x0*{point:x}(?:;|(?![0-9a-f]))",
        rf"(?-i:&{_ENTITY_NAMES[char]};)",
    )


def _spellings(plain: tuple[str, ...]) -> str:
    """One separator character's alternation: its plain glyphs, then its entity references."""
    return f"(?:{'|'.join((*(re.escape(g) for g in plain), *_entity_forms(plain[0])))})"


_COLON_SPELLING = _spellings(_COLONS)
_SOLIDUS_SPELLING = _spellings(_SOLIDI)

# The *defanged* separators, the one family that is a bracketed token rather than a respelling of
# the character. Held apart from the plain forms because the matcher composes the plain ones out of
# the per-character alternations above while the streaming hold-back needs them all as literal text.
_DEFANGED_AUTHORITY_SEPS = tuple(
    f"{lo}{tok}{hi}{tail}" for lo, hi in _BRACKETS for tok, tail in (("://", ""), (":", "//"))
)
_DEFANGED_OPAQUE_SEPS = tuple(f"{lo}:{hi}" for lo, hi in _BRACKETS)

# Every separator spelling as *literal text*, for the streaming hold-back's scheme prefixes below.
# The entity forms are variable-length and so cannot be enumerated here, exactly as the encoded
# bracket chunk could not; `_OPEN_SEP_RE` carries both instead.
_AUTHORITY_SEPS = (
    *(f"{colon}{first}{second}" for colon in _COLONS for first in _SOLIDI for second in _SOLIDI),
    *_DEFANGED_AUTHORITY_SEPS,
)
_OPAQUE_SEPS = (*_COLONS, *_DEFANGED_OPAQUE_SEPS)

# The matcher's separator, per scheme family: any spelling of the colon (and, for an authority
# scheme, of both solidi), or one of the defang tokens. Composing the per-character alternations is
# what makes every mixture free, an entity colon in front of fullwidth solidi included.
_AUTHORITY_SEP_RE = "|".join(
    (
        rf"{_COLON_SPELLING}{_SOLIDUS_SPELLING}{{2}}",
        *(re.escape(s) for s in _DEFANGED_AUTHORITY_SEPS),
    )
)
_OPAQUE_SEP_RE = "|".join((_COLON_SPELLING, *(re.escape(s) for s in _DEFANGED_OPAQUE_SEPS)))

# The bracket vocabulary, shared by every bracketed token below so they cannot drift. The inner run
# excludes whitespace, prose/markup quoting, and every bracket, so a chunk cannot swallow a second
# one and the matcher stays linear (a closer-less run fails and backtracks linearly).
_OPEN_BRACKET = r"[\[({]"
_CLOSE_BRACKET = r"[\])}]"
_CHUNK_INNER = r"[^\s<>\"'\[\](){}]"

_DEFANG_CHUNK = rf"{_OPEN_BRACKET}{_CHUNK_INNER}+{_CLOSE_BRACKET}"

_ENCODED_SEP_CHUNK = rf"{_OPEN_BRACKET}{_CHUNK_INNER}*[&%]{_CHUNK_INNER}*{_CLOSE_BRACKET}"

# A character that may belong to a URL body: anything but whitespace and the usual prose/markup
# closers (which also bound a Markdown `(url)`/`[url]`). A bracket `_DEFANG_CHUNK` is matched
# atomically ahead of this, so a defang token's closing bracket does not end the match early.
_URL_CHAR = r"[^\s<>\"'\)\]\}]"


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
    tuple(w + s for w in _AUTHORITY_WORDS for s in _AUTHORITY_SEPS)
    + tuple(w + s for w in _OPAQUE_WORDS for s in _OPAQUE_SEPS)
    + tuple("data" + s for s in _OPAQUE_SEPS)
)

# The longest string that is a prefix of a scheme+separator but not yet a URL match
# ("https://" needs one more character to match URL_RE). It is the stream filter's hold-back bound.
_LONGEST_OPEN_PREFIX = max(len(prefix) for prefix in _SCHEME_PREFIXES)

_UNFINISHED_ENTITY = r"&[#0-9a-z]*"

_OPEN_SEP_RE = re.compile(
    rf"\b(?:{'|'.join(_SCHEME_WORDS)})"
    rf"(?:{_OPEN_BRACKET}{_CHUNK_INNER}*"
    rf"|(?:{_COLON_SPELLING}|{_SOLIDUS_SPELLING})*(?:{_UNFINISHED_ENTITY})?)\Z",
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
