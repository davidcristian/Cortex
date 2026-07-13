"""The URL grammar and identity behind the output guardrail's laundering defense (ADR-0015)."""

import html
import re
import unicodedata
from urllib.parse import unquote

_AUTHORITY_WORDS = ("https", "http", "hxxps", "hxxp", "ftp")
_OPAQUE_WORDS = ("mailto", "tel")

_AUTHORITY_SEPS = ("://", "[://]", "[:]//")
_OPAQUE_SEPS = (":", "[:]")

# A defanged dot inside the host/path: `[.]`, `(.)`, `{.}`, `[dot]`, `(dot)`, `{dot}` (any case).
# The *refanger*'s token (`_REFANG_SUBS`), applied after `_decode_escapes`, so it needs only the
# literal form; the *matcher* uses the broader `_DEFANG_CHUNK` below. Recognized only in a URL.
_DEFANG_DOT = r"[\[({](?:\.|dot)[\])}]"

_DEFANG_CHUNK = r"[\[({][^\s<>\"'\[\](){}]+[\])}]"

# A character that may belong to a URL body: anything but whitespace and the usual prose/markup
# closers (which also bound a Markdown `(url)`/`[url]`). A bracket `_DEFANG_CHUNK` is matched
# atomically ahead of this, so a defang token's closing bracket does not end the match early.
_URL_CHAR = r"[^\s<>\"'\)\]\}]"


def _family(words: tuple[str, ...], seps: tuple[str, ...]) -> str:
    """A regex alternation matching any of ``words`` followed by any of ``seps`` (regex-escaped)."""
    return rf"(?:{'|'.join(words)})(?:{'|'.join(re.escape(sep) for sep in seps)})"


_DATA_ANCHOR = r"(?=[\w.+-]+/|[;,])"
_DATA_SCHEME = rf"data(?:{'|'.join(re.escape(sep) for sep in _OPAQUE_SEPS)}){_DATA_ANCHOR}"


# A clickable link, plain or defanged, anchored at a word boundary (so `sftp://` / `hotel:` are not
# partial-matched) and matched liberally to the first character that cannot belong to one. Defanged,
# percent-encoded, and fullwidth forms are reduced to a canonical identity by `normalize_url`.
URL_RE = re.compile(
    rf"\b(?:{_family(_AUTHORITY_WORDS, _AUTHORITY_SEPS)}|{_family(_OPAQUE_WORDS, _OPAQUE_SEPS)}"
    rf"|{_DATA_SCHEME})"
    rf"(?:{_DEFANG_CHUNK}|{_URL_CHAR})+",
    re.IGNORECASE,
)

_SCHEME_PREFIXES = (
    tuple(w + s for w in _AUTHORITY_WORDS for s in _AUTHORITY_SEPS)
    + tuple(w + s for w in _OPAQUE_WORDS for s in _OPAQUE_SEPS)
    + tuple("data" + s for s in _OPAQUE_SEPS)
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


_MAX_DECODE_PASSES = 5


def _decode_escapes(url: str) -> str:
    """Decode ``url``'s HTML character references and percent-escapes to a fixpoint (bounded)."""
    for _ in range(_MAX_DECODE_PASSES):
        decoded = unquote(html.unescape(url))
        if decoded == url:
            return decoded
        url = decoded
    return url


_CONFUSABLES = str.maketrans(
    {
        # Cyrillic -> Latin, lowercase (a e o p c y x i j s d h l)
        "\u0430": "a",
        "\u0435": "e",
        "\u043e": "o",
        "\u0440": "p",
        "\u0441": "c",
        "\u0443": "y",
        "\u0445": "x",
        "\u0456": "i",
        "\u0458": "j",
        "\u0455": "s",
        "\u0501": "d",
        "\u04bb": "h",
        "\u04cf": "l",
        # Cyrillic -> Latin, the classic uppercase lookalikes (A B E K M H O P C T Y X)
        "\u0410": "A",
        "\u0412": "B",
        "\u0415": "E",
        "\u041a": "K",
        "\u041c": "M",
        "\u041d": "H",
        "\u041e": "O",
        "\u0420": "P",
        "\u0421": "C",
        "\u0422": "T",
        "\u0423": "Y",
        "\u0425": "X",
        # Greek -> Latin (omicron/rho, both cases)
        "\u03bf": "o",
        "\u039f": "O",
        "\u03c1": "p",
        "\u03a1": "P",
    }
)


def _fold_confusables(url: str) -> str:
    """Fold the curated cross-script confusable letters to their ASCII twin (``_CONFUSABLES``)."""
    return url.translate(_CONFUSABLES)


def normalize_url(url: str) -> str:
    """One URL's identity: escapes decoded (to a fixpoint), defang refanged, NFKC-folded,
    cross-script confusables folded, trailing prose punctuation dropped, scheme+authority lowered.
    """
    decoded = _refang(_decode_escapes(url))
    folded = _fold_confusables(unicodedata.normalize("NFKC", decoded))
    trimmed = folded.rstrip(TRAILING_PUNCTUATION)
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
