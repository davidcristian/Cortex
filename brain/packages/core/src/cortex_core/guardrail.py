"""The model-independent output guardrail: a deterministic defence against URL laundering."""

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from enum import Enum, auto
from typing import Protocol

from cortex_core.url_holdback import held_from
from cortex_core.url_identity import TRAILING_PUNCTUATION, host_of, normalize_url
from cortex_core.urls import URL_RE

REDACTED_LINK = "[link removed: untrusted source]"


class _Ground(Enum):
    """Why one URL in a reply is redacted; each policy below is a set of these."""

    COLLECTED = auto()
    LOOKALIKE = auto()
    LINK = auto()


# The grounds that need the turn to be tainted. COLLECTED is not one: a non-empty collected set
# is itself the evidence, and a turn cannot collect a URL without being marked tainted.
_ON_TAINT = frozenset({_Ground.LOOKALIKE, _Ground.LINK})

# What an opaque turn adds to the configured policy: a URL drawn into pixels is in no result
# text, so nothing is collected and no host is read, leaving LINK as the only ground left.
_ON_OPAQUE = frozenset({_Ground.LINK})


class OutputFilter(Protocol):
    """One turn's streaming output filter: ``feed`` each delta, ``flush`` at end of stream."""

    def feed(self, chunk: str) -> str: ...

    def flush(self) -> str: ...

    @property
    def policy(self) -> str:
        """The ``CORTEX_OUTPUT_GUARDRAIL`` name of the policy this filter applies."""
        ...

    def redactions(self) -> Mapping[str, int]:
        """How many URLs this filter has replaced so far, per ground, every ground named."""
        ...


class TaintView(Protocol):
    """The live taint signals the guardrail reads at scan time."""

    @property
    def tainted(self) -> bool: ...

    @property
    def opaque(self) -> bool: ...

    @property
    def untrusted_urls(self) -> AbstractSet[str]: ...


class OutputGuardrail(Protocol):
    """Opens one turn's ``OutputFilter`` over that turn's live laundering evidence."""

    def open(self, taint: TaintView, *, allow: frozenset[str]) -> OutputFilter: ...


class UrlRedactingGuardrail:
    """The default ``OutputGuardrail``: redact URLs sourced verbatim from untrusted content."""

    POLICY = "redact"

    def open(self, taint: TaintView, *, allow: frozenset[str]) -> OutputFilter:
        """One turn's redacting filter; its state lasts only for that turn."""
        return _UrlRedactingFilter(
            taint, allow, policy=self.POLICY, grounds=frozenset({_Ground.COLLECTED})
        )


class LookalikeUrlRedactingGuardrail:
    """The default policy plus the lookalike-host ground."""

    POLICY = "lookalike"

    def open(self, taint: TaintView, *, allow: frozenset[str]) -> OutputFilter:
        """One turn's redacting filter; its state lasts only for that turn."""
        return _UrlRedactingFilter(
            taint,
            allow,
            policy=self.POLICY,
            grounds=frozenset({_Ground.COLLECTED, _Ground.LOOKALIKE}),
        )


class StrictUrlRedactingGuardrail:
    """The optional strict ``OutputGuardrail``: on a tainted turn every link is redacted."""

    POLICY = "strict"

    def open(self, taint: TaintView, *, allow: frozenset[str]) -> OutputFilter:
        """One turn's strict redacting filter; its state lasts only for that turn."""
        return _UrlRedactingFilter(
            taint, allow, policy=self.POLICY, grounds=frozenset({_Ground.LINK})
        )


class _UrlRedactingFilter:
    """The streaming redactor behind the redacting guardrails (one instance per turn)."""

    def __init__(
        self,
        taint: TaintView,
        allow: frozenset[str],
        *,
        policy: str,
        grounds: frozenset[_Ground],
    ) -> None:
        self._taint = taint
        self._allow = allow
        self._policy = policy
        self._grounds = grounds
        self._pending = ""
        self._counts = dict.fromkeys(_Ground, 0)

    @property
    def policy(self) -> str:
        """The name of the policy this filter was opened under."""
        return self._policy

    def redactions(self) -> dict[str, int]:
        """The URLs replaced so far, keyed by each ground's lowercase name."""
        return {ground.name.lower(): count for ground, count in self._counts.items()}

    def feed(self, chunk: str) -> str:
        """Scrub and release the finished prefix; keep back what a later chunk might extend."""
        buf = self._pending + chunk
        held = held_from(buf)
        self._pending = buf[held:]
        return self._scrub(buf[:held])

    def flush(self) -> str:
        """End of stream: what was kept back is complete now, so scrub and release it."""
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
        """The replacement for one matched URL."""
        ground = self._flagged(url, collected, live)
        if ground is None:
            return url
        self._counts[ground] += 1
        stripped = url.rstrip(TRAILING_PUNCTUATION)
        return REDACTED_LINK + url[len(stripped) :]

    def _flagged(
        self, url: str, collected: frozenset[str], live: frozenset[_Ground]
    ) -> _Ground | None:
        """The first ground that applies to one matched URL, or ``None``."""
        identity = normalize_url(url)
        if identity in self._allow:
            return None
        if identity in collected:
            return _Ground.COLLECTED
        if _Ground.LINK in live:
            return _Ground.LINK
        if _Ground.LOOKALIKE not in live:
            return None
        ascii_host = host_of(normalize_url(url, confusables=False)).isascii()
        return None if ascii_host else _Ground.LOOKALIKE
