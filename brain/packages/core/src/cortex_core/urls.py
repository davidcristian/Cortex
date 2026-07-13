"""The URL grammar and identity behind the output guardrail's laundering defense (ADR-0015).

Split from ``guardrail.py`` (which owns the streaming redactor and its policies): this module
*recognizes* a clickable URL in text (even a partial one mid-stream) and reduces it to a
canonical *identity*, so a link collected from untrusted content and its reproduction in the reply
compare equal however the model rewrote it. ``extract_urls`` is the single entry both sides of the
defense share: the ``TaintLedger``'s collection and the user-message allowlist.

Obfuscation-resistant by construction, and deterministic + dependency-free (stdlib only). The
line that keeps this out of the heuristic/screening-model layer. A URL's identity is computed by
``normalize_url`` after (1) *decoding escapes* to a fixpoint, both HTML character references
(``evil&#46;com``, the way HTML email hides a dot) and percent-escapes (``evil%252ecom`` →
``evil%2ecom`` → ``evil.com``; bounded; ADR-0015 fourth + fifth addenda), (2) *refanging* common
defang forms (``hxxp://``, ``evil[.]com``, ``[://]``; run after decode so an entity-hidden bracket
refangs too), (3) *NFKC* Unicode folding (fullwidth/compatibility homoglyphs → ASCII), and (4)
folding a *curated* table of cross-script confusable letters (Cyrillic/Greek Latin-lookalikes →
ASCII), so a defanged, encoded, fullwidth, or homoglyph link reduces to the same identity as its
plain twin. Recognized schemes are ``http(s)``, ``ftp``, ``mailto``, ``tel``, and ``data:`` (the
last only behind a MIME-type anchor, so ``data:the results`` prose stays out; ADR-0015 fifth
addendum). What is *not* recognized is never redacted, so the scope stays deliberately narrow: bare
addresses/domains, whitespace-split defang (``evil dot com``), and the *full* UTS-39 confusables
set + IDN/punycode (need a dependency) stay out. See the ADR for why. Pure, no I/O, no state.
"""

import html
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


# The `data:` scheme opens an inline `data:<mediatype>[;base64],<data>` URL: a clickable phishing
# page / exfil payload. Unlike the bare-scheme families it is admitted only when the colon is
# followed by a MIME-type shape (`type/subtype`, a `/`-bearing token) or the `,`/`;` that begins the
# data, so prose like `data:the results` (no slash, no immediate `,`/`;`) stays out while a real
# data URL matches (ADR-0015 fifth addendum). Its separator may be defanged (`data[:]`) like the
# other opaque schemes; identity folds it whole (no `://` authority to split, so the payload
# lowercases symmetrically, harmless for comparison). The lookahead consumes nothing; the body then
# matches from the MIME type.
_DATA_ANCHOR = r"(?=[\w.+-]+/|[;,])"
_DATA_SCHEME = rf"data(?:{'|'.join(re.escape(sep) for sep in _OPAQUE_SEPS)}){_DATA_ANCHOR}"


# A clickable link, plain or defanged, anchored at a word boundary (so `sftp://` / `hotel:` are not
# partial-matched) and matched liberally to the first character that cannot belong to one. Defanged,
# percent-encoded, and fullwidth forms are reduced to a canonical identity by `normalize_url`.
URL_RE = re.compile(
    rf"\b(?:{_family(_AUTHORITY_WORDS, _AUTHORITY_SEPS)}|{_family(_OPAQUE_WORDS, _OPAQUE_SEPS)}"
    rf"|{_DATA_SCHEME})"
    rf"(?:{_DEFANG_DOT}|{_URL_CHAR})+",
    re.IGNORECASE,
)

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


# The common single-script *confusables*: Cyrillic and Greek letters that render identically to an
# ASCII Latin letter, folded to that letter so a homoglyph host (`<cyr>evil.example`) normalizes to
# its plain twin (ADR-0015 fourth addendum). A curated, high-confidence table, deterministic and
# dependency-free, but NOT the full UTS-39 confusables set (which, with IDN/punycode, needs a
# dependency and stays deferred). Folding only ever *widens* a redaction and is *symmetric* on both
# sides of the defense, so its false-positive surface is a legitimately Cyrillic/Greek URL, rare in
# a single-user deployment, and already redacted on a tainted turn under strict mode. Keys are `\u`
# escapes so the source stays ASCII and each confusable codepoint is explicit.
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

    The obfuscation-resistant passes run first so a defanged/encoded/fullwidth/homoglyph link
    reduces to its plain twin's identity (ADR-0015 third + fourth + fifth addenda). Decoding runs
    *before* refanging so an entity-encoded bracket (`&#91;.&#93;` → `[.]`) refangs too, and the
    passes still compose (a percent-encoded homoglyph decodes, then folds). The path/query/fragment
    keep their case (URL semantics). Laundering is verbatim reproduction, so an exact but
    case-normalized identity is the right match. An opaque URL (`mailto:`/`tel:`/`data:`) has no
    ``://`` authority to split on, so it folds whole (harmless: it only widens a redaction, and both
    sides fold identically so verbatim matches still compare equal).
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
