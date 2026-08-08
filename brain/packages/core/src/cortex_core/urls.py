"""The URL *grammar* behind the output guardrail's laundering defense (ADR-0015).

This module *recognizes* a clickable URL in text (even a partial one mid-stream); ``url_identity``
reduces a match to its canonical identity, so a link collected from untrusted content and its
reproduction in the reply compare equal however the model rewrote it. ``extract_urls`` is the single
entry both sides of the defense share: the ``TaintLedger``'s collection and the user-message
allowlist. The two modules split at the line cap as the seventh addendum landed.

Obfuscation-resistant by construction, and deterministic + dependency-free (stdlib only). The
matcher tolerates a *defanged* scheme (``hxxp://``, ``[://]``, ``[:]``), a **fullwidth** scheme
separator (a U+FF1A colon or a U+FF0F solidus, which NFKC folds to ASCII in the identity but
which anchored nothing here; ADR-0015 eighth addendum), a bracketed chunk anywhere
in the body (so an encoded defang dot behind a literal closer like ``evil[&#46;]com`` is consumed
whole rather than cutting the match short; ADR-0015 sixth addendum), and an **encoded separator**
(``http[&#58;//]evil.com``, admitted as a bracket chunk that carries an escape marker; ADR-0015
seventh addendum). Recognized schemes are ``http(s)``, ``ftp``, ``mailto``, ``tel``, and ``data:``
(the last only behind a MIME-type anchor, so ``data:the results`` prose stays out; ADR-0015 fifth
addendum). What is *not* recognized is never redacted, so the scope stays deliberately narrow: bare
addresses/domains and whitespace-split defang (``evil dot com``) stay out. See the ADR for why.
Pure state- and I/O-free.
"""

import re

from cortex_core.url_identity import normalize_url

# The scheme families a URL may open with, plain or *defanged*, keyed by separator shape. Authority
# schemes (`http(s)`, its CTI defang `hxxp(s)`, and `ftp`) take `://`; opaque schemes (`mailto`,
# `tel`) take a bare `:`. Every one is an intentional, clickable exfil / phishing / call vector.
# Bare addresses, bare domains, and every unlisted scheme stay out, as matching each `user@host`,
# `name.py`, or `metadata:` would redact ordinary prose. Longer variants precede their prefixes
# (`https` before `http`) so the alternation prefers the full scheme.
_AUTHORITY_WORDS = ("https", "http", "hxxps", "hxxp", "ftp")
_OPAQUE_WORDS = ("mailto", "tel")

# Scheme separators, plain or defanged: `://` may arrive defanged as `[://]` or `[:]//`, an opaque
# colon as `[:]`. Each family pairs only with its own separators, so `http:foo` / `mailto://x` do
# not over-match. Held here in plain text; escaped into the regex and concatenated into the
# streaming hold-back prefixes below, so both derive from one table and cannot drift.
#
# Every defang bracket shape is enumerated, not just `[...]`: the refanger always folded `(.)`/`{.}`
# as readily as `[.]`, but the separator tables listed only the square form, so `http(://)evil.com`
# and `http{://}evil.com` anchored *nothing* and were never matched at all. That asymmetry was a
# standing bypass in its own right, found while widening this position (ADR-0015 seventh addendum).
_BRACKETS = (("[", "]"), ("(", ")"), ("{", "}"))

# The colon and solidus a plain separator is built from, each in its ASCII form and its fullwidth
# twin (U+FF1A, U+FF0F), written as `\u` escapes so the source stays ASCII (the `_CONFUSABLES`
# convention). NFKC already folds both to ASCII in the *identity*, but the matcher runs before any
# normalization, so a fullwidth-separated URL anchored nothing, matched nothing, and was therefore
# redacted by neither mode (ADR-0015 eighth addendum). Every combination is generated from the two
# tables rather than listed, the `_BRACKETS` precedent, so a mixed spelling (an ASCII colon with a
# fullwidth solidus) cannot be the one nobody remembered.
_COLONS = (":", "\uff1a")
_SOLIDI = ("/", "\uff0f")
_AUTHORITY_SEPS = (
    *(f"{colon}{first}{second}" for colon in _COLONS for first in _SOLIDI for second in _SOLIDI),
    *(f"{lo}{tok}{hi}{tail}" for lo, hi in _BRACKETS for tok, tail in (("://", ""), (":", "//"))),
)
_OPAQUE_SEPS = (*_COLONS, *(f"{lo}:{hi}" for lo, hi in _BRACKETS))

# The bracket vocabulary, shared by every bracketed token below so they cannot drift. The inner run
# excludes whitespace, prose/markup quoting, and every bracket, so a chunk cannot swallow a second
# one and the matcher stays linear (a closer-less run fails and backtracks linearly).
_OPEN_BRACKET = r"[\[({]"
_CLOSE_BRACKET = r"[\])}]"
_CHUNK_INNER = r"[^\s<>\"'\[\](){}]"

# The matcher's bracket-delimited chunk in a URL *body*: an opening bracket, a non-empty inner run,
# then a closing bracket. Broader than the refanger's literal `[.]`/`[dot]` so `URL_RE` also eats
# a defang dot whose inner is *encoded* (`[&#46;]`, `[%2e]`) sitting behind a *literal* closing
# bracket: that raw `]`/`)`/`}` (excluded from `_URL_CHAR`) would otherwise end the match before
# `normalize_url`'s decode could expose the token to the refanger (ADR-0015 sixth addendum). Only a
# chunk that *decodes to* `[.]`/`[dot]` folds to a dot; any other (`[0]` in a query, `(a)` in a
# path)
# is consumed but kept verbatim in the identity, so the widening is symmetric and over-redacts a
# fuller span at worst. The inner is `+` (never empty), so a bare `[]` array-param still terminates.
_DEFANG_CHUNK = rf"{_OPEN_BRACKET}{_CHUNK_INNER}+{_CLOSE_BRACKET}"

# The matcher's bracket chunk at the *separator* position (`http[&#58;//]evil.com`): the same shape,
# but its inner must carry an escape marker (`&` or `%`). That constraint is what keeps the widening
# honest (ADR-0015 seventh addendum). The separator anchors the whole match and so is matched
# before any decoding can run, but it does not follow that the encodings must be enumerated there:
# requiring
# only the *shape* of an escape leaves `normalize_url`'s decode fixpoint to resolve whichever
# encoding it actually was, so no table of encodings appears in the anchor. The marker is load
# bearing: an unconstrained chunk here would match ordinary prose like `http(s)-only`, which strict
# mode would then redact out of the repo's own docs.
_ENCODED_SEP_CHUNK = rf"{_OPEN_BRACKET}{_CHUNK_INNER}*[&%]{_CHUNK_INNER}*{_CLOSE_BRACKET}"

# A character that may belong to a URL body: anything but whitespace and the usual prose/markup
# closers (which also bound a Markdown `(url)`/`[url]`). A bracket `_DEFANG_CHUNK` is matched
# atomically ahead of this, so a defang token's closing bracket does not end the match early.
_URL_CHAR = r"[^\s<>\"'\)\]\}]"


def _family(words: tuple[str, ...], seps: tuple[str, ...]) -> str:
    """A regex alternation: any of ``words``, then any of ``seps`` (escaped) or an encoded chunk."""
    plain = "|".join(re.escape(sep) for sep in seps)
    return rf"(?:{'|'.join(words)})(?:{plain}|{_ENCODED_SEP_CHUNK})"


# The `data:` scheme opens an inline `data:<mediatype>[;base64],<data>` URL: a clickable phishing
# page / exfil payload. Unlike the bare-scheme families it is admitted only when the colon is
# followed by a MIME-type shape (`type/subtype`, a `/`-bearing token) or the `,`/`;` that begins the
# data, so prose like `data:the results` (no slash, no immediate `,`/`;`) stays out while a real
# data URL matches (ADR-0015 fifth addendum). Its separator may be defanged (`data[:]`) or encoded
# (`data[&#58;]`) like the other opaque schemes, sharing `_family` so it cannot drift from them;
# identity folds it whole (no `://` authority to split, so the payload lowercases symmetrically,
# harmless for comparison). The lookahead consumes nothing; the body matches from the MIME type.
_DATA_ANCHOR = r"(?=[\w.+-]+/|[;,])"
_DATA_SCHEME = rf"{_family(('data',), _OPAQUE_SEPS)}{_DATA_ANCHOR}"


# A clickable link, plain or defanged, anchored at a word boundary (so `sftp://` / `hotel:` are not
# partial-matched) and matched liberally to the first character that cannot belong to one. Defanged,
# encoded, and fullwidth forms are reduced to a canonical identity by `normalize_url`.
URL_RE = re.compile(
    rf"\b(?:{_family(_AUTHORITY_WORDS, _AUTHORITY_SEPS)}|{_family(_OPAQUE_WORDS, _OPAQUE_SEPS)}"
    rf"|{_DATA_SCHEME})"
    rf"(?:{_DEFANG_CHUNK}|{_URL_CHAR})+",
    re.IGNORECASE,
)

# Every scheme word, for the hold-back's open-chunk check below. Derived from the same tables as
# `URL_RE`, so the two cannot drift.
_SCHEME_WORDS = _AUTHORITY_WORDS + _OPAQUE_WORDS + ("data",)

# Every plain/defanged scheme opening, derived from the same families as `URL_RE` (the `data:`
# openings included, so a `data:` split across deltas is carried too). The streaming hold-back
# carries a trailing prefix of any of these so a scheme split across deltas is not leaked
# (`held_from`). Sharing the table with the matcher makes drift structurally impossible.
_SCHEME_PREFIXES = (
    tuple(w + s for w in _AUTHORITY_WORDS for s in _AUTHORITY_SEPS)
    + tuple(w + s for w in _OPAQUE_WORDS for s in _OPAQUE_SEPS)
    + tuple("data" + s for s in _OPAQUE_SEPS)
)

# The longest string that is a prefix of a scheme+separator but not yet a URL match
# ("https://" needs one more character to match URL_RE). It is the stream filter's hold-back bound.
_LONGEST_OPEN_PREFIX = max(len(prefix) for prefix in _SCHEME_PREFIXES)

# A scheme word whose separator bracket chunk is still **open** at the buffer's end (`http[&#58;`).
# An encoded separator is variable-length, so unlike the plain forms it cannot be enumerated into
# `_SCHEME_PREFIXES`; without this the buffer would match no URL, hold nothing, and leak the pieces
# of a separator split across deltas (ADR-0015 seventh addendum). Bounded by the same bracket-free
# inner run, so it cannot run past the chunk it is waiting to close.
_OPEN_SEP_RE = re.compile(
    rf"\b(?:{'|'.join(_SCHEME_WORDS)}){_OPEN_BRACKET}{_CHUNK_INNER}*\Z",
    re.IGNORECASE,
)


def extract_urls(text: str) -> frozenset[str]:
    """Every clickable URL in ``text`` (any listed scheme), normalized for identity comparison.

    Both sides of the laundering defense use this one function, with collection from untrusted tool
    results (``TaintLedger.observe``) and the user-message allowlist, so a collected URL and its
    reappearance in a reply always compare equal.
    """
    return frozenset(normalize_url(match.group()) for match in URL_RE.finditer(text))


def held_from(buf: str) -> int:
    """The index from which ``buf`` may still be growing a URL. Everything before is final.

    Three open cases: a URL match touching the buffer's end (the next chunk may extend it), an
    unclosed separator chunk after a scheme word (`http[&#58;`, which is not yet a match at all),
    and a trailing prefix of a scheme ("h" … "https://") that has not yet become matchable. All are
    carried; anything else cannot change meaning with more text.
    """
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
