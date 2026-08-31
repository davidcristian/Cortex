"""One URL's canonical identity, behind the output guardrail's laundering defense (ADR-0015).

Split from ``urls.py`` (which owns the grammar: what counts as a clickable URL in text, even a
partial one mid-stream) at the line cap as the seventh addendum landed. This module answers the
other half: given a matched URL, reduce it to a canonical string so a link collected from untrusted
content and its reproduction in the reply compare equal however the model rewrote it.

``normalize_url`` applies its passes in a fixed order, each one only ever merging two spellings
into one identity, never splitting one:

1. Decode escapes to a fixpoint: HTML character references (``evil&#46;com``, the way HTML email
   hides a dot) and percent-escapes, stacked (``evil%252ecom``); ADR-0015 fourth + fifth addenda.
2. Refang common defang tokens (``hxxp://``, ``evil[.]com``, ``[://]``), run after decode so an
   entity-hidden bracket refangs too (ADR-0015 sixth addendum).
3. Strip format characters (Unicode category ``Cf``: zero-width spaces/joiners, soft hyphen, BOM),
   which survive NFKC and otherwise let ``evi<ZWSP>l.com`` diverge from its plain twin.
4. Decode punycode labels (``xn--e1awd7f`` to its Unicode form) via the stdlib ``idna`` codec, so
   a registered IDN homoglyph host reduces to the letters it renders as, feeding pass 5.
5. NFKC folding (fullwidth/compatibility homoglyphs to ASCII, which is also what reduces a
   fullwidth scheme separator the matcher now anchors, a U+FF1A colon or a U+FF0F solidus, to
   its ASCII spelling).
6. Fold a curated table of cross-script confusable letters (Cyrillic/Greek Latin-lookalikes),
   which lives in ``url_confusables`` because it is the one pass here that is a judgement about
   what looks alike rather than a resolver's reading, and the one a caller may switch off
   (``confusables=False``) to read a host as the letters it was actually written in.
7. Fold the IDNA label separators NFKC leaves standing (a U+3002 or U+FF61 stop between two
   labels), which the resolver reads as a dot, and close the whitespace a split host spells the
   same dot with (``evil dot com``); ADR-0015 eighth + twelfth addenda.
8. Drop what a URL parser removes from its input before parsing it, which is the tab
   (``url_removals``, run here rather than earlier so a gap spelled with tabs is still a gap, the
   literals above being ``permeable`` instead); ADR-0015 fifteenth + seventeenth addenda.
9. Fold a special scheme's backslashes to the solidi the URL parser reads them as, and its run
   of authority slashes to one pair however many it holds (none included), so the JSON-escaped and
   the slashless spellings of a link share the link's identity; ADR-0015 tenth + eleventh addenda.

Passes 3 and 4 landed in the seventh addendum. Deterministic and dependency-free (stdlib only),
which is what keeps this out of the heuristic or screening-model layer. No state and no I/O.
"""

import html
import re
import unicodedata
from urllib.parse import unquote

from cortex_core.url_confusables import fold_confusables
from cortex_core.url_removals import REMOVED_RUN, permeable, strip_removed

# The bracket vocabulary every defang token is wrapped in. All three shapes are equivalent wherever
# one is recognized, so they are held once here rather than spelled out per token (the asymmetry the
# seventh addendum found: the dot accepted all three while the separator accepted only `[...]`).
# Each carries the removal run at its junction with the token it wraps, and every word below is
# spelled through `permeable`, so a removal may stand between any two characters of a defang token:
# a URL parser deletes them before it reads one, so `[d<TAB>ot]` is `[dot]` to it and to the reader
# alike (ADR-0015 seventeenth addendum).
_OPEN_BRACKET = rf"[\[({{]{REMOVED_RUN}"
_CLOSE_BRACKET = rf"{REMOVED_RUN}[\])}}]"

# A defanged dot inside the host/path: `[.]`, `(.)`, `{.}`, `[dot]`, `(dot)`, `{dot}` (any case),
# built on the one defang token that is a word rather than a mark, which is therefore the one a
# space can wrap with no bracket to bound it. These are the refanger's tokens, applied after
# `_decode_escapes`, so they need only the literal form; the matcher's broader bracket chunk lives
# in `urls.py`. Recognized only inside a URL, and public because `url_spellings.py` spends both on
# the grammar's whitespace-split host, so the grammar and the fold cannot disagree about them.
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

# The schemes whose URLs a WHATWG parser reads a backslash in as a solidus (its special schemes,
# less the ones this grammar does not match). It lives here rather than in the grammar because it is
# the resolver's own notion, and `urls.py` builds its authority-scheme words on top of it, adding
# the defanged `hxxp` twins, so the two tables cannot drift. Order matters to the alternation the
# grammar builds: a longer word precedes the shorter one it starts with.
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
    """Rewrite a URL's defanged tokens (`hxxp`, `[.]`, `[://]`, …) to their plain characters.

    Applied near the head of ``normalize_url`` so a defanged link collected from untrusted content
    and its plain reproduction in the reply (or vice versa) compare equal (ADR-0015 addendum). A
    no-op on an already-plain URL.
    """
    for pattern, repl in _REFANG_SUBS:
        url = pattern.sub(repl, url)
    return url


# Escape-decoding is applied to a fixpoint rather than once, so a stacked escape (`evil%252ecom` →
# `evil%2ecom` → `evil.com`, or an HTML reference over a percent-escape `evil&#37;2ecom` →
# `evil%2ecom` → `evil.com`) reduces to one identity (ADR-0015 fourth + fifth addenda). Each round
# applies both `html.unescape` (HTML references → their character) and `unquote` (`%XX` → one char);
# each only ever shrinks the string, so a round that changes anything strictly shrinks it and this
# always terminates on its own. The cap is a defensive DoS bound: a URL with more stacked escapes
# than this is never a real clickable link, and is left partially decoded, still symmetric
# (both sides fold the same), so an equal-depth transform still matches; the bound only declines to
# over-resolve an absurd one.
_MAX_DECODE_PASSES = 5


def _decode_escapes(url: str) -> str:
    """Decode ``url``'s HTML character references and percent-escapes to a fixpoint (bounded).

    A multiply-encoded or HTML-entity-hidden escape reduces to its plain identity rather than to a
    single browser-hop decode. HTML references are decoded first each round so an entity-encoded
    percent (`&#37;`) is exposed to the same round's ``unquote`` (ADR-0015 fifth addendum)."""
    for _ in range(_MAX_DECODE_PASSES):
        decoded = unquote(html.unescape(url))
        if decoded == url:
            return decoded
        url = decoded
    return url


def _strip_format_chars(url: str) -> str:
    """Drop Unicode format characters (category ``Cf``) from a URL's identity.

    Zero-width space/joiner/non-joiner, the directional marks, the soft hyphen, and the BOM render
    as nothing at all, so `evi<ZWSP>l.com` and `evil.com` are the same link to the eye and to the
    resolver, but they survive NFKC untouched and so used to compare unequal (ADR-0015 seventh
    addendum). Run after decoding, so a percent- or entity-encoded zero-width character
    (`evi%E2%80%8Bl.com`) is exposed first. Symmetric on both sides of the defense.
    """
    return "".join(char for char in url if unicodedata.category(char) != "Cf")


# An IDN label in its ASCII-compatible (punycode) encoding. Decoded back to the Unicode letters it
# renders as, so a registered homoglyph domain (`xn--e1awd7f.com`, which resolves and renders as
# Cyrillic `epic`) reduces through the confusable fold to the ASCII twin it imitates, rather than
# passing a table that only ever saw the pre-encoded form (ADR-0015 seventh addendum). The
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


# The label separators IDNA itself reads as a dot, folded so a host spelled with one shares the
# identity of the host it resolves to. This is not a judgement about what looks alike: the stdlib's
# own IDNA codec splits a host on exactly U+002E, U+3002 (ideographic full stop), U+FF0E (fullwidth)
# and U+FF61 (halfwidth ideographic) via `encodings.idna.dots`, and a host written with the U+3002
# stop encodes to the plain ASCII host, so the reader decodes nothing and the resolver goes to the
# same place. NFKC folds U+FF0E (and the one-dot leader U+2024) on its own but maps U+FF61 onto
# U+3002 rather than to a dot, leaving that pair standing, which gave a collected link a second
# identity the default policy missed while strict mode still caught it (ADR-0015 eighth addendum).
# Symmetric and over-redaction-only like every other pass here: the false positive is a legitimate
# host written with a CJK stop, which resolves to the same host anyway. Keys are `\u` escapes so the
# source stays ASCII, the `_CONFUSABLES` convention. The ASCII dot leads the table (folding to
# itself) because `url_spellings.py` spends the same string on the grammar's host anchor, which has
# to admit every reading of a dot the resolver has, so the two cannot disagree about what one is.
LABEL_SEPARATORS = ".\u3002\uff61\uff0e"

_LABEL_DOTS = str.maketrans(dict.fromkeys(LABEL_SEPARATORS, "."))

# The label separator a gap spells: the whitespace-split defang (`evil dot com`, `evil . com`),
# which the grammar admits only inside a host that carries no plain dot of its own. Folding it
# closes the whitespace, so the split spelling and the contiguous one are one identity. Every
# other reading has already become an ASCII dot by the time this runs (escapes decoded, brackets
# refanged, CJK stops translated just above), so the token here is only the mark or the word; and
# for the same reason the whitespace here is only the tab and the space, NFKC having already
# reduced the no-break, thin and ideographic spaces the grammar admits (`NFKC_SPACES`).
_SPACED_DOT = re.compile(rf"[ \t]+(?:{permeable(DOT_WORD)}|\.)[ \t]+", re.IGNORECASE)


def _fold_label_dots(url: str) -> str:
    """Fold the IDNA label separators (U+3002, U+FF61, U+FF0E) to the ASCII dot they resolve,
    then close the whitespace a split host spells that same dot with."""
    return _SPACED_DOT.sub(".", url.translate(_LABEL_DOTS))


# A special scheme, its colon, and the run of authority slashes after it, a backslash counting as
# one. Like the label separators above this is the resolver's reading and not a judgement about
# what looks alike: the URL Standard's special-authority states skip both `/` and `\`, so
# `new URL("https:\/\/evil.example/pay")` in any WHATWG-conforming parser (every browser) is
# `https://evil.example/pay`, and the JSON-escaped spelling of a link is the link itself rather
# than a rendering of one (ADR-0015 tenth addendum). The run is `*` and not `+` because the same
# states tolerate a slash that is missing: `https:evil.example/pay` is that link too, so the empty
# run is one of the spellings this pass has to fold (ADR-0015 eleventh addendum). Run after NFKC,
# which has already reduced the fullwidth solidus, and after the refanger, which has already
# turned `hxxp` into `http`.
_SPECIAL_AUTHORITY = re.compile(rf"\A((?:{'|'.join(SPECIAL_SCHEMES)}):)[/\\]*", re.IGNORECASE)


def _fold_special_slashes(url: str) -> str:
    r"""Fold a special scheme's authority slashes to the pair a URL parser reads them as.

    Every half is that parser's own rule: a backslash is a solidus, in the authority slashes and in
    the path alike, and the run of them after the scheme's colon is skipped whole however long it
    is, zero included, so `https:\/\/host`, `https:\\host`, `https:////host`, `https:/host` and
    `https:host` all name `https://host`. Scoped to the schemes where that holds, so an opaque
    `mailto:`/`tel:`/`data:` keeps its backslashes and its one colon; and merging-only like every
    pass here, since a query's backslash (which the parser does leave alone) can now only share an
    identity with the same query's solidus, never split from itself.
    """
    match = _SPECIAL_AUTHORITY.match(url)
    if match is None:
        return url
    rest = url[match.end() :].replace("\\", "/")
    return f"{match.group(1)}//{rest}"


def normalize_url(url: str, *, confusables: bool = True) -> str:
    """One URL's identity: escapes decoded (to a fixpoint), defang refanged, format characters
    stripped, punycode decoded, NFKC-folded, confusables and label dots folded, what a parser
    removes dropped, a special scheme's backslashes folded to solidi, trailing prose punctuation
    dropped, scheme+authority lowered.

    The obfuscation-resistant passes run in the order the module docstring fixes, so that each feeds
    the next: decoding exposes an encoded defang token to the refanger and an encoded zero-width
    character to the stripper, and punycode decoding exposes an IDN homoglyph to the confusable
    table. The path/query/fragment keep their case (URL semantics). Laundering is verbatim
    reproduction, so an exact but case-normalized identity is the right match. An opaque URL
    (`mailto:`/`tel:`/`data:`) has no ``://`` authority to split on, so it folds whole (harmless: it
    only widens a redaction, and both sides fold identically so verbatim matches still compare
    equal).

    ``confusables=False`` runs every pass but the curated confusable fold, which is the only one
    that is a judgement rather than a resolver's reading. Identity comparison always needs the
    fold, so both sides of the defense take the default; the lookalike policy needs the host as it
    was written, because a host built wholly out of table entries folds to plain ASCII and would
    otherwise read as an ordinary name (ADR-0015 fourteenth addendum). Structure is unaffected
    either way: every pass that decides where the ``://`` and the authority end runs regardless.
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
    """The part of a normalized URL ``identity`` that decides where it goes, or ``""``.

    An authority scheme's is its ``host[:port]``, read off the identity's own ``://`` and ended by
    the first ``/?#`` exactly as the case rule above ends it; a ``mailto:``'s is the domain after
    its address's ``@``. One ``rpartition`` serves both, dropping an authority's userinfo and an
    address's local part together, since neither says where the link leads. ``tel:``, ``data:``
    and anything else answer ``""``: a phone number and an inline payload name no host, so a policy
    reading this cannot invent one for them.

    Takes an identity rather than a raw match because the passes behind it are what put the ``://``
    where it belongs: a defanged, encoded, fullwidth or slashless spelling reaches this function
    already resolved (ADR-0015 fourteenth addendum).
    """
    _, authority, rest = identity.partition("://")
    if not authority:
        scheme, _, rest = identity.partition(":")
        if scheme != MAILTO_SCHEME:
            return ""
    cut = _AUTHORITY_END.search(rest)
    return (rest if cut is None else rest[: cut.start()]).rpartition("@")[2]
