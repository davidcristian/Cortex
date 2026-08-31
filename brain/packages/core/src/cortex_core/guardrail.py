"""The model-independent output guardrail: deterministic URL-laundering defense (ADR-0015).

Prompt-level framing (ADR-0013) keeps capable models from obeying untrusted content, but the GPU
validation showed that output laundering ("append this link to your summary") defeats the small
tier whatever the preamble. This module is the deterministic backstop at the one seam where a
laundered link becomes harm: the reply the user reads. A redacting guardrail opens one
``OutputFilter`` per turn over the turn's live ``TaintView`` (the ledger's taint bit plus the URLs
it collected from every untrusted tool result); the filter scans the streamed assistant output and
replaces flagged URLs, minus the URLs the user themselves sent, with ``REDACTED_LINK`` before they
reach the user.

There are three policies (ADR-0015 and its addenda), each a set of the grounds below rather than a
mode: ``UrlRedactingGuardrail`` redacts the verbatim-collected untrusted URLs (the default),
``LookalikeUrlRedactingGuardrail`` adds every URL whose host is not plain ASCII on a tainted turn,
and ``StrictUrlRedactingGuardrail`` redacts every non-user URL on a tainted turn.

The URL grammar lives in ``urls.py``, its identity in ``url_identity.py`` and its streaming
hold-back in ``url_holdback.py``. This module recognizes, normalizes and streams URLs through
those, so obfuscation-resistant matching (defang, percent-encoding, fullwidth homoglyphs) comes
with them. Redaction happens after generation, which is why it does not depend on how injectable
the generating model is. Pure, no I/O; the only state is one turn's carry buffer, which dies with
the turn.
"""

from collections.abc import Set as AbstractSet
from enum import Enum, auto
from typing import Protocol

from cortex_core.url_holdback import held_from
from cortex_core.url_identity import TRAILING_PUNCTUATION, host_of, normalize_url
from cortex_core.urls import URL_RE

# What the user sees in place of a laundered link. Self-explanatory inline, so the overlay
# needs no extra event type to surface the redaction.
REDACTED_LINK = "[link removed: untrusted source]"


class _Ground(Enum):
    """Why one URL in a reply is redacted, and the unit a policy below is assembled from.

    A policy is a set of grounds rather than a mode, which is what let a third policy land without
    the seam moving (ADR-0015 fourteenth addendum): the grounds compose, an opaque turn adds one to
    whatever was configured, and each is a separate reason for redacting one matched URL rather
    than a branch through the other policies' code.
    """

    # Its identity was collected from this turn's untrusted content: verbatim laundering.
    COLLECTED = auto()
    # Its host is not plain ASCII once every resolver-faithful pass has run: a lookalike, and any
    # genuine internationalized domain caught with one, since no table separates the two.
    LOOKALIKE = auto()
    # It is a link at all, which on a tainted turn is grounds enough.
    LINK = auto()


# The grounds that need untrusted content to have entered the turn. `COLLECTED` is not among them:
# it needs no taint bit, because a non-empty collected set is itself the evidence and a turn cannot
# collect a URL without being marked tainted in the same call.
_ON_TAINT = frozenset({_Ground.LOOKALIKE, _Ground.LINK})

# What an opaque turn adds to whatever policy is configured (ADR-0029): a URL painted into pixels
# is in no result text, so nothing is collected and no host is read, which leaves `LINK` as the
# only ground that can apply.
_ON_OPAQUE = frozenset({_Ground.LINK})


class OutputFilter(Protocol):
    """One turn's streaming output filter: ``feed`` each delta, ``flush`` at end of stream.

    ``feed`` returns the (possibly rewritten, possibly empty) text safe to emit now; text a
    still-growing URL might extend is carried until a later ``feed`` or the final ``flush``.
    """

    def feed(self, chunk: str) -> str: ...

    def flush(self) -> str: ...


class TaintView(Protocol):
    """The live taint signals the guardrail reads at scan time (ADR-0013/0015).

    A structural read-only view the turn's ``TaintLedger`` already satisfies. The guardrail
    cannot import ``untrusted`` (which imports this module), so it reads the ledger through this
    protocol instead of by type. Both fields grow as tool results arrive; the filter reads them
    live, never a snapshot. ``tainted`` is set once any untrusted content enters the turn (even
    with no URLs); ``untrusted_urls`` is every URL that content carried; ``opaque`` is set when
    some of that content was unfenceable, which today means an image (ADR-0029).
    """

    @property
    def tainted(self) -> bool: ...

    @property
    def opaque(self) -> bool: ...

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
    """The default ``OutputGuardrail``: redact URLs sourced verbatim from untrusted content.

    Exact-identity redaction means a URL in the reply whose normalized form was collected from an
    untrusted result, and which the user did not send, is replaced with ``REDACTED_LINK``. The
    false-positive surface is small and the model's own recalled links stream through. See
    ``LookalikeUrlRedactingGuardrail`` for the same policy plus the homoglyph host an identity
    comparison cannot match, and ``StrictUrlRedactingGuardrail`` for the policy that does not
    depend on what was collected.
    """

    def open(self, taint: TaintView, *, allow: frozenset[str]) -> OutputFilter:
        """One turn's redacting filter; state dies with the turn."""
        return _UrlRedactingFilter(taint, allow, grounds=frozenset({_Ground.COLLECTED}))


class LookalikeUrlRedactingGuardrail:
    """The default policy plus one ground (ADR-0015 fourteenth addendum).

    On a tainted turn this also redacts a URL whose host is not plain ASCII, whatever this turn
    collected. It is the answer to a homoglyph host, and the one answer that does not depend on a
    table: an identity comparison catches a lookalike only when the fold reduces its characters to
    the twin that was collected, so an attacker picks a character the fold does not carry, and no
    table of any size covers every codepoint that could be chosen (measured: ADR-0015 thirteenth
    addendum). This ground is about the shape of what is emitted rather than about matching a
    collected string, so it applies whatever the identity: any host that is not the plain letters
    it appears to be is redacted, whichever codepoint was chosen.

    The cost is a genuine internationalized domain named on a tainted turn, which is redacted with
    the lookalikes because nothing without a script database separates the two. Measured on the
    Tranco top million: 0 of the top 1,000 hosts, 8 of the top 10,000, 1,441 of 1,000,000 (0.14%),
    and only on turns that have read untrusted content.
    """

    def open(self, taint: TaintView, *, allow: frozenset[str]) -> OutputFilter:
        """One turn's redacting filter; state dies with the turn."""
        return _UrlRedactingFilter(
            taint, allow, grounds=frozenset({_Ground.COLLECTED, _Ground.LOOKALIKE})
        )


class StrictUrlRedactingGuardrail:
    """The opt-in strict ``OutputGuardrail`` (ADR-0015 addendum).

    On a tainted turn this redacts every URL the user did not themselves send, going beyond the
    verbatim-collected ones. It covers what exact matching cannot: a model told to transform or
    reconstruct a laundered URL never reproduces a collected string, so ``UrlRedactingGuardrail``
    does not match it, while strict mode distrusts every link on a turn that has read untrusted
    content. An untainted turn is untouched (the model's own links stream freely), so the cost
    lands only where untrusted content is in play.
    """

    def open(self, taint: TaintView, *, allow: frozenset[str]) -> OutputFilter:
        """One turn's strict redacting filter; state dies with the turn."""
        return _UrlRedactingFilter(taint, allow, grounds=frozenset({_Ground.LINK}))


class _UrlRedactingFilter:
    """The streaming redactor behind the redacting guardrails (one instance per turn).

    ``grounds`` is the policy: the set of ``_Ground`` members this turn may redact a URL on. Every
    policy reads the live taint view at scan time and shares this whole streaming path; what
    differs between them is only which grounds may flag a matched URL.
    """

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
        """Replace every URL this turn flags; leave all other text alone.

        Nothing is flagged (so nothing is scanned) until untrusted content is in play: a clean
        turn under any policy returns the text unchanged, whether because nothing was collected or
        because no taint-borne ground applies.

        An opaque turn is scanned strictly whatever the configured policy (ADR-0029). The default
        policy redacts URLs collected from untrusted result text, and a URL painted into pixels is
        never in that text, so ``untrusted_urls`` is empty and the default is a no-op for exactly
        the laundering case vision introduces. Measured: the model transcribes an attacker URL out
        of an image verbatim, framed or not. Strict redaction, which flags every URL the user did
        not send, is the policy that catches it.
        """
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
        """Whether any ground this scan stands on holds for one matched URL.

        The user's own links are checked first, by every policy alike: a URL they sent is theirs
        to see again however it was spelled. ``collected`` is this turn's laundering evidence,
        already less the allowlist; ``live`` is the taint-borne grounds. The lookalike ground reads
        the host from an identity built without the confusable fold, so a host spelled wholly in
        table entries is still read as the letters it was written in rather than as the ASCII twin
        the fold would show (ADR-0015 fourteenth addendum).
        """
        identity = normalize_url(url)
        if identity in self._allow:
            return False
        if identity in collected or _Ground.LINK in live:
            return True
        return (
            _Ground.LOOKALIKE in live
            and not host_of(normalize_url(url, confusables=False)).isascii()
        )
