"""The model-independent output guardrail: deterministic URL-laundering defense (ADR-0015)."""

import re
from collections.abc import Set as AbstractSet
from typing import Protocol

_URL_RE = re.compile(r"https?://[^\s<>\"'\)\]\}]+", re.IGNORECASE)

# Prose punctuation a URL match may drag along at its end is part of the sentence, never of
# the URL identity, and preserved outside a redaction.
_TRAILING_PUNCTUATION = ".,;:!?"

# Ends the authority (host[:port]) component: from here on a URL is case-sensitive.
_AUTHORITY_END = re.compile(r"[/?#]")

# The longest string that is a prefix of a scheme+separator but not yet a URL match
# ("https://" needs one more character to match _URL_RE). It is the stream filter's hold-back bound.
_LONGEST_OPEN_PREFIX = len("https://")

# What the user sees in place of a laundered link. Self-explanatory inline, so the overlay
# needs no extra event type to surface the redaction.
REDACTED_LINK = "[link removed: untrusted source]"


def _normalize(url: str) -> str:
    """One URL's identity: trailing prose punctuation dropped, scheme+authority lowercased.

    The path/query/fragment keep their case (URL semantics). Laundering is verbatim
    reproduction, so exact-but-case-normalized identity is the right match.
    """
    trimmed = url.rstrip(_TRAILING_PUNCTUATION)
    head, sep, tail = trimmed.partition("://")
    cut = _AUTHORITY_END.search(tail)
    if cut is None:
        return f"{head.lower()}{sep}{tail.lower()}"
    return f"{head.lower()}{sep}{tail[: cut.start()].lower()}{tail[cut.start() :]}"


def extract_urls(text: str) -> frozenset[str]:
    """Every absolute http(s) URL in ``text``, normalized for identity comparison."""
    return frozenset(_normalize(match.group()) for match in _URL_RE.finditer(text))


class OutputFilter(Protocol):
    """One turn's streaming output filter: ``feed`` each delta, ``flush`` at end of stream.

    ``feed`` returns the (possibly rewritten, possibly empty) text safe to emit now; text a
    still-growing URL might extend is carried until a later ``feed`` or the final ``flush``.
    """

    def feed(self, chunk: str) -> str: ...

    def flush(self) -> str: ...


class OutputGuardrail(Protocol):
    """Opens one turn's ``OutputFilter`` over that turn's laundering evidence (ADR-0015)."""

    def open(self, untrusted_urls: AbstractSet[str], *, allow: frozenset[str]) -> OutputFilter: ...


class UrlRedactingGuardrail:
    """The shipped ``OutputGuardrail``: replace untrusted-sourced URLs with ``REDACTED_LINK``."""

    def open(self, untrusted_urls: AbstractSet[str], *, allow: frozenset[str]) -> OutputFilter:
        """One turn's redacting filter; state dies with the turn."""
        return _UrlRedactingFilter(untrusted_urls, allow)


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
        if "https://".startswith(suffix) or "http://".startswith(suffix):
            return len(buf) - size
    return len(buf)


class _UrlRedactingFilter:
    """The streaming redactor behind ``UrlRedactingGuardrail`` (one instance per turn)."""

    def __init__(self, untrusted_urls: AbstractSet[str], allow: frozenset[str]) -> None:
        self._untrusted_urls = untrusted_urls
        self._allow = allow
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
        """Replace every URL sourced only from untrusted content; leave all other text alone."""
        flagged = self._untrusted_urls - self._allow
        if not flagged:
            return text
        return _URL_RE.sub(lambda match: self._redacted(match.group(), flagged), text)

    @staticmethod
    def _redacted(url: str, flagged: AbstractSet[str]) -> str:
        """The replacement for one matched URL. Its trailing prose punctuation survives."""
        if _normalize(url) not in flagged:
            return url
        stripped = url.rstrip(_TRAILING_PUNCTUATION)
        return REDACTED_LINK + url[len(stripped) :]
