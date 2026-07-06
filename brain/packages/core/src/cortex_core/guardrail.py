"""The model-independent output guardrail: deterministic URL-laundering defense (ADR-0015)."""

from collections.abc import Set as AbstractSet
from typing import Protocol

from cortex_core.urls import TRAILING_PUNCTUATION, URL_RE, held_from, normalize_url

# What the user sees in place of a laundered link. Self-explanatory inline, so the overlay
# needs no extra event type to surface the redaction.
REDACTED_LINK = "[link removed: untrusted source]"


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
        held = held_from(buf)
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
        return URL_RE.sub(lambda match: self._redacted(match.group(), flagged), text)

    def _redacted(self, url: str, flagged: frozenset[str] | None) -> str:
        """The replacement for one matched URL. Its trailing prose punctuation survives.

        ``flagged`` is the verbatim set to redact, or ``None`` in strict mode (redact any URL
        outside the user's allowlist).
        """
        normalized = normalize_url(url)
        redact = normalized not in self._allow if flagged is None else normalized in flagged
        if not redact:
            return url
        stripped = url.rstrip(TRAILING_PUNCTUATION)
        return REDACTED_LINK + url[len(stripped) :]
