"""One URL's canonical *identity*, behind the output guardrail's laundering defense (ADR-0015).

Split from ``urls.py`` (which owns the *grammar*: what counts as a clickable URL in text, even a
partial one mid-stream) at the line cap as the seventh addendum landed. This module answers the
other half: given a matched URL, reduce it to a canonical string so a link collected from untrusted
content and its reproduction in the reply compare equal however the model rewrote it.

``normalize_url`` applies its passes in a fixed order, each one only ever *merging* two spellings
into one identity, never splitting one:

1. *Decode escapes* to a fixpoint: HTML character references (``evil&#46;com``, the way HTML email
   hides a dot) and percent-escapes, stacked (``evil%252ecom``); ADR-0015 fourth + fifth addenda.
2. *Refang* common defang tokens (``hxxp://``, ``evil[.]com``, ``[://]``), run after decode so an
   entity-hidden bracket refangs too (ADR-0015 sixth addendum).
3. *Strip format characters* (Unicode category ``Cf``: zero-width spaces/joiners, soft hyphen, BOM),
   which survive NFKC and otherwise let ``evi<ZWSP>l.com`` diverge from its plain twin.
4. *Decode punycode* labels (``xn--e1awd7f`` to its Unicode form) via the stdlib ``idna`` codec, so
   a registered IDN homoglyph host reduces to the letters it renders as, feeding pass 5.
5. *NFKC* folding (fullwidth/compatibility homoglyphs to ASCII).
6. Fold a *curated* table of cross-script confusable letters (Cyrillic/Greek Latin-lookalikes).

Passes 3 and 4 landed in the seventh addendum. Deterministic and dependency-free (stdlib only), the
line that keeps this out of the heuristic/screening-model layer. Pure state- and I/O-free.
"""

import html
import re
import unicodedata
from urllib.parse import unquote

# The bracket vocabulary every defang token is wrapped in. All three shapes are equivalent wherever
# one is recognized, so they are held once here rather than spelled out per token (the asymmetry the
# seventh addendum found: the dot accepted all three while the separator accepted only `[...]`).
_OPEN_BRACKET = r"[\[({]"
_CLOSE_BRACKET = r"[\])}]"

# A defanged dot inside the host/path: `[.]`, `(.)`, `{.}`, `[dot]`, `(dot)`, `{dot}` (any case).
# The *refanger*'s token, applied after `_decode_escapes`, so it needs only the literal form; the
# *matcher*'s broader bracket chunk lives in `urls.py`. Recognized only inside a URL.
_DEFANG_DOT = rf"{_OPEN_BRACKET}(?:\.|dot){_CLOSE_BRACKET}"

# The defanged scheme separators, in any bracket shape: `[://]`/`(://)`/`{://}` for an authority
# scheme, `[:]`/`(:)`/`{:}` for the bare colon (which also covers the `[:]//` split form, as the
# `//` survives untouched). Unambiguous wherever they appear, so they need no anchoring.
_DEFANG_AUTHORITY_SEP = rf"{_OPEN_BRACKET}://{_CLOSE_BRACKET}"
_DEFANG_COLON = rf"{_OPEN_BRACKET}:{_CLOSE_BRACKET}"

# Prose punctuation a URL match may drag along at its end is part of the sentence, never of the URL
# identity, and preserved outside a redaction. Shared with the redactor.
TRAILING_PUNCTUATION = ".,;:!?"

# Ends the authority (host[:port]) component: from here on a URL is case-sensitive.
_AUTHORITY_END = re.compile(r"[/?#]")

# Defanged-token substitutions applied before identity comparison (`_refang`): each maps a defanged
# token back to the character it hides. `hxx` is rewritten only at the scheme (anchored), never
# inside a host/path; the separator and dot forms are unambiguous wherever they appear.
_REFANG_SUBS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\Ahxx", re.IGNORECASE), "htt"),
    (re.compile(_DEFANG_AUTHORITY_SEP), "://"),
    (re.compile(_DEFANG_COLON), ":"),
    (re.compile(_DEFANG_DOT, re.IGNORECASE), "."),
)


def _refang(url: str) -> str:
    """Rewrite a URL's defanged tokens (`hxxp`, `[.]`, `[://]`, …) to their plain characters.

    Applied near the head of ``normalize_url`` so a defanged link collected from untrusted content
    and its plain reproduction in the reply (or vice versa) compare equal (ADR-0015 addendum). A
    no-op on an already-plain URL.
    """
    for pattern, repl in _REFANG_SUBS:
        url = pattern.sub(repl, url)
    return url


# Escape-decoding is applied to a **fixpoint**, not once, so a *stacked* escape (`evil%252ecom` →
# `evil%2ecom` → `evil.com`, or an HTML reference over a percent-escape `evil&#37;2ecom` →
# `evil%2ecom` → `evil.com`) reduces to one identity (ADR-0015 fourth + fifth addenda). Each round
# applies both `html.unescape` (HTML references → their character) and `unquote` (`%XX` → one char);
# each only ever *shrinks* the string, so a round that changes anything strictly shrinks it and this
# always terminates on its own. The cap is a belt-and-suspenders DoS bound: a URL with more stacked
# escapes than this is never a real clickable link, and is left *partially* decoded, still symmetric
# (both sides fold the same), so an equal-depth transform still matches; the bound only declines to
# over-resolve an absurd one.
_MAX_DECODE_PASSES = 5


def _decode_escapes(url: str) -> str:
    """Decode ``url``'s HTML character references and percent-escapes to a fixpoint (bounded).

    A multiply-encoded or HTML-entity-hidden escape reduces to its plain identity, not just a single
    browser-hop decode. HTML references are decoded first each round so an entity-encoded percent
    (`&#37;`) is exposed to the same round's ``unquote`` (ADR-0015 fifth addendum)."""
    for _ in range(_MAX_DECODE_PASSES):
        decoded = unquote(html.unescape(url))
        if decoded == url:
            return decoded
        url = decoded
    return url


def _strip_format_chars(url: str) -> str:
    """Drop Unicode format characters (category ``Cf``) from a URL's identity.

    Zero-width space/joiner/non-joiner, the directional marks, the soft hyphen, and the BOM render
    as *nothing*, so `evi<ZWSP>l.com` and `evil.com` are the same link to the eye and to the
    resolver, but they survive NFKC untouched and so used to compare unequal (ADR-0015 seventh
    addendum). Run after decoding, so a percent- or entity-encoded zero-width character
    (`evi%E2%80%8Bl.com`) is exposed first. Symmetric on both sides of the defense.
    """
    return "".join(char for char in url if unicodedata.category(char) != "Cf")


# An IDN label in its ASCII-compatible (punycode) encoding. Decoded back to the Unicode letters it
# renders as, so a *registered* homoglyph domain (`xn--e1awd7f.com`, which resolves and renders as
# Cyrillic `epic`) reduces through the confusable fold to the ASCII twin it imitates, instead of
# sailing past a table that only ever saw the pre-encoded form (ADR-0015 seventh addendum). The
# stdlib `idna` codec does this with no dependency, contrary to the sixth addendum's scope note.
_PUNYCODE_LABEL = re.compile(r"\bxn--[a-z0-9-]+", re.IGNORECASE)


def _decode_punycode(url: str) -> str:
    """Decode every punycode (``xn--``) label in ``url`` to the Unicode it renders as.

    Per label rather than per host, so one malformed label cannot cost the rest their decoding, and
    so a path segment that merely looks like one is handled by the same rule. A label the codec
    rejects (empty, over-long, or not valid punycode) is left exactly as it was: the identity stays
    the raw text, which is still symmetric on both sides of the defense.
    """

    def decoded(match: re.Match[str]) -> str:
        label = match.group()
        try:
            return label.encode("ascii").decode("idna")
        except UnicodeError:
            return label

    return _PUNYCODE_LABEL.sub(decoded, url)


# The common single-script *confusables*: Cyrillic and Greek letters that render identically to an
# ASCII Latin letter, folded to that letter so a homoglyph host (`<cyr>evil.example`) normalizes to
# its plain twin (ADR-0015 fourth addendum). A curated, high-confidence table, deterministic and
# dependency-free, but NOT the full UTS-39 confusables set (which needs a dependency and stays
# deferred; punycode, which the same note used to bundle in, landed in the seventh addendum).
# Folding only ever *widens* a redaction and is *symmetric* on both sides of the defense, so its
# false-positive surface is a legitimately Cyrillic/Greek URL, rare in a single-user deployment, and
# already redacted on a tainted turn under strict mode. Keys are `\u` escapes so the source stays
# ASCII and each confusable codepoint is explicit.
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
    """One URL's identity: escapes decoded (to a fixpoint), defang refanged, format characters
    stripped, punycode decoded, NFKC-folded, confusables folded, trailing prose punctuation dropped,
    scheme+authority lowered.

    The obfuscation-resistant passes run in the order the module docstring fixes, so that each feeds
    the next: decoding exposes an encoded defang token to the refanger and an encoded zero-width
    character to the stripper, and punycode decoding exposes an IDN homoglyph to the confusable
    table. The path/query/fragment keep their case (URL semantics). Laundering is verbatim
    reproduction, so an exact but case-normalized identity is the right match. An opaque URL
    (`mailto:`/`tel:`/`data:`) has no ``://`` authority to split on, so it folds whole (harmless: it
    only widens a redaction, and both sides fold identically so verbatim matches still compare
    equal).
    """
    plain = _strip_format_chars(_refang(_decode_escapes(url)))
    folded = _fold_confusables(unicodedata.normalize("NFKC", _decode_punycode(plain)))
    trimmed = folded.rstrip(TRAILING_PUNCTUATION)
    head, sep, tail = trimmed.partition("://")
    cut = _AUTHORITY_END.search(tail)
    if cut is None:
        return f"{head.lower()}{sep}{tail.lower()}"
    return f"{head.lower()}{sep}{tail[: cut.start()].lower()}{tail[cut.start() :]}"
