"""The model-independent output guardrail: deterministic URL-laundering defense (ADR-0015).

Prompt-level framing (ADR-0013) keeps capable models from obeying untrusted content, but the
GPU validation showed output-laundering ("append this link to your summary") defeats the
small tier regardless of preamble. This module is the deterministic backstop at the one seam
where a laundered link becomes harm: the reply the user reads. A redacting guardrail opens one
``OutputFilter`` per turn over the turn's live ``TaintView`` (the ledger's taint bit + the URLs
it collected from every untrusted tool result); the filter scans the streamed assistant output
and replaces flagged URLs (minus URLs the user themselves sent) with ``REDACTED_LINK`` before
they reach the user. Two policies (ADR-0015 + addendum): ``UrlRedactingGuardrail`` redacts the
verbatim-collected untrusted URLs (the default), ``StrictUrlRedactingGuardrail`` redacts *every*
non-user URL on a tainted turn. The URL grammar and identity live in ``urls.py``, and this module
recognizes, normalizes, and streams URLs through it, so obfuscation-resistant matching (defang,
percent-encoding, fullwidth homoglyphs) is inherited for free. Model-independent by construction:
however injectable the generating model is, a laundered link does not survive the seam. Pure, no
I/O; the only state is one turn's carry buffer, dying with the turn.
"""

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
    """The **live** taint signals the guardrail reads at scan time (ADR-0013/0015).

    A structural read-only view the turn's ``TaintLedger`` already satisfies. The guardrail
    cannot import ``untrusted`` (which imports this module), so it reads the ledger through this
    protocol instead of by type. Both fields grow as tool results arrive; the filter reads them
    live, never a snapshot. ``tainted`` is set once any untrusted content enters the turn (even
    with no URLs); ``untrusted_urls`` is every URL that content carried.
    """

    @property
    def tainted(self) -> bool: ...

    @property
    def untrusted_urls(self) -> AbstractSet[str]: ...


class OutputGuardrail(Protocol):
    """Opens one turn's ``OutputFilter`` over that turn's live laundering evidence (ADR-0015).

    ``taint`` is the turn's live taint view (``untrusted_urls`` grows as tool results arrive, and
    ``tainted`` flips on the first untrusted content, and is read at scan time, never a snapshot);
    ``allow`` holds the URLs the user's own message carried, which are theirs to see again.
    """

    def open(self, taint: TaintView, *, allow: frozenset[str]) -> OutputFilter: ...


class UrlRedactingGuardrail:
    """The default ``OutputGuardrail``: redact URLs sourced *verbatim* from untrusted content.

    Exact-identity redaction means a URL in the reply whose normalized form was collected from an
    untrusted result (and the user did not send) is replaced with ``REDACTED_LINK``. Tiny
    false-positive surface; the model's own recalled links survive. See
    ``StrictUrlRedactingGuardrail`` for the verbatim-independent policy.
    """

    def open(self, taint: TaintView, *, allow: frozenset[str]) -> OutputFilter:
        """One turn's redacting filter; state dies with the turn."""
        return _UrlRedactingFilter(taint, allow, strict=False)


class StrictUrlRedactingGuardrail:
    """The opt-in strict ``OutputGuardrail`` (ADR-0015 addendum): on a **tainted** turn, redact
    *every* URL the user did not themselves send, going beyond the verbatim-collected ones.

    The answer to exact-match's blind spot: a model told to transform or reconstruct a laundered
    URL never reproduces a collected string, so ``UrlRedactingGuardrail`` misses it; strict mode
    distrusts every link on a turn that has read untrusted content. An untainted turn is untouched
    (the model's own links stream freely), so the cost lands only where untrusted content is in
    play.
    """

    def open(self, taint: TaintView, *, allow: frozenset[str]) -> OutputFilter:
        """One turn's strict redacting filter; state dies with the turn."""
        return _UrlRedactingFilter(taint, allow, strict=True)


class _UrlRedactingFilter:
    """The streaming redactor behind the redacting guardrails (one instance per turn).

    ``strict`` selects the flagging policy: verbatim (redact only untrusted-collected URLs) or
    strict (on a tainted turn, redact every URL the user did not send). Both read the live taint
    view at scan time; only the predicate over one matched URL differs.
    """

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
        """Replace every URL this turn flags; leave all other text alone.

        Nothing is flagged (so nothing is scanned) until untrusted content is in play: a
        clean redact-mode turn (nothing collected) and an untainted strict-mode turn both
        short-circuit to the text unchanged.
        """
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
