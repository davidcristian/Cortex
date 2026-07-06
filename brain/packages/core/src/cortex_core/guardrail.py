"""The model-independent output guardrail: deterministic URL-laundering defense (ADR-0015)."""

import re
from collections.abc import Set as AbstractSet
from typing import Protocol

_HTTP_WORD = r"h(?:tt|xx)ps?"

# Scheme separators, plain or defanged: `://` may arrive as `[://]` or `[:]//`, a `mailto:` colon
# as `[:]`. Each pairs only with its own scheme, so `http:foo`/`mailto://x` do not over-match.
_HTTP_SEP = r"://|\[://\]|\[:\]//"
_MAILTO_SEP = r":|\[:\]"

# A defanged dot inside the host/path: `[.]`, `(.)`, `{.}`, `[dot]`, `(dot)`, `{dot}` (any case).
# Recognized only *inside* a scheme'd URL, so a bare `evil[.]com` in prose still never matches.
_DEFANG_DOT = r"[\[({](?:\.|dot)[\])}]"

# A character that may belong to a URL body: anything but whitespace and the usual prose/markup
# closers (which also bound a Markdown `(url)`/`[url]`). A defanged dot is matched atomically
# ahead of this, so its closing bracket does not end the match early.
_URL_CHAR = r"[^\s<>\"'\)\]\}]"

# A clickable link, plain or defanged, matched liberally to the first character that cannot belong
# to one. Defanged forms are refanged to a canonical identity by `_normalize`/`_refang`.
_URL_RE = re.compile(
    rf"(?:{_HTTP_WORD}(?:{_HTTP_SEP})|mailto(?:{_MAILTO_SEP}))(?:{_DEFANG_DOT}|{_URL_CHAR})+",
    re.IGNORECASE,
)

# The full scheme openings, plain and defanged, whose prefixes the streaming hold-back carries so
# a scheme split across deltas is never leaked (`_held_from`). Kept in sync with `_URL_RE`.
_SCHEME_PREFIXES = (
    "https://",
    "http://",
    "hxxps://",
    "hxxp://",
    "https[://]",
    "http[://]",
    "hxxps[://]",
    "hxxp[://]",
    "https[:]//",
    "http[:]//",
    "hxxps[:]//",
    "hxxp[:]//",
    "mailto:",
    "mailto[:]",
)

# Prose punctuation a URL match may drag along at its end is part of the sentence, never of
# the URL identity, and preserved outside a redaction.
_TRAILING_PUNCTUATION = ".,;:!?"

# Ends the authority (host[:port]) component: from here on a URL is case-sensitive.
_AUTHORITY_END = re.compile(r"[/?#]")

# The longest string that is a prefix of a scheme+separator but not yet a URL match
# ("https://" needs one more character to match _URL_RE). It is the stream filter's hold-back bound.
_LONGEST_OPEN_PREFIX = max(len(prefix) for prefix in _SCHEME_PREFIXES)

# What the user sees in place of a laundered link. Self-explanatory inline, so the overlay
# needs no extra event type to surface the redaction.
REDACTED_LINK = "[link removed: untrusted source]"

# Defanged-token substitutions applied before identity comparison (`_refang`): each maps a
# defanged token back to the character it hides. `hxx` is rewritten only at the scheme (anchored),
# never inside a host/path; the separator and dot forms are unambiguous wherever they appear.
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


def _normalize(url: str) -> str:
    """One URL's identity: defang refanged, trailing prose punctuation dropped, scheme+authority
    lowercased.
    """
    trimmed = _refang(url).rstrip(_TRAILING_PUNCTUATION)
    head, sep, tail = trimmed.partition("://")
    cut = _AUTHORITY_END.search(tail)
    if cut is None:
        return f"{head.lower()}{sep}{tail.lower()}"
    return f"{head.lower()}{sep}{tail[: cut.start()].lower()}{tail[cut.start() :]}"


def extract_urls(text: str) -> frozenset[str]:
    """Every clickable http(s)/``mailto:`` URL in ``text``, normalized for identity comparison."""
    return frozenset(_normalize(match.group()) for match in _URL_RE.finditer(text))


class OutputFilter(Protocol):
    """One turn's streaming output filter: ``feed`` each delta, ``flush`` at end of stream.

    ``feed`` returns the (possibly rewritten, possibly empty) text safe to emit now; text a
    still-growing URL might extend is carried until a later ``feed`` or the final ``flush``.
    """

    def feed(self, chunk: str) -> str: ...

    def flush(self) -> str: ...


class TaintView(Protocol):
    """The **live** taint signals the guardrail reads at scan time (ADR-0013/0015)."""

    @property
    def tainted(self) -> bool: ...

    @property
    def untrusted_urls(self) -> AbstractSet[str]: ...


class OutputGuardrail(Protocol):
    """Opens one turn's ``OutputFilter`` over that turn's live laundering evidence (ADR-0015)."""

    def open(self, taint: TaintView, *, allow: frozenset[str]) -> OutputFilter: ...


class UrlRedactingGuardrail:
    """The default ``OutputGuardrail``: redact URLs sourced *verbatim* from untrusted content."""

    def open(self, taint: TaintView, *, allow: frozenset[str]) -> OutputFilter:
        """One turn's redacting filter; state dies with the turn."""
        return _UrlRedactingFilter(taint, allow, strict=False)


class StrictUrlRedactingGuardrail:
    """The opt-in strict ``OutputGuardrail`` (ADR-0015 addendum): on a **tainted** turn, redact
    *every* URL the user did not themselves send, going beyond the verbatim-collected ones.
    """

    def open(self, taint: TaintView, *, allow: frozenset[str]) -> OutputFilter:
        """One turn's strict redacting filter; state dies with the turn."""
        return _UrlRedactingFilter(taint, allow, strict=True)


def _held_from(buf: str) -> int:
    """The index from which ``buf`` may still be growing a URL. Everything before is final."""
    last = None
    for match in _URL_RE.finditer(buf):
        last = match
    if last is not None and last.end() == len(buf):
        return last.start()
    lower = buf.lower()
    for size in range(min(len(buf), _LONGEST_OPEN_PREFIX), 0, -1):
        suffix = lower[-size:]
        if any(prefix.startswith(suffix) for prefix in _SCHEME_PREFIXES):
            return len(buf) - size
    return len(buf)


class _UrlRedactingFilter:
    """The streaming redactor behind the redacting guardrails (one instance per turn)."""

    def __init__(self, taint: TaintView, allow: frozenset[str], *, strict: bool) -> None:
        self._taint = taint
        self._allow = allow
        self._strict = strict
        self._pending = ""

    def feed(self, chunk: str) -> str:
        """Scrub and release the finalized prefix; carry what a later chunk might extend."""
        buf = self._pending + chunk
        held = _held_from(buf)
        self._pending = buf[held:]
        return self._scrub(buf[:held])

    def flush(self) -> str:
        """End of stream: the carried tail is complete by termination, scrub and release it."""
        out = self._scrub(self._pending)
        self._pending = ""
        return out

    def _scrub(self, text: str) -> str:
        """Replace every URL this turn flags; leave all other text alone."""
        if self._strict:
            if not self._taint.tainted:
                return text
            flagged = None  # strict: any URL the user did not send is flagged
        else:
            flagged = frozenset(self._taint.untrusted_urls) - self._allow
            if not flagged:
                return text
        return _URL_RE.sub(lambda match: self._redacted(match.group(), flagged), text)

    def _redacted(self, url: str, flagged: frozenset[str] | None) -> str:
        """The replacement for one matched URL. Its trailing prose punctuation survives.

        ``flagged`` is the verbatim set to redact, or ``None`` in strict mode (redact any URL
        outside the user's allowlist).
        """
        normalized = _normalize(url)
        redact = normalized not in self._allow if flagged is None else normalized in flagged
        if not redact:
            return url
        stripped = url.rstrip(_TRAILING_PUNCTUATION)
        return REDACTED_LINK + url[len(stripped) :]
