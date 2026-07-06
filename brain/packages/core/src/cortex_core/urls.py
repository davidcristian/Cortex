"""The URL grammar and identity behind the output guardrail's laundering defense (ADR-0015)."""

import re
import unicodedata
from urllib.parse import unquote

_AUTHORITY_WORDS = ("https", "http", "hxxps", "hxxp", "ftp")
_OPAQUE_WORDS = ("mailto", "tel")

_AUTHORITY_SEPS = ("://", "[://]", "[:]//")
_OPAQUE_SEPS = (":", "[:]")

# A defanged dot inside the host/path: `[.]`, `(.)`, `{.}`, `[dot]`, `(dot)`, `{dot}` (any case).
# Recognized only *inside* a scheme'd URL, so a bare `evil[.]com` in prose still never matches.
_DEFANG_DOT = r"[\[({](?:\.|dot)[\])}]"

# A character that may belong to a URL body: anything but whitespace and the usual prose/markup
# closers (which also bound a Markdown `(url)`/`[url]`). A defanged dot is matched atomically ahead
# of this, so its closing bracket does not end the match early.
_URL_CHAR = r"[^\s<>\"'\)\]\}]"


def _family(words: tuple[str, ...], seps: tuple[str, ...]) -> str:
    """A regex alternation matching any of ``words`` followed by any of ``seps`` (regex-escaped)."""
    return rf"(?:{'|'.join(words)})(?:{'|'.join(re.escape(sep) for sep in seps)})"


# A clickable link, plain or defanged, anchored at a word boundary (so `sftp://` / `hotel:` are not
# partial-matched) and matched liberally to the first character that cannot belong to one. Defanged,
# percent-encoded, and fullwidth forms are reduced to a canonical identity by `normalize_url`.
URL_RE = re.compile(
    rf"\b(?:{_family(_AUTHORITY_WORDS, _AUTHORITY_SEPS)}|{_family(_OPAQUE_WORDS, _OPAQUE_SEPS)})"
    rf"(?:{_DEFANG_DOT}|{_URL_CHAR})+",
    re.IGNORECASE,
)

# Every plain/defanged scheme opening, derived from the same families as `URL_RE`. The streaming
# hold-back carries a trailing prefix of any of these so a scheme split across deltas is not leaked
# (`held_from`). Sharing the table with the matcher makes drift structurally impossible.
_SCHEME_PREFIXES = tuple(w + s for w in _AUTHORITY_WORDS for s in _AUTHORITY_SEPS) + tuple(
    w + s for w in _OPAQUE_WORDS for s in _OPAQUE_SEPS
)

# The longest string that is a prefix of a scheme+separator but not yet a URL match
# ("https://" needs one more character to match URL_RE). It is the stream filter's hold-back bound.
_LONGEST_OPEN_PREFIX = max(len(prefix) for prefix in _SCHEME_PREFIXES)

# Prose punctuation a URL match may drag along at its end is part of the sentence, never of the URL
# identity, and preserved outside a redaction.
TRAILING_PUNCTUATION = ".,;:!?"

# Ends the authority (host[:port]) component: from here on a URL is case-sensitive.
_AUTHORITY_END = re.compile(r"[/?#]")

# Defanged-token substitutions applied before identity comparison (`_refang`): each maps a defanged
# token back to the character it hides. `hxx` is rewritten only at the scheme (anchored), never
# inside a host/path; the separator and dot forms are unambiguous wherever they appear.
_REFANG_SUBS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\Ahxx", re.IGNORECASE), "htt"),
    (re.compile(r"\[://\]"), "://"),
    (re.compile(r"\[:\]"), ":"),
    (re.compile(_DEFANG_DOT, re.IGNORECASE), "."),
)


def _refang(url: str) -> str:
    """Rewrite a URL's defanged tokens (`hxxp`, `[.]`, `[://]`, …) to their plain characters."""
    for pattern, repl in _REFANG_SUBS:
        url = pattern.sub(repl, url)
    return url


def normalize_url(url: str) -> str:
    """One URL's identity: defang refanged, percent-decoded, NFKC-folded, trailing prose
    punctuation dropped, scheme+authority lowercased.
    """
    trimmed = unicodedata.normalize("NFKC", unquote(_refang(url))).rstrip(TRAILING_PUNCTUATION)
    head, sep, tail = trimmed.partition("://")
    cut = _AUTHORITY_END.search(tail)
    if cut is None:
        return f"{head.lower()}{sep}{tail.lower()}"
    return f"{head.lower()}{sep}{tail[: cut.start()].lower()}{tail[cut.start() :]}"


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
    lower = buf.lower()
    for size in range(min(len(buf), _LONGEST_OPEN_PREFIX), 0, -1):
        suffix = lower[-size:]
        if any(prefix.startswith(suffix) for prefix in _SCHEME_PREFIXES):
            return len(buf) - size
    return len(buf)
