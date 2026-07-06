"""The URL grammar and identity behind the output guardrail's laundering defense (ADR-0015).

Split from ``guardrail.py`` (which owns the streaming redactor and its policies): this module
*recognizes* a clickable URL in text (even a partial one mid-stream) and reduces it to a
canonical *identity*, so a link collected from untrusted content and its reproduction in the reply
compare equal however the model rewrote it. ``extract_urls`` is the single entry both sides of the
defense share: the ``TaintLedger``'s collection and the user-message allowlist.

Obfuscation-resistant by construction, and deterministic + dependency-free (stdlib only). The
line that keeps this out of the heuristic/screening-model layer. A URL's identity is computed by
``normalize_url`` after (1) *refanging* common defang forms (``hxxp://``, ``evil[.]com``, ``[://]``;
ADR-0015 obfuscation addendum), (2) *percent-decoding* once (``evil%2ecom`` → ``evil.com``), and
(3) *NFKC* Unicode folding (fullwidth/compatibility homoglyphs → ASCII), so a defanged, encoded, or
fullwidth link reduces to the same identity as its plain twin (ADR-0015 third addendum). What is
*not* recognized is never redacted, so the scope stays deliberately narrow: bare addresses/domains,
whitespace-split defang (``evil dot com``), cross-script homoglyphs/IDN/punycode, and unlisted
schemes (``data:`` …) stay out. See the ADR for why. Pure, no I/O, no state.
"""

import re
import unicodedata
from urllib.parse import unquote

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
    """Rewrite a URL's defanged tokens (`hxxp`, `[.]`, `[://]`, …) to their plain characters.

    Applied at the head of ``normalize_url`` so a defanged link collected from untrusted content
    and its plain reproduction in the reply (or vice versa) compare equal (ADR-0015 addendum). A
    no-op on an already-plain URL.
    """
    for pattern, repl in _REFANG_SUBS:
        url = pattern.sub(repl, url)
    return url


def normalize_url(url: str) -> str:
    """One URL's identity: defang refanged, percent-decoded, NFKC-folded, trailing prose
    punctuation dropped, scheme+authority lowercased.

    The three obfuscation-resistant passes run first so a defanged/encoded/fullwidth link reduces
    to the same identity as its plain twin (ADR-0015 third addendum). The path/query/fragment keep
    their case (URL semantics). Laundering is verbatim reproduction, so exact-but-case-normalized
    identity is the right match. An opaque URL (`mailto:`/`tel:`) has no ``://`` authority to split
    on, so it folds whole (harmless: it only widens a security redaction, and both sides fold
    identically so verbatim matches still compare equal).
    """
    trimmed = unicodedata.normalize("NFKC", unquote(_refang(url))).rstrip(TRAILING_PUNCTUATION)
    head, sep, tail = trimmed.partition("://")
    cut = _AUTHORITY_END.search(tail)
    if cut is None:
        return f"{head.lower()}{sep}{tail.lower()}"
    return f"{head.lower()}{sep}{tail[: cut.start()].lower()}{tail[cut.start() :]}"


def extract_urls(text: str) -> frozenset[str]:
    """Every clickable URL in ``text`` (any listed scheme), normalized for identity comparison.

    Both sides of the laundering defense use this one function, with collection from untrusted tool
    results (``TaintLedger.observe``) and the user-message allowlist, so a collected URL and its
    reappearance in a reply always compare equal.
    """
    return frozenset(normalize_url(match.group()) for match in URL_RE.finditer(text))


def held_from(buf: str) -> int:
    """The index from which ``buf`` may still be growing a URL. Everything before is final.

    Two open cases: a URL match touching the buffer's end (the next chunk may extend it), and a
    trailing prefix of a scheme ("h" … "https://") that has not yet become matchable. Both are
    carried; anything else cannot change meaning with more text.
    """
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
