"""The model-independent output guardrail: deterministic URL-laundering defense (ADR-0015)."""

from collections.abc import Set as AbstractSet
from enum import Enum, auto
from typing import Protocol

from cortex_core.url_identity import TRAILING_PUNCTUATION, host_of, normalize_url
from cortex_core.urls import URL_RE, held_from

# What the user sees in place of a laundered link. Self-explanatory inline, so the overlay
# needs no extra event type to surface the redaction.
REDACTED_LINK = "[link removed: untrusted source]"


class _Ground(Enum):
    """Why one URL in a reply is redacted, and the unit a policy below is assembled from."""

    # Its identity was collected from this turn's untrusted content: verbatim laundering.
    COLLECTED = auto()
    # Its host is not plain ASCII once every resolver-faithful pass has run: a lookalike, and any
    # genuine internationalized domain caught with one, since no table separates the two.
    LOOKALIKE = auto()
    # It is a link at all, which on a tainted turn is grounds enough.
    LINK = auto()


# The grounds that need untrusted content to have entered the turn. `COLLECTED` is not among them:
# it needs no taint *bit* because a non-empty collected set is itself the evidence, and a turn
# cannot collect a URL without being marked tainted in the same call.
_ON_TAINT = frozenset({_Ground.LOOKALIKE, _Ground.LINK})

# What an **opaque** turn adds to whatever policy is configured (ADR-0029): a URL painted into
# pixels is in no result text, so nothing is collected and no host is read, and distrusting every
# link is the only ground left standing.
_ON_OPAQUE = frozenset({_Ground.LINK})


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
    def opaque(self) -> bool: ...

    @property
    def untrusted_urls(self) -> AbstractSet[str]: ...


class OutputGuardrail(Protocol):
    """Opens one turn's ``OutputFilter`` over that turn's live laundering evidence (ADR-0015)."""

    def open(self, taint: TaintView, *, allow: frozenset[str]) -> OutputFilter: ...


class UrlRedactingGuardrail:
    """The default ``OutputGuardrail``: redact URLs sourced *verbatim* from untrusted content."""

    def open(self, taint: TaintView, *, allow: frozenset[str]) -> OutputFilter:
        """One turn's redacting filter; state dies with the turn."""
        return _UrlRedactingFilter(taint, allow, grounds=frozenset({_Ground.COLLECTED}))


class LookalikeUrlRedactingGuardrail:
    """The default policy plus one ground (ADR-0015 fourteenth addendum): on a **tainted** turn,
    also redact a URL whose **host is not plain ASCII**, whatever this turn collected.
    """

    def open(self, taint: TaintView, *, allow: frozenset[str]) -> OutputFilter:
        """One turn's redacting filter; state dies with the turn."""
        return _UrlRedactingFilter(
            taint, allow, grounds=frozenset({_Ground.COLLECTED, _Ground.LOOKALIKE})
        )


class StrictUrlRedactingGuardrail:
    """The opt-in strict ``OutputGuardrail`` (ADR-0015 addendum): on a **tainted** turn, redact
    *every* URL the user did not themselves send, going beyond the verbatim-collected ones.
    """

    def open(self, taint: TaintView, *, allow: frozenset[str]) -> OutputFilter:
        """One turn's strict redacting filter; state dies with the turn."""
        return _UrlRedactingFilter(taint, allow, grounds=frozenset({_Ground.LINK}))


class _UrlRedactingFilter:
    """The streaming redactor behind the redacting guardrails (one instance per turn)."""

    def __init__(
        self, taint: TaintView, allow: frozenset[str], *, grounds: frozenset[_Ground]
    ) -> None:
        self._taint = taint
        self._allow = allow
        self._grounds = grounds
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
        grounds = (self._grounds | _ON_OPAQUE) if self._taint.opaque else self._grounds
        collected = (
            frozenset(self._taint.untrusted_urls) - self._allow
            if _Ground.COLLECTED in grounds
            else frozenset[str]()
        )
        live = (grounds & _ON_TAINT) if self._taint.tainted else frozenset[_Ground]()
        if not collected and not live:
            return text
        return URL_RE.sub(lambda match: self._redacted(match.group(), collected, live), text)

    def _redacted(self, url: str, collected: frozenset[str], live: frozenset[_Ground]) -> str:
        """The replacement for one matched URL. Its trailing prose punctuation survives."""
        if not self._flagged(url, collected, live):
            return url
        stripped = url.rstrip(TRAILING_PUNCTUATION)
        return REDACTED_LINK + url[len(stripped) :]

    def _flagged(self, url: str, collected: frozenset[str], live: frozenset[_Ground]) -> bool:
        """Whether any ground this scan stands on holds for one matched URL."""
        identity = normalize_url(url)
        if identity in self._allow:
            return False
        if identity in collected or _Ground.LINK in live:
            return True
        return (
            _Ground.LOOKALIKE in live
            and not host_of(normalize_url(url, confusables=False)).isascii()
        )
