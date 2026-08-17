"""One URL's canonical *identity*, behind the output guardrail's laundering defense (ADR-0015)."""

import html
import re
import unicodedata
from urllib.parse import unquote

from cortex_core.url_confusables import fold_confusables
from cortex_core.url_removals import REMOVED_RUN, permeable, strip_removed

_OPEN_BRACKET = rf"[\[({{]{REMOVED_RUN}"
_CLOSE_BRACKET = rf"{REMOVED_RUN}[\])}}]"

DOT_WORD = "dot"
DEFANG_DOT = rf"{_OPEN_BRACKET}(?:\.|{permeable(DOT_WORD)}){_CLOSE_BRACKET}"

# The defanged scheme separators, in any bracket shape: `[://]`/`(://)`/`{://}` for an authority
# scheme, `[:]`/`(:)`/`{:}` for the bare colon (which also covers the `[:]//` split form, as the
# `//` survives untouched). Unambiguous wherever they appear, so they need no anchoring.
_DEFANG_AUTHORITY_SEP = rf"{_OPEN_BRACKET}{permeable('://')}{_CLOSE_BRACKET}"
_DEFANG_COLON = rf"{_OPEN_BRACKET}:{_CLOSE_BRACKET}"

# Prose punctuation a URL match may drag along at its end is part of the sentence, never of the URL
# identity, and preserved outside a redaction. Shared with the redactor.
TRAILING_PUNCTUATION = ".,;:!?"

SPECIAL_SCHEMES = ("https", "http", "ftp")

# The one opaque scheme that still names a host, spelled here because `host_of` below reads it and
# `urls.py` builds its opaque-scheme words on top of it, the `SPECIAL_SCHEMES` precedent: a
# `mailto:`'s domain decides where the mail goes exactly as an authority decides where a click goes.
MAILTO_SCHEME = "mailto"

# Ends the authority (host[:port]) component: from here on a URL is case-sensitive.
_AUTHORITY_END = re.compile(r"[/?#]")

# Defanged-token substitutions applied before identity comparison (`_refang`): each maps a defanged
# token back to the character it hides. `hxx` is rewritten only at the scheme (anchored), never
# inside a host/path; the separator and dot forms are unambiguous wherever they appear.
_REFANG_SUBS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(rf"\A{permeable('hxx')}", re.IGNORECASE), "htt"),
    (re.compile(_DEFANG_AUTHORITY_SEP), "://"),
    (re.compile(_DEFANG_COLON), ":"),
    (re.compile(DEFANG_DOT, re.IGNORECASE), "."),
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


def _strip_format_chars(url: str) -> str:
    """Drop Unicode format characters (category ``Cf``) from a URL's identity."""
    return "".join(char for char in url if unicodedata.category(char) != "Cf")


_PUNYCODE_LABEL = re.compile(r"\bxn--[a-z0-9-]+", re.IGNORECASE)


def _decode_punycode(url: str) -> str:
    """Decode every punycode (``xn--``) label in ``url`` to the Unicode it renders as."""

    def decoded(match: re.Match[str]) -> str:
        label = match.group()
        try:
            return label.encode("ascii").decode("idna")
        except UnicodeError:
            return label

    return _PUNYCODE_LABEL.sub(decoded, url)


LABEL_SEPARATORS = ".\u3002\uff61\uff0e"

_LABEL_DOTS = str.maketrans(dict.fromkeys(LABEL_SEPARATORS, "."))

_SPACED_DOT = re.compile(rf"[ \t]+(?:{permeable(DOT_WORD)}|\.)[ \t]+", re.IGNORECASE)


def _fold_label_dots(url: str) -> str:
    """Fold the IDNA label separators (U+3002, U+FF61, U+FF0E) to the ASCII dot they resolve,
    then close the whitespace a split host spells that same dot with."""
    return _SPACED_DOT.sub(".", url.translate(_LABEL_DOTS))


_SPECIAL_AUTHORITY = re.compile(rf"\A((?:{'|'.join(SPECIAL_SCHEMES)}):)[/\\]*", re.IGNORECASE)


def _fold_special_slashes(url: str) -> str:
    r"""Fold a special scheme's authority slashes to the pair a URL parser reads them as."""
    match = _SPECIAL_AUTHORITY.match(url)
    if match is None:
        return url
    rest = url[match.end() :].replace("\\", "/")
    return f"{match.group(1)}//{rest}"


def normalize_url(url: str, *, confusables: bool = True) -> str:
    """One URL's identity: escapes decoded (to a fixpoint), defang refanged, format characters
    stripped, punycode decoded, NFKC-folded, confusables and label dots folded, what a parser
    removes dropped, a special scheme's backslashes folded to solidi, trailing prose punctuation
    """
    plain = _strip_format_chars(_refang(_decode_escapes(url)))
    normalized = unicodedata.normalize("NFKC", _decode_punycode(plain))
    if confusables:
        normalized = fold_confusables(normalized)
    folded = _fold_special_slashes(strip_removed(_fold_label_dots(normalized)))
    trimmed = folded.rstrip(TRAILING_PUNCTUATION)
    head, sep, tail = trimmed.partition("://")
    cut = _AUTHORITY_END.search(tail)
    if cut is None:
        return f"{head.lower()}{sep}{tail.lower()}"
    return f"{head.lower()}{sep}{tail[: cut.start()].lower()}{tail[cut.start() :]}"


def host_of(identity: str) -> str:
    """The part of a normalized URL ``identity`` that decides where it goes, or ``""``."""
    _, authority, rest = identity.partition("://")
    if not authority:
        scheme, _, rest = identity.partition(":")
        if scheme != MAILTO_SCHEME:
            return ""
    cut = _AUTHORITY_END.search(rest)
    return (rest if cut is None else rest[: cut.start()]).rpartition("@")[2]
