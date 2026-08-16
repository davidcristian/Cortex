"""One URL's canonical *identity*, behind the output guardrail's laundering defense (ADR-0015)."""

import html
import re
import unicodedata
from urllib.parse import unquote

# The bracket vocabulary every defang token is wrapped in. All three shapes are equivalent wherever
# one is recognized, so they are held once here rather than spelled out per token (the asymmetry the
# seventh addendum found: the dot accepted all three while the separator accepted only `[...]`).
_OPEN_BRACKET = r"[\[({]"
_CLOSE_BRACKET = r"[\])}]"

DOT_WORD = "dot"
DEFANG_DOT = rf"{_OPEN_BRACKET}(?:\.|{DOT_WORD}){_CLOSE_BRACKET}"

# The defanged scheme separators, in any bracket shape: `[://]`/`(://)`/`{://}` for an authority
# scheme, `[:]`/`(:)`/`{:}` for the bare colon (which also covers the `[:]//` split form, as the
# `//` survives untouched). Unambiguous wherever they appear, so they need no anchoring.
_DEFANG_AUTHORITY_SEP = rf"{_OPEN_BRACKET}://{_CLOSE_BRACKET}"
_DEFANG_COLON = rf"{_OPEN_BRACKET}:{_CLOSE_BRACKET}"

# Prose punctuation a URL match may drag along at its end is part of the sentence, never of the URL
# identity, and preserved outside a redaction. Shared with the redactor.
TRAILING_PUNCTUATION = ".,;:!?"

SPECIAL_SCHEMES = ("https", "http", "ftp")

# Ends the authority (host[:port]) component: from here on a URL is case-sensitive.
_AUTHORITY_END = re.compile(r"[/?#]")

# Defanged-token substitutions applied before identity comparison (`_refang`): each maps a defanged
# token back to the character it hides. `hxx` is rewritten only at the scheme (anchored), never
# inside a host/path; the separator and dot forms are unambiguous wherever they appear.
_REFANG_SUBS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\Ahxx", re.IGNORECASE), "htt"),
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


LABEL_SEPARATORS = ".\u3002\uff61\uff0e"

_LABEL_DOTS = str.maketrans(dict.fromkeys(LABEL_SEPARATORS, "."))

_SPACED_DOT = re.compile(rf"[ \t]+(?:{DOT_WORD}|\.)[ \t]+", re.IGNORECASE)


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


def normalize_url(url: str) -> str:
    """One URL's identity: escapes decoded (to a fixpoint), defang refanged, format characters
    stripped, punycode decoded, NFKC-folded, confusables and label dots folded, a special scheme's
    backslashes folded to solidi, trailing prose punctuation dropped, scheme+authority lowered.
    """
    plain = _strip_format_chars(_refang(_decode_escapes(url)))
    normalized = unicodedata.normalize("NFKC", _decode_punycode(plain))
    folded = _fold_special_slashes(_fold_label_dots(_fold_confusables(normalized)))
    trimmed = folded.rstrip(TRAILING_PUNCTUATION)
    head, sep, tail = trimmed.partition("://")
    cut = _AUTHORITY_END.search(tail)
    if cut is None:
        return f"{head.lower()}{sep}{tail.lower()}"
    return f"{head.lower()}{sep}{tail[: cut.start()].lower()}{tail[cut.start() :]}"
